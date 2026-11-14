#!/bin/sh
# Passive evidence for the builder agent: callgrind self-cost profiles of both engines on Pair A's gap cells (seed 1).
D=/work/pilot/data/a1
for q in point_rowid point_index scan_agg join3_star order_limit like in_subquery distinct insert_txn startup; do
  valgrind --tool=callgrind --callgrind-out-file=/work/agent/profiles/turso_$q.out /work/pilot/bin/turso-0.8.3/tursodb -q -m list $D/db_S1.t1 < $D/q_$q.sql > /dev/null 2>&1
  valgrind --tool=callgrind --callgrind-out-file=/work/agent/profiles/sqlite_$q.out /work/pilot/bin/sqlite3-3.50.4 -batch $D/db_S1.s < $D/q_$q.sql > /dev/null 2>&1
  echo done $q
done
echo PROFILES_DONE
