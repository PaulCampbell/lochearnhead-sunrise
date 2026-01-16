# Architecture & Design Recommendations

## Current Architecture

```
main.py
  └─ TimeLapseCam (time_lapse_cam.py)
      ├─ WifiManager (wifimgr.py)
      │   └─ MicroDNSSrv (microDNSSrv.py) [Captive Portal]
      ├─ IotManagerClient (iot_manager_client.py)
      │   └─ OTAUpdater [Firmware Updates]
      └─ camera module (MicroPython built-in)
```

## Issues with Current Architecture

### 1. **Tight Coupling**
- `TimeLapseCam` directly instantiates dependencies
- Hard to test individual components
- Difficult to swap implementations

**Current:**
```python
class TimeLapseCam:
    def __init__(self, iot_manager_base_url, device_id, device_password):
        self.client = IotManagerClient(base_url=self.iot_manager_base_url)
        self.wifi_manager = WifiManager(ssid='sunrise-cam', password='', authmode=0)
```

**Better (Dependency Injection):**
```python
class TimeLapseCam:
    def __init__(self, 
                 iot_manager_base_url,
                 device_id,
                 device_password,
                 iot_client=None,
                 wifi_manager=None):
        self.iot_manager_base_url = iot_manager_base_url
        self.device_id = device_id
        self.device_password = device_password
        
        # Allow injection for testing
        self.client = iot_client or IotManagerClient(base_url=iot_manager_base_url)
        self.wifi_manager = wifi_manager or WifiManager(ssid='sunrise-cam', password='', authmode=0)
```

---

### 2. **No State Management**
Currently, device state is local to method execution. No persistent state tracking for:
- Boot count
- Last successful upload time
- WiFi failure count
- Camera initialization failures
- Firmware version history

**Recommendation: Create a DeviceState class**

```python
class DeviceState:
    """Persistent device state manager."""
    
    def __init__(self, state_file='device_state.json'):
        self.state_file = state_file
        self.state = self._load()
    
    def _load(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.loads(f.read())
        except OSError:
            return self._default_state()
    
    def _default_state(self):
        return {
            'boot_count': 0,
            'last_upload_time': 0,
            'last_upload_success': False,
            'wifi_failures': 0,
            'camera_failures': 0,
            'firmware_version': None,
            'last_error': None,
            'last_error_time': 0,
        }
    
    def save(self):
        try:
            with open(self.state_file, 'w') as f:
                f.write(json.dumps(self.state))
        except Exception as e:
            print(f"Warning: Could not save device state: {e}")
    
    def increment_boot_count(self):
        self.state['boot_count'] += 1
        self.save()
    
    def record_upload_success(self):
        self.state['last_upload_time'] = time.time()
        self.state['last_upload_success'] = True
        self.state['wifi_failures'] = 0  # Reset on success
        self.save()
    
    def record_upload_failure(self, error_msg=None):
        self.state['last_upload_success'] = False
        self.state['last_error'] = error_msg
        self.state['last_error_time'] = time.time()
        self.save()
```

---

### 3. **Error Handling is Inconsistent**
- Mix of exceptions and return values
- Some errors silently ignored
- No centralized error logging

**Recommendation: Create standardized error handling**

```python
class TimeLapseCamError(Exception):
    """Base error class."""
    pass

class WiFiError(TimeLapseCamError):
    """WiFi connection failed."""
    pass

class CameraError(TimeLapseCamError):
    """Camera operation failed."""
    pass

class UploadError(TimeLapseCamError):
    """Image upload failed."""
    pass

class ConfigError(TimeLapseCamError):
    """Configuration retrieval failed."""
    pass

# Usage in main flow
def main(self):
    try:
        self.state.increment_boot_count()
        
        try:
            wlan = self.connect_wifi(enter_captive_portal_if_needed=allow_captive_portal)
        except WiFiError as e:
            self.state.record_error(f"WiFi error: {e}")
            print(f"WiFi connection failed: {e}")
            machine.deepsleep(60 * 60 * 1000)  # Retry after 1 hour
        
        try:
            config = self.fetch_config()
        except ConfigError as e:
            self.state.record_error(f"Config error: {e}")
            config = None  # Use defaults
        
        try:
            success = self.take_photo(weather_condition, test_post)
            if success:
                self.state.record_upload_success()
            else:
                self.state.record_upload_failure("Photo capture failed")
        except (CameraError, UploadError) as e:
            self.state.record_upload_failure(str(e))
            print(f"Upload failed: {e}")
    
    except Exception as e:
        print(f"Unhandled error in main: {e}")
        import traceback
        traceback.print_exc()
        machine.reset()
```

---

### 4. **Configuration is Spread Across Multiple Files**
- Camera settings hardcoded in `take_photo()`
- WiFi AP settings hardcoded in `__init__()`
- Network timeout hardcoded in `IotManagerClient`

**Recommendation: Create centralized config**

```python
# config.py
DEFAULT_CONFIG = {
    'wifi': {
        'ap_ssid': 'sunrise-cam',
        'ap_password': '',
        'ap_authmode': 0,  # Open
        'connection_timeout_s': 20,
    },
    'camera': {
        'init_delay_s': 1.2,
        'contrast': 1,
        'saturation': -1,
        'framesize': 'QXGA',
        'quality': 80,
        'wb_modes': {
            'sunny': 'WB_SUNNY',
            'cloudy': 'WB_CLOUDY',
            'overcast': 'WB_CLOUDY',
        },
    },
    'network': {
        'timeout_s': 10,
        'ntp_sync_retries': 3,
    },
    'firmware': {
        'check_interval_s': 3600,  # Check every hour
        'update_timeout_s': 120,
    },
    'wakeup': {
        'default_interval_ms': 24 * 60 * 60 * 1000,
        'min_interval_ms': 1 * 60 * 1000,
        'max_interval_ms': 48 * 60 * 60 * 1000,
    },
}
```

---

### 5. **No Health Monitoring**
Currently, if something goes wrong, it's only visible via serial connection.

**Recommendation: Add health check endpoint**

```python
class DeviceHealth:
    """Track device health metrics."""
    
    def __init__(self):
        self.metrics = {
            'uptime_s': 0,
            'resets': 0,
            'wifi_failures': 0,
            'camera_failures': 0,
            'uploads': 0,
            'successful_uploads': 0,
            'battery_voltage': 0,
            'last_error': None,
        }
    
    def get_health_status(self):
        """Return health status for server reporting."""
        uptime = time.time()
        upload_success_rate = (
            self.metrics['successful_uploads'] / self.metrics['uploads'] * 100
            if self.metrics['uploads'] > 0 else 0
        )
        
        return {
            'status': 'healthy' if upload_success_rate > 80 else 'degraded',
            'uptime_s': uptime,
            'upload_success_rate': upload_success_rate,
            'wifi_failures': self.metrics['wifi_failures'],
            'camera_failures': self.metrics['camera_failures'],
            'last_error': self.metrics['last_error'],
        }
```

---

## Proposed New Architecture

```
main.py
  └─ App
      ├─ Config (config.py) ───┐
      ├─ DeviceState (state.py) ├─ Shared
      ├─ DeviceHealth (health.py) ┤
      └─ TimeLapseCam           │
          ├─ WifiManager        │
          ├─ IotManagerClient   ├─ Uses config
          └─ CameraManager      │
```

### Key Improvements

1. **Separation of Concerns**
   - Config: all settings in one place
   - State: persistent device state
   - Health: metrics and diagnostics
   - Camera: dedicated camera handler

2. **Easier Testing**
   - Can mock dependencies
   - Can test individual components
   - Easier to add unit tests

3. **Better Observability**
   - Device state visible at any time
   - Health metrics sendable to server
   - Centralized error logging

4. **Configuration Flexibility**
   - Can load config from server
   - Can override via environment
   - Can change at runtime (sort of)

---

## Suggested File Structure After Refactoring

```
time-lapse-cam/
├── main.py                 # Entry point, minimal
├── lib/
│   ├── __init__.py
│   ├── app.py             # Main application class
│   ├── config.py          # Configuration management
│   ├── device_state.py    # Persistent state
│   ├── device_health.py   # Health metrics
│   ├── time_lapse_cam.py  # Core logic (refactored)
│   ├── iot_manager_client.py
│   ├── wifi_manager.py
│   ├── camera_manager.py  # NEW: Dedicated camera handling
│   ├── logger.py          # NEW: Centralized logging
│   ├── errors.py          # NEW: Custom exception types
│   ├── wifimgr.py         # Keep for compatibility
│   ├── microDNSSrv.py
│   ├── wifi_portal_template.py
│   └── utarfile.py
├── tests/                 # NEW: Unit tests
│   ├── test_config.py
│   ├── test_state.py
│   └── test_time_lapse_cam.py
├── environment.py
├── environment.example.py
├── requirements.txt
├── README.md
├── IMPROVEMENT_SUGGESTIONS.md
└── ARCHITECTURE.md        # This document
```

---

## Migration Path

### Phase 1: Non-Breaking Refactoring (Week 1)
- [ ] Create `config.py` with DEFAULT_CONFIG
- [ ] Create `errors.py` with exception types
- [ ] Create `device_state.py` for state management
- [ ] Create `logger.py` for centralized logging
- [ ] Update `time_lapse_cam.py` to use new modules
- [ ] **No breaking changes to `main.py`**

### Phase 2: Enhanced Features (Week 2)
- [ ] Create `device_health.py`
- [ ] Create `camera_manager.py`
- [ ] Add health endpoint to `IotManagerClient`
- [ ] Add tests for core functionality

### Phase 3: Polish (Week 3+)
- [ ] Add documentation
- [ ] Performance optimization
- [ ] Memory profiling
- [ ] Battery life optimization

---

## Testing Strategy

### Unit Tests (Offline)
```python
# tests/test_config.py
def test_default_config_is_valid():
    config = DEFAULT_CONFIG
    assert 'wifi' in config
    assert 'camera' in config
    assert config['wakeup']['min_interval_ms'] > 0

# tests/test_state.py
def test_device_state_persists():
    state = DeviceState()
    state.increment_boot_count()
    state.save()
    
    state2 = DeviceState()
    assert state2.state['boot_count'] == state.state['boot_count']
```

### Integration Tests (With Mock Server)
```python
# tests/test_time_lapse_cam.py
def test_wifi_failure_triggers_sleep():
    config = DEFAULT_CONFIG
    mock_wifi = MockWifiManager(should_fail=True)
    app = TimeLapseCam(..., wifi_manager=mock_wifi)
    
    with pytest.raises(WiFiError):
        app.connect_wifi()
```

### Device Tests (On Hardware)
- Manual testing with debug REPL
- Capture device logs during operation
- Verify wake times match server config

---

## Performance Considerations

### Memory Usage
- ESP32 typically has 520KB SRAM
- Current code likely uses ~100-150KB during execution
- Large JPEG images (500KB+) must be streamed, not buffered

**Mitigation:**
```python
# Don't load entire image in memory
def upload_image_chunked(self, image_path, chunk_size=4096):
    """Upload image in chunks to avoid memory issues."""
    with open(image_path, 'rb') as f:
        # Use chunked upload
        pass
```

### Power Consumption
- Deep sleep: ~10-20 mA
- WiFi connect: ~150 mA
- Camera capture: ~100-200 mA
- Typical cycle: 150ms (WiFi) + 500ms (capture) + 24h (sleep)

**Optimization:**
- Keep WiFi off during sleep ✓ (already done)
- Minimize time awake
- Use lower camera quality if bandwidth limited

### Startup Time
- Current: ~5-10 seconds to WiFi connection
- Goal: <3 seconds (to reduce power consumption)

**Improvement:**
- Cache last WiFi network
- Skip captive portal if WiFi available
- Pre-connect to WiFi before taking photo

---

## Reliability Improvements

### Watchdog Timer
```python
from machine import WDT

# Reset device if main loop blocked for >30 seconds
wdt = WDT(timeout=30000)

while True:
    wdt.feed()  # Reset watchdog
    # do work
```

### Graceful Degradation
```python
# Try to upload with photo
try:
    upload_photo()
except Exception:
    # Fallback: at least report that device is alive
    report_status_only()
    # Sleep and retry
    machine.deepsleep(30 * 60 * 1000)
```

### Circuit Breaker Pattern
```python
class CircuitBreaker:
    """Prevent repeated requests to failing endpoint."""
    
    def __init__(self, failure_threshold=3, timeout_s=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_s = timeout_s
        self.last_failure_time = 0
    
    def call(self, func, *args, **kwargs):
        if self.is_open():
            raise CircuitBreakerOpen("Circuit is open")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def is_open(self):
        if self.failure_count >= self.failure_threshold:
            if time.time() - self.last_failure_time > self.timeout_s:
                self.reset()
                return False
            return True
        return False
```

---

## Monitoring & Observability

### Metrics to Track
- WiFi connection success rate
- Photo capture success rate
- Upload success rate
- Average response times
- Firmware version
- Boot count
- Last error and timestamp
- Battery voltage (if ADC available)

### Server-Side Dashboard
The server should display:
```
Device: sunrise-cam-01
├─ Status: Healthy
├─ Last Contact: 5m ago
├─ Uptime: 47 days
├─ WiFi Success: 98%
├─ Upload Success: 96%
├─ Photos Taken: 47
├─ Latest Photo: 2026-01-16 06:23:14 UTC
├─ Firmware: v1.2.3
└─ Battery: 3.8V (76%)
```

---

## Summary

**High Priority:**
- [ ] Fix critical bugs (see QUICK_FIX_CHECKLIST.md)
- [ ] Add centralized error handling
- [ ] Improve logging

**Medium Priority:**
- [ ] Refactor for separation of concerns
- [ ] Add device state management
- [ ] Create comprehensive tests

**Nice to Have:**
- [ ] Circuit breaker for retries
- [ ] Watchdog timer support
- [ ] Battery voltage monitoring
- [ ] Server-side health dashboard
