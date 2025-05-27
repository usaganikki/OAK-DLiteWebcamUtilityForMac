import pytest
import time
import logging
import psutil # システムリソース確認用

# conftest.py で sys.path にプロジェクトルートが追加されていることを期待
try:
    from src.device_connection_manager import DeviceConnectionManager, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID
    from src import iokit_wrapper # trigger_device_scan_and_notify を後でここから使う想定
except ImportError as e:
    logging.error(f"DeviceConnectionManager等のインポートに失敗しました: {e}")
    DeviceConnectionManager = None
    iokit_wrapper = None
    OAK_D_LITE_VENDOR_ID = 0
    OAK_D_LITE_PRODUCT_ID = 0


# このテストファイル全体に 'integration' マーカーを適用
pytestmark = pytest.mark.integration

# --- Mock UI Callbacks ---
def mock_notify_ui(title, subtitle, message):
    logging.debug(f"[Mock UI Notify] {title} - {subtitle}: {message}")

def mock_alert_ui(title, message):
    logging.warning(f"[Mock UI Alert] {title}: {message}") # Alerts might be warnings in tests

def mock_update_menu(is_enabled):
    logging.debug(f"[Mock UI Menu Update] Auto mode: {is_enabled}")

def mock_update_status_label(status_text):
    logging.debug(f"[Mock UI Status Label] Status: {status_text}")

@pytest.fixture
def device_manager_fixture():
    if DeviceConnectionManager is None or iokit_wrapper is None:
        pytest.skip("DeviceConnectionManager or iokit_wrapper could not be imported.")

    manager = DeviceConnectionManager(
        notify_ui_callback=mock_notify_ui,
        alert_ui_callback=mock_alert_ui,
        update_menu_callback=mock_update_menu,
        update_status_label_callback=mock_update_status_label
    )
    # In a real test environment, we might need to ensure the IOKit run loop source
    # from manager.get_run_loop_source_address() is handled if tests rely on
    # actual async IOKit events. However, for tests using a synchronous
    # trigger_device_scan_and_notify, this might be less critical.
    # For now, we assume synchronous triggers.
    
    # If camera started during DCM init (due to initial auto_mode=True and device present), stop it.
    if manager.get_camera_running_status():
        logging.info("DeviceManagerFixture: Camera found running after DCM initialization, stopping it for controlled test setup.")
        manager.stop_camera_action() 
        # Ensure camera_running is False before proceeding
        # Add a small delay if stop_camera_action is not immediately synchronous in its effect on get_camera_running_status
        time.sleep(0.5) # Adjust if necessary
        if manager.get_camera_running_status():
            logging.warning("DeviceManagerFixture: Camera still running after attempting to stop it. Test might be flaky.")

    # Disable auto mode for more controlled testing of auto-detection logic in Step 1
    manager.auto_mode_enabled = False 
    manager.update_menu_callback(False) # Reflect this in mock UI status
    logging.info("DeviceManagerFixture: Auto mode disabled and camera confirmed stopped for test control.")

    yield manager
    logging.info("Cleaning up device_manager_fixture...")
    manager.cleanup_on_quit()


class TestSystemIntegration:
    """システム統合テスト"""

    @pytest.mark.slow
    @pytest.mark.requires_camera # This marker is handled by conftest.py
    def test_end_to_end_camera_workflow(self, device_manager_fixture):
        """エンドツーエンドのカメラワークフローテスト"""
        dcm = device_manager_fixture
        
        if iokit_wrapper is None:
            pytest.skip("iokit_wrapper could not be imported.")

        # --- ステップ0: 初期状態 ---
        # 物理カメラが接続されていることを前提とする
        # フィクスチャで自動モードは初期状態で無効に設定されている
        assert dcm.get_auto_mode_status() is False, "自動モードがフィクスチャにより初期状態で無効になっていません。"
        # 自動モードが無効なので、DCM初期化時のスキャンでデバイスが見つかってもカメラは起動しないはず
        assert dcm.get_camera_running_status() is False, "カメラが初期状態で動作中になっています（自動モード無効のはず）。"
        logging.info("初期状態確認完了。自動モード無効、カメラ停止中。")

        # --- ステップ1: カメラ表示確認 (物理カメラ接続による自動起動) ---
        logging.info("ステップ1: カメラ表示確認（自動モード有効化とデバイススキャンによる自動起動）開始...")
        try:
            # 自動モードを有効にする
            logging.info("自動モードを有効化します...")
            dcm.toggle_auto_mode()
            assert dcm.get_auto_mode_status() is True, "自動モードが有効化されませんでした。"
            
            # iokit_wrapper.trigger_device_scan_and_notify を呼び出してデバイス検出をシミュレート
            # これが dcm._event_handler.on_device_connected を呼び出し、
            # 自動モードが有効なので dcm.start_camera_action が実行されるはず
            logging.info(f"iokit_wrapper.trigger_device_scan_and_notify を呼び出し (VID: {OAK_D_LITE_VENDOR_ID:04x}, PID: {OAK_D_LITE_PRODUCT_ID:04x})")
            if hasattr(iokit_wrapper, 'trigger_device_scan_and_notify'):
                 devices_found = iokit_wrapper.trigger_device_scan_and_notify(
                     dcm._event_handler, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID
                 )
                 # 物理カメラが接続されていれば1以上になるはず
                 assert devices_found > 0, "trigger_device_scan_and_notify でOAK-D Liteが見つかりませんでした。"
            else:
                 # この関数がないとテストが成立しないためスキップ
                 pytest.skip("iokit_wrapper.trigger_device_scan_and_notify が未実装のため、このテストは実行できません。")

            time.sleep(2) # カメラ起動処理とUVCハンドラ起動の待機 (環境に応じて調整)
            assert dcm.get_camera_running_status() is True, "カメラが自動起動しませんでした。"
            logging.info("ステップ1: カメラ表示確認（自動起動）成功。")
        except Exception as e:
            error_message = (
                f"ステップ1でエラー: {e}\n"
                "テストが予期せず失敗しました。OAK-D Liteカメラが正しく接続されているか確認し、"
                "一度取り外してから再接続して再度テストを実行してみてください。"
            )
            pytest.fail(error_message)

        # --- ステップ2: カメラ切断確認 ---
        logging.info("ステップ2: カメラ切断確認 開始...")
        try:
            dcm.disconnect_camera_explicitly()
            time.sleep(1) # カメラ停止処理の待機
            assert dcm.get_camera_running_status() is False, "カメラが切断されませんでした。"
            # disconnect_camera_explicitly は auto_mode も無効にするはず
            assert dcm.get_auto_mode_status() is False, "手動切断後、自動モードが無効になっていません。"
            logging.info("ステップ2: カメラ切断確認 成功。")
        except Exception as e:
            error_message = (
                f"ステップ2でエラー: {e}\n"
                "テストが予期せず失敗しました。OAK-D Liteカメラが正しく接続されているか確認し、"
                "一度取り外してから再接続して再度テストを実行してみてください。"
            )
            pytest.fail(error_message)

        # --- ステップ3: カメラ再認識確認 ---
        # 自動モードが無効になっているので、再度有効にするか、手動で開始する必要がある。
        # シナリオは「もう一度AutoDetectするようにしてカメラが認識するか」なので、自動モードを有効化する。
        logging.info("ステップ3: カメラ再認識確認（自動モード再有効化による）開始...")
        try:
            dcm.toggle_auto_mode() # 自動モードを再度有効にする
            assert dcm.get_auto_mode_status() is True, "自動モードが再有効化されませんでした。"
            
            # 自動モードを有効にした際、デバイスが接続されていればカメラが起動するはず
            # dcm.toggle_auto_mode() の内部ロジックで start_camera_action が呼ばれることを期待
            # ただし、このロジックは connected_target_device_info がセットされている場合に依存する。
            # connected_target_device_info は on_device_connected でセットされ、
            # on_device_disconnected でクリアされる。
            # disconnect_camera_explicitly() の後、物理的に再接続しない限り、
            # connected_target_device_info は None のままの可能性がある。
            # その場合、再度 trigger_device_scan_and_notify が必要。
            
            logging.info(f"再度 iokit_wrapper.trigger_device_scan_and_notify を呼び出し")
            if hasattr(iokit_wrapper, 'trigger_device_scan_and_notify'):
                 devices_found = iokit_wrapper.trigger_device_scan_and_notify(
                     dcm._event_handler, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID
                 )
                 assert devices_found > 0, "再スキャンでOAK-D Liteが見つかりませんでした。"
            else:
                 pytest.skip("trigger_device_scan_and_notify が未実装のため、このテストは実行できません。")

            time.sleep(2) # カメラ起動処理の待機
            assert dcm.get_camera_running_status() is True, "カメラが再認識・自動起動しませんでした。"
            logging.info("ステップ3: カメラ再認識確認 成功。")
        except Exception as e:
            error_message = (
                f"ステップ3でエラー: {e}\n"
                "テストが予期せず失敗しました。OAK-D Liteカメラが正しく接続されているか確認し、"
                "一度取り外してから再接続して再度テストを実行してみてください。"
            )
            pytest.fail(error_message)
        
        # --- クリーンアップ (フィクスチャの後処理で行われる) ---
        logging.info("エンドツーエンドのカメラワークフローテストが正常に完了しました。")


    @pytest.mark.slow
    @pytest.mark.requires_camera
    def test_system_resource_usage(self, device_manager_fixture):
        """システムリソース使用量テスト"""
        dcm = device_manager_fixture

        try:
            process = psutil.Process() # 現在のPythonプロセス
        except Exception as e:
            pytest.fail(f"psutil.Process() の取得に失敗しました: {e}")

        initial_memory = process.memory_info().rss
        logging.info(f"初期メモリ使用量: {initial_memory / (1024*1024):.2f} MB")

        # カメラ操作の実行: DeviceConnectionManager を直接使う
        # このテストでは、カメラが実際に起動しなくても、
        # DeviceConnectionManager のスキャンロジック（もしあれば）や
        # 関連オブジェクトの生成・破棄によるリソース変化を見たい。
        # しかし、DeviceConnectionManager自体にはscan_camerasのようなメソッドはない。
        # uvc_handler.py を起動・停止する start/stop_camera_action を使う。
        
        # まずカメラを起動
        if not dcm.get_camera_running_status():
            logging.info("リソーステストのためカメラを起動します...")
            
            # 自動モードが有効でない場合は有効にする
            if not dcm.get_auto_mode_status():
                logging.info("リソーステストのため自動モードを有効化します...")
                dcm.toggle_auto_mode()
                assert dcm.get_auto_mode_status() is True, "リソーステストのための自動モード有効化に失敗しました。"

            if hasattr(iokit_wrapper, 'trigger_device_scan_and_notify'):
                devices_found = iokit_wrapper.trigger_device_scan_and_notify(
                    dcm._event_handler, OAK_D_LITE_VENDOR_ID, OAK_D_LITE_PRODUCT_ID
                )
                assert devices_found > 0, "リソーステストのカメラ起動時に trigger_device_scan_and_notify でデバイスが見つかりませんでした。"
                time.sleep(2) # カメラ起動処理とUVCハンドラ起動の待機
            else:
                pytest.skip("iokit_wrapper.trigger_device_scan_and_notify が未実装のため、リソーステストは実行できません。")

        if not dcm.get_camera_running_status():
            error_message = (
                "リソーステスト前にカメラを起動できませんでした。\n"
                "テストが予期せず失敗しました。OAK-D Liteカメラが正しく接続されているか確認し、"
                "一度取り外してから再接続して再度テストを実行してみてください。"
            )
            pytest.fail(error_message)

        num_iterations = 5 # 回数を5回に変更
        logging.info(f"{num_iterations}回のカメラ停止・開始サイクルを実行します...")
        for i in range(num_iterations):
            try:
                dcm.stop_camera_action()
                # logging.debug(f"サイクル {i+1}/{num_iterations}: カメラ停止")
                time.sleep(0.1) 
                dcm.start_camera_action()
                # logging.debug(f"サイクル {i+1}/{num_iterations}: カメラ開始")
                time.sleep(0.1)
            except Exception as e:
                error_message = (
                    f"カメラ操作サイクル {i+1}回目でエラー: {e}\n"
                    "テストが予期せず失敗しました。OAK-D Liteカメラが正しく接続されているか確認し、"
                    "一度取り外してから再接続して再度テストを実行してみてください。"
                )
                pytest.fail(error_message)
        
        logging.info(f"{num_iterations}回のカメラ操作サイクルが完了しました。")

        # 最終的にカメラを停止
        if dcm.get_camera_running_status():
            dcm.stop_camera_action()
            time.sleep(1)

        final_memory = process.memory_info().rss
        logging.info(f"最終メモリ使用量: {final_memory / (1024*1024):.2f} MB")

        memory_increase = final_memory - initial_memory
        max_allowed_increase_mb = 100
        max_allowed_increase_bytes = max_allowed_increase_mb * 1024 * 1024
        
        logging.info(f"メモリ増加量: {memory_increase / (1024*1024):.2f} MB")
        
        assert memory_increase < max_allowed_increase_bytes, \
            f"メモリ使用量が許容範囲を超えて増加しました。増加量: {memory_increase / (1024*1024):.2f} MB, " \
            f"許容上限: {max_allowed_increase_mb} MB"
        
        logging.info("システムリソース使用量テストが成功しました。")
