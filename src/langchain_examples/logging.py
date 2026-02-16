import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FILE = Path("data/app.log")


def setup_logging(level: int = logging.DEBUG, log_file: Path | None = None) -> None:
    """Configure logging to file only."""
    log_path = log_file or DEFAULT_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    app_logger = logging.getLogger("langchain_examples")
    app_logger.setLevel(level)
    app_logger.addHandler(handler)

    # Third-party loggers stay quiet
    logging.root.setLevel(logging.WARNING)
    logging.root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
