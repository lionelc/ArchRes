"""Claim B5 and the signature of B-cg1 (deterministic; run after the timing chain, never during a timing run).

  python3 markers.py            writes results/markers.json

For each Pair B cell of B_KO, runs GNU 9.12 and uutils 0.12.0 with --debug on a 4 MiB input, in the default
environment and in the KO environment, and records the exit status and stderr. Rules fixed before the run:
  - a cell is GNU-accelerated if GNU's default-state --debug output names a hardware feature as used
    ('using <feature> hardware support' with <feature> other than 'generic');
  - B5 holds for an engine if, in every cell where its default state names a feature as used, the KO state does not."""
import json, os, re, subprocess

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
GNU, U12 = f'{P}/bin/gnu-9.12/bin', f'{P}/bin/uu-0.12.0/coreutils'
SMALL = f'{P}/data/b1/small'
KO = {'GLIBC_TUNABLES': 'glibc.cpu.hwcaps=-AVX512F,-AVX2,-AVX,-PMULL,-VPCLMULQDQ', 'OPENSSL_ia32cap': '0x0'}
CELLS = {'B_cksum': ['cksum', '{S}/bin4'], 'B_base64': ['base64', '{S}/bin4'], 'B_sha256sum': ['sha256sum', '{S}/bin4'],
         'B_md5sum': ['md5sum', '{S}/bin4'], 'B_b2sum': ['b2sum', '{S}/bin4'], 'B_wc_l': ['wc', '-l', '{S}/text4'],
         'B_wc_w': ['wc', '-w', '{S}/text4']}
USED = re.compile(r'using (\w+) hardware support', re.I)


def run(engine, argv, env):
    argv = [a.replace('{S}', SMALL) for a in argv]
    cmd = ([f'{GNU}/{argv[0]}'] if engine == 'gnu' else [U12, argv[0]]) + ['--debug'] + argv[1:]
    p = subprocess.run(cmd, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', **env}, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return {'rc': p.returncode, 'stderr': p.stderr.strip()[:400]}


def used(rec):
    return [f for f in USED.findall(rec['stderr']) if f.lower() != 'generic'] if rec['rc'] == 0 else []


def main():
    out = {'cells': {}}
    for cell, argv in CELLS.items():
        out['cells'][cell] = {eng: {st: run(eng, argv, env) for st, env in (('default', {}), ('KO', KO))} for eng in ('gnu', 'uu12')}
    acc = sorted(c for c, v in out['cells'].items() if used(v['gnu']['default']))
    out['gnu_accelerated_cells'] = acc
    b5 = {}
    for eng in ('gnu', 'uu12'):
        cells = [c for c, v in out['cells'].items() if used(v[eng]['default'])]
        b5[eng] = {'cells_with_feature_in_use': cells, 'KO_switches_all': all(not used(out['cells'][c][eng]['KO']) for c in cells)}
    out['B5'] = b5
    json.dump(out, open(os.path.join(HERE, 'results', 'markers.json'), 'w'), indent=1)
    for c, v in out['cells'].items():
        for eng in ('gnu', 'uu12'):
            print(c, eng, '| default:', v[eng]['default']['stderr'].replace('\n', ' / ')[:120], '| KO:', v[eng]['KO']['stderr'].replace('\n', ' / ')[:120])
    print('accelerated (GNU):', acc)
    print('B5:', b5)


if __name__ == '__main__':
    main()
