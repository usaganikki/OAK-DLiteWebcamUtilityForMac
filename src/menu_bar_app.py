import rumps
import depthai as dai
from src.uvc_handler import UVCCamera, getMinimalPipeline # Assuming uvc_handler is in src
import os

# Ensure the script can find uvc_handler if it's not installed as a package
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class MenuBarApp(rumps.App):
    def __init__(self):
        super(MenuBarApp, self).__init__("OAK-D UVC", title="OAK-D") # Name for the app, title for the menu bar

        # Configure UVCCamera
        device_config = dai.Device.Config()
        # These UVC settings are similar to those in uvc_handler.py's run_uvc_device
        # They might be overridden by the pipeline's own BoardConfig if not set carefully.
        # However, UVCCamera class expects a device_config.
        device_config.board.uvc = dai.BoardConfig.UVC(1920, 1080)
        device_config.board.uvc.frameType = dai.ImgFrame.Type.NV12
        # The cameraName in pipeline's BoardConfig will likely take precedence for the UVC device name.

        self.camera = UVCCamera(pipeline_func=getMinimalPipeline, device_config=device_config)
        self.camera_running = False

        self.start_button = rumps.MenuItem("Start Camera", callback=self.start_camera_action)
        self.stop_button = rumps.MenuItem("Stop Camera", callback=None) # Initially disabled

        self.menu = [self.start_button, self.stop_button]
        # rumps automatically adds a "Quit" button that calls rumps.quit_application

    def start_camera_action(self, sender):
        if not self.camera_running:
            try:
                self.camera.start()
                self.camera_running = True
                rumps.notification("OAK-D Camera", "Status", "Camera started successfully.")
                # Update menu items
                self.start_button.set_callback(None) # Disable Start
                self.stop_button.set_callback(self.stop_camera_action) # Enable Stop
            except Exception as e:
                rumps.alert("Error starting camera", str(e))
                # Ensure camera is considered stopped if start failed
                if self.camera:
                    self.camera.stop() # Attempt to clean up
                self.camera_running = False
                self.start_button.set_callback(self.start_camera_action) # Re-enable Start
                self.stop_button.set_callback(None) # Keep Stop disabled


    def stop_camera_action(self, sender):
        if self.camera_running:
            try:
                self.camera.stop()
                self.camera_running = False
                rumps.notification("OAK-D Camera", "Status", "Camera stopped.")
                # Update menu items
                self.start_button.set_callback(self.start_camera_action) # Enable Start
                self.stop_button.set_callback(None) # Disable Stop
            except Exception as e:
                rumps.alert("Error stopping camera", str(e))
                # Consider the state uncertain, but try to reflect UI for attempting another stop/start
                self.start_button.set_callback(self.start_camera_action)
                self.stop_button.set_callback(self.stop_camera_action) # Leave stop enabled if error


    # rumps calls this method when the app is about to quit.
    # This can be triggered by the default Quit button or programmatically.
    def quit(self, sender=None):
        if self.camera_running:
            print("Stopping camera before quitting...")
            self.camera.stop()
            self.camera_running = False
            print("Camera stopped.")
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
