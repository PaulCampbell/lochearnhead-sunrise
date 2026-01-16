"""
Input validation utilities for the Time Lapse Camera firmware.

This module provides functions to validate configuration, parameters,
and data received from external sources.
"""

import re
from lib.config import (
    VALID_WEATHER_CONDITIONS,
    CAMERA_CONFIG,
    WAKEUP_CONFIG,
)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


# ============================================================================
# URL VALIDATION
# ============================================================================

def validate_url(url):
    """
    Validate a URL string.
    
    Args:
        url (str): URL to validate
    
    Returns:
        str: The validated URL
    
    Raises:
        ValidationError: If URL is invalid
    """
    if not isinstance(url, str):
        raise ValidationError(f"URL must be string, got {type(url)}")
    
    if not url.strip():
        raise ValidationError("URL cannot be empty")
    
    if not (url.startswith('http://') or url.startswith('https://')):
        raise ValidationError("URL must start with http:// or https://")
    
    # Basic URL pattern check
    if len(url) < 10:
        raise ValidationError("URL is too short")
    
    return url.strip()


# ============================================================================
# DEVICE ID VALIDATION
# ============================================================================

def validate_device_id(device_id):
    """
    Validate a device ID.
    
    Args:
        device_id (str): Device ID to validate
    
    Returns:
        str: The validated device ID
    
    Raises:
        ValidationError: If device ID is invalid
    """
    if not isinstance(device_id, str):
        raise ValidationError(f"Device ID must be string, got {type(device_id)}")
    
    if not device_id.strip():
        raise ValidationError("Device ID cannot be empty")
    
    device_id = device_id.strip()
    
    # Allow alphanumeric, dash, underscore
    if not re.match(r'^[a-zA-Z0-9_-]+$', device_id):
        raise ValidationError(f"Device ID contains invalid characters: {device_id}")
    
    if len(device_id) > 64:
        raise ValidationError("Device ID is too long (max 64 characters)")
    
    return device_id


# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

def validate_password(password):
    """
    Validate a password.
    
    Args:
        password (str): Password to validate
    
    Returns:
        str: The validated password
    
    Raises:
        ValidationError: If password is invalid
    """
    if not isinstance(password, str):
        raise ValidationError(f"Password must be string, got {type(password)}")
    
    # Password can be empty (for open networks)
    password = password.strip()
    
    if len(password) > 128:
        raise ValidationError("Password is too long (max 128 characters)")
    
    return password


# ============================================================================
# WEATHER CONDITION VALIDATION
# ============================================================================

def validate_weather_condition(condition):
    """
    Validate a weather condition.
    
    Args:
        condition (str): Weather condition to validate
    
    Returns:
        str: The validated condition (lowercased)
    
    Raises:
        ValidationError: If condition is invalid
    """
    if not isinstance(condition, str):
        raise ValidationError(f"Weather condition must be string, got {type(condition)}")
    
    condition = condition.strip().lower()
    
    if condition not in VALID_WEATHER_CONDITIONS:
        valid_str = ', '.join(VALID_WEATHER_CONDITIONS)
        raise ValidationError(
            f"Weather condition '{condition}' is invalid. "
            f"Must be one of: {valid_str}"
        )
    
    return condition


# ============================================================================
# CAMERA SETTINGS VALIDATION
# ============================================================================

def validate_framesize(framesize):
    """
    Validate camera framesize setting.
    
    Args:
        framesize (str): Frame size name (e.g., 'QXGA', 'VGA')
    
    Returns:
        str: The validated framesize
    
    Raises:
        ValidationError: If framesize is invalid
    """
    valid_sizes = [
        'QXGA',    # 2048x1536
        'UXGA',    # 1600x1200
        'SXGA',    # 1280x1024
        'XGA',     # 1024x768
        'SVGA',    # 800x600
        'VGA',     # 640x480
        'CIF',     # 352x288
        'QVGA',    # 320x240
        'HQVGA',   # 240x176
    ]
    
    if not isinstance(framesize, str):
        raise ValidationError(f"Framesize must be string, got {type(framesize)}")
    
    framesize = framesize.strip().upper()
    
    if framesize not in valid_sizes:
        valid_str = ', '.join(valid_sizes)
        raise ValidationError(
            f"Framesize '{framesize}' is invalid. "
            f"Must be one of: {valid_str}"
        )
    
    return framesize


def validate_contrast(contrast):
    """
    Validate camera contrast setting.
    
    Args:
        contrast (int): Contrast value (-2 to 2)
    
    Returns:
        int: The validated contrast
    
    Raises:
        ValidationError: If contrast is invalid
    """
    if not isinstance(contrast, int):
        raise ValidationError(f"Contrast must be integer, got {type(contrast)}")
    
    if contrast < -2 or contrast > 2:
        raise ValidationError(f"Contrast must be between -2 and 2, got {contrast}")
    
    return contrast


def validate_saturation(saturation):
    """
    Validate camera saturation setting.
    
    Args:
        saturation (int): Saturation value (-2 to 2)
    
    Returns:
        int: The validated saturation
    
    Raises:
        ValidationError: If saturation is invalid
    """
    if not isinstance(saturation, int):
        raise ValidationError(f"Saturation must be integer, got {type(saturation)}")
    
    if saturation < -2 or saturation > 2:
        raise ValidationError(f"Saturation must be between -2 and 2, got {saturation}")
    
    return saturation


# ============================================================================
# WAKEUP TIME VALIDATION
# ============================================================================

def validate_wakeup_time_ms(wakeup_time_ms):
    """
    Validate a wakeup time in milliseconds.
    
    Args:
        wakeup_time_ms (int): Wakeup time in milliseconds
    
    Returns:
        int: The validated wakeup time
    
    Raises:
        ValidationError: If wakeup time is invalid
    """
    if not isinstance(wakeup_time_ms, int):
        raise ValidationError(
            f"Wakeup time must be integer, got {type(wakeup_time_ms)}"
        )
    
    min_ms = WAKEUP_CONFIG['min_interval_ms']
    max_ms = WAKEUP_CONFIG['max_interval_ms']
    
    if wakeup_time_ms < min_ms:
        raise ValidationError(
            f"Wakeup time {wakeup_time_ms}ms is too short "
            f"(minimum: {min_ms}ms = 1 minute)"
        )
    
    if wakeup_time_ms > max_ms:
        raise ValidationError(
            f"Wakeup time {wakeup_time_ms}ms is too long "
            f"(maximum: {max_ms}ms = 48 hours)"
        )
    
    return wakeup_time_ms


# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================

def validate_server_config(config):
    """
    Validate configuration received from server.
    
    Args:
        config (dict): Configuration dictionary from server
    
    Returns:
        dict: Cleaned and validated configuration
    
    Raises:
        ValidationError: If config is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError(f"Config must be dict, got {type(config)}")
    
    validated = {}
    
    # Validate testMode (optional boolean)
    if 'testMode' in config:
        test_mode = config['testMode']
        if not isinstance(test_mode, bool):
            raise ValidationError(f"testMode must be boolean, got {type(test_mode)}")
        validated['testMode'] = test_mode
    
    # Validate weatherCondition (optional string)
    if 'weatherCondition' in config:
        try:
            validated['weatherCondition'] = validate_weather_condition(
                config['weatherCondition']
            )
        except ValidationError as e:
            raise ValidationError(f"Invalid weatherCondition: {e}")
    
    # Validate nextWakeupTimeMs (optional integer)
    if 'nextWakeupTimeMs' in config:
        wakeup_ms = config['nextWakeupTimeMs']
        if not isinstance(wakeup_ms, int):
            raise ValidationError(
                f"nextWakeupTimeMs must be integer, got {type(wakeup_ms)}"
            )
        if wakeup_ms <= 0:
            raise ValidationError(f"nextWakeupTimeMs must be positive, got {wakeup_ms}")
        validated['nextWakeupTimeMs'] = wakeup_ms
    
    # Preserve any other unknown fields for forward compatibility
    for key, value in config.items():
        if key not in validated:
            validated[key] = value
    
    return validated


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_get_bool(obj, key, default=False):
    """
    Safely get a boolean value from a dict.
    
    Args:
        obj (dict): Dictionary to get from
        key (str): Key to look up
        default (bool): Default value if key not present
    
    Returns:
        bool: The value, or default if not found
    """
    if not isinstance(obj, dict):
        return default
    
    value = obj.get(key, default)
    
    if isinstance(value, bool):
        return value
    
    return default


def safe_get_int(obj, key, default=0):
    """
    Safely get an integer value from a dict.
    
    Args:
        obj (dict): Dictionary to get from
        key (str): Key to look up
        default (int): Default value if key not present
    
    Returns:
        int: The value, or default if not found
    """
    if not isinstance(obj, dict):
        return default
    
    value = obj.get(key, default)
    
    if isinstance(value, int):
        return value
    
    return default


def safe_get_string(obj, key, default=''):
    """
    Safely get a string value from a dict.
    
    Args:
        obj (dict): Dictionary to get from
        key (str): Key to look up
        default (str): Default value if key not present
    
    Returns:
        str: The value, or default if not found
    """
    if not isinstance(obj, dict):
        return default
    
    value = obj.get(key, default)
    
    if isinstance(value, str):
        return value
    
    return default
