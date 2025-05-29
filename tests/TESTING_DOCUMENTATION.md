# OAK-D Lite Webcam Utility テストドキュメント 

## 1. はじめに

このドキュメントは、OAK-D Lite Webcam Utility プロジェクトにおけるテストの構造、目的、および主要なテストケースについて解説します。テストは、アプリケーションの品質を保証し、変更が予期せぬ問題を引き起こさないことを確認するために不可欠です。

このプロジェクトでは、主に **`pytest`** というPythonのテストフレームワークを利用してテストを記述・実行しています。`pytest` は、シンプルで分かりやすい記法と強力な機能を兼ね備えており、効率的なテスト作成をサポートします。このドキュメントでは、`pytest` の基本的な概念にも触れながら、テストコードを理解できるように説明します。

## 2. Pytestの基本 (このプロジェクトで使われている主な機能)

`pytest` を理解するために、まずいくつかの基本的なルールと機能を見ていきましょう。

*   **テストファイルとテスト関数:**
    *   `pytest` は、デフォルトで `test_*.py` または `*_test.py` という名前のファイルからテストを探します。
    *   これらのファイルの中で、`test_` で始まる名前の関数（例: `def test_example():`）がテスト関数として認識されます。
*   **アサーション (Assertion):**
    *   テスト関数の中では、`assert` 文を使って期待する結果と実際の値が一致するかを検証します。
    *   例: `assert x == 5` (変数 `x` の値が `5` であることを期待する)
    *   もし `assert` の条件が `False` になると、テストは失敗したと報告されます。
*   **フィクスチャ (Fixtures):**
    *   フィクスチャは、テスト関数を実行する前に必要な準備（セットアップ）を行い、テスト後には後片付け（クリーンアップ）を行うための仕組みです。
    *   例えば、テスト対象のオブジェクトを生成したり、データベース接続を準備したり、特定の状態を作り出したりするのに使います。
    *   `@pytest.fixture` というデコレータを関数に付けることでフィクスチャを定義できます。
    *   テスト関数は、引数にフィクスチャ名を指定するだけで、そのフィクスチャが準備したものを利用できます。これにより、同じ準備処理を複数のテストで簡単に再利用できます。
*   **マーカー (Markers):**
    *   マーカーは、テスト関数にメタデータ（追加情報）を付与するための仕組みです。
    *   `@pytest.mark.<marker_name>` のようにデコレータとして使用します。
    *   例えば、特定の種類のテスト（例: `slow` なテスト、`system` テスト）にマーカーを付けておき、後でマーカーを指定して特定のテストだけを実行したり、逆にスキップしたりすることができます。
*   **`conftest.py` ファイル:**
    *   `conftest.py` は、特定のディレクトリとそのサブディレクトリ全体で共有されるフィクスチャやフック（`pytest` の動作をカスタマイズする関数）を定義するための特別なファイルです。
    *   ここに共通のフィクスチャを定義することで、テストコードがより整理され、再利用性が高まります。

## 3. テストの構成

テストコードは主に `tests` ディレクトリ以下に配置されています。特にシステム全体の動作を検証するテストは `tests/system` ディレクトリにあります。

### 3.1. `tests/system/conftest.py` - テスト全体の設定ファイル

このファイルは、`tests/system` ディレクトリ以下のテスト全体に影響を与える設定や共通のフィクスチャを定義しています。

*   **プロジェクトルートのパス追加:**
    *   `sys.path.insert(0, project_root)`: `src` ディレクトリ内のモジュール（例: `DeviceConnectionManager`）をテストコードから `from src.device_connection_manager import DeviceConnectionManager` のように簡単にインポートできるように、Pythonがモジュールを探すパスのリストにプロジェクトのルートディレクトリを追加しています。
*   **`setup_system_test_environment()` フィクスチャ:**
    *   `@pytest.fixture(scope="session", autouse=True)`:
        *   `scope="session"`: このフィクスチャはテストセッション全体で1回だけ実行されます。
        *   `autouse=True`: このフィクスチャは、テスト関数が明示的に要求しなくても自動的に使用されます。
    *   **役割**: テスト実行前にログの設定など、テスト環境全体の基本的なセットアップを行います。
*   **コマンドラインオプションの追加 (`pytest_addoption`):**
    *   `parser.addoption("--physical-camera", ...)`: `pytest` コマンド実行時に `--physical-camera` というオプションを指定できるようにします。このオプションは、物理的なカメラ接続が必要なテストを実行するかどうかを制御するために使われます。
*   **カスタムマーカーの登録 (`pytest_configure`):**
    *   `config.addinivalue_line("markers", "marker_name: 説明")`: `pytest` に新しいマーカーを登録します。これにより、`@pytest.mark.marker_name` のようにテスト関数にマーカーを付けられるようになります。
    *   登録されている主なマーカー:
        *   `system`: システムテストであることを示します。
        *   `camera_lifecycle`: カメラの接続・切断ライフサイクル関連のテストを示します。
        *   `requires_camera`: 物理的なカメラ接続が必要なテストを示します。
*   **マーカーの自動処理 (`pytest_collection_modifyitems`):**
    *   このフック関数は、`pytest` がテスト関数を集めた後に呼び出されます。
    *   **役割**:
        *   `tests/system/` ディレクトリ内のすべてのテストアイテムに自動的に `system` マーカーを付与します。
        *   `--physical-camera` オプションが指定されていない場合、`requires_camera` マーカーが付いたテストを自動的にスキップします。これにより、物理カメラがない環境でも安全にテストを実行できます。

### 3.2. `tests/system/test_camera_lifecycle.py` - カメラライフサイクルのテスト

このファイルは、`DeviceConnectionManager` クラスのカメラ接続・切断に関するライフサイクルが正しく動作するかを検証するシステムテストを定義しています。**このテストは、物理的なカメラデバイスが接続されていなくても実行できるように、IOKit (macOSのハードウェアインターフェース) とのやり取りをモック化（模擬化）しています。**

**主な特徴とPytestの活用ポイント:**

*   **テスト対象**: `DeviceConnectionManager` クラス。
*   **IOKitのモック化**:
    *   **なぜモックが必要か？**:
        1.  **ハードウェア非依存**: 実際のカメラが接続されていなくてもテストを実行できます。
        2.  **テストの安定性**: 物理デバイスの状態や外部環境に左右されず、常に同じ条件でテストできます。
        3.  **テストの速度**: 実際のハードウェア操作は時間がかかることがありますが、モックなら高速に動作します。
        4.  **特定状況の再現**: エラー発生時など、実際のハードウェアでは再現が難しい状況を簡単にシミュレートできます。
    *   **`mock_iokit_wrapper` フィクスチャ**:
        *   `@pytest.fixture` で定義されています。
        *   `unittest.mock.MagicMock` を使って、`src.iokit_wrapper` モジュール内の関数（例: `init_usb_monitoring`, `stop_usb_monitoring`）の動作を模擬します。
        *   `MagicMock` オブジェクトは、呼び出された回数や引数を記録したり、特定の返り値を返すように設定したり、呼び出された際に特定の処理（副作用、`side_effect`）を実行させたりできます。
        *   例えば、`mock_wrapper_module.init_usb_monitoring = MagicMock(return_value=12345)` は、`init_usb_monitoring` が呼び出されたら `12345` を返すように設定します。
        *   `patch('src.device_connection_manager.iokit_wrapper', mock_wrapper_module)`: `DeviceConnectionManager` モジュールがインポートしている `iokit_wrapper` を、ここで作成したモックオブジェクト (`mock_wrapper_module`) に差し替えます。これにより、`DeviceConnectionManager` はテスト中に実際の `iokit_wrapper` の代わりにモックとやり取りします。
*   **`dcm` フィクスチャ**:
    *   `@pytest.fixture` で定義されています。
    *   テスト対象である `DeviceConnectionManager` のインスタンスを生成して返します。
    *   このフィクスチャは `mock_iokit_wrapper` フィクスチャを引数に取るため、`dcm` が生成する `DeviceConnectionManager` はモック化された `iokit_wrapper` を使用します。
    *   `DeviceConnectionManager` の初期化に必要なUIコールバック関数も `MagicMock` で作成し、UIの動作に依存しないようにしています。
*   **テストメソッドの例**:
    *   **`test_dcm_initial_state(self, dcm)`**:
        *   `dcm` フィクスチャを受け取り、`DeviceConnectionManager` の初期状態（カメラが動いていないか、デバイス情報が空かなど）を `assert` で検証します。
    *   **`test_dcm_connection_scenarios(self, dcm, mock_iokit_wrapper, connection_scenario)`**:
        *   **`@pytest.mark.parametrize("connection_scenario", [...])`**: このデコレータにより、テストメソッドは `connection_scenario` 引数にリスト内の各値を順番に受け取り、複数回実行されます。
            *   `"connect_then_disconnect"`: 1回接続し、1回切断するシナリオ。
            *   `"multiple_connect_disconnect"`: 複数回接続と切断を繰り返すシナリオ。
            *   `"rapid_connect_disconnect"`: 短い間隔で接続と切断を繰り返すシナリオ。
        *   **`start_camera_action` / `stop_camera_action` のモック化**:
            ```python
            dcm.start_camera_action = MagicMock(side_effect=lambda: setattr(dcm, 'camera_running', True))
            dcm.stop_camera_action = MagicMock(side_effect=lambda: setattr(dcm, 'camera_running', False))
            ```
            *   **目的**: `DeviceConnectionManager` の `start_camera_action` や `stop_camera_action` メソッドは、実際にカメラのサブプロセスを起動・停止する重い処理です。テストでは、これらのメソッドが「呼び出されたか」と「呼び出された結果として期待される状態変化（`camera_running`フラグの変更など）が起きたか」を検証できれば十分な場合があります。
            *   **動作**:
                1.  `dcm.start_camera_action` を `MagicMock` オブジェクトで置き換えます。
                2.  `side_effect=lambda: setattr(dcm, 'camera_running', True)`: このモック化された `start_camera_action` が呼び出されると、`lambda` 関数が実行され、`dcm` オブジェクトの `camera_running` 属性が `True` に設定されます。これにより、実際のカメラ起動処理をスキップしつつ、カメラが起動したという状態をシミュレートします。
                3.  後で `dcm.start_camera_action.assert_called_once()` のようにして、このモックが期待通りに1回呼び出されたかなどを検証できます。
        *   **イベントのシミュレーション**:
            *   `callback_handler = mock_iokit_wrapper.g_python_callback_handler` で、`DeviceConnectionManager` がIOKitモックに登録したコールバックハンドラを取得します。
            *   `event_handler.on_device_connected(...)` や `event_handler.on_device_disconnected(...)` を直接呼び出すことで、IOKitからデバイスの接続・切断イベントが発生したことをシミュレートします。
        *   **検証**: イベント発生後、`dcm.start_camera_action` や `dcm.stop_camera_action` が期待通りに呼び出されたか、`dcm.get_camera_running_status()` や `dcm.connected_target_device_info` の状態が正しく更新されたかを `assert` で検証します。
    *   **`test_dcm_error_handling_init_monitoring_failure(self, mock_iokit_wrapper)`**:
        *   IOKitの初期化処理 (`init_usb_monitoring`) が失敗した場合のエラーハンドリングをテストします。
        *   `mock_iokit_wrapper.init_usb_monitoring.side_effect = mock_iokit_wrapper.IOKitError(...)` のように設定することで、`init_usb_monitoring` が呼び出された際に強制的にエラー (`IOKitError`) を発生させます。
        *   エラー発生時に、UIにアラートが表示されるか (`mock_alert_ui.assert_called_once()`) などを検証します。

### 3.3. `tests/system/test_integration.py` - 統合テスト (現在動作しません)

このファイルは、よりシステム全体に近い形での統合テストを定義しています。`test_camera_lifecycle.py` と異なり、**物理的なカメラデバイスが接続されていることを前提とするテストケースが含まれています。**

*   **`@pytest.mark.requires_camera` マーカー**:
    *   このマーカーが付いたテストは、`conftest.py` の設定により、`pytest` 実行時に `--physical-camera` オプションが指定されていない場合はスキップされます。
*   **`device_manager_fixture` フィクスチャ**:
    *   `DeviceConnectionManager` のインスタンスを準備しますが、こちらは実際のIOKitと連携する可能性があります（ただし、テスト内では `iokit_wrapper.trigger_device_scan_and_notify` のような、より制御された形でデバイスイベントを発生させる関数も使用しています）。
*   **テストケース例 (`test_end_to_end_camera_workflow`)**:
    *   カメラの自動検出による起動、明示的な切断、再認識といった一連のワークフローをテストします。
    *   `iokit_wrapper.trigger_device_scan_and_notify(...)` を呼び出して、デバイススキャンとイベント通知を能動的に発生させ、`DeviceConnectionManager` がそれに反応するかを検証します。これは、実際のUSB接続/切断イベントに近い動作をシミュレートしつつ、テストのタイミングを制御しやすくするためのものです。
*   **リソース使用量テスト (`test_system_resource_usage`)**:
    *   カメラの起動・停止を繰り返した際のメモリ使用量の変化を監視し、メモリリークなどが発生していないかを確認します。`psutil` ライブラリを使用してプロセスのメモリ情報を取得しています。

## 4. テストの実行方法

プロジェクトのルートディレクトリで以下のコマンドを実行することで、テストを実行できます。

*   **すべてのテストを実行:**
    ```bash
    pytest
    ```
*   **特定のファイルを実行:**
    ```bash
    pytest tests/system/test_camera_lifecycle.py
    ```
    （`test_camera_lifecycle.py` 内のすべてのテストが実行されます。）
*   **特定のマーカーが付いたテストを実行:**
    ```bash
    pytest -m camera_lifecycle
    ```
    （`@pytest.mark.camera_lifecycle` マーカーが付いたテストのみが実行されます。）
*   **物理カメラが必要なテストを含めて実行:**
    ```bash
    pytest --physical-camera
    ```
    （`@pytest.mark.requires_camera` マーカーが付いたテストも実行対象になります。）
*   **詳細な情報を表示して実行:**
    ```bash
    pytest -v
    ```
    （`-v` オプションで、各テスト関数の名前など、より詳細な実行結果が表示されます。）
*   **テスト失敗時にデバッガを起動:**
    ```bash
    pytest --pdb
    ```
    （テストが失敗した箇所でPythonのデバッガ `pdb` が起動し、対話的に調査できます。）

## 5. 今後の展望と課題

*   **物理カメラ連携テストの安定化:** 現在 `trace trap` エラーが発生していßる物理カメラを用いたテスト (`test_integration.py` など) の原因を特定し、安定して実行できるようにすることが急務です。
*   **カバレッジの向上:** テストケースを拡充し、コードカバレッジ（テストによって実行されたコードの割合）を向上させることで、より多くの潜在的な不具合を発見できるようにします。
*   **テストの自動化:** CI (継続的インテグレーション) 環境を整備し、コード変更時に自動的にテストが実行される仕組みを構築します。
