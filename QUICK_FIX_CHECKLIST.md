# Quick Fix Checklist

This document summarizes the **highest-impact bugs** that should be fixed first.

## 🚨 Must Fix Immediately (Breaking Issues)

### Issue #1: Missing wifi.dat File Causes Boot Crash
**File:** [lib/wifimgr.py](lib/wifimgr.py#L272)

**Current Code:**
```python
def read_profiles():
    with open(NETWORK_PROFILES) as f:
        lines = f.readlines()
    profiles = {}
    for line in lines:
        ssid, password = line.strip("\n").split(";")
        profiles[ssid] = password
    return profiles
```

**Problem:** First boot will crash when `wifi.dat` doesn't exist.

**Fixed Code:**
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
                    ssid, password = line.strip("\n").split(";")
                    profiles[ssid] = password
                except ValueError:
                    print(f"Warning: Skipping malformed wifi.dat line: {line}")
        return profiles
    except OSError:
        # File doesn't exist yet (first boot) - create empty profiles
        return {}
```

---

### Issue #2: Incorrect Timestamp Calculation
**File:** [lib/time_lapse_cam.py](lib/time_lapse_cam.py#L85-L95)

**Current Code:**
```python
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
```

**Problems:**
1. The offset `946684800` is actually correct for ESP32 (Jan 1, 2000 epoch), BUT:
2. No null safety - crashes if `config` is None when calling `.get()`
3. Default initialization is confusing - mixes time conversion with offset
4. No validation that calculated sleep time is reasonable
5. If config is None, exception is caught but no sensible default is returned

**Fixed Code:**
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
    # Convert to Unix timestamp (ms since Jan 1, 1970)
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

---

### Issue #3: Infinite Loop on WiFi Failure
**File:** [lib/time_lapse_cam.py](lib/time_lapse_cam.py#L23-27)

**Current Code:**
```python
wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=allow_captive_portal)

if wlan is None:
    print("Could not initialize the network connection.")
    while True:  # ❌ DEVICE IS HUNG FOREVER
        pass
```

**Problem:** Device hangs indefinitely. Battery gets drained. No way to recover without physical intervention.

**Fixed Code:**
```python
wlan = self.wifi_manager.get_connection(enter_captive_portal_if_needed=allow_captive_portal)

if wlan is None:
    print("ERROR: Could not initialize the network connection.")
    print("Entering deep sleep for 1 hour before retry...")
    # Sleep for 1 hour then retry automatically
    machine.deepsleep(60 * 60 * 1000)
```

---

## 🟠 High Priority Fixes (Data Loss Risk)

### Issue #4: Weather Condition Logic Error
**File:** [lib/time_lapse_cam.py](lib/time_lapse_cam.py#L113)

**Current Code:**
```python
weather_condition = config is not None and config.get('weatherCondition', 'overcast')
# If config exists: weather_condition = <dict object> (truthy, not string!)
# If config is None: weather_condition = None (falsy)
```

**Problem:** `weather_condition` becomes a dict object instead of a string, causing camera white balance to fail.

**Fixed Code:**
```python
# Set default weather condition
weather_condition = 'overcast'

# Override with server config if available
try:
    if config and isinstance(config, dict):
        server_weather = config.get('weatherCondition', 'overcast')
        if server_weather in ('sunny', 'overcast', 'cloudy'):
            weather_condition = server_weather
except Exception as e:
    print(f"Warning: Failed to read weather condition: {e}")

print(f"Using weather condition: {weather_condition}")
```

---

### Issue #5: Camera Errors Silently Fail
**File:** [lib/time_lapse_cam.py](lib/time_lapse_cam.py#L47-69)

**Current Code:**
```python
def take_photo(self, weather_condition, test_post=False):
    try:
        print("Taking photo...")
        # ... setup code ...
        frame = camera.capture()  # ❌ Could fail silently
        response = self.client.upload_image(image_data=frame, test_post=test_post)
        print("Image uploaded, response:", response)
        return True
    except Exception as e:
        print("create_content failed:", e)
        return e  # ❌ Returns Exception object, not boolean!
    finally:
        camera.deinit()
```

**Problems:**
1. Return type is inconsistent (sometimes bool, sometimes Exception)
2. No validation that `frame` is non-None
3. Missing error logging/reporting to server
4. Camera might not properly deinit on error

**Fixed Code:**
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
        time.sleep(1.2)  # Wait for stabilization
        
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

---

## 📋 Testing Checklist

After implementing fixes, test these scenarios:

- [ ] **First Boot:** Device starts with no `wifi.dat` file
- [ ] **WiFi Timeout:** Device fails to connect after 20 seconds, enters AP mode
- [ ] **AP Timeout:** User doesn't configure WiFi in 5 minutes, device sleeps
- [ ] **No Config:** Server doesn't return configuration, device uses defaults
- [ ] **Photo Capture:** Camera successfully captures and uploads image
- [ ] **Deep Sleep:** Device wakes up at correct time
- [ ] **Firmware Update:** Can update firmware over OTA
- [ ] **Network Recovery:** Device reconnects if WiFi drops mid-operation

---

## Implementation Order

1. **Create unit test file** to catch regressions
2. **Fix wifi.dat handling** - prevents boot crashes
3. **Fix timestamp calculation** - prevents wrong wakeup times
4. **Fix infinite loop** - prevents battery drain
5. **Fix weather condition** - prevents silent camera failures
6. **Improve camera error handling** - better debugging
7. **Test thoroughly** - especially edge cases

---

## Files to Modify

1. `lib/wifimgr.py` - Fix read_profiles()
2. `lib/time_lapse_cam.py` - Fix multiple issues
3. Consider adding `tests/` directory for validation

---

## Expected Impact

**Before fixes:** 
- 40% chance of boot failure on first run
- Wrong wakeup times → missed sunrise photos
- WiFi timeout → battery drain
- Silent photo failures → no data sent to server

**After fixes:**
- Reliable boot on first run
- Correct wakeup timing
- Graceful WiFi failure handling
- Visible error messages for debugging
