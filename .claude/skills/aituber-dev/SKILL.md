---
name: aituber-dev
description: AITuberぶつぶつシステムに新しい機能（イベント/コマンド/ハンドラ/サービス）を追加したり、テストを書く・実行するときに使う。「ハンドラを追加したい」「新しいイベント/コマンドを足す」「機能を実装して」「テストを書いて/動かして」「アーキテクチャに沿って直して」などのとき。murmur のイベント駆動・責務分離の原則、events.py→handler→main.py 配線→main_controller の手順、.cursorrules の TDD ループ、pytest 実行を案内する。
---

# 機能追加（イベント駆動）とテスト

murmur パッケージ（本番アプリ本体）はイベント駆動・責務分離で設計されている。機能追加・修正・テストは必ずこの原則に沿って行う。

## アーキテクチャ要点

中核は `murmur/core/events.py` の 2 つのベース（いずれも `@dataclass(frozen=True)`）。

- `Event`: 「何かが起きた」を示す。フィールド無し。
- `Command`: 「何かを実行せよ」を示す。必須フィールド `task_id: str`。

これらが `EventQueue`（`murmur/core/event_queue.py`、`queue.Queue` のラッパ）を流れる。`main.py` のメインループが `event_queue` から取り出し、型を見てディスパッチする。

- **Command** → `main.py` の `command_handlers` dict（Command 型 → 処理関数）。
- **Event** → `MainController.process_item()`（`murmur/controllers/main_controller.py`）。MainController は `event_handlers` dict（Event 型 → 処理メソッド）でディスパッチする。

ハンドラとサービスが Event/Command を生む。

- **Handler**（`murmur/handlers/`）= 反応型。`handle_prepare_X(command)` が **daemon thread** を起動 →`_execute_X_in_background()` が重い処理（LLM 呼び出し等）を行い、完了したら `*Ready` Event を `event_queue.put()`。**例外時も、謝罪系のフォールバック文を載せた `*Ready` Event を put する**のが既存の慣習（例: `monologue_handler` は例外時に `MonologueReady` にフォールバック文「うーん、今ちょっと思考が整理できていないみたいです。」を入れて put、`comment_handler` は `["コメントありがとうございます！"]`、`greeting_handler` は定型の挨拶文を put）。`ServiceErrorOccurred(source, error)` は `events.py` に定義はあるが、現状 murmur 配下のどこからも import / put されていない（未使用）。エラーを別経路で通知したい場合は別途設計判断が必要。
- **Service**（`murmur/services/`）= 能動型。`start()`/`stop()` で監視・ワーカースレッドを回し、自発的に Event を put する（例: `IntegratedCommentManager` が `NewCommentReceived`、`AudioManager` が `SpeechPlaybackCompleted`）。

代表例（既存）:

- Command: `PrepareMonologue` / `PrepareCommentResponse` / `PrepareInitialGreeting` / `PrepareEndingGreeting` / `PrepareDailySummary` / `PlaySpeech` / `FetchComments` / `Shutdown`
- Event: `AppStarted` / `MonologueReady` / `CommentResponseReady` / `InitialGreetingReady` / `EndingGreetingReady` / `DailySummaryReady` / `NewCommentReceived` / `SpeechPlaybackCompleted` など（`ServiceErrorOccurred` も `events.py` に定義されているが現状未使用）

## Handler と Service の使い分け

- **反応型なら Handler**: コマンドを受けて一回処理し、結果 Event を返す（生成タスク）。`murmur/handlers/` に置く。
- **能動型なら Service**: 外部入力の監視や音声再生など、自分で回り続けて Event を能動的に発行する。`murmur/services/` に置く。

## 新ハンドラ追加の配線手順（5 ステップ）

新しい生成タスク（Handler）を足すときは、この順で配線する。

1. **events.py** — `murmur/core/events.py` に `PrepareX(Command)` と `XReady(Event)` を追加（`@dataclass(frozen=True)`。Command は `task_id` を含む）。
2. **handlers/** — `murmur/handlers/x_handler.py` に Handler クラスを追加。`__init__(self, event_queue, ...)` を持ち、`handle_prepare_x(self, command)` で daemon Thread を起動、`_execute_x_in_background()` で処理し `XReady` を `event_queue.put()`。**例外時は既存ハンドラに倣い、フォールバック文を載せた `XReady` を put する**（既存ハンドラは `ServiceErrorOccurred` を put していない。`events.py` に定義はあるが未使用）。
3. **main.py** — `main()` 内でハンドラを初期化し、`command_handlers` dict に `PrepareX: x_handler.handle_prepare_x` を登録。
4. **main_controller.py** — `MainController.__init__` の `event_handlers` dict に `XReady: self.handle_x_ready` を登録し、`handle_x_ready(self, event)` メソッドを実装（多くは `state_manager` を遷移させ `PlaySpeech` を put する）。
5. **tests/** — `murmur/tests/` に対応するテストを追加（下記）。

```python
# events.py 追加例
@dataclass(frozen=True)
class PrepareX(Command):
    task_id: str

@dataclass(frozen=True)
class XReady(Event):
    task_id: str
    sentences: List[str]
```

```python
# main.py: command_handlers への登録
command_handlers = {
    PlaySpeech: audio_manager.handle_play_speech,
    PrepareX: x_handler.handle_prepare_x,
    # ...
}
```

能動型なら Service として `murmur/services/` に追加し、`main.py` で `start()`/`stop()` を呼ぶ（`command_handlers`/`event_handlers` への登録は put する Event/受ける Command に応じて）。

## 責務分離の原則

murmur のサブパッケージは責務で分かれている。新コードは正しい場所に置く。

- `controllers/` = 制御（MainController が Event を受けて次の Command を発行）
- `handlers/` = 生成（LLM などで文章を作り `*Ready` を返す）
- `services/` = 外部連携・音声（YouTube コメント、AivisSpeech 音声、OBS 字幕）
- `core/` = 基盤（events, event_queue, logger など）
- `state/` = 状態（`StateManager`, `SystemState`）
- `models/` `runtime/` = キャラクター（`Character` モデルと `init_character`/`get_character` ランタイム）

設計判断に迷ったら `doc/` の該当ドキュメントを必ず確認してから実装する（package_layout.md, monologue_management_system.md, graceful_shutdown_system.md など）。

## TDD ループ（.cursorrules）

`.cursorrules` の開発原則を厳守する。

1. 機能を **一つ** 実装する。
2. その機能に対するテストを **必ず** 作成する。
3. 全テストの成功を確認してから次へ進む。

```bash
poetry run pytest murmur/tests/
```

全成功を確認できたら次の機能へ。doc の設計方針と murmur の原則（イベント駆動・責務分離）を逸脱しないこと。

## テストの場所・命名・実行

- 置き場所: `murmur/tests/` 配下の `test_*.py`。種類別サブディレクトリあり: `controllers/` `handlers/` `services/`。新 Handler のテストは `murmur/tests/handlers/`、新 Service は `murmur/tests/services/`、MainController の挙動は `murmur/tests/controllers/`。
- `murmur/tests/conftest.py` に session スコープの autouse fixture があり、全テスト前に `init_character()` を呼ぶ（`get_character()` 依存コードがそのまま動く）。
- `pyproject.toml` の `[tool.pytest.ini_options] pythonpath = ["."]` によりリポジトリルートから実行する前提。`import murmur.*` / `import app.*` がそのまま通る。

実行コマンド:

```bash
poetry run pytest murmur/tests/            # 全テスト
poetry run pytest murmur/tests/ -v         # 詳細表示
poetry run pytest murmur/tests/handlers/test_monologue_handler.py   # ファイル単位
```

テスト方針: イベント駆動なので、Handler は「コマンドを渡す→`event_queue` に期待した `*Ready` が put される」ことを検証する。失敗時も `*Ready`（フォールバック文を載せたもの）が put される前提で検証する（既存ハンドラは例外時に `ServiceErrorOccurred` を put しない。put されない Event を検証しないこと）。MainController は `process_item(event)` 後のキュー内容・状態遷移を検証する（`run_once(blocking=False)` でループ 1 回分を回せる）。

## lint

ruff の設定（`line-length = 120`）は `pyproject.toml` の `[tool.ruff]` にある。ただし **ruff 自体は依存として宣言されていない**（`[tool.poetry.group.dev.dependencies]` は `pytest` のみ）。そのため `poetry` 環境にはデフォルトで入っておらず、利用時は別途インストールが必要。

```bash
poetry run pip install ruff   # poetry 環境へ追加して使う場合
poetry run ruff check murmur/

# あるいは隔離実行 / グローバルの ruff
uvx ruff check murmur/
ruff check murmur/
```

## 関連

- 関連 skill: [[aituber-run]]（起動・stop・status・detach の運用）, [[aituber-character]]（キャラ YAML の追加・検証）, [[aituber-theme]]（テーマファイル）, [[aituber-diagnose]]（不具合調査）, [[aituber-release]]（バージョン更新・RELEASE_NOTES）
- 中核実装: `murmur/core/events.py`, `murmur/core/event_queue.py`, `murmur/controllers/main_controller.py`, `main.py`
- Handler の手本: `murmur/handlers/monologue_handler.py`, `murmur/handlers/daily_summary_handler.py`, `murmur/handlers/comment_handler.py`, `murmur/handlers/greeting_handler.py`
- Service の手本: `murmur/services/integrated_comment_manager.py`, `murmur/services/audio_manager.py`, `murmur/services/obs_text_manager.py`
- テスト: `murmur/tests/`, `murmur/tests/conftest.py`
- 設計ドキュメント: `doc/package_layout.md`, `doc/monologue_management_system.md`, `doc/graceful_shutdown_system.md`
- 開発原則: `.cursorrules`
