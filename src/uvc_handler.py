#!/usr/bin/env python3

import time
import argparse
import os
import depthai as dai

def getMinimalPipeline():
    pipeline = dai.Pipeline()
    cam_rgb = pipeline.createColorCamera()
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam_rgb.setInterleaved(False)
    cam_rgb.setFps(30)

    uvc = pipeline.createUVC()
    cam_rgb.video.link(uvc.input)

    board_config = dai.BoardConfig()
    uvc_board_settings = dai.BoardConfig.UVC(1920, 1080)
    uvc_board_settings.frameType = dai.ImgFrame.Type.NV12
    uvc_board_settings.cameraName = "MinimalUVCCam_1080p"
    board_config.uvc = uvc_board_settings
    pipeline.setBoardConfig(board_config)
    return pipeline

def getPipeline():
    enable_4k = True

    pipeline = dai.Pipeline()

    # Define a source - color camera
    cam_rgb = pipeline.createColorCamera()
    cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam_rgb.setInterleaved(False)

    if enable_4k:
        cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_4_K)
        cam_rgb.setIspScale(1, 2)
    else:
        cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_720_P)

    # Create an UVC (USB Video Class) output node
    uvc = pipeline.createUVC()
    cam_rgb.video.link(uvc.input)

    # Note: if the pipeline is sent later to device (using startPipeline()),
    # it is important to pass the device config separately when creating the device
    config = dai.Device.Config()

    board_config = dai.BoardConfig()
    uvc_board_settings = dai.BoardConfig.UVC(1920, 1080)
    uvc_board_settings.frameType = dai.ImgFrame.Type.NV12
    uvc_board_settings.cameraName = "FlashedCam_1080p_NV12"
    board_config.uvc = uvc_board_settings

    # パイプラインにBoardConfigを設定
    pipeline.setBoardConfig(board_config)

    return pipeline


class UVCCamera:
    def __init__(self, pipeline_func, device_config=None):
        self.pipeline_func = pipeline_func
        self.device_config = device_config
        self.device = None
        self.pipeline = None

    def start(self):
        self.pipeline = self.pipeline_func()
        if self.device_config:
            # If a device_config is provided, use it for device initialization
            # This is typically used when specific UVC settings are needed before pipeline start
            self.device = dai.Device(self.device_config)
            self.device.startPipeline(self.pipeline)
        else:
            # If no device_config is provided, assume pipeline contains all config
            # or we are using default device settings.
            # This branch might need adjustment based on how dai.Device behaves
            # when device_config is None but pipeline has board config.
            # For run_uvc_device, we pass a config.
            self.device = dai.Device()
            self.device.startPipeline(self.pipeline)


    def stop(self):
        if self.device is not None and not self.device.isClosed():
            self.device.close()
            self.device = None

# Will flash the bootloader if no pipeline is provided as argument
def flash(pipeline=None):
    (f, bl) = dai.DeviceBootloader.getFirstAvailableDevice()
    if bl is None:
        print("No DepthAI device found in bootloader mode. Please hold BOOT button and reset the device.")
        return

    bootloader = dai.DeviceBootloader(bl, True)

    # Create a progress callback lambda
    progress = lambda p : print(f'Flashing progress: {p*100:.1f}%')

    startTime = time.monotonic()
    if pipeline is None:
        print("Flashing bootloader...")
        bootloader.flashBootloader(progress)
    else:
        print("Flashing application pipeline...")
        bootloader.flash(progress, pipeline)

    elapsedTime = round(time.monotonic() - startTime, 2)
    print("Done in", elapsedTime, "seconds")

def handle_flash_bootloader():
    flash()
    print("Flashing successful. Please power-cycle the device")

def handle_flash_app():
    flash(getMinimalPipeline)
    print("Flashing successful. Please power-cycle the device")

def handle_load_and_exit():
    os.environ["DEPTHAI_WATCHDOG"] = "0"

    device_config = dai.Device.Config()
    device_config.board.uvc = dai.BoardConfig.UVC(1920, 1080)
    device_config.board.uvc.frameType = dai.ImgFrame.Type.NV12

    device = dai.Device(device_config, getPipeline())

    print("\nDevice started. Attempting to force-terminate this process...")
    print("Open an UVC viewer to check the camera stream.")
    print("To reconnect with depthai, a device power-cycle may be required in some cases")
    import signal
    os.kill(os.getpid(), signal.SIGTERM)


def run_uvc_device():
    # Standard UVC load with depthai (オプションなしの場合)
    device_config_main = dai.Device.Config()
    device_config_main = dai.Device.Config()
    device_config_main.board.uvc = dai.BoardConfig.UVC(1920, 1080)
    device_config_main.board.uvc.frameType = dai.ImgFrame.Type.NV12

    camera = UVCCamera(pipeline_func=getMinimalPipeline, device_config=device_config_main)

    try:
        camera.start()
        print("\nDevice started, please keep this process running")
        print("and open an UVC viewer to check the camera stream.")
        print("\nTo close: Ctrl+C")

        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interrupted, stopping camera...")
    finally:
        camera.stop()
        print("Camera stopped.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-fb', '--flash-bootloader', default=False, action="store_true")
    parser.add_argument('-f',  '--flash-app',        default=False, action="store_true")
    parser.add_argument('-l',  '--load-and-exit',    default=False, action="store_true")
    parser.add_argument('--start-uvc', default=False, action="store_true", help="Start UVC camera mode (for menu bar app)")
    args = parser.parse_args()

    if args.flash_bootloader and args.flash_app:
        print("Error: Cannot flash bootloader and application simultaneously.")
        print("Please run with either -fb or -f.")
        return

    if args.flash_bootloader:
        handle_flash_bootloader()
    elif args.flash_app:
        handle_flash_app()
    elif args.load_and_exit:
        handle_load_and_exit()
    elif args.start_uvc:
        run_uvc_device()
    else:
        # デフォルトの動作（引数なし、または他のフラグが指定されていない場合）
        # ここでは、引数なしの場合も run_uvc_device() を呼ぶか、
        # 何もしないか（メニューバーからの起動専用とするか）を選択できる。
        # 既存の挙動を維持するため、run_uvc_device() を呼ぶ。
        # ただし、メニューバーアプリからは必ず --start-uvc をつける想定。
        if not any(vars(args).values()): # いずれのフラグもFalseの場合
            run_uvc_device()
        # 他のフラグが指定されている場合は、その処理のみ実行される

if __name__ == "__main__":
    main()
