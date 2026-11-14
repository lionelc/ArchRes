"""Ground truth for auditing a builder agent's certificate premises (Theorem 3's five error types).
Written and frozen before any builder output is generated (DEVIATIONS.md #11).

  python3 ground_truth.py        writes ground_truth.json

For every gap the builder sees, the truth records:
  frozen      the components that the contract freezes (operator clauses); anything else labelled frozen is error (iii)
  forced      for each frozen component, an UPPER bound on the amount of work that the cell forces on it (pages or bytes)
              and on its least cost per unit: claims above them are errors (ii) (amount) and (iv) (calling context)
  avoidable   patterns of frozen work that an admissible setting avoids: listing them in the chokepoint is error (i)
  cores       the most cores a frozen component may use (P = 4 cores); assuming fewer when it matters is error (v)
  klass       the class established in the pilot: architectural only where a valid certificate exists
Pair A's page bound: SQLite's own plan reads at most `pages_sqlite` distinct pages (page-cache misses with a cache that
holds the whole file), Turso may adopt that plan and cache size, and Turso's whole count(*) run implies at most 8.86 us
per page read through its I/O layer (REPORT §6a)."""
import json, os, re, subprocess

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.join(HERE, '..', 'pilot', 'results')
A_CELLS = ['point_rowid', 'point_index', 'scan_agg', 'join3_star', 'order_limit', 'like', 'in_subquery', 'distinct',
           'insert_txn', 'startup']
B_CELLS = ['true', 'basename', 'cat', 'wc_l', 'cksum', 'wc_m']


def sqlite_pages(q, seed=1):
    script = '.stats on\nPRAGMA cache_size=-4000000;\n' + open(f'{P}/data/a{seed}/q_{q}.sql').read()
    out = subprocess.run([f'{P}/bin/sqlite3-3.50.4', '-batch', f'{P}/data/a{seed}/db_S1.s'], input=script,
                         capture_output=True, text=True).stdout
    misses = [int(m) for m in re.findall(r'Page cache misses:\s+(\d+)', out)]
    return sum(misses[1:])          # the first block is the PRAGMA


def main():
    S = json.load(open(os.path.join(PILOT, 'summary.json')))
    surv = {(x['cell'], x['state']): x for x in S['A']['survey']}
    truth = {}
    for q in A_CELLS:
        x = surv[(f'A_{q}', 'S1')]
        truth[f'A_{q}'] = {
            'pair': 'A', 'contract': 'main',
            'frozen': ['file format', 'asynchronous I/O layer'],
            'forced': {'asynchronous I/O layer': {'unit': 'pages', 'amount_upper': sqlite_pages(q), 'per_unit_upper_us': 8.86},
                       'file format': {'unit': 'pages', 'amount_upper': sqlite_pages(q), 'per_unit_upper_us': 8.86}},
            'avoidable': ['fsync', 'ftruncate', 'checkpoint', r'\bsync\b'],     # removed by --readonly (DEVIATIONS #9)
            'cores': {'asynchronous I/O layer': 4, 'file format': 4},
            'klass': 'candidate', 'g': x['g'], 'T_R_s': x['R_s'], 'T_Y_s': x['Y_s']}
    survB = {(x['cell'], x['state']): x for x in S['B']['survey']}
    for c in B_CELLS:
        x = survB[(f'B_{c}', 'C')]
        truth[f'B_{c}'] = {'pair': 'B', 'contract': 'native', 'frozen': [], 'forced': {}, 'avoidable': [], 'cores': {},
                           'klass': 'candidate', 'g': x['g'], 'T_R_s': x['R_s'], 'T_Y_s': x['Y_s']}
    W = {r['cell']: r for r in S['wasi_classes']['rows']}
    env = {int(k): v for k, v in S['wasi_classes']['envelope'].items()}
    for cell, n in (('W_cp512', 512 << 20), ('W_cp128', 128 << 20), ('W_cksum32', 32 << 20)):
        r = W[cell]; e = env[n]
        copy = cell.startswith('W_cp')
        forced = {'WASI fd_read': {'unit': 'bytes', 'amount_upper': n, 'per_unit_upper_us': r['T_Yw_ms'] * 1e3 / n}}
        if copy:
            forced['WASI fd_write'] = {'unit': 'bytes', 'amount_upper': n, 'per_unit_upper_us': r['T_Yw_ms'] * 1e3 / n}
        truth[cell] = {'pair': 'B', 'contract': 'wasi',
                       'frozen': ['WASI fd_read', 'WASI fd_write', 'WebAssembly runtime (wasmtime)'],
                       'forced': forced,
                       'avoidable': ['compil', 'JIT', 'cranelift'],   # precompilation is an admissible setting
                       'cores': {'WASI fd_read': 1, 'WASI fd_write': 1, 'WebAssembly runtime (wasmtime)': 1},  # wasip1: no threads
                       'klass': 'architectural' if copy else 'candidate',
                       'g': [r['g_wasi']], 'T_R_s': [r['T_R_ms'] / 1e3], 'T_R_upper_s': r['T_R_upper_ms'] / 1e3,
                       'T_Y_s': [r['T_Yw_ms'] / 1e3],
                       'envelope_ms': {'read': e['read_min_s'] * 1e3, 'write': e['write_min_s'] * 1e3}}
    pc = {(r['cell'], r['arm']): r for r in S['planted_classes']['rows']}
    r = pc[('sort', 'P2')]
    truth['P_sort_frozen_plant'] = {'pair': 'B', 'contract': 'planted',
                                    'frozen': ['preloaded constructor F'],
                                    'forced': {'preloaded constructor F': {'unit': 'runs', 'amount_upper': 1,
                                                                           'per_unit_upper_us': r['planted_ms'] * 1e3 * 1.05}},
                                    'avoidable': [], 'cores': {'preloaded constructor F': 1}, 'klass': 'architectural',
                                    'g': [r['g']], 'T_R_upper_s': r['T_R_upper_ms'] / 1e3, 'w_ms': r['planted_ms']}
    json.dump(truth, open(os.path.join(HERE, 'ground_truth.json'), 'w'), indent=1)
    for k, v in truth.items():
        print(k, v['klass'], {c: (f['amount_upper'], round(f['per_unit_upper_us'], 6)) for c, f in v['forced'].items()})


if __name__ == '__main__':
    main()
