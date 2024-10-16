import os
import logging

from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv('LOG_LEVEL')

class CustomFormatter(logging.Formatter):

    blue = "\x1b[36;20m"
    green = "\x1b[32;20m"
    # grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# define a custom logging
log = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
log.addHandler(handler)
# log_oa.addHandler(logging.FileHandler(__name__ + ".log"))

match log_level:
    case 'DEBUG':
        log.setLevel(logging.DEBUG)
    case 'INFO':
        log.setLevel(logging.INFO)
    case 'WARNING':
        log.setLevel(logging.WARNING)
    case 'ERROR':
        log.setLevel(logging.ERROR)
    case 'CRITICAL':
        log.setLevel(logging.CRITICAL)
    case _:
        log.setLevel(logging.INFO)
        log.warning("The log_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        log.warning("Log level set to 'INFO'")

