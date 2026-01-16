from environment import (
    CAPTIVE_PORTAL_SSID,
)

# ============================================================================
# WIFI CONFIGURATION
# ============================================================================

WIFI_CONFIG = {
    'ssid': CAPTIVE_PORTAL_SSID,          # Captive portal SSID
    'password': '',                  # Captive portal password (empty = open)
    'authmode': 0,                   # 0=open, 1=WEP, 2=WPA-PSK, 3=WPA2-PSK, 4=WPA/WPA2-PSK
    'profiles_file': 'wifi.dat',    # File storing known WiFi networks
}

WIFI_TIMEOUT_CONFIG = {
    'scan_retry_delay_s': 3,        # Delay before retrying WiFi connection
    'captive_portal_timeout_ms': 5 * 60 * 1000,  # Portal stays open for 5 minutes
    'client_socket_timeout_s': 5.0, # HTTP socket timeout during portal
    'connect_check_delay_s': 3,     # Delay before checking connection again
}

# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================

CAMERA_CONFIG = {
    'camera_id': 0,                 # Camera ID (usually 0 for ESP32)
    'format': 'JPEG',               # Image format (JPEG recommended)
    'fb_location': 'PSRAM',         # Frame buffer location (PSRAM or DRAM)
    'contrast': 1,                  # Camera contrast (-2 to 2)
    'saturation': -1,               # Camera saturation (-2 to 2)
    'framesize': 'QXGA',            # Frame size (OV2640: QXGA is 2048x1536)
}

CAMERA_TIMING = {
    'stabilize_delay_s': 1.2,       # Time to wait for camera to stabilize after init
    'capture_timeout_s': 10,        # Max time to wait for capture
}

CAMERA_WHITE_BALANCE = {
    'sunny': 'WB_SUNNY',            # Sunny day white balance
    'cloudy': 'WB_CLOUDY',          # Cloudy day white balance
    'overcast': 'WB_CLOUDY',        # Overcast same as cloudy
    'default': 'WB_NONE',           # Default/auto white balance
}

# ============================================================================
# NETWORK CONFIGURATION (IoT Manager)
# ============================================================================

NETWORK_CONFIG = {
    'request_timeout_s': 10,        # HTTP request timeout
    'retry_delay_s': 2,             # Delay between retries
    'max_retries': 3,               # Maximum number of retries (not currently used)
}

# ============================================================================
# WAKEUP TIMING CONFIGURATION
# ============================================================================

WAKEUP_CONFIG = {
    'default_interval_ms': 24 * 60 * 60 * 1000,  # Default: 24 hours
    'min_interval_ms': 1 * 60 * 1000,            # Minimum: 1 minute
    'max_interval_ms': 48 * 60 * 60 * 1000,      # Maximum: 48 hours
    'test_mode_interval_ms': 30 * 1000,          # Test mode: 30 seconds
    'esp32_epoch_offset': 946684800,             # ESP32 epoch: Jan 1, 2000 (seconds from esp32 epoch)
}

# ============================================================================
# SLEEP CONFIGURATION (Power management)
# ============================================================================

SLEEP_CONFIG = {
    'wifi_failure_sleep_ms': 60 * 60 * 1000,    # Sleep 1 hour if WiFi fails
    'firmware_update_retry_sleep_ms': 10 * 60 * 1000,  # Sleep 10 min between update checks
}

# ============================================================================
# DEVICE STATE & LOGGING
# ============================================================================

STATE_CONFIG = {
    'state_file': 'device_state.json',  # File to store device state
    'log_file': 'device.log',           # Optional: device log file
    'max_log_entries': 100,             # Max entries in circular log
}

LOG_CONFIG = {
    'level': 'INFO',                    # Log level: DEBUG, INFO, WARN, ERROR
    'format': 'simple',                 # Log format: simple or detailed
    'file_enabled': False,              # Enable file logging (uses more storage)
}

# ============================================================================
# WEATHER CONDITIONS (validated set)
# ============================================================================

VALID_WEATHER_CONDITIONS = [
    'sunny',
    'cloudy',
    'overcast',
]
DEFAULT_WEATHER_CONDITION = 'overcast' # It's Scotland

# ============================================================================
# FIRMWARE & VERSIONING
# ============================================================================

FIRMWARE_CONFIG = {
    'current_version': '0.0.0',     # Current firmware version
    'ota_check_enabled': True,      # Check for OTA updates
}

# ============================================================================
# TEST MODE CONFIGURATION
# ============================================================================

TEST_MODE_CONFIG = {
    'always_upload_test_image': True,   # Upload image even in test mode
    'sleep_time_override_ms': 30 * 1000,  # Override sleep time to 30 seconds
}

# ============================================================================
# STARTUP MODE CONFIGURATION
# ============================================================================

# Set TEST_MODE=True to force test mode on device startup
TEST_MODE = False

# ============================================================================
# CONFIGURATION BUILDER
# ============================================================================

def get_config():
    """
    Get the complete configuration dictionary.
    
    This function merges all configuration sections into a single
    dictionary for easy access throughout the application.
    
    Returns:
        dict: Complete configuration
    """
    return {
        'wifi': WIFI_CONFIG,
        'wifi_timeout': WIFI_TIMEOUT_CONFIG,
        'camera': CAMERA_CONFIG,
        'camera_timing': CAMERA_TIMING,
        'camera_white_balance': CAMERA_WHITE_BALANCE,
        'network': NETWORK_CONFIG,
        'wakeup': WAKEUP_CONFIG,
        'sleep': SLEEP_CONFIG,
        'state': STATE_CONFIG,
        'log': LOG_CONFIG,
        'firmware': FIRMWARE_CONFIG,
        'test_mode': TEST_MODE_CONFIG,
        'test_mode_enabled': TEST_MODE,
    }


def validate_config():
    """
    Validate the configuration for consistency and correctness.
    
    Checks:
    - Wakeup intervals are in correct order (min < default < max)
    - Weather conditions are in valid set
    - Timeouts are positive
    
    Returns:
        bool: True if config is valid
    
    Raises:
        ValueError: If config is invalid
    """
    wakeup = WAKEUP_CONFIG
    
    # Validate wakeup intervals
    if wakeup['min_interval_ms'] >= wakeup['default_interval_ms']:
        raise ValueError("min_interval must be less than default_interval")
    
    if wakeup['default_interval_ms'] > wakeup['max_interval_ms']:
        raise ValueError("default_interval must be less than max_interval")
    
    # Validate weather condition
    if DEFAULT_WEATHER_CONDITION not in VALID_WEATHER_CONDITIONS:
        raise ValueError(f"Default weather condition '{DEFAULT_WEATHER_CONDITION}' not in valid set")
    
    # Validate timeouts
    if WIFI_TIMEOUT_CONFIG['scan_retry_delay_s'] <= 0:
        raise ValueError("WiFi scan retry delay must be positive")
    
    if NETWORK_CONFIG['request_timeout_s'] <= 0:
        raise ValueError("Network request timeout must be positive")
    
    return True


# ============================================================================
# INITIALIZATION
# ============================================================================

# Validate config on module load
try:
    validate_config()
except ValueError as e:
    print(f"ERROR: Invalid configuration: {e}")
    raise
