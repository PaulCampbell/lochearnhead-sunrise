from lib.iot_manager_client import IotManagerClient
from lib.wifimgr import WifiManager
import time
import ntptime
import machine
import camera

class SuperCoolEsp:
    def __init__(self, iot_manager_base_url, device_id, device_password):
        self.iot_manager_base_url = iot_manager_base_url
        self.device_id = device_id
        self.device_password = device_password
        self.client = IotManagerClient(base_url=self.iot_manager_base_url)
        print("SuperCoolEsp initialized with device ID:", self.device_id)

    def connect_wifi(self):
        print("Connecting to WiFi...")
        wlan = WifiManager().get_connection()
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
        


    def take_photo(self, test_post=False):
        try:
            print("Taking photo...")
            camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM)
            camera.framesize(camera.FRAME_SXGA)
            frame = camera.capture()
            camera.deinit()
            print("Photo taken, size:", len(frame))
            response = self.client.upload_image(
                image_data=frame,
                test_post=test_post,
            )
            print("Image uploaded, response:", response)
        except Exception as e:
            print("create_content failed:", e)

    def fetch_wakeup_time(self):
        # Get tomorrow's wakeup time from IoT Manager
        # Default to 24 hours later
        wakeup_time_ms = (946684800 + time.time()) * 1000 + (24 * 60 * 60 * 1000)
        try:
            wakeup_time = self.client.get_config()
            wakeup_time_ms = wakeup_time.get('nextWakeupTimeMs')
            print("Next wakeup time from server:", wakeup_time_ms)
        except Exception as e:
            print("get_next_wakeup_time failed:", e)

        current_unix_timestamp = (946684800 + time.time()) * 1000
        print("wakeup_time_ms", wakeup_time_ms)
        print("current_unix_timestamp", current_unix_timestamp)
        ms_til_next_wakeup = wakeup_time_ms - current_unix_timestamp
        return ms_til_next_wakeup

    def main(self):
        wakeup_time = time.time()
        reason = machine.wake_reason()
        print("Wakeup time:", wakeup_time)
        print("Wake reason:", reason)

        self.connect_wifi()
        print("Connected to wifi. the time is now:", time.time())

        try:
            auth = self.client.authenticate(self.device_id, self.device_password)
            print("Authenticated; Authorization:", auth)
        except Exception as e:
            print("Authenticate failed:", e)
            return
        
        try:
            self.client.discover()
        except Exception as e:
            print("Service discovery failed:", e)
            return

        if reason == machine.DEEPSLEEP_RESET:
            self.take_photo()
        else:
            self.take_photo(test_post=True)
        
        ms_til_next_wakeup = self.fetch_wakeup_time()
        print("Entering deep sleep for: ", ms_til_next_wakeup)
        deepsleep_override = 60000 * 2
        print('deepsleep override to', deepsleep_override)
        machine.deepsleep(deepsleep_override)
