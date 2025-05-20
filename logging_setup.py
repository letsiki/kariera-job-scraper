"""
logging_setup.py

basic setup for logging.Logger.
- Sets logger to debug level
- Creates a console logger displaying everything from INFO and above
- Creates a file logger holding only debug messages

Usage:
    Create a Logger instance and call logging setup on it.
"""

import logging
import sys


# Console handler setup
def setup_console_handler(logger: logging.Logger):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# File handler setup
def setup_file_handler(
    logger: logging.Logger, filename="debug.log", filemode="a"
):
    file_handler = logging.FileHandler(filename=filename, mode=filemode)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(message)s", datefmt="%H:%M"
    )
    file_handler.setFormatter(formatter)
    # Add filter to allow only DEBUG messages
    logger.addHandler(file_handler)


# Combined setup (for both console and file)
def setup_file_and_console_handler(
    logger, filename="default.log", filemode="a"
):
    setup_console_handler(logger)
    setup_file_handler(logger, filename, filemode)


# Main logging setup function
def logging_setup(
    logger, mode="c", filename="default.log", filemode="a"
):
    """
    ease of life function, setting up logging
    - default 'c' mode -> info level, console-only
    - 'f' mode writes to a file
    - 'fc' mode writes to both
    - file is at debug level - filename and write mode can be provided
    """
    if mode == "c":  # Console only
        setup_console_handler(logger)
    elif mode == "f":  # File only
        setup_file_handler(logger, filename, filemode)
    elif mode == "fc":  # File and Console
        setup_file_and_console_handler(logger, filename, filemode)
    else:
        raise ValueError(f"Unsupported logging mode: {mode}")

    logger.setLevel(logging.DEBUG)
