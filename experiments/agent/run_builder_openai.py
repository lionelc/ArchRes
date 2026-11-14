"""Runs the frontier builder through the OpenAI API on the same blinded prompts as run_builder.py (DEVIATIONS.md #12a).

  GAPCR_OPENAI_KEY_FILE=/mnt/session/uploads/openai_api_key.txt python3 run_builder_openai.py [--model ID] SAMPLES...
  e.g. ... run_builder_openai.py 1 2        writes outputs_frontier/<gap>__s<sample>.json

The key is read from the file and never printed or written anywhere.
- Model: without --model, the id is looked up in GET /v1/models. It is the newest model whose id contains both "6.1"
  and "sol" (GPT-6.1 Sol). If none matches, the script stops and lists the GPT ids it found. It never guesses.
- API and reasoning: the Responses API with reasoning effort "high". If the model rejects that, the chain falls back
  through effort "medium", then Chat Completions with reasoning_effort "high", then Chat Completions without the
  parameter. Every output records the mode actually used.
- Prompts: unchanged, except that the Qwen-specific '/no_think' switch is not appended."""
import concurrent.futures as cf, glob, json, os, sys, threading, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.openai.com/v1'
OUT = os.path.join(HERE, os.environ.get('GAPCR_OUT_DIR', 'outputs_frontier'))   # DEVIATIONS #13
PROMPTS = os.path.join(HERE, os.environ.get('GAPCR_PROMPTS_DIR', 'prompts'))     # DEVIATIONS #13
LOCK = threading.Lock()


def key():
    path = os.environ.get('GAPCR_OPENAI_KEY_FILE', '/mnt/session/uploads/openai_api_key.txt')
    return open(path).read().strip()


def call(method, path, body=None, timeout=1800):
    req = urllib.request.Request(f'{API}{path}', method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': f'Bearer {key()}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pick_model(explicit=None):
    ids = sorted((m.get('created', 0), m['id']) for m in call('GET', '/models').get('data', []))
    if explicit:
        assert any(i == explicit for _, i in ids), f'model {explicit} not available'
        return explicit, [i for _, i in ids]
    cand = [i for c, i in sorted(ids, reverse=True) if '6.1' in i.lower() and 'sol' in i.lower()]
    if not cand:
        raise SystemExit('no model id contains "6.1" and "sol"; GPT ids available: '
                         + ', '.join(i for _, i in ids if i.lower().startswith('gpt')))
    return cand[0], [i for _, i in ids if i.lower().startswith(('gpt', 'o'))]


MODES = [('responses', 'high'), ('responses', 'medium'), ('chat', 'high'), ('chat', None)]


def request(model, system, user, mode):
    api, effort = MODES[mode]
    if api == 'responses':
        body = {'model': model, 'instructions': system, 'input': user, 'max_output_tokens': 32000,
                'reasoning': {'effort': effort}}
        r = call('POST', '/responses', body)
        text = ''.join(c.get('text', '') for item in r.get('output', []) if item.get('type') == 'message'
                       for c in item.get('content', []) if c.get('type') in ('output_text', 'text'))
        return text, r.get('usage', {}), r.get('model', model), r.get('status')
    body = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'max_completion_tokens': 32000}
    if effort:
        body['reasoning_effort'] = effort
    r = call('POST', '/chat/completions', body)
    return r['choices'][0]['message'].get('content') or '', r.get('usage', {}), r.get('model', model), r['choices'][0].get('finish_reason')


def ask(model, system, user, state):
    attempt = 0
    while True:
        try:
            t0 = time.time(); out = request(model, system, user, state['mode']); return out + (time.time() - t0,)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:400]
            if e.code in (400, 404) and state['mode'] + 1 < len(MODES) and any(w in msg.lower() for w in
                                                                              ('reasoning', 'effort', 'unsupported', 'not supported', 'responses', 'unknown')):
                with LOCK:
                    state['mode'] += 1; state['log'].append(f'fallback to {MODES[state["mode"]]} after HTTP {e.code}: {msg[:160]}')
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 6:
                time.sleep(2 ** (attempt + 1)); attempt += 1; continue
            raise RuntimeError(f'HTTP {e.code}: {msg}')


def one(model, prompt_path, sample, state):
    pr = json.load(open(prompt_path))
    dst = os.path.join(OUT, f"{pr['gap']}__s{sample}.json")
    if os.path.exists(dst):
        return None
    text, usage, used_model, finish, secs = ask(model, pr['system'], pr['user'], state)
    json.dump({'gap': pr['gap'], 'seed': sample, 'model': used_model, 'mode': MODES[state['mode']], 'text': text,
               'usage': usage, 'finish': finish, 'seconds': round(secs, 1)}, open(dst, 'w'), indent=1)
    return f"{time.strftime('%H:%M:%S')} {pr['gap']} s{sample} {json.dumps(usage)[:120]} {secs:.0f}s"


def main(args):
    model = None
    if args and args[0] == '--model':
        model, args = args[1], args[2:]
    samples = [int(s) for s in args] or [1]
    os.makedirs(OUT, exist_ok=True)
    model, ids = pick_model(model)
    state = {'mode': 0, 'log': []}
    print('model', model, flush=True)
    jobs = [(p, s) for s in samples for p in sorted(glob.glob(os.path.join(PROMPTS, '*.json')))]
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(lambda js: one(model, js[0], js[1], state), jobs):
            if msg:
                print(msg, flush=True)
    json.dump({'chosen': model, 'gpt_ids_available': ids, 'final_mode': MODES[state['mode']], 'fallbacks': state['log'],
               'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(os.path.join(OUT, '_model_choice.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
