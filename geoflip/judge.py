"""OpenAI-compatible chat-completions transport; no provider credentials stored."""
from pathlib import Path
import json
from .core import digest
from .media import image_url


def assets():
    return Path(__file__).parent / 'prompts'


def render_prompt(task, span, count):
    specs = json.loads((assets() / 'tasks.json').read_text())
    spec = specs[task]
    definitions = '\n'.join(f'{lab}: {spec["label_definitions"][lab]}' for lab in spec['allowed_labels'] if lab in spec['label_definitions'])
    if not definitions:
        definitions = 'stable: visibly stays at initial position and orientation throughout the shown window.'
    return (assets() / 'judge.txt').read_text().rstrip('\n').format(
        n=count, span=span, event=spec['event'], labels=spec['allowed_labels'], definitions=definitions)


def prompt_fingerprint():
    return {'template_sha256': digest(assets() / 'judge.txt'), 'tasks_sha256': digest(assets() / 'tasks.json')}


def parse_answer(text):
    if not isinstance(text, str):
        raise ValueError('Judge content must be text')
    text = text.strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines[-1].strip() != '```':
            raise ValueError('Unclosed JSON code block')
        text = '\n'.join(lines[1:-1])
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get('label'), str):
        raise ValueError('Judge answer requires a label')
    if data.get('violation') not in {'clear', 'flagged', 'uncertain'}:
        raise ValueError('Invalid structural label')
    confidence = data.get('confidence')
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError('Confidence must be a number between zero and one')
    if not isinstance(data.get('evidence'), str) or not data['evidence'].strip():
        raise ValueError('Judge answer needs visual evidence')
    return {key: data[key] for key in ('label', 'violation', 'confidence', 'evidence')}


def request_judgment(base_url, model, api_key, images, prompt, timeout=180):
    import requests
    from urllib.parse import urlsplit
    parsed = urlsplit(base_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Provide a plain chat-completions base URL')
    from ipaddress import ip_address
    host = parsed.hostname
    try:
        local = host == 'localhost' or ip_address(host).is_loopback
    except ValueError:
        local = False
    if parsed.scheme == 'http' and not local:
        raise ValueError('Remote judge endpoints require HTTPS')
    body = {'model': model, 'temperature': 0, 'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': [
                *[{'type': 'image_url', 'image_url': {'url': image_url(im)}} for im in images],
                {'type': 'text', 'text': prompt}]}]}
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    # One request per call; errors never trigger undisclosed paid retries.
    response = requests.post(base_url.rstrip('/') + '/chat/completions', headers=headers,
                             json=body, timeout=timeout, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f'Judge HTTP status {response.status_code}')
    try:
        content = response.json()['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('Invalid chat-completions response') from None
    parsed_answer = parse_answer(content)
    served_model = response.json().get('model')
    if isinstance(served_model, str):
        parsed_answer['served_model'] = served_model
    return parsed_answer
