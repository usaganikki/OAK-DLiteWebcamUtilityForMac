import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from queue import Queue
import subprocess
import logging

# conftest.py で sys.path にプロジェクトルートが追加されていることを期待
try:
    # CameraManager の代わりに DeviceConnectionManager をテスト対象とする
    from src.device_connection_manager import DeviceConnectionManager, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID
except ImportError as e:
    logging.error(f"必要なモジュールのインポートに失敗しました: {e}")
    logging.error("プロジェクトルートが sys.path に正しく追加されているか、またはモジュールパスが正しいか確認してください。")
    DeviceConnectionManager = MagicMock(name="FallbackDeviceConnectionManager")
    OAK_D_LITE_VENDOR_ID = 0x03e7 # フォールバック値
    OAK_D_LITE_PRODUCT_ID = 0x2485 # フォールバック値


# このテストファイル全体に 'camera_lifecycle' マーカーを適用
pytestmark = pytest.mark.camera_lifecycle

class TestCameraLifecycle:
    """カメラの接続・切断ライフサイクルのシステムテスト"""
    
    @pytest.fixture
    def dcm(self, mock_iokit_wrapper): # mock_iokit_wrapperをフィクスチャとして受け取る
        """DeviceConnectionManagerのフィクスチャ"""
        mock_notify_ui = MagicMock()
        mock_alert_ui = MagicMock()
        mock_update_menu = MagicMock()
        mock_update_status_label = MagicMock()
        
        try:
            # DeviceConnectionManagerの初期化時に _start_iokit_monitoring が呼ばれ、
            # その中で mock_iokit_wrapper.init_usb_monitoring が呼ばれる
            manager = DeviceConnectionManager(
                notify_ui_callback=mock_notify_ui,
                alert_ui_callback=mock_alert_ui,
                update_menu_callback=mock_update_menu,
                update_status_label_callback=mock_update_status_label
            )
            # init_usb_monitoring が呼ばれたことを確認
            mock_iokit_wrapper.init_usb_monitoring.assert_called_once()
            # コールバックハンドラが設定されたことを確認
            assert mock_iokit_wrapper.g_python_callback_handler is not None
            assert mock_iokit_wrapper.g_python_callback_handler == manager._event_handler
            return manager
        except Exception as e:
            pytest.fail(f"DeviceConnectionManagerの初期化に失敗しました: {e}")
    
    @pytest.fixture
    def mock_iokit_wrapper(self):
        """IOKitWrapperのモックフィクスチャ。
        src.iokit_wrapper モジュール内の関数をモックします。
        """
        # IOKitWrapperはクラスではなく、関数ベースのモジュールとして扱われているため、
        # モックする対象は 'src.iokit_wrapper' モジュール自体か、その中の主要な関数になります。
        # ここでは、DeviceMonitorが使用するであろう関数をモックします。
        
        mock_wrapper_module = MagicMock()
        
        # init_usb_monitoring のモック設定
        # この関数はコールバックハンドラとVID/PIDを受け取り、run loop sourceのアドレス(整数)を返す
        mock_wrapper_module.init_usb_monitoring = MagicMock(return_value=12345) # ダミーのsource_addr
        mock_wrapper_module.g_python_callback_handler = None # コールバックを保存するため
        
        def _mock_init_usb_monitoring(callback_handler, vid, pid):
            logging.info(f"mock_iokit_wrapper: init_usb_monitoring called with callback={callback_handler}, VID={vid}, PID={pid}")
            mock_wrapper_module.g_python_callback_handler = callback_handler
            mock_wrapper_module.monitoring_active = True
            return 12345 # ダミーのsource_addr
        
        mock_wrapper_module.init_usb_monitoring.side_effect = _mock_init_usb_monitoring

        # stop_usb_monitoring のモック設定
        mock_wrapper_module.stop_usb_monitoring = MagicMock()
        def _mock_stop_usb_monitoring():
            logging.info("mock_iokit_wrapper: stop_usb_monitoring called")
            mock_wrapper_module.monitoring_active = False
            mock_wrapper_module.g_python_callback_handler = None
        mock_wrapper_module.stop_usb_monitoring.side_effect = _mock_stop_usb_monitoring
        
        mock_wrapper_module.monitoring_active = False

        # add_run_loop_source_to_main_loop / remove_run_loop_source_from_main_loop のモック
        mock_wrapper_module.add_run_loop_source_to_main_loop = MagicMock(return_value=True)
        mock_wrapper_module.remove_run_loop_source_from_main_loop = MagicMock(return_value=True)

        # IOKitError 例外もモックモジュールに属性として持たせておく
        # これにより、 from src.iokit_wrapper import IOKitError のようなインポートがテスト内で機能する
        mock_wrapper_module.IOKitError = type('MockIOKitError', (Exception,), {})

        # 'src.iokit_wrapper' をこのモックオブジェクトでパッチします。
        # src.device_connection_manager モジュール内で iokit_wrapper がインポートされているため、
        # パッチターゲットは 'src.device_connection_manager.iokit_wrapper' となります。
        with patch('src.device_connection_manager.iokit_wrapper', mock_wrapper_module, create=True) as patched_module:
            # create=True は、モジュールや属性が存在しない場合にエラーにせずMagicMockを作成します。
            # これにより、テスト対象のコードがリファクタリングされても、ある程度テストが通りやすくなります。
            # (ただし、パッチする対象が存在することが望ましい)
            yield patched_module # patched_module は mock_wrapper_module と同じオブジェクト

    def test_dcm_initial_state(self, dcm):
        """DeviceConnectionManagerの初期状態テスト"""
        # Given: DeviceConnectionManagerが初期化されている
        assert dcm is not None, "DeviceConnectionManagerが初期化されていません"
        
        # Then: 初期状態の確認
        assert dcm.get_camera_running_status() is False, "初期状態でカメラが動作中になっています"
        assert dcm.connected_target_device_info is None, "初期状態でデバイス情報が設定されています"
        assert dcm.auto_mode_enabled is True, "初期状態でオートモードが無効になっています"
        # mock_iokit_wrapper.init_usb_monitoring が呼ばれたことは dcm フィクスチャ内でアサート済み

    @pytest.mark.parametrize("connection_scenario", [
        "connect_then_disconnect",
        "multiple_connect_disconnect",
        "rapid_connect_disconnect"
    ])
    def test_dcm_connection_scenarios(self, dcm, mock_iokit_wrapper, connection_scenario):
        """様々な接続シナリオのテスト (DeviceConnectionManager対象)"""
        
        callback_handler = mock_iokit_wrapper.g_python_callback_handler
        assert callback_handler is not None, "コールバックハンドラがiokit_wrapperに設定されていません。"
        assert callback_handler == dcm._event_handler, "設定されたコールバックハンドラがDCMのイベントハンドラと一致しません。"

        # start_camera_action と stop_camera_action をモックして、サブプロセス起動を避ける
        # 各テストシナリオの前にリセットする必要があるため、ここで MagicMock インスタンスを割り当てる
        dcm.start_camera_action = MagicMock(side_effect=lambda: setattr(dcm, 'camera_running', True))
        dcm.stop_camera_action = MagicMock(side_effect=lambda: setattr(dcm, 'camera_running', False))

        if connection_scenario == "connect_then_disconnect":
            self._test_dcm_simple_connect_disconnect(dcm, callback_handler)
        elif connection_scenario == "multiple_connect_disconnect":
            self._test_dcm_multiple_cycles(dcm, callback_handler)
        elif connection_scenario == "rapid_connect_disconnect":
            self._test_dcm_rapid_cycles(dcm, callback_handler)

    # Helper methods for connection scenarios, targeting DeviceConnectionManager
    def _test_dcm_simple_connect_disconnect(self, dcm, event_handler):
        """単純な接続→切断テスト (DeviceConnectionManager対象)"""
        
        # Given: 初期状態
        # camera_running の初期状態は dcm フィクスチャで確認済み、またはテスト開始時にリセットされる
        assert dcm.connected_target_device_info is None

        # When: カメラ接続イベントをシミュレート (event_handlerのメソッドを直接呼び出す)
        test_serial_number = 'test_sn_001'
        test_service_id = 123456789
        
        try:
            event_handler.on_device_connected(
                OAK_D_LITE_VENDOR_ID,
                OAK_D_LITE_PRODUCT_ID,
                test_serial_number,
                test_service_id
            )
        except Exception as e:
            pytest.fail(f"event_handler.on_device_connected でエラー: {e}")
        
        # Then: カメラが認識され、関連情報が更新される
        # DeviceConnectionManager は camera_running を直接 True にせず、start_camera_action を呼ぶ
        # start_camera_action が成功すると camera_running が True になる想定
        # ここでは start_camera_action が呼ばれたことを確認
        dcm.start_camera_action.assert_called_once()
        # start_camera_action が呼ばれ、その side_effect で camera_running が True になることを期待
        dcm.start_camera_action.assert_called_once()
        assert dcm.get_camera_running_status() is True, "カメラ接続後、camera_running が True になっていません"
        assert dcm.connected_target_device_info is not None
        assert dcm.connected_target_device_info['vendor_id'] == OAK_D_LITE_VENDOR_ID
        assert dcm.connected_target_device_info['product_id'] == OAK_D_LITE_PRODUCT_ID
        assert dcm.connected_target_device_info['serial_number'] == test_serial_number
        assert dcm.connected_target_device_info['service_id'] == test_service_id
        logging.info(f"カメラ接続後 (DCM): {dcm.connected_target_device_info}, camera_running (mocked call): {dcm.start_camera_action.called}")

        # When: カメラ切断イベントをシミュレート
        try:
            event_handler.on_device_disconnected(
                OAK_D_LITE_VENDOR_ID,
                OAK_D_LITE_PRODUCT_ID,
                test_serial_number, # 切断時もSNが渡されると仮定
                test_service_id # 切断時もService IDが渡されると仮定
            )
        except Exception as e:
            pytest.fail(f"event_handler.on_device_disconnected でエラー: {e}")
        
        # Then: カメラ情報がクリアされ、関連処理が呼ばれる
        dcm.stop_camera_action.assert_called_once()
        # stop_camera_action が呼ばれ、その side_effect で camera_running が False になることを期待
        dcm.stop_camera_action.assert_called_once()
        assert dcm.get_camera_running_status() is False, "カメラ切断後、camera_running が False になっていません"
        assert dcm.connected_target_device_info is None
        logging.info(f"カメラ切断後 (DCM): connected_info is None, camera_running is False, stop_camera_action called: {dcm.stop_camera_action.called}")


    def _test_dcm_multiple_cycles(self, dcm, event_handler):
        """複数回の接続・切断サイクルテスト (DeviceConnectionManager対象)"""
        num_cycles = 3
        
        for cycle in range(num_cycles):
            logging.info(f"Multiple Cycles - Cycle {cycle + 1}/{num_cycles} - Connect")
            test_serial_number = f'test_sn_cycle_{cycle:03d}'
            test_service_id = 1000 + cycle

            # Reset mock call counts for each cycle for start/stop actions
            dcm.start_camera_action.reset_mock()
            dcm.stop_camera_action.reset_mock()

            # 接続
            event_handler.on_device_connected(
                OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, test_serial_number, test_service_id
            )
            dcm.start_camera_action.assert_called_once()
            assert dcm.connected_target_device_info['serial_number'] == test_serial_number
            time.sleep(0.05)  # 短い待機

            # 切断
            logging.info(f"Multiple Cycles - Cycle {cycle + 1}/{num_cycles} - Disconnect")
            event_handler.on_device_disconnected(
                OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, test_serial_number, test_service_id
            )
            dcm.stop_camera_action.assert_called_once()
            # disconnected_target_device_info は None になるはずだが、
            # 別のデバイスが接続されたままのケースも考慮すると、特定のSN/IDが消えたことを確認するのがより正確。
            # ここでは単純化のため、最後にNoneになることを期待。
            # assert dcm.connected_target_device_info is None # 最終サイクル後で確認
            time.sleep(0.05)
        
        # 最終状態確認
        assert dcm.connected_target_device_info is None, "複数サイクル後、デバイス情報がクリアされていません。"
        # start/stop_camera_action の総呼び出し回数を確認
        # (各サイクルで1回ずつ呼ばれるはずだが、dcmフィクスチャでリセットされるため、ここでは個別のサイクルで確認済み)

    def _test_dcm_rapid_cycles(self, dcm, event_handler):
        """高速な接続・切断サイクルテスト (DeviceConnectionManager対象)"""
        num_cycles = 10
        test_serial_number = 'test_sn_rapid'
        test_service_id_base = 2000

        for i in range(num_cycles):
            logging.info(f"Rapid Cycles - Cycle {i + 1}/{num_cycles}")
            current_service_id = test_service_id_base + i

            dcm.start_camera_action.reset_mock()
            dcm.stop_camera_action.reset_mock()

            # 高速で接続・切断を繰り返す
            event_handler.on_device_connected(
                OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, test_serial_number, current_service_id
            )
            # 接続直後に切断イベントが来ても、start_camera_actionは呼ばれるはず
            dcm.start_camera_action.assert_called_once()
            
            event_handler.on_device_disconnected(
                OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID, test_serial_number, current_service_id
            )
            # 切断イベントにより stop_camera_action が呼ばれるはず
            dcm.stop_camera_action.assert_called_once()
        
        # システムが安定していることを確認 (最終的にデバイス情報がクリアされていること)
        time.sleep(0.1) # 短い待機で状態が落ち着くのを待つ
        assert dcm.connected_target_device_info is None, "高速サイクル後、デバイス情報がクリアされていません。"
    
    # test_concurrent_device_operations (Phase 2以降で検討)
    # def test_concurrent_device_operations(self, camera_manager):
    #     pytest.skip("Phase 2以降で検討・実装予定")
    #     # ... (サンプルコード参照)

    def test_dcm_error_handling_init_monitoring_failure(self, mock_iokit_wrapper):
        """iokit_wrapper.init_usb_monitoring が失敗した場合のエラーハンドリングテスト"""
        # Given: iokit_wrapper.init_usb_monitoring が IOKitError を送出するように設定
        # mock_iokit_wrapper はフィクスチャなので、テストメソッド内で直接変更するのではなく、
        # このテストケース専用のDCMインスタンスをここで作成し、
        # その初期化中にエラーが発生することを確認する。
        
        # mock_iokit_wrapper の init_usb_monitoring を上書きしてエラーを発生させる
        mock_iokit_wrapper.init_usb_monitoring.side_effect = mock_iokit_wrapper.IOKitError("Simulated IOKit Init Error")
        
        mock_notify_ui = MagicMock()
        mock_alert_ui = MagicMock()
        mock_update_menu = MagicMock()
        mock_update_status_label = MagicMock()

        # When: DeviceConnectionManagerを初期化
        try:
            dcm_instance = DeviceConnectionManager(
                notify_ui_callback=mock_notify_ui,
                alert_ui_callback=mock_alert_ui,
                update_menu_callback=mock_update_menu,
                update_status_label_callback=mock_update_status_label
            )
            # DeviceConnectionManager の _start_iokit_monitoring 内で例外がキャッチされ、
            # alert_ui_callback が呼ばれることを期待。例外は外に伝播しないはず。
        except Exception as e:
            pytest.fail(f"DeviceConnectionManager初期化中に予期せぬ例外が外に伝播しました: {e}")
            dcm_instance = None # 念のため

        # Then: alert_ui_callback が呼び出されたことを確認
        mock_alert_ui.assert_called_once()
        call_args = mock_alert_ui.call_args[0] # (args, kwargs) の args
        assert "IOKit Initialization Error" in call_args[0] # title
        assert "Simulated IOKit Init Error" in call_args[1] # message
        
        if dcm_instance: # 初期化自体は成功するはず
             assert dcm_instance._run_loop_source_addr == 0, "エラー発生時 run_loop_source_addr が0にリセットされていません"

    # test_long_running_stability (Phase 3で実装予定)
    # @pytest.mark.slow
    # def test_long_running_stability(self, camera_manager):
    #     pytest.skip("Phase 3で実装予定")
    #     # ... (サンプルコード参照)
