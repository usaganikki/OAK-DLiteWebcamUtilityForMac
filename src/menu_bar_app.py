import rumps
import subprocess
import os
import signal
import sys

# Ensure the script can find uvc_handler if it's not installed as a package
# This might not be strictly necessary if running from the project root
# and src is a package, but can help in some execution contexts.
# However, for subprocess calls, the path to uvc_handler.py needs to be correct.
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class MenuBarApp(rumps.App):
    def __init__(self):
        super(MenuBarApp, self).__init__("OAK-D UVC", title="OAK-D", quit_button=None)
        self.uvc_process = None  # To store the subprocess object
        self.camera_running = False

        self.start_button = rumps.MenuItem("Start Camera", callback=self.start_camera_action)
        self.stop_button = rumps.MenuItem("Stop Camera", callback=None)  # Initially disabled
        self.menu = [self.start_button, self.stop_button]
        # rumps automatically adds a "Quit" button

    def start_camera_action(self, sender):
        if not self.camera_running:
            try:
                # Construct the path to uvc_handler.py relative to this script's location
                current_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(current_dir, 'uvc_handler.py')

                if not os.path.exists(script_path):
                    rumps.alert("Error", f"uvc_handler.py not found at {script_path}")
                    return

                # Start uvc_handler.py as a subprocess
                # Using python3 explicitly, ensure it's in PATH or provide full path
                self.uvc_process = subprocess.Popen(['python3', script_path, '--start-uvc'])
                self.camera_running = True
                rumps.notification("OAK-D Camera", "Status", "Camera starting...")
                self.start_button.set_callback(None)  # Disable Start
                self.stop_button.set_callback(self.stop_camera_action)  # Enable Stop
            except Exception as e:
                rumps.alert("Error Starting Camera", str(e))
                self.camera_running = False
                if self.uvc_process: # If process was created but failed
                    try:
                        self.uvc_process.terminate()
                        self.uvc_process.wait(timeout=2) # Short wait
                    except Exception:
                        pass # Ignore errors during cleanup
                self.uvc_process = None
                self.start_button.set_callback(self.start_camera_action)  # Re-enable Start
                self.stop_button.set_callback(None)  # Keep Stop disabled

    def stop_camera_action(self, sender):
        if self.camera_running and self.uvc_process:
            try:
                print("Sending SIGINT to uvc_handler process...")
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10)  # Wait for the process to terminate
                rumps.notification("OAK-D Camera", "Status", "Camera stopped.")
            except subprocess.TimeoutExpired:
                rumps.alert("Stopping camera timed out. Forcing termination.")
                print("uvc_handler process timed out. Terminating...")
                self.uvc_process.terminate() # Force kill if it doesn't respond to SIGINT
                try:
                    self.uvc_process.wait(timeout=5) # Wait for terminate
                except Exception as e_term:
                    print(f"Error during forced termination: {e_term}")
            except Exception as e:
                rumps.alert("Error Stopping Camera", str(e))
                print(f"Error stopping camera: {e}")
                # In case of error, still try to reflect that a stop was attempted.
                # Consider if process might still be running or if it's safe to reset.
            finally:
                self.uvc_process = None
                self.camera_running = False
                self.start_button.set_callback(self.start_camera_action)  # Enable Start
                self.stop_button.set_callback(None)  # Disable Stop
        elif not self.uvc_process and self.camera_running:
            # State inconsistency: running flag is true but no process
            rumps.alert("Camera State Inconsistent", "Resetting UI. Camera might still be running if started externally.")
            self.camera_running = False
            self.start_button.set_callback(self.start_camera_action)
            self.stop_button.set_callback(None)


    @rumps.clicked("Quit") # Handles the default Quit button
    def quit_app(self, sender=None): # Renamed from quit to avoid conflict if rumps.App has a quit method
        if self.camera_running and self.uvc_process:
            print("Stopping camera before quitting...")
            try:
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10)
                print("Camera stopped via subprocess.")
            except subprocess.TimeoutExpired:
                print("Timeout stopping camera on quit. Terminating...")
                self.uvc_process.terminate()
                try:
                    self.uvc_process.wait(timeout=5)
                except Exception:
                    pass
            except Exception as e:
                print(f"Error stopping camera on quit: {e}")
                if self.uvc_process: # If process still exists
                    try:
                        self.uvc_process.terminate()
                        self.uvc_process.wait(timeout=2)
                    except Exception:
                        pass
            finally:
                self.uvc_process = None
                self.camera_running = False
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
