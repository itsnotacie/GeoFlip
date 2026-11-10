from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import base64
import io
import json
import os
import sys

import pytest
from geoflip.cli import main
from geoflip.core import read_jsonl, write_json, write_jsonl
from geoflip.judge import parse_answer, render_prompt


def video(path, color, frames=32, fps=16):
    import av
    import numpy as np
    with av.open(str(path), 'w') as container:
        stream = container.add_stream('libx264', rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
        for _ in range(frames):
            array = np.zeros((48, 64, 3), dtype='uint8')
            array[:, :, color] = 220
            for packet in stream.encode(av.VideoFrame.from_ndarray(array, format='rgb24')):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / 'dataset'
    root.mkdir()
    truth = [{'id': 'a', 'task': 'table_overhang', 'reference_label': 'stable', 'allowed_labels': ['stable', 'fell'],
              'pair_id': 'p', 'observation_time_s': .5, 'reference_video': 'a.mp4'},
             {'id': 'b', 'task': 'table_overhang', 'reference_label': 'fell', 'allowed_labels': ['stable', 'fell'],
              'pair_id': 'p', 'observation_time_s': .5, 'reference_video': 'b.mp4'}]
    write_jsonl(root / 'evaluation/truth.jsonl', truth)
    write_json(root / 'splits/core.json', ['a', 'b'])
    video(root / 'a.mp4', 0)
    video(root / 'b.mp4', 2)
    write_json(root / 'submission.json', {'model': 'fixture', 'videos': [{'id': 'a', 'video': 'a.mp4'}, {'id': 'b', 'video': 'b.mp4'}]})
    return root


def test_video_validate_and_identical_pixel_diagnostic(dataset, tmp_path):
    assert main(['validate', '--data', str(dataset), '--subset', 'core', '--submission', str(dataset / 'submission.json'), '--out', str(tmp_path / 'v.json')]) == 0
    report = json.loads((tmp_path / 'v.json').read_text())
    assert report['valid'] == 2
    assert all(v['covers_observation_time'] for v in report['videos'])
    assert main(['similarity', '--data', str(dataset), '--subset', 'core', '--submission', str(dataset / 'submission.json'), '--out', str(tmp_path / 'pixel.json')]) == 0
    similarity = json.loads((tmp_path / 'pixel.json').read_text())
    assert similarity['mean']['psnr'] == 99
    assert similarity['mean']['ssim'] == pytest.approx(1)


def test_prompt_and_parser():
    text = render_prompt('table_overhang', 1.5, 8)
    assert 'These 8' in text and 'first 1.500 seconds' in text
    assert 'reference_label' not in text and 'pair_id' not in text
    answer = {'label': 'fell', 'violation': 'clear', 'confidence': .9, 'evidence': 'Visible descent.'}
    assert parse_answer('```json\n' + json.dumps(answer) + '\n```') == answer
    for mutation in [{'confidence': True}, {'confidence': 2}, {'violation': 'yes'}, {'evidence': ''}]:
        with pytest.raises(ValueError):
            parse_answer(json.dumps(dict(answer, **mutation)))


def test_judge_http_resume_and_missing_denominator(dataset, tmp_path, monkeypatch):
    from PIL import Image
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(body)
            content = body['messages'][0]['content']
            prompt = content[-1]['text']
            assert 'reference_label' not in prompt and 'pair_id' not in prompt
            raw = base64.b64decode(content[0]['image_url']['url'].split(',')[1])
            color = Image.open(io.BytesIO(raw)).getpixel((1, 1))
            label = 'stable' if color[0] > color[2] else 'fell'
            answer = {'label': label, 'violation': 'clear', 'confidence': .9, 'evidence': 'Synthetic transport fixture.'}
            payload = json.dumps({'model': 'fixture-v1', 'choices': [{'message': {'content': json.dumps(answer)}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('localhost', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f'http://{server.server_address[0]}:{server.server_address[1]}/v1'
    args = ['judge', '--data', str(dataset), '--subset', 'core', '--submission', str(dataset / 'submission.json'),
            '--base-url', endpoint, '--model', 'fixture-v1', '--allow-no-key', '--out', str(tmp_path / 'judged.jsonl')]
    try:
        assert main(args) == 0
        assert len(calls) == 2
        assert main(args) == 0
        assert len(calls) == 2  # successful responses reused only with identical identity
        assert json.loads((tmp_path / 'judged.report.json').read_text())['event_percent'] == 100
        # Change a video while keeping its id; cached judgment must be invalidated.
        video(dataset / 'a.mp4', 2)
        assert main(args) == 0
        assert len(calls) == 3
        assert json.loads((tmp_path / 'judged.report.json').read_text())['event_percent'] == 50
        # Missing files remain in both event and structure denominators.
        (dataset / 'b.mp4').unlink()
        assert main(args) == 1
        result = json.loads((tmp_path / 'judged.report.json').read_text())
        assert result['n'] == 2 and result['errors'] == 1
        assert result['structure_percent'] == 50
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_download_pins_commit_and_hashes(tmp_path, monkeypatch):
    import huggingface_hub
    from geoflip.download import download
    from geoflip.core import digest
    calls = []
    def snapshot_download(**kwargs):
        calls.append(kwargs)
        output = Path(kwargs['local_dir']); output.mkdir(exist_ok=True)
        (output / 'README.md').write_text('fixture')
        write_json(output / 'SHA256SUMS.json', {'README.md': digest(output / 'README.md')})
    class Api:
        def __init__(self, **kwargs): pass
        def dataset_info(self, **kwargs):
            class Info: sha = 'frozen-fixture-commit'
            return Info()
    monkeypatch.setattr(huggingface_hub, 'HfApi', Api)
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', snapshot_download)
    result = download('fixture/dataset', tmp_path / 'download')
    assert result['commit'] == 'frozen-fixture-commit' and result['verified_files'] == 1
    assert calls[0]['revision'] == 'frozen-fixture-commit'
    assert not any('evaluation' in pattern or 'references' in pattern for pattern in calls[0]['allow_patterns'])


def test_download_rejects_mixed_revisions(tmp_path, monkeypatch):
    import huggingface_hub
    from geoflip.download import download
    write_json(tmp_path / 'DOWNLOAD_REVISION.json', {'repo_id': 'fixture/dataset', 'commit': 'old-fixture-commit'})
    class Api:
        def __init__(self, **kwargs): pass
        def dataset_info(self, **kwargs):
            class Info: sha = 'new-fixture-commit'
            return Info()
    monkeypatch.setattr(huggingface_hub, 'HfApi', Api)
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', lambda **kwargs: pytest.fail('must reject before download'))
    with pytest.raises(ValueError, match='different dataset revision'):
        download('fixture/dataset', tmp_path)
