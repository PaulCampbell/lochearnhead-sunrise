# Timelapse esp32 Camera (locheanhead-sunrise)

Here is the code for an esp32 timelapse camera. 

It powers the Lochearnhead-Sunrise Fediverse Bot: https://agoodmooring.com/a/lochearnhead-sunrise

If you know what the fediverse is, you should follow that thing :)

## Components

The hardware for this thing is cheap and cheerful. You'll need:

 - [esp32 cam development board](https://www.amazon.co.uk/diymore-ESP32-CAM-Development-Board-2PCS-Micro-USB/dp/B0FQ5PSKBP/ref=sr_1_12?tag=agoodmooring-21)
 - [18650 Lithium Li-ion Battery Expansion Shield](https://www.amazon.co.uk/AZDelivery-Lithium-Li-ion-Battery-Expansion/dp/B086W72P2W/ref=sr_1_4?tag=agoodmooring-21)

You're also gonna need a battery, a soldering iron, some jumper cables, and some kind of enclosure. 

If you have a 3d printer you could maybe [print one](3d-models])

## Features

- Wifi configuration via Access Point (local hotspot)
- OTA updates
- Take a picture, upload a picture, deepsleep until next picture

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

## Wifi config

When the device starts up, if it cannot connect to the internet it will start a wifi hotspot. Connect to the hotspot with your phone, and after a few seconds one of those captive wifi pages will pop open.  Select your local wifi network, and give the device the network password, and from now on the device will use your wifi network. Woop.

## OTA updates

IOT Manager on the server uses the github api to call this repository to get the latest release. It hands the link back to the device, which pulls the latest release, unzips it and installs it. New releases in the repository will end up on the device soon.

## Enclosure

I never had anything sensible lying around to put the thing in, so I made a little [enclosure](/3d-models) with OpenScad and printed it. It's pretty basic, but hopefully it will do the job!.

## On the server...

It uses https://github.com/PaulCampbell/iot_manager as the backend

IOT Manager is configured something like this:

```javascript
import createIotManager from 'iot_manager'
import {Authenticate, CreateContent } from 'iot_manager/events'
import iotManagerBasicHttpAuth from 'iot_manager/authentication/iot-manager-basic-http'

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
  .on(GetLatestVersion, async (ctx) => {
    debug('GetLatestVersion event received:', ctx);
    const response = await octokit.request('GET /repos/{owner}/{repo}/releases/latest', {
      owner: process.env.SUNRISE_BOT_REPO_OWNER,
      repo: process.env.SUNRISE_BOT_REPO_NAME,
      headers: {
        'X-GitHub-Api-Version': '2022-11-28'
      }
    })
    const latestRelease = response.data;
    const { tag_name, tarball_url } = latestRelease;
    return {
      version: tag_name,
      url: tarball_url,
    };
  })
  .on(GetConfig, async (ctx, data) => {
    const nextWakeupDateTime = await getTomorrowSunriseTime()
    const nextWakeupTimeMs = nextWakeupDateTime.getTime() - new Date().getTime()
    return {
      nextWakeupDateTime,
      nextWakeupTimeMs,
    };
  })
  .on(CreateContent, async (ctx, data) => {
    // Nice - picture received...
    const picUrl = await savePicture(data._formData)
    await postToFediverse({
        imageUrl: picUrl
    })
    return { success: true }
  })
```
