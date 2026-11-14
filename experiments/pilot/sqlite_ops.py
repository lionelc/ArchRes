"""DEVIATIONS.md #7 (exploratory, deterministic): SQLite bytecode of the plan-identical cells with the largest gaps,
under the default and under single optimization knock-outs. Run after the timing chain.

  python3 sqlite_ops.py         writes results/sqlite_ops.json

The rule, fixed before the run: a knock-out "makes SQLite use Turso's operator" for `distinct` if SQLite's program
gains an ephemeral table for the DISTINCT (Turso shows a hash table for count(DISTINCT)); for `order_limit` if SQLite's
sorter loses its LIMIT bound (Turso's EXPLAIN is inspected for the same)."""
import json, os, re, subprocess

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
SQLITE = f'{P}/bin/sqlite3-3.50.4'
TURSO = f'{P}/bin/turso-0.8.3/tursodb'
MASKS = {'default': None, 'GroupByOrder': 0x4, 'DistinctOpt': 0x10, 'CoverIdxScan': 0x20, 'OrderByIdxJoin': 0x40,
         'MinMaxOpt': 0x10000, 'OmitOrderBy': 0x40000, 'all': 0xffffffff}


def stmt(q):
    return open(f'{P}/data/a1/q_{q}.sql').read().strip().split(';')[0] + ';'


def sqlite_explain(q, mask):
    pre = '' if mask is None else f'.testctrl optimizations 0x{mask:08x}\n'
    p = subprocess.run([SQLITE, '-batch', f'{P}/data/a1/db_S1.s'], input=pre + 'EXPLAIN ' + stmt(q) + '\n', capture_output=True, text=True)
    ops = [m.group(1) for m in (re.match(r'^\d+\s+(\w+)', ln.strip()) for ln in p.stdout.splitlines()) if m]
    return {'ops': ops, 'raw': p.stdout}


def turso_explain(q):
    p = subprocess.run([TURSO, '-q', '-m', 'list', f'{P}/data/a1/db_S1.t1', 'EXPLAIN ' + stmt(q)], capture_output=True, text=True)
    return p.stdout


def main():
    out = {}
    for q in ('distinct', 'order_limit', 'count_star'):
        rec = {'stmt': stmt(q), 'sqlite': {}, 'turso_explain': turso_explain(q)}
        for name, m in MASKS.items():
            e = sqlite_explain(q, m)
            rec['sqlite'][name] = {'n_ops': len(e['ops']), 'OpenEphemeral': e['ops'].count('OpenEphemeral'),
                                   'SorterOpen': e['ops'].count('SorterOpen'), 'Count': e['ops'].count('Count'),
                                   'IdxGT_SeekGT': sum(e['ops'].count(o) for o in ('IdxGT', 'SeekGT', 'IdxGE', 'SeekGE')),
                                   'ops': ' '.join(e['ops'])}
        out[q] = rec
        print('==', q, rec['stmt'])
        for name, v in rec['sqlite'].items():
            print(f"  {name:15s} n={v['n_ops']:3d} eph={v['OpenEphemeral']} sorter={v['SorterOpen']} count={v['Count']} seek={v['IdxGT_SeekGT']} :: {v['ops'][:160]}")
        print('  turso:', ' '.join(re.findall(r'^\d+\|(\w+)\|', rec['turso_explain'], re.M))[:300])
    json.dump(out, open(os.path.join(HERE, 'results', 'sqlite_ops.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
