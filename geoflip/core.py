"""Deterministic paper metrics, independent of the video reader and judge."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('Each JSONL row must be an object')
            rows.append(row)
    return rows


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    atomic_text(path, ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inside(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute():
        raise ValueError('Dataset paths must be relative')
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Dataset path leaves the dataset directory')
    return target


def unique(rows, name='rows'):
    result = {}
    for row in rows:
        sid = row.get('id')
        if not isinstance(sid, str) or not sid:
            raise ValueError(f'{name}: each record needs a nonempty id')
        if sid in result:
            raise ValueError(f'{name}: duplicate id')
        result[sid] = row
    return result


def load_truth(root, subset='core'):
    if not subset or any(c not in 'abcdefghijklmnopqrstuvwxyz-' for c in subset):
        raise ValueError('Invalid subset name')
    rows = unique(read_jsonl(Path(root) / 'evaluation/truth.jsonl'), 'truth')
    ids = json.loads((Path(root) / 'splits' / (subset + '.json')).read_text())
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ValueError('Subset must contain distinct, nonempty condition ids')
    if any(sid not in rows for sid in ids):
        raise ValueError('Subset contains unknown ids')
    selected = [rows[sid] for sid in ids]
    for row in selected:
        if row['reference_label'] not in row['allowed_labels']:
            raise ValueError('Truth label is outside the task taxonomy')
    return selected


def score(truth, predictions):
    truth_map = unique(truth, 'truth')
    pred = unique(predictions, 'predictions')
    if not truth_map:
        raise ValueError('Empty evaluation set')
    if set(pred) - set(truth_map):
        raise ValueError('Prediction id is outside the requested subset')
    valid_pred = {sid: row for sid, row in pred.items() if not row.get('error_type') and not row.get('error')}
    by_task = defaultdict(list)
    for row in truth:
        by_task[row['task']].append(row)
    correct = {r['id']: valid_pred.get(r['id'], {}).get('label') == r['reference_label'] for r in truth}
    tasks = {}
    for task, rows in sorted(by_task.items()):
        by_label = defaultdict(list)
        for row in rows:
            by_label[row['reference_label']].append(row)
        recalls = {lab: sum(correct[r['id']] for r in rs) / len(rs) for lab, rs in sorted(by_label.items())}
        clear = sum(valid_pred.get(r['id'], {}).get('violation') == 'clear' for r in rows)
        tasks[task] = {'n': len(rows), 'class_counts': {lab: len(rs) for lab, rs in sorted(by_label.items())},
                       'recall_by_label': recalls, 'event': sum(recalls.values()) / len(recalls),
                       'structure': clear / len(rows)}
    pairs = defaultdict(list)
    for row in truth:
        if row.get('pair_id'):
            pairs[row['pair_id']].append(row)
    complete = [rs for rs in pairs.values() if len(rs) == 2]
    return {'n': len(truth), 'tasks': len(tasks),
            'event_percent': 100 * sum(t['event'] for t in tasks.values()) / len(tasks),
            'structure_percent': 100 * sum(t['structure'] for t in tasks.values()) / len(tasks),
            'prediction_coverage': len(valid_pred) / len(truth),
            'failed': len(pred) - len(valid_pred),
            'missing': len(truth_map.keys() - pred.keys()),
            'complete_pairs': len(complete),
            'pair_complete_accuracy': sum(all(correct[r['id']] for r in rs) for rs in complete) / len(complete) if complete else None,
            'per_task': tasks}


def average_ranks(values, descending=True):
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError('Ranks require finite scores')
    order = sorted(range(len(values)), key=values.__getitem__, reverse=descending)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in order[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def overall_ranking(rows):
    """Only combine event/structure with independently supplied 40-clip metrics."""
    ranks = {key: average_ranks([float(r[key]) for r in rows]) for key in ('event', 'structure', 'psnr', 'ssim')}
    means = [(ranks['event'][i] + ranks['structure'][i] + (ranks['psnr'][i] + ranks['ssim'][i]) / 2) / 3 for i in range(len(rows))]
    ordered = sorted(range(len(rows)), key=means.__getitem__)
    return [dict(rows[i], mean_rank=means[i], rank=1 + sum(v < means[i] - 1e-12 for v in means)) for i in ordered]


def read_submission(path):
    path = Path(path).resolve()
    if path.suffix == '.jsonl':
        records = read_jsonl(path)
        metadata = {}
    else:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or not isinstance(data.get('videos'), list):
            raise ValueError('Submission JSON needs a videos array')
        records, metadata = data['videos'], {k: v for k, v in data.items() if k != 'videos'}
    records = unique(records, 'submission')
    for row in records.values():
        if not isinstance(row.get('video'), str) or not row['video']:
            raise ValueError('Each submission record needs a video path')
    return path.parent, records, metadata
