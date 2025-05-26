import rumps
import os
import sys
from .device_connection_manager import DeviceConnectionManager
from src import iokit_wrapper # Import the Cython module


class MenuBarApp(rumps.App):
    def __init__(self):
        print("[MenuBarApp] __init__: Start")
        super(MenuBarApp, self).__init__("OAK-D UVC", title="OAK-D", quit_button=None)
        print("[MenuBarApp] __init__: super().__init__ done")
        
        self.status_label_item = rumps.MenuItem("Status: Initializing...")
        print("[MenuBarApp] __init__: status_label_item created")

        print("[MenuBarApp] __init__: Before DeviceConnectionManager instantiation")
        self.device_manager = DeviceConnectionManager(
            notify_ui_callback=self.show_notification,
            alert_ui_callback=self.show_alert,
            update_menu_callback=self.update_auto_mode_menu_state,
            update_status_label_callback=self.update_status_label
        )
        print("[MenuBarApp] __init__: After DeviceConnectionManager instantiation")

        # print("[MenuBarApp] __init__: Attempting to proceed past DeviceConnectionManager...") # No longer needed
        # Restore MenuItem creation
        self.auto_mode_menu_item = rumps.MenuItem(
            "Enable Auto Camera Control", 
            callback=self.callback_toggle_auto_mode
        )
        print("[MenuBarApp] __init__: auto_mode_menu_item created")
        # Initial state from DeviceConnectionManager
        self.auto_mode_menu_item.state = self.device_manager.get_auto_mode_status() 
        print("[MenuBarApp] __init__: auto_mode_menu_item state set")
        
        self.disconnect_camera_menu_item = rumps.MenuItem(
            "Disconnect Camera",
            callback=self.callback_disconnect_camera
        )
        print("[MenuBarApp] __init__: disconnect_camera_menu_item created")
        
        self.menu = [self.auto_mode_menu_item, self.status_label_item, self.disconnect_camera_menu_item, rumps.separator]
        print("[MenuBarApp] __init__: menu list populated")
        
        # rumps automatically adds a "Quit" button
        print("[MenuBarApp] __init__: End") # Restored original end log

        # Add the IOKit run loop source to the main run loop
        self._iokit_run_loop_source_addr = self.device_manager.get_run_loop_source_address()
        if self._iokit_run_loop_source_addr != 0:
            print(f"[MenuBarApp] Attempting to add IOKit run loop source (addr: {self._iokit_run_loop_source_addr}) to main loop.")
            if not iokit_wrapper.add_run_loop_source_to_main_loop(self._iokit_run_loop_source_addr):
                rumps.alert("IOKit Error", "Failed to add USB event listener to the main application loop.")
        else:
            print("[MenuBarApp] No valid IOKit run loop source address obtained.")
            rumps.alert("IOKit Error", "Failed to initialize USB event listener.")


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
        print("[MenuBarApp] Quit callback initiated.")
        if hasattr(self, '_iokit_run_loop_source_addr') and self._iokit_run_loop_source_addr != 0:
            print(f"[MenuBarApp] Attempting to remove IOKit run loop source (addr: {self._iokit_run_loop_source_addr}) from main loop.")
            if not iokit_wrapper.remove_run_loop_source_from_main_loop(self._iokit_run_loop_source_addr):
                print("[MenuBarApp] Warning: Failed to remove IOKit run loop source from main loop.")
        
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
        print("[MenuBarApp] MenuBarApp instance created.")
        print("[MenuBarApp] About to call app.run()")
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
