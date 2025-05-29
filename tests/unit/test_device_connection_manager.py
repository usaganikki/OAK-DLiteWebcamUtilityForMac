import pytest
from unittest.mock import patch, MagicMock, call # Added call for checking call order if needed
import signal # For SIGINT
import os # For os.path.exists in start_camera_action
import subprocess # For subprocess.Popen and TimeoutExpired

# Modules to be tested
from src.device_connection_manager import DeviceConnectionManager, USBEventHandler, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID

# Path to the uvc_handler.py script for mocking os.path.exists
UVC_HANDLER_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(os.path.join(__file__, '../../../src'))), 'src', 'uvc_handler.py')


@pytest.fixture
def mock_ui_callbacks():
    """Fixture to create mock UI callback functions."""
    return {
        'notify_ui_callback': MagicMock(),
        'alert_ui_callback': MagicMock(),
        'update_menu_callback': MagicMock(),
        'update_status_label_callback': MagicMock(),
    }

@pytest.fixture
@patch('src.device_connection_manager.iokit_wrapper', autospec=True)
def mock_iokit_wrapper(mock_iokit_wrapper_module, mock_ui_callbacks):
    """Fixture to create a DeviceConnectionManager with a mocked iokit_wrapper and UI callbacks."""
    # Configure the mock iokit_wrapper behavior needed for DCM initialization
    mock_iokit_wrapper_module.init_usb_monitoring.return_value = 12345 # Mock run_loop_source_addr
    
    manager = DeviceConnectionManager(
        notify_ui_callback=mock_ui_callbacks['notify_ui_callback'],
        alert_ui_callback=mock_ui_callbacks['alert_ui_callback'],
        update_menu_callback=mock_ui_callbacks['update_menu_callback'],
        update_status_label_callback=mock_ui_callbacks['update_status_label_callback']
    )
    # Allow access to the mocked iokit_wrapper module through the manager if needed, or return it separately
    manager.mock_iokit_wrapper_module = mock_iokit_wrapper_module 
    return manager, mock_ui_callbacks, mock_iokit_wrapper_module


class TestDeviceConnectionManager:
    def test_dcm_initialization(self, mock_iokit_wrapper):
        """Test the initialization of DeviceConnectionManager."""
        manager, ui_callbacks, iokit_mock = mock_iokit_wrapper

        assert manager.uvc_process is None
        assert not manager.camera_running
        assert manager.auto_mode_enabled  # Default based on current implementation
        assert manager.connected_target_device_info is None
        
        iokit_mock.init_usb_monitoring.assert_called_once_with(
            manager._event_handler, 
            OAK_D_LITE_VENDOR_ID, 
            OAK_D_LITE_PRODUCT_ID
        )
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし") # Initial status update

    def test_get_run_loop_source_address(self, mock_iokit_wrapper):
        """Test retrieval of the run loop source address."""
        manager, _, iokit_mock = mock_iokit_wrapper
        iokit_mock.init_usb_monitoring.return_value = 12345
        # Re-initialize or assume the fixture's init is sufficient.
        # For this test, we just need to ensure the value from init_usb_monitoring is returned.
        # If DCM is re-initialized in the fixture every time, this check is implicitly covered.
        # However, if init_usb_monitoring was called in the fixture, we can check the stored value.
        # Re-calling _start_iokit_monitoring or checking the result of get_run_loop_source_address
        
        # If the fixture already initialized the manager, then _run_loop_source_addr is set.
        assert manager.get_run_loop_source_address() == 12345

        # Test case where init_usb_monitoring fails (returns 0)
        iokit_mock.init_usb_monitoring.return_value = 0
        # We need a fresh manager for this, or to re-trigger _start_iokit_monitoring
        temp_manager = DeviceConnectionManager(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        assert temp_manager.get_run_loop_source_address() == 0
        # Check if alert was called (depends on how _start_iokit_monitoring handles this)
        # This might require the alert_ui_callback to be passed to this temp_manager
        

    def test_toggle_auto_mode_enable(self, mock_iokit_wrapper):
        """Test enabling auto mode."""
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = False # Start with it disabled

        manager.toggle_auto_mode()

        assert manager.auto_mode_enabled
        ui_callbacks['update_menu_callback'].assert_called_once_with(True)
        ui_callbacks['notify_ui_callback'].assert_called_with(
            "OAK-D Auto Control", "Setting Changed", "Auto Camera Control has been enabled."
        )
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし") # Assuming no device connected initially

    def test_toggle_auto_mode_disable_camera_running(self, mock_iokit_wrapper):
        """Test disabling auto mode when the camera is running."""
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = True
        manager.camera_running = True # Simulate camera running
        manager.uvc_process = MagicMock() # Simulate a running process

        with patch.object(manager, 'stop_camera_action', wraps=manager.stop_camera_action) as mock_stop_camera:
            manager.toggle_auto_mode()

            assert not manager.auto_mode_enabled
            ui_callbacks['update_menu_callback'].assert_called_with(False)
            ui_callbacks['notify_ui_callback'].assert_any_call( # Using any_call due to multiple calls
                "OAK-D Auto Control", "Setting Changed", "Auto Camera Control has been disabled."
            )
            mock_stop_camera.assert_called_once()
            # Status label update will be checked in stop_camera_action tests

    # More tests to be added here for:
    # - toggle_auto_mode (when device connected, camera not running -> starts camera)
    # - disconnect_camera_explicitly (auto_mode on/off, camera on/off)
    # - start_camera_action (success, script_not_found, subprocess_error)
    # - stop_camera_action (success, timeout, general_error, no_process)
    # - cleanup_on_quit
    # - USBEventHandler.on_device_connected (target device, other device, auto_mode on/off)
    # - USBEventHandler.on_device_disconnected (target device, other device, camera running)

    @patch('src.device_connection_manager.subprocess.Popen')
    @patch('src.device_connection_manager.os.path.exists')
    def test_start_camera_action_success(self, mock_exists, mock_popen, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        mock_exists.return_value = True
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        manager.start_camera_action()

        mock_exists.assert_called_once_with(UVC_HANDLER_SCRIPT_PATH)
        mock_popen.assert_called_once_with(['python3', UVC_HANDLER_SCRIPT_PATH, '--start-uvc'])
        assert manager.camera_running
        assert manager.uvc_process == mock_proc
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Camera", "Status", "Camera starting...")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続中")

    @patch('src.device_connection_manager.os.path.exists')
    def test_start_camera_action_script_not_found(self, mock_exists, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        mock_exists.return_value = False

        manager.start_camera_action()

        assert not manager.camera_running
        assert manager.uvc_process is None
        ui_callbacks['alert_ui_callback'].assert_called_once_with("Error", f"uvc_handler.py not found at {UVC_HANDLER_SCRIPT_PATH}")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    @patch('src.device_connection_manager.subprocess.Popen')
    @patch('src.device_connection_manager.os.path.exists')
    def test_start_camera_action_subprocess_error(self, mock_exists, mock_popen, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        mock_exists.return_value = True
        mock_popen.side_effect = Exception("Popen failed")

        manager.start_camera_action()

        assert not manager.camera_running
        assert manager.uvc_process is None
        ui_callbacks['alert_ui_callback'].assert_called_once_with("Error Starting Camera", "Popen failed")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")

    def test_stop_camera_action_success(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = True
        mock_proc = MagicMock()
        manager.uvc_process = mock_proc

        manager.stop_camera_action()

        mock_proc.send_signal.assert_called_once_with(signal.SIGINT)
        mock_proc.wait.assert_called_once_with(timeout=10)
        assert not manager.camera_running
        assert manager.uvc_process is None
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Camera", "Status", "Camera stopped.")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_stop_camera_action_timeout(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = True
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="uvc_handler", timeout=10)
        manager.uvc_process = mock_proc

        manager.stop_camera_action()
        
        mock_proc.send_signal.assert_called_once_with(signal.SIGINT)
        mock_proc.terminate.assert_called_once() # Ensure terminate is called on timeout
        ui_callbacks['alert_ui_callback'].assert_called_with("Stopping camera timed out.", "Forcing termination.")
        assert not manager.camera_running
        assert manager.uvc_process is None
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")

    def test_stop_camera_action_general_error(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = True
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = Exception("Wait failed") # Simulate general error
        manager.uvc_process = mock_proc

        manager.stop_camera_action()

        mock_proc.send_signal.assert_called_once_with(signal.SIGINT)
        ui_callbacks['alert_ui_callback'].assert_called_with("Error Stopping Camera", "Wait failed")
        assert not manager.camera_running # Should still reset state
        assert manager.uvc_process is None
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_stop_camera_action_no_process(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = True # Marked as running
        manager.uvc_process = None    # But no process

        manager.stop_camera_action()
        
        assert not manager.camera_running # Should be reset
        # No notification if no process was there to stop, but status label updates
        ui_callbacks['notify_ui_callback'].assert_not_called() 
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")

    def test_stop_camera_action_already_stopped(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = False # Already stopped
        manager.uvc_process = None

        manager.stop_camera_action()
        
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Camera", "Status", "Camera is already stopped.")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_cleanup_on_quit_camera_running(self, mock_iokit_wrapper):
        manager, _, iokit_mock = mock_iokit_wrapper
        manager.camera_running = True
        manager.uvc_process = MagicMock() # Simulate process

        with patch.object(manager, 'stop_camera_action', wraps=manager.stop_camera_action) as mock_stop_camera:
            manager.cleanup_on_quit()
            mock_stop_camera.assert_called_once()
        
        iokit_mock.stop_usb_monitoring.assert_called_once()


    def test_cleanup_on_quit_camera_not_running(self, mock_iokit_wrapper):
        manager, _, iokit_mock = mock_iokit_wrapper
        manager.camera_running = False

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            manager.cleanup_on_quit()
            mock_stop_camera.assert_not_called()

        iokit_mock.stop_usb_monitoring.assert_called_once()

    def test_dcm_initialization_iokit_failure(self, mock_ui_callbacks):
        """Test DCM initialization when iokit_wrapper.init_usb_monitoring fails."""
        with patch('src.device_connection_manager.iokit_wrapper', autospec=True) as iokit_mock_fail:
            iokit_mock_fail.init_usb_monitoring.return_value = 0 # Simulate failure
            
            manager = DeviceConnectionManager(
                notify_ui_callback=mock_ui_callbacks['notify_ui_callback'],
                alert_ui_callback=mock_ui_callbacks['alert_ui_callback'],
                update_menu_callback=mock_ui_callbacks['update_menu_callback'],
                update_status_label_callback=mock_ui_callbacks['update_status_label_callback']
            )
            
            assert manager._run_loop_source_addr == 0
            mock_ui_callbacks['alert_ui_callback'].assert_called_once()
            args, _ = mock_ui_callbacks['alert_ui_callback'].call_args
            assert args[0] == "IOKit Initialization Error"
            mock_ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_disconnect_camera_explicitly_auto_mode_on_camera_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = True
        manager.camera_running = True
        manager.uvc_process = MagicMock()

        with patch.object(manager, 'stop_camera_action', wraps=manager.stop_camera_action) as mock_stop_camera:
            manager.disconnect_camera_explicitly()

        assert not manager.auto_mode_enabled # Auto mode should be disabled
        ui_callbacks['update_menu_callback'].assert_called_with(False)
        ui_callbacks['notify_ui_callback'].assert_any_call("OAK-D Auto Control", "Disabled", "Auto-mode disabled due to manual disconnect.")
        mock_stop_camera.assert_called_once()
        ui_callbacks['notify_ui_callback'].assert_any_call("OAK-D Camera", "Disconnected", "Camera has been manually disconnected.")
        # stop_camera_action will call update_status_label_callback

    def test_disconnect_camera_explicitly_auto_mode_off_camera_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = False # Auto mode already off
        manager.camera_running = True
        manager.uvc_process = MagicMock()

        with patch.object(manager, 'stop_camera_action', wraps=manager.stop_camera_action) as mock_stop_camera:
            manager.disconnect_camera_explicitly()

        assert not manager.auto_mode_enabled # Stays disabled
        # update_menu_callback should not be called if auto_mode was already false
        ui_callbacks['update_menu_callback'].assert_not_called()
        mock_stop_camera.assert_called_once()
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Camera", "Disconnected", "Camera has been manually disconnected.")


    def test_disconnect_camera_explicitly_camera_not_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = False

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            manager.disconnect_camera_explicitly()
        
        mock_stop_camera.assert_not_called() # stop_camera should not be called if not running
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Camera", "Status", "Camera is not currently running.")
        # No change in status label if already "接続なし" (assuming initial state or after a stop)
        # If it could be "接続中" then a call to "接続なし" would be expected.
        # Let's ensure the label reflects the "not running" state.
        manager._update_status_label_based_on_state() # Manually trigger for this check if disconnect doesn't
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_toggle_auto_mode_enable_device_connected_camera_not_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = False
        manager.connected_target_device_info = {'serial_number': 'test-sn', 'vendor_id': OAK_D_LITE_VENDOR_ID, 'product_id': OAK_D_LITE_PRODUCT_ID} # Simulate device connected
        manager.camera_running = False

        with patch.object(manager, 'start_camera_action', wraps=manager.start_camera_action) as mock_start_camera:
            manager.toggle_auto_mode()
        
        assert manager.auto_mode_enabled
        mock_start_camera.assert_called_once()
        ui_callbacks['notify_ui_callback'].assert_any_call("OAK-D Auto Control", "Setting Changed", "Auto Camera Control has been enabled.")
        ui_callbacks['notify_ui_callback'].assert_any_call("OAK-D Auto Control", "Starting Camera", "Device already connected, auto-starting camera.")
        # start_camera_action will call update_status_label_callback

    def test_toggle_auto_mode_enable_device_not_connected(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.auto_mode_enabled = False
        manager.connected_target_device_info = None # No device
        manager.camera_running = False

        with patch.object(manager, 'start_camera_action') as mock_start_camera:
            manager.toggle_auto_mode()
        
        assert manager.auto_mode_enabled
        mock_start_camera.assert_not_called() # Should not start if no device
        ui_callbacks['notify_ui_callback'].assert_called_with("OAK-D Auto Control", "Setting Changed", "Auto Camera Control has been enabled.")
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_update_status_label_camera_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = True
        manager._update_status_label_based_on_state()
        ui_callbacks['update_status_label_callback'].assert_called_with("接続中")

    def test_update_status_label_camera_not_running(self, mock_iokit_wrapper):
        manager, ui_callbacks, _ = mock_iokit_wrapper
        manager.camera_running = False
        manager._update_status_label_based_on_state()
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


@pytest.fixture
def manager_with_event_handler(mock_ui_callbacks):
    """Fixture to create a DeviceConnectionManager and its USBEventHandler instance."""
    # Mock iokit_wrapper for this specific fixture if its calls during init are not desired
    with patch('src.device_connection_manager.iokit_wrapper', autospec=True) as mock_iokit:
        mock_iokit.init_usb_monitoring.return_value = 123 # Dummy run loop source
        manager = DeviceConnectionManager(**mock_ui_callbacks)
        event_handler = manager._event_handler 
        # Store mock_iokit on manager if needed for assertions about its usage during event handling
        manager.mock_iokit = mock_iokit 
        return manager, event_handler, mock_ui_callbacks

class TestUSBEventHandler:
    TARGET_SN = "test-sn-123"
    TARGET_SERVICE_ID = 123456789

    def test_on_device_connected_target_device_auto_mode_on(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.auto_mode_enabled = True
        manager.camera_running = False

        with patch.object(manager, 'start_camera_action') as mock_start_camera:
            handler.on_device_connected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID)

        assert manager.connected_target_device_info == {
            'vendor_id': OAK_D_LITE_VENDOR_ID,
            'product_id': OAK_D_LITE_PRODUCT_ID,
            'serial_number': self.TARGET_SN,
            'service_id': self.TARGET_SERVICE_ID
        }
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Status", "Device Connected", f"OAK-D Lite (SN: {self.TARGET_SN}) detected."
        )
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Auto Control", "Starting Camera", "Device connected, auto-starting camera."
        )
        mock_start_camera.assert_called_once()
        # Status label is updated by start_camera_action

    def test_on_device_connected_target_device_auto_mode_on_camera_already_running(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.auto_mode_enabled = True
        manager.camera_running = True # Camera already running
        # Simulate a different device was connected previously, or no device
        manager.connected_target_device_info = None 

        with patch.object(manager, 'start_camera_action') as mock_start_camera:
            handler.on_device_connected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID)

        assert manager.connected_target_device_info is not None # Should be updated
        # Notification about connection
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Status", "Device Connected", f"OAK-D Lite (SN: {self.TARGET_SN}) detected."
        )
        # Should not try to start camera if already running
        mock_start_camera.assert_not_called()
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Auto Control", "Info", "Camera already running or starting."
        )
        # Status label should reflect "接続中" if camera_running is true
        manager._update_status_label_based_on_state() # Ensure it's called or check last call
        ui_callbacks['update_status_label_callback'].assert_called_with("接続中")


    def test_on_device_connected_target_device_auto_mode_off(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.auto_mode_enabled = False
        manager.camera_running = False

        with patch.object(manager, 'start_camera_action') as mock_start_camera:
            handler.on_device_connected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID)

        assert manager.connected_target_device_info is not None # Check it's populated
        mock_start_camera.assert_not_called()
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Status", "Device Connected", f"OAK-D Lite (SN: {self.TARGET_SN}) detected."
        )
        # Check that "Starting camera" notification was NOT called
        called_start_camera_notification = any(
            call_arg[0][0] == "OAK-D Auto Control" and call_arg[0][1] == "Starting Camera"
            for call_arg in ui_callbacks['notify_ui_callback'].call_args_list
        )
        assert not called_start_camera_notification
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_on_device_connected_other_device(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.connected_target_device_info = {"sn": "some-other-oak"} # Pre-existing OAK
        
        with patch.object(manager, 'start_camera_action') as mock_start_camera:
            handler.on_device_connected(0x1234, 0x5678, "other-device-sn", 98765) # Non-OAK device

        assert manager.connected_target_device_info == {"sn": "some-other-oak"} # Should not change
        mock_start_camera.assert_not_called()
        
        # Check that no "Device Connected" for OAK-D Lite was sent for THIS device
        oak_connected_notification_for_other_device = any(
            call_arg[0][0] == "OAK-D Status" and "OAK-D Lite" in call_arg[0][2] and "other-device-sn" in call_arg[0][2]
            for call_arg in ui_callbacks['notify_ui_callback'].call_args_list
        )
        assert not oak_connected_notification_for_other_device
        # Status label should reflect the state of "some-other-oak" if that logic exists, or "接続なし" / "接続中" based on camera_running
        # For this test, assume no change triggered by non-target device connection if one is already connected.
        # If no OAK was connected, it should remain "接続なし".
        # Let's assume initial state for label was "接続なし" and camera not running.
        manager.camera_running = False 
        manager.connected_target_device_info = None # Reset for this check
        handler.on_device_connected(0x1234, 0x5678, "other-device-sn", 98765)
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_on_device_disconnected_target_device_camera_running(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.camera_running = True
        manager.connected_target_device_info = { # Simulate it was our device
            'vendor_id': OAK_D_LITE_VENDOR_ID,
            'product_id': OAK_D_LITE_PRODUCT_ID,
            'serial_number': self.TARGET_SN,
            'service_id': self.TARGET_SERVICE_ID
        }

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            handler.on_device_disconnected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID)

        assert manager.connected_target_device_info is None
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Status", "Device Disconnected", f"OAK-D Lite (SN: {self.TARGET_SN}) disconnected."
        )
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Control", "Stopping Camera", "Device disconnected, stopping camera."
        )
        mock_stop_camera.assert_called_once()
        # stop_camera_action updates status label

    def test_on_device_disconnected_target_device_camera_not_running(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.camera_running = False # Camera not running
        manager.connected_target_device_info = { 
            'vendor_id': OAK_D_LITE_VENDOR_ID, 
            'product_id': OAK_D_LITE_PRODUCT_ID, 
            'serial_number': self.TARGET_SN,
            'service_id': self.TARGET_SERVICE_ID
        }

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            handler.on_device_disconnected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID)

        assert manager.connected_target_device_info is None # Info cleared
        ui_callbacks['notify_ui_callback'].assert_any_call(
            "OAK-D Status", "Device Disconnected", f"OAK-D Lite (SN: {self.TARGET_SN}) disconnected."
        )
        # "Stopping camera" notification should NOT be sent if camera wasn't running
        stopping_camera_notification = any(
            call_arg[0][0] == "OAK-D Control" and call_arg[0][1] == "Stopping Camera"
            for call_arg in ui_callbacks['notify_ui_callback'].call_args_list
        )
        assert not stopping_camera_notification
        mock_stop_camera.assert_not_called() # Stop action should not be called
        ui_callbacks['update_status_label_callback'].assert_called_with("接続なし")


    def test_on_device_disconnected_target_device_mismatched_service_id(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.camera_running = True 
        # Connected device has a specific service_id
        current_device_info = {
            'vendor_id': OAK_D_LITE_VENDOR_ID,
            'product_id': OAK_D_LITE_PRODUCT_ID,
            'serial_number': self.TARGET_SN, # Same SN for simplicity
            'service_id': self.TARGET_SERVICE_ID 
        }
        manager.connected_target_device_info = current_device_info.copy()

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            # A device with same VID/PID/SN disconnects, but it has a DIFFERENT service_id in the event
            handler.on_device_disconnected(OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, self.TARGET_SN, self.TARGET_SERVICE_ID + 1)

        # The stored info should NOT be cleared because the service_id from the event does not match stored one
        assert manager.connected_target_device_info == current_device_info 
        # Stop camera should NOT be called if the specific service_id instance is not the one disconnecting
        mock_stop_camera.assert_not_called() 
        # Disconnect notification for the specific disconnecting service_id (even if not our primary) might occur
        # but the main state (connected_target_device_info, camera_running for that device) should be unaffected.
        # Check that "Device Disconnected" for the *stored* SN was NOT called IF service_id mismatch means "it's not our active one"
        # This depends on the exact logic: does it notify for any OAK-D disconnect by VID/PID/SN, or only the one matching service_id?
        # Current code: `if self.manager.is_target_device(vendor_id, product_id, serial_number, service_id):`
        # This line implies that the service_id from the event must match the stored one for it to be considered "our" device disconnecting.
        
        # So, no "Device Disconnected" for the stored SN, and no "Stopping Camera"
        device_disconnected_notification_for_stored_sn = any(
            call_arg[0][0] == "OAK-D Status" and f"SN: {self.TARGET_SN}" in call_arg[0][2] and call_arg[0][1] == "Device Disconnected"
            for call_arg in ui_callbacks['notify_ui_callback'].call_args_list
        )
        assert not device_disconnected_notification_for_stored_sn

        stopping_camera_notification = any(
            call_arg[0][0] == "OAK-D Control" and call_arg[0][1] == "Stopping Camera"
            for call_arg in ui_callbacks['notify_ui_callback'].call_args_list
        )
        assert not stopping_camera_notification
        # Status label should remain "接続中" as our target device is still considered connected and camera running
        manager._update_status_label_based_on_state()
        ui_callbacks['update_status_label_callback'].assert_called_with("接続中")


    def test_on_device_disconnected_other_device(self, manager_with_event_handler):
        manager, handler, ui_callbacks = manager_with_event_handler
        manager.connected_target_device_info = { # Simulate OAK-D is connected
            'vendor_id': OAK_D_LITE_VENDOR_ID,
            'product_id': OAK_D_LITE_PRODUCT_ID,
            'serial_number': self.TARGET_SN,
            'service_id': self.TARGET_SERVICE_ID
        }
        original_info = manager.connected_target_device_info.copy()

        with patch.object(manager, 'stop_camera_action') as mock_stop_camera:
            handler.on_device_disconnected(0x9999, 0x8888, "other-sn", 11111)
        
        assert manager.connected_target_device_info == original_info # Should not be cleared
        mock_stop_camera.assert_not_called() # Should not stop if a non-target device disconnected
        # Status label should reflect that the original OAK-D is still connected and camera running (if it was)
        # For this test, let's assume camera was running with the original_info device
        manager.camera_running = True # if it was
        manager._update_status_label_based_on_state()
        ui_callbacks['update_status_label_callback'].assert_called_with("接続中")
