"""Executing a design: output verification, timed blocks with warm-ups, whole-panel runs with pinned binaries.

One generic record per cell (and state), whatever the case's file format (celltest.write converts it):
  {'cell', 'state', 'setting', 'role', 'family', 'factors', 'argv',
   'verify': {arm: {'sha256', 'rc', 'bytes', 'stderr'}},
   'agree': [bool per design.agree group], 'equal_to_ref': {arm: 'equal' | 'differ'},
   'timing': {'rounds': [[{'w': arm, 'med': ns}, ...], ...]}}   (timed only when every agree group holds)
A block is `warmup` discarded runs then `reps` timed runs; its value is the median wall time in ns (stdout and
stderr to /dev/null). Verification runs once per arm before timing, capturing stdout's sha256 and the exit status.
Arms whose path is pinned (celltest.registry.pin) are re-checked before every cell."""
import hashlib, json, os, statistics, subprocess, time

from . import registry
from .spec import command_env


def verify_output(argv, env, stderr_chars=300):
    p = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'rc': p.returncode, 'sha256': hashlib.sha256(p.stdout).hexdigest(), 'bytes': len(p.stdout),
            'stderr': p.stderr.decode(errors='replace')[:stderr_chars]}


def timed_block(argv, env, reps, warmup=0, clock=time.perf_counter_ns):
    for _ in range(warmup):
        subprocess.run(argv, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ts = []
    for _ in range(reps):
        t0 = clock()
        subprocess.run(argv, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ts.append(clock() - t0)
    return statistics.median(ts)


def same_output(a, b):
    return a['sha256'] == b['sha256'] and a['rc'] == b['rc']


def run_cell(design, cell, data_dir, state, pins=None):
    cmds = {a.name: command_env(design, a, cell, data_dir, state) for a in design.arms}
    for p in (pins or {}).values():
        registry.check_pin(p)
    ver = {name: verify_output(*cmds[name]) for name in cmds}
    agree = [all(same_output(ver[g[0]], ver[x]) for x in g) for g in design.agree]
    ref = design.ref_arm or design.arms[0].name
    rec = {'cell': cell.id, 'state': state, 'setting': cell.setting, 'role': cell.role, 'family': cell.family,
           'factors': cell.factors, 'argv': cell.argv, 'verify': ver, 'agree': agree,
           'equal_to_ref': {n: ('equal' if same_output(ver[ref], ver[n]) else 'differ') for n in cmds if n != ref},
           'timing': {'rounds': []}}
    if all(agree):
        for order in design.orders:
            rec['timing']['rounds'].append([{'w': n, 'med': timed_block(*cmds[n], design.reps, design.warmup)} for n in order])
    return rec


def plan(cells, states):
    """The run order: a panel whose cells are all bound to a state runs in panel order (cu1's replication panel; the
    order fixes the order of the analysis's random draws); otherwise every state, then every cell (cu1's survey)."""
    if cells and all(c.state for c in cells):
        return [(c.state, c) for c in cells if c.state in states]
    return [(st, c) for st in states for c in cells]


def run_panel(design, cells, data_dir, states=None, pins=None, progress=print, checkpoint=None):
    """Runs the plan's (state, cell) pairs. checkpoint(records) is called after every cell (e.g. to rewrite the run
    file). Returns the records in run order."""
    records = []
    for state, cell in plan(cells, states or list(design.states)):
        rec = run_cell(design, cell, data_dir, state, pins)
        records.append(rec)
        if progress:
            progress(state, cell.id, cell.setting or '', 'agree', rec['agree'], 'equal_to_ref', rec['equal_to_ref'])
        if checkpoint:
            checkpoint(records)
    return records
