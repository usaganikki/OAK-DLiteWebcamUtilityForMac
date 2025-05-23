import subprocess
import os
import signal
import depthai as dai
import datetime
import rumps # For rumps.Timer, will be managed internally

class DeviceConnectionManager:
    def __init__(self, notify_ui_callback, alert_ui_callback, update_menu_callback, update_status_label_callback):
        self.uvc_process = None
        self.camera_running = False
        self.auto_mode_enabled = True  # Default to True as in MenuBarApp
        self.last_stable_device_state = False
        self.current_device_state_candidate = False
        self.device_state_change_counter = 0
        self.debounce_threshold = 2  # Default debounce threshold

        # Callbacks to MenuBarApp
        self.notify_ui_callback = notify_ui_callback
        self.alert_ui_callback = alert_ui_callback
        self.update_menu_callback = update_menu_callback
        self.update_status_label_callback = update_status_label_callback # Store the new callback

        # 初期状態でのカメラ起動チェック
        initial_devices = dai.Device.getAllAvailableDevices()
        if self.auto_mode_enabled and len(initial_devices) > 0:
            # 物理的に接続されていると判断し、関連状態も初期化
            self.last_stable_device_state = True
            self.current_device_state_candidate = True
            self.device_state_change_counter = self.debounce_threshold # デバウンスカウンターも満たしておく

            self.notify_ui_callback("OAK-D Auto Control", "Starting Camera (Initial)", "Device connected at startup, auto-starting camera.")
            self.start_camera_action()

        self.device_check_timer = rumps.Timer(self.check_device_connection, 3)
        self.device_check_timer.start()

        self._update_status_label_based_on_state() # Initial status update

    def _update_status_label_based_on_state(self):
        if self.camera_running:
            self.update_status_label_callback("接続中")
        else:
            # Per refined requirement: "接続なし" if not camera_running
            self.update_status_label_callback("接続なし")

    def check_device_connection(self, sender=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        action_taken = "None"
        
        initial_stable_state_this_cycle = self.last_stable_device_state

        available_devices = dai.Device.getAllAvailableDevices()
        num_devices = len(available_devices)
        
        if self.camera_running:
            physical_device_is_connected = True 
        else:
            physical_device_is_connected = num_devices > 0

        if physical_device_is_connected == self.current_device_state_candidate:
            self.device_state_change_counter += 1
        else:
            self.current_device_state_candidate = physical_device_is_connected
            self.device_state_change_counter = 1
        
        if self.device_state_change_counter >= self.debounce_threshold:
            if self.current_device_state_candidate != initial_stable_state_this_cycle:
                self.last_stable_device_state = self.current_device_state_candidate
                
                if self.last_stable_device_state and not initial_stable_state_this_cycle:
                    self.notify_ui_callback("OAK-D Status", "Device Connected (Stable)", "OAK-D device has been connected.")
                    if self.auto_mode_enabled and not self.camera_running:
                        self.notify_ui_callback("OAK-D Auto Control", "Starting Camera (Stable)", "Device connected, auto-starting camera.")
                        self.start_camera_action() # No sender needed here
                        action_taken = "Start Camera (Stable)"
                elif not self.last_stable_device_state and initial_stable_state_this_cycle:
                    self.notify_ui_callback("OAK-D Status", "Device Disconnected (Stable)", "OAK-D device has been disconnected.")
                    if self.auto_mode_enabled and self.camera_running:
                        self.notify_ui_callback("OAK-D Auto Control", "Stopping Camera (Stable)", "Device disconnected, auto-stopping camera.")
                        self.stop_camera_action() # No sender needed here
                        action_taken = "Stop Camera (Stable)"
        
        log_message_parts = [
            f"[{timestamp}] DCM:CheckDeviceConnection:",
            f"  Devices Found (Raw API): {num_devices}",
            f"  Physical Connected (Logic): {physical_device_is_connected}",
            f"  State Candidate: {self.current_device_state_candidate}",
            f"  Candidate Count: {self.device_state_change_counter}/{self.debounce_threshold}",
            f"  Initial Stable State this cycle: {initial_stable_state_this_cycle}",
            f"  Last Stable State (updated): {self.last_stable_device_state}",
            f"  Auto Mode: {self.auto_mode_enabled}",
            f"  Camera Running: {self.camera_running}",
            f"  Action Taken: {action_taken}"
        ]
        print("\n".join(log_message_parts))
        self._update_status_label_based_on_state() # Update status at the end of check

    def toggle_auto_mode(self):
        self.auto_mode_enabled = not self.auto_mode_enabled
        self.update_menu_callback(self.auto_mode_enabled) # Notify MenuBarApp to update menu item state
        status_message = "enabled" if self.auto_mode_enabled else "disabled"
        self.notify_ui_callback("OAK-D Auto Control", "Setting Changed", f"Auto Camera Control has been {status_message}.")
        
        if self.auto_mode_enabled:
            # 自動モードが有効になった場合
            # 既にデバイスが安定して接続されており、かつカメラが起動していない場合は、カメラを起動する
            if self.last_stable_device_state and not self.camera_running:
                self.notify_ui_callback("OAK-D Auto Control", "Starting Camera (Manual Enable)", "Auto mode enabled, device connected, starting camera.")
                self.start_camera_action()
            else:
                # 上記条件に合致しない場合は、通常の接続チェックに任せる
                # (デバイス未接続の場合や、既にカメラ起動中の場合など)
                self.check_device_connection() # これにより接続状態の変化を待つ
        elif not self.auto_mode_enabled and self.camera_running:
            # 自動モードが無効になり、かつカメラが起動している場合は停止する
            self.notify_ui_callback("OAK-D Auto Control", "Stopping Camera", "Auto mode disabled, stopping camera.")
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
        if hasattr(self, 'device_check_timer') and self.device_check_timer.is_alive():
            self.device_check_timer.stop()

        if self.camera_running and self.uvc_process:
            print("DCM: Stopping camera before quitting...")
            try:
                self.uvc_process.send_signal(signal.SIGINT)
                self.uvc_process.wait(timeout=10)
                print("DCM: Camera stopped via subprocess.")
            except subprocess.TimeoutExpired:
                print("DCM: Timeout stopping camera on quit. Terminating...")
                self.uvc_process.terminate()
                try:
                    self.uvc_process.wait(timeout=5)
                except Exception:
                    pass # Ignore error during forced termination wait
            except Exception as e:
                print(f"DCM: Error stopping camera on quit: {e}")
                if self.uvc_process:
                    try:
                        self.uvc_process.terminate()
                        self.uvc_process.wait(timeout=2)
                    except Exception:
                        pass
            finally:
                self.uvc_process = None
                self.camera_running = False
