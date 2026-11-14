"""Exploratory deterministic checks of DEVIATIONS.md #6 (run after the timing chain, never during a timing run).

  python3 capture_extra.py      writes results/captures_heldout.json and results/base64_mechanism.json"""
import json, os, re, subprocess, tempfile

from capture import callgrind, c_cmd, P

HERE = os.path.dirname(os.path.abspath(__file__))
C = {'Y1': f'{P}/rav1d/target/release/dav1d', 'R1': f'{P}/rav1d/build/tools/dav1d', 'R0': f'{P}/dav1d_151/build/tools/dav1d',
     'P1400p': f'{P}/wt_pr1400p/target/release/dav1d', 'P1400': f'{P}/wt_pr1400/target/release/dav1d',
     'P1397p': f'{P}/wt_pr1397p/target/release/dav1d', 'P1397': f'{P}/wt_pr1397/target/release/dav1d'}
GNU, U12, U02 = f'{P}/bin/gnu-9.12/bin', f'{P}/bin/uu-0.12.0/coreutils', f'{P}/bin/uu-0.2.0/coreutils'


def heldout_captures():
    res = {}
    for skip in (3000, 6000):
        for k, b in C.items():
            res[f'C|{k}|-1|s{skip}'] = callgrind(c_cmd(b, skip=skip))
            print('C', k, skip, res[f'C|{k}|-1|s{skip}']['total'], flush=True)
    json.dump(res, open(os.path.join(HERE, 'results', 'captures_heldout.json'), 'w'))


def strace_counts(cmd, env):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'st')
        subprocess.run(['strace', '-c', '-f', '-o', out] + cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        calls = {}
        for ln in open(out):
            parts = ln.split()
            if len(parts) >= 5 and parts[-1].isidentifier() and parts[3].isdigit():
                calls[parts[-1]] = int(parts[3])
        return calls


def time_v(cmd, env):
    p = subprocess.run(['/usr/bin/time', '-v'] + cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    keep = ('Maximum resident set size', 'Minor (reclaiming a frame) page faults', 'Major', 'Voluntary context switches',
            'Involuntary context switches', 'File system inputs', 'File system outputs')
    return {ln.split(':')[0].strip(): ln.split(':')[-1].strip() for ln in p.stderr.splitlines() if ln.strip().startswith(keep)}


def base64_mechanism():
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}
    f = f'{P}/data/b2/bin32'
    cmds = {'R': [f'{GNU}/base64', f], 'Y1': [U12, 'base64', f], 'Y0': [U02, 'base64', f]}
    out = {k: {'strace': strace_counts(c, env), 'time_v': time_v(c, env)} for k, c in cmds.items()}
    json.dump(out, open(os.path.join(HERE, 'results', 'base64_mechanism.json'), 'w'), indent=1)
    for k, v in out.items():
        top = sorted(v['strace'].items(), key=lambda t: -t[1])[:4]
        print(k, top, v['time_v'])


if __name__ == '__main__':
    base64_mechanism()
    heldout_captures()
