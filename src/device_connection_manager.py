import subprocess
import os
import signal
import depthai as dai
import datetime
import rumps # For rumps.Timer, will be managed internally
import IOKit # Import the IOKit module directly
import threading # For the IOKit event loop thread

# PyObjC imports
from Foundation import NSObject, NSRunLoop, NSDate, NSDefaultRunLoopMode 
# NSDefaultRunLoopMode is a string constant like "kCFRunLoopDefaultMode"
# and is available from Foundation.
from IOKit import (
    kIOMasterPortDefault,     # Constant for the master port
    kIOUSBDeviceClassName,    # String constant for matching USB devices
    kIOMatchedNotification,   # Notification type for device connection
    kIOTerminatedNotification # Notification type for device disconnection
    # IOServiceMatching, IONotificationPortCreate, IOServiceAddMatchingNotification,
    # IOIteratorNext, IOObjectRelease are functions directly available from IOKit module.
)

# Define OAK-D Lite's Vendor ID and Product ID
OAK_D_LITE_VENDOR_ID = 0x03e7
OAK_D_LITE_PRODUCT_ID = 0xf63d

# Standard IOKit keys for matching dictionary (these are string constants)
kIOUSBVendorIDKey = "idVendor"
kIOUSBProductIDKey = "idProduct"


class DeviceConnectionManager(NSObject): # Inherit from NSObject
    def __init__(self, notify_ui_callback, alert_ui_callback, update_menu_callback, update_status_label_callback):
        super().__init__() # Call superclass initializer

        # Initialize IOKit related attributes
        self.notify_port = None
        self.connection_iterator = None
        self.disconnection_iterator = None
        self.iokit_thread = None # Thread for IOKit event loop
        # For IOServiceAddMatchingNotification, to hold the returned iterator
        self.connection_iterator_holder = [None] 
        self.disconnection_iterator_holder = [None]

        self.uvc_process = None
        self.camera_running = False
        self.auto_mode_enabled = True  # Default to True as in MenuBarApp
        # Removed: self.last_stable_device_state, self.current_device_state_candidate, 
        # self.device_state_change_counter, self.debounce_threshold

        # Callbacks to MenuBarApp
        self.notify_ui_callback = notify_ui_callback
        self.alert_ui_callback = alert_ui_callback
        self.update_menu_callback = update_menu_callback
        self.update_status_label_callback = update_status_label_callback # Store the new callback

        # The old initial device check block is removed.
        # IOKit's notification arming in _setup_iokit_notifications 
        # will handle devices connected at startup.

        # Removed: self.device_check_timer initialization and start

        self._update_status_label_based_on_state() # Initial status update
        self._setup_iokit_notifications() # Call the new setup method

        if self.notify_port: # Only start thread if notification port was successfully created
            self.iokit_thread = threading.Thread(target=self._iokit_event_loop, name="IOKitEventLoop")
            self.iokit_thread.daemon = True  # Ensure thread exits when main program exits
            self.iokit_thread.start()
            print("DCM: IOKitEventLoop thread initiated and started.")
        else:
            print("DCM: Not starting IOKitEventLoop thread as notify_port is None.")

    def _iokit_event_loop(self):
        print("DCM: IOKitEventLoop thread started.")
        # Get the run loop for this new thread
        # Note: NSRunLoop.currentRunLoop() creates a run loop if one doesn't exist for the thread.
        
        if not self.notify_port:
            print("DCM: IOKitEventLoop: Notification port is None. Cannot start event loop.")
            return

        # Add the notification port to this thread's run loop.
        # This is where events for this port will be processed.
        NSRunLoop.currentRunLoop().addPort_forMode_(self.notify_port, NSDefaultRunLoopMode)
        print("DCM: IOKitEventLoop: Notification port added to run loop. Starting run loop.")
        
        # Run the event loop. This will block on this thread and process IOKit notifications.
        # It will continue until the run loop is stopped, e.g., by invalidating all its sources (like our notify_port).
        NSRunLoop.currentRunLoop().run()
        
        # This line will likely not be reached if the loop runs indefinitely until the port is invalidated.
        # However, if run() terminates for other reasons, this indicates the loop has stopped.
        print("DCM: IOKitEventLoop: Run loop finished.")

    def _usb_device_connected(self, refCon, iterator):
    def _usb_device_connected(self, refCon, iterator):
        # refCon is self, passed during registration
        print(f"DCM: IOKit: _usb_device_connected. Iterator: {hex(iterator) if iterator else 'None'}")
        if not iterator: return

        device = IOKit.IOIteratorNext(iterator)
        while device:
            try:
                print(f"DCM: IOKit: Processing connected device: {hex(device)}")
                # Current logic for connection:
                self.notify_ui_callback("OAK-D Status", "Device Connected (IOKit)", "OAK-D device detected by IOKit.")
                if self.auto_mode_enabled and not self.camera_running:
                    self.notify_ui_callback("OAK-D Auto Control", "Starting Camera (IOKit)", "Device connected, auto-starting camera.")
                    self.start_camera_action()
                elif not self.camera_running:
                    print("DCM: IOKit: Device connected, auto mode is off, camera not started.")
                self._update_status_label_based_on_state()
                # End of current logic
            except Exception as e:
                print(f"DCM: IOKit: Error during _usb_device_connected processing for device {hex(device)}: {e}")
                # self.alert_ui_callback("IOKit Error", f"Error processing USB connect: {e}") # Optional alert
            finally:
                IOKit.IOObjectRelease(device) # Release current device
            device = IOKit.IOIteratorNext(iterator) # Get next device

    def _usb_device_disconnected(self, refCon, iterator):
        print(f"DCM: IOKit: _usb_device_disconnected. Iterator: {hex(iterator) if iterator else 'None'}")
        if not iterator: return

        device = IOKit.IOIteratorNext(iterator)
        while device:
            try:
                print(f"DCM: IOKit: Processing disconnected device: {hex(device)}")
                # Current logic for disconnection:
                self.notify_ui_callback("OAK-D Status", "Device Disconnected (IOKit)", "OAK-D device disconnected event from IOKit.")
                if self.camera_running:
                    if self.auto_mode_enabled:
                        self.notify_ui_callback("OAK-D Auto Control", "Stopping Camera (IOKit)", "Device disconnected, auto-stopping camera.")
                        self.stop_camera_action()
                    else:
                        self.notify_ui_callback("OAK-D Camera", "Stopping Camera (IOKit)", "Device disconnected, stopping manually started camera.")
                        self.stop_camera_action()
                else:
                    print("DCM: IOKit: Device disconnected, camera was not running.")
                self._update_status_label_based_on_state()
                # End of current logic
            except Exception as e:
                print(f"DCM: IOKit: Error during _usb_device_disconnected processing for device {hex(device)}: {e}")
                # self.alert_ui_callback("IOKit Error", f"Error processing USB disconnect: {e}") # Optional alert
            finally:
                IOKit.IOObjectRelease(device) # Release current device
            device = IOKit.IOIteratorNext(iterator) # Get next device

    def _setup_iokit_notifications(self):
        master_port = kIOMasterPortDefault # Get the I/O Kit master port
        self.notify_port = IOKit.IONotificationPortCreate(master_port)
        
        if not self.notify_port:
            error_message = "DCM: IOKit: Failed to create IONotificationPort. USB event monitoring will be disabled."
            print(error_message)
            self.alert_ui_callback("IOKit Error", error_message)
            return # Exit early if port creation fails

        # Get the run loop source for the notification port.
        run_loop_source = IOKit.IONotificationPortGetRunLoopSource(self.notify_port)
        if not run_loop_source:
            error_message = "DCM: IOKit: Failed to get run loop source from notification port. USB event monitoring will be disabled."
            print(error_message)
            self.alert_ui_callback("IOKit Error", error_message)
            IOKit.IONotificationPortDestroy(self.notify_port) # Clean up the created port
            self.notify_port = None
            return
            
        # DO NOT add the port to the current thread's run loop here.
        # This will be done in the _iokit_event_loop method on the dedicated thread.

        # For Matched (Connection) Notifications:
        matching_dict_connect = IOKit.IOServiceMatching(kIOUSBDeviceClassName)
        if not matching_dict_connect: # Should ideally not happen with a valid class name
            error_message = "DCM: IOKit: Failed to create basic matching dictionary for connect. USB connect events may not be detected."
            print(error_message)
            self.alert_ui_callback("IOKit Warning", error_message)
            # Continue to attempt disconnect notification setup, as port is valid.
        else:
            matching_dict_connect[kIOUSBVendorIDKey] = OAK_D_LITE_VENDOR_ID
            matching_dict_connect[kIOUSBProductIDKey] = OAK_D_LITE_PRODUCT_ID

            result_connect = IOKit.IOServiceAddMatchingNotification(
                self.notify_port,
                kIOMatchedNotification,
                matching_dict_connect,
                self._usb_device_connected,
                self,
                self.connection_iterator_holder
            )
            if result_connect != 0: # kIOReturnSuccess is 0
                error_message = f"DCM: IOKit: Failed to register connect notification: {result_connect}. USB connect events may not be detected."
                print(error_message)
                self.alert_ui_callback("IOKit Warning", error_message)
                self.connection_iterator = None
            else:
                self.connection_iterator = self.connection_iterator_holder[0]
                if self.connection_iterator:
                    print(f"DCM: IOKit: Connect notification registered. Iterator: {hex(self.connection_iterator)}")
                    self._usb_device_connected(self, self.connection_iterator)
                else: # Should not happen if result_connect was 0, but as a safeguard
                    print("DCM: IOKit: Connect iterator is null despite successful registration.")
                    self.alert_ui_callback("IOKit Warning", "Connect iterator null post-registration.")


        # For Terminated (Disconnection) Notifications:
        matching_dict_terminate = IOKit.IOServiceMatching(kIOUSBDeviceClassName)
        if not matching_dict_terminate: # Should ideally not happen
            error_message = "DCM: IOKit: Failed to create basic matching dictionary for terminate. USB disconnect events may not be detected."
            print(error_message)
            self.alert_ui_callback("IOKit Warning", error_message)
        else:
            matching_dict_terminate[kIOUSBVendorIDKey] = OAK_D_LITE_VENDOR_ID
            matching_dict_terminate[kIOUSBProductIDKey] = OAK_D_LITE_PRODUCT_ID

            result_terminate = IOKit.IOServiceAddMatchingNotification(
                self.notify_port,
                kIOTerminatedNotification,
                matching_dict_terminate,
                self._usb_device_disconnected,
                self,
                self.disconnection_iterator_holder
            )
            if result_terminate != 0: # kIOReturnSuccess is 0
                error_message = f"DCM: IOKit: Failed to register disconnect notification: {result_terminate}. USB disconnect events may not be detected."
                print(error_message)
                self.alert_ui_callback("IOKit Warning", error_message)
                self.disconnection_iterator = None
            else:
                self.disconnection_iterator = self.disconnection_iterator_holder[0]
                if self.disconnection_iterator:
                    print(f"DCM: IOKit: Disconnect notification registered. Iterator: {hex(self.disconnection_iterator)}")
                    self._usb_device_disconnected(self, self.disconnection_iterator)
                else: # Safeguard
                    print("DCM: IOKit: Disconnect iterator is null despite successful registration.")
                    self.alert_ui_callback("IOKit Warning", "Disconnect iterator null post-registration.")

    def _update_status_label_based_on_state(self):
        if self.camera_running:
            self.update_status_label_callback("接続中")
        else:
            # Per refined requirement: "接続なし" if not camera_running
            self.update_status_label_callback("接続なし")

    # Removed: check_device_connection method

    def toggle_auto_mode(self):
        self.auto_mode_enabled = not self.auto_mode_enabled
        self.update_menu_callback(self.auto_mode_enabled) # Notify MenuBarApp to update menu item state
        status_message = "enabled" if self.auto_mode_enabled else "disabled"
        self.notify_ui_callback("OAK-D Auto Control", "Setting Changed", f"Auto Camera Control has been {status_message}.")
        
        if self.auto_mode_enabled:
            # Auto mode has just been enabled.
            # Check if a device is currently connected and if so, and camera isn't running, start it.
            # This covers the case where a device is present, IOKit connected event fired,
            # but auto_mode was off at that moment.
            try:
                # This check uses depthai API to see if any OAK device is currently available.
                # It's a direct check for the current state.
                available_devices = dai.Device.getAllAvailableDevices()
                if len(available_devices) > 0 and not self.camera_running:
                    self.notify_ui_callback("OAK-D Auto Control", "Starting Camera (Auto Mode Enabled)", "Auto mode enabled, device detected, starting camera.")
                    self.start_camera_action()
                elif len(available_devices) == 0 and not self.camera_running:
                    print("DCM: Auto mode enabled, no device currently detected. Waiting for IOKit connection event.")
                # If camera is already running, or no devices, do nothing more here.
                # The IOKit _usb_device_connected callback will handle future connections.
            except Exception as e:
                print(f"DCM: Error checking devices in toggle_auto_mode: {e}")
                # Potentially alert UI if this check is critical and fails often.
                # self.alert_ui_callback("Device Check Error", f"Failed to check for devices: {e}")

        elif not self.auto_mode_enabled and self.camera_running:
            # Auto mode has just been disabled, and the camera is running. Stop the camera.
            self.notify_ui_callback("OAK-D Auto Control", "Stopping Camera (Auto Mode Disabled)", "Auto mode disabled, stopping camera.")
            self.stop_camera_action()
        
        # Ensure label is updated after potential start/stop actions
        self._update_status_label_based_on_state()

    def disconnect_camera_explicitly(self):
        if self.camera_running and self.uvc_process:
            original_auto_mode_status = self.auto_mode_enabled
            if self.auto_mode_enabled:
                self.auto_mode_enabled = False
                self.update_menu_callback(False) # Update UI
            
            self.stop_camera_action() # This should set camera_running to False and uvc_process to None

            # Notification message depends on whether auto_mode was disabled by this action
            if original_auto_mode_status and not self.auto_mode_enabled:
                message = "Camera has been disconnected. Auto-mode was active and has been disabled."
            else:
                message = "Camera has been disconnected."
            self.notify_ui_callback("OAK-D Camera", "Disconnected", message)
            # stop_camera_action already called _update_status_label_based_on_state
        else:
            self.notify_ui_callback("OAK-D Camera", "Status", "Camera is not currently running or connected.")
            self._update_status_label_based_on_state() # Ensure label is "接続なし"

    def start_camera_action(self):
        if not self.camera_running:
            try:
                # Path construction needs to be relative to this file or an absolute path
                # Assuming uvc_handler.py is in the same directory (src)
                current_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(current_dir, 'uvc_handler.py')

                if not os.path.exists(script_path):
                    self.alert_ui_callback("Error", f"uvc_handler.py not found at {script_path}")
                    return

                self.uvc_process = subprocess.Popen(['python3', script_path, '--start-uvc'])
                self.camera_running = True
                self.notify_ui_callback("OAK-D Camera", "Status", "Camera starting...")
                self._update_status_label_based_on_state() # Update on successful start
            except Exception as e:
                self.alert_ui_callback("Error Starting Camera", str(e))
                self.camera_running = False
                if self.uvc_process:
                    try:
                        self.uvc_process.terminate()
                        self.uvc_process.wait(timeout=2)
                    except Exception:
                        pass
                self.uvc_process = None
                self._update_status_label_based_on_state() # Update on failure

    def stop_camera_action(self):
        if self.camera_running and self.uvc_process:
            try:
                print("DCM: Sending SIGINT to uvc_handler process...")
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10)
                self.notify_ui_callback("OAK-D Camera", "Status", "Camera stopped.")
            except subprocess.TimeoutExpired:
                self.alert_ui_callback("Stopping camera timed out.", "Forcing termination.")
                print("DCM: uvc_handler process timed out. Terminating...")
                self.uvc_process.terminate()
                try:
                    self.uvc_process.wait(timeout=5)
                except Exception as e_term:
                    print(f"DCM: Error during forced termination: {e_term}")
            except Exception as e:
                self.alert_ui_callback("Error Stopping Camera", str(e))
                print(f"DCM: Error stopping camera: {e}")
            finally:
                self.uvc_process = None
                self.camera_running = False
                self._update_status_label_based_on_state() # Update after stopping
        elif not self.uvc_process and self.camera_running:
            # This case indicates an inconsistent state.
            # For example, camera_running was true but no process handle.
            self.alert_ui_callback("Camera State Inconsistent", "Resetting. Camera might still be running if started externally.")
            self.camera_running = False
            self._update_status_label_based_on_state() # Update label

    def get_camera_running_status(self):
        return self.camera_running

    def get_auto_mode_status(self):
        return self.auto_mode_enabled

    def cleanup_on_quit(self):
        print("DCM: Cleanup initiated on quit...")

        # 1. Stop IOKit event loop and release IOKit resources
        if hasattr(self, 'notify_port') and self.notify_port:
            print("DCM: Invalidating IOKit notification port.")
            IOKit.IONotificationPortDestroy(self.notify_port)
            self.notify_port = None

        if hasattr(self, 'iokit_thread') and self.iokit_thread and self.iokit_thread.is_alive():
            print("DCM: Joining IOKit event loop thread...")
            self.iokit_thread.join(timeout=2.0)
            if self.iokit_thread.is_alive():
                print("DCM: Warning: IOKit event loop thread did not terminate in time.")
            else:
                print("DCM: IOKit event loop thread successfully joined.")
            self.iokit_thread = None # Clear thread object

        if hasattr(self, 'connection_iterator') and self.connection_iterator:
            try:
                print(f"DCM: Releasing IOKit connection_iterator: {hex(self.connection_iterator)}")
                IOKit.IOObjectRelease(self.connection_iterator)
                self.connection_iterator = None
            except Exception as e:
                print(f"DCM: Error releasing connection_iterator: {e}")
        
        if hasattr(self, 'disconnection_iterator') and self.disconnection_iterator:
            try:
                print(f"DCM: Releasing IOKit disconnection_iterator: {hex(self.disconnection_iterator)}")
                IOKit.IOObjectRelease(self.disconnection_iterator)
                self.disconnection_iterator = None
            except Exception as e:
                print(f"DCM: Error releasing disconnection_iterator: {e}")

        # 2. Stop the old polling timer (REMOVED as part of Step 5)
        # Removed: device_check_timer cleanup block

        # 3. Stop the UVC handler subprocess (existing logic)
        if self.camera_running and self.uvc_process:
            print("DCM: Stopping camera (uvc_process) before quitting...")
            try:
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10) # Adjusted from original for consistency
                print("DCM: Camera stopped via subprocess send_signal.")
            except subprocess.TimeoutExpired:
                print("DCM: Timeout stopping camera on quit via SIGINT. Terminating...")
                self.uvc_process.terminate()
                try:
                    self.uvc_process.wait(timeout=5)
                except Exception:
                    print("DCM: Exception during terminate wait.")
            except Exception as e:
                print(f"DCM: Error stopping camera on quit: {e}")
                if self.uvc_process: # Check if process still exists
                    try:
                        print("DCM: Attempting forced termination due to error.")
                        self.uvc_process.terminate()
                        self.uvc_process.wait(timeout=2)
                    except Exception:
                        print("DCM: Exception during forced termination wait.")
            finally:
                self.uvc_process = None
                self.camera_running = False # Ensure state is updated
        
        print("DCM: Cleanup finished.")
