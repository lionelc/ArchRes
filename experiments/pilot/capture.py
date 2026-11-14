"""Deterministic captures for the pilot (callgrind): total instructions and self instructions per function.

  python3 capture.py OUT.json
Captures never overlap a timing run. Instruction counts depend on the binary, the input and the environment, not on load."""
import json, os, re, subprocess, sys, tempfile

P = '/work/pilot'
VIDEO = f'{P}/videos/Chimera-AV1-8bit-1280x720-3363kbps.ivf'
LINE = re.compile(r'^\s*([\d,]+)\s+(?:\(\s*[\d.]+%\)\s+)?(\S.*)$')
ASM = re.compile(r'_(sse2|ssse3|sse4|sse41|avx2|avx512icl|avx512)(\b|$|\.)')


def callgrind(cmd, env=None, stdin=None):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'cg.out')
        e = dict(os.environ, **(env or {}))
        with open(stdin) if stdin else open(os.devnull) as fin:
            subprocess.run(['valgrind', '--tool=callgrind', f'--callgrind-out-file={out}', *cmd], env=e, stdin=fin,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        ann = subprocess.run(['callgrind_annotate', '--threshold=100', '--inclusive=no', out],
                             capture_output=True, text=True).stdout
    total, funcs = None, {}
    for ln in ann.splitlines():
        if 'PROGRAM TOTALS' in ln:
            total = int(ln.split()[0].replace(',', ''))
            continue
        m = LINE.match(ln)
        if m and total is not None and ':' in m.group(2):
            name = m.group(2).split(':', 1)[1].strip()
            name = re.sub(r'\s+\[[^\]]*\]$', '', name)
            funcs[name] = funcs.get(name, 0) + int(m.group(1).replace(',', ''))
    return {'cmd': cmd, 'total': total, 'funcs': funcs}


def c_cmd(binary, skip=0, frames=60, threads=1, mask='-1'):
    return [binary, '-q', '-i', VIDEO, '-o', '/dev/null', '--skip', str(skip), '--limit', str(frames),
            '--threads', str(threads), '--cpumask', mask]


def main(out):
    res = {}
    C = {'Y1': f'{P}/rav1d/target/release/dav1d', 'R1': f'{P}/rav1d/build/tools/dav1d',
         'Y0': f'{P}/wt_v110/target/release/dav1d', 'R0': f'{P}/dav1d_151/build/tools/dav1d',
         'P1400p': f'{P}/wt_pr1400p/target/release/dav1d', 'P1400': f'{P}/wt_pr1400/target/release/dav1d',
         'P1397p': f'{P}/wt_pr1397p/target/release/dav1d', 'P1397': f'{P}/wt_pr1397/target/release/dav1d'}
    for mask in ('-1', 'none'):
        for k in ('Y1', 'R1', 'Y0', 'R0', 'P1400p', 'P1400', 'P1397p', 'P1397'):
            if mask == 'none' and k not in ('Y1', 'R1'):
                continue
            res[f'C|{k}|{mask}'] = callgrind(c_cmd(C[k], mask=mask)); print('C', k, mask, res[f'C|{k}|{mask}']['total'], flush=True)
    gnu, u12, u02 = f'{P}/bin/gnu-9.12/bin', f'{P}/bin/uu-0.12.0/coreutils', f'{P}/bin/uu-0.2.0/coreutils'
    small = f'{P}/data/b1/small'
    os.makedirs(small, exist_ok=True)
    for src, dst in (('bin32', 'bin4'), ('text32', 'text4'), ('csv32', 'csv4')):
        with open(f'{P}/data/b1/{src}', 'rb') as f:
            data = f.read(4 << 20)
        if 'bin' not in dst:
            data = data.rsplit(b'\n', 1)[0] + b'\n'
        open(f'{small}/{dst}', 'wb').write(data)
    cells = {'base64': ['base64', f'{small}/bin4'], 'cksum': ['cksum', f'{small}/bin4'], 'sha256sum': ['sha256sum', f'{small}/bin4'],
             'wc_l': ['wc', '-l', f'{small}/text4'], 'sort': ['sort', f'{small}/text4'], 'cut': ['cut', '-d,', '-f2', f'{small}/csv4']}
    env = {'LC_ALL': 'C'}
    for name, argv in cells.items():
        res[f'B|R|{name}'] = callgrind([f'{gnu}/{argv[0]}'] + argv[1:], env)
        res[f'B|Y1|{name}'] = callgrind([u12] + argv, env)
        res[f'B|Y0|{name}'] = callgrind([u02] + argv, env)
        print('B', name, res[f'B|R|{name}']['total'], res[f'B|Y1|{name}']['total'], res[f'B|Y0|{name}']['total'], flush=True)
    a = f'{P}/data/a1'
    for q in ('scan_agg', 'point_rowid', 'join2'):
        for k, cmd in (('R', [f'{P}/bin/sqlite3-3.50.4', '-batch', f'{a}/db_S1.s']),
                       ('Y1', [f'{P}/bin/turso-0.8.3/tursodb', '-q', '-m', 'list', f'{a}/db_S1.t1']),
                       ('Y0', [f'{P}/bin/turso-0.5.0/tursodb', '-q', '-m', 'list', f'{a}/db_S1.t0'])):
            res[f'A|{k}|{q}'] = callgrind(cmd, stdin=f'{a}/q_{q}.sql'); print('A', k, q, res[f'A|{k}|{q}']['total'], flush=True)
    json.dump(res, open(out, 'w'))


if __name__ == '__main__':
    main(sys.argv[1])
