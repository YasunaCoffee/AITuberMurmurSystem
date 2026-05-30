# リリースノート

AITuber ぶつぶつシステム（z-aituber）のユーザー向け変更履歴です。技術的なディレクトリ構成は [doc/package_layout.md](doc/package_layout.md) を参照してください。

---

## 開発支援: Claude Code Skills（2026-05-31）

> このエントリはパッケージ版（`pyproject.toml` の `z-aituber`）を **変更しません**。リポジトリで [Claude Code](https://docs.claude.com/claude-code) を使うコントリビュータ／オーナー向けの開発支援の追加です。

`.claude/skills/` に、このリポジトリでの作業を支援する 6 つの skill を追加しました。各 skill は `description` に書かれた状況に合致すると自動的に参照され、手動では `/<name>` で呼べます。記載のコマンド・パス・フィールド名は実装に照らして検証済みです。

| skill | 役割 |
|-------|------|
| `aituber-run` | 起動・停止・状態確認の運用（`poetry run aituber run/stop/status`、`--theme`/`--character`/`--detach`） |
| `aituber-character` | キャラクター定義 YAML（`characters/*.yaml`）の作成・編集・検証 |
| `aituber-theme` | テーマファイル（`prompts/*.txt`）の作成・編集・指定 |
| `aituber-dev` | 機能追加（イベント駆動・責務分離）と TDD・`pytest` 実行 |
| `aituber-diagnose` | 環境・設定の不調の切り分け（AivisSpeech / OBS / YouTube / OpenAI） |
| `aituber-release` | リリースノート（本ファイル）とバージョン更新の手順 |

一覧は [`.claude/skills/README.md`](.claude/skills/README.md) を参照。コードを変更したら該当 skill も更新してください。

---

## 1.1.0（2026-03〜04）

パッケージ版 **1.1.0**（`pyproject.toml`）。CLI の一本化、キャラクター定義のランタイム統合、パッケージ名の整理、ルート直下のモジュール整理を含みます。

### CLI（`poetry run aituber`）

- **`run`** … 従来の `python main.py` と同等の起動。`--theme` / `--character` に対応。
- **`run --detach`** … バックグラウンド起動。ログは既定で `monologue.log`（`--log-file` で変更可）。
- **`stop` / `shutdown`** … 終了リクエスト（`shutdown_request.txt`）。Unix では可能な範囲で SIGINT。
- **`stop --force`（`-f`）** … 本体プロセスの強制終了（`psutil` 利用）。
- **`status`** … 本体プロセスの有無と `monologue.log` 末尾の要約。
- **`character info`** … 読み込んだキャラ YAML の要約。
- **`character validate <path>`** … キャラ YAML の検証。

ルートの `cli.py` は `aituber.cli` への薄いラッパーです。エントリは `python -m aituber` でも同様です。

### キャラクター（Character YAML）

- `characters/*.yaml` 形式のキャラ定義と、`murmur.models.character` による読み込み。
- `murmur.runtime.character_runtime` で起動時に YAML を解決し、音声・プロンプト・記憶パスなどへ配線。
- `config.yaml` の `character.yaml_path` または `--character` で上書き可能。

### パッケージ名 `murmur`（旧 `v2/`）

- アプリ本体コードのトップレベル名を **`murmur`** に統一（リポジトリ名に合わせた命名）。
- import は `murmur.*`。ドキュメント内の「Monologue Agent v2」等の表記は歴史的な呼称として残る場合があります。

### `app/` と `scripts/`（ルート整理）

- **`app/`** … OpenAI 通信、Aivis 音声、長期記憶、会話履歴、テキスト処理ユーティリティなど、ルートにあった共通モジュールを集約。import は `app.*`。
- **`scripts/check_youtube_config.py`** … YouTube 設定確認（リポジトリルート基準で `.env` を参照）。
- **`config.py` / `main.py`** … パス解決のためリポジトリルートに維持。

### 運用上の注意

- **Windows** … 通常の `aituber stop` は終了ファイルとアプリ側のポーリングに依存します。確実に止める場合は `aituber stop --force` を使用してください。
- **依存** … CLI のプロセス検出に **psutil** を追加。

### 互換・移行

| 以前 | いま |
|------|------|
| `python main.py` | 引き続き有効。`poetry run aituber run` も可 |
| `v2/...` | `murmur/...` |
| ルートの `openai_adapter` 等 | `app.openai_adapter` 等 |
| `python check_youtube_config.py` | `python scripts/check_youtube_config.py` |

---

## それ以前

- **初期コミット以降** … テーマベース会話、YouTube コメント、OBS 連携、AivisSpeech など（詳細は [doc/](doc/) 内の設計・要件ドキュメントを参照）。
