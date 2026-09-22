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

# Ilford's ISO range (R, ISO 6846) for each paper at each filter, from the table in
# "MULTIGRADE RC PAPERS Technical Information" (Oct 2020). The page's row tones must have these.
ISO_RANGE = {
    "Multigrade RC Deluxe":
        {"00": 1.60, "0": 1.30, "1": 1.10, "2": 0.90, "3": 0.70, "4": 0.60, "5": 0.50},
    "Multigrade FB Classic":
        {"00": 1.70, "0": 1.40, "1": 1.10, "2": 0.95, "3": 0.80, "4": 0.60, "5": 0.50},
    "Multigrade IV RC Deluxe":
        {"00": 1.80, "0": 1.60, "1": 1.30, "2": 1.10, "3": 0.90, "4": 0.60, "5": 0.40},
}

# Their ISO speed (P) at each filter, from the next table in that sheet. Two filters are compared
# by these: the speed is measured where the print is 0.6 above paper white.
ISO_SPEED = {
    "Multigrade RC Deluxe":
        {"00": 240, "0": 240, "1": 240, "2": 240, "3": 240, "4": 220, "5": 220},
    "Multigrade FB Classic":
        {"00": 230, "0": 230, "1": 230, "2": 230, "3": 230, "4": 210, "5": 210},
    "Multigrade IV RC Deluxe":
        {"00": 200, "0": 200, "1": 200, "2": 200, "3": 200, "4": 100, "5": 100},
}

# Paper white, and the span maximum black lies in, as the sheet's plots draw them
WHITE = {"Multigrade RC Deluxe": 0.05, "Multigrade FB Classic": 0.02, "Multigrade IV RC Deluxe": 0.03}
BLACK = {"Multigrade RC Deluxe": (2.05, 2.10), "Multigrade FB Classic": (2.05, 2.10),
         "Multigrade IV RC Deluxe": (2.00, 2.05)}

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
    seconds = np.array(beats) * 60 / winner["tempo"]
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


def tone_failures(paper, filter_name, tones):
    """The page's row tones on one paper at one filter, as (thirds of a stop, grey), against Ilford.

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
    iso_range, published = stops * np.log10(2), ISO_RANGE[paper][filter_name]
    blackest, deepest = BLACK[paper]
    base = densities[thirds.index(0)]
    checks = [
        ("the base row is 18% middle grey", abs(10 ** -base - 0.18) < 0.0005),
        ("more exposure never prints lighter",
         all(a <= b + 1e-12 for a, b in zip(densities, densities[1:]))),
        ("far under is paper white, far over is the paper's maximum black",
         abs(lightest - WHITE[paper]) < 1e-9 and blackest < darkest < deepest),
        (f"the ISO range is Ilford's {published:.2f}, got {iso_range:.2f}",
         abs(iso_range - published) <= 0.02),
    ]
    return [f"{paper}, filter {filter_name}: {name}" for name, holds in checks if not holds]


def zone_failures(paper, zones):
    """The zones the page cuts each strip into.

    Zone V is 18% grey by definition, Zone 0 the paper's full black and Zone X its white. One
    zone gives way to the next where the print is halfway between their densities, so the
    exposure the page finds for each border must really give that density on the curve.
    """
    printed = zones["printed"]
    blackest, deepest = BLACK[paper]
    halfway = [(a + b) / 2 for a, b in zip(printed, printed[1:])]
    numbers = [0.0] + [float(zone) for zone in range(11)] + [10.0]
    checks = [
        ("there are eleven, Zone 0 to Zone X", len(printed) == 11),
        ("Zone V is 18% middle grey", abs(10 ** -printed[5] - 0.18) < 0.0005),
        ("Zone 0 is full black and Zone X paper white",
         blackest < printed[0] < deepest and abs(printed[10] - WHITE[paper]) < 1e-9),
        ("every zone prints lighter than the one below it",
         all(a > b for a, b in zip(printed, printed[1:]))),
        ("a density gets the number of its zone, 0 beyond black and 10 beyond white",
         all(abs(got - number) < 1e-9 for (_, got), number in zip(zones["numbered"], numbers))),
    ]
    for filter_name, found in zones["borders"].items():
        checks += [
            (f"filter {filter_name}: each border is where the print is halfway between two zones",
             all(abs(reached - half) < 1e-9 for (_, reached), half in zip(found, halfway))),
            (f"filter {filter_name}: borders come at ever less exposure towards Zone X",
             all(a > b for (a, _), (b, _) in zip(found, found[1:]))),
        ]
    return [f"{paper}, zones: {name}" for name, holds in checks if not holds]


def strip_failures(paper, strips, printed):
    """A row is drawn as zones between edges, and probed as a density at one place.

    Both must tell the same story: the zone a place lies in is the zone nearest to the density
    probed there, whether the row is at the reference row's filter or at another. And a row
    exposed like the reference, at its filter, is an even scale.
    """
    halfway = [(a + b) / 2 for a, b in zip(printed, printed[1:])]
    nearest = lambda reached: min(range(11), key=lambda zone: abs(printed[zone] - reached))
    failures = []
    for strip in strips:
        name = (f"{paper}, filter {strip['other']} against {strip['filter']}, "
                f"{strip['exposed']:+.3f} stops")
        even = [100 * zone / 11 for zone in range(12)]
        is_reference = strip["other"] == strip["filter"] and not strip["exposed"]
        if is_reference and any(abs(a - b) > 1e-9 for a, b in zip(strip["edges"], even)):
            failures.append(f"strips: {name}: the reference row is not an even scale")
        for share, reached in strip["probed"]:
            on_a_border = (any(abs(edge - 100 * share) < 1e-6 for edge in strip["edges"])
                           or any(abs(reached - half) < 1e-9 for half in halfway))
            drawn = max(zone for zone in range(11) if strip["edges"][zone] <= 100 * share + 1e-9)
            if not on_a_border and drawn != nearest(reached):
                failures.append(f"strips: {name}, {share:.4f} along: drawn as zone {drawn}, "
                                f"probed as zone {nearest(reached)}")
    return failures


def speed_failures(paper, speeds):
    """Two filters are lined up by their ISO speeds.

    The speed says how much light the tone 0.6 above paper white takes. So where the reference
    row has that tone, a row at another filter has it too when it gets as many stops more as
    its filter is slower, and with half the speed that is one stop.
    """
    failures = []
    for pair in speeds:
        slower = np.log2(ISO_SPEED[paper][pair["filter"]] / ISO_SPEED[paper][pair["other"]])
        if not any(np.isclose(exposed, slower) for exposed, _ in pair["probed"]):
            failures.append(f"{paper}, speeds: filter {pair['other']} against {pair['filter']} is "
                            f"not tried {slower:+.3f} stops apart, as Ilford's speeds put them")
        for exposed, reached in pair["probed"]:
            if np.isclose(exposed, slower) != (abs(reached - WHITE[paper] - 0.6) < 1e-9):
                failures.append(f"{paper}, speeds: filter {pair['other']} against "
                                f"{pair['filter']}, given "
                                f"{exposed:+.3f} stops, prints the tone speed is measured at as "
                                f"{reached:.3f}")
    return failures


def timer_failures(settings, rows):
    """The same strip timed with a timer: each patch gets its f-stop seconds, to a tenth.

    `add` is what the strip is given once the patch before has been covered, so the additions
    must run up to each patch's seconds. The error is what the rounding costs, in stops.
    """
    steps = np.arange(settings["numsteps"]) - settings["baseplace"]
    exact = settings["base"] * 2.0 ** (steps / settings["stepsize"])
    seconds, error, add = (np.array([row[key] for row in rows], dtype=float)
                           for key in ("seconds", "error", "add"))
    checks = [
        ("one row for each step", [row["step"] for row in rows] == list(steps)),
        ("seconds are whole tenths, and at least one",
         np.allclose(seconds * 10, np.round(seconds * 10), atol=1e-6) and seconds.min() > 0.09),
        ("seconds are the f-stop times, to the nearest tenth",
         all(abs(got - want) <= 0.05 + 1e-9 for got, want in zip(seconds, exact) if want > 0.05)),
        ("the error is what rounding the seconds costs, in stops",
         np.allclose(error, np.log2(seconds / exact), atol=1e-9)),
        ("what is added runs up to each patch's seconds",
         np.allclose(np.cumsum(add), seconds, atol=1e-9)),
    ]
    return [f"timer: {name}\n  settings {settings}" for name, holds in checks if not holds]


def sound_failures(settings, rows, marks, sound):
    """A run's marks, in seconds from the moment it starts.

    The count-in comes first, then the lamp goes on, then a mark at each patch's seconds, the
    last of which is the lamp going off again.
    """
    count_in = sound["COUNT_IN"]
    want = [count_in] + [count_in + row["seconds"] for row in rows]
    checks = [
        ("one mark for the lamp, then one for every patch", len(marks) == len(rows) + 1),
        ("the lamp goes on when the count-in ends", abs(marks[0] - count_in) < 1e-9),
        ("every mark falls at its patch's seconds after the lamp",
         len(marks) == len(want) and all(abs(a - b) < 1e-9 for a, b in zip(marks, want))),
        ("the marks never run backwards", all(a <= b for a, b in zip(marks, marks[1:]))),
    ]
    return [f"sound: {name}\n  settings {settings}" for name, holds in checks if not holds]


def wait_failures(wait, rows):
    """A count-in of any length holds the run back by exactly that, and changes nothing else."""
    seconds = [row["seconds"] for row in rows]
    want = [wait["countIn"]] + [wait["countIn"] + second for second in seconds]
    holds = (len(wait["marks"]) == len(want)
             and all(abs(a - b) < 1e-9 for a, b in zip(wait["marks"], want)))
    return [] if holds else [f"sound: a count-in of {wait['countIn']} s does not hold the run "
                             f"back by exactly that: {wait['marks'][:3]}"]


def climb_failures(climbs, sound):
    """The glide through one gap, as the frequencies the page hands to the browser.

    It leaves the fundamental where the gap begins and lands exactly an octave above it on the
    mark, by the curve the sound is defined by: with a share t of the gap still to run it stands
    1 - t ** BEND of the way up the octave. The browser draws straight lines between the points,
    so they have to lie close enough together for that to be the same curve, and closest of all
    at the mark, where it is steepest.
    """
    f0, bend, steps = sound["FUNDAMENTAL"], sound["BEND"], sound["CLIMBS"]
    failures = []
    for gap in climbs:
        span = gap["mark"] - gap["from"]
        times = [time for time, _ in gap["points"]]
        hertz = [rate for _, rate in gap["points"]]
        left = [max(0.0, (gap["mark"] - time) / span) for time in times]
        curve = [f0 * 2.0 ** (1 - share ** bend) for share in left]
        checks = [
            (f"it is {steps + 1} points", len(gap["points"]) == steps + 1),
            ("it leaves the fundamental where the gap begins",
             abs(times[0] - gap["from"]) < 1e-9 and hertz[0] == f0),
            ("it lands an octave up, on the mark",
             abs(times[-1] - gap["mark"]) < 1e-9 and hertz[-1] == 2 * f0),
            ("it never turns back in time", all(a <= b for a, b in zip(times, times[1:]))),
            ("it climbs the whole way", all(a < b for a, b in zip(hertz, hertz[1:]))),
            ("every point is on the curve",
             all(abs(a - b) < 1e-6 for a, b in zip(hertz, curve))),
            ("no two points are more than a step of the octave apart",
             max(b / a for a, b in zip(hertz, hertz[1:])) <= 2.0 ** (1 / steps) + 1e-12),
            ("the points crowd into the mark", times[-1] - times[-2] < span / 200),
        ]
        failures += [f"glide from {gap['from']} to {gap['mark']}: {name}"
                     for name, holds in checks if not holds]
    return failures


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

    if sorted(answer["papers"]) != sorted(ISO_RANGE):
        failures.append("the page does not offer exactly the papers the suite knows")
    for paper, told in answer["papers"].items():
        if sorted(told["tones"]) != sorted(ISO_RANGE[paper]):
            failures.append(f"{paper}: not exactly the filters its own sheet publishes")
        # A paper is offered a run of the filter list, never a gap in the middle of it: the
        # slider on the page is one range, so a missing filter can only be at an end
        canonical = ["00", "0", "1", "2", "3", "4", "5"]
        offered = [f for f in canonical if f in told["tones"]]
        if offered != canonical[canonical.index(offered[0]):canonical.index(offered[-1]) + 1]:
            failures.append(f"{paper}: the filters it offers have a gap in the middle, "
                            f"which the page's slider cannot show: {offered}")
        for filter_name, tones in told["tones"].items():
            failures += tone_failures(paper, filter_name, tones)
        failures += zone_failures(paper, told["zones"])
        failures += strip_failures(paper, told["strips"], told["zones"]["printed"])
        failures += speed_failures(paper, told["speeds"])

    if answer["added"] != ["5.0", "+1.3", "0.1", "+12.0"]:
        failures.append(f"timer: what is added is written as {answer['added']}")
    for settings, rows in zip(all_settings, answer["timers"]):
        failures += timer_failures(settings, rows)
    for settings, rows, marks in zip(all_settings, answer["timers"], answer["runs"]):
        failures += sound_failures(settings, rows, marks, answer["sound"])
    for wait in answer["waits"]:
        failures += wait_failures(wait, answer["timers"][0])
    failures += climb_failures(answer["climbs"], answer["sound"])

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
