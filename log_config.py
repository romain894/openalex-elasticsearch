import os
import logging

from rich.logging import RichHandler
from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv('LOG_LEVEL')

# FORMAT = "%(message)s"

# define a custom logging
log = logging.getLogger(__name__)
handler = logging.StreamHandler()
# handler.setFormatter(logging.Formatter(FORMAT))
log.addHandler(RichHandler())

match log_level:
    case "NOTSET":
        log.setLevel(logging.NOTSET)
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
        log.setLevel(logging.NOTSET)
        log.warning("The log_level must be NOTSET, DEBUG, INFO, WARNING, ERROR or CRITICAL")
        log.warning("Log level set to 'NOTSET'")
