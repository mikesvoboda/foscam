#!/usr/bin/env python3
"""
Centralized logging configuration for Foscam services
"""
import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def setup_logger(service_name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Set up a logger for a specific service with file and console output.
    
    Args:
        service_name: Name of the service (e.g., 'webui', 'crawler', 'monitor')
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10MB per file, keep 10 files)
    log_file = LOGS_DIR / f"{service_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(simple_formatter)
    
    # Error file handler for critical issues
    error_file = LOGS_DIR / f"{service_name}_error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    
    # Log the initialization
    logger.info(f"Logger initialized for {service_name} with level {log_level}")
    logger.info(f"Log files: {log_file} and {error_file}")
    
    return logger

def setup_uvicorn_logging(service_name: str = "webui") -> dict:
    """
    Set up logging configuration for Uvicorn server.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Uvicorn logging configuration dictionary
    """
    
    # Ensure logs directory exists
    access_log = LOGS_DIR / f"{service_name}_access.log"
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s - %(client_addr)s - \"%(request_line)s\" %(status_code)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOGS_DIR / f"{service_name}_uvicorn.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "access": {
                "formatter": "access",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(access_log),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "console": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default", "console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access", "console"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
    }

def get_log_files() -> list:
    """Get list of all log files in the logs directory."""
    if not LOGS_DIR.exists():
        return []
    
    return [f for f in LOGS_DIR.iterdir() if f.is_file() and f.suffix == '.log']

def get_log_stats() -> dict:
    """Get statistics about log files."""
    log_files = get_log_files()
    
    stats = {
        "total_files": len(log_files),
        "total_size_mb": 0,
        "files": []
    }
    
    for log_file in log_files:
        size_mb = log_file.stat().st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(log_file.stat().st_mtime)
        
        stats["total_size_mb"] += size_mb
        stats["files"].append({
            "name": log_file.name,
            "size_mb": round(size_mb, 2),
            "modified": modified.isoformat()
        })
    
    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats

if __name__ == "__main__":
    # Test the logging setup
    print("Testing logging configuration...")
    
    # Test web UI logger
    webui_logger = setup_logger("webui", "INFO")
    webui_logger.info("Web UI logger test message")
    webui_logger.warning("Web UI warning test")
    webui_logger.error("Web UI error test")
    
    # Test crawler logger
    crawler_logger = setup_logger("crawler", "DEBUG")
    crawler_logger.debug("Crawler debug message")
    crawler_logger.info("Crawler info message")
    
    # Print log statistics
    stats = get_log_stats()
    print(f"\nLog Statistics:")
    print(f"Total files: {stats['total_files']}")
    print(f"Total size: {stats['total_size_mb']} MB")
    
    for file_info in stats['files']:
        print(f"  {file_info['name']}: {file_info['size_mb']} MB")
    
    print("\nLogging configuration test complete!") 