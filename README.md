# Timelapse esp32 Camera (locheanhead-sunrise)

Here is the code for an esp32 timelapse camera. 

It powers the Lochearnhead-Sunrise Fediverse Bot: https://agoodmooring.com/a/lochearnhead-sunrise

If you know what the fediverse is, you should follow that thing :)

It uses https://github.com/PaulCampbell/iot_manager as the backend

IOT Manager is configured something like this:

```javascript
import createIotManager from 'iot_manager'
import {Authenticate, CreateContent } from 'iot_manager/events'
import iotManagerBasicHttpAuth from 'iot_manager/authentication/iot-manager-basic-http'

// Create data store and authentication
const iotAuthentication = iotManagerBasicHttpAuth({ 
  secret: process.env.AUTH_SECRET
})

// Create IoT manager and register event handlers
const iotManager = createIotManager({  iotAuthentication })

iotManager.setEndpointListener({ pathRoot: '/iot-manager' })
  .on(Authenticate, async (ctx, data) => {
     const { deviceId, password } = payload;
     if (!deviceId || !password) {
        throw Object.assign(new Error('deviceId and password are required'), {
            status: 400,
            body: { error: 'deviceId and password are required' },
        });
     }
     // do some authentication stuff
     const authHeader = generateAuthHeader(deviceId, secret);
     return {
          deviceId: deviceId,
          authorization: authHeader,
      };
  })
  .on(CreateContent, async (ctx, data) => {
    // Nice - picture received
    const picUrl = await savePicture(data._formData)
    await postToFediverse({
        imageUrl: picUrl
    })
    return { success: true }
  })
```

## Development

Create & source a venv and restore the requirements

```
python3 -m venv .venv
source .venv/bin/activate 
pip install -r requirements.txt
```

Plug your esp32 into your usb and find its port:

```
ls /dev/tty.usb*
```

erase the flash and install the micropython firmware:

```
esptool --baud 115200 --chip esp32 --port /dev/tty.usbserial-10 erase-flash 

esptool.py --chip esp32 --port /dev/tty.usbserial-10 write_flash -z 0x1000  clients/micropython/micropython_v1.21.0_camera_no_ble.bin
```

Copy environment.example.py to environment.py and set the environment variables

```
WIFI_SSID = "your_ssid"
WIFI_PASSWORD = "your_password"
IOT_MANAGER_BASE_URL = "server_api_endpoint"
DEVICE_ID = "your_device_id"
DEVICE_PASSWORD = "your_password"
```

Copy the code to the device:

```
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh 
```

Debugging: Connect to the device to check the logs / run code etc

```
mpremote connect "/dev/tty.usbserial-10" repl
```

## Enclosure

I never had anything sensible lying around to put the thing in, so I made a little [enclosure]|(/3d-models) with OpenScad and printed it. It's pretty basic, but hopefully it will do the job!.
