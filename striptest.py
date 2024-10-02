#!/usr/bin/env python3

import argparse
import numpy as np

parser = argparse.ArgumentParser(description='Calculate the best tempo for darkroom timer.')
parser.add_argument('-b', '--base', type=float, default=10.0, 
                    help='Base value for calculation (default: 10)')
parser.add_argument('-s', '--stepsize', type=int, default=3, 
                    help='Inverse of the stepsize as an integer. 1 is one stop, 2 is 1/2 stop etc. (default: 3)')
parser.add_argument('-n', '--numsteps', type=int, default=7, 
                    help='Number of steps (default: 7)')
parser.add_argument('-p', '--baseplace', type=int, default=-1, 
                    help='Baseplace value. This is 1-indexed such that the first value is 1 (default: is middle for uneven n, left to middle for even n)')
parser.add_argument('-tmin', '--tmin', type=int, default=40, 
                    help='Minimum tempo (default: 40)')
parser.add_argument('-tmax', '--tmax', type=int, default=208, 
                    help='Maximum tempo (default: 208)')
parser.add_argument('-f', '--file', type=argparse.FileType('r'), 
                    help='Optional input file with specific tempo options. Should be a plaintext file where each line is a bpm number, only separated by newline (overrides -tmax and -tmin)')
parser.add_argument('-l', '--local', action='store_true', 
                    help='Use local timing for the test strip such that each step is a full exposure. Useful for local teststrips, or for those who prefer not to start from 0 on each step, but rather to continue their count from the previous step (default is cumulative timing).')

args = parser.parse_args()

base = args.base
stepsize = args.stepsize
numsteps = args.numsteps
baseplace = args.baseplace if args.baseplace > 0 else (numsteps + 1) // 2
min_tempo = args.tmin
max_tempo = args.tmax

if stepsize <= 0:
    raise ValueError("Stepsize must be a positive integer.")
if numsteps <= 0:
    raise ValueError("Number of steps must be a positive integer.")
if base <= 0:
    raise ValueError("Base must be greater than zero.")
if baseplace < 1 or numsteps < baseplace:
    raise ValueError("baseplace must be in [1,...,numsteps]")
if min_tempo <= 0 or max_tempo <= 0:
    raise ValueError("All provided tempi must be greater than zero.")


# Read tempos from file if provided, otherwise use the range
if args.file:
    print(f"Using file '{args.file.name}' for tempos")
    tempos = [int(line.strip()) for line in args.file if line.strip().isdigit()]
    args.file.close()
    tempos = sorted(set(tempos))
else:
    tempos = [i for i in range(min_tempo, max_tempo + 1)]

if not tempos:
    raise ValueError("Tempo list is empty")

# A purely integer list of (fractional)stops to be evaluated and output 
int_steps = [i-baseplace+1 for i in range(numsteps)] 
# The same stops but as correct floats
steps = [i/stepsize for i in int_steps]


def beats_seconds_and_stops(tempo):
    """
    Input: A tempo (int) as bpm
    Output: a list of 3-tuples, where:
        first number is the beat number n (1-indexed since time 0 makes no sense), 
        second number is the beats placement in seconds, 
        third number is the beats deviance from base in stops.
    The list includes only (but all) beats in the relevant space.
    """
    # First calculate the bounds for relevant beat numbers.
    lower_n = int(np.floor(tempo*base*2**steps[0]/60))
    lower_n = max(lower_n, 1) # step 0 makes no sense. Also avoids log(0) issue
    upper_n = int(np.ceil(tempo*base*2**steps[-1]/60))

    n_list = [n for n in range(lower_n, upper_n+1)]
    seconds = [n*60/tempo for n in n_list]
    stops = [np.log2(s)-np.log2(base) for s in seconds]
    for n,s in enumerate(seconds):
        if s <= 0:
            print('lowsecond:',s)
            print('thestop:', stops[n])
    
    return list(zip(n_list, seconds, stops))

winner = {'loss':np.inf,'tempo': -1,'lst': []} # a triple |squared loss|tempo|quad_list|
# Now we iterate through each of the tempos and find the optimal one
for tempo in tempos:
    l = beats_seconds_and_stops(tempo)

    closest_quads = [] 
    # a quad for a tempo is: |n|sec|stop|stoperror|
    for targ_step in steps:
        # find the closest triple
        n, sec, stop = min(l, key=lambda x: abs(x[2]-targ_step))
        steperror = (stop - targ_step)
        closest_quads.append( (n, sec, stop, steperror) )

    # Compute squared loss
    squared_loss = sum([i[3]**2 for i in closest_quads])

    if winner['loss'] > squared_loss:
        winner['loss'] = squared_loss
        winner['tempo'] = tempo
        winner['lst'] = closest_quads

if not args.local:
    cumulative_lst = []
    previous_n = 0  # Initialize the previous exposure count

    for n, sec, stop, stoperror in winner['lst']:
        # Calculate the cumulative `n` as the difference from the previous step
        cumulative_n = n - previous_n
        cumulative_lst.append((cumulative_n, sec, stop, stoperror))
        
        # Update the previous exposure count
        previous_n = n
    
    # Update winner['lst'] with the cumulative counts
    winner['lst'] = cumulative_lst
    
def ordinal_suffix(n):
    """
    finds the correct suffix for positive integers, e.g. 2nd, 3rd etc.
    """
    if n%1 != 0 or n < 0:
        raise ValueError("n must be positive integer")
    # Special case for numbers ending in 11, 12, 13
    if 11 <= n % 100 <= 13:
        return "th"
    # General rule for other numbers
    last_digit = n % 10
    if last_digit == 1:
        return "st"
    elif last_digit == 2:
        return "nd"
    elif last_digit == 3:
        return "rd"
    else:
        return "th"


def subdivisions(tempo):
    # Put all logic for subdivisions in here.
    ## Decide subdivision
    subdivision = max(1,int(tempo/60))

    ## Make subdivision notice
    if subdivision == 1:
        subdivision_notice = 'Count every beat'
    else:
        suffix = ordinal_suffix(subdivision)
        subdivision_notice = f'Count every {subdivision}{suffix} beat'
    return subdivision, subdivision_notice

# Possibly make subdivisions based on tempo
countdivisor, subdivision_notice = subdivisions(winner['tempo'])
winner['lst'] = [(a/countdivisor,b,c,d) for a,b,c,d in winner['lst']]


def format_stops(stopint):
    if stopint == 0:
        return "0"
    sign = "+" if stopint > 0 else "-"
    abs_int = abs(stopint)
    if (abs_int/stepsize)%1 == 0:
        return f"{sign}{int(abs_int//stepsize)}"
    else:
        return f"{sign}{abs_int}/{stepsize}"

def format_counts(n):
    if n%1 == 0:
        return str(int(n))+'    '
    else:
        orig_n = int(round(n*countdivisor))
        return f'{orig_n//countdivisor}+{orig_n%countdivisor}/{countdivisor}'


target_seconds = [base * 2 ** step for step in steps]
# Output final results in a clear format
print()
print(f"TEMPO {winner['tempo']}")
print(subdivision_notice)
print()

# Output table header
print(f"{'Count':>10} {'Stops':>10} {'Seconds':>10} {'Target Sec':>12} {'% of stepsize Error':>21}")

# Format the output for each quad in the winner's list
for (n, sec, stop, steperror), int_step, targ_sec in zip(winner['lst'], int_steps, target_seconds):
    count_formatted = format_counts(n)  # Format the beat count properly
    stops_formatted = format_stops(int_step)  # Use the int_steps value to format stops
    seconds_formatted = f"{sec:.3f}"  # Show actual seconds with 3 decimal places
    target_sec_formatted = f"{targ_sec:.3f}"  # Show target seconds with 3 decimal places
    error_formatted = f"{steperror*stepsize*100:.1f}%"  # Show error as a percentage with one decimal point
    
    # Print each row in the formatted table
    print(f"{count_formatted:>10} {stops_formatted:>10} {seconds_formatted:>10} {target_sec_formatted:>12} {error_formatted:>10}")
