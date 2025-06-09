import logging


def configure_logging():
    logging.basicConfig(
        filemode='w',
        filename='log.txt',
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )