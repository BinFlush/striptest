#!/usr/bin/env python3
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import fractions

def main():
    args = parse_arguments()

    tempi = populate_tempi(args.tmin, args.tmax, args.file)
    
    base, stepsize, numsteps, baseplace, divisions, cumulative, plot = (
        args.base, args.stepsize, args.numsteps, args.baseplace, args.divisions, args.cumulative, args.plot)

    # A purely integer list representing (fractional)stops to be evaluated and output 
    int_steps = np.arange(numsteps) - baseplace + 1

    # The same stops but as correct floats
    # (for actual calculation)
    steps = int_steps/stepsize

    # Only used in output, since all calculations are done in logspace
    target_seconds = base * 2 ** steps
    
    # Generic loss function. Not sure whether to use L1 or L2.
    # L1 seems to often produce more convenient BPMs, but L2 seems like
    # a better idea, since it would punish outliers.
    L_p_loss = lambda p: lambda errors: np.sum(np.abs(errors) ** p)

    # this is where the magic happens
    winner = find_winner(tempi, steps, base, L_p_loss(2)) 

    # This also mutates winner['lst']
    countdivisor, subdivision_notice = finalize_timing(winner, cumulative, divisions)

    # Output final results in a clear format
    print()
    print(f"TEMPO {winner['tempo']}")
    print(subdivision_notice)
    print()

    # Table header
    print(f"{'Count':>10} {'Stops':>10} {'Seconds':>10} {'Target Sec':>12} {'% of stepsize Error':>21}")

    # Format the output for each quad in the winner's list
    for (n, sec, _, steperror), int_step, targ_sec in zip(winner['lst'], int_steps, target_seconds):
        count_formatted = format_counts(n, countdivisor)  # Format the beat count properly
        stops_formatted = format_stops(int_step, stepsize)  # Use the int_steps value to format stops
        seconds_formatted = f"{sec:.3f}"  # Show actual seconds with 3 decimal places
        target_sec_formatted = f"{targ_sec:.3f}"  # Show target seconds with 3 decimal places
        error_formatted = f"{steperror*stepsize*100:.1f}%"  # Show error as a percentage with one decimal point
        
        # Print each row in the formatted table
        print(f"{count_formatted:>10} {stops_formatted:>10} {seconds_formatted:>10} {target_sec_formatted:>12} {error_formatted:>10}")
        
    if plot:
        plotter(steps, winner['lst'][:,2])


def plotter(steps, closest_stops):
# Create the figure and axes
    fig, ax = plt.subplots(figsize=(8, 1))

# Plot the number line
    ax.scatter(closest_stops, np.zeros_like(closest_stops), color='blue', marker='o', label='Real')
    ax.scatter(steps, np.zeros_like(steps), color='red', marker='x', label='Theoretical')

# Add vertical lines to emphasize each point
    ax.vlines(closest_stops, -0.1, 0.1, color='blue', alpha=0.5)
    ax.vlines(steps, -0.1, 0.1, color='red', alpha=0.5)

# Formatting the plot
    ax.set_yticks([])  # Hide y-axis
    ax.set_xlabel('Stops')
    ax.set_title('Real exposures vs theoretical exposures')
    ax.legend()
    ax.grid(True, axis='x', linestyle='--', alpha=0.6)

# Display the plot
    plt.show()



def parse_arguments():
    parser = argparse.ArgumentParser(description='Calculate the best tempo for darkroom timer.')
    parser.add_argument('-b', '--base', type=float, default=10.0, 
                        help='Base value for calculation (default: 10)')

    parser.add_argument('-s', '--stepsize', type=int, default=3, 
                        help='Inverse of the stepsize as an integer. 1 is one stop, '
                             '2 is 1/2 stop etc. (default: 3)')

    parser.add_argument('-n', '--numsteps', type=int, default=7, 
                        help='Number of steps (default: 7)')

    parser.add_argument('-p', '--baseplace', type=int, default=-1, 
                        help='Baseplace value. This is 1-indexed such that the first value is 1 '
                             '(default: is middle for uneven n, left to middle for even n)')

    parser.add_argument('-tmin', '--tmin', type=int, default=40, 
                        help='Minimum tempo (default: 40)')

    parser.add_argument('-tmax', '--tmax', type=int, default=208, 
                        help='Maximum tempo (default: 208)')

    parser.add_argument('-f', '--file', type=argparse.FileType('r'), 
                    help='Optional input file with specific tempo options. '
                          'The file should be a plaintext file with one tempo per line. '
                          'Each line can either be a single BPM number or a shorthand for a range. '
                          'For a single BPM, simply list the number (e.g., "60"). '
                          'For a range of BPMs, use the shorthand format "start:end [step]" '
                          '(e.g., "40:60 [2]" for a range from 40 to 60 in steps of 2). '
                          'Multiple ranges can be specified on separate lines. '
                          'If a file is provided, it overrides -tmax and -tmin options.')

    parser.add_argument('-c', '--cumulative', action='store_true', 
                        help='Use cumulative timing for the test strip such that each step builds upon the previous. '
                             'Useful for those who prefer to start counting from 0 on each step. (often easier with divisions set to 1; e.g. -d 1)')

    parser.add_argument('-d', '--divisions', type=int, default=None, 
                        help='Force a specific subdivision pattern for the beats. '
                             'If provided, this overrides the automatic subdivision '
                             'based on tempo (e.g., halves, triplets). Accepts an integer to set the divisor '
                             '(e.g., 2 for halves, 3 for triplets).')

    parser.add_argument('--plot', action='store_true', 
                        help='If specified, plot the achieved stops vs the theoretical stops'
                             'at the end. By default, this option is False.')

    args = parser.parse_args()

    args.baseplace = args.baseplace if args.baseplace > 0 else (args.numsteps + 1) // 2

    if args.stepsize <= 0:
        raise ValueError("Stepsize must be a positive integer.")
    if args.numsteps <= 0:
        raise ValueError("Number of steps must be a positive integer.")
    if args.base <= 0:
        raise ValueError("Base must be greater than zero.")
    if args.baseplace < 1 or args.numsteps < args.baseplace:
        raise ValueError("baseplace must be in [1,...,numsteps]")
    if args.tmin <= 0 or args.tmax <= 0:
        raise ValueError("All provided tempi must be greater than zero.")
    if args.divisions and args.divisions < 1:
        raise ValueError("Divisions must be a strictly positive integer.")

    return args


def parse_tempo_file(file):
    # Tempo file can have either ints on lines, or shorthand
    # range specifications in the form first:last [interval]
    # 40:60 [2] is for instance shorthand for 40, 42, 44, ..., 60
    tempi = []
    for line in file:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and "[" in line and "]" in line:
            try:
                range_part, interval_part = line.split("[")
                start, end = map(int, range_part.split(":"))
                step = int(interval_part.split("]")[0])
                
                tempi.extend(range(start, end + 1, step))
            except ValueError:
                print(f"Invalid format in line: {line}")
        else:
            # Parse individual BPM
            try:
                tempi.append(int(line))
            except ValueError:
                print(f"Invalid BPM format in line: {line}")

    return sorted(set(tempi))


def populate_tempi(tmin, tmax, file):
# Read tempi from file if provided, otherwise use the range
    if file:
        print(f"Using file '{file.name}' for tempi")
        tempi = parse_tempo_file(file)
    else:
        tempi = [i for i in range(tmin, tmax + 1)]

    if not tempi:
        raise ValueError("Tempo list is empty")
    return tempi



def find_divisors(n):
    # returns all divisors except the number itself and 1.
    potential_divisors = np.arange(2, int(np.sqrt(n)) + 1)
    divisors = potential_divisors[n % potential_divisors == 0]
    return set(divisors).union(n // divisors)

def closest_np_searchsorted(stops, steps):
    # Use binary search
    closest_indices = np.searchsorted(stops, steps)
    # ensure we will be within range
    high_indices = np.clip(closest_indices, 1, len(stops) - 1)
    low_indices = high_indices - 1
    low_diffs = np.abs(stops[low_indices] - steps)
    high_diffs = np.abs(stops[high_indices] - steps)
    closest_indices = np.where(low_diffs < high_diffs, low_indices, high_indices)
    return closest_indices


def get_optimal_beat_numbers(M, u, steps):
    """Find the closest beat numbers in log-space between Mlow and Mhigh."""
    Mlow = np.floor(M)
    Mhigh = np.ceil(M)
    e_low = (np.log2(Mlow) + u - steps)**2
    e_high = (np.log2(Mhigh) + u - steps)**2
    return np.where(e_low <= e_high, Mlow, Mhigh)


def find_winner(tempi, steps, base, loss_function):
    """
    Find the optimal tempo that minimizes the squared loss of step errors.

    Parameters:
    ----------
    tempi : list of int
        A list of tempo values (in bpm) to evaluate.
    steps : array-like
        A list or NumPy array of target steps (in stops).
    base : float
        The base value for the timing calculations.

    Returns:
    -------
    dict
        A dictionary with:
        - 'loss': Minimum squared loss.
        - 'tempo': The optimal tempo value in bpm.
        - 'lst': A NumPy array containing the optimal triplets (n, sec, stoperror).
    """

    excluded = set() # used for optimization
    tempi.reverse() # we will iterate from the highest to lowest
    winner = {'loss': np.inf, 'tempo': -1, 'lst': None}

    for tempo in tempi:
        if tempo in excluded:
            continue
        
        u = np.log2(60/(base*tempo))

        #steps is the "a(k)" array
        M = 2**(steps-u)
        # We can't simply round M. 
        # because we need to find the closest in logspace
        M_star = get_optimal_beat_numbers(M, u, steps)

        stops = np.log2(M_star) + u
        step_errors = stops - steps
        loss = loss_function(step_errors)

        if winner['loss'] >= loss:
            # We have a (better/lower) winner. We can build the rest of the vectors
            closest_sec = M_star * 60 / tempo
            closest_triplets = np.column_stack( (M_star, closest_sec, stops, step_errors) )

            winner['loss'] = loss
            winner['tempo'] = tempo
            winner['lst'] = closest_triplets
        else:
            # We have a loser. We can thus safely remove all lower tempi that divide this tempo
            # since their beats are a subset of these beats.
            excluded |= find_divisors(tempo)

    return winner


def convert_to_cumulative_timing(lst):
    cumulative_lst = np.zeros_like(lst)
    cumulative_lst[:, 1:] = lst[:, 1:]  # Copy over sec, stop, stoperror

    # The difference is simply each element minus the previous. Vectorize this
    cumulative_lst[1:, 0] = lst[1:, 0] - lst[:-1, 0]
    cumulative_lst[0, 0] = lst[0, 0]  # First count value is unchanged
    
    return cumulative_lst


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


def subdivisions(tempo, choice):
    # Put all logic for subdivisions in here.
    ## Decide subdivision
    if choice:
        subdivision = choice
    else:
        # intelligent choice
        subdivision = max(1,int(tempo/60))

    ## Make subdivision notice
    if subdivision == 1:
        subdivision_notice = 'Count every beat'
    else:
        suffix = ordinal_suffix(subdivision)
        subdivision_notice = f'Count every {subdivision}{suffix} beat'
    return subdivision, subdivision_notice


def finalize_timing(winner, cumulative, divisions):
    # Possibly convert to cumulative timing
    if cumulative:
        winner['lst'] = convert_to_cumulative_timing(winner['lst'])
    
    # Apply subdivisions based on tempo or divisions
    countdivisor, subdivision_notice = subdivisions(winner['tempo'], divisions)
    winner['lst'][:, 0] /= countdivisor

    return countdivisor, subdivision_notice


def format_stops(stopint, stepsize):
    if stopint == 0:
        return "0"
    sign = "+" if stopint > 0 else "-"
    abs_int = abs(stopint)
    if (abs_int/stepsize)%1 == 0:
        return f"{sign}{int(abs_int//stepsize)}"
    else:
        return f"{sign}{abs_int}/{stepsize}"


def format_counts(n, countdivisor):
    if n%1 == 0:
        return str(int(n))+'    '
    else:
        orig_n = int(round(n*countdivisor))
        return f'{orig_n//countdivisor}+{orig_n%countdivisor}/{countdivisor}'


if __name__ == "__main__":
    main()

