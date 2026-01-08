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
            print("Could not initialize the network connection.")
            while True:
                pass

        print("Network connected:", wlan.ifconfig())
        try:
            ntptime.settime()
            print("System time synchronized:", time.time())
        except Exception as e:
            print("Failed to synchronize time:", e)
        
        return wlan
        
    def take_photo(self, test_post=False):
        try:
            print("Taking photo...")
            camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM)
            camera.framesize(camera.FRAME_SXGA)
            camera.whitebalance(camera.WB_SUNNY)
            frame = camera.capture()
            camera.deinit()
            print("Photo taken, size:", len(frame))
            response = self.client.upload_image(
                image_data=frame,
                test_post=test_post,
            )
            print("Image uploaded, response:", response)
            return True
        except Exception as e:
            print("create_content failed:", e)
            return e

    def fetch_config(self):
        try:
            config = self.client.get_config()
            print("Configuration fetched:", config)
            return config
        except Exception as e:
            print("fetch_config failed:", e)
            return None

    def get_wakeup_time(self, config):
        # Get tomorrow's wakeup time from IoT Manager
        # Default to 24 hours later
        wakeup_time_ms = (946684800 + time.time()) * 1000 + (24 * 60 * 60 * 1000)
        try:
            wakeup_time_ms = config.get('nextWakeupTimeMs')
            print("Next wakeup time from server:", wakeup_time_ms)
        except Exception as e:
            print("get_next_wakeup_time failed:", e)

        current_unix_timestamp = (946684800 + time.time()) * 1000
        print("wakeup_time_ms", wakeup_time_ms)
        print("current_unix_timestamp", current_unix_timestamp)
        ms_til_next_wakeup = wakeup_time_ms - current_unix_timestamp
        return ms_til_next_wakeup

    def main(self):
        print("Starting TimeLapseCam main function")
        wakeup_time = time.time()
        wake_reason = machine.wake_reason()
        print("Wake reason:", wake_reason, "at time:", wakeup_time)
        allow_captive_portal = (wake_reason != machine.DEEPSLEEP_RESET)
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

        image_send_successful = None 
        in_test_mode = config is not None and config.get('testMode', False)
        if wake_reason == machine.DEEPSLEEP_RESET:
            image_send_successful = self.take_photo(test_post=in_test_mode)   
        else:
            print("Not taking photo on normal reset wakeup.")
         
        ms_til_next_wakeup = 30 * 1000
        if in_test_mode:
            ms_til_next_wakeup = 30 * 1000
        else:
            ms_til_next_wakeup = self.get_wakeup_time(config)

        try:
            print("Checking for firmware updates...")
            self.client.check_and_update_firmware()
        except Exception as e:
            print("Firmware update check failed:", e)

        signal_strength = self.wifi_manager.get_signal_strength()
        device_status = {
            "signal_strength": signal_strength,
            "firmware_version": self.client.get_firmware_version(),
            "image_send_successful": image_send_successful,
            "wake_reason": wake_reason,
            "running_in_test_mode": in_test_mode,
        }
        self.client.create_device_status(device_status)
        print("Entering deep sleep for: ", ms_til_next_wakeup)
        machine.deepsleep(ms_til_next_wakeup)