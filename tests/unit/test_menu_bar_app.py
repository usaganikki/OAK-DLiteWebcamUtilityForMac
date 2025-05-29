import pytest
from unittest.mock import patch, MagicMock, ANY
import sys

# Temporarily add src to sys.path for direct import if tests are run from top-level
# This might be needed if 'src' is not installed as a package in the test environment
# For a robust setup, consider using a proper python package structure or tox/nox.
# However, for this task, direct path manipulation is simpler.
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Modules to be tested
# Need to handle the 'from .device_connection_manager import DeviceConnectionManager'
# If 'src' is treated as a package, this should work if tests are run with 'python -m pytest' from root
# Or if __init__.py in tests allows relative imports to src.
# For now, assuming src.module can be imported.
from src.menu_bar_app import MenuBarApp
# Mocked dependencies
# import rumps # Will be mocked
# from src.device_connection_manager import DeviceConnectionManager # Will be mocked
# from src import iokit_wrapper # Will be mocked


# It's often better to patch specific modules where they are LOOKED UP, not where they are defined.
# So, if MenuBarApp imports 'rumps', we patch 'src.menu_bar_app.rumps'.
# Same for DeviceConnectionManager and iokit_wrapper if they are imported into menu_bar_app.py.

@pytest.fixture
def mock_rumps():
    """Mocks the entire rumps module and its relevant classes/functions."""
    mock = MagicMock()
    mock.App = MagicMock()
    mock.MenuItem = MagicMock(return_value=MagicMock(state=False)) # Ensure state attribute exists
    mock.notification = MagicMock()
    mock.alert = MagicMock()
    mock.quit_application = MagicMock()
    mock.separator = '---separator---' # Or a MagicMock if it's called/interacted with
    mock.clicked = MagicMock(return_value=lambda x: x) # Decorator mock
    return mock

@pytest.fixture
def mock_device_manager_class():
    """Mocks the DeviceConnectionManager class."""
    mock_dcm_instance = MagicMock()
    mock_dcm_instance.get_auto_mode_status.return_value = True # Default auto mode on
    mock_dcm_instance.get_run_loop_source_address.return_value = 12345 # Mock address
    
    mock_dcm_class = MagicMock(return_value=mock_dcm_instance)
    return mock_dcm_class, mock_dcm_instance

@pytest.fixture
def mock_iokit_wrapper_menu_app():
    """Mocks the iokit_wrapper module for menu_bar_app tests."""
    mock = MagicMock()
    mock.add_run_loop_source_to_main_loop.return_value = True
    mock.remove_run_loop_source_from_main_loop.return_value = True
    return mock

@patch('src.menu_bar_app.rumps', new_callable=MagicMock) # Use new_callable for module mock
@patch('src.menu_bar_app.DeviceConnectionManager')
@patch('src.menu_bar_app.iokit_wrapper')
def test_menu_bar_app_initialization(mock_iokit, mock_dcm_class, mock_rumps_module):
    """Test the initialization of MenuBarApp."""
    # Configure mocks before MenuBarApp is instantiated
    mock_dcm_instance = MagicMock()
    mock_dcm_instance.get_auto_mode_status.return_value = True
    mock_dcm_instance.get_run_loop_source_address.return_value = 12345 # Valid address
    mock_dcm_class.return_value = mock_dcm_instance
    
    mock_rumps_module.MenuItem.return_value = MagicMock(state=False) # Ensure .state can be set
    mock_rumps_module.clicked.return_value = lambda x: x # Mock the decorator

    app = MenuBarApp()

    # Assert rumps.App was called
    mock_rumps_module.App.assert_called_once_with("OAK-D UVC", title="OAK-D", quit_button=None)

    # Assert DeviceConnectionManager was instantiated
    mock_dcm_class.assert_called_once_with(
        notify_ui_callback=app.show_notification,
        alert_ui_callback=app.show_alert,
        update_menu_callback=app.update_auto_mode_menu_state,
        update_status_label_callback=app.update_status_label
    )

    # Assert menu items were created
    # Expected calls to rumps.MenuItem: Status, Auto Mode, Disconnect
    assert mock_rumps_module.MenuItem.call_count >= 3 
    mock_rumps_module.MenuItem.assert_any_call("Enable Auto Camera Control", callback=app.callback_toggle_auto_mode)
    mock_rumps_module.MenuItem.assert_any_call("Disconnect Camera", callback=app.callback_disconnect_camera)
    mock_rumps_module.MenuItem.assert_any_call("Status: Initializing...") # Initial status text

    # Check initial state of auto_mode_menu_item
    # This requires capturing the instance of MenuItem for "Enable Auto Camera Control"
    # For simplicity, we assume the mock_dcm_instance.get_auto_mode_status() was used.
    # A more direct way: app.auto_mode_menu_item.state = mock_dcm_instance.get_auto_mode_status()
    # We can check that the created MenuItem mock had its state set.
    # Find the mock for the auto_mode_menu_item among all MenuItem calls
    auto_mode_menu_item_mock = None
    for call in mock_rumps_module.MenuItem.mock_calls:
        if call.args and call.args[0] == "Enable Auto Camera Control":
            auto_mode_menu_item_mock = mock_rumps_module.MenuItem.return_value # This is tricky if return_value is shared
            # A better way: have MenuItem return different mocks or track calls better.
            # For now, let's assume the LAST call to .state = was for this.
            # This part is fragile with simple MagicMock().MenuItem.
    # Instead, let's check that get_auto_mode_status was called.
    mock_dcm_instance.get_auto_mode_status.assert_called()


    # Assert iokit_wrapper.add_run_loop_source_to_main_loop was called
    mock_iokit.add_run_loop_source_to_main_loop.assert_called_once_with(12345)
    
    # Assert menu structure
    assert app.menu == [
        app.auto_mode_menu_item, 
        app.status_label_item, 
        app.disconnect_camera_menu_item, 
        mock_rumps_module.separator
    ]


@patch('src.menu_bar_app.rumps', new_callable=MagicMock)
@patch('src.menu_bar_app.DeviceConnectionManager')
@patch('src.menu_bar_app.iokit_wrapper')
def test_menu_bar_app_initialization_iokit_failure(mock_iokit, mock_dcm_class, mock_rumps_module):
    """Test MenuBarApp initialization when IOKit fails to add run loop source."""
    mock_dcm_instance = MagicMock()
    mock_dcm_instance.get_run_loop_source_address.return_value = 12345 # Valid address
    mock_dcm_class.return_value = mock_dcm_instance
    
    mock_iokit.add_run_loop_source_to_main_loop.return_value = False # Simulate failure

    mock_rumps_module.clicked.return_value = lambda x: x # Mock the decorator
    # rumps.alert will be called by the app
    
    app = MenuBarApp() # Should not raise error, but should call rumps.alert

    mock_iokit.add_run_loop_source_to_main_loop.assert_called_once_with(12345)
    mock_rumps_module.alert.assert_called_once_with("IOKit Error", "Failed to add USB event listener to the main application loop.")


@patch('src.menu_bar_app.rumps', new_callable=MagicMock)
@patch('src.menu_bar_app.DeviceConnectionManager')
@patch('src.menu_bar_app.iokit_wrapper')
def test_menu_bar_app_initialization_no_iokit_source(mock_iokit, mock_dcm_class, mock_rumps_module):
    """Test MenuBarApp initialization when no IOKit run loop source is available."""
    mock_dcm_instance = MagicMock()
    mock_dcm_instance.get_run_loop_source_address.return_value = 0 # Simulate no source
    mock_dcm_class.return_value = mock_dcm_instance
    
    mock_rumps_module.clicked.return_value = lambda x: x # Mock the decorator

    app = MenuBarApp()

    mock_iokit.add_run_loop_source_to_main_loop.assert_not_called()
    mock_rumps_module.alert.assert_called_once_with("IOKit Error", "Failed to initialize USB event listener.")


class TestMenuBarAppCallbacks:

    @pytest.fixture(autouse=True)
    def setup_patches(self, mock_rumps, mock_device_manager_class, mock_iokit_wrapper_menu_app):
        """Apply patches for all test methods in this class."""
        self.mock_rumps = mock_rumps
        self.mock_dcm_class = mock_device_manager_class[0] # The class mock
        self.mock_dcm_instance = mock_device_manager_class[1] # The instance mock
        self.mock_iokit = mock_iokit_wrapper_menu_app

        # Patch the modules where they are looked up by menu_bar_app.py
        with patch('src.menu_bar_app.rumps', self.mock_rumps), \
             patch('src.menu_bar_app.DeviceConnectionManager', self.mock_dcm_class), \
             patch('src.menu_bar_app.iokit_wrapper', self.mock_iokit):
            # Mock the rumps.clicked decorator before MenuBarApp is instantiated
            self.mock_rumps.clicked.return_value = lambda func_to_decorate: func_to_decorate
            self.app = MenuBarApp()
        
        # Reset mocks that might be called during init, if testing specific calls later
        self.mock_rumps.reset_mock()
        self.mock_dcm_instance.reset_mock()
        self.mock_iokit.reset_mock()
        # Re-assign the instance from the class mock as it's recreated by MenuBarApp init
        self.app.device_manager = self.mock_dcm_instance 


    def test_show_notification(self):
        self.app.show_notification("Test Title", "Test Subtitle", "Test Message")
        self.mock_rumps.notification.assert_called_once_with("Test Title", "Test Subtitle", "Test Message")

    def test_show_alert(self):
        self.app.show_alert("Test Alert Title", "Test Alert Message")
        self.mock_rumps.alert.assert_called_once_with("Test Alert Title", "Test Alert Message")

    def test_update_auto_mode_menu_state(self):
        self.app.auto_mode_menu_item = MagicMock() # Give it a fresh mock MenuItem
        self.app.update_auto_mode_menu_state(True)
        assert self.app.auto_mode_menu_item.state == True
        self.app.update_auto_mode_menu_state(False)
        assert self.app.auto_mode_menu_item.state == False

    def test_update_status_label(self):
        self.app.status_label_item = MagicMock() # Fresh mock MenuItem
        self.app.update_status_label("New Status")
        assert self.app.status_label_item.title == "New Status"

    def test_callback_toggle_auto_mode(self):
        # Create a mock sender if the callback uses it (current version does not)
        mock_sender = MagicMock() 
        self.app.callback_toggle_auto_mode(mock_sender)
        self.mock_dcm_instance.toggle_auto_mode.assert_called_once()

    def test_callback_disconnect_camera(self):
        mock_sender = MagicMock()
        self.app.callback_disconnect_camera(mock_sender)
        self.mock_dcm_instance.disconnect_camera_explicitly.assert_called_once()

    def test_callback_quit_app(self):
        # Simulate the _iokit_run_loop_source_addr being set
        self.app._iokit_run_loop_source_addr = 12345 
        
        # Call the quit callback (it's decorated, so we call the original method)
        # The rumps.clicked decorator is mocked to just return the function itself.
        self.app.callback_quit_app(None) # Sender is optional

        self.mock_iokit.remove_run_loop_source_from_main_loop.assert_called_once_with(12345)
        self.mock_dcm_instance.cleanup_on_quit.assert_called_once()
        self.mock_rumps.quit_application.assert_called_once()

    def test_callback_quit_app_no_iokit_source(self):
        self.app._iokit_run_loop_source_addr = 0 # Simulate no source was added
        
        self.app.callback_quit_app(None)

        self.mock_iokit.remove_run_loop_source_from_main_loop.assert_not_called()
        self.mock_dcm_instance.cleanup_on_quit.assert_called_once()
        self.mock_rumps.quit_application.assert_called_once()

# Placeholder for more tests if complex logic is added to MenuBarApp later.
# For now, MenuBarApp is mostly a passthrough to DeviceConnectionManager and rumps.
