import random
import time


def randomize_by_percentage(amount, randomize):
    """
    Randomize a value by a given percentage.

    :param amount: The original amount (float or int)
    :param randomize: The percentage to randomize (e.g., 0.1 for 10%)
    :return: A randomized value within the range [amount * (1 - randomize), amount * (1 + randomize)]
    """
    min_value = amount * (1 - randomize)
    max_value = amount * (1 + randomize)
    return random.uniform(min_value, max_value)


def random_delay_from_range(range_string):
    """
    Parses a range string and inserts a random delay within the specified range.

    :param range_string: A string representing the range in the format "min-max" (e.g., "1-20")
    """
    try:
        # Parse the range string
        min_seconds, max_seconds = map(float, range_string.split('-'))
        
        # Ensure valid range
        if min_seconds > max_seconds:
            raise ValueError("Minimum value cannot be greater than maximum value.")

        # Generate random delay
        delay = random.uniform(min_seconds, max_seconds)
        print(f"Delaying for {delay:.2f} seconds...")
        time.sleep(delay)
    except ValueError as e:
        print(f"Error parsing range string: {e}")


def parse_ranges(input_string):
    """
    Parse a string with single IDs and ranges, and return a list of integers.
    Example inputs: "2,3-10,14", "3-7", "1-2,3,4-7"
    """
    ids = []
    for part in input_string.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            ids.extend(range(start, end + 1))
        else:
            ids.append(int(part))
    return ids