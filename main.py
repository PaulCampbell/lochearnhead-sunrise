import machine
from lib.program import Program
from lib.logger import init_logger
from lib.config import LOG_CONFIG, TEST_MODE
from environment import (
    IOT_MANAGER_BASE_URL,
    DEVICE_ID,
    DEVICE_PASSWORD,
)


def main():
    # Initialize infrastructure
    logger = init_logger(level=LOG_CONFIG.get('level', 'INFO'))
    
    logger.info("=" * 60)
    logger.info("DEVICE STARTUP")
    logger.info("=" * 60)
    logger.info(f"Test mode: {TEST_MODE}")
    
    try:
        program = Program(
            iot_manager_base_url=IOT_MANAGER_BASE_URL,
            device_id=DEVICE_ID,
            device_password=DEVICE_PASSWORD,
        )

        logger.info('Starting main program')
        program.main()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        import traceback
        traceback.print_exc()
        # probably a WiFi issue; restart
        logger.info("Restarting device...")
        machine.reset()

if __name__ == '__main__':
    main()

