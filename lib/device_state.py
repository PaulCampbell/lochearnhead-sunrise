"""
Device state management for the Time Lapse Camera firmware.

This module provides persistent state tracking across power cycles,
allowing the device to maintain history and status information.
"""

import json
import time
from lib.config import STATE_CONFIG


class DeviceState:
    """
    Manages persistent device state.
    
    Tracks:
    - Boot count (how many times device has restarted)
    - Last upload timestamp and result
    - Error history
    - WiFi connection statistics
    - Camera capture statistics
    """
    
    def __init__(self, state_file=None):
        """
        Initialize device state manager.
        
        Args:
            state_file (str): Path to state file (default: from config)
        """
        self.state_file = state_file or STATE_CONFIG.get('state_file', 'device_state.json')
        self.state = self._load_state()
        self._init_defaults()
    
    def _init_defaults(self):
        """Ensure all required state fields exist."""
        defaults = {
            'boot_count': 0,
            'first_boot_time': None,
            'last_boot_time': None,
            'last_upload_time': None,
            'last_upload_success': None,
            'error_count': 0,
            'last_error': None,
            'last_error_time': None,
            'wifi_failures': 0,
            'camera_failures': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'events': [],  # List of [timestamp, event_type, message]
        }
        
        # Add missing fields
        for key, default_value in defaults.items():
            if key not in self.state:
                self.state[key] = default_value
    
    def _load_state(self):
        """Load state from file."""
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"WARNING: Failed to load device state: {e}")
            return {}
    
    def _save_state(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f)
        except Exception as e:
            print(f"ERROR: Failed to save device state: {e}")
    
    def record_boot(self):
        """Record a device boot event."""
        current_time = time.time()
        self.state['last_boot_time'] = current_time
        
        if self.state['first_boot_time'] is None:
            self.state['first_boot_time'] = current_time
        
        self.state['boot_count'] = self.state.get('boot_count', 0) + 1
        self._record_event('boot', f"Device booted (count: {self.state['boot_count']})")
        self._save_state()
    
    def record_wifi_failure(self):
        """Record a WiFi connection failure."""
        self.state['wifi_failures'] = self.state.get('wifi_failures', 0) + 1
        self._record_event('wifi_failure', 'Failed to connect to WiFi')
        self._save_state()
    
    def record_wifi_success(self):
        """Record successful WiFi connection."""
        self._record_event('wifi_success', 'Connected to WiFi')
        self._save_state()
    
    def record_camera_failure(self):
        """Record a camera capture failure."""
        self.state['camera_failures'] = self.state.get('camera_failures', 0) + 1
        self._record_event('camera_failure', 'Failed to capture image')
        self._save_state()
    
    def record_camera_success(self, frame_size_bytes):
        """Record successful camera capture."""
        self._record_event('camera_success', f'Captured {frame_size_bytes} bytes')
        self._save_state()
    
    def record_upload_attempt(self, success, error_msg=None):
        """
        Record an upload attempt.
        
        Args:
            success (bool): Whether upload succeeded
            error_msg (str): Error message if failed
        """
        current_time = time.time()
        self.state['last_upload_time'] = current_time
        self.state['last_upload_success'] = success
        
        if success:
            self.state['successful_uploads'] = self.state.get('successful_uploads', 0) + 1
            self._record_event('upload_success', 'Image uploaded successfully')
        else:
            self.state['failed_uploads'] = self.state.get('failed_uploads', 0) + 1
            self.record_error(error_msg or 'Upload failed')
            self._record_event('upload_failure', error_msg or 'Upload failed')
        
        self._save_state()
    
    def record_error(self, error_msg, error_type='general'):
        """
        Record an error event.
        
        Args:
            error_msg (str): Error message
            error_type (str): Type of error (wifi, camera, network, etc)
        """
        current_time = time.time()
        self.state['error_count'] = self.state.get('error_count', 0) + 1
        self.state['last_error'] = error_msg
        self.state['last_error_time'] = current_time
        self._record_event(f'error_{error_type}', error_msg)
        self._save_state()
    
    def _record_event(self, event_type, message):
        """
        Record an event in the event log.
        
        Args:
            event_type (str): Type of event
            message (str): Event message
        """
        current_time = time.time()
        event = [current_time, event_type, message]
        
        if 'events' not in self.state:
            self.state['events'] = []
        
        self.state['events'].append(event)
        
        # Keep only recent events (last 50)
        max_events = 50
        if len(self.state['events']) > max_events:
            self.state['events'] = self.state['events'][-max_events:]
    
    def get_status(self):
        """
        Get comprehensive device status.
        
        Returns:
            dict: Device status information
        """
        uptime_s = None
        if self.state['last_boot_time']:
            uptime_s = time.time() - self.state['last_boot_time']
        
        return {
            'boot_count': self.state.get('boot_count', 0),
            'uptime_seconds': uptime_s,
            'last_upload_success': self.state.get('last_upload_success'),
            'successful_uploads': self.state.get('successful_uploads', 0),
            'failed_uploads': self.state.get('failed_uploads', 0),
            'error_count': self.state.get('error_count', 0),
            'wifi_failures': self.state.get('wifi_failures', 0),
            'camera_failures': self.state.get('camera_failures', 0),
            'last_error': self.state.get('last_error'),
        }
    
    def get_status_json(self):
        """Get status as JSON string (for transmission to server)."""
        return json.dumps(self.get_status())
    
    def get_recent_events(self, count=20):
        """
        Get recent events.
        
        Args:
            count (int): Number of recent events to return
        
        Returns:
            list: List of [timestamp, event_type, message] events
        """
        events = self.state.get('events', [])
        if count > 0:
            return events[-count:]
        return events
    
    def get_recent_events_json(self, count=20):
        """Get recent events as JSON string."""
        return json.dumps(self.get_recent_events(count=count))
    
    def get_error_log(self, count=10):
        """
        Get recent errors.
        
        Args:
            count (int): Number of recent errors to return
        
        Returns:
            list: List of error events
        """
        events = self.state.get('events', [])
        errors = [e for e in events if 'error' in e[1]]
        if count > 0:
            return errors[-count:]
        return errors
    
    def reset_error_count(self):
        """Reset error counter."""
        self.state['error_count'] = 0
        self._save_state()
    
    def reset_all(self):
        """Reset all state (careful!)."""
        self.state = {}
        self._init_defaults()
        self._save_state()
    
    def export_state(self):
        """
        Export complete state for debugging.
        
        Returns:
            dict: Complete state
        """
        return json.loads(json.dumps(self.state))


# Global device state instance
_device_state = None


def init_device_state(state_file=None):
    """
    Initialize the global device state manager.
    
    Args:
        state_file (str): Path to state file
    
    Returns:
        DeviceState: The initialized state manager
    """
    global _device_state
    _device_state = DeviceState(state_file=state_file)
    return _device_state


def get_device_state():
    """
    Get the global device state manager.
    
    Returns:
        DeviceState: The state manager instance
    
    Raises:
        RuntimeError: If state manager not initialized
    """
    global _device_state
    if _device_state is None:
        _device_state = DeviceState()
    return _device_state
