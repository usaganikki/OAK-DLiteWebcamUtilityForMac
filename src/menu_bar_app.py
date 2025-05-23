import rumps
import os
import sys
from device_connection_manager import DeviceConnectionManager


class MenuBarApp(rumps.App):
    def __init__(self):
        super(MenuBarApp, self).__init__("OAK-D UVC", title="OAK-D", quit_button=None)
        
        self.status_label_item = rumps.MenuItem("Status: Initializing...")

        self.device_manager = DeviceConnectionManager(
            notify_ui_callback=self.show_notification,
            alert_ui_callback=self.show_alert,
            update_menu_callback=self.update_auto_mode_menu_state,
            update_status_label_callback=self.update_status_label
        )

        self.auto_mode_menu_item = rumps.MenuItem(
            "Enable Auto Camera Control", 
            callback=self.callback_toggle_auto_mode
        )
        # Initial state from DeviceConnectionManager
        self.auto_mode_menu_item.state = self.device_manager.get_auto_mode_status() 
        
        self.disconnect_camera_menu_item = rumps.MenuItem(
            "Disconnect Camera",
            callback=self.callback_disconnect_camera
        )
        
        self.menu = [self.auto_mode_menu_item, self.status_label_item, self.disconnect_camera_menu_item, rumps.separator]
        # rumps automatically adds a "Quit" button

    # --- Callback methods for DeviceConnectionManager ---
    def show_notification(self, title, subtitle, message):
        rumps.notification(title, subtitle, message)

    def show_alert(self, title, message):
        rumps.alert(title, message)

    def update_auto_mode_menu_state(self, is_enabled):
        self.auto_mode_menu_item.state = is_enabled
    
    # --- Menu item callbacks that delegate to DeviceConnectionManager ---
    def callback_toggle_auto_mode(self, sender):
        # No need to pass sender, DeviceConnectionManager handles its own logic
        self.device_manager.toggle_auto_mode()
        # The menu item state will be updated via the update_menu_callback

    def callback_disconnect_camera(self, sender):
        self.device_manager.disconnect_camera_explicitly()

    def update_status_label(self, status_text):
        self.status_label_item.title = status_text

    @rumps.clicked("Quit")
    def callback_quit_app(self, sender=None):
        self.device_manager.cleanup_on_quit()
        rumps.quit_application()

if __name__ == "__main__":
    # This check is crucial for macOS apps packaged with py2app or similar
    # to prevent issues with multiprocessing and process forking.
    # Not strictly necessary for rumps apps run directly via python, but good practice.
    # However, rumps apps often have issues with this guard on macOS if not handled carefully.
    # For a simple rumps app, it's usually fine to instantiate and run directly.

    # Check if running in a GUI environment (very basic check)
    # rumps apps are GUI apps and should not run in a headless environment
    # This is a placeholder, actual check for macOS GUI can be more complex
    # or rely on rumps to handle it.
    is_gui_environment = "TERM" not in os.environ or os.environ.get("TERM") == "dumb"
    if not hasattr(sys, 'frozen') and not sys.stdout.isatty() and not is_gui_environment:
         print("This is a GUI application and cannot be run in this environment.")
         # sys.exit(1) # Or simply don't run the app

    try:
        app = MenuBarApp()
        app.run()
    except RuntimeError as e:
        # rumps can raise RuntimeError if it cannot connect to the window server (e.g. headless environment)
        if "cannot find NSApplication" in str(e) or "Unable to connect to WindowServer" in str(e):
            print(f"Failed to start rumps application: {e}")
            print("This is a macOS menu bar application and requires a GUI environment.")
        else:
            raise # Re-raise other RuntimeErrors
    except Exception as e:
        # Catch all other exceptions during app setup or run
        print(f"An unexpected error occurred: {e}")
