"""Deterministic counters for whole-process cells (Linux): callgrind, strace -c, /usr/bin/time.

  callgrind(cmd, env)        user-space instruction total and the top functions by self instructions (callgrind_annotate)
  strace_counts(cmd, env)    system calls by name (kernel work that callgrind cannot see: read sizes, copy_file_range,
                             splice, threads via clone/clone3)
  time_v(cmd, env)           max RSS (KiB), user and system CPU seconds, wall seconds (context, not deterministic)
  signature(top, pct)        the functions with at least `pct` % of self instructions (a deterministic witness)
  switch_capture(...)        one cell with a fix's switch OFF and ON: instruction ratio, signatures, marker presence
Instruction counts depend on the binary, the input and the environment, not on machine load, so captures may run
alongside other work; timing runs may not."""
import os, re, subprocess, tempfile

STRACE_LINE = re.compile(r'\s*[\d.]+\s+[\d.]+\s+\d+\s+(\d+)\s+(?:(\d+)\s+)?(\w+)\s*$')
CG_TOTAL = re.compile(r'\s*([\d,]+) \(100\.0%\)\s+PROGRAM TOTALS')
CG_FN = re.compile(r'\s*([\d,]+) \(\s*([\d.]+)%\)\s+(\S.*)$')


def strace_counts(cmd, env, tmpdir=None):
    with tempfile.NamedTemporaryFile('r', suffix='.st', dir=tmpdir) as f:
        subprocess.run(['strace', '-f', '-c', '-o', f.name, *cmd], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        counts = {}
        for ln in open(f.name):
            m = STRACE_LINE.match(ln)
            if m and m.group(3) != 'total':
                counts[m.group(3)] = int(m.group(1))
        return counts


def time_v(cmd, env):
    p = subprocess.run(['/usr/bin/time', '-f', '%M %U %S %e', *cmd], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    m, u, s, e = p.stderr.strip().splitlines()[-1].split()
    return {'max_rss_kib': int(m), 'user_s': float(u), 'sys_s': float(s), 'wall_s': float(e)}


def callgrind(cmd, env, tmpdir=None, top=15):
    with tempfile.TemporaryDirectory(dir=tmpdir) as d:
        out = os.path.join(d, 'cg.out')
        subprocess.run(['valgrind', '--tool=callgrind', f'--callgrind-out-file={out}', *cmd], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ann = subprocess.run(['callgrind_annotate', '--threshold=99', out], capture_output=True, text=True).stdout
    total, fns = None, []
    for ln in ann.splitlines():
        m = CG_TOTAL.match(ln)
        if m:
            total = int(m.group(1).replace(',', ''))
        m = CG_FN.match(ln)
        if m and 'PROGRAM TOTALS' not in ln and len(fns) < top:
            fns.append({'ir': int(m.group(1).replace(',', '')), 'pct': float(m.group(2)), 'fn': m.group(3)[:160]})
    return {'ir_total': total, 'top_self': fns}


def signature(top_self, pct=1.0):
    return sorted({t['fn'].split(' [')[0] for t in top_self if t['pct'] >= pct})


def switch_capture(cmd, env_off, env_on, marker, tmpdir=None):
    """A fix's deterministic leg on one cell: the same command with the switch OFF and ON."""
    rec = {}
    for arm, env in (('off', env_off), ('on', env_on)):
        cg = callgrind(cmd, env, tmpdir)
        sig = signature(cg['top_self'])
        rec[arm] = {'ir_total': cg['ir_total'], 'sig': sig, 'marker_in_top': any(marker in s for s in sig)}
    rec['ir_ratio_on_off'] = rec['on']['ir_total'] / rec['off']['ir_total']
    return rec
