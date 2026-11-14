"""Timing experiments of the pilot, on gapCR's celltest (counterbalanced rotation rounds, A/A arms, output checks).

  python3 run.py EXP [EXP ...]        writes results/<EXP>.json after every cell
Experiments: C_SURVEY C_TIMESPLIT C_SWAPS C_PLANTS C_LAYOUT  B_TIMESPLIT B_KO B_SURVEY B_PLANTS B_LAYOUT
             A_SURVEY A_TIMESPLIT A_PLANTS A_LAYOUT A_KO"""
import datetime, json, os, statistics, subprocess, sys, time

sys.path.insert(0, '/workspace/gapCR')
from celltest.spec import Arm, Cell, Design, command_env
from celltest.execute import run_cell
from celltest import orders as O

P = '/work/pilot'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
VIDEO = f'{P}/videos/Chimera-AV1-8bit-1280x720-3363kbps.ivf'
PLANT = f'{P}/bin/libplant.so'
BASE_ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/root'}
KO = {'GLIBC_TUNABLES': 'glibc.cpu.hwcaps=-AVX512F,-AVX2,-AVX,-PMULL,-VPCLMULQDQ', 'OPENSSL_ia32cap': '0x0'}
REPS_SHORT = (2, 1)   # runs and warm-ups per block for cells under 1 s (registration said 3 and 1; DEVIATIONS.md #2)
REPS_LONG = (1, 0)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ------------------------------------------------------------------------------------------------ engines
C_BIN = {'Y1': f'{P}/rav1d/target/release/dav1d', 'R1': f'{P}/rav1d/build/tools/dav1d',
         'Y0': f'{P}/wt_v110/target/release/dav1d', 'R0': f'{P}/dav1d_151/build/tools/dav1d',
         'P1400p': f'{P}/wt_pr1400p/target/release/dav1d', 'P1400': f'{P}/wt_pr1400/target/release/dav1d',
         'P1397p': f'{P}/wt_pr1397p/target/release/dav1d', 'P1397': f'{P}/wt_pr1397/target/release/dav1d'}
B_GNU, B_U12, B_U02 = f'{P}/bin/gnu-9.12/bin', f'{P}/bin/uu-0.12.0/coreutils', f'{P}/bin/uu-0.2.0/coreutils'
A_WRAP = {'Y1': f'{P}/bin/wrap_t1', 'Y0': f'{P}/bin/wrap_t0', 'R': f'{P}/bin/wrap_sqlite'}


def c_arm(name, key, env=None):
    return Arm(name, key, 'multicall', C_BIN[key], dict(env or {}))


def b_arm(name, key, env=None):
    if key == 'R':
        return Arm(name, 'gnu-9.12', 'dir', B_GNU, dict(env or {}))
    return Arm(name, {'Y1': 'uu-0.12.0', 'Y0': 'uu-0.2.0'}[key], 'multicall', {'Y1': B_U12, 'Y0': B_U02}[key], dict(env or {}))


def a_arm(name, key, env=None):
    return Arm(name, {'Y1': 'turso-0.8.3', 'Y0': 'turso-0.5.0', 'R': 'sqlite-3.50.4'}[key], 'multicall', A_WRAP[key], dict(env or {}))


# ------------------------------------------------------------------------------------------------ cells
def c_cell(skip, threads, mask, frames=240):
    return Cell(f'C_s{skip}_t{threads}_m{mask}', ['-q', '-i', VIDEO, '-o', '/dev/null', '--skip', str(skip), '--limit', str(frames),
                                                   '--threads', str(threads), '--cpumask', mask],
                family='decode', factors={'skip': skip, 'threads': threads, 'mask': mask, 'frames': frames})


B_CELLS = {'base64': ['base64', '{D}/bin32'], 'base64_d': ['base64', '-d', '{D}/bin32.b64'], 'cksum': ['cksum', '{D}/bin32'],
           'sha256sum': ['sha256sum', '{D}/bin32'], 'md5sum': ['md5sum', '{D}/bin32'], 'b2sum': ['b2sum', '{D}/bin32'],
           'wc_l': ['wc', '-l', '{D}/text32'], 'wc_w': ['wc', '-w', '{D}/text32'], 'wc_m': ['wc', '-m', '{D}/text32'],
           'sort': ['sort', '{D}/text8'], 'sort_n': ['sort', '-n', '{D}/nums4'], 'sort_u': ['sort', '-u', '{D}/text8'],
           'cut': ['cut', '-d,', '-f2', '{D}/csv32'], 'cat': ['cat', '{D}/text32'], 'head': ['head', '-n', '1000000', '{D}/text32'],
           'tail': ['tail', '-n', '1000000', '{D}/text32'], 'uniq': ['uniq', '{D}/text8.sorted'], 'seq': ['seq', '1', '5000000'],
           'basename': ['basename', '/a/b/c'], 'true': ['true']}
A_NAMES = ['point_rowid', 'point_index', 'range_index', 'scan_agg', 'count_star', 'group_by', 'join2', 'join3_star', 'order_limit',
           'like', 'in_subquery', 'distinct', 'insert_txn', 'startup']


def b_cell(name):
    return Cell(f'B_{name}', list(B_CELLS[name]), family=name.split('_')[0], factors={'util': name})


def a_cell(name):
    return Cell(f'A_{name}', ['{D}/db_{S}', f'{{D}}/q_{name}.sql'], family='sql', factors={'query': name})


# ------------------------------------------------------------------------------------------------ running
def design(arms, states, rounds=None):
    names = [a.name for a in arms]
    orders = O.rotation(names, rounds or len(names))
    O.check(orders, names)
    return Design(arms=arms, orders=orders, reps=1, warmup=0, states=states, base_env=dict(BASE_ENV), ref_arm=names[0], agree=[names])


def probe(des, cell, d, state):
    worst = 0.0
    for a in des.arms:
        argv, env = command_env(des, a, cell, d, state)
        t0 = time.perf_counter(); subprocess.run(argv, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        worst = max(worst, time.perf_counter() - t0)
    return worst


def run_exp(name, items, states, rounds=None):
    """items: [(cell, data_dir, state, seed, arms)]"""
    os.makedirs(OUT, exist_ok=True)
    meta = {'exp': name, 'start_utc': utc()}; recs = []
    for cell, d, state, seed, arms in items:
        des = design(arms, states, rounds)
        t = probe(des, cell, d, state)
        des.reps, des.warmup = REPS_LONG if t >= 1.0 else REPS_SHORT
        t0 = time.time()
        rec = run_cell(des, cell, d, state)
        rec.update({'seed': seed, 'probe_s': t, 'reps': des.reps, 'warmup': des.warmup, 'wall_s': round(time.time() - t0, 1),
                    'arms': {a.name: {'engine': a.engine, 'path': a.path, 'env': a.env} for a in arms}})
        recs.append(rec)
        json.dump({'meta': meta, 'records': recs}, open(f'{OUT}/{name}.json', 'w'))
        print(utc(), name, state, seed, cell.id, 'agree', rec['agree'], f"{rec['wall_s']:.0f}s", flush=True)
    meta['end_utc'] = utc()
    json.dump({'meta': meta, 'records': recs}, open(f'{OUT}/{name}.json', 'w'))


def median_time(exp, cell_id, seed, arm, state=None):
    """Median block time (s) of an arm in an earlier experiment, for sizing plants."""
    data = json.load(open(f'{OUT}/{exp}.json'))
    for r in data['records']:
        if r['cell'] == cell_id and r['seed'] == seed and (state is None or r['state'] == state):
            return statistics.median(b['med'] for rd in r['timing']['rounds'] for b in rd if b['w'] == arm) / 1e9
    raise KeyError((exp, cell_id, seed, arm))


def plant_arms(mk, key, base_s):
    arms = [mk('Yd', key), mk('Ya', key)]
    for frac in (0.02, 0.05, 0.15):
        arms.append(mk(f'P{int(frac * 100)}', key, {'LD_PRELOAD': PLANT, 'GAPCR_PLANT_US': str(int(base_s * frac * 1e6))}))
    arms += [mk('Pnull', key, {'LD_PRELOAD': PLANT, 'GAPCR_PLANT_US': '0'}), mk('Psham', key, {'GAPCR_SHAM': '1'})]
    return arms


def pad(n):
    return {'GAPCR_PAD': 'x' * n}


SEEDS_C = (0, 3000, 6000)
STATES_B = {'C': {'LC_ALL': 'C'}, 'U': {'LC_ALL': 'C.UTF-8'}}
STATES_A = {'S1': {}, 'S0': {}}
STATES_C = {'-': {}}


def experiments(name):
    D = lambda s: f'{P}/data/b{s}'
    DA = lambda s: f'{P}/data/a{s}'
    if name == 'C_SURVEY':
        arms = [c_arm('Yd', 'Y1'), c_arm('Ya', 'Y1'), c_arm('Rd', 'R1'), c_arm('Ra', 'R1')]
        items = [(c_cell(s, t, m), P, '-', s, arms) for s in SEEDS_C for t in (1, 4) for m in ('-1', 'avx2', 'none')]
        return items, STATES_C, None
    if name == 'C_TIMESPLIT':
        arms = [c_arm('Y0d', 'Y0'), c_arm('Y0a', 'Y0'), c_arm('R0d', 'R0'), c_arm('Y1d', 'Y1')]
        items = [(c_cell(s, t, '-1'), P, '-', s, arms) for s in SEEDS_C for t in (1, 4)]
        return items, STATES_C, None
    if name == 'C_SWAPS':
        arms = [c_arm('P1400p', 'P1400p'), c_arm('P1400', 'P1400'), c_arm('P1397p', 'P1397p'), c_arm('P1397', 'P1397')]
        items = [(c_cell(s, 1, '-1'), P, '-', s, arms) for s in SEEDS_C]
        return items, STATES_C, 8
    if name == 'C_PLANTS':
        items = []
        for s in (3000, 6000):
            cell = c_cell(s, 1, '-1')
            items.append((cell, P, '-', s, plant_arms(c_arm, 'Y1', median_time('C_SURVEY', cell.id, s, 'Yd'))))
        return items, STATES_C, None
    if name == 'C_LAYOUT':
        arms = [c_arm('Yd', 'Y1'), c_arm('Ye1', 'Y1', pad(1024)), c_arm('Ye2', 'Y1', pad(2048)), c_arm('Ye3', 'Y1', pad(3072))]
        items = [(c_cell(0, t, m), P, '-', 0, arms) for t, m in ((1, '-1'), (1, 'none'), (4, '-1'))]
        return items, STATES_C, None
    if name == 'B_TIMESPLIT':
        arms = [b_arm('Y0d', 'Y0'), b_arm('Y0a', 'Y0'), b_arm('Rd', 'R'), b_arm('Yd', 'Y1')]
        names = ['base64', 'base64_d', 'cksum', 'sha256sum', 'md5sum', 'b2sum', 'wc_l', 'wc_w', 'sort', 'cut', 'cat']
        return [(b_cell(n), D(s), 'C', s, arms) for s in (1, 2) for n in names], STATES_B, None
    if name == 'B_KO':
        arms = [b_arm('Y0d', 'Y0'), b_arm('Yd', 'Y1'), b_arm('Rd', 'R'), b_arm('Rk', 'R', KO)]
        names = ['cksum', 'base64', 'sha256sum', 'md5sum', 'b2sum', 'wc_l', 'wc_w']
        return [(b_cell(n), D(s), 'C', s, arms) for s in (1, 2) for n in names], STATES_B, None
    if name == 'B_SURVEY':
        arms = [b_arm('Yd', 'Y1'), b_arm('Ya', 'Y1'), b_arm('Rd', 'R'), b_arm('Ra', 'R')]
        items = [(b_cell(n), D(s), 'C', s, arms) for s in (1, 2) for n in B_CELLS]
        items += [(b_cell(n), D(s), 'U', s, arms) for s in (1, 2) for n in ('wc_m', 'sort', 'sort_u')]
        return items, STATES_B, None
    if name == 'B_PLANTS':
        items = [(b_cell(n), D(2), 'C', 2, plant_arms(b_arm, 'Y1', median_time('B_SURVEY', f'B_{n}', 2, 'Yd', 'C')))
                 for n in ('cksum', 'wc_l', 'sort', 'cut')]
        return items, STATES_B, None
    if name == 'B_LAYOUT':
        arms = [b_arm('Yd', 'Y1'), b_arm('Ye1', 'Y1', pad(1024)), b_arm('Ye2', 'Y1', pad(2048)), b_arm('Ye3', 'Y1', pad(3072))]
        return [(b_cell(n), D(1), 'C', 1, arms) for n in ('cksum', 'sort', 'base64')], STATES_B, None
    if name == 'A_SURVEY':
        arms = [a_arm('Yd', 'Y1'), a_arm('Ya', 'Y1'), a_arm('Rd', 'R'), a_arm('Ra', 'R')]
        items = [(a_cell(n), DA(s), 'S1', s, arms) for s in (1, 2) for n in A_NAMES]
        items += [(a_cell(n), DA(1), 'S0', 1, arms) for n in ('point_index', 'range_index', 'group_by', 'join2', 'join3_star', 'in_subquery')]
        return items, STATES_A, None
    if name == 'A_TIMESPLIT':
        arms = [a_arm('Y0d', 'Y0'), a_arm('Y0a', 'Y0'), a_arm('Rd', 'R'), a_arm('Yd', 'Y1')]
        return [(a_cell(n), DA(2), 'S1', 2, arms) for n in A_NAMES], STATES_A, None
    if name == 'A_PLANTS':
        items = [(a_cell(n), DA(2), 'S1', 2, plant_arms(a_arm, 'Y1', median_time('A_SURVEY', f'A_{n}', 2, 'Yd', 'S1')))
                 for n in ('scan_agg', 'join2')]
        return items, STATES_A, None
    if name == 'A_LAYOUT':
        arms = [a_arm('Yd', 'Y1'), a_arm('Ye1', 'Y1', pad(1024)), a_arm('Ye2', 'Y1', pad(2048)), a_arm('Ye3', 'Y1', pad(3072))]
        return [(a_cell(n), DA(1), 'S1', 1, arms) for n in ('scan_agg', 'point_rowid', 'join2')], STATES_A, None
    if name == 'A_KO':   # DEVIATIONS.md #4: plan-equalized contrasts for claim A1; every arm uses the same pipe wrapper
        def pa(arm_name, wrapper, env):
            return Arm(arm_name, wrapper, 'multicall', f'{P}/bin/{wrapper}', env)
        bloom = {'KO': f'{P}/bin/ko_bloom.sql'}
        items = []
        for s in (1, 2):
            db = lambda st: {'A_DB': f'{DA(s)}/db_{st}'}
            items.append((a_cell('in_subquery'), DA(s), 'S1', s,
                          [pa('Yp', 'wrap_t1_pipe', {}), pa('Ya', 'wrap_t1_pipe', {}), pa('Rp', 'wrap_sqlite_ko', {}), pa('Rk', 'wrap_sqlite_ko', bloom)]))
            items.append((a_cell('join3_star'), DA(s), 'S1', s,
                          [pa('Y0p', 'wrap_t0_pipe', {}), pa('Y1p', 'wrap_t1_pipe', {}), pa('Rp', 'wrap_sqlite_ko', {}), pa('Rk', 'wrap_sqlite_ko', bloom)]))
            items.append((a_cell('join2'), DA(s), 'S1', s,
                          [pa('Y_S1', 'wrap_t1_pipe', db('S1')), pa('R_S0', 'wrap_sqlite_ko', db('S0')),
                           pa('Y_S0', 'wrap_t1_pipe', db('S0')), pa('R_S1', 'wrap_sqlite_ko', db('S1'))]))
        return items, STATES_A, None
    if name == 'A_KO2':  # DEVIATIONS.md #7 (exploratory): DistinctOpt knock-out makes SQLite use Turso's distinct operator
        def pa(arm_name, wrapper, env):
            return Arm(arm_name, wrapper, 'multicall', f'{P}/bin/{wrapper}', env)
        ko = {'KO': f'{P}/bin/ko_distinct.sql'}
        items = [(a_cell('distinct'), DA(s), 'S1', s, [pa('Yp', 'wrap_t1_pipe', {}), pa('Ya', 'wrap_t1_pipe', {}),
                                                         pa('Rp', 'wrap_sqlite_ko', {}), pa('Rk', 'wrap_sqlite_ko', ko)]) for s in (1, 2)]
        return items, STATES_A, None
    if name in ('B_ARCH', 'B_ENV'):  # DEVIATIONS.md #8: planted classes under the contract variant V_F
        sizes = {n: median_time('B_SURVEY', f'B_{n}', 2, 'Rd', 'C') for n in ('cksum', 'sort')}
        plant = lambda s: {'LD_PRELOAD': PLANT, 'GAPCR_PLANT_US': str(int(s * 1e6))}
        if name == 'B_ARCH':
            items = []
            for n in ('cksum', 'sort'):
                arms = [b_arm('Rd', 'R'), b_arm('Ra', 'R'), b_arm('Yd', 'Y1'), b_arm('Ya', 'Y1'),
                        b_arm('P2', 'Y1', plant(2.0 * sizes[n])), b_arm('P05', 'Y1', plant(0.5 * sizes[n]))]
                items.append((b_cell(n), D(2), 'C', 2, arms))
            return items, STATES_B, None
        arms = [b_arm('E0', 'R')] + [b_arm(f'E_{n}_{k}', 'R', plant(f * sizes[n])) for n in ('cksum', 'sort') for k, f in (('2', 2.0), ('05', 0.5))]
        return [(b_cell('true'), D(2), 'C', 2, arms)], STATES_B, None
    if name == 'A_RO':  # DEVIATIONS.md #9: --readonly as a configuration witness for the startup gap
        ro = Arm('Yro', 'turso-0.8.3-ro', 'multicall', f'{P}/bin/wrap_t1_ro', {})
        arms = [a_arm('Yd', 'Y1'), ro, a_arm('Rd', 'R'), a_arm('Ra', 'R')]
        return [(a_cell(n), DA(s), 'S1', s, arms) for s in (1, 2) for n in ('startup', 'point_index')], STATES_A, None
    if name == 'W_ARCH':  # DEVIATIONS.md #10: uutils under its wasm32-wasip1 contract, on XFS with reflink
        WB = '/work/wasi/bin'
        wa = lambda n, w: Arm(n, w, 'multicall', f'{WB}/{w}', {})
        cp_arms = [wa('Rd', 'cp_gnu'), wa('Ra', 'cp_gnu'), wa('Rk', 'cp_gnu_never'), wa('Yn', 'cp_uu'), wa('Yw', 'cp_wasi')]
        ck_arms = [wa('Rd', 'cksum_gnu'), wa('Ra', 'cksum_gnu'), wa('Yn', 'cksum_uu'), wa('Yw', 'cksum_wasi')]
        items = [(Cell('W_cp512', ['/mnt/xfs/in512'], family='cp', factors={'bytes': 512 << 20}), '/mnt/xfs', 'X', 512, cp_arms),
                 (Cell('W_cp128', ['/mnt/xfs/in128'], family='cp', factors={'bytes': 128 << 20}), '/mnt/xfs', 'X', 128, cp_arms),
                 (Cell('W_cksum32', ['/mnt/xfs/bin32'], family='cksum', factors={'bytes': 32 << 20}), '/mnt/xfs', 'X', 32, ck_arms)]
        return items, {'X': {}}, None
    raise KeyError(name)


if __name__ == '__main__':
    for exp in sys.argv[1:]:
        items, states, rounds = experiments(exp)
        print(utc(), 'START', exp, len(items), 'cells', flush=True)
        run_exp(exp, items, states, rounds)
        print(utc(), 'END', exp, flush=True)
