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

# The tempo file from the README: a realistic metronome scale, full of gaps
MECHANICAL = ["40:60 [2]", "60:72 [3]", "72:120 [4]", "120:144 [6]", "144:208 [8]"]

# Ilford's ISO range (R, ISO 6846) for Multigrade IV RC Deluxe at each filter, from the table in
# "MULTIGRADE RC PAPERS Technical Information" (Oct 2020). The page's row tones must have these.
ISO_RANGE = {"00": 1.80, "0": 1.60, "1": 1.30, "2": 1.10, "3": 0.90, "4": 0.60, "5": 0.40}

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
    """What striptest.py computes for these settings, as plain numbers.

    The page lets people skip tempi their metronome lacks and shows which better
    ones it passed over. striptest.py has no such option, so the reference is its
    own ranking: take the winner, and while that one is skipped, drop it and ask again.
    """
    steps = (np.arange(settings["numsteps"]) - settings["baseplace"]) / settings["stepsize"]
    loss = lambda errors: np.sum(np.abs(errors) ** 2)
    skipped = set(settings.get("skipped", []))
    tempi, passed, winner = list(settings["tempi"]), [], None
    while tempi:
        winner = striptest.find_winner(tempi, steps, settings["base"], loss)
        if winner["tempo"] not in skipped:
            break
        passed.append(int(winner["tempo"]))
        tempi.remove(winner["tempo"])
    if not tempi:
        return dict(passed=passed, direct=None)

    # Passing over skipped winners one by one has to end where solving without them starts
    allowed = [tempo for tempo in settings["tempi"] if tempo not in skipped]
    direct = int(striptest.find_winner(allowed, steps, settings["base"], loss)["tempo"])

    beats = [int(n) for n in winner["lst"][:, 0]]
    divisions = settings["divisions"] or None
    every, _ = striptest.finalize_timing(winner, settings["cumulative"], divisions)
    return dict(
        tempo=int(winner["tempo"]),
        every=int(every),
        beats=beats,
        counts=[int(round(n * every)) for n in winner["lst"][:, 0]],
        printed=[striptest.format_counts(n, every).strip() for n in winner["lst"][:, 0]],
        passed=passed,
        direct=direct,
    )


def random_tempi(rng):
    """A range or the mechanical scale, sometimes with gaps, the way a tempo file can have."""
    slowest = rng.randint(20, 150)
    mechanical = striptest.parse_tempo_file(MECHANICAL)
    tempi = rng.choice([list(range(slowest, rng.randint(slowest, 300) + 1)), mechanical,
                        [t for t in mechanical if t >= slowest] or mechanical])
    if rng.random() < 0.4:
        kept = rng.sample(tempi, rng.randint(1, len(tempi)))
        tempi = sorted(kept)
    return tempi


def random_skipped(rng, tempi):
    """Usually nothing or a handful, now and then most or all of the list."""
    most = rng.choice([0, 0, 6, 6, 6, len(tempi)])
    return sorted(rng.sample(tempi, rng.randint(0, min(most, len(tempi)))))


def random_settings(rng):
    numsteps = rng.randint(1, 24)
    tempi = random_tempi(rng)
    return dict(
        base=rng.choice([round(rng.uniform(0.5, 120), 2), float(rng.choice(ROUND_BASES))]),
        stepsize=rng.choice(STEPSIZES),
        numsteps=numsteps,
        baseplace=rng.randint(-3, numsteps + 2),
        tempi=tempi,
        skipped=random_skipped(rng, tempi),
        cumulative=rng.random() < 0.4,
        divisions=rng.choice([0, 0, 0, 1, 2, 3, 4]),
    )


def density(grey):
    """Reflection density of a grey given as an sRGB value from 0 to 1."""
    return -np.log10(((grey + 0.055) / 1.055) ** 2.4)


def tone_failures(filter_name, tones):
    """The page's row tones at one filter, given as (thirds of a stop, grey), against Ilford.

    ISO 6846 measures a paper's contrast as its log exposure range R: from the exposure that
    gives 0.04 above the paper's minimum density to the one that gives 90% of its maximum
    above the minimum.
    """
    thirds = sorted(third for third, _ in tones)
    densities = [density(grey) for _, grey in sorted(tones)]
    lightest, darkest = densities[0], densities[-1]
    low, high = lightest + 0.04, lightest + 0.9 * (darkest - lightest)
    rising = np.array(densities) + np.arange(len(densities)) * 1e-9
    stops = (np.interp(high, rising, thirds) - np.interp(low, rising, thirds)) / 3
    iso_range, published = stops * np.log10(2), ISO_RANGE[filter_name]
    base = densities[thirds.index(0)]
    checks = [
        ("the base row is 18% middle grey", abs(10 ** -base - 0.18) < 0.0005),
        ("more exposure never prints lighter",
         all(a <= b + 1e-12 for a, b in zip(densities, densities[1:]))),
        ("far under is paper white, far over is the paper's maximum black",
         abs(lightest - 0.03) < 1e-9 and 2.0 < darkest < 2.05),
        (f"the ISO range is Ilford's {published:.2f}, got {iso_range:.2f}",
         abs(iso_range - published) <= 0.02),
    ]
    return [f"filter {filter_name}: {name}" for name, holds in checks if not holds]


def zone_failures(zones):
    """The zones the page cuts each strip into.

    Zone V is 18% grey by definition, Zone 0 the paper's full black and Zone X its white. One
    zone gives way to the next where the print is halfway between their densities, so the
    exposure the page finds for each border must really give that density on the curve.
    """
    printed = zones["printed"]
    checks = [
        ("there are eleven, Zone 0 to Zone X", len(printed) == 11),
        ("Zone V is 18% middle grey", abs(10 ** -printed[5] - 0.18) < 0.0005),
        ("Zone 0 is full black and Zone X paper white",
         2.0 < printed[0] < 2.05 and abs(printed[10] - 0.03) < 1e-9),
        ("every zone prints lighter than the one below it",
         all(a > b for a, b in zip(printed, printed[1:]))),
    ]
    # zoneOf() numbers a density: whole numbers on the zones, clamped beyond black and white
    wanted = [0.0] + [float(zone) for zone in range(11)] + [10.0]
    checks.append(("a density gets the number of its zone, 0 beyond black and 10 beyond white",
                   all(abs(number - want) < 1e-9
                       for (_, number), want in zip(zones["numbered"], wanted))))
    for filter_name, found in zones["borders"].items():
        halfway = [(a + b) / 2 for a, b in zip(printed, printed[1:])]
        checks += [
            (f"filter {filter_name}: each border is where the print is halfway between two zones",
             all(abs(density - wanted) < 1e-9 for (_, density), wanted in zip(found, halfway))),
            (f"filter {filter_name}: borders come at ever less exposure towards Zone X",
             all(a > b for (a, _), (b, _) in zip(found, found[1:]))),
        ]
    # A row is drawn as zones between edges, and probed as a density at one place. Both must
    # tell the same story: the zone a place lies in is the zone nearest to its probed density.
    nearest = lambda density: min(range(11), key=lambda zone: abs(printed[zone] - density))
    halfway = [(a + b) / 2 for a, b in zip(printed, printed[1:])]
    disagree = []
    for row in zones["rows"]:
        evenly = abs(row["exposed"]) < 1e-12
        if evenly and any(abs(edge - 100 * k / 11) > 1e-9 for k, edge in enumerate(row["edges"])):
            disagree.append(f"filter {row['filter']}: the reference row is not an even scale")
        for share, density in row["probed"]:
            on_a_border = (any(abs(edge - 100 * share) < 1e-6 for edge in row["edges"])
                           or any(abs(density - half) < 1e-9 for half in halfway))
            drawn = max(zone for zone in range(11) if row["edges"][zone] <= 100 * share + 1e-9)
            if not on_a_border and drawn != nearest(density):
                disagree.append(f"filter {row['filter']}, {row['exposed']:+.3f} stops, {share:.4f} "
                                f"along: drawn as zone {drawn}, probed as {nearest(density)}")
    checks.append((f"the zones drawn and the tone probed agree at every place: {disagree[:3]}",
                   not disagree))
    return [f"zones: {name}" for name, holds in checks if not holds]


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

    if sorted(answer["tones"]) != sorted(ISO_RANGE):
        failures.append("the page does not offer exactly Ilford's seven filters")
    for filter_name, tones in answer["tones"].items():
        failures += tone_failures(filter_name, tones)
    failures += zone_failures(answer["zones"])

    for settings, ours, theirs in zip(all_settings, expected, answer["results"]):
        if ours["direct"] not in (None, ours.get("tempo")):
            failures.append(f"passing over skipped tempi ends at {ours['tempo']}, but solving "
                            f"without them gives {ours['direct']}\n  settings {settings}")
        ours = {key: ours.get(key) for key in theirs}
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
