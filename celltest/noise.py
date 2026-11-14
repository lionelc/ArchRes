"""A/A noise diagnostics for paired timing files (any of celltest.write's formats).

  single_block_pairs(cell)        |log(block1 / block2)| per arm and round (what gapgraph's bands are built from)
  estimator(cell, a, b)           median over rounds of log(mean(a blocks) / mean(b blocks)) (the effect's estimator)
  band(values)                    p95, nearest rank (gapgraph.config.p95)
  matched_vs_single(cells, ...)   per stratum: the p95 of |estimator| for an A/A arm pair against the single-block band
                                  (cu1 step 34: 0.01-0.08 against 0.03-0.27; the mismatch that motivated sufficiency)
  outlier_blocks(cells, k)        blocks deviating from their round's same-engine median by more than k log units
  order_effects(cells, engine_of) mean log deviation of a block from its round's same-engine median, by the engine of
                                  the block before it (cu1 step 33)"""
import math, statistics

from .write import rounds_by_arm


def band(values):
    xs = sorted(values)
    return xs[min(len(xs) - 1, max(0, math.ceil(0.95 * len(xs)) - 1))] if xs else None


def single_block_pairs(cell):
    return {a: [abs(math.log(r[0] / r[1])) for r in rounds if len(r) == 2] for a, rounds in rounds_by_arm(cell).items()}


def estimator(cell, a, b):
    r = rounds_by_arm(cell)
    return statistics.median(math.log(statistics.mean(x) / statistics.mean(y)) for x, y in zip(r[a], r[b]))


def stratum_of(cell, ref, strata):
    ns = statistics.median(v for rd in rounds_by_arm(cell)[ref] for v in rd)
    for lo, hi, name in strata:
        if lo <= ns < hi:
            return name


def matched_vs_single(cells, aa_pair, ref, strata):
    """cells: {id: cell} of one run. Per stratum: {'matched_p95', 'matched_max', 'single_block_p95', 'cells'}."""
    m, s = {}, {}
    for c in cells.values():
        if not c['timing']['rounds']:
            continue
        st = stratum_of(c, ref, strata)
        m.setdefault(st, []).append(abs(estimator(c, *aa_pair)))
        for v in single_block_pairs(c).values():
            s.setdefault(st, []).extend(v)
    return {st: {'matched_p95': band(m[st]), 'matched_max': max(m[st]), 'single_block_p95': band(s.get(st, [])), 'cells': len(m[st])}
            for st in m}


def outlier_blocks(cells, k=0.2, engine_of=lambda arm: arm[0]):
    out = []
    for cid, c in cells.items():
        for i, rd in enumerate(c['timing']['rounds']):
            by = {}
            for b in rd:
                by.setdefault(engine_of(b.get('w', b.get('eng'))), []).append(b['med'])
            for b in rd:
                med = statistics.median(by[engine_of(b.get('w', b.get('eng')))])
                d = math.log(b['med'] / med)
                if abs(d) > k:
                    out.append({'cell': cid, 'round': i, 'arm': b.get('w', b.get('eng')), 'log_dev': round(d, 3)})
    return out


def order_effects(cells, engine_of=lambda arm: arm[0]):
    """{'<engine> after <engine>': mean log deviation} over all blocks except each round's first."""
    acc = {}
    for c in cells.values():
        for rd in c['timing']['rounds']:
            by = {}
            for b in rd:
                by.setdefault(engine_of(b.get('w', b.get('eng'))), []).append(b['med'])
            med = {e: statistics.median(v) for e, v in by.items()}
            for i in range(1, len(rd)):
                e, prev = engine_of(rd[i].get('w', rd[i].get('eng'))), engine_of(rd[i - 1].get('w', rd[i - 1].get('eng')))
                acc.setdefault(f'{e} after {prev}', []).append(math.log(rd[i]['med'] / med[e]))
    return {k: {'n': len(v), 'mean_log_dev': round(statistics.mean(v), 4)} for k, v in sorted(acc.items())}
