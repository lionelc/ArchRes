"""Runs the builder agent (an open-weight LLM served locally by llama.cpp) on every prompt.

  python3 run_builder.py SEEDS...      e.g. python3 run_builder.py 1 2 3; writes outputs/<gap>__s<seed>.json

The builder sees only prompts/<gap>.json. Sampling follows the model card's non-thinking settings."""
import glob, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'http://127.0.0.1:8088/v1/chat/completions'


def ask(system, user, seed):
    body = {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user + '\n/no_think'}],
            'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'max_tokens': 1200, 'seed': seed,
            'chat_template_kwargs': {'enable_thinking': False}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.load(r)
    return out['choices'][0]['message']['content'], out.get('usage', {}), time.time() - t0


def main(seeds):
    os.makedirs(os.path.join(HERE, 'outputs'), exist_ok=True)
    for seed in seeds:
        for p in sorted(glob.glob(os.path.join(HERE, 'prompts', '*.json'))):
            pr = json.load(open(p))
            dst = os.path.join(HERE, 'outputs', f"{pr['gap']}__s{seed}.json")
            if os.path.exists(dst):
                continue
            text, usage, secs = ask(pr['system'], pr['user'], seed)
            json.dump({'gap': pr['gap'], 'seed': seed, 'text': text, 'usage': usage, 'seconds': round(secs, 1)}, open(dst, 'w'), indent=1)
            print(time.strftime('%H:%M:%S'), pr['gap'], seed, usage.get('completion_tokens'), f'{secs:.0f}s', flush=True)


if __name__ == '__main__':
    main([int(s) for s in sys.argv[1:]] or [1])
