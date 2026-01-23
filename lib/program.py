from lib.iot_manager_client import IotManagerClient
from lib.wifimgr import WifiManager
from lib.config import (
    WIFI_CONFIG,
    SLEEP_CONFIG,
    CAMERA_CONFIG,
    CAMERA_TIMING,
    CAMERA_WHITE_BALANCE,
    WAKEUP_CONFIG,
    DEFAULT_WEATHER_CONDITION,
)
from lib.logger import get_logger
from lib.validation import (
    validate_url,
    validate_device_id,
    validate_password,
    validate_weather_condition,
    validate_server_config,
    ValidationError,
)
import time
import ntptime
import camera
import machine

class Program:
    def __init__(self, iot_manager_base_url, device_id, device_password):
        """
        Initialize Program with validation of all parameters.
        
        Args:
            iot_manager_base_url (str): Base URL of IoT Manager server
            device_id (str): Device identifier
            device_password (str): Device password for authentication
        
        Raises:
            ValidationError: If any parameter is invalid
        """
        self.logger = get_logger()
        
        # Validate all parameters
        try:
            self.iot_manager_base_url = validate_url(iot_manager_base_url)
            self.device_id = validate_device_id(device_id)
            self.device_password = validate_password(device_password)
        except ValidationError as e:
            self.logger.error(f"Invalid parameter: {e}")
            raise
        
        self.client = IotManagerClient(base_url=self.iot_manager_base_url)
        
        # Initialize WiFi manager with config
        wifi_config = WIFI_CONFIG
        self.wifi_manager = WifiManager(
            ssid=wifi_config['ssid'],
            password=wifi_config['password'],
            authmode=wifi_config['authmode']
        )
        
        self.logger.info(f"Program initialized with device ID: {self.device_id}")

    def connect_wifi(self, enter_captive_portal_if_needed):
        """Connect to WiFi with graceful failure handling."""
        self.logger.info("Connecting to WiFi...")
        wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=enter_captive_portal_if_needed)
        if wlan is None:
            self.logger.error("Could not initialize network connection")
            self.logger.info(f"Entering deep sleep for {SLEEP_CONFIG['wifi_failure_sleep_ms'] / 1000 / 60:.0f} minutes")
            # Sleep then retry automatically
            machine.deepsleep(SLEEP_CONFIG['wifi_failure_sleep_ms'])

        self.logger.info(f"Network connected: {wlan.ifconfig()}")
        try:
            ntptime.settime()
            self.logger.info(f"System time synchronized: {time.time()}")
        except Exception as e:
            self.logger.warn(f"Failed to synchronize time: {e}")
        
        return wlan
        
    def take_photo(self, weather_condition, test_post=False):
        """
        Capture and upload a photo.
        
        Args:
            weather_condition (str): 'sunny', 'overcast', or 'cloudy'
            test_post (bool): If True, marks upload as test post
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate weather condition
            try:
                weather_condition = validate_weather_condition(weather_condition)
            except ValidationError:
                self.logger.warn(f"Invalid weather condition '{weather_condition}', using default")
                weather_condition = DEFAULT_WEATHER_CONDITION
            
            self.logger.info("Taking photo...")
            camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM)
            time.sleep(CAMERA_TIMING['stabilize_delay_s'])  # Wait for camera to stabilize
            
            # Apply camera settings from config
            camera.contrast(CAMERA_CONFIG['contrast'])
            camera.saturation(CAMERA_CONFIG['saturation'])
            camera.framesize(camera.FRAME_QXGA)
            
            # Set white balance based on weather
            wb_setting = CAMERA_WHITE_BALANCE.get(weather_condition, CAMERA_WHITE_BALANCE['default'])
            if weather_condition == 'sunny':
                camera.whitebalance(camera.WB_SUNNY)
            elif weather_condition in ('cloudy', 'overcast'):
                camera.whitebalance(camera.WB_CLOUDY)
            else:
                camera.whitebalance(camera.WB_NONE)
            
            # Capture frame
            frame = camera.capture()
            if frame is None or len(frame) == 0:
                self.logger.error("Camera capture returned empty frame")
                return False
            
            self.logger.info(f"Captured frame: {len(frame)} bytes")
            
            # Upload
            try:
                response = self.client.upload_image(
                    image_data=frame,
                    test_post=test_post,
                )
                self.logger.info("Image uploaded successfully")
                return True
            except Exception as e:
                self.logger.error(f"Image upload failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            self.logger.error(f"Photo capture failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            try:
                camera.deinit()
            except Exception as e:
                self.logger.warn(f"Camera deinit failed: {e}")

    def fetch_config(self):
        """Fetch configuration from IoT Manager server."""
        try:
            config = self.client.get_config()
            self.logger.info(f"Configuration fetched: {config}")
            
            # Validate server config
            try:
                validated_config = validate_server_config(config)
                return validated_config
            except ValidationError as e:
                self.logger.error(f"Server config validation failed: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Fetch config failed: {e}")
            return None

    def get_wakeup_time(self, config):
        """
        Calculate milliseconds until next scheduled wakeup.
        
        Args:
            config (dict): Configuration dict from server (may be None)
        
        Returns:
            int: Milliseconds to sleep (validated to reasonable range)
        """
        # Get config values
        default_ms = WAKEUP_CONFIG['default_interval_ms']
        min_ms = WAKEUP_CONFIG['min_interval_ms']
        max_ms = WAKEUP_CONFIG['max_interval_ms']
        esp32_offset = WAKEUP_CONFIG['esp32_epoch_offset']
        
        wakeup_time_ms = None
        
        # Try to get wakeup time from config with null safety
        try:
            if config and isinstance(config, dict):
                wakeup_time_ms = config.get('nextWakeupTimeMs')
                if wakeup_time_ms:
                    self.logger.info(f"Next wakeup time from server: {wakeup_time_ms}")
        except Exception as e:
            self.logger.warn(f"Error reading wakeup time from config: {e}")
        
        # If no valid wakeup time from server, use default
        if wakeup_time_ms is None:
            self.logger.info(f"Using default wakeup interval: {default_ms}ms ({default_ms / 1000 / 60 / 60:.0f} hours)")
            return default_ms
        
        # Calculate how long until that time
        # ESP32 time.time() returns seconds since Jan 1, 2000
        # Convert to Unix timestamp (ms since Jan 1, 1970) for comparison with server
        current_unix_timestamp_ms = (esp32_offset + time.time()) * 1000
        ms_til_next_wakeup = wakeup_time_ms - current_unix_timestamp_ms
        
        self.logger.debug(f"Current timestamp (Unix ms): {current_unix_timestamp_ms}")
        self.logger.debug(f"Wakeup time (Unix ms): {wakeup_time_ms}")
        self.logger.info(f"Time until wakeup: {ms_til_next_wakeup}ms ({ms_til_next_wakeup / 1000 / 60:.0f} minutes)")
        
        # Validate sleep time is in reasonable range
        if ms_til_next_wakeup < min_ms:
            self.logger.warn(f"Wakeup time in past or too soon. Using minimum: {min_ms}ms (1 minute)")
            return min_ms
        
        if ms_til_next_wakeup > max_ms:
            self.logger.warn(f"Wakeup time too far away. Capping to maximum: {max_ms}ms (48 hours)")
            return max_ms
        
        return ms_til_next_wakeup

    def main(self):
        """Main execution loop."""
        self.logger.info("Starting Program main function")
        wakeup_time = time.time()
        wake_reason = machine.wake_reason()
        self.logger.info(f"Wake reason: {wake_reason} at time: {wakeup_time}")
        timer_based_wakeup = (wake_reason == 4)
        allow_captive_portal = not timer_based_wakeup
        wlan = self.connect_wifi(enter_captive_portal_if_needed=allow_captive_portal)
        
        if wlan is None:
            self.logger.error("Failed to connect to WiFi")
            raise Exception("WiFi connection failed")
        
        self.logger.info(f"Connected to wifi. The time is now: {time.time()}")
        self.client.authenticate(self.device_id, self.device_password)
        self.client.discover()
        self.logger.info(f"Connected to IoT Manager at: {self.iot_manager_base_url}")
        
        config = None
        try:
            config = self.fetch_config()
            self.logger.info(f"Configuration: {config}")
        except Exception as e:
            self.logger.warn(f"Fetch config failed: {e}")

        # Set defaults
        in_test_mode = False
        weather_condition = DEFAULT_WEATHER_CONDITION
        
        # Override with server config if available
        try:
            if config and isinstance(config, dict):
                in_test_mode = config.get('testMode', False)
                server_weather = config.get('weatherCondition', DEFAULT_WEATHER_CONDITION)
                try:
                    weather_condition = validate_weather_condition(server_weather)
                except ValidationError:
                    self.logger.warn(f"Invalid weather condition '{server_weather}' from server, using default")
                    weather_condition = DEFAULT_WEATHER_CONDITION
        except Exception as e:
            self.logger.warn(f"Failed to read config: {e}")
        
        image_send_successful = None

        upload_test_image = in_test_mode or not timer_based_wakeup
        image_send_successful = self.take_photo(
            weather_condition=weather_condition,
            test_post=upload_test_image
        )   

        ms_til_next_wakeup = WAKEUP_CONFIG['test_mode_interval_ms']
        if not in_test_mode:
            ms_til_next_wakeup = self.get_wakeup_time(config)

        signal_strength = self.wifi_manager.get_signal_strength()
        device_status = {
            "signal_strength": signal_strength,
            "firmware_version": self.client.get_firmware_version(),
            "image_send_successful": image_send_successful,
            "wake_reason": wake_reason,
            "running_in_test_mode": in_test_mode,
            "sleep_for": ms_til_next_wakeup,
            "weather_condition": weather_condition
        }
        self.logger.info(f'Reporting device status: {device_status}')
        self.client.create_device_status(device_status)

        if not in_test_mode:
            try:
                self.logger.info("Checking for firmware updates...")
                self.client.check_and_update_firmware()
            except Exception as e:
                self.logger.error(f"Firmware update check failed: {e}")

        self.logger.info(f"Entering deep sleep for {ms_til_next_wakeup / 1000 / 60:.0f} minutes")
        machine.deepsleep(ms_til_next_wakeup)