"""Prompts for the builder agent: one per gap, with passive evidence only (default runs: timings, plans, profiles,
markers, system-call summaries, data facts) and the architecture contract. No intervention result is shown.

  python3 build_prompts.py      writes prompts/<gap>.json ({"system": ..., "user": ...})"""
import json, os, re, sqlite3, subprocess

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.join(HERE, '..', 'pilot', 'results')
PROF = '/work/agent/profiles'

SYSTEM = """You are a performance engineer. A system Y reimplements a reference R, and Y is slower than R on one cell (a fixed command or query on fixed data). Decide whether the gap is ARCHITECTURAL under the given architecture contract: whether NO admissible change to Y can bring Y's time within the band b of R's time (in log units: log(T_Y) - log(T_R) <= b).

A claim of ARCHITECTURAL must come with a certificate made of three premises:
(C1) chokepoint: a set D of FROZEN operators (frozen by the contract) that EVERY admissible version of Y must execute on this cell;
(C2) least work: for each operator in D, the smallest cost it can have under ANY admissible calling context (batch sizes, caching, buffer sizes, ordering, options, settings);
(C3) floor: L = max( (sum of the least works) / P , max over operators of (least work / cores the operator may use) ), with P = 4 cores. The gap is architectural if log(L) - log(T_R_upper) > b.
Mutable code (anything the contract does not freeze) can be changed arbitrarily, so its cost never counts toward the floor.
If you cannot give a valid certificate, answer "candidate". If a setting or an admissible change you can name would close the gap, answer "fixable".

Answer with ONE JSON object and nothing else, following this schema:
{"class": "architectural" | "candidate" | "fixable",
 "chokepoint": [{"operator": "<name>", "component": "<one of the listed components>", "frozen": true | false,
                 "why_every_version_executes_it": "<short>",
                 "least_work": {"amount": <number>, "unit": "<pages|bytes|rows|calls|runs|...>", "per_unit_cost_us": <number>,
                                "total_ms": <number>, "calling_context": "<the context you assume>"},
                 "max_cores": <integer>}],
 "floor_ms": <number>, "L_delta": <number>, "rationale": "<at most 80 words>"}
List in "chokepoint" every operator your floor uses (an empty list if you give no floor)."""

CONTRACTS = {
    'main': ("Architecture contract (Turso, main): FROZEN: the SQLite file format (on-disk layout of pages, B-trees and records) "
             "and SQL semantics; Turso's asynchronous I/O layer, through which every page read and write passes. "
             "MUTABLE: everything else (pager and page cache, B-tree code, bytecode virtual machine (VDBE), query planner and "
             "optimizer, SQL parser, command-line shell, build options); any code change to these is admissible. Existing "
             "settings (PRAGMAs, command-line flags such as --readonly) may be changed.",
             ['file format', 'asynchronous I/O layer', 'pager/page cache', 'B-tree code', 'VDBE (bytecode interpreter)',
              'query planner/optimizer', 'SQL parser', 'command-line shell', 'process start-up and dynamic loading',
              'operating system kernel']),
    'native': ("Architecture contract (uutils, native Linux): CONSTRAINTS ONLY: the program must stay pure Rust and ship as one "
               "multicall binary. No component is frozen: any change to uutils' code, dependencies or build settings that "
               "satisfies the constraints is admissible.",
               ['uutils utility code', 'Rust standard library', 'multicall dispatch', 'dynamic loader and relocations',
                'process start-up', 'operating system kernel', 'CPU hardware']),
    'wasi': ("Architecture contract (uutils compiled to WebAssembly, target wasm32-wasip1, run by wasmtime 50.0.1): FROZEN: the WASI "
             "preview1 interface as implemented by wasmtime 50.0.1; data move between files and the program only through fd_read "
             "(into the program's linear memory) and fd_write (out of linear memory); preview1 has no call that clones, splices or "
             "copies a file, and a hard link is not a copy. wasip1 programs are single-threaded. MUTABLE: uutils' Rust code, its "
             "build for this target, and wasmtime's settings (for example, running a precompiled module).",
             ['uutils utility code', 'Rust standard library (wasi)', 'WASI fd_read', 'WASI fd_write',
              'WebAssembly runtime (wasmtime)', 'operating system kernel']),
    'planted': ("Architecture contract (uutils native, variant V_F): as the native contract (pure Rust, one multicall binary), plus "
                "one operator clause: the constructor F below, preloaded into uutils' process, is FROZEN and runs once in every "
                "invocation.",
                ['uutils utility code', 'preloaded constructor F', 'Rust standard library', 'process start-up',
                 'operating system kernel']),
}


def top_functions(path, n=8):
    out = subprocess.run(['callgrind_annotate', '--threshold=100', '--inclusive=no', path], capture_output=True, text=True).stdout
    tot, rows = None, []
    for ln in out.splitlines():
        if 'PROGRAM TOTALS' in ln:
            tot = int(ln.split()[0].replace(',', '')); continue
        m = re.match(r'^\s*([\d,]+)\s+\(\s*([\d.]+)%\)\s+(.*)$', ln)
        if m and tot:
            name = m.group(3).split(':', 1)[-1].strip()
            name = re.sub(r'\s+\[[^\]]*\]$', '', name)
            rows.append(f'{float(m.group(2)):5.1f}%  {name[:110]}')
        if len(rows) >= n:
            break
    return f'total {tot:,} instructions\n' + '\n'.join(rows)


def ms(xs):
    return ', '.join(f'{x * 1e3:.1f} ms' for x in xs)


def db_facts():
    c = sqlite3.connect(f'file:{P}/data/a1/db_S1.s?immutable=1', uri=True)
    pages = dict(c.execute("SELECT name, count(*) FROM dbstat GROUP BY name").fetchall())
    rows = {t: c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('orders', 'customers', 'items')}
    schema = '\n'.join(r[0] for r in c.execute("SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"))
    return (f"Database (both engines read byte-identical copies; page size 4096; WAL mode; statistics present):\n{schema}\n"
            f"Rows: orders {rows['orders']:,}; customers {rows['customers']:,}; items {rows['items']:,}. "
            f"Pages: " + ', '.join(f'{k} {v:,}' for k, v in sorted(pages.items()) if not k.startswith('sqlite')))


def main():
    S = json.load(open(os.path.join(PILOT, 'summary.json')))
    plans = json.load(open(os.path.join(PILOT, 'plans.json')))
    os.makedirs(os.path.join(HERE, 'prompts'), exist_ok=True)
    facts = db_facts()
    survA = {(x['cell'], x['state']): x for x in S['A']['survey']}
    st = survA[('A_startup', 'S1')]
    bandsA = S['A']['bands']
    for q in ['point_rowid', 'point_index', 'scan_agg', 'join3_star', 'order_limit', 'like', 'in_subquery', 'distinct',
              'insert_txn', 'startup']:
        x = survA[(f'A_{q}', 'S1')]
        stmts = [s.strip() for s in open(f'{P}/data/a1/q_{q}.sql').read().split(';') if s.strip()]
        b = bandsA['<0.1s'] if x['R_s'][0] < 0.1 else bandsA['0.1-1s']
        pl = plans.get(f'1|S1|{q}')
        planR = pl['R']['raw'].strip() if pl else '(no plan: not a query)'
        planY = pl['Y1']['raw'].strip() if pl else '(no plan: not a query)'
        user = (f"System Y: Turso 0.8.3 command-line shell (Rust reimplementation of SQLite). Reference R: SQLite 3.50.4 "
                f"command-line shell. Each run is one process: `shell DB < script`, warm OS page cache, output discarded.\n"
                f"{CONTRACTS['main'][0]}\nComponents: {', '.join(CONTRACTS['main'][1])}.\n\n{facts}\n\n"
                f"Cell `{q}`: a script of {len(stmts)} statement(s); the first is:\n  {stmts[0]};\n"
                f"Measured (two data seeds): T_R = {ms(x['R_s'])}; T_Y = {ms(x['Y_s'])}; gap g = log(T_Y/T_R) = "
                f"{', '.join(f'{g:.2f}' for g in x['g'])}; band b = {b:.3f}; T_R_upper = {max(x['R_s']) * 1e3 * 1.1:.1f} ms.\n"
                f"Start-up cell (`SELECT 1`): Turso {ms(st['Y_s'])}; SQLite {ms(st['R_s'])}.\n\n"
                f"EXPLAIN QUERY PLAN, SQLite:\n{planR}\nEXPLAIN QUERY PLAN, Turso:\n{planY}\n\n"
                f"Profile of Turso (callgrind, self instructions, top functions):\n{top_functions(f'{PROF}/turso_{q}.out')}\n"
                f"Profile of SQLite:\n{top_functions(f'{PROF}/sqlite_{q}.out')}")
        json.dump({'gap': f'A_{q}', 'system': SYSTEM, 'user': user}, open(os.path.join(HERE, 'prompts', f'A_{q}.json'), 'w'), indent=1)
    survB = {(x['cell'], x['state']): x for x in S['B']['survey']}
    stB = survB[('B_true', 'C')]
    bandsB = S['B']['bands']
    markers = json.load(open(os.path.join(PILOT, 'markers.json')))['cells']
    cmds = {'true': 'true', 'basename': 'basename /a/b/c', 'cat': 'cat FILE (32 MiB of ASCII text lines), output to /dev/null',
            'wc_l': 'wc -l FILE (32 MiB of ASCII text lines)', 'cksum': 'cksum FILE (32 MiB of random bytes)',
            'wc_m': 'wc -m FILE (32 MiB of ASCII text lines)'}
    for c, cmd in cmds.items():
        x = survB[(f'B_{c}', 'C')]
        b = bandsB['<0.1s'] if x['R_s'][0] < 0.1 else bandsB['0.1-1s']
        mk = markers.get(f'B_{c}')
        mtxt = (f"--debug markers: GNU: {mk['gnu']['default']['stderr'][:160]!r}; uutils: {mk['uu12']['default']['stderr'][:160]!r}"
                if mk else '--debug markers: not available for this utility')
        user = (f"System Y: uutils coreutils 0.12.0 (Rust; one dynamically linked multicall binary of 19 MB). Reference R: GNU "
                f"coreutils 9.12 (C; one small binary per utility). Each run is one process, LC_ALL=C, warm page cache.\n"
                f"{CONTRACTS['native'][0]}\nComponents: {', '.join(CONTRACTS['native'][1])}.\n\n"
                f"Cell `{c}`: {cmd}.\nMeasured (two data seeds): T_R = {ms(x['R_s'])}; T_Y = {ms(x['Y_s'])}; gap g = "
                f"{', '.join(f'{g:.2f}' for g in x['g'])}; band b = {b:.3f}; T_R_upper = {max(x['R_s']) * 1e3 * 1.1:.2f} ms.\n"
                f"Start-up cell (`true`): uutils {ms(stB['Y_s'])}; GNU {ms(stB['R_s'])}.\n{mtxt}")
        json.dump({'gap': f'B_{c}', 'system': SYSTEM, 'user': user}, open(os.path.join(HERE, 'prompts', f'B_{c}.json'), 'w'), indent=1)
    W = {r['cell']: r for r in S['wasi_classes']['rows']}
    for cell, desc in (('W_cp512', 'cp SRC DST, SRC a 512 MiB file'), ('W_cp128', 'cp SRC DST, SRC a 128 MiB file'),
                       ('W_cksum32', 'cksum FILE, a 32 MiB file')):
        r = W[cell]
        ncalls = (512 << 20 if cell == 'W_cp512' else 128 << 20) // 8192
        sys_calls = (f'Default-run system calls (strace -c): GNU cp: 1 ioctl FICLONE, no read/write of file data; uutils WebAssembly '
                     f'cp: {ncalls:,} pread64 and {ncalls:,} pwrite64 of 8 KiB.' if cell.startswith('W_cp') else
                     'Default-run system calls: both read the file sequentially.')
        user = (f"System Y: uutils coreutils 0.12.0 compiled to WebAssembly (wasm32-wasip1), run by wasmtime 50.0.1 from a "
                f"precompiled module. Reference R: GNU coreutils 9.12 native. The file system is XFS with reflink support; warm "
                f"page cache.\n{CONTRACTS['wasi'][0]}\nComponents: {', '.join(CONTRACTS['wasi'][1])}.\n\n"
                f"Cell `{cell}`: {desc}.\nMeasured: T_R = {r['T_R_ms']:.2f} ms (GNU); T_R_upper = {r['T_R_upper_ms']:.2f} ms; "
                f"T_Y = {r['T_Yw_ms']:.1f} ms (uutils WebAssembly); uutils native: {r['T_Yn_ms']:.2f} ms; gap g = {r['g_wasi']:.2f}; "
                f"band b = {r['band']:.3f}.\n{sys_calls}\nMachine: 4 cores; native read() of the file into a 1 MiB buffer runs at "
                f"about 8 GB/s, and write() of a buffer into a new file at about 8 GB/s, on this file system.")
        json.dump({'gap': cell, 'system': SYSTEM, 'user': user}, open(os.path.join(HERE, 'prompts', f'{cell}.json'), 'w'), indent=1)
    pc = {(r['cell'], r['arm']): r for r in S['planted_classes']['rows']}
    r = pc[('sort', 'P2')]
    plant_src = open(os.path.join(HERE, '..', 'pilot', 'plant.c')).read()
    user = (f"System Y: uutils coreutils 0.12.0 sort (native), with a constructor F preloaded (LD_PRELOAD) as below. Reference R: "
            f"GNU coreutils 9.12 sort. Cell `sort`: sort FILE (8 MiB of ASCII text lines), LC_ALL=C, warm page cache.\n"
            f"{CONTRACTS['planted'][0]}\nComponents: {', '.join(CONTRACTS['planted'][1])}.\n\nSource of F (GAPCR_PLANT_US = "
            f"{int(r['planted_ms'] * 1e3)}):\n{plant_src}\nMeasured: T_R = 43.6 ms (GNU); T_R_upper = {r['T_R_upper_ms']:.1f} ms; "
            f"T_Y = 113.1 ms (uutils with F); uutils without F: 27.8 ms; gap g = {r['g']:.2f}; band b = 0.236. Running F alone "
            f"inside GNU `true` takes {r['w_measured_ms']:.1f} ms more than `true` without it.")
    json.dump({'gap': 'P_sort_frozen_plant', 'system': SYSTEM, 'user': user},
              open(os.path.join(HERE, 'prompts', 'P_sort_frozen_plant.json'), 'w'), indent=1)
    print(len(os.listdir(os.path.join(HERE, 'prompts'))), 'prompts')


if __name__ == '__main__':
    main()
