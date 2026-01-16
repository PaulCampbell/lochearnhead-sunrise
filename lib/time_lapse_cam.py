from lib.iot_manager_client import IotManagerClient
from lib.wifimgr import WifiManager
import time
import ntptime
import camera
import machine

TEST_MODE = False

class TimeLapseCam:
    def __init__(self, iot_manager_base_url, device_id, device_password):
        self.iot_manager_base_url = iot_manager_base_url
        self.device_id = device_id
        self.device_password = device_password
        self.client = IotManagerClient(base_url=self.iot_manager_base_url)
        self.wifi_manager = WifiManager(ssid='sunrise-cam', password='', authmode=0)
        print("TimeLapseCam initialized with device ID:", self.device_id)

    def connect_wifi(self, enter_captive_portal_if_needed):
        print("Connecting to WiFi...")
        wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=enter_captive_portal_if_needed)
        if wlan is None:
            print("ERROR: Could not initialize the network connection.")
            print("Entering deep sleep for 1 hour before retry...")
            # Sleep for 1 hour then retry automatically
            machine.deepsleep(60 * 60 * 1000)

        print("Network connected:", wlan.ifconfig())
        try:
            ntptime.settime()
            print("System time synchronized:", time.time())
        except Exception as e:
            print("Failed to synchronize time:", e)
        
        return wlan
        
    def take_photo(self, weather_condition, test_post=False):
        """Capture and upload a photo.
        
        Args:
            weather_condition: 'sunny', 'overcast', or other
            test_post: If True, marks upload as test post
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("Taking photo...")
            camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM)
            time.sleep(1.2)  # Wait for camera to stabilize
            
            # Apply camera settings
            camera.contrast(1)
            camera.saturation(-1)
            camera.framesize(camera.FRAME_QXGA)
            
            # Set white balance based on weather
            if weather_condition == 'sunny':
                camera.whitebalance(camera.WB_SUNNY)
            elif weather_condition == 'cloudy' or weather_condition == 'overcast':
                camera.whitebalance(camera.WB_CLOUDY)
            else:
                camera.whitebalance(camera.WB_NONE)
            
            # Capture frame
            frame = camera.capture()
            if frame is None or len(frame) == 0:
                print("ERROR: Camera capture returned empty frame")
                return False
            
            print(f"Captured frame: {len(frame)} bytes")
            
            # Upload
            try:
                response = self.client.upload_image(
                    image_data=frame,
                    test_post=test_post,
                )
                print("Image uploaded successfully")
                return True
            except Exception as e:
                print(f"ERROR: Image upload failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"ERROR: Photo capture failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            try:
                camera.deinit()
            except Exception as e:
                print(f"WARNING: Camera deinit failed: {e}")

    def fetch_config(self):
        try:
            config = self.client.get_config()
            print("Configuration fetched:", config)
            return config
        except Exception as e:
            print("fetch_config failed:", e)
            return None

    def get_wakeup_time(self, config):
        """Calculate milliseconds until next scheduled wakeup.
        
        Args:
            config: Configuration dict from server (may be None)
        
        Returns:
            int: Milliseconds to sleep (validated to reasonable range)
        """
        # Constants
        DEFAULT_WAKEUP_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 hours
        MIN_WAKEUP_INTERVAL_MS = 1 * 60 * 1000             # 1 minute
        MAX_WAKEUP_INTERVAL_MS = 48 * 60 * 60 * 1000      # 48 hours
        
        # ESP32 epoch offset: Jan 1, 2000 = 946684800 seconds from Unix epoch
        ESP32_EPOCH_OFFSET = 946684800
        
        wakeup_time_ms = None
        
        # Try to get wakeup time from config with null safety
        try:
            if config and isinstance(config, dict):
                wakeup_time_ms = config.get('nextWakeupTimeMs')
                if wakeup_time_ms:
                    print("Next wakeup time from server:", wakeup_time_ms)
        except Exception as e:
            print("Error reading wakeup time from config:", e)
        
        # If no valid wakeup time from server, use default
        if wakeup_time_ms is None:
            print("Using default wakeup interval:", DEFAULT_WAKEUP_INTERVAL_MS, "ms")
            return DEFAULT_WAKEUP_INTERVAL_MS
        
        # Calculate how long until that time
        # ESP32 time.time() returns seconds since Jan 1, 2000
        # Convert to Unix timestamp (ms since Jan 1, 1970) for comparison with server
        current_unix_timestamp_ms = (ESP32_EPOCH_OFFSET + time.time()) * 1000
        ms_til_next_wakeup = wakeup_time_ms - current_unix_timestamp_ms
        
        print("Current timestamp (Unix ms):", current_unix_timestamp_ms)
        print("Wakeup time (Unix ms):", wakeup_time_ms)
        print("Time until wakeup:", ms_til_next_wakeup, "ms")
        
        # Validate sleep time is in reasonable range
        if ms_til_next_wakeup < MIN_WAKEUP_INTERVAL_MS:
            print(f"Warning: Wakeup time in past or too soon. Using minimum: {MIN_WAKEUP_INTERVAL_MS}ms")
            return MIN_WAKEUP_INTERVAL_MS
        
        if ms_til_next_wakeup > MAX_WAKEUP_INTERVAL_MS:
            print(f"Warning: Wakeup time too far away. Capping to maximum: {MAX_WAKEUP_INTERVAL_MS}ms")
            return MAX_WAKEUP_INTERVAL_MS
        
        return ms_til_next_wakeup

    def main(self):
        print("Starting TimeLapseCam main function")
        wakeup_time = time.time()
        wake_reason = machine.wake_reason()
        print("Wake reason:", wake_reason, "at time:", wakeup_time)
        timer_based_wakeup = (wake_reason == 4)
        allow_captive_portal = not timer_based_wakeup
        wlan = self.connect_wifi(enter_captive_portal_if_needed=allow_captive_portal)
        
        if wlan is None:
            print("Failed to connect to WiFi.")
            raise Exception("WiFi connection failed")
        
        print("Connected to wifi. the time is now:", time.time())
        self.client.authenticate(self.device_id, self.device_password)
        self.client.discover()
        print("Connected to IoT Manager at:", self.iot_manager_base_url)
        
        config = None
        try:
            config = self.fetch_config()
            print("Configuration:", config)
        except Exception as e:
            print("Fetch config failed:", e)

        # Set defaults
        in_test_mode = False
        weather_condition = 'overcast'
        
        # Override with server config if available
        try:
            if config and isinstance(config, dict):
                in_test_mode = config.get('testMode', False)
                server_weather = config.get('weatherCondition', 'overcast')
                if server_weather in ('sunny', 'overcast', 'cloudy'):
                    weather_condition = server_weather
                else:
                    print(f"Warning: Unknown weather condition '{server_weather}', using 'overcast'")
        except Exception as e:
            print(f"Warning: Failed to read config: {e}")
        
        image_send_successful = None


        upload_test_image = in_test_mode or not timer_based_wakeup
        image_send_successful = self.take_photo(weather_condition=weather_condition, test_post=upload_test_image)   

        ms_til_next_wakeup = 30 * 1000
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
            "weather_condition": weather_condition,
        }
        print('Reporting device status:', device_status)
        self.client.create_device_status(device_status)

        if not in_test_mode:
            try:
                print("Checking for firmware updates...")
                self.client.check_and_update_firmware()
            except Exception as e:
                print("Firmware update check failed:", e)

        print("Entering deep sleep for: ", ms_til_next_wakeup)
        machine.deepsleep(ms_til_next_wakeup)