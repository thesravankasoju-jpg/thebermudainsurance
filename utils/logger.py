"""
Logging configuration for the trading system
"""

import logging
import os
from config.settings import LOG_LEVEL, LOG_FILE, LOG_FORMAT

def setup_logger(name):
    """Setup logger with file and console handlers"""

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # Add handlers to logger
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
