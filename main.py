import machine

from lib.super_cool_esp import SuperCoolEsp
from environment import (
    IOT_MANAGER_BASE_URL,
    DEVICE_ID,
    DEVICE_PASSWORD,
)


def main():
    program = SuperCoolEsp(
        iot_manager_base_url=IOT_MANAGER_BASE_URL,
        device_id=DEVICE_ID,
        device_password=DEVICE_PASSWORD,
    )

    try:
        print('Starting main program')
        program.main()
    except Exception as e:
        print("Unhandled exception in main:", e)
        # probably a WiFi issue; sleep for 5 minutes and try again
        print("Entering deep sleep for 5 minutes")
        machine.deepsleep(5 * 60 * 1000)

main()
