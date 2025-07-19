import logging
from contextlib import contextmanager
from functools import wraps


def setup_logging(level=logging.INFO):
    """
    Set up the basic configuration for the logging system.
    Args:
        level (int): The logging level, e.g., logging.INFO, logging.DEBUG.
    Example:
        setup_logging(logging.DEBUG)
    """
    logging.basicConfig(level=level,
                        format='%(asctime)s : %(filename)s : %(funcName)s : %(lineno)d : %(levelname)s : %(message)s')

    '''
    # if we wanted to use a custom logger, this is how we'd do it

    # Create logger
    logger = logging.getLogger('theLogger')
    logger.setLevel(level)

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(level)

    # Create formatter including file name, function name, and line number
    formatter = logging.Formatter('%(asctime)s : %(filename)s : %(funcName)s : %(lineno)d : %(levelname)s : %(message)s')

    # Add formatter to ch (console handler)
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)
    return logger
    '''



@contextmanager
def log_block(name):
    """
    Context manager for logging the entry and exit of a code block.
    Args:
        name (str): The name of the block for logging purposes.
    Example:
        with log_block("process_data"):
            # code block
    """
    logging.info(f"Entering block: {name}", stacklevel=4)
    try:
        yield
    finally:
        logging.info(f"Exiting block: {name}", stacklevel=4)


def log_function(func):
    """
    Decorator for logging function calls with their arguments and return values.
    Args:
        func (function): The function to be wrapped for logging.
    Returns:
        function: The wrapped function.
    Example:
        @log_function
        def add(a, b):
            return a + b
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.debug(f"Function {func.__name__} called with args: {args} and kwargs: {kwargs}", stacklevel=4)
        result = func(*args, **kwargs)
        logging.debug(f"Function {func.__name__} returned {result}", stacklevel=4)
        return result
    return wrapper


# Decorator to handle non-string inputs in logging functions
def handle_non_string_inputs(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Convert all args to strings
        str_args = [str(arg) for arg in args]
        # Convert all key-value pairs in kwargs to strings
        str_kwargs = {k: str(v) for k, v in kwargs.items()}
        return func(*str_args, **str_kwargs)
    return wrapper


@handle_non_string_inputs
def log_info(message, stacklevel=4):
    """
    Log an informational message.
    Args:
        message (str): The message to log.
    Example:
        log_info("Data processing complete.")
    """
    logging.info(message, stacklevel=stacklevel)


@handle_non_string_inputs
def log_error(message, stacklevel=4):
    """
    Log an error message.

    Args:
        message (str): The message to log.

    Example:
        log_error("Data processing failed.")
    """
    logging.error(message, stacklevel=stacklevel)


@handle_non_string_inputs
def log_debug(message, stacklevel=4):
    """
    Log an informational message.

    Args:
        message (str): The message to log.

    Example:
        log_debug("Data processing complete.")
    """
    logging.debug(message, stacklevel=stacklevel)


@handle_non_string_inputs
def log_out(message):
    """
    Output a message without any additional formatting.

    Args:
        message (str): The message to output.
    """
    print(message)


