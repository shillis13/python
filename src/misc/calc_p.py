import sys


# Calculate the probability of a sequence based on the given inputs.
def p_calc(n, p, memo=None):
    if memo is None:
        memo = {}
    if (n, p) in memo:
        return memo[(n, p)]
    # Debug statement to print the current state
    print(f"p_calc( {n}, {p})", flush=True)

    if n == 1:
        return 1 / p
    else:
        total_probability = 0.0
        for i in range(min(n, p), 0, -1):
            total_probability += p_calc(n - i, p) * (1 / p)
        return total_probability


# ------------------------------------------------------------------------------


# Read input from stdin and output computed probabilities.
def main():
    input_data = sys.stdin.read().strip().split("\n")
    c = int(input_data[0])

    results = []
    for i in range(1, c + 1):
        n, p = map(int, input_data[i].split())
        probability = p_calc(n, p)
        results.append(f"{probability:.9f}")

    for result in results:
        print(result)


# ------------------------------------------------------------------------------


# Run basic test cases for the probability calculator.
def test():
    # List of test cases in the format (n, p, expected_result)
    test_cases = [
        (1, 3, "0.333333333"),
        (2, 3, "0.444444444"),
        # Add more test cases as necessary
    ]

    for i, (n, p, expected) in enumerate(test_cases):
        print(f"[DEBUG] Testing case {i+1} with n={n}, p={p}", flush=True)
        result = f"{p_calc(n, p):.9f}"
        if result == expected:
            print(
                f"Test case {i+1} passed: p_calc({n}, {p}) = {result}, expected {expected}",
                flush=True,
            )
        else:
            print(
                f"Test case {i+1} failed: p_calc({n}, {p}) = {result}, expected {expected}",
                flush=True,
            )


# ------------------------------------------------------------------------------

if __name__ == "__main__":
    if "-test" in sys.argv:
        test()
    else:
        main()
# ------------------------------------------------------------------------------
