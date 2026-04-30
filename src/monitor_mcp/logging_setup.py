import logging
import sys
from pathlib import Path

def setup_logging():
    """Configure logging to both file and terminal (with different levels)."""
    logger = logging.getLogger("monitor_mcp")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "monitor.log"

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # File Handler (Full Detail)
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_formatter)

    # Console Handler (High Level Info)
    # Use a stream wrapper to handle encoding issues on some terminals (e.g. Windows CMD)
    class SafeStreamHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                super().emit(record)
            except UnicodeEncodeError:
                if self.stream and hasattr(self.stream, 'encoding'):
                    msg = self.format(record)
                    self.stream.write(msg.encode('ascii', 'replace').decode('ascii') + self.terminator)
                    self.flush()

    ch = SafeStreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    
    # Also redirect standard library logs (like mss or httpx if they use logging)
    # to our file handler if needed, but let's keep it focused on our app for now.
    
    return logger

# Create a default logger instance
logger = setup_logging()
