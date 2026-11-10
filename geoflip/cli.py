"""Public CLI for validating and scoring world-model generated videos."""
from pathlib import Path
import argparse
import hashlib
import json
import os

from .core import (digest, inside, load_truth, overall_ranking, read_jsonl,
                   read_submission, score, unique, write_json, write_jsonl)


def checked_submission(data, subset, submission):
    truth = load_truth(data, subset)
    parent, videos, metadata = read_submission(submission)
    allowed = {r['id'] for r in truth}
    if set(videos) - allowed:
        raise ValueError('Submission contains ids outside the selected subset')
    return truth, parent, videos, metadata


def validate(args):
    from .media import inspect_video
    truth, parent, videos, _ = checked_submission(args.data, args.subset, args.submission)
    rows = []
    for item in truth:
        sid = item['id']
        if sid not in videos:
            rows.append({'id': sid, 'status': 'missing'})
            continue
        path = parent / videos[sid]['video']
        try:
            info = inspect_video(path)
            info.pop('timestamps_s')
            rows.append({'id': sid, 'status': 'ok', 'video_sha256': digest(path), **info,
                         'covers_observation_time': info['last_timestamp_s'] + 0.001 >= item['observation_time_s']})
        except Exception as error:
            rows.append({'id': sid, 'status': 'invalid', 'error_type': type(error).__name__})
    result = {'subset': args.subset, 'conditions': len(truth),
              'valid': sum(r['status'] == 'ok' for r in rows),
              'missing': sum(r['status'] == 'missing' for r in rows),
              'invalid': sum(r['status'] == 'invalid' for r in rows), 'videos': rows}
    write_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'videos'}))
    return 1 if result['invalid'] or result['missing'] else 0


def judge(args):
    from .judge import prompt_fingerprint, render_prompt, request_judgment
    from .media import sample_video
    truth, parent, videos, metadata = checked_submission(args.data, args.subset, args.submission)
    previous = unique(read_jsonl(args.out)) if args.out.exists() else {}
    output = []
    fingerprints = prompt_fingerprint()
    if args.api_key_env not in os.environ and not args.allow_no_key:
        raise ValueError('Set the judge API key environment variable, or use --allow-no-key for a local server')
    api_key = os.environ.get(args.api_key_env)
    if not api_key and not args.allow_no_key:
        raise ValueError('Judge API key environment variable is empty')
    for row in truth:
        sid = row['id']
        answer = {'id': sid, 'label': 'uncertain', 'violation': 'uncertain'}
        try:
            if sid not in videos:
                raise FileNotFoundError('Missing submitted video')
            path = parent / videos[sid]['video']
            window = 119/30 if args.profile == 'paper-prefix-8' else max(119/30, row['observation_time_s'])
            import av
            import PIL
            identity = {'video_sha256': digest(path), 'observation_time_s': row['observation_time_s'],
                        'window_s': window, 'sampler_sha256': digest(Path(__file__).with_name('media.py')),
                        'transport_sha256': digest(Path(__file__).with_name('judge.py')),
                        'decoder_version': av.__version__, 'image_library_version': PIL.__version__, 'task': row['task'], 'model': args.model,
                        'endpoint_sha256': hashlib.sha256(args.base_url.encode()).hexdigest(),
                        'frames': 8, 'profile': args.profile, **fingerprints}
            if previous.get(sid, {}).get('identity') == identity and not previous[sid].get('error_type'):
                output.append(previous[sid])
                continue
            images, info = sample_video(path, count=8, window=window)
            prompt = render_prompt(row['task'], info['sampled_times_s'][-1], len(images))
            # In the observation profile, do not ask a judge to guess an unseen event time.
            if args.profile == 'observation-8' and info['sampled_times_s'][-1] + 0.001 < row['observation_time_s']:
                answer.update(identity=identity, sampling=info, error_type='InsufficientObservationWindow')
            else:
                parsed = request_judgment(args.base_url, args.model, api_key, images, prompt)
                answer.update(parsed, identity=identity, sampling=info,
                              prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                              covers_observation_time=info['sampled_times_s'][-1] + 0.001 >= row['observation_time_s'])
        except Exception as error:
            # Error details may contain private URLs, paths, or provider diagnostics.
            answer['error_type'] = type(error).__name__
        output.append(answer)
        write_jsonl(args.out, output)
    write_jsonl(args.out, output)
    report = score(truth, output)
    report.update(subset=args.subset, judge_model=args.model, sampling_profile=args.profile,
                  prompt_fingerprints=fingerprints,
                  errors=sum(bool(r.get('error_type')) for r in output))
    write_json(args.out.with_suffix('.report.json'), report)
    print(json.dumps({k: report[k] for k in ['n', 'event_percent', 'structure_percent', 'errors']}))
    return int(bool(report['errors']))


def scoring(args):
    truth = load_truth(args.data, args.subset)
    report = score(truth, read_jsonl(args.predictions))
    report.update(subset=args.subset, truth_sha256=digest(args.data / 'evaluation/truth.jsonl'),
                  subset_sha256=digest(args.data / 'splits' / (args.subset + '.json')))
    write_json(args.out, report)
    print(json.dumps({k: report[k] for k in ['n', 'tasks', 'event_percent', 'structure_percent', 'missing']}))
    return 0


def baseline(args):
    truth = load_truth(args.data, args.subset)
    rows = read_jsonl(args.data / 'baselines/judgments.jsonl')
    selected = [r for r in rows if r['subset'] == args.subset and r['judge'] == args.judge]
    models = sorted({r['model'] for r in selected})
    if not models:
        raise ValueError('No frozen baseline judgments for this subset/judge')
    results = [{'model': m, **score(truth, [r for r in selected if r['model'] == m])} for m in models]
    write_json(args.out, {'subset': args.subset, 'judge': args.judge, 'models': results})
    print(f'Rescored {len(models)} frozen model results on {len(truth)} conditions.')
    return 0


def similarity(args):
    from .similarity import compare_videos
    truth, parent, videos, _ = checked_submission(args.data, args.subset, args.submission)
    output = []
    for row in truth:
        result = {'id': row['id']}
        try:
            if row['id'] not in videos:
                raise FileNotFoundError('Missing submitted video')
            result.update(compare_videos(parent / videos[row['id']]['video'], inside(args.data, row['reference_video'])))
        except Exception as error:
            result['error_type'] = type(error).__name__
        output.append(result)
    valid = [r for r in output if 'error_type' not in r]
    write_json(args.out, {'subset': args.subset, 'benchmark': 'geoflip-reference-diagnostic',
                         'expected': len(truth), 'scored': len(valid), 'errors': len(output) - len(valid),
                         'mean': {k: sum(r[k] for r in valid) / len(valid) if valid else None for k in ['mse', 'psnr', 'ssim']},
                         'per_condition': output})
    print(f'Compared {len(valid)}/{len(truth)} conditions. This is separate from paper 40-clip similarity.')
    return int(len(valid) != len(truth))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name, callback in [('validate', validate), ('judge', judge), ('score', scoring), ('baselines', baseline), ('similarity', similarity)]:
        sub = commands.add_parser(name)
        sub.set_defaults(callback=callback)
        sub.add_argument('--data', type=Path, required=True)
        sub.add_argument('--subset', default='paper-main', choices=['core', 'auxiliary', 'paper-main', 'cross-judge', 'paper-pool'])
        if name in {'validate', 'judge', 'similarity'}:
            sub.add_argument('--submission', type=Path, required=True)
        if name in {'validate', 'judge', 'score', 'baselines', 'similarity'}:
            sub.add_argument('--out', type=Path, required=True)
        if name == 'judge':
            sub.add_argument('--base-url', required=True, help='Chat-completions API base, ending in /v1 if applicable')
            sub.add_argument('--model', required=True, help='Explicit judge model/version served by your endpoint')
            sub.add_argument('--api-key-env', default='GEOFLIP_JUDGE_API_KEY')
            sub.add_argument('--allow-no-key', action='store_true')
            sub.add_argument('--profile', choices=['observation-8', 'paper-prefix-8'], default='observation-8')
        elif name == 'score':
            sub.add_argument('--predictions', type=Path, required=True)
        elif name == 'baselines':
            sub.add_argument('--judge', choices=['gpt-6-astra', 'Qwen3-VL-32B-Instruct'], default='gpt-6-astra')
    ranking = commands.add_parser('rank')
    ranking.add_argument('--results', type=Path, required=True, help='JSON array: model, event, structure, psnr, ssim')
    ranking.add_argument('--out', type=Path, required=True)
    ranking.set_defaults(callback=lambda a: write_json(a.out, overall_ranking(json.loads(a.results.read_text()))) or 0)
    args = parser.parse_args(argv)
    try:
        return args.callback(args)
    except (ValueError, KeyError, FileNotFoundError, ImportError) as error:
        parser.exit(2, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
