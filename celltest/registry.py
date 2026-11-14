"""Registration helpers: seeds derived from a registration file, code freezes, pinned binaries, run metadata.

The registered protocol of a case fixes, before any data: the code (by sha256), the binaries (by sha256) and the seeds
(derived from the registration's own sha256, so they cannot be chosen after the fact)."""
import hashlib, os, platform, time
from pathlib import Path


class RegistryError(RuntimeError):
    pass


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive_seed(prefix, k, registration_sha=None, length=16):
    """sha256('<prefix>:<registration sha256>:<k>')[:length], or sha256('<prefix>:<k>') when no registration is named
    (cu1's discovery seeds: derive_seed('cu1:disc', k))."""
    text = f'{prefix}:{registration_sha}:{k}' if registration_sha else f'{prefix}:{k}'
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def derive_seeds(prefix, n, registration=None, start=0, length=16):
    """Seeds k = start .. start+n-1; `registration` is a path whose sha256 enters every seed."""
    reg = sha256_file(registration) if registration else None
    return [derive_seed(prefix, k, reg, length) for k in range(start, start + n)]


def freeze(paths, root='.'):
    """{relative path: sha256} for the files a registration freezes."""
    root = Path(root)
    return {str(p): sha256_file(root / p) for p in paths}


def verify(manifest, root='.'):
    """Files whose current sha256 differs from the manifest (empty list = intact)."""
    root = Path(root)
    return [p for p, h in manifest.items() if not (root / p).exists() or sha256_file(root / p) != h]


def require_intact(manifest, root='.'):
    bad = verify(manifest, root)
    if bad:
        raise RegistryError(f'frozen files changed since registration: {bad}')


def pin(path, expect=None):
    """A binary reference that a run checks before every use: {'path', 'sha256'}. With expect (the registered sha256),
    refuse a binary that is not that build (cu1 lesson: a fixed path was later rebuilt with a repair; a pin taken at
    start would have accepted it)."""
    p = {'path': str(path), 'sha256': sha256_file(path)}
    if expect and p['sha256'] != expect:
        raise RegistryError(f"{path} is not the registered build: {p['sha256'][:16]} != {expect[:16]}")
    return p


def check_pin(p):
    """Refuse to run a binary that changed since it was pinned (cu1 lesson: a binary was overwritten under a capture)."""
    now = sha256_file(p['path'])
    if now != p['sha256']:
        raise RegistryError(f"pinned binary changed: {p['path']} {p['sha256'][:16]} -> {now[:16]}")
    return True


def utc_now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def run_meta(**extra):
    """Metadata recorded with every run: real UTC time, platform, CPU affinity, load average (cu1 lesson: never estimate)."""
    m = {'started_utc': utc_now(), 'platform': platform.platform(), 'python': platform.python_version(),
         'cpu_count': os.cpu_count(), 'loadavg_start': os.getloadavg() if hasattr(os, 'getloadavg') else None}
    if hasattr(os, 'sched_getaffinity'):
        m['sched_affinity'] = len(os.sched_getaffinity(0))
    m.update(extra)
    return m


def finish_meta(m, t0):
    m.update({'finished_utc': utc_now(), 'elapsed_s': round(time.time() - t0, 1),
              'loadavg_end': os.getloadavg() if hasattr(os, 'getloadavg') else None})
    return m
