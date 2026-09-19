# justfile

default:
    just --list

install:
    git config --local core.hooksPath .githooks

# Check striptest.py against the README's worked examples, and index.html
# against striptest.py on random settings. Args (both optional):
#   rounds  random settings to compare                           [2000]
#   seed    RNG seed, "random" to roll one, or "HEAD" to derive  [HEAD]
#           it from the current commit hash.
# "HEAD" varies the settings per commit (surfacing latent bugs) yet stays
# reproducible: same commit -> same seed, and the resolved seed is printed so a
# failure replays via `just test <rounds> <seed>`. In the pre-commit hook HEAD
# is the previous commit, so every commit is checked against a fresh corpus.
# e.g. `just test`, `just test 50000`, `just test 2000 random`.
test rounds="2000" seed="HEAD":
    #!/usr/bin/env bash
    set -euo pipefail
    seed='{{seed}}'
    if [ "$seed" = "HEAD" ]; then
      hash=$(git rev-parse HEAD 2>/dev/null | head -c 8 || true)
      if [ -n "$hash" ]; then seed=$(printf '%d' "0x$hash"); else seed=1234567; fi
    fi
    python3 tests/check.py '{{rounds}}' "$seed"

check:
    just test
