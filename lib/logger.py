"""
Centralized logging system for the Time Lapse Camera firmware.

This module provides structured logging with different log levels
(DEBUG, INFO, WARN, ERROR) and optional file-based persistence.
"""

import time
import json
from lib.config import LOG_CONFIG, STATE_CONFIG


class Logger:
    """
    Centralized logger for the application.
    
    Features:
    - Log levels: DEBUG, INFO, WARN, ERROR
    - Configurable verbosity
    - Optional file logging
    - Structured output for easy parsing
    """
    
    # Log levels
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    
    LEVEL_NAMES = {
        0: 'DEBUG',
        1: 'INFO',
        2: 'WARN',
        3: 'ERROR',
    }
    
    def __init__(self, level='INFO', enable_file=False):
        """
        Initialize the logger.
        
        Args:
            level (str): Log level - 'DEBUG', 'INFO', 'WARN', 'ERROR'
            enable_file (bool): Whether to log to file
        """
        self.level_name = level.upper()
        self.level = self._parse_level(level)
        self.enable_file = enable_file and LOG_CONFIG.get('file_enabled', False)
        self.log_file = STATE_CONFIG.get('log_file', 'device.log')
        self.logs = []  # In-memory circular buffer
        self.max_logs = STATE_CONFIG.get('max_log_entries', 100)
    
    def _parse_level(self, level_name):
        """Parse log level name to number."""
        level_map = {
            'DEBUG': self.DEBUG,
            'INFO': self.INFO,
            'WARN': self.WARN,
            'ERROR': self.ERROR,
        }
        return level_map.get(level_name.upper(), self.INFO)
    
    def _timestamp(self):
        """Get current timestamp as milliseconds since boot."""
        try:
            return int(time.time() * 1000)
        except:
            return 0
    
    def _format_message(self, level, message):
        """Format log message with timestamp and level."""
        level_name = self.LEVEL_NAMES.get(level, 'UNKNOWN')
        timestamp = self._timestamp()
        return f"[{timestamp}] [{level_name}] {message}"
    
    def _write_to_memory(self, level, message):
        """Store log in memory buffer."""
        log_entry = {
            'timestamp': self._timestamp(),
            'level': self.LEVEL_NAMES.get(level, 'UNKNOWN'),
            'message': message,
        }
        self.logs.append(log_entry)
        
        # Maintain circular buffer
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
    
    def _write_to_file(self, formatted_message):
        """Append log message to file."""
        if not self.enable_file:
            return
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(formatted_message + '\n')
        except Exception as e:
            print(f"WARNING: Failed to write to log file: {e}")
    
    def _log(self, level, message):
        """Internal log method."""
        # Check if message should be logged
        if level < self.level:
            return
        
        # Format the message
        formatted_message = self._format_message(level, message)
        
        # Print to console
        print(formatted_message)
        
        # Store in memory
        self._write_to_memory(level, message)
        
        # Optionally write to file
        self._write_to_file(formatted_message)
    
    def debug(self, message):
        """Log debug message."""
        self._log(self.DEBUG, message)
    
    def info(self, message):
        """Log info message."""
        self._log(self.INFO, message)
    
    def warn(self, message):
        """Log warning message."""
        self._log(self.WARN, message)
    
    def warning(self, message):
        """Alias for warn()."""
        self.warn(message)
    
    def error(self, message):
        """Log error message."""
        self._log(self.ERROR, message)
    
    def set_level(self, level_name):
        """Change log level at runtime."""
        self.level = self._parse_level(level_name)
        self.level_name = level_name.upper()
        self.info(f"Log level changed to {self.level_name}")
    
    def get_logs(self, level_filter=None, count=None):
        """
        Retrieve stored log entries.
        
        Args:
            level_filter (str): Only return logs of this level ('DEBUG', 'INFO', etc)
            count (int): Return only the last N entries
        
        Returns:
            list: List of log entries (dicts with 'timestamp', 'level', 'message')
        """
        logs = self.logs
        
        # Filter by level if specified
        if level_filter:
            level_filter = level_filter.upper()
            logs = [log for log in logs if log['level'] == level_filter]
        
        # Return last N entries if specified
        if count and count > 0:
            return logs[-count:]
        
        return logs
    
    def get_logs_json(self, level_filter=None, count=None):
        """
        Get logs as JSON string (useful for transmission to server).
        
        Args:
            level_filter (str): Only return logs of this level
            count (int): Return only the last N entries
        
        Returns:
            str: JSON-encoded log entries
        """
        logs = self.get_logs(level_filter=level_filter, count=count)
        return json.dumps(logs)
    
    def clear_logs(self):
        """Clear in-memory log buffer."""
        self.logs = []
    
    def get_stats(self):
        """Get logging statistics."""
        error_count = len([l for l in self.logs if l['level'] == 'ERROR'])
        warn_count = len([l for l in self.logs if l['level'] == 'WARN'])
        
        return {
            'total_entries': len(self.logs),
            'max_entries': self.max_logs,
            'errors': error_count,
            'warnings': warn_count,
            'level': self.level_name,
        }


# Global logger instance
_logger = None


def init_logger(level='INFO', enable_file=False):
    """
    Initialize the global logger.
    
    Args:
        level (str): Log level ('DEBUG', 'INFO', 'WARN', 'ERROR')
        enable_file (bool): Enable file logging
    
    Returns:
        Logger: The initialized logger instance
    """
    global _logger
    _logger = Logger(level=level, enable_file=enable_file)
    return _logger


def get_logger():
    """
    Get the global logger instance.
    
    Returns:
        Logger: The logger instance
    
    Raises:
        RuntimeError: If logger not initialized
    """
    global _logger
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call init_logger() first.")
    return _logger


# Convenience functions that use global logger

def debug(message):
    """Log debug message."""
    get_logger().debug(message)


def info(message):
    """Log info message."""
    get_logger().info(message)


def warn(message):
    """Log warning message."""
    get_logger().warn(message)


def warning(message):
    """Log warning message (alias for warn)."""
    warn(message)


def error(message):
    """Log error message."""
    get_logger().error(message)
