#!/usr/bin/env python3
"""Checks striptest.py against the README, and index.html against striptest.py.

usage: tests/check.py [rounds] [seed]
    rounds  random settings to compare                [2000]
    seed    RNG seed, or "random" to roll one         [1234567]
            (the resolved seed is printed for replay)

striptest.py is the reference. The README's worked examples pin it down, and
the page has to agree with it on every setting, worked or random.
"""
import json
import pathlib
import random
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import striptest

STEPSIZES = [1, 2, 3, 4, 6, 12]
ROUND_BASES = [4, 5, 6, 8, 10, 12, 16, 20, 32]

# The tempo file from the README, which the page offers as its "Mechanical" scale
MECHANICAL = ["40:60 [2]", "60:72 [3]", "72:120 [4]", "120:144 [6]", "144:208 [8]"]

# The README's worked examples: settings, then the tempo and counts it prints
README = [
    (dict(base=10.0, stepsize=3, numsteps=7, baseplace=3, tempi=list(range(40, 209)),
          cumulative=False, divisions=0),
     181, ["5", "6+1/3", "8", "10", "12+2/3", "16", "20"]),
    (dict(base=6.0, stepsize=3, numsteps=5, baseplace=2, tempi=list(range(40, 209)),
          cumulative=False, divisions=0),
     190, ["4", "5", "6+1/3", "8", "10"]),
    (dict(base=8.0, stepsize=6, numsteps=5, baseplace=-1, tempi=list(range(30, 201)),
          cumulative=True, divisions=1),
     160, ["24", "3", "3", "4", "4"]),
]


def reference(settings):
    """What striptest.py computes for these settings, as plain numbers."""
    steps = (np.arange(settings["numsteps"]) - settings["baseplace"]) / settings["stepsize"]
    loss = lambda errors: np.sum(np.abs(errors) ** 2)
    winner = striptest.find_winner(settings["tempi"], steps, settings["base"], loss)
    beats = [int(n) for n in winner["lst"][:, 0]]
    divisions = settings["divisions"] or None
    every, _ = striptest.finalize_timing(winner, settings["cumulative"], divisions)
    return dict(
        tempo=int(winner["tempo"]),
        every=int(every),
        beats=beats,
        counts=[int(round(n * every)) for n in winner["lst"][:, 0]],
        printed=[striptest.format_counts(n, every).strip() for n in winner["lst"][:, 0]],
    )


def random_settings(rng):
    numsteps = rng.randint(1, 24)
    slowest = rng.randint(20, 150)
    mechanical = striptest.parse_tempo_file(MECHANICAL)
    return dict(
        base=rng.choice([round(rng.uniform(0.5, 120), 2), float(rng.choice(ROUND_BASES))]),
        stepsize=rng.choice(STEPSIZES),
        numsteps=numsteps,
        baseplace=rng.randint(-3, numsteps + 2),
        tempi=rng.choice([list(range(slowest, rng.randint(slowest, 300) + 1)), mechanical,
                          [t for t in mechanical if t >= slowest] or mechanical]),
        cumulative=rng.random() < 0.4,
        divisions=rng.choice([0, 0, 0, 1, 2, 3, 4]),
    )


def page(all_settings):
    """What index.html computes for the same settings."""
    command = ["node", str(ROOT / "tests" / "solve.js")]
    done = subprocess.run(command, input=json.dumps(all_settings), capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"node failed:\n{done.stderr}")
    return json.loads(done.stdout)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = sys.argv[2] if len(sys.argv) > 2 else "1234567"
    seed = int(time.time()) if seed == "random" else int(seed)
    print(f"tests/check.py: rounds={rounds}  seed={seed}")

    rng = random.Random(seed)
    all_settings = [settings for settings, _, _ in README]
    all_settings += [random_settings(rng) for _ in range(rounds)]
    started = time.time()
    expected = [reference(settings) for settings in all_settings]
    answer = page(all_settings)
    failures = []

    for (settings, tempo, printed), ours in zip(README, expected):
        if (ours["tempo"], ours["printed"]) != (tempo, printed):
            failures.append(f"README example no longer reproduced by striptest.py\n"
                            f"  settings {settings}\n  README   {tempo} {printed}\n"
                            f"  got      {ours['tempo']} {ours['printed']}")

    if answer["mechanical"] != striptest.parse_tempo_file(MECHANICAL):
        failures.append("the page's Mechanical scale differs from the README's tempo file")

    for settings, ours, theirs in zip(all_settings, expected, answer["results"]):
        ours = {key: ours[key] for key in theirs}
        if ours != theirs:
            failures.append(f"index.html disagrees with striptest.py\n  settings {settings}\n"
                            f"  python   {ours}\n  page     {theirs}")

    for failure in failures[:5]:
        print(f"\nFAIL {failure}")
    verdict = "FAIL" if failures else "PASS"
    print(f"\n{verdict} -- {len(README)} README examples and {rounds} random settings "
          f"in {time.time() - started:.2f}s ({len(failures)} failures)")
    if failures:
        print(f"replay with: just test {rounds} {seed}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
