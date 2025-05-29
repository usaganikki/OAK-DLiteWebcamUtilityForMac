import pytest
import logging
import sys
import os

# プロジェクトのルートディレクトリをPythonのパスに追加
# これにより、src.module_name のような形式でインポートが可能になる
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

@pytest.fixture(scope="session", autouse=True)
def setup_system_test_environment():
    """システムテスト環境のセットアップ"""
    # ログレベルの設定
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("システムテスト環境のセットアップを開始します。")
    
    # テスト用の一時ディレクトリやファイルの準備などがあればここで行う
    # (現時点では特になし)
    
    yield
    
    # クリーンアップ処理
    logger.info("システムテスト環境のクリーンアップ処理を実行します。")

# pytestコマンドラインオプションの追加
def pytest_addoption(parser):
    parser.addoption(
        "--physical-camera", action="store_true", default=False,
        help="Run tests that require a physical camera connection"
    )

# システムテスト用のマーカー定義
# conftest.pyでpytest.mark.<marker_name>を直接代入するのではなく、
# pytest_configureフックを使用してマーカーを登録することが推奨されています。
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "system: システムテスト全体を示すマーカー"
    )
    config.addinivalue_line(
        "markers", "slow: 実行に時間がかかるテストを示すマーカー"
    )
    config.addinivalue_line(
        "markers", "integration: 統合テストを示すマーカー"
    )
    config.addinivalue_line(
        "markers", "camera_lifecycle: カメラライフサイクル関連のテストを示すマーカー"
    )
    config.addinivalue_line(
        "markers", "requires_camera: mark test as requiring a physical camera"
    )

# pytestの実行時に自動的に適用されるフック
def pytest_collection_modifyitems(config, items):
    """
    tests/system ディレクトリ内のすべてのテストアイテムに 'system' マーカーを自動的に付与する。
    また、'--physical-camera' オプションが指定されていない場合、
    'requires_camera' マーカーが付いたテストをスキップする。
    """
    skip_physical_camera_tests = not config.getoption("--physical-camera")
    if skip_physical_camera_tests:
        skip_reason = "Skipping physical camera tests. Use --physical-camera to run."
        skip_marker = pytest.mark.skip(reason=skip_reason)

    for item in items:
        # 'system' マーカーの付与
        if item.nodeid.startswith("tests/system/"):
            item.add_marker(pytest.mark.system)
        
        # 'requires_camera' テストのスキップ処理
        if skip_physical_camera_tests and "requires_camera" in item.keywords:
            item.add_marker(skip_marker)
