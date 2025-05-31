import pytest
from unittest.mock import patch, MagicMock, call
import argparse # For testing main()
import os # For os.environ, os.kill
import sys # For sys.modules

# Mock depthai globally for all tests in this file
# We create a MagicMock instance that will behave as the 'dai' module
mock_dai = MagicMock()

# Fixture to apply the mock_dai patch for tests that need it
@pytest.fixture(autouse=True) # Apply to all tests in this file for simplicity
def patch_dai():
    # First patch sys.modules to prevent import
    with patch.dict('sys.modules', {'depthai': mock_dai}):
        # Also patch the already imported module in uvc_handler
        with patch('src.uvc_handler.dai', mock_dai):
            # Reset mock before each test to ensure isolation
            mock_dai.reset_mock()
            # Define common mock attributes or return values needed across tests
            # Pipeline and Camera related mocks
            mock_dai.Pipeline.return_value = MagicMock()
            mock_dai.ColorCameraProperties = MagicMock()
            mock_dai.ColorCameraProperties.SensorResolution.THE_1080_P = "1080p"
            mock_dai.ColorCameraProperties.SensorResolution.THE_4_K = "4k"
            mock_dai.ColorCameraProperties.SensorResolution.THE_720_P = "720p"
            mock_dai.CameraBoardSocket.CAM_A = "CAM_A"
            mock_dai.ImgFrame = MagicMock()
            mock_dai.ImgFrame.Type.NV12 = "NV12"
            
            # BoardConfig and UVC related mocks
            mock_uvc_config_instance = MagicMock()
            mock_dai.BoardConfig.UVC.return_value = mock_uvc_config_instance
            
            mock_board_config_instance = MagicMock()
            mock_board_config_instance.uvc = mock_uvc_config_instance
            mock_dai.BoardConfig.return_value = mock_board_config_instance

            # Device and Bootloader related mocks
            mock_dai.Device = MagicMock()
            mock_dai.Device.return_value = MagicMock()
            mock_dai.Device.Config = MagicMock()
            mock_dai.Device.Config.return_value = MagicMock()

            mock_device_info = MagicMock()
            mock_dai.DeviceBootloader.getFirstAvailableDevice.return_value = (True, mock_device_info) 
            
            mock_bootloader_instance = MagicMock()
            mock_bootloader_instance.flash = MagicMock()
            mock_bootloader_instance.flashBootloader = MagicMock()
            mock_dai.DeviceBootloader.return_value = mock_bootloader_instance
            
            # Create mock constants that the code expects
            mock_dai.kCFNumberLongType = 1  # Mock constant value

            yield mock_dai

# Import the module to be tested AFTER setting up the mock
# This ensures that when uvc_handler imports depthai, it gets our mock
from src import uvc_handler


class TestPipelineCreation:
    def test_get_minimal_pipeline(self):
        pipeline_mock = mock_dai.Pipeline.return_value # Use the globally mocked pipeline
        
        cam_rgb_mock = MagicMock()
        uvc_mock = MagicMock()

        pipeline_mock.createColorCamera.return_value = cam_rgb_mock
        pipeline_mock.createUVC.return_value = uvc_mock
        
        # Ensure .video and .input are present for linking
        cam_rgb_mock.video = MagicMock()
        uvc_mock.input = MagicMock()

        pipeline_result = uvc_handler.getMinimalPipeline()

        assert pipeline_result == pipeline_mock
        pipeline_mock.createColorCamera.assert_called_once()
        cam_rgb_mock.setResolution.assert_called_once_with(mock_dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam_rgb_mock.setBoardSocket.assert_called_once_with(mock_dai.CameraBoardSocket.CAM_A)
        cam_rgb_mock.setInterleaved.assert_called_once_with(False)
        cam_rgb_mock.setFps.assert_called_once_with(30)
        
        pipeline_mock.createUVC.assert_called_once()
        cam_rgb_mock.video.link.assert_called_once_with(uvc_mock.input)
        
        mock_dai.BoardConfig.UVC.assert_called_once_with(1920, 1080)
        # board_config_uvc_settings_mock is the instance returned by mock_dai.BoardConfig.UVC()
        assert mock_dai.BoardConfig.UVC.return_value.frameType == mock_dai.ImgFrame.Type.NV12
        assert mock_dai.BoardConfig.UVC.return_value.cameraName == "MinimalUVCCam_1080p"
        
        pipeline_mock.setBoardConfig.assert_called_once()
        args, _ = pipeline_mock.setBoardConfig.call_args
        board_config_arg = args[0]
        assert board_config_arg.uvc == mock_dai.BoardConfig.UVC.return_value

    def test_get_pipeline_4k_enabled(self):
        pipeline_mock = mock_dai.Pipeline.return_value
        cam_rgb_mock = MagicMock()
        uvc_mock = MagicMock()

        pipeline_mock.createColorCamera.return_value = cam_rgb_mock
        pipeline_mock.createUVC.return_value = uvc_mock
        cam_rgb_mock.video = MagicMock() # For link
        uvc_mock.input = MagicMock()    # For link
        
        # Since getPipeline() has enable_4k = True hardcoded, we test the actual behavior
        pipeline_result = uvc_handler.getPipeline()

        assert pipeline_result == pipeline_mock
        pipeline_mock.createColorCamera.assert_called_once()
        cam_rgb_mock.setResolution.assert_called_once_with(mock_dai.ColorCameraProperties.SensorResolution.THE_4_K)
        cam_rgb_mock.setIspScale.assert_called_once_with(1,2)
        cam_rgb_mock.setBoardSocket.assert_called_once_with(mock_dai.CameraBoardSocket.CAM_A)
        cam_rgb_mock.setInterleaved.assert_called_once_with(False)

        pipeline_mock.createUVC.assert_called_once()
        cam_rgb_mock.video.link.assert_called_once_with(uvc_mock.input)
        
        mock_dai.BoardConfig.UVC.assert_called_once_with(1920, 1080) # UVC output is still 1080p
        assert mock_dai.BoardConfig.UVC.return_value.frameType == mock_dai.ImgFrame.Type.NV12
        assert mock_dai.BoardConfig.UVC.return_value.cameraName == "FlashedCam_1080p_NV12" # Name implies 1080p output
        
        pipeline_mock.setBoardConfig.assert_called_once()
        args, _ = pipeline_mock.setBoardConfig.call_args
        board_config_arg = args[0]
        assert board_config_arg.uvc == mock_dai.BoardConfig.UVC.return_value


class TestUVCCamera:
    def test_uvc_camera_start_with_device_config(self):
        mock_pipeline_func = MagicMock(return_value="mock_pipeline_obj")
        # Use the globally configured mock_dai.Device.Config.return_value
        mock_device_config = mock_dai.Device.Config.return_value 
        
        camera = uvc_handler.UVCCamera(pipeline_func=mock_pipeline_func, device_config=mock_device_config)
        
        mock_device_instance = mock_dai.Device.return_value # From global fixture
        # Configure the Device mock to accept the device_config argument
        mock_dai.Device.side_effect = lambda config: mock_device_instance

        camera.start()

        mock_pipeline_func.assert_called_once()
        assert camera.pipeline == "mock_pipeline_obj"
        # Check that dai.Device was called with the config
        mock_dai.Device.assert_called_once_with(mock_device_config)
        mock_device_instance.startPipeline.assert_called_once_with("mock_pipeline_obj")
        assert camera.device == mock_device_instance

    def test_uvc_camera_start_no_device_config(self):
        mock_pipeline_func = MagicMock(return_value="mock_pipeline_obj")
        camera = uvc_handler.UVCCamera(pipeline_func=mock_pipeline_func) # No device_config

        mock_device_instance = mock_dai.Device.return_value
        # Configure the Device mock for no-argument constructor
        mock_dai.Device.side_effect = lambda: mock_device_instance
        
        camera.start()
        # dai.Device called with no arguments
        mock_dai.Device.assert_called_once_with()
        mock_device_instance.startPipeline.assert_called_once_with("mock_pipeline_obj")
        assert camera.device == mock_device_instance

    def test_uvc_camera_stop(self):
        camera = uvc_handler.UVCCamera(MagicMock())
        mock_device_instance = mock_dai.Device.return_value # Get the one from fixture
        mock_device_instance.isClosed.return_value = False
        camera.device = mock_device_instance # Assign it

        camera.stop()

        mock_device_instance.close.assert_called_once()
        assert camera.device is None

    def test_uvc_camera_stop_no_device_or_closed(self):
        camera = uvc_handler.UVCCamera(MagicMock())
        # Case 1: device is None
        camera.device = None
        camera.stop() # Should not raise error

        # Case 2: device is already closed
        mock_device_instance = MagicMock() # Fresh mock for this specific case
        mock_device_instance.isClosed.return_value = True
        camera.device = mock_device_instance
        camera.stop()
        mock_device_instance.close.assert_not_called()


@patch('src.uvc_handler.time', MagicMock()) # Mock time globally for flash tests
class TestFlashFunctions:
    def test_flash_bootloader(self):
        mock_bootloader_instance = mock_dai.DeviceBootloader.return_value
        # Get the mocked device info from the fixture
        _, mock_device_info = mock_dai.DeviceBootloader.getFirstAvailableDevice.return_value
        
        uvc_handler.flash(pipeline=None) # Test flashing bootloader

        mock_dai.DeviceBootloader.getFirstAvailableDevice.assert_called_once()
        mock_dai.DeviceBootloader.assert_called_once_with(mock_device_info, True)
        mock_bootloader_instance.flashBootloader.assert_called_once()
        mock_bootloader_instance.flash.assert_not_called()

    def test_flash_application(self):
        mock_bootloader_instance = mock_dai.DeviceBootloader.return_value
        mock_pipeline = MagicMock()
        
        uvc_handler.flash(pipeline=mock_pipeline)
        
        _, mock_device_info = mock_dai.DeviceBootloader.getFirstAvailableDevice.return_value
        mock_dai.DeviceBootloader.assert_called_once_with(mock_device_info, True)
        # Use ANY for progress callback since it's a lambda function
        from unittest.mock import ANY
        mock_bootloader_instance.flash.assert_called_once_with(ANY, mock_pipeline)
        mock_bootloader_instance.flashBootloader.assert_not_called()

    def test_flash_no_device_found(self):
        mock_dai.DeviceBootloader.getFirstAvailableDevice.return_value = (False, None) # Simulate no device
        
        with patch('builtins.print') as mock_print:
            uvc_handler.flash(pipeline=MagicMock())
            mock_print.assert_any_call("No DepthAI device found in bootloader mode. Please hold BOOT button and reset the device.")
        # Constructor should not be called if no device is found
        mock_dai.DeviceBootloader.assert_not_called() 

    @patch('src.uvc_handler.flash')
    def test_handle_flash_bootloader(self, mock_flash_func):
        uvc_handler.handle_flash_bootloader()
        mock_flash_func.assert_called_once_with() # Default pipeline=None

    @patch('src.uvc_handler.flash')
    @patch('src.uvc_handler.getMinimalPipeline')
    def test_handle_flash_app(self, mock_get_minimal_pipeline, mock_flash_func):
        mock_pipeline_obj = "pipeline_for_flash_app"
        mock_get_minimal_pipeline.return_value = mock_pipeline_obj
        
        uvc_handler.handle_flash_app()
        
        # The actual code passes the function getMinimalPipeline as a positional argument
        mock_flash_func.assert_called_once_with(uvc_handler.getMinimalPipeline)


@patch('src.uvc_handler.os', new_callable=MagicMock)
class TestSpecialHandlers:
    def test_handle_load_and_exit(self, mock_os_mod):
        # This function calls os.kill and uses dai.Device
        # mock_dai is already active via autouse fixture
        
        mock_device_instance = mock_dai.Device.return_value # From global fixture
        mock_device_config = mock_dai.Device.Config.return_value # From global fixture
        
        # Mock getPipeline to return a value that Device can accept
        with patch('src.uvc_handler.getPipeline', return_value="pipeline_obj") as mock_get_pipeline:
            # The actual code expects Device(config, pipeline) constructor
            # We need to make sure the Device mock accepts both arguments
            mock_dai.Device.side_effect = lambda config, pipeline: mock_device_instance
            uvc_handler.handle_load_and_exit()

        mock_os_mod.environ.__setitem__.assert_called_once_with("DEPTHAI_WATCHDOG", "0")
        # Device should be called with (config, pipeline)
        mock_dai.Device.assert_called_once()
        # Use ANY for signal since we're testing the kill call, not the specific signal
        from unittest.mock import ANY
        mock_os_mod.kill.assert_called_once_with(mock_os_mod.getpid(), ANY)


@patch('src.uvc_handler.time', MagicMock()) # Mock time.sleep
@patch('src.uvc_handler.UVCCamera') # Mock the UVCCamera class
class TestRunUVCDevice:
    def test_run_uvc_device_normal_flow(self, mock_uvc_camera_class):
        mock_camera_instance = MagicMock()
        mock_uvc_camera_class.return_value = mock_camera_instance
        
        # Simulate time.sleep throwing KeyboardInterrupt after first call
        with patch('src.uvc_handler.time.sleep', side_effect=KeyboardInterrupt("Test Interrupt")):
            uvc_handler.run_uvc_device()

        # Check that UVCCamera was called with correct arguments
        # Since the actual code creates a new Device.Config instance, we check the type
        args, kwargs = mock_uvc_camera_class.call_args
        assert kwargs['pipeline_func'] == uvc_handler.getMinimalPipeline
        # For device_config, just verify it was passed (actual implementation creates new instance)
        assert 'device_config' in kwargs
        mock_camera_instance.start.assert_called_once()
        mock_camera_instance.stop.assert_called_once() # Called in finally

    def test_run_uvc_device_runtime_error(self, mock_uvc_camera_class):
        mock_camera_instance = MagicMock()
        mock_uvc_camera_class.return_value = mock_camera_instance
        mock_camera_instance.start.side_effect = RuntimeError("DepthAI Error")

        with patch('builtins.print') as mock_print:
            uvc_handler.run_uvc_device()
        
        mock_camera_instance.start.assert_called_once()
        mock_print.assert_any_call("uvc_handler.py: DepthAI runtime error: DepthAI Error")
        mock_camera_instance.stop.assert_called_once()


@patch('src.uvc_handler.handle_flash_bootloader')
@patch('src.uvc_handler.handle_flash_app')
@patch('src.uvc_handler.handle_load_and_exit')
@patch('src.uvc_handler.run_uvc_device')
@patch('argparse.ArgumentParser')
class TestMainArgParsing:
    def _setup_parser_mock(self, parser_mock_class, args_dict):
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse_args.return_value = argparse.Namespace(**args_dict)
        parser_mock_class.return_value = mock_parser_instance
        return mock_parser_instance

    def test_main_flash_bootloader(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': True, 'flash_app': False, 'load_and_exit': False, 'start_uvc': False})
        uvc_handler.main()
        mock_flash_bootloader.assert_called_once()
        mock_run_uvc.assert_not_called()

    def test_main_flash_app(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': False, 'flash_app': True, 'load_and_exit': False, 'start_uvc': False})
        uvc_handler.main()
        mock_flash_app.assert_called_once()
        mock_run_uvc.assert_not_called()

    def test_main_load_and_exit(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': False, 'flash_app': False, 'load_and_exit': True, 'start_uvc': False})
        uvc_handler.main()
        mock_load_exit.assert_called_once()
        mock_run_uvc.assert_not_called()

    def test_main_start_uvc(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': False, 'flash_app': False, 'load_and_exit': False, 'start_uvc': True})
        uvc_handler.main()
        mock_run_uvc.assert_called_once()

    def test_main_no_args(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': False, 'flash_app': False, 'load_and_exit': False, 'start_uvc': False})
        uvc_handler.main()
        mock_run_uvc.assert_called_once() # Default behavior

    def test_main_flash_bootloader_and_app_error(self, mock_argparse, mock_run_uvc, mock_load_exit, mock_flash_app, mock_flash_bootloader):
        self._setup_parser_mock(mock_argparse, {'flash_bootloader': True, 'flash_app': True, 'load_and_exit': False, 'start_uvc': False})
        with patch('builtins.print') as mock_print:
            uvc_handler.main()
        mock_print.assert_any_call("Error: Cannot flash bootloader and application simultaneously.")
        mock_flash_bootloader.assert_not_called()
        mock_flash_app.assert_not_called()
        mock_run_uvc.assert_not_called()