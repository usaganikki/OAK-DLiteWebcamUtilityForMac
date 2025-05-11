# OAK-D Lite Webcam Utility for Mac

## 概要

このプロジェクトは、Luxonis社のOAK-D-LiteカメラをmacOS上で手軽に高性能なWebカメラとして利用するためのユーティリティです。
プラグアンドプレイに対応し、OAK-D-Liteを接続するだけでWebカメラとして認識され、メニューバーからの簡単な操作で深度カメラなど他の用途への切り替えも可能です。
Python実行環境がインストールされていないMacでも利用できるよう、単一のアプリケーション形式で提供することを目指します。

## 主な機能

*   **Webカメラ化**: OAK-D-LiteのカラーカメラをUVC (USB Video Class) デバイスとして動作させ、Mac標準のWebカメラとして利用可能にします。
*   **プラグアンドプレイ**: OAK-D-LiteのUSB接続を検知して自動的にWebカメラ機能を有効化し、切断時に無効化します。
*   **メニューバー制御**: macOSのメニューバーに常駐するアイコンから、手動でWebカメラ機能のON/OFFを切り替えられます。
*   **スタンドアロンアプリケーション**: `PyInstaller` を利用して単一の `.app` バンドルにパッケージ化し、Python環境がないユーザーでも利用可能です。
*   **自動起動**: Macログイン時に自動的にユーティリティが起動するように `launchd` サービスを設定可能です。

## システム構成

本ユーティリティは、主に以下のコンポーネントで構成されます。

1.  **`uvc_runner` (コアUVC化プロセス)**
    *   OAK-D-Liteデバイスと通信し、カラーカメラの映像ストリームを取得してUVC形式でMacに提供します。
    *   Pythonスクリプト (`src/uvc_handler.py`) を `PyInstaller` でビルドした単一実行ファイルです。
    *   メニューバーアプリからバックグラウンドプロセスとして起動・停止されます。

2.  **`OakWebcamApp` (メニューバー制御アプリケーション)**
    *   ユーザーインターフェースを提供し、`uvc_runner` の制御、OAK-D-Liteの接続監視、設定変更などを行います。
    *   Pythonスクリプト (`src/menu_bar_control.py`) を `PyInstaller` でビルドした `.app` バンドルです。
    *   macOSのメニューバーに常駐します。

3.  **`launchd` サービス (自動起動設定)**
    *   Macのログイン時に `OakWebcamApp` (メニューバーアプリ) を自動的に起動するための設定ファイル (`.plist`) です。

## 技術要素

*   **プログラミング言語**: Python 3.x
*   **主要ライブラリ**:
    *   `depthai-sdk`: OAK-D-Liteの制御、UVC (USB Video Class) 化機能の利用。
    *   `depthai`: `depthai-sdk` のコアライブラリ。
    *   `rumps`: macOSネイティブなメニューバーアプリケーションをPythonで簡単に作成するためのライブラリ。
    *   `PyInstaller`: Pythonスクリプトを実行ファイルやアプリケーションバンドルにパッケージ化するツール。
    *   標準ライブラリ: `subprocess`, `threading`, `os`, `signal`, `time` など。

## ファイル構成 (案)

```text
.
├── src/
│   ├── uvc_handler.py        # OAK-D Lite UVC化コアロジック
│   └── menu_bar_control.py   # メニューバーアプリロジック
├── assets/
│   └── app_icon.icns         # アプリケーションアイコン (例: .icns形式)
├── launchd/
│   └── com.yourcompany.oakwebcam.plist.template # launchd plistテンプレート
├── build_scripts/            # ビルド用シェルスクリプトなど (オプション)
│   └── build_app.sh
├── requirements.txt          # Python依存ライブラリリスト (開発用)
├── LICENSE                   # プロジェクトのライセンスファイル
└── README.md                 # このファイル
```

## セットアップとビルド手順 (開発者向け)

### 1. 開発環境のセットアップ

*   Python 3.8以上を推奨。(例: Python 3.9.x を推奨します。)
*   (推奨) 開発時には、プロジェクト固有の環境分離のため、仮想環境の利用を推奨します。
    *   `venv` を利用する場合:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   `conda` を利用する場合 (別途インストールが必要):
        ```bash
        conda create -n oak_webcam_env python=3.9
        conda activate oak_webcam_env
        ```
*   必要なライブラリをインストール:
    ```bash
    pip install -r requirements.txt
    ```
    (`requirements.txt` には `depthai`, `depthai-sdk`, `rumps`, `pyinstaller` などを記載)

### 2. `uvc_runner` のビルド

`uvc_handler.py` を単一の実行ファイル `uvc_runner` にパッケージ化します。

```bash
cd src
pyinstaller --name uvc_runner \
            --onefile \
            --hidden-import=depthai_sdk.components \
            --hidden-import=pkg_resources.py2_warn \
            --hidden-import=cv2 \
            --hidden-import=blobconverter \
            # macOSの場合、コンソールを非表示にするなら --noconsole または --windowed
            uvc_handler.py
cd ..
# dist/uvc_runner が作成されるので、src/ ディレクトリなどにコピーしておく
cp dist/uvc_runner src/
```
*注意: `depthai` や関連ライブラリは多くの隠れた依存関係を持つため、`--hidden-import` の調整が必要になることがあります。エラーメッセージを参考に適宜追加してください。*

### 3. `OakWebcamApp.app` のビルド

`menu_bar_control.py` をmacOSアプリケーションバンドル `.app` にパッケージ化します。
この際、ステップ2で作成した `uvc_runner` をバンドルに含めます。

```bash
# uvc_runner が src/ ディレクトリに存在することを確認
pyinstaller --name OakWebcamApp \
            --windowed \
            --osx-bundle-identifier com.yourcompany.oakwebcamapp # 任意の一意なID
            --add-data "src/uvc_runner:." \
            --icon="assets/app_icon.icns" \
            --hidden-import=rumps \
            --hidden-import=depthai \
            src/menu_bar_control.py
# dist/OakWebcamApp.app が作成されます
```
*   `--add-data "src/uvc_runner:."` (macOSでは `--add-binary` も可) で `uvc_runner` を `.app` バンドルの `Contents/MacOS` ディレクトリ (ドット`.`で指定) に含めます。
*   `com.yourcompany.oakwebcamapp` は適切なバンドルIDに変更してください。
*   `assets/app_icon.icns` は事前に用意したアプリアイコンファイルです。

*(オプション) ビルドスクリプト (`build_scripts/build_app.sh`) に上記コマンドをまとめておくと便利です。*

## インストールと使用方法 (ユーザー向け)

1.  **アプリケーションの配置**:
    *   ビルドされた `OakWebcamApp.app` をMacの `/Applications` フォルダ、または任意の場所にコピーします。

2.  **自動起動設定 (推奨)**:
    *   `OakWebcamApp.app` を初めて起動した際、ログイン時の自動起動を設定するか尋ねるダイアログを表示する機能、または手動で設定できるメニュー項目を設けることを検討します。
    *   手動設定の場合:
        1.  `launchd` ディレクトリにある `com.yourcompany.oakwebcam.plist.template` を `com.yourcompany.oakwebcam.plist` として `~/Library/LaunchAgents/` にコピーします。
        2.  plistファイル内の `ProgramArguments` (実行パス) やログパスのユーザー名部分を実際の環境に合わせて編集します。
        3.  ターミナルで以下のコマンドを実行してサービスをロードします:
            ```bash
            launchctl load ~/Library/LaunchAgents/com.yourcompany.oakwebcam.plist
            ```
    *   アンロード (自動起動解除) は `launchctl unload ~/Library/LaunchAgents/com.yourcompany.oakwebcam.plist` です。

3.  **使用方法**:
    *   Macを起動すると、(自動起動設定がされていれば) メニューバーにOAK Webcamユーティリティのアイコンが表示されます。
    *   OAK-D-LiteをMacにUSB接続します。
    *   ユーティリティがデバイスを検知し、「接続時に自動開始」がオンの場合、自動的にWebカメラ機能が有効になります。
    *   ビデオ会議アプリケーション (Zoom, Teams, Meetなど) で、カメラとして「OAK-D Lite UVC」(または `uvc_handler.py` で設定した名前) を選択します。
    *   **手動制御**: メニューバーのアイコンをクリックして表示されるメニューから以下の操作が可能です。
        *   「Webカメラとして使用」: OAK-D-LiteをWebカメラモードにします。
        *   「Webカメラを停止」: Webカメラモードを解除し、OAK-D-Liteを他の用途 (深度計測など) のために解放します。
        *   「接続時に自動開始」: USB接続時の自動ON/OFF機能の有効/無効を切り替えます。
        *   「アプリを終了」: ユーティリティを完全に終了します。

## 注意点・既知の問題

*   **`depthai-sdk` のバージョン**: UVC機能は比較的新しい機能のため、`depthai-sdk` の最新バージョンを使用することを推奨します。APIの変更があった場合は、スクリプトの修正が必要になることがあります。
*   **パッケージング**: `PyInstaller` でのパッケージング、特に `depthai` や `OpenCV` などの複雑なライブラリの依存関係解決は、試行錯誤が必要になる場合があります。
*   **macOSの権限**: アプリケーションがカメラにアクセスするため、macOSの「セキュリティとプライバシー」設定でカメラへのアクセス許可が必要になる場合があります。
*   **パフォーマンス**: Pythonスクリプトを介してUVC化するため、ネイティブなUVCカメラと比較して若干のCPU/メモリオーバーヘッドや遅延が発生する可能性があります。通常利用では問題ない範囲と想定されますが、リソースにシビアな環境では注意が必要です。
*   **ログファイル**: ログは `~/Library/Logs/OakWebcamApp/` ディレクトリに出力されます。問題発生時の調査に役立ちます。

## 今後の改善点 (TODO)

*   [ ] より堅牢なUSBイベント監視: 現在のポーリング方式から、macOSネイティブのIOKit通知を利用したイベントドリブンな監視への移行 (例: `pyobjc` を利用)。
*   [ ] `launchd` plistの動的生成と管理: アプリケーション内から `launchd` サービスの設定・解除を容易に行えるようにする。
*   [ ] 詳細なエラーハンドリングとユーザーフレンドリーなフィードバック。
*   [ ] GUI設定画面の追加 (ログレベル変更、カメラ解像度/FPS選択など)。
*   [ ] アプリケーションのコード署名と公証 (配布用)。
*   [ ] 多言語対応。

## ライセンス

このプロジェクトは [ライセンス名 (例: MIT License)] のもとで公開されます。詳細は `LICENSE` ファイルを参照してください。
```

**補足:**

* `com.yourcompany.oakwebcam` のような部分は、ご自身のプロジェクト名やドメインに合わせて適宜変更してください。
* `requirements.txt` の具体的な内容は、使用するライブラリのバージョンを固定するために `pip freeze > requirements.txt` のようにして開発環境から生成すると良いでしょう。
* アイコンファイル `app_icon.icns` は別途作成し、`assets` ディレクトリに配置する想定です。

このMarkdownがプロジェクト管理の一助となれば幸いです。
