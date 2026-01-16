# Developer Quick Start: Implementing the Fixes

This guide walks you through implementing the critical fixes step-by-step.

## Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify you can connect to device
mpremote connect "/dev/tty.usbserial-10" ls
```

## Fix #1: wifi.dat Missing File (15 minutes)

**File:** `lib/wifimgr.py`
**Lines:** Around 272

### Current Code
```python
def read_profiles():
    with open(NETWORK_PROFILES) as f:  # ❌ Crashes if missing
        lines = f.readlines()
    profiles = {}
    for line in lines:
        ssid, password = line.strip("\n").split(";")
        profiles[ssid] = password
    return profiles
```

### Replace With
```python
def read_profiles():
    """Read WiFi profiles from storage. Returns empty dict if file doesn't exist."""
    try:
        with open(NETWORK_PROFILES) as f:
            lines = f.readlines()
        profiles = {}
        for line in lines:
            if line.strip():  # Skip empty lines
                try:
                    ssid, password = line.strip("\n").split(";", 1)  # Use split with max=1
                    profiles[ssid] = password
                except ValueError:
                    print(f"Warning: Skipping malformed wifi.dat line: {line}")
        return profiles
    except OSError:
        # File doesn't exist yet (first boot) - return empty profiles
        print("Note: wifi.dat not found. Device will scan for networks.")
        return {}
```

### Test
```bash
# Connect to device
mpremote connect "/dev/tty.usbserial-10" repl

# In REPL:
from lib.wifimgr import read_profiles
profiles = read_profiles()  # Should not crash, should return {}
print(profiles)
```

---

## Fix #2: Timestamp Calculation (20 minutes)

**File:** `lib/time_lapse_cam.py`
**Lines:** 77-89

### Current Code
```python
def get_wakeup_time(self, config):
    # Get tomorrow's wakeup time from IoT Manager
    # Default to 24 hours later
    wakeup_time_ms = (946684800 + time.time()) * 1000 + (24 * 60 * 60 * 1000)
    try:
        wakeup_time_ms = config.get('nextWakeupTimeMs')  # ❌ Crashes if config is None!
        print("Next wakeup time from server:", wakeup_time_ms)
    except Exception as e:
        print("get_next_wakeup_time failed:", e)

    current_unix_timestamp = (946684800 + time.time()) * 1000
    print("wakeup_time_ms", wakeup_time_ms)
    print("current_unix_timestamp", current_unix_timestamp)
    ms_til_next_wakeup = wakeup_time_ms - current_unix_timestamp
    return ms_til_next_wakeup
```

### Problems
The offset (946684800) is correct for ESP32's year-2000 epoch, BUT:
1. No null safety - crashes if `config` is None
2. Confusing initialization mixing time conversion with offset
3. No validation that sleep time is reasonable
4. Exception caught but no sensible default returned

### Replace With
```python
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
```
```

### Test
```bash
# In REPL:
import time
from lib.time_lapse_cam import TimeLapseCam

cam = TimeLapseCam("http://test", "test-id", "test-pwd")

# Test with None config
sleep_time = cam.get_wakeup_time(None)
print(f"Sleep time: {sleep_time}ms (should be 86400000)")

# Test with valid config
config = {'nextWakeupTimeMs': int(time.time() * 1000) + 3600000}  # 1 hour from now
sleep_time = cam.get_wakeup_time(config)
print(f"Sleep time: {sleep_time}ms (should be ~3600000)")
```

---

## Fix #3: Infinite Loop (10 minutes)

**File:** `lib/time_lapse_cam.py`
**Lines:** 23-27

### Current Code
```python
wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=allow_captive_portal)

if wlan is None:
    print("Could not initialize the network connection.")
    while True:  # ❌ DEVICE HANGS FOREVER
        pass
```

### Replace With
```python
wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=allow_captive_portal)

if wlan is None:
    print("ERROR: Could not initialize the network connection.")
    print("Entering deep sleep for 1 hour before retry...")
    # Sleep for 1 hour then retry automatically
    machine.deepsleep(60 * 60 * 1000)
```

### Test
```bash
# Turn off WiFi on your computer
# Connect device and power on
# Device should try WiFi for ~20 seconds
# Then print "Entering deep sleep..."
# Then enter sleep (LED off)
# Wait 10 seconds and verify it doesn't wake up immediately
```

---

## Fix #4: Weather Condition (15 minutes)

**File:** `lib/time_lapse_cam.py`
**Lines:** 112-113

### Current Code
```python
in_test_mode = config is not None and config.get('testMode', False)
weather_condition = config is not None and config.get('weatherCondition', 'overcast')
```

### Replace With
```python
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

print(f"Test mode: {in_test_mode}, Weather: {weather_condition}")
```

### Test
```bash
# In REPL:
config = {'testMode': True, 'weatherCondition': 'sunny'}

# Before fix: weather_condition = <dict object>
# After fix: weather_condition = 'sunny'

from lib.time_lapse_cam import TimeLapseCam
cam = TimeLapseCam("http://test", "test-id", "test-pwd")

# In main, it will properly set camera white balance now
```

---

## Fix #5: Camera Error Handling (20 minutes)

**File:** `lib/time_lapse_cam.py`
**Lines:** 47-69

### Current Code
```python
def take_photo(self, weather_condition, test_post=False):
    try:
        print("Taking photo...")
        camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM)
        time.sleep(1.2) 
        camera.contrast(1)
        camera.saturation(-1)
        camera.framesize(camera.FRAME_QXGA)

        if weather_condition == 'sunny':
            camera.whitebalance(camera.WB_SUNNY)
        elif weather_condition == 'overcast':
            camera.whitebalance(camera.WB_CLOUDY)
        else:
            camera.whitebalance(camera.WB_NONE)

        frame = camera.capture()
        response = self.client.upload_image(
            image_data=frame,
            test_post=test_post,
        )
        print("Image uploaded, response:", response)
        return True
    except Exception as e:
        print("create_content failed:", e)
        return e  # ❌ Returns exception, not bool!
    finally:
        camera.deinit()
```

### Replace With
```python
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
```

### Test
```bash
# In REPL:
# Test that return value is always boolean
result = cam.take_photo('sunny', test_post=True)
print(f"Result type: {type(result)}, Value: {result}")
# Should print: Result type: <class 'bool'>, Value: True (or False)
```

---

## Integration Test: Full Boot Sequence

```bash
# Deploy updated code to device
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh

# Connect to device
mpremote connect "/dev/tty.usbserial-10" repl

# Monitor output - should see:
# ✓ "Starting main program"
# ✓ "Connecting to WiFi..."
# ✓ "Network connected: ..."
# ✓ "Taking photo..."
# ✓ "Captured frame: XXX bytes"
# ✓ "Image uploaded successfully"
# ✓ "Entering deep sleep for: XXX ms"

# Ctrl+C to exit
```

---

## Verification Checklist

After implementing all 5 fixes:

- [ ] Device boots without crashing
- [ ] Device scans WiFi even if wifi.dat missing
- [ ] Captive portal works if no WiFi configured
- [ ] Connected WiFi is saved to wifi.dat
- [ ] Wakeup time calculation is correct (test with known server time)
- [ ] WiFi timeout doesn't hang, device sleeps
- [ ] Camera photo is captured correctly
- [ ] Photo is uploaded to server
- [ ] Device reports status to server
- [ ] Device enters deep sleep at end
- [ ] No inconsistent return types (all bool)
- [ ] All exceptions have proper error messages

---

## Common Issues & Solutions

### Issue: Device still crashes on boot
**Solution:** Verify you've edited the right function in wifimgr.py

```bash
# Search for the function
mpremote connect "/dev/tty.usbserial-10" ls lib/wifimgr.py

# Re-deploy
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

### Issue: WiFi timeout hangs
**Solution:** Verify the `while True` loop is removed and replaced with `machine.deepsleep()`

```bash
# Check deployed code
mpremote connect "/dev/tty.usbserial-10" cat lib/time_lapse_cam.py | grep -A2 "wlan is None"
```

### Issue: Wrong wakeup times
**Solution:** Verify timestamp calculation doesn't use the 946684800 offset

```bash
# Test timestamp directly
mpremote connect "/dev/tty.usbserial-10" repl
import time
print(int(time.time() * 1000))  # Should be ~1.7 trillion
```

### Issue: Photo capture returns exception instead of bool
**Solution:** Verify the except clause returns `False` not `e`

```bash
# Search for "return e"
mpremote connect "/dev/tty.usbserial-10" grep -n "return e" lib/time_lapse_cam.py
# Should return nothing (if fixed)
```

---

## Next Steps

1. **Implement all 5 fixes** above (1-1.5 hours total)
2. **Deploy to device** (5 min)
3. **Test each scenario** (30 min)
4. **Commit changes** to git (5 min)
5. **Read IMPROVEMENT_SUGGESTIONS.md** for next batch of improvements

---

## Need Help?

Check these in order:
1. **QUICK_FIX_CHECKLIST.md** - More detailed explanations
2. **IMPROVEMENT_SUGGESTIONS.md** - All 20 issues documented
3. **VISUAL_GUIDE.md** - Diagrams and flow charts
4. **ARCHITECTURE_RECOMMENDATIONS.md** - Long-term improvements

---

**Time to implement:** ~1.5 hours
**Expected result:** Device boots reliably, handles errors gracefully, captures photos correctly
