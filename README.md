# striptest
A small script to find optimal tempo settings for f/stop printing with a metronome in the darkroom.
## Overview
**striptest** is a Python script designed for darkroom enthusiasts who want to optimize their exposure settings for f/stop printing using a metronome. This tool finds the best tempo settings reducing exposure inaccuracies.

## Background

### Traditional f/stop Printing
When working in the darkroom, exposures are best timed in f/stops, and these exposures are often timed using very expensive special f/stop timers. However, using a metronome set to 60 bpm (simply counting seconds) is also possible. Exposure calculations are done using $t = b \cdot 2^{\text{stop}}$

Where $t$ is the exposure time we are looking for, $b$ is a base time that we are calculating from, and **stop** is how many f/stops we want to adjust away from our base time.

However, even when rounding exposure times to the nearest half-second, it can lead to inaccuracies. For example, if performing a 5-step test strip in 1/3 stops based on a 6-second base exposure:

| **Stops** | -2/3   | -1/3   | 0   |   +1/3|    +2/3   |
|-------:|--------|----------|----------|---------|-------------|
| **Formula** | $6\cdot2^{-2/3}$   | $6\cdot2^{-1/3}$   | $6\cdot2^{0}$   | $6\cdot2^{+1/3}$| $6\cdot2^{+2/3}$|
| **True time** (s)| 3.780   | 4.762  | 6   | 7.560 | 9.524| 
| **Rounded time** (s)| 4  | 5   | 6   | 7.5| 9.5 |
|**% of 1/3 stop error**| 24.5%| 21.1%|0%|3.4%| 1.1%|

This rounding issue, combined with the use of a metronome, motivated the creation of this script.

## Function

### Basic Example
To find the optimal tempo for a 6-second base exposure over 5 steps:
```bash
$ python striptest.py -b 6 -n 5
TEMPO 190
Count every third beat

     Count      Stops    Seconds   Target Sec   % of stepsize Error
     4           -2/3      3.789        3.780       1.1%
     5           -1/3      4.737        4.762      -2.3%
     6+1/3          0      6.000        6.000       0.0%
     8           +1/3      7.579        7.560       1.1%
    10           +2/3      9.474        9.524      -2.3%
```
As seen, the script finds an optimal tempo (e.g., 190 bpm) to minimize exposure inaccuracies, with much smaller errors compared to the above example counting half seconds.

In this case, set your metronome to 190 bpm, optionally make the metronome accent every third beat, and simply start exposing by counting the accented beats. The metronome will in this case be effectively beating triplets, so a count of 6+1/3 illustrates you should stop on the first triplet after the 6th accented beat.

As always in darkroom printing, you should start your exposure at the count of zero.

## Usage

To use the script, you can adjust several parameters to control how the tempo is calculated. Below are the options available:

- `-b`, `--base`: Base exposure time in seconds (float). Default is `10`.
- `-s`, `--stepsize`: Inverse of the stepsize as an integer (int). `1` is one stop, `2` is 1/2 stop, etc. Default is `3`.
- `-n`, `--numsteps`: Number of steps (int) for the strip test. Default is `7`.
- `-p`, `--baseplace`: The position of the base value in the test strip (1-indexed). The default is the middle for an uneven `n`, and left to middle for an even `n`.
- `-tmin`, `--tmin`: Minimum tempo (int) in bpm to consider. Default is `40`.
- `-tmax`, `--tmax`: Maximum tempo (int) in bpm to consider. Default is `208`.
- `-f`, `--file`: Optional input file with specific tempo options (plaintext file with each line as a bpm number). Overrides `-tmax` and `-tmin`.

### Example

To run a strip test with a base exposure of 6 seconds, 5 steps, and default options:
```bash
python striptest.py -b 6 -n 5
```

To specify a different stepsize (e.g., 1/2 stop increments):
```bash
python striptest.py -s 2
```

To use a custom tempo range between 60 and 180 bpm:
```bash
python striptest.py -tmin 60 -tmax 180
```

To use a custom file with tempo options:
```bash
python striptest.py -b 6 -n 5 -f tempos.txt
```

Custom tempo files are useful for metronomes with skips in their possible bpm options. Some metronomes for instance only include every other bpm above a certain value, and even every third bpm above a higher value. Tempo files should have every tempo as an integer number, separated with newline. If you only want to use tempos 60, 120, and 180, the file contents should simply be:
```
60
120
180
```

### Extended example
Let's say our metronome has a range from 30-300 bpm, and that we previously obtained a good exposure at 8 seconds, but the contrast needed modification such that we know that the 8-second exposure might be slightly underexposed at the new contrast setting. We can do the following:
We make a 5-step striptest where we place the base of 8 seconds at the first step, and do increments of 1/6 stops from there. It will result in the following output:
```bash
$ python striptest.py -b 8 -n 5 -p 1 -s 6 -tmin 30 -tmax 300

TEMPO 255
Count every fourth beat

     Count      Stops    Seconds   Target Sec   % of stepsize Error
     8+2/4          0      8.000        8.000       0.0%
     9+2/4       +1/6      8.941        8.980      -3.7%
    10+3/4       +2/6     10.118       10.079       3.3%
    12           +3/6     11.294       11.314      -1.5%
    13+2/4       +4/6     12.706       12.699       0.5%
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/BinFlush/striptest.git
   ```

2. Install dependencies (numpy):
   ```bash
   pip install numpy
   ```

## Contributing
Contributions are welcome! Please open an issue or submit a pull request.

