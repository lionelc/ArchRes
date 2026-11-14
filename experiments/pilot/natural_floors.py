"""Where can an architectural gap come from in the three pairs? Deterministic inputs to the certificate attempts of
Sec. V (exploratory; DEVIATIONS.md #8-#9). Run after the timing chain; it never overlaps a timing run.

  python3 natural_floors.py     writes results/natural_floors.json

  A  Turso's frozen asynchronous I/O layer, cell scan_agg (seed 2): pages the format forces (dbstat on SQLite's
     byte-identical copy), and an upper bound on the layer's least work per page, from Turso's whole count(*) run
     (it must read every page of the orders_day index) minus its startup cell. The floor through this chokepoint is at
     most pages x that bound.
  B  uutils' startup: what the multicall binary makes the loader do (relative relocations, writable relocated data,
     page faults) against GNU's true. These are set by how the binary is built, which the contract leaves mutable.
  C  rav1d's frozen part is shared: the share of dav1d's instructions in the assembly both engines call (msac routines
     are reached through 7-9 byte C wrappers in this dav1d build, so callgrind books them under the wrapper names)."""
import json, os, re, sqlite3, statistics, subprocess, sys

sys.path.insert(0, '/workspace/gapCR')
from celltest.write import rounds_by_arm

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
P = '/work/pilot'


def med_ms(exp, cell, seed, arm, state='S1'):
    for r in json.load(open(os.path.join(RES, f'{exp}.json')))['records']:
        if r['cell'] == cell and r['seed'] == seed and r['state'] == state:
            return statistics.median(v for rd in rounds_by_arm(r)[arm] for v in rd) / 1e6
    raise KeyError((exp, cell, seed, arm))


def pair_a():
    c = sqlite3.connect(f'file:{P}/data/a2/db_S1.s?immutable=1', uri=True)
    pages = dict(c.execute("SELECT name, count(*) FROM dbstat WHERE name IN ('orders','orders_day') GROUP BY 1").fetchall())
    y_count, y_start = med_ms('A_SURVEY', 'A_count_star', 2, 'Yd'), med_ms('A_SURVEY', 'A_startup', 2, 'Yd')
    t_r = med_ms('A_SURVEY', 'A_scan_agg', 2, 'Rd')
    per_page_ub_us = (y_count - y_start) * 1e3 / pages['orders_day']
    out = {'pages_orders_table': pages['orders'], 'pages_orders_day_index': pages['orders_day'],
           'turso_count_star_ms': round(y_count, 3), 'turso_startup_ms': round(y_start, 3),
           'layer_least_work_per_page_upper_bound_us': round(per_page_ub_us, 2),
           'scan_agg_floor_upper_bound_ms': round(per_page_ub_us * pages['orders'] / 1e3, 1),
           'sqlite_scan_agg_ms': round(t_r, 1)}
    for name, b in (('band_0.165', 0.1645), ('matched_null_0.070', 0.0705)):
        out[f'per_page_needed_for_certificate_us_{name}'] = round(t_r * 1e3 * pow(2.718281828, b) / pages['orders'], 1)
    return out


def loader(cmd):
    rd = subprocess.run(['readelf', '-d', cmd[0]], capture_output=True, text=True).stdout
    secs = subprocess.run(['readelf', '-S', '-W', cmd[0]], capture_output=True, text=True).stdout
    relacount = re.search(r'RELACOUNT\)\s+(\d+)', rd)
    drr = re.search(r'\.data\.rel\.ro\s+PROGBITS\s+\S+\s+\S+\s+(\S+)', secs)
    faults = []
    for _ in range(5):
        p = subprocess.run(['/usr/bin/time', '-f', '%R'] + cmd, capture_output=True, text=True)
        faults.append(int(p.stderr.strip().splitlines()[-1]))
    return {'binary_bytes': os.path.getsize(cmd[0]), 'relative_relocations': int(relacount.group(1)) if relacount else 0,
            'data_rel_ro_bytes': int(drr.group(1), 16) if drr else 0, 'minor_faults_median': statistics.median(faults)}


def pair_b():
    return {'gnu_true': loader([f'{P}/bin/gnu-9.12/bin/true']), 'uutils_true': loader([f'{P}/bin/uu-0.12.0/coreutils', 'true']),
            'startup_ms': {'gnu': [round(med_ms('B_SURVEY', 'B_true', s, 'Rd', 'C'), 3) for s in (1, 2)],
                           'uutils': [round(med_ms('B_SURVEY', 'B_true', s, 'Yd', 'C'), 3) for s in (1, 2)]}}


def pair_c():
    import analyze as A
    cap = json.load(open(os.path.join(RES, 'captures.json'))); ch = json.load(open(os.path.join(RES, 'captures_heldout.json')))
    is_asm = lambda k: k.startswith('dav1d_') and bool(A.ASM.search(k))
    wrap = re.compile(r'^dav1d_msac_decode_(symbol_adapt(4|8|16)|bool_adapt|bool_equi|bool|hi_tok)$')
    out = {}
    for seg, rr, ry in (('s0', cap['C|R1|-1'], cap['C|Y1|-1']), ('s3000', ch['C|R1|-1|s3000'], ch['C|Y1|-1|s3000']),
                        ('s6000', ch['C|R1|-1|s6000'], ch['C|Y1|-1|s6000'])):
        fr = A.resolve(rr['funcs'], A.OBJ['R1']); fy = A.resolve(ry['funcs'], A.OBJ['Y1'])
        ar = sum(v for k, v in fr.items() if is_asm(k) or wrap.match(k)); ay = sum(v for k, v in fy.items() if is_asm(k))
        out[seg] = {'shared_asm_share_of_dav1d_instr': round(ar / rr['total'], 3), 'rav1d_asm_instr_over_dav1d': round(ay / ar, 4)}
    return out


def main():
    out = {'A': pair_a(), 'B': pair_b(), 'C': pair_c()}
    json.dump(out, open(os.path.join(RES, 'natural_floors.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
