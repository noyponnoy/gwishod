import logging
import os
import sys
import traceback
from datetime import datetime, timezone


class MessageBot:
    def __init__(self, log_level: str, message: str):
        self.log_level = log_level
        self.message = message


def init_panic_handler():
    def exception_handler(exc_type, exc_value, exc_traceback):
        log_dir = "/var/log/gwvpn/"
        os.makedirs(log_dir, exist_ok=True)
        
        message = str(exc_value) if exc_value else "Unknown panic occurred!"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_output = f"Panic occurred: {message} ::::: {timestamp}\n"
        
        tb_str = "".join(traceback.format_tb(exc_traceback))
        if tb_str:
            log_output += f"{tb_str}\n"
        
        try:
            with open(os.path.join(log_dir, "panic.log"), "a") as f:
                f.write(log_output)
        except Exception:
            pass
        
        print(f"Panic occurred: {message} ::::: {timestamp}")
    
    sys.excepthook = exception_handler


class FileAndConsoleHandler(logging.Handler):
    def __init__(self, log_file_path: str):
        super().__init__()
        self.log_file_path = log_file_path
        log_dir = os.path.dirname(log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def emit(self, record):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{record.levelname} - {record.getMessage()} :::: {timestamp}"
        
        print(log_message)
        
        try:
            with open(self.log_file_path, "a") as f:
                f.write(log_message + "\n")
        except Exception:
            pass
        
        if record.levelno >= logging.ERROR:
            print(f"Critical error occurred: {record.getMessage()}")


def init_logger():
    log_dir = "/var/log/gwvpn/"
    os.makedirs(log_dir, exist_ok=True)
    
    handler = FileAndConsoleHandler(os.path.join(log_dir, "app.log"))
    handler.setLevel(logging.CRITICAL)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    root_logger.addHandler(handler)
