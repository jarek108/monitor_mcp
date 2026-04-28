import logging
import sys
from pathlib import Path

def setup_logging(log_file: str = "monitor.log"):
    """Configure logging to both file and terminal (with different levels)."""
    logger = logging.getLogger("monitor_mcp")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # File Handler (Full Detail)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_formatter)

    # Console Handler (High Level Info)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    
    # Also redirect standard library logs (like mss or httpx if they use logging)
    # to our file handler if needed, but let's keep it focused on our app for now.
    
    return logger

# Create a default logger instance
logger = setup_logging()
