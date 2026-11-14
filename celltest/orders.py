"""Block-order designs for paired timing, and the checks that make them counterbalanced.

A round runs every connection (arm) in two blocks; the two blocks of one connection form an A/A pair. The order of the
blocks inside a round matters (cu1: a block that follows another engine's block can run slower), so designs vary it
across rounds and the checks below must pass before a design is used.

cu1 lesson: "reverse the order on odd rounds" is a no-op when the order is a palindrome (gd ga ud ua ua ud ga gd), so
check() rejects designs whose rounds are all identical."""


class OrderError(ValueError):
    pass


def abba(a, b):
    """The classic two-engine block: a b b a (ts1 and cu1's discovery survey)."""
    return [a, b, b, a]


def mirror(first):
    """A round from its first half: first + reversed(first); every connection appears twice (palindromic by design)."""
    return list(first) + list(first)[::-1]


def rotation(conns, rounds):
    """Round r: first half = conns rotated by r, second half reversed. Over len(conns) rounds every connection takes
    every first-half position once (cu1 amendment 2c)."""
    n = len(conns)
    return [mirror(conns[r % n:] + conns[:r % n]) for r in range(rounds)]


def cycle(orders, rounds):
    """Round r uses orders[r % len(orders)] (cu1 amendment 2b: four explicit orders)."""
    return [list(orders[r % len(orders)]) for r in range(rounds)]


def alternate_reversed(order, rounds):
    """Round r uses order, reversed on odd rounds. NOT a counterbalance if `order` is a palindrome (kept to reproduce
    cu1's first verdict run; check() flags it)."""
    return [list(order) if r % 2 == 0 else list(order)[::-1] for r in range(rounds)]


def is_palindrome(order):
    return list(order) == list(order)[::-1]


def check(orders, conns, require_distinct=True, require_position_balance=True, blocks_per_conn=2):
    """Checks of a whole design (all rounds). Returns a report; raises OrderError when a required check fails.
      distinct           not every round is the same order (a single repeated order has no counterbalance)
      blocks             each round holds every connection exactly `blocks_per_conn` times
      position_balance   over the design, each first-half position is taken by each connection equally often
                         (exact when the number of rounds is a multiple of the number of connections)"""
    conns = list(conns); rounds = [list(o) for o in orders]
    rep = {'rounds': len(rounds), 'distinct_orders': len({tuple(o) for o in rounds}),
           'blocks_ok': all(sorted(o) == sorted(conns * blocks_per_conn) for o in rounds),
           'palindromic_rounds': sum(is_palindrome(o) for o in rounds)}
    half = len(conns)
    counts = {i: {c: 0 for c in conns} for i in range(half)}
    for o in rounds:
        for i in range(half):
            counts[i][o[i]] += 1
    vals = [v for i in counts for v in counts[i].values()]
    rep['position_counts'] = counts
    rep['position_balanced'] = max(vals) - min(vals) == 0
    if not rep['blocks_ok']:
        raise OrderError(f'a round does not hold every connection {blocks_per_conn} times')
    if require_distinct and rep['distinct_orders'] < 2:
        raise OrderError('all rounds use the same block order: no counterbalance (palindrome reversal?)')
    if require_position_balance and not rep['position_balanced']:
        raise OrderError(f'first-half positions are not balanced: {counts}')
    return rep
