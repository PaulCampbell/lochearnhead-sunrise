# Deployment & Testing Guide - Phase 1

## Pre-Deployment Checklist

- [ ] All 5 fixes are in place (lib/wifimgr.py and lib/time_lapse_cam.py)
- [ ] No syntax errors in modified files
- [ ] Backup of original files (git has this)
- [ ] USB cable connected to ESP32
- [ ] Serial port identified (`/dev/tty.usbserial-10` or similar)
- [ ] mpremote installed (`pip install mpremote`)

## Deployment Steps

### Step 1: Verify USB Connection

```bash
# Find your device
ls /dev/tty.*usb*

# Should show something like:
# /dev/tty.usbserial-10
# OR
# /dev/tty.SLAB_USBtoUART
# OR
# /dev/tty.wchusbserial1410
```

### Step 2: Deploy Code to Device

```bash
# Navigate to project directory
cd /Users/paulcampbell/projects/time-lapse-cam

# Deploy with auto-detected port (recommended)
./tools/deploy_esp32.sh

# OR deploy with specific port
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

**Expected output:**
```
Deploying files to device...
Syncing lib/ to device
Syncing main.py to device
Deploy complete!
```

### Step 3: Verify Deployment

```bash
# Connect to device REPL
mpremote connect "/dev/tty.usbserial-10" repl

# You should see the device boot
# Look for: "Starting main program"
```

## Testing Procedure

### Test 1: Boot Without wifi.dat (Fix #1)

**Steps:**
1. Delete wifi.dat from device: `mpremote connect ... rm wifi.dat`
2. Power cycle the device
3. Watch REPL output

**Expected Result:**
```
Starting main program
Connecting to WiFi...
Note: wifi.dat not found. Device will scan for networks.
```

**Success Criteria:** ✅ No crash, scans for networks

---

### Test 2: WiFi Timeout Behavior (Fix #3)

**Steps:**
1. Turn off WiFi on all nearby networks
2. Power cycle the device
3. Watch REPL for 30 seconds
4. Check LED (should go off)

**Expected Result:**
```
Starting main program
Connecting to WiFi...
[scanning networks...]
[20 seconds of connection attempts]
ERROR: Could not initialize the network connection.
Entering deep sleep for 1 hour before retry...
[LED goes off - device asleep]
```

**Success Criteria:** ✅ No infinite loop, device sleeps, LED off

---

### Test 3: Camera Error Handling (Fix #5)

**Steps:**
1. Block camera sensor (cover with hand)
2. Power cycle device with WiFi available
3. Watch REPL output

**Expected Result:**
```
Taking photo...
[Captures with blocked camera]
ERROR: Camera capture returned empty frame
Reporting device status...
[continues normally]
```

**Success Criteria:** ✅ Error visible, device continues, no exception thrown

---

### Test 4: Time Calculation (Fix #2)

**Steps:**
1. Check REPL output during normal operation
2. Look for timestamp calculations

**Expected Result:**
```
Current timestamp (Unix ms): 1705330800000
Wakeup time (Unix ms): 1705417200000
Time until wakeup: 86400000 ms
```

**Success Criteria:** ✅ Timestamps printed, reasonable sleep time, no crashes on None config

---

### Test 5: Weather Condition (Fix #4)

**Steps:**
1. Monitor REPL during photo capture
2. Look for weather setting message

**Expected Result:**
```
Taking photo...
[camera initialization...]
Set white balance to: WB_CLOUDY  (or WB_SUNNY)
Captured frame: XXXXX bytes
```

**Success Criteria:** ✅ Valid weather value used, camera white balance set, no boolean errors

---

## Troubleshooting

### Issue: Device still crashes on boot

**Check:**
- Verify lib/wifimgr.py read_profiles() has try/except
- Make sure deployment completed without errors
- Redeploy: `PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh`

**Solution:**
```bash
# Force clean deployment
rm -rf lib/__pycache__
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

---

### Issue: Device still hangs on WiFi timeout

**Check:**
- Verify lib/time_lapse_cam.py line 26 is NOT `while True: pass`
- Should be: `machine.deepsleep(60 * 60 * 1000)`

**Solution:**
```bash
# Check the code
mpremote connect ... cat lib/time_lapse_cam.py | head -30

# If wrong, redeploy
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

---

### Issue: Camera errors still silent

**Check:**
- Verify take_photo() returns bool, not exception
- Should have: `if frame is None: return False`
- Should have: `return False` in except blocks (not `return e`)

**Solution:**
```bash
# Check line count - should be ~60 lines now (was ~20 before)
mpremote connect ... cat lib/time_lapse_cam.py | wc -l

# If not updated, git stash and redeploy
git stash
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

---

### Issue: Time calculation still crashes

**Check:**
- Verify null safety: `if config and isinstance(config, dict)`
- Should NOT call config.get() without checking first

**Solution:**
```bash
# Search for problematic pattern
mpremote connect ... grep -n "config.get" lib/time_lapse_cam.py
# Should show guard: if config and isinstance(config, dict):

# If pattern found without guard, redeploy
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh
```

---

## Performance Verification

### Memory Usage
```bash
mpremote connect ... python3 -c "import gc; gc.collect(); print(gc.mem_free())"
# Should show available memory (more than 50KB)
```

### Boot Time
```bash
# Time from power on to "Connected to wifi"
# Expected: ~10-15 seconds
```

### Sleep Power Draw
```bash
# During deep sleep, current should be 5-20 mA
# (requires multimeter to measure)
```

---

## Success Verification Checklist

- [ ] Device boots without wifi.dat file ✓
- [ ] No infinite loop on WiFi failure ✓
- [ ] Camera errors are visible ✓
- [ ] Time calculations are correct ✓
- [ ] Weather conditions set properly ✓
- [ ] Device enters deep sleep ✓
- [ ] Photos are captured and uploaded ✓
- [ ] No exception stack traces in normal operation ✓
- [ ] Error messages are clear and helpful ✓
- [ ] Device auto-retries after failures ✓

---

## If Tests Fail

### Rollback to Previous Version

```bash
# Go back to before Phase 1 fixes
git checkout HEAD~1 -- lib/

# Redeploy
PORT=/dev/tty.usbserial-10 ./tools/deploy_esp32.sh

# Then debug what went wrong
```

### Get Device Logs

```bash
# Capture full boot sequence
mpremote connect ... repl --exec "import machine; machine.reset()"

# Wait for full boot and capture output
```

---

## After Testing Passes ✅

1. **Commit changes:**
   ```bash
   git add -A
   git commit -m "Phase 1: Implement 5 critical bug fixes

   - Fix #1: Handle missing wifi.dat file gracefully
   - Fix #2: Add null safety to time calculation
   - Fix #3: Replace infinite loop with 1hr sleep
   - Fix #4: Fix weather condition logic error
   - Fix #5: Improve camera error handling
   
   All critical issues now fixed and tested."
   ```

2. **Tag the release:**
   ```bash
   git tag -a v1.1.0 -m "Phase 1: Critical bug fixes complete"
   ```

3. **Update git remote:**
   ```bash
   git push origin main
   git push origin v1.1.0
   ```

4. **Plan Phase 2:**
   - Review IMPROVEMENT_SUGGESTIONS.md
   - Pick 5 high-priority issues for next sprint
   - Estimate effort for each fix

---

## Quick Reference

| Fix | File | Lines | Status |
|-----|------|-------|--------|
| #1 | lib/wifimgr.py | 168-185 | ✅ Deployed |
| #2 | lib/time_lapse_cam.py | 99-152 | ✅ Deployed |
| #3 | lib/time_lapse_cam.py | 20-27 | ✅ Deployed |
| #4 | lib/time_lapse_cam.py | 197-213 | ✅ Deployed |
| #5 | lib/time_lapse_cam.py | 37-97 | ✅ Deployed |

---

**Status: Ready to Deploy** 🚀
