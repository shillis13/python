import time

try:
    from tqdm import tqdm

    tqdm_available = True
except ImportError:
    tqdm = None
    tqdm_available = False

progress_bar_enabled = True


"""
Enables progress bars.
"""


def enable_progress_bars():
    global progress_bar_enabled
    progress_bar_enabled = True


"""
Disables progress bars.
"""


def disable_progress_bars():
    global progress_bar_enabled
    progress_bar_enabled = False


"""
Decorator to add a progress bar to a function. This decorator is suitable for functions where the progress can be tracked externally, not within loops inside the function.

For functions containing loops, it is better to use the ProgressBarContext.

Args:
    func (function): The function to wrap with a progress bar.
 Returns:
    function: The wrapped function with a progress bar.
"""


def progress_bar(func):
    def wrapper(*args, **kwargs):
        if tqdm_available and progress_bar_enabled:
            total = kwargs.get("total", None)
            with tqdm(total=total, desc=func.__name__) as pbar:

                def update(*args, **kwargs):
                    result = func(*args, **kwargs)
                    pbar.update(1)
                    return result

                return update(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    return wrapper


"""
    Context manager for creating a progress bar.

Args:
    total (int): The total number of iterations for the progress bar.
    desc (str, optional): Description for the progress bar. Defaults to ''.
"""


class ProgressBarContext:
    def __init__(self, total, desc=""):
        self.total = total
        self.desc = desc
        self.pbar = (
            tqdm(total=total, desc=desc)
            if tqdm_available and progress_bar_enabled
            else None
        )

    def __enter__(self):
        return self.pbar

    def __exit__(self, exc_type, exc_value, traceback):
        if self.pbar:
            self.pbar.close()


"""
Example function to demonstrate the use of ProgressBarContext for loops.

Args:
    total (int): Total iterations for the progress bar.
"""


def example_function_with_progress(total):
    results = []
    with ProgressBarContext(total=total, desc="example_function_with_progress") as pbar:
        for i in range(total):
            time.sleep(0.1)
            results.append(i)
            print(".", end="")
            if pbar:
                pbar.update(1)
    return results


"""
Example function to demonstrate the progress bar decorator. This function does not contain a loop.

Args:
    total (int): Total iterations for the progress bar.
"""


@progress_bar
def example_function_with_progress_decorated(total):
    results = []
    for i in range(total):
        time.sleep(0.1)
        results.append(i)
        print(".", end="")
    return results


"""
Test function for example_function_with_progress.
"""


def test_example_function_with_progress():
    print("Testing example_function_with_progress...")
    example_function_with_progress(total=10)


"""
Test function for example_function_with_progress_decorated.
"""


def test_example_function_with_progress_decorated():
    print("Testing example_function_with_progress_decorated...")
    example_function_with_progress_decorated(total=1)


"""
Main function to run the test cases for progress bars.
"""


def main():
    if tqdm_available and progress_bar_enabled:
        test_example_function_with_progress()
        test_example_function_with_progress_decorated()
    else:
        print("tqdm is not available or progress bars are disabled.")


if __name__ == "__main__":
    main()
