---
name: aituber-diagnose
description: AITuberぶつぶつシステム（z-aituber）の環境・設定の不調を診断するときに使う。「起動しない」「音が出ない」「OBSにつながらない」「コメントが取れない」「config/.env が正しいか確認したい」「AivisSpeechにつながらない」などのとき。config.validate_config / scripts/check_youtube_config.py / AivisSpeech・OBS・VB-CABLE・YouTube・OpenAI の接続確認と、よくあるエラーの切り分けを案内する。
---

# 環境・設定の診断

このシステムの「動かない」を切り分けるための skill。原因の多くは `.env` の必須キー欠落、外部プロセス（AivisSpeech Engine / OBS）の未起動、YouTube 配信 ID の不正。下記の順に上から潰していくと早い。

## 0. まず確認すること（必須キーとパス）

Claude が最初に走らせるべき2つ。

```bash
# 設定全体の妥当性チェック（必須 api_keys と paths を検査）
poetry run python -c "from config import config; print(config.validate_config() or 'All OK')"

# YouTube まわりの設定確認（.env 存在・YOUTUBE_VIDEO_ID 形式・OPENAI_API_KEY 等）
poetry run python scripts/check_youtube_config.py
```

`config.validate_config()` が検査するのは以下。問題があれば文字列リストで返る（空なら OK）。

- 必須 api_keys: `openai`（= 環境変数 `OPENAI_API_KEY`）, `youtube_video_id`（= `YOUTUBE_VIDEO_ID`）
- 必須 paths: `prompts` / `txt` / `summary`（いずれも config.yaml の `paths` で定義、`BASE_DIR` 基準で絶対パス化。ディレクトリが実在するか）

`.env` が無ければ `.env.template` をコピーして作る。

```bash
cp .env.template .env
```

`.env` の必須キー（config.yaml の `api_keys` がこの環境変数名を参照する）:

- `OPENAI_API_KEY`（必須）
- `YOUTUBE_VIDEO_ID`（必須）
- `OBS_WS_PASSWORD` / `OBS_WS_HOST`（既定 `127.0.0.1`）/ `OBS_WS_PORT`（既定 `4455`）（必須）
- `AIVIS_SPEECH_API_KEY`（任意・空でよい）
- `CHAT_TEST_MODE` / `FORCE_TEST_ON_ERROR`（任意。テスト切り分け用）

`config.api_keys.*` が `None` のままなら、対応する環境変数が読めていない（`.env` の場所はリポジトリルート、`config.py` の `BASE_DIR` 基準）。

## 1. YouTube（コメントが取れない）

### まず設定を検査（`scripts/check_youtube_config.py`）

```bash
poetry run python scripts/check_youtube_config.py
```

このスクリプトは **ライブには接続せず**、`.env` の存在・`YOUTUBE_VIDEO_ID` の有無と形式・`OPENAI_API_KEY` の有無・`OBS_WS_PASSWORD` の有無を検査するだけ。出る文字列は以下。

- `❌ .envファイルが見つかりません`: `.env.template` をコピーして作る（後述）。
- `❌ YOUTUBE_VIDEO_IDが設定されていません`: `.env` に `YOUTUBE_VIDEO_ID` を設定する。
- `⚠️  ビデオIDの形式が不正の可能性があります`: ID の形式チェック（正規表現 `^[a-zA-Z0-9_-]{11}$`、通常 11 文字の英数字・ハイフン・アンダースコア）を満たさない。配信 URL（`https://www.youtube.com/watch?v=XXXXXXXXXXX`）の `v=` 以降から正しい ID を取り直す。
- `⚠️  OPENAI_API_KEYが設定されていません`: 動作には OpenAI キーが必要。

`YOUTUBE_VIDEO_ID` は配信 URL の `v=` 以降。

### 実際にライブへ接続して確認（pytchat 接続テスト）

設定が正しくてもコメントが流れないときは、実接続テストで切り分ける。これらは `check_youtube_config.py` ではなく **接続テスト時（pytchat）に現れる**文字列。

```bash
poetry run python murmur/tests/test_youtube_live_simple.py
```

- `❌ Chat is not available (stream might not be live)`: その配信が終了済み・未ライブ。**現在ライブ中**の配信 ID を指定する。
- `❌ Connection failed: ...`: ネットワーク不通。インターネット接続を確認。

コメント取得本体は `murmur/services/integrated_comment_manager.py`（pytchat）。`NewCommentReceived` Event を流す。

## 2. AivisSpeech（音が出ない・合成に失敗する）

音声合成は `app/aivis_speech_adapter.py`。起動時に `config.audio.synthesis.aivis_url`（既定 `http://127.0.0.1:10101`）の `/version` に GET して接続テストする。

- 接続失敗時のログ: `警告: AivisSpeechエンジンへの接続に失敗しました: ...`。
- `requests.exceptions.ConnectionError` / `HTTPConnectionPool ... Max retries exceeded`: **AivisSpeech Engine が起動していない**、または `aivis_url` の host/port 不一致。
  - 対処: AivisSpeech のエンジンを起動し、`config.yaml` の `audio.synthesis.aivis_url` がエンジンのアドレスと一致しているか確認。
- 話者（ボイスモデル）が見つからない: 起動時に `/speakers` を照会し、キャラクター YAML の `voice.speaker_uuid` / `style_id` が存在するか検証する。`警告: 話者UUID ... が見つかりません` が出たら、対象のボイスモデルを **AivisSpeech Engine にインポート**する（既定キャラ 蒼月ハヤテ = `characters/hayate.yaml`, speaker_id 1）。
  - キャラ定義そのものの妥当性は別途確認: `poetry run aituber character validate characters/hayate.yaml` / `poetry run aituber character info`（詳細は [[aituber-character]]）。

## 3. OBS（つながらない・字幕が出ない）

OBS 連携は `murmur/obs_adaper.py`（`obsws_python`）と `murmur/services/obs_text_manager.py`。

接続前提:

1. OBS 側で **WebSocket Server を有効化**（OBS の「ツール → WebSocket サーバー設定」）。
2. `.env` の `OBS_WS_HOST` / `OBS_WS_PORT` / `OBS_WS_PASSWORD` を OBS の設定値と一致させる。`config.api_keys.obs_ws_*` のいずれかが `None` だとアダプタ初期化時にエラー。
3. 字幕用にテキスト（GDI+）ソースを用意し、**ソース名を `Answer`** にする（アダプタは `set_input_settings(name="Answer", ...)` で更新する）。
4. 字幕の有効/無効は `config.yaml` の `obs_subtitles.enabled`（既定 `true`）。

症状:

- `[OBSTextManager] Failed to connect to OBS` / `Failed to initialize OBS Adapter`: WebSocket Server 未起動、ホスト/ポート/パスワード不一致を疑う。
- 接続はできるが字幕が出ない: ソース名が `Answer` か、`obs_subtitles.enabled` が `true` か、`[OBSTextManager] OBS not connected` ログが出ていないかを確認。

## 4. 音声出力（OBS に声が乗らない）

OBS へ音声を流すには **仮想オーディオデバイス（VB-CABLE 等）をシステムの音声出力デバイスに設定**し、OBS の「音声入力キャプチャ」でそのデバイスを取り込む。AivisSpeech の再生は `config.audio.playback`（`default_output_device_id` など）で制御される。「ローカルでは聞こえるが配信に乗らない」ときは、再生先デバイスと OBS の取り込みデバイスが一致しているかを確認する。

## 5. OpenAI（応答が生成されない）

- `app/openai_adapter.py`（Chat Completions, モデルは `config.openai.models`）。`OPENAI_API_KEY` 必須。初期化時に接続テストを行い、`✅ OpenAI API接続テスト成功` / `❌ OpenAI API接続テスト失敗: ...` を出力する。`RateLimitError` などは内部で捕捉・リトライされる（リトライ設定は `config.network`）。
- 重要: OpenAI エラーは **`ServiceErrorOccurred` Event としては流れない**（`ServiceErrorOccurred` は `events.py` に定義はあるが未使用。[[aituber-dev]] 参照）。生成系ハンドラが例外を **捕捉してログに print し、フォールバック文を載せた `*Ready` を put** するため、配信は止まらずフィラー的な定型文に切り替わる（例: `MonologueHandler` は `[MonologueHandler] Error during LLM call: ...` を出力して `MonologueReady` にフォールバック文を入れる）。
- 切り分けは `monologue.log` を `OpenAI API接続テスト失敗` / `Error during LLM call` / `❌` / `⚠️` で grep する（`ServiceErrorOccurred` を探しても出ない）。ログの見方は [[aituber-run]]。

## よくあるエラー対応表

| 症状 | 主な原因 | 対処 |
| --- | --- | --- |
| 起動直後に Configuration Issues が出る | `.env` 必須キー欠落 / paths 不在 | `config.validate_config()` の指摘を解消。`.env` 作成、prompts/txt/summary ディレクトリ確認 |
| `Chat is not available`（接続テスト/pytchat 時） | 配信終了済み・未ライブ | ライブ中の配信 ID に変更 |
| `Connection failed`（接続テスト/pytchat 時） | ネットワーク不通 | インターネット接続を確認 |
| `ビデオIDの形式が不正の可能性があります`（check_youtube_config.py） | `YOUTUBE_VIDEO_ID` の形式不正 | URL の `v=` から 11 文字 ID を取り直す |
| `HTTPConnectionPool ... Max retries` / AivisSpeech 接続失敗 | Engine 未起動 / `aivis_url` 不一致 | Engine 起動、`audio.synthesis.aivis_url` を一致させる |
| `話者UUID ... が見つかりません` | ボイスモデル未インポート | 対象モデルを AivisSpeech にインポート、`voice.speaker_uuid` を確認 |
| `Failed to connect to OBS` | WebSocket Server 未起動 / 認証不一致 | OBS で WebSocket 有効化、`OBS_WS_*` を一致 |
| 字幕が表示されない | ソース名不一致 / 無効化 | ソース名を `Answer` に、`obs_subtitles.enabled: true` |
| 配信に声が乗らない | 出力デバイス不一致 | VB-CABLE をシステム出力にし OBS で取り込む |

`status` の見方・`monologue.log` の確認・停止操作は [[aituber-run]] を参照。

## 設定を直したあとの再確認

- `.env` / `config.yaml` を編集したら、稼働中インスタンスは再起動するか、`config.reload_config()` で再読込する。

```python
from config import config
config.reload_config()   # 成功で True、再度 validate 結果を表示
```

- 外部 API なしで配線だけ切り分けたいときは、**環境変数** `CHAT_TEST_MODE=true`（または `TEST_MODE=unit`）を付けて起動する。テストモード判定は `murmur/core/test_mode.py` の `_detect_test_mode()` が環境変数 `TEST_MODE` / `CHAT_TEST_MODE` / `DEBUG` のみを参照しており、YouTube はダミーコメント、OpenAI/音声はモックに切り替わってイベントフローだけを確認できる。
  - 注意: `config.yaml` の `debug` セクション（`test_mode` / `mock_apis` / `verbose_logging` / `log_level`）は項目としては存在するが、現状アプリコードからは参照されておらず、これらを `true` にしても挙動は変わらない。切り分けは上記の環境変数で行う。

## 関連

- [[aituber-run]] — 起動・停止・`status`・`monologue.log` の見方
- [[aituber-character]] — キャラ YAML の検証（`character validate` / `info`）、`voice` 設定
- [[aituber-dev]] — イベント駆動アーキテクチャ・テスト
- 参照ファイル/doc:
  - `config.py`（`validate_config` / `reload_config`）, `config.yaml`, `.env.template`
  - `scripts/check_youtube_config.py`
  - `app/aivis_speech_adapter.py`, `app/openai_adapter.py`
  - `murmur/obs_adaper.py`, `murmur/services/obs_text_manager.py`, `murmur/services/integrated_comment_manager.py`
  - `doc/quick_setup_guide.md`
