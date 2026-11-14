"""Pair A plans (deterministic): EXPLAIN QUERY PLAN for every query, state and engine, normalized to the sequence of
table accesses (SCAN/SEARCH, table, index or key used) plus the grouping/sorting steps. Writes results/plans.json.
Plan identity is judged on this normalized sequence, ignoring the engines' different wording for temp structures."""
import json, os, re, subprocess, sys

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
ENG = {'R': [f'{P}/bin/sqlite3-3.50.4', '-batch'], 'Y1': [f'{P}/bin/turso-0.8.3/tursodb', '-q', '-m', 'list'],
       'Y0': [f'{P}/bin/turso-0.5.0/tursodb', '-q', '-m', 'list']}
SUF = {'R': 's', 'Y1': 't1', 'Y0': 't0'}


def first_stmt(path):
    return open(path).read().strip().split(';')[0] + ';'


def eqp(eng, db, sql):
    p = subprocess.run(ENG[eng] + [db, 'EXPLAIN QUERY PLAN ' + sql], capture_output=True, text=True)
    return p.stdout + p.stderr


def normalize(text):
    steps = []
    for ln in text.splitlines():
        ln = re.sub(r'^[|`\- ]+', '', ln.split('|')[-1] if re.match(r'^\d+\|', ln) else ln).strip()
        if not ln or ln == 'QUERY PLAN':
            continue
        m = re.match(r'(SCAN|SEARCH)\s+(\w+)(?:\s+AS\s+\w+)?(.*)', ln)
        if m:
            how = m.group(3)
            idx = re.search(r'USING (?:COVERING |AUTOMATIC (?:PARTIAL )?(?:COVERING )?)?INDEX (\w+)', how)
            key = 'PK' if 'PRIMARY KEY' in how or 'rowid' in how else (idx.group(1) if idx else ('auto' if 'AUTOMATIC' in how else 'full'))
            steps.append(f'{m.group(1)} {m.group(2)} [{key}]')
        elif re.search(r'GROUP BY', ln):
            steps.append('GROUP')
        elif re.search(r'ORDER BY', ln):
            steps.append('ORDER')
        elif 'BLOOM' in ln:
            steps.append('BLOOM')
        elif 'LIST SUBQUERY' in ln or 'SUBQUERY' in ln:
            steps.append('SUBQUERY')
    return steps


def main():
    out = {}
    for seed in (1, 2):
        d = f'{P}/data/a{seed}'
        for f in sorted(os.listdir(d)):
            if not f.startswith('q_'):
                continue
            q = f[2:-4]
            if q in ('insert_txn', 'startup'):
                continue
            sql = first_stmt(f'{d}/{f}')
            for state in ('S1', 'S0'):
                rec = {}
                for eng in ENG:
                    raw = eqp(eng, f'{d}/db_{state}.{SUF[eng]}', sql)
                    rec[eng] = {'raw': raw, 'steps': normalize(raw)}
                rec['same_R_Y1'] = rec['R']['steps'] == rec['Y1']['steps']
                rec['same_R_Y0'] = rec['R']['steps'] == rec['Y0']['steps']
                out[f'{seed}|{state}|{q}'] = rec
    json.dump(out, open(f'{HERE}/results/plans.json', 'w'), indent=1)
    for k, v in out.items():
        if k.startswith('1|'):
            print(f"{k:24s} same(R,Y1)={v['same_R_Y1']!s:5s} R={v['R']['steps']}  Y1={v['Y1']['steps']}")


if __name__ == '__main__':
    os.makedirs(f'{HERE}/results', exist_ok=True)
    main()
