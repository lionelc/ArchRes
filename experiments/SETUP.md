# Reproducing the pilot experiments locally

The scripts expect binaries and data under `/work/pilot` (and `/work/wasi`, `/work/agent`, `/mnt/xfs` for the later
addenda). These paths are hard-coded at the top of each script (`P = '/work/pilot'`). Either create these directories,
or edit the constants. Binaries are pinned by sha256 in `pilot/manifest.json`. Check yours against it: a different
build is a different engine.

The original host was Ubuntu 24.04.5 (glibc 2.39, gcc 13.3.0, Python 3.11, valgrind 3.22) on a 4-vCPU Xeon with
AVX-512. Timings differ on other hosts, and that is expected. The registered rules (bands, matched nulls, verdicts) are
computed from your own A/A arms.

## 1. Tools

```
apt-get install -y build-essential python3 valgrind strace sqlite3 nasm meson xfsprogs
```

`celltest/` (in this repository, imported by `pilot/run.py`) is the timing harness. It provides counterbalanced
rotation rounds, A/A arms and output checks.

## 2. Pair A: Turso against SQLite

- **SQLite 3.50.4 CLI.** Build it from the amalgamation (`sqlite-amalgamation-3500400.zip`, sqlite.org) with gcc 13.3,
  for example:
  ```
  gcc -O2 -DSQLITE_ENABLE_STMT_SCANSTATUS -DSQLITE_ENABLE_EXPLAIN_COMMENTS shell.c sqlite3.c -lm -lpthread -ldl -o /work/pilot/bin/sqlite3-3.50.4
  ```
  The exact compile options of the binary used are in `pilot/bin_helpers/sqlite_compile_options.txt`. Compare them
  with `PRAGMA compile_options;`, and match them if they differ.
- **Turso CLI 0.8.3 and 0.5.0.** Use the release binaries (`tursodb`, x86_64 Linux) from the project's GitHub
  releases, unpacked to `/work/pilot/bin/turso-0.8.3/` and `/work/pilot/bin/turso-0.5.0/`.
- **Wrappers.** Copy `pilot/bin_helpers/wrap_*` and `ko_*.sql` to `/work/pilot/bin/` and make the wrappers
  executable.

## 3. Pair B: uutils against GNU coreutils

- **GNU coreutils 9.12.** Build from `coreutils-9.12.tar.xz`:
  ```
  FORCE_UNSAFE_CONFIGURE=1 ./configure --prefix=/work/pilot/bin/gnu-9.12 && make -j && make install
  ```
  It links OpenSSL libcrypto if the development package is present, which the `OPENSSL_ia32cap` knock-out needs.
- **uutils 0.12.0 and 0.2.0.** Use the release tarballs (x86_64-unknown-linux-gnu), unpacked to
  `/work/pilot/bin/uu-0.12.0/` and `/work/pilot/bin/uu-0.2.0/`. Each contains the multicall `coreutils` binary.
- **Planted mechanisms.** Build the plant library:
  ```
  gcc -O2 -shared -fPIC pilot/plant.c -o /work/pilot/bin/libplant.so
  ```

## 4. Data

```
python3 pilot/inputs.py /work/pilot/data
```

This writes the Pair B files and the Pair A databases and scripts for seeds 1 and 2. Every engine gets its own
byte-identical copy of each database.

## 5. Running

```
cd pilot
python3 capture.py results/captures.json          # deterministic captures (callgrind)
python3 plans.py                                  # query plans
python3 run.py A_SURVEY A_TIMESPLIT A_KO A_KO2 B_SURVEY B_TIMESPLIT B_KO A_PLANTS B_PLANTS A_LAYOUT B_LAYOUT
python3 run.py B_ARCH B_ENV A_RO                  # addenda #8 and #9
python3 markers.py; python3 sqlite_ops.py; python3 capture_extra.py; python3 natural_floors.py
python3 analyze.py && python3 report.py           # results/summary.json and results/tables.md
```

- Never run captures and timing at the same time: the registration forbids overlap.
- `run.py` writes `results/<EXP>.json` after every cell.
- Pair C experiments (C_*) need rav1d, dav1d and the Chimera clip. The paper no longer reports them; see
  `pilot/REGISTRATION.md` and `pilot/manifest.json` if you want them.

## 6. Addendum #10: uutils under WebAssembly (natural architectural gap)

1. Build uutils 0.12.0 (tag `0.12.0`) for WASI, as uutils' CI does:
   ```
   rustup target add wasm32-wasip1
   cargo build --release --target wasm32-wasip1 --no-default-features --features feat_wasm
   ```
2. Precompile the module with wasmtime 50.0.1:
   ```
   wasmtime compile target/wasm32-wasip1/release/coreutils.wasm -o /work/wasi/coreutils.cwasm
   ```
3. Install the runtime at `/work/wasi/wasmtime-v50.0.1-x86_64-linux/wasmtime`.
4. Create an XFS file system with reflink. This needs root and loop devices; the original image was in RAM:
   ```
   truncate -s 3G /dev/shm/xfs.img && mkfs.xfs -f /dev/shm/xfs.img && mkdir -p /mnt/xfs && mount -o loop /dev/shm/xfs.img /mnt/xfs
   head -c 536870912 /dev/urandom > /mnt/xfs/in512; head -c 134217728 /mnt/xfs/in512 > /mnt/xfs/in128
   head -c 33554432 /dev/urandom > /mnt/xfs/bin32
   ```
5. Copy `pilot/wasi_wrappers/*` to `/work/wasi/bin/`.
6. Build the envelope probe:
   ```
   gcc -O2 pilot/envelope.c -o /work/wasi/env/envelope
   ```
7. Run:
   ```
   cd pilot && python3 run.py W_ARCH
   for f in in512 in128 bin32; do /work/wasi/env/envelope /mnt/xfs/$f /mnt/xfs/env_out 5; done > results/envelope_xfs.jsonl
   python3 analyze.py
   ```

## 7. Addendum #11: builder-agent error rates

See `agent/README.md`. You need:
- llama.cpp, any recent build; the original was commit 68598133;
- Qwen3-8B-Q4_K_M.gguf from `Qwen/Qwen3-8B-GGUF` on Hugging Face (sha256 d98cdcbd…5785);
- the callgrind profiles quoted in the prompts, from `agent/profile_cells.sh`.

The prompts are committed (`agent/prompts/`), so you can rerun the builder without regenerating them:
```
llama-server -m Qwen3-8B-Q4_K_M.gguf -c 8192 -t 4 --port 8088 --jinja &
cd agent && python3 run_builder.py 1 2 && python3 audit.py
```

## 8. Theory scripts (standard library only)

```
python3 theory/sim_certificates.py --n 20000 --seed 7
python3 theory/sim_breakdown.py
python3 theory/review_checks.py
```
