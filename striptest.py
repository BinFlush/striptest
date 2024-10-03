#!/usr/bin/env python3
import argparse
import numpy as np

def main():
    args = parse_arguments()

    tempos = populate_tempos(args.tmin, args.tmax, args.file)
    
    base, stepsize, numsteps, baseplace, divisions, local = (
        args.base, args.stepsize, args.numsteps, args.baseplace, args.divisions, args.local)

    # A purely integer list representing (fractional)stops to be evaluated and output 
    int_steps = np.arange(numsteps) - baseplace + 1

    # The same stops but as correct floats
    # (for actual calculation)
    steps = int_steps/stepsize

    # Only used in output, since all calculations are done in logspace
    target_seconds = base * 2 ** steps

    # this is where the magic happens
    winner = find_winner(tempos, steps, base) 

    # This also mutates winner['lst']
    countdivisor, subdivision_notice = finalize_timing(winner, local, divisions)

    # Output final results in a clear format
    print()
    print(f"TEMPO {winner['tempo']}")
    print(subdivision_notice)
    print()

    # Table header
    print(f"{'Count':>10} {'Stops':>10} {'Seconds':>10} {'Target Sec':>12} {'% of stepsize Error':>21}")

    # Format the output for each quad in the winner's list
    for (n, sec, stop, steperror), int_step, targ_sec in zip(winner['lst'], int_steps, target_seconds):
        count_formatted = format_counts(n, countdivisor)  # Format the beat count properly
        stops_formatted = format_stops(int_step, stepsize)  # Use the int_steps value to format stops
        seconds_formatted = f"{sec:.3f}"  # Show actual seconds with 3 decimal places
        target_sec_formatted = f"{targ_sec:.3f}"  # Show target seconds with 3 decimal places
        error_formatted = f"{steperror*stepsize*100:.1f}%"  # Show error as a percentage with one decimal point
        
        # Print each row in the formatted table
        print(f"{count_formatted:>10} {stops_formatted:>10} {seconds_formatted:>10} {target_sec_formatted:>12} {error_formatted:>10}")








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
                             'Should be a plaintext file where each line is a bpm number, '
                             'only separated by newline (overrides -tmax and -tmin)')
    parser.add_argument('-l', '--local', action='store_true', 
                        help='Use local timing for the test strip such that each step is a full exposure. '
                             'Useful for local teststrips, or for those who prefer not to start from 0 on each step, '
                             'but rather to continue their count from the previous step (default is cumulative timing).')
    parser.add_argument('-d', '--divisions', type=int, default=None, 
                        help='Force a specific subdivision pattern for the beats. '
                             'If provided, this overrides the automatic subdivision '
                             'based on tempo (e.g., halves, triplets). Accepts an integer to set the divisor '
                             '(e.g., 2 for halves, 3 for triplets).')

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


def populate_tempos(tmin, tmax, file):
# Read tempos from file if provided, otherwise use the range
    if file:
        print(f"Using file '{file.name}' for tempos")
        tempos = [int(line.strip()) for line in file if line.strip().isdigit()]
        file.close()
        tempos = sorted(set(tempos))
    else:
        tempos = [i for i in range(tmin, tmax + 1)]

    if not tempos:
        raise ValueError("Tempo list is empty")
    return tempos


def finalize_timing(winner, local, divisions):
    # Possibly convert to local timing
    if not local:
        winner['lst'] = convert_to_local_timing(winner['lst'])
    
    # Apply subdivisions based on tempo or divisions
    countdivisor, subdivision_notice = subdivisions(winner['tempo'], divisions)
    winner['lst'] = apply_subdivisions(winner['lst'], countdivisor)

    return countdivisor, subdivision_notice


def beats_seconds_and_stops(tempo, steps, base):
    """
    Input: A tempo (int) as bpm
    Output: a numpy matrix for, where:
        first column is the beat number n (1-indexed since time 0 makes no sense), 
        second column is the beats placement in seconds, 
        third column is the beats deviance from base in stops.
    The list includes only (but all) beats in the relevant space.
    """
    # First calculate the bounds for relevant beat numbers.
    lower_n = int(np.floor(tempo*base*2**steps[0]/60))
    lower_n = max(lower_n, 1) # step 0 makes no sense. Also avoids log(0) issue
    upper_n = int(np.ceil(tempo*base*2**steps[-1]/60))

    n_list = np.arange(lower_n, upper_n + 1)
    beatlength = 60/tempo
    seconds = n_list * beatlength
    stops = np.log2(seconds / base)
    # results are a matrix of shape (num_beats, 3) 
    result = np.column_stack((n_list, seconds, stops))
    
    return result


def find_winner(tempos, steps, base):
    """
    Find the optimal tempo that minimizes the squared loss of step errors.

    Parameters:
    ----------
    tempos : list of int
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
        - 'lst': A NumPy array containing the optimal quads (n, sec, stop, stoperror).
    """
    winner = {'loss': np.inf, 'tempo': -1, 'lst': None}

    for tempo in tempos:
        # a matrix of shape (num_beats, 3)
        l = beats_seconds_and_stops(tempo, steps, base)

        n_values = l[:, 0]
        sec_values = l[:, 1]
        stops = l[:, 2]

        differences = np.abs(stops[:, np.newaxis] - steps)  # Shape (num_beats, num_steps)
        closest_indices = np.argmin(differences, axis=0)  # Shape (num_steps,)

        # Use these indices to get the closest triples for each step
        closest_n = n_values[closest_indices]  # Closest beat numbers
        closest_sec = sec_values[closest_indices]  # Closest seconds
        closest_stop = stops[closest_indices]  # Closest stops

        # Calculate step errors
        step_errors = closest_stop - steps  # Deviation from the target steps

        # Form the closest quads: |n|sec|stop|stoperror|
        closest_quads = np.column_stack((closest_n, closest_sec, closest_stop, step_errors))
        squared_loss = np.sum(step_errors ** 2)

        if winner['loss'] > squared_loss:
            winner['loss'] = squared_loss
            winner['tempo'] = tempo
            winner['lst'] = closest_quads

    return winner


def convert_to_local_timing(lst):
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


def apply_subdivisions(lst, countdivisor):
    lst[:, 0] /= countdivisor  # Divide the count column
    return lst



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
