# striptest
A small script to find optimal tempo settings for f/stop printing with a metronome in the darkroom
## Background

When working in the darkroom, I usually think in f/stops and use a metronome on 60 bpm to time my teststrips and other exposures.
I used to manually calculate each exposure with $t=b\cdot 2^{\text{stop}}$ and simply round the times to the nearest half second. If I for instance wanted a 5-step teststrip in $\frac{1}{3}$ stops, and I had an idea that 6 seconds would be a good target, I would perform following calculations:

| **Stops** | -2/3   | -1/3   | 0   |   +1/3|    +2/3   |
|-------:|--------|----------|----------|---------|-------------|
| **Formula** | $6\cdot2^{-2/3}$   | $6\cdot2^{-1/3}$   | $6\cdot2^{0}$   | $6\cdot2^{+1/3}$| $6\cdot2^{+2/3}$|
| **Time** (s)| 3.780   | 4.762  | 6   | 7.560 | 9.524| 
| **Rounded time** (s)| 4  | 5   | 6   | 7.5| 9.5 |

I however quickly became annoyed by the fact, that the rounding of seconds technically should be done in log-space. The rounding should be done with respect to which half second is closest to the target f/stop, so when naively rounding seconds, it's possible to round in the wrong direction.

This however is a relatively minor problem, but when thinking about it, it dawned on me, that I am using a metronome. Maybe counting half seconds isn't optimal for a given selection of exposure times. This is what motivated me to script this together.

|*% of 1/3 stop error*| 24.5%| 21.1%|0%|3.4%| 1.1%|
