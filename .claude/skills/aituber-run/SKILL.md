---
name: aituber-run
description: AITuberぶつぶつシステム（z-aituber）の起動・停止・状態確認など運用操作を行うときに使う。「配信を始めて/起動して」「止めて/停止して」「いま動いてる?/状態は?」「バックグラウンドで動かして」「テーマやキャラを指定して起動」などのとき。poetry run aituber run/stop/status の使い分け、--theme/--character/--detach/--log-file、AivisSpeech・OBS・VB-CABLE の前提を案内する。
---

# AITuber 起動・停止・運用

z-aituber 本体（main.py）の起動・停止・状態確認を `poetry run aituber` の CLI で行う。実装は `aituber/cli.py`（CLI）と `aituber/ops.py`（プロセス検出・終了・psutil 依存）。

## 使いどころ

- 起動: 「配信を始めて」「起動して」→ `run`
- バックグラウンド: 「裏で動かして」→ `run --detach`
- テーマ/キャラ指定: 「このテーマで」「このキャラで」→ `run --theme ...` / `run --character ...`
- 停止: 「止めて」「停止して」→ `stop`（効かないとき `stop --force`）
- 状態: 「いま動いてる?」「状態は?」→ `status`
- 接続エラーで起動できない/音声・字幕が出ない場合は [[aituber-diagnose]] へ。

## 前提（起動前に満たすこと）

- **AivisSpeech Engine** が起動していること。蒼月ハヤテのボイスモデルを Engine にインポート済みであること（既定キャラ characters/hayate.yaml は speaker_id 1）。接続先は `config.yaml` の `audio.synthesis.aivis_url`（既定 `http://127.0.0.1:10101`）。
- **OBS**: WebSocket Server を有効化し、テキストソース名 `answer` を用意。音声は VB-CABLE を出力デバイスにして OBS で取り込む。`config.yaml` の `obs_subtitles.enabled` で字幕連携を制御。
- **VB-CABLE** を音声出力経路として用意。
- **`.env`**（`.env.template` をコピーして作成）に必須値:
  - `OPENAI_API_KEY`（必須）
  - `YOUTUBE_VIDEO_ID`（必須）
  - `OBS_WS_PASSWORD` / `OBS_WS_HOST`（既定 127.0.0.1）/ `OBS_WS_PORT`（既定 4455）（必須）
  - `AIVIS_SPEECH_API_KEY`（任意）
- 設定確認: インポート時に `config.print_config_status()` が状況を表示。`config.validate_config()` が必須 api_keys（openai, youtube_video_id）と必須 paths（prompts, txt, summary）を検査する。YouTube 設定は `poetry run python scripts/check_youtube_config.py` で確認できる。

## run（起動）

すべてリポジトリルートで実行する。`poetry run aituber ...` を第一に使う。

```bash
# 前景で起動（Ctrl+C で停止）。従来の python main.py と同等
poetry run aituber run

# テーマを指定（prompts/*.txt）
poetry run aituber run --theme prompts/poem.txt

# キャラを指定（省略時は config.yaml の character.yaml_path）
poetry run aituber run --character characters/hayate.yaml

# バックグラウンド起動（ログは monologue.log に追記）
poetry run aituber run --detach

# バックグラウンド + ログ出力先を指定（リポジトリルート相対）
poetry run aituber run --detach --log-file monologue.log
```

- `--detach` は `python -m aituber run ...` を `subprocess.Popen` で起動し、stdout/stderr を `--log-file`（既定 `monologue.log`、リポジトリルート基準）へ**追記**する。Unix は `start_new_session`、Windows は `CREATE_NEW_PROCESS_GROUP` で切り離す。起動後「バックグラウンドで起動しました。ログ: ...」と表示。
- `--theme` / `--character` は前景・`--detach` どちらでも使える。

### 等価コマンド

```bash
poetry run aituber run          # 第一に案内
python -m aituber run           # 同等
python main.py                  # run と同等（引数は main(argv) に渡る形）
python cli.py run --theme prompts/poem.txt   # cli.py は aituber.cli への薄いラッパ。同じサブコマンド＋オプションが使える
```

## stop / shutdown（停止）

```bash
# 通常停止: shutdown_request.txt を作成し、Unix では本体へ SIGINT を送る
poetry run aituber stop

# 強制停止: psutil で本体プロセスを kill
poetry run aituber stop --force   # -f も可

# 互換用: stop と同じ（強制なし・終了ファイルのみ）
poetry run aituber shutdown
```

- `stop`: `find_app_processes()` で本体（`main.py` を含む、または `python -m aituber run`）を探し、無ければ「実行中の AITuber 本体プロセスは見つかりませんでした。」と表示。見つかれば `shutdown_request.txt` を書き込み、各プロセスに **SIGINT**（Unix のみ）を送る。終了処理自体はアプリ側に委ねる（グレースフルシャットダウン）。
- `stop --force`: 上記の終了ファイル作成に加え、`psutil` で各プロセスを **kill**。通常停止で落ちないときに使う。
- `shutdown`: `stop`（force なし）と同じ。互換目的。
- **Windows の注意**: SIGINT は送れない（`signal_interrupt` は False）。終了ファイル `shutdown_request.txt` をアプリがポーリングして終了する方式に依存する（従来の stop_monologue.ps1 と同様）。確実に落としたいときは `stop --force`。

## status（状態確認）

```bash
poetry run aituber status
```

- 本体プロセスの有無を表示（「ステータス: 実行中（N プロセス）」または「ステータス: 停止中（本体プロセスなし）」）。実行中は各 PID とコマンドラインを表示。
- 続けて `monologue.log`（リポジトリルート）のサイズ・行数と**末尾 5 行**を表示。ログが無ければ「まだありません」と表示。
- ログをリアルタイムで追うなら、別途 `poetry run` の外で `tail -f monologue.log` などを使う。

## よくあるつまずき

- **起動はするがエラーが出る/音声・字幕が出ない/コメントが取れない**: AivisSpeech・OBS WebSocket・YouTube・OpenAI への接続を疑う。まず [[aituber-diagnose]] へ。
- **`status` で「停止中」なのに止まっていない感覚**: `find_app_processes` はコマンドラインに `main.py` か `python -m aituber run` を含むプロセスのみ検出する。別の起動方法のプロセスは検出されないことがある。
- **`stop` が効かない**: グレースフル終了待ちか、Windows で SIGINT 不可のケース。`stop --force` を使う。
- **キャラやテーマの確認**: 起動前に `poetry run aituber character info` / `character validate` で確認（[[aituber-character]]）。テーマの作り方は [[aituber-theme]]。

## 関連

- [[aituber-diagnose]] — 起動・接続不良の切り分け（AivisSpeech / OBS / YouTube / OpenAI）
- [[aituber-character]] — キャラ定義の確認・検証・切り替え（`--character`）
- [[aituber-theme]] — テーマファイルの作成・指定（`--theme`）
- [[aituber-dev]] — 開発・テスト・アーキテクチャ

参照ファイル/doc（リポジトリルート相対）:
- `aituber/cli.py`（run/stop/shutdown/status の実装）
- `aituber/ops.py`（プロセス検出・SIGINT・kill・shutdown_request.txt）
- `main.py`（起動エントリ）
- `config.py` / `config.yaml` / `.env.template`（設定）
- `scripts/check_youtube_config.py`（YouTube 設定確認）
- `doc/quick_setup_guide.md`（セットアップ手順）
- `doc/graceful_shutdown_system.md`（終了の仕組み）
