import subprocess
import os
import signal
import threading
import time # For testing/demonstration if needed

# Import the Cython wrapper
from src import iokit_wrapper # Assuming iokit_wrapper.pyx is compiled into src package

# Define OAK-D Lite's Vendor ID and Product ID
OAK_D_LITE_VENDOR_ID = 0x03e7
OAK_D_LITE_PRODUCT_ID = 0x2485

class USBEventHandler:
    """
    Handles callbacks from the Cython IOKit wrapper when USB events occur.
    """
    def __init__(self, manager_ref):
        self.manager = manager_ref # Reference to DeviceConnectionManager instance

    def on_device_connected(self, vendor_id, product_id, serial_number, service_id):
        # This method is called from the Cython layer (IOKit event thread)
        print(f"[DCM - USBEventHandler] on_device_connected: Start. VID={vendor_id:04x}, PID={product_id:04x}, SN='{serial_number}', ServiceID={service_id}")
        
        # Check if it's the OAK-D Lite device we are interested in
        if vendor_id == OAK_D_LITE_VENDOR_ID and product_id == OAK_D_LITE_PRODUCT_ID:
            self.manager.connected_target_device_info = {
                'vendor_id': vendor_id,
                'product_id': product_id,
                'serial_number': serial_number,
                'service_id': service_id
            }
            print(f"DCM: Target device connected. Stored info: {self.manager.connected_target_device_info}")
            self.manager.notify_ui_callback("OAK-D Status", "Device Connected", f"OAK-D Lite (SN: {serial_number}) detected.")
            if self.manager.auto_mode_enabled and not self.manager.camera_running:
                self.manager.notify_ui_callback("OAK-D Auto Control", "Starting Camera", "Device connected, auto-starting camera.")
                self.manager.start_camera_action() # Call manager's method
            elif not self.manager.camera_running:
                print("DCM: Device connected, auto mode is off, camera not started by auto-mode.")
            self.manager._update_status_label_based_on_state()
        else:
            print(f"DCM: Connected device (VID:{vendor_id:04x}, PID:{product_id:04x}) is not the target OAK-D Lite.")
        print(f"[DCM - USBEventHandler] on_device_connected: End. VID={vendor_id:04x}, PID={product_id:04x}")


    def on_device_disconnected(self, vendor_id, product_id, serial_number, service_id):
        # This method is called from the Cython layer (IOKit event thread)
        print(f"[PY EVENT HANDLER] Device Disconnected: VID={vendor_id:04x}, PID={product_id:04x}, SN='{serial_number}', ServiceID={service_id}")

        if vendor_id == OAK_D_LITE_VENDOR_ID and product_id == OAK_D_LITE_PRODUCT_ID:
            # Clear the stored device info if the target device is disconnected
            if self.manager.connected_target_device_info and \
               self.manager.connected_target_device_info.get('service_id') == service_id:
                print(f"DCM: Target device disconnected. Clearing stored info for ServiceID: {service_id}")
                self.manager.connected_target_device_info = None
            
            self.manager.notify_ui_callback("OAK-D Status", "Device Disconnected", f"OAK-D Lite (SN: {serial_number}) disconnected.")
            if self.manager.camera_running:
                # Regardless of auto_mode, if camera is running for this device, stop it.
                self.manager.notify_ui_callback("OAK-D Control", "Stopping Camera", "Device disconnected, stopping camera.")
                self.manager.stop_camera_action() # Call manager's method
            else:
                print("DCM: Device disconnected, camera was not running.")
            self.manager._update_status_label_based_on_state()
        else:
            print(f"DCM: Disconnected device (VID:{vendor_id:04x}, PID:{product_id:04x}) is not the target OAK-D Lite.")


class DeviceConnectionManager:
    def __init__(self, notify_ui_callback, alert_ui_callback, update_menu_callback, update_status_label_callback):
        self.uvc_process = None
        self.camera_running = False
        self.auto_mode_enabled = True

        self.notify_ui_callback = notify_ui_callback
        self.alert_ui_callback = alert_ui_callback
        self.update_menu_callback = update_menu_callback
        self.update_status_label_callback = update_status_label_callback

        self._event_handler = USBEventHandler(self) # Pass self reference
        # self._iokit_monitoring_thread = None # No longer managing a separate thread here
        self._run_loop_source_addr = 0 # To store the address of the CFRunLoopSourceRef
        self.connected_target_device_info = None # Store info of the connected OAK-D Lite
        
        self._update_status_label_based_on_state()
        self._start_iokit_monitoring()
        print("[DCM] DeviceConnectionManager initialized.")


    def _start_iokit_monitoring(self):
        # if self._iokit_monitoring_thread is not None and self._iokit_monitoring_thread.is_alive():
        #     print("DCM: IOKit monitoring thread is already running.") # Obsolete check
        #     return

        try:
            # Initialize IOKit monitoring in the Cython module, passing the event handler
            # and the VID/PID of the device to monitor.
            # This will now return the address of the CFRunLoopSourceRef.
            print("DCM: Calling iokit_wrapper.init_usb_monitoring...")
            run_loop_source_addr = iokit_wrapper.init_usb_monitoring(
                self._event_handler, 
                OAK_D_LITE_VENDOR_ID, 
                OAK_D_LITE_PRODUCT_ID
            )
            
            if run_loop_source_addr == 0 or run_loop_source_addr is None: # Check for null pointer / error
                raise Exception("Failed to get a valid run_loop_source_addr from iokit_wrapper.")

            self._run_loop_source_addr = run_loop_source_addr
            print(f"DCM: Obtained run_loop_source_addr: {self._run_loop_source_addr}")
            # Thread creation and start is removed.
            # The run loop source will be added to the main run loop by MenuBarApp.

        except Exception as e:
            error_message = f"DCM: Failed to initialize Cython IOKit monitoring: {e}"
            print(error_message)
            self.alert_ui_callback("IOKit Initialization Error", error_message)
            self._run_loop_source_addr = 0 # Ensure it's zeroed on error

    def get_run_loop_source_address(self):
        return self._run_loop_source_addr

    def _update_status_label_based_on_state(self):
        if self.camera_running:
            self.update_status_label_callback("接続中")
        else:
            self.update_status_label_callback("接続なし")


    def toggle_auto_mode(self):
        self.auto_mode_enabled = not self.auto_mode_enabled
        self.update_menu_callback(self.auto_mode_enabled)
        status_message = "enabled" if self.auto_mode_enabled else "disabled"
        self.notify_ui_callback("OAK-D Auto Control", "Setting Changed", f"Auto Camera Control has been {status_message}.")
        
        # If auto mode just enabled, and a device is connected (check via camera_running status,
        # which should be updated by IOKit events), start camera if not already running.
        # This logic might need refinement based on how `camera_running` reflects true device presence.
        # For now, assume IOKit events keep `camera_running` accurate.
        if self.auto_mode_enabled:
            print("DCM: Auto mode enabled.")
            # Check if the target device is already connected and camera is not running
            if self.connected_target_device_info is not None and not self.camera_running:
                print("DCM: Target device is connected and camera is not running. Starting camera due to auto_mode enabling.")
                self.notify_ui_callback("OAK-D Auto Control", "Starting Camera", "Device already connected, auto-starting camera.")
                self.start_camera_action()
            else:
                print("DCM: Auto mode enabled. Future device connections will auto-start camera if not running, or device not currently connected/camera already running.")

        elif not self.auto_mode_enabled and self.camera_running:
            print("DCM: Auto mode disabled and camera is running. Stopping camera.")
            self.notify_ui_callback("OAK-D Auto Control", "Stopping Camera", "Auto mode disabled, stopping camera.")
            self.stop_camera_action()
        
        self._update_status_label_based_on_state()


    def disconnect_camera_explicitly(self):
        if self.camera_running:
            # If auto_mode is on, user is manually disconnecting, so disable auto_mode.
            if self.auto_mode_enabled:
                self.auto_mode_enabled = False
                self.update_menu_callback(False) # Update UI menu
                self.notify_ui_callback("OAK-D Auto Control", "Disabled", "Auto-mode disabled due to manual disconnect.")

            self.stop_camera_action()
            self.notify_ui_callback("OAK-D Camera", "Disconnected", "Camera has been manually disconnected.")
        else:
            self.notify_ui_callback("OAK-D Camera", "Status", "Camera is not currently running.")
        self._update_status_label_based_on_state()


    def start_camera_action(self):
        if not self.camera_running:
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(current_dir, 'uvc_handler.py')

                if not os.path.exists(script_path):
                    self.alert_ui_callback("Error", f"uvc_handler.py not found at {script_path}")
                    return

                self.uvc_process = subprocess.Popen(['python3', script_path, '--start-uvc'])
                self.camera_running = True
                self.notify_ui_callback("OAK-D Camera", "Status", "Camera starting...")
            except Exception as e:
                self.alert_ui_callback("Error Starting Camera", str(e))
                self.camera_running = False
                self.uvc_process = None # Ensure process handle is cleared on error
            finally:
                self._update_status_label_based_on_state()


    def stop_camera_action(self):
        if self.camera_running and self.uvc_process:
            try:
                print("DCM: Sending SIGINT to uvc_handler process...")
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10) # Wait for graceful shutdown
                self.notify_ui_callback("OAK-D Camera", "Status", "Camera stopped.")
            except subprocess.TimeoutExpired:
                self.alert_ui_callback("Stopping camera timed out.", "Forcing termination.")
                print("DCM: uvc_handler process timed out. Terminating...")
                self.uvc_process.terminate()
                try:
                    self.uvc_process.wait(timeout=5) # Wait for forced termination
                except Exception as e_term:
                    print(f"DCM: Error during forced termination: {e_term}")
            except Exception as e:
                self.alert_ui_callback("Error Stopping Camera", str(e))
                print(f"DCM: Error stopping camera: {e}")
            finally:
                self.uvc_process = None
                self.camera_running = False
        elif self.camera_running and not self.uvc_process:
            # Camera was marked as running, but no process handle. Reset state.
            print("DCM: Camera marked as running, but no uvc_process handle. Resetting state.")
            self.camera_running = False
        
        self._update_status_label_based_on_state()


    def get_camera_running_status(self):
        return self.camera_running

    def get_auto_mode_status(self):
        return self.auto_mode_enabled

    def cleanup_on_quit(self):
        print("DCM: Cleanup initiated on quit...")

        # 1. Stop Cython IOKit event monitoring
        try:
            print("DCM: Stopping Cython IOKit USB monitoring (resources)...")
            # This will now primarily release port and iterators.
            # RunLoopSource removal from main loop needs to be handled by MenuBarApp or a new Cython helper.
            iokit_wrapper.stop_usb_monitoring() 
        except Exception as e:
            print(f"DCM: Error calling stop_usb_monitoring: {e}")

        # 2. Join the IOKit monitoring thread - REMOVED as thread is no longer managed here
        # if self._iokit_monitoring_thread and self._iokit_monitoring_thread.is_alive():
        #     print("DCM: Joining IOKit event loop thread...")
        #     self._iokit_monitoring_thread.join(timeout=2.0) # Wait for thread to finish
        #     if self._iokit_monitoring_thread.is_alive():
        #         print("DCM: Warning: IOKit event loop thread did not terminate in time.")
        #     else:
        #         print("DCM: IOKit event loop thread successfully joined.")
        # self._iokit_monitoring_thread = None

        # 3. Stop the UVC handler subprocess (if running)
        if self.camera_running and self.uvc_process:
            print("DCM: Stopping camera (uvc_process) before quitting...")
            self.stop_camera_action() # Use existing method for consistency
        
        print("DCM: Cleanup finished.")
