# striptest
A small script to find optimal tempo settings for f/stop printing with a metronome in the darkroom
## Background

When working in the darkroom, I usually think in f/stops and use a metronome on 60 bpm to time my teststrips and other exposures.
I used to manually calculate each exposure with $t=b\cdot 2^{\text{stop}}$ and simply round the times to the nearest half second. If I for instance wanted a 5-step teststrip in $\frac{1}{3}$ stops, and I had an idea that 6 seconds would be a good target, I would perform following calculations (I added the percentwise error of 1/3 stop appropriately calculated in logspace, to illustrate the inaccuracy):

| **Stops** | -2/3   | -1/3   | 0   |   +1/3|    +2/3   |
|-------:|--------|----------|----------|---------|-------------|
| **Formula** | $6\cdot2^{-2/3}$   | $6\cdot2^{-1/3}$   | $6\cdot2^{0}$   | $6\cdot2^{+1/3}$| $6\cdot2^{+2/3}$|
| **True time** (s)| 3.780   | 4.762  | 6   | 7.560 | 9.524| 
| **Rounded time** (s)| 4  | 5   | 6   | 7.5| 9.5 |
|**% of 1/3 stop error**| 24.5%| 21.1%|0%|3.4%| 1.1%|

This method is usually accurate enough, and in the above example, the base (6s) was specifically chosen for its bad fit with counting half seconds.
I quickly became annoyed by the fact, that the rounding of seconds technically should be done in log-space. The rounding should be done with respect to which half second is closest to the target f/stop, so when naively rounding seconds, it's possible to round in the wrong direction.

This however is a relatively minor problem, but when thinking about it, it dawned on me, that I am using a metronome. Maybe counting half seconds isn't optimal for a given selection of exposure times (such as 1/3 stops with a base of 6 seconds). This is what motivated me to make this script.

## Function
If you have a base in mind, maybe you feel that a 6-second exposure would be fitting, but you would like to do a striptest in 1/3 stop increments, with two more exposures to the left, and 2 more exposures to the right, simply run the script with the flags `striptest -b 6 -n 5`
The scripts defaults to 1/3 stop increments, and by default it puts the base exposure in the middle.
```
[user@machine directory]$ python striptest.py -b 6 -n 5

TEMPO 190
Subdivide into triplets

     Count      Stops    Seconds   Target Sec   % of stepsize Error
     4           -2/3      3.789        3.780       1.1%
     5           -1/3      4.737        4.762      -2.3%
     6+1/3          0      6.000        6.000       0.0%
     8           +1/3      7.579        7.560       1.1%
    10           +2/3      9.474        9.524      -2.3%
```
As we see, the script found the optimal tempo to be 190bpm. 
Given these instructions, simply set your metronome to 190, and make it mark every third beat (hence the message "Subdivide into triplets"). Then the exposures should be timed by counting the marked beats in accordance to the "Count" column. As we see by the error column, the error in this case is much smaller then when counting half seconds.
