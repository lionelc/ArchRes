"""Runs a frontier builder through the Anthropic Messages API on the same blinded prompts as run_builder.py.

  GAPCR_ANTHROPIC_KEY_FILE=/mnt/session/uploads/anthropic_api_key.txt python3 run_builder_anthropic.py [--model ID] SAMPLES...
  e.g. ... run_builder_anthropic.py 1 2      writes outputs_frontier/<gap>__s<sample>.json

The key is read from the file and never printed or written anywhere. Without --model, the newest model whose id or display
name contains "opus" is chosen from GET /v1/models, and the choice is logged. Extended thinking is enabled
(budget 16,000 tokens); if the model rejects that configuration, adaptive thinking is tried, and the mode actually used
is recorded with every output. The prompts are unchanged except that the Qwen-specific '/no_think' switch is not appended."""
import concurrent.futures as cf, glob, json, os, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.anthropic.com/v1'
OUT = os.path.join(HERE, os.environ.get('GAPCR_OUT_DIR', 'outputs_frontier'))   # DEVIATIONS #12c: separate directory per builder
PROMPTS = os.path.join(HERE, os.environ.get('GAPCR_PROMPTS_DIR', 'prompts'))     # DEVIATIONS #13


def key():
    path = os.environ.get('GAPCR_ANTHROPIC_KEY_FILE', '/mnt/session/uploads/anthropic_api_key.txt')
    return open(path).read().strip()


def call(method, path, body=None, timeout=900):
    req = urllib.request.Request(f'{API}{path}', method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'x-api-key': key(), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pick_model(explicit=None):
    models = call('GET', '/models?limit=100').get('data', [])
    ids = [(m.get('created_at', ''), m['id'], m.get('display_name', '')) for m in models]
    if explicit:
        assert any(i == explicit for _, i, _ in ids), f'model {explicit} not available: {[i for _, i, _ in ids]}'
        return explicit, ids
    opus = sorted([t for t in ids if 'opus' in (t[1] + t[2]).lower()], reverse=True)
    assert opus, f'no Opus model available: {[i for _, i, _ in ids]}'
    return opus[0][1], ids


THINKING = [{'thinking': {'type': 'enabled', 'budget_tokens': 16000}},
            {'thinking': {'type': 'adaptive'}, 'output_config': {'effort': 'high'}}]   # DEVIATIONS #12d


def ask(model, system, user, mode):
    body = {'model': model, 'max_tokens': 24000, 'system': system, 'messages': [{'role': 'user', 'content': user}],
            **THINKING[mode]}
    for attempt in range(6):
        try:
            t0 = time.time(); r = call('POST', '/messages', body); return r, time.time() - t0
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:300]
            if e.code == 400 and 'thinking' in msg.lower() and mode + 1 < len(THINKING):
                raise ValueError('thinking-config')
            if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                time.sleep(2 ** (attempt + 1)); continue
            raise RuntimeError(f'HTTP {e.code}: {msg}')
    raise RuntimeError('retries exhausted')


def one(model, prompt_path, sample, state):
    pr = json.load(open(prompt_path))
    dst = os.path.join(OUT, f"{pr['gap']}__s{sample}.json")
    if os.path.exists(dst):
        return None
    r, secs = ask(model, pr['system'], pr['user'], state['mode'])
    text = ''.join(b.get('text', '') for b in r.get('content', []) if b.get('type') == 'text')
    thinking = [b.get('thinking', '') for b in r.get('content', []) if b.get('type') == 'thinking']
    json.dump({'gap': pr['gap'], 'seed': sample, 'model': r.get('model', model), 'thinking_mode': THINKING[state['mode']],
               'text': text, 'thinking': thinking, 'usage': r.get('usage', {}), 'stop_reason': r.get('stop_reason'),
               'seconds': round(secs, 1)}, open(dst, 'w'), indent=1)
    return f"{time.strftime('%H:%M:%S')} {pr['gap']} s{sample} {r.get('usage', {}).get('output_tokens')} tok {secs:.0f}s"


def main(args):
    model = None
    if args and args[0] == '--model':
        model, args = args[1], args[2:]
    samples = [int(s) for s in args] or [1]
    os.makedirs(OUT, exist_ok=True)
    model, ids = pick_model(model)
    json.dump({'chosen': model, 'available': ids, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(os.path.join(OUT, '_model_choice.json'), 'w'), indent=1)
    print('model', model, flush=True)
    state = {'mode': 0}
    while True:   # choose the thinking mode once, before the parallel calls (DEVIATIONS #12d)
        try:
            ask(model, 'Reply OK.', 'OK?', state['mode']); break
        except ValueError:
            state['mode'] += 1
    print('thinking', THINKING[state['mode']], flush=True)
    jobs = [(p, s) for s in samples for p in sorted(glob.glob(os.path.join(PROMPTS, '*.json')))]
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(lambda js: one(model, js[0], js[1], state), jobs):
            if msg:
                print(msg, flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
