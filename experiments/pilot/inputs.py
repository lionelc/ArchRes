"""Seeded inputs for the pilot: Pair B files, Pair A databases and SQL scripts. Pair C uses the Chimera clip segments.

  python3 inputs.py /work/pilot/data
writes data/b<seed>/... and data/a<seed>/... for seeds 1 and 2. Every engine of Pair A gets its own byte-identical
copy of each database (suffix .s = SQLite, .t1 = Turso 0.8.3, .t0 = Turso 0.5.0)."""
import base64, os, random, shutil, sqlite3, subprocess, sys

MiB = 1 << 20
SQLITE = '/work/pilot/bin/sqlite3-3.50.4'
WORDS = None


def words(rng):
    global WORDS
    if WORDS is None:
        r = random.Random(12345)
        WORDS = [''.join(r.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(r.randint(2, 11))) for _ in range(5000)]
    return WORDS


def text_lines(rng, nbytes, maxwords=14):
    ws = words(rng); out = []; n = 0
    while n < nbytes:
        line = ' '.join(rng.choice(ws) for _ in range(rng.randint(1, maxwords))) + '\n'
        out.append(line); n += len(line)
    return ''.join(out)[:nbytes].rsplit('\n', 1)[0] + '\n'


def pair_b(d, seed):
    rng = random.Random(1000 + seed); os.makedirs(d, exist_ok=True)
    raw = rng.randbytes(32 * MiB)
    open(f'{d}/bin32', 'wb').write(raw)
    open(f'{d}/bin32.b64', 'wb').write(subprocess.run(['/work/pilot/bin/gnu-9.12/bin/base64', f'{d}/bin32'],
                                                      capture_output=True, check=True).stdout)
    open(f'{d}/text32', 'w').write(text_lines(rng, 32 * MiB))
    small = text_lines(rng, 8 * MiB)
    open(f'{d}/text8', 'w').write(small)
    open(f'{d}/text8.sorted', 'w').write(''.join(sorted(small.splitlines(keepends=True))))
    open(f'{d}/nums4', 'w').write(''.join(f'{rng.randint(-10**9, 10**9)}\n' for _ in range(400000)))
    rows = [f'{rng.randint(1, 10**6)},{rng.choice(words(rng))},{rng.randint(0, 999)},{rng.choice(words(rng))},{rng.random():.6f}\n'
            for _ in range(800000)]
    open(f'{d}/csv32', 'w').write(''.join(rows))


A_CELLS = {  # name: (statement template, repetitions); every output is an integer or text, never a float
    'point_rowid': ('SELECT qty FROM orders WHERE id = {k};', 2000),
    'point_index': ('SELECT count(*) FROM orders WHERE cust = {c};', 600),
    'range_index': ('SELECT sum(qty) FROM orders WHERE day BETWEEN {d} AND {d} + 5;', 150),
    'scan_agg': ('SELECT sum(qty * price_cents) FROM orders;', 6),
    'count_star': ('SELECT count(*) FROM orders;', 60),
    'group_by': ('SELECT cust % 100 AS g, count(*), sum(qty) FROM orders GROUP BY g ORDER BY g;', 3),
    'join2': ('SELECT c.region, count(*), sum(o.qty) FROM orders o JOIN customers c ON o.cust = c.id GROUP BY c.region ORDER BY c.region;', 3),
    'join3_star': ('SELECT i.category, c.region, count(*) FROM orders o JOIN customers c ON o.cust = c.id JOIN items i ON o.item = i.id '
                   'WHERE c.region < 3 AND i.category < 5 GROUP BY i.category, c.region ORDER BY i.category, c.region;', 3),
    'order_limit': ('SELECT id FROM orders ORDER BY price_cents DESC, id LIMIT 10;', 15),
    'like': ("SELECT count(*) FROM orders WHERE note LIKE '%qz%';", 6),
    'in_subquery': ('SELECT count(*) FROM customers WHERE id IN (SELECT cust FROM orders WHERE price_cents > 99000);', 6),
    'distinct': ('SELECT count(DISTINCT cust) FROM orders;', 4),
    'insert_txn': (None, 3),
    'startup': ('SELECT 1;', 1),
}


def a_script(name, rng):
    tmpl, reps = A_CELLS[name]
    if name == 'insert_txn':
        return ''.join('BEGIN;\nINSERT INTO scratch SELECT id, cust, qty FROM orders WHERE id <= 40000;\nROLLBACK;\n'
                       for _ in range(reps))
    return ''.join(tmpl.format(k=rng.randint(1, 300000), c=rng.randint(1, 30000), d=rng.randint(0, 3600)) + '\n'
                   for _ in range(reps))


def pair_a(d, seed):
    rng = random.Random(2000 + seed); os.makedirs(d, exist_ok=True)
    base = f'{d}/base.db'
    if os.path.exists(base):
        os.remove(base)
    con = sqlite3.connect(base); cur = con.cursor()
    cur.executescript('''PRAGMA page_size=4096;
      CREATE TABLE customers(id INTEGER PRIMARY KEY, region INT, name TEXT);
      CREATE TABLE items(id INTEGER PRIMARY KEY, category INT, label TEXT);
      CREATE TABLE orders(id INTEGER PRIMARY KEY, cust INT, item INT, qty INT, price_cents INT, day INT, note TEXT);
      CREATE TABLE scratch(id INT, cust INT, qty INT);''')
    ws = words(rng)
    cur.executemany('INSERT INTO customers VALUES (?,?,?)', [(i, rng.randint(0, 9), rng.choice(ws)) for i in range(1, 30001)])
    cur.executemany('INSERT INTO items VALUES (?,?,?)', [(i, rng.randint(0, 49), rng.choice(ws)) for i in range(1, 5001)])
    cur.executemany('INSERT INTO orders VALUES (?,?,?,?,?,?,?)',
                    [(i, int(rng.paretovariate(1.2)) % 30000 + 1, rng.randint(1, 5000), rng.randint(1, 20), rng.randint(100, 100000),
                      rng.randint(0, 3650), ' '.join(rng.choice(ws) for _ in range(rng.randint(2, 8)))) for i in range(1, 300001)])
    cur.executescript('CREATE INDEX orders_cust ON orders(cust); CREATE INDEX orders_day ON orders(day); '
                      'CREATE INDEX customers_region ON customers(region);')
    con.commit(); con.close()
    for state in ('S0', 'S1'):
        db = f'{d}/db_{state}'
        shutil.copyfile(base, db)
        sql = ('PRAGMA journal_mode=WAL; ' + ('ANALYZE; ' if state == 'S1' else '') + 'VACUUM; PRAGMA wal_checkpoint(TRUNCATE);')
        subprocess.run([SQLITE, db, sql], check=True, capture_output=True)
        for suf in ('s', 't1', 't0'):
            shutil.copyfile(db, f'{db}.{suf}')
    os.remove(base)
    for name in A_CELLS:
        open(f'{d}/q_{name}.sql', 'w').write(a_script(name, rng))


if __name__ == '__main__':
    root = sys.argv[1]
    for seed in (1, 2):
        pair_b(f'{root}/b{seed}', seed)
        pair_a(f'{root}/a{seed}', seed)
        print('seed', seed, 'done')
