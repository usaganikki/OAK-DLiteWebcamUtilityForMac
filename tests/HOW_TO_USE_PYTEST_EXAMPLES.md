# Pytest と unittest.mock の使い方入門 (OAK-D Utility プロジェクトの例より)

このドキュメントは、OAK-D Lite Webcam Utility プロジェクトのテストコードで実際に使われている例を通して、`pytest` と `unittest.mock` の基本的な使い方を初心者向けに解説します。

## 1. Pytest の基本のキ

*   **テストファイルとテスト関数はどうやって見つけるの？**
    *   `pytest` は `test_*.py` や `*_test.py` という名前のファイルを探します。
    *   その中で `test_` で始まる関数がテストとして実行されます。
*   **テストの合否はどうやって決まるの？ - `assert` 文**
    *   `assert 条件` と書くと、「この条件は絶対に正しいはずだ！」と宣言したことになります。
    *   もし条件が間違っていたら（`False` だったら）、テストは失敗です。
    *   例: `x = 5; assert x == 5` (OK), `assert x == 3` (失敗!)
*   **テストのお供 - `conftest.py` ファイル**
    *   同じディレクトリやサブディレクトリにあるテストファイルで共通して使いたい設定（フィクスチャなど）をまとめて書くための特別なファイルです。

## 2. テストの準備はおまかせ！ - フィクスチャ (`@pytest.fixture`)

テストを実行する前に、何か準備が必要なことがよくあります（例: テスト用のデータを作る、特定の状態にする）。フィクスチャは、この「準備」と「後片付け」を自動でやってくれる便利な仕組みです。

*   `@pytest.fixture` デコレータを関数につけると、その関数がフィクスチャになります。
*   テスト関数は、引数にフィクスチャ名を指定するだけで、フィクスチャが準備したものを利用できます。
*   **例 (`tests/unit/test_menu_bar_app.py` より):**
    ```python
    @pytest.fixture
    def mock_rumps_functions():
        # mocksオブジェクトに必要なモック関数を設定する（詳細は後述）
        mocks = MagicMock()
        mocks.notification = create_autospec(actual_rumps.notification)
        # ...
        return mocks # この mocks オブジェクトがテスト関数に渡される

    def test_some_function(mock_rumps_functions): # 引数にフィクスチャ名を指定
        # mock_rumps_functions には、上のフィクスチャ関数が返した mocks オブジェクトが入っている
        # これを使ってテストを行う
        mock_rumps_functions.notification.assert_not_called() # 例
    ```

## 3. テストに目印をつけよう - マーカー (`@pytest.mark`)

たくさんのテストがあるとき、「このテストは時間がかかる」「このテストは特定の環境でだけ動かす」のように、テストを分類したり、特別な扱いをしたりしたいことがあります。マーカーはそのための機能です。

*   `@pytest.mark.名前` のようにテスト関数につけます。
*   例: `@pytest.mark.slow` とつけたテストは、後で `pytest -m "not slow"` のようにして実行対象から外したりできます。
*   プロジェクトによっては、`conftest.py` でカスタムマーカーを登録して使うこともあります。

## 4. モックオブジェクトとは？ なぜ使うの？

ユニットテストでは、テストしたい一部分（ユニット）だけを独立して検証したいと考えます。しかし、多くのコードは他の部分や外部ライブラリに依存しています。例えば、UIを表示するライブラリや、ハードウェアを制御するモジュールなどです。

これらの依存関係をそのままテストに含めると、
*   テストが遅くなる（例: 実際のUI表示を待つ）
*   テストが不安定になる（例: 外部環境に左右される）
*   テストの準備が複雑になる（例: 特定のハードウェアが必要）
といった問題が起こりがちです。

そこで登場するのが**モックオブジェクト**です。モックオブジェクトは、本物のオブジェクトの「ふり」をする偽物のオブジェクトです。本物のように振る舞いますが、実際の複雑な処理は行いません。代わりに、以下のようなことができます。
*   特定のメソッドが呼び出されたことを記録する。
*   呼び出された際に、あらかじめ設定された値を返す。
*   意図的にエラーを発生させる。

これにより、依存関係をモックに置き換えることで、テスト対象のユニットが依存部分と「正しくやり取りしようとしているか」を、実際の動作なしに検証できます。

## 5. `unittest.mock.create_autospec` - 本物のふりをするモック

`tests/unit/test_menu_bar_app.py` の `mock_rumps_functions` フィクスチャで使われています。

```python
# (フィクスチャ定義の一部)
from unittest.mock import create_autospec, MagicMock
# import rumps as actual_rumps # 実際のrumpsライブラリ

# @pytest.fixture
# def mock_rumps_functions():
#     mocks = MagicMock()
mocks.alert = create_autospec(actual_rumps.alert) # actual_rumps.alert は実際の関数を指す
#     return mocks
```

*   **`create_autospec(元のオブジェクト)`**: 元のオブジェクト（ここでは `actual_rumps.alert` 関数）のインターフェース（引数の数や名前など）をそっくり真似たモックオブジェクトを作ります。
*   **何が嬉しいの？**:
    *   もしテスト対象のコードが、元の関数の使い方を間違えて（例: 引数の数が違う）モックを呼び出そうとすると、エラーが発生します。これにより、より安全なテストが書けます。
    *   **重要**: このモックは、実際の `rumps.alert` のようにアラートダイアログを画面に表示したりはしません。ただ、「`alert` がこのように呼び出されましたよ」という情報を記録するだけです。

## 6. `@patch` デコレータ - 一時的にオブジェクトを置き換える魔法

テスト中だけ、特定のモジュールやクラス、関数をモックに差し替えたい場合があります。そんなときに使うのが `@patch` デコレータです (`unittest.mock.patch` からインポート)。

```python
from unittest.mock import patch

@patch('src.menu_bar_app.DeviceConnectionManager') # (1)
@patch('src.menu_bar_app.iokit_wrapper')          # (2)
def test_menu_bar_app_initialization(mock_iokit, mock_dcm_class, ...): # (3)
    # この関数の中では、
    # 'src.menu_bar_app.DeviceConnectionManager' は mock_dcm_class (モック) に、
    # 'src.menu_bar_app.iokit_wrapper' は mock_iokit (モック) に置き換えられています。
    # (mock_iokitが引数の最初に来るのは、@patchが内側から適用されるため)
    ...
# 関数が終わると、置き換えは自動的に元に戻ります。
```

*   **(1) & (2)**: `src.menu_bar_app` モジュールから見た `DeviceConnectionManager` と `iokit_wrapper` を、テスト関数の実行中だけモックオブジェクトに置き換えます。
*   **(3)**: 置き換えられたモックオブジェクトは、テスト関数の引数として渡されます。`@patch` デコレータは下から上（または右から左）の順で評価され、引数リストではその逆順（左から右）に対応します。つまり、一番内側の `@patch`（この例では `@patch('src.menu_bar_app.iokit_wrapper')`）がテスト関数の最初のモック引数（`mock_iokit`）に対応します。
*   **何が嬉しいの？**: `DeviceConnectionManager` や `iokit_wrapper` の実際の複雑な処理を実行せずに、テスト対象の `MenuBarApp` がこれらを「正しく使おうとしているか」を検証できます。

## 7. `with patch(...)` - 期間限定のパッチ

特定のコードブロック内だけでオブジェクトをモックに置き換えたい場合、`with` 構文と `patch` を組み合わせます。

```python
# def test_menu_bar_app_initialization(..., mock_rumps_functions):
    # ...
    with patch('src.menu_bar_app.rumps.notification', mock_rumps_functions.notification), \
         patch('src.menu_bar_app.rumps.alert', mock_rumps_functions.alert):
        # この with ブロックの中だけ、rumps.notification と rumps.alert が
        # mock_rumps_functions 内の対応するモックに置き換えられる。
        app = MenuBarApp() # MenuBarAppのインスタンスを作成
    # with ブロックを抜けると、rumps.notification などは元の状態に戻る。
    # ...
```

*   `patch` オブジェクトは「コンテキストマネージャ」としても振る舞えるため、`with` 文で使えます。
*   `with` ブロックに入る時にパッチが適用され、抜ける時に自動的に解除されます。
*   **この例の意図**: `MenuBarApp` の初期化処理 (`MenuBarApp()`) の間だけ、`rumps.notification` などのUI関連関数をモックし、初期化が完了したら元の状態に戻しています。これにより、初期化ロジックと他の部分のテストを分離できます。

## 8. モックの呼び出しを検証するアサーションメソッド

モックオブジェクトは、どのように呼び出されたかを記録しています。テストでは、この記録を使って期待通りに呼び出されたかを確認します。

*   **`mock_object.assert_called_once_with(*args, **kwargs)`**:
    *   `mock_object` が**ちょうど1回だけ**、かつ**指定された引数 (`*args`, `**kwargs`) で**呼び出されたことを確認します。
    *   例 (`tests/unit/test_menu_bar_app.py` より):
        ```python
        mock_dcm_class.assert_called_once_with(
            notify_ui_callback=app.show_notification,
            alert_ui_callback=app.show_alert,
            # ... 他のコールバック引数 ...
        )
        ```
        これは、`MenuBarApp` の初期化時に `DeviceConnectionManager` のコンストラクタ（のモック `mock_dcm_class`）が1回だけ、かつ期待通りのコールバック関数を引数として呼び出されたかを確認しています。

*   **`mock_object.assert_called()`**:
    *   `mock_object` が**少なくとも1回は呼び出されたこと**を確認します（引数は問いません）。
    *   例 (`tests/unit/test_menu_bar_app.py` より):
        ```python
        mock_dcm_instance.get_auto_mode_status.assert_called()
        ```
        これは、`MenuBarApp` の初期化時に、自動モードの状態を取得するために `DeviceConnectionManager` の `get_auto_mode_status` メソッド（のモック）が呼び出されたかを確認しています。

他にも `assert_called_with()`, `assert_any_call()`, `assert_not_called()`, `call_count` など、様々なアサーションメソッドがあります。これらを使い分けることで、モックオブジェクトとのインタラクションを詳細にテストできます。

---

このドキュメントが、`pytest` とモックを使ったテストの理解の一助となれば幸いです。
