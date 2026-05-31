# AITuberぶつぶつシステム

![AITuber](images/AIVTuber.png)

AITuberのための自動配信システム。テーマに基づいて自動的に話題を展開し、視聴者とインタラクティブなコミュニケーションを行います。

## 機能

- テーマベースの自動会話生成
- 視聴者コメントへの応答
- OBSと連携した字幕表示
- AivisSpeechを使用した音声合成（ボイスモデル: 蒼月ハヤテ）
- 配信サマリーの自動生成

## ソース構成（概要）

| 場所 | 内容 |
|------|------|
| `murmur/` | 本番アプリ（コントローラ・ハンドラ・サービス） |
| `app/` | OpenAI・Aivis・記憶・会話履歴など共通モジュール |
| `aituber/` | `poetry run aituber` 用 CLI |
| `scripts/` | ユーティリティ（例: `scripts/check_youtube_config.py`） |
| `main.py` / `config.py` | 起動エントリと設定ローダ（ルートに配置） |
| `.claude/skills/` | Claude Code 用の開発・運用支援 skill（[一覧](.claude/skills/README.md)） |

詳細は `doc/package_layout.md` を参照。ユーザー向けの変更履歴は [`RELEASE_NOTES.md`](RELEASE_NOTES.md) を参照。

### Claude Code で開発する場合

[Claude Code](https://docs.claude.com/claude-code) を使う場合、`.claude/skills/` の skill がセットアップ（オンボーディング）・起動・キャラ定義・テーマ作成・機能追加（イベント駆動）・環境診断・リリースの各作業を支援します。一覧は [`.claude/skills/README.md`](.claude/skills/README.md) を参照。**初めての方は `aituber-onboarding`（「セットアップして」「初めて使う」などで起動）から始めると、前提ソフトの導入から初回起動まで順に案内されます。**

## セットアップ

### 必要なソフトウェア

- Python 3.11以上（`pyproject.toml` の `requires-python` に準拠）
- Poetry（パッケージ管理）
- AivisSpeech Engine
- OBS Studio
- VB-CABLE（音声出力用）

### インストール手順

1. リポジトリのクローン：
```bash
git clone [repository-url]
cd AITuberMurmurSystem
```

2. 依存関係のインストール：
```bash
poetry install
```

3. AivisSpeechのセットアップ：
   - AivisSpeech Engineをセットアップし、起動します。
   - [蒼月ハヤテ ボイスモデル](https://hub.aivis-project.com/aivm-models/eefe1fbd-d15a-49ae-bc83-fc4aaad680e1)をダウンロードし、AivisSpeech Engineにインポートします。

4. OBSのセットアップ：
   - OBS Studioをインストール
   - WebSocketサーバーを有効化（ツール > WebSocket Server Settings）
   - テキストソースを追加（名前: **`Answer`**。大文字始まり。本体が `set_input_settings(name="Answer", ...)` で字幕を更新します）。機能によっては `Question` / `SelectedComment` / `Summary` も使用します（`murmur/obs_adaper.py`）。

5. VB-CABLEのセットアップ：
   - [VB-CABLE](https://vb-audio.com/Cable/)をダウンロードしてインストール
   - システムの音声出力デバイスとして設定
   - OBSでVB-CABLEを音声キャプチャデバイスとして追加

### 設定

1. API キーなどの設定（`.env`）：
   - `cp .env.template .env` で `.env` を作成し、`OPENAI_API_KEY` / `YOUTUBE_VIDEO_ID` / `OBS_WS_PASSWORD` などの **実値を `.env` に** 記入します（秘密情報は `.gitignore` 済みの `.env` に置く）。
   - `config.yaml` の `api_keys` セクションは **環境変数名のみ** を書く欄です（既定で `openai: OPENAI_API_KEY` のように対応済み）。値を直書きせず、通常は編集不要です。

```yaml
# config.yaml（抜粋）: 値ではなく「参照する環境変数名」を書く
api_keys:
  openai: OPENAI_API_KEY
  youtube_video_id: YOUTUBE_VIDEO_ID
```

   - 音声合成エンジン（AivisSpeech）の接続先は `config.yaml` の `audio.synthesis.aivis_url`（既定 `http://127.0.0.1:10101`）で指定します。

2. テーマファイルの準備：
   - `prompts/`ディレクトリにテーマファイルを配置
   - 例: `test_theme.txt`

## 実行方法

### CLI（推奨）

Poetry 環境から `aituber` コマンドで起動・停止・状態確認ができます（OS 共通）。

| 操作 | コマンド例 |
|------|------------|
| フォアグラウンド起動 | `poetry run aituber run` |
| テーマ指定 | `poetry run aituber run --theme test_theme.txt`（`prompts/` 配下など実際のパス） |
| キャラ YAML 指定 | `poetry run aituber run --character characters/hayate.yaml` |
| バックグラウンド起動 | `poetry run aituber run --detach`（ログは既定で `monologue.log`、`--log-file` で変更） |
| 終了依頼 | `poetry run aituber stop` または `poetry run aituber shutdown` |
| 強制終了 | `poetry run aituber stop --force`（`-f`） |
| 状態 | `poetry run aituber status` |
| キャラ確認・検証 | `poetry run aituber character info` / `poetry run aituber character validate characters/hayate.yaml` |

`python main.py` を直接実行しても同じアプリが起動します。`python -m aituber run` も同等です。

**Windows の注意:** 通常の `stop` は終了ファイル（`shutdown_request.txt`）とアプリ側のポーリングに依存します。確実にプロセスを止めたいときは `aituber stop --force` を使ってください。

### シェルスクリプト（従来どおり）

CLI と同じ役割のラッパーです。好みやスクリプト連携用に残しています。

#### Windows

1. PowerShellを管理者として実行し、以下のコマンドで実行ポリシーを設定（初回のみ）：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

2. 起動：
```powershell
.\start_monologue.ps1
```

3. テーマを指定して起動：
```powershell
.\start_monologue.ps1 --theme test_theme.txt
```

4. 停止：
```powershell
.\stop_monologue.ps1
```

#### Mac/Linux

1. 起動：
```bash
./start_monologue.sh
```

2. テーマを指定して起動：
```bash
./start_monologue.sh --theme test_theme.txt
```

3. 停止：
```bash
./stop_monologue.sh
```

## 参考資料

- [参考YouTube動画](https://www.youtube.com/watch?v=GvLcysqJIuk)

## トラブルシューティング

### 一般的な問題

1. AivisSpeechが起動していない：
   - AivisSpeech Engineを起動してから、プログラムを開始してください
   - エラーメッセージ: "接続エラー: HTTPConnectionPool..."

2. OBS接続エラー：
   - OBSが起動していることを確認
   - WebSocketサーバーが有効になっていることを確認
   - エラーメッセージ: "Failed to connect to OBS"

3. 音声が出力されない：
   - VB-CABLEが正しくインストールされているか確認
   - システムの音声出力デバイスがVB-CABLEになっているか確認
   - OBSでVB-CABLEからの音声をキャプチャしているか確認

### Windows固有の問題

1. スクリプト実行エラー：
   - PowerShellの実行ポリシーを確認
   - 管理者権限で実行が必要な場合あり

2. プロセス終了エラー：
   - `poetry run aituber stop --force` で強制終了を試す
   - それでもダメな場合はタスクマネージャーから `python` プロセスを手動で終了

### Mac/Linux固有の問題

1. 実行権限エラー：
```bash
chmod +x start_monologue.sh stop_monologue.sh
```

2. シェルスクリプトエラー：
   - 改行コードがLF（Unix形式）になっているか確認

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は`LICENSE`ファイルをご覧ください。