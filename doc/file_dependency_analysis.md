# Monologue システム ファイル依存関係分析

## 概要

`start_monologue.sh` → `main.py` から起動されるmonologueシステムのファイル依存関係を分析し、本番実行に必要なファイルと不要なファイルを特定しました。

## 分析日時
- **分析日**: 2025-07-31
- **対象**: monologue v2システム
- **起動フロー**: `start_monologue.sh` → `main.py`

## 更新履歴
- **2025-07-31**: 挨拶後のコメント処理とテーマ朗読開始ロジックに関する大規模なデバッグと安定化を実施。`v2/controllers/main_controller.py`のロジックを大幅に改善し、関連するテストケースを`v2/tests/controllers/test_main_controller.py`に多数追加。ファイル依存関係自体に変更はないが、システムの安定性が大幅に向上。
- **2025-07-26**: 初回分析を実施。

---

## 🟢 本番実行に**必要なファイル・ディレクトリ**

### コアシステム
```
main.py                     # システムのメインエントリーポイント
start_monologue.sh          # 起動スクリプト
config.py                   # 設定管理システム
config.yaml                 # システム設定ファイル
.env                        # 環境変数ファイル（必須：APIキー等）
pyproject.toml              # Python依存関係定義
poetry.lock                 # 依存関係ロックファイル
```

### v1互換性コンポーネント（本番必須）
```
openai_adapter.py           # OpenAI API通信
conversation_history.py     # 会話履歴管理
memory_manager.py           # メモリ管理
aivis_speech_adapter.py     # 音声合成
```

### v2アーキテクチャ（本番必須）

#### コア機能
```
v2/core/
├── event_queue.py          # イベントキューシステム
├── events.py               # イベント定義
├── logger.py               # ログシステム
├── metrics.py              # メトリクス収集
└── test_mode.py            # テストモード管理
```

#### コントローラー
```
v2/controllers/
└── main_controller.py      # メインコントローラー
```

#### ハンドラー
```
v2/handlers/
├── monologue_handler.py         # 独り言処理
├── comment_handler.py           # コメント処理
├── greeting_handler.py          # 挨拶処理
├── daily_summary_handler.py     # 日次要約処理
├── mode_manager.py              # モード管理
└── master_prompt_manager.py     # マスタープロンプト管理
```

#### サービス
```
v2/services/
├── audio_manager.py             # 音声管理
├── integrated_comment_manager.py # 統合コメント管理
└── prompt_manager.py            # プロンプト管理
```

#### 状態管理
```
v2/state/
└── state_manager.py        # 状態管理
```

#### ユーティリティ
```
v2/utils/
└── comment_filter.py       # コメントフィルター
```

### プロンプトファイル（本番必須）

#### 必須プロンプト
```
prompts/
├── master_prompt.txt           # 全応答の基盤プロンプト
├── persona_prompt.txt          # システムプロンプト
├── integrated_response.txt     # コメント応答
├── initial_greeting.txt        # 開始挨拶
└── ending_greeting.txt         # 終了挨拶
```

#### モード別プロンプト
```
prompts/
├── normal_monologue.txt              # 通常独り言（60%使用）
├── theme_continuation_monologue.txt  # テーマ継続（20%使用）
├── episode_deep_dive_prompt.txt      # 深掘り思考（5%使用）
├── chill_chat_prompt.txt             # 雑談モード（60%使用）
├── viewer_consultation_prompt.txt    # 視聴者相談（40%使用）
└── poem.txt                          # デフォルトテーマファイル
```

### 設定・データディレクトリ
```
v2/config/
└── comment_filter.json     # コメントフィルター設定

conversation_history/       # 会話履歴保存ディレクトリ（空でも必要）
summary/                    # 配信要約保存ディレクトリ（空でも必要）
logs/                       # ログ保存ディレクトリ（空でも必要）

txt/
└── ng_word.txt            # NGワードリスト（コメントフィルタリング用）
```

---

## 🔴 不要なファイル・ディレクトリ（削除候補）

### テスト・開発専用ファイル（29ファイル）
```
v2/tests/                   # テストディレクトリ全体
├── controllers/
│   └── test_main_controller.py
├── handlers/
│   └── test_monologue_handler.py
├── services/
│   ├── test_audio_manager.py
│   └── test_integrated_comment_manager.py
├── test_*.py              # 各種テストファイル（22ファイル）
└── ...

v2/run_integrated_test.py   # 統合テスト実行スクリプト
```

### デバッグ・チェック用スクリプト
```
debug_pytchat_attributes.py # デバッグ用スクリプト
debug_test_mode.py          # テストモード用デバッグ
check_youtube_config.py     # 設定チェック用
advanced_text_processor.py # 未使用コンポーネント
```

### ドキュメントファイル（11ファイル）
```
README.md                   # プロジェクト説明
README_ja.md               # 日本語版README

doc/                       # ドキュメントディレクトリ全体
├── dev_log_v2_bootstrap.md
├── development_summary.md
├── feature_topic_consistency.md
├── graceful_shutdown_system.md
├── monologue_management_system.md
├── quick_setup_guide.md
├── requirement_definition_v2.md
├── test_mode_guide.md
├── theme_system_guide.md
├── youtube_video_id_specification.md
└── コメントがない場合の話の広げ方設定ガイド.md

dev_log/                   # 開発ログディレクトリ全体
├── code_analysis_details.md
├── dev_log20250712.md
├── refactoring_checklist.md
├── refactoring_phase1_summary.md
├── refactoring_plan.md
└── zundamon_dev_log_20250711.md
```

### 使用されていないプロンプトファイル
```
prompts/
├── music_syotaro.txt      # システムで参照されていない
├── yogore_nakahara.txt    # システムで参照されていない
└── test_theme.txt         # テスト用テーマ
```

### ログ・出力ファイル（実行時に再生成される）
```
monologue.log              # 実行時ログ
txt/
├── output_text_history.txt # 出力履歴
├── kioku_hayate.txt       # 記憶データ
└── VTuber_Stream_Classification_Prompt.txt # 未使用

conversation_history/*.json # 既存の会話履歴ファイル
```

### 管理スクリプト（オプション）
```
status_monologue.sh        # ステータス確認用（保持推奨）
stop_monologue.sh          # 停止スクリプト（保持推奨）
```

---

## 🔄 システム起動フロー

1. **`start_monologue.sh`** が **`main.py`** を起動
2. **`main.py`** が以下を順次実行：
   - `config.py` / `config.yaml` から設定読み込み
   - v2アーキテクチャコンポーネントの初期化
   - v1互換コンポーネントの初期化
   - プロンプトファイルの読み込み
   - イベントループの開始

## 📊 削除効果の概算

| カテゴリ | ファイル数 | 削除候補 |
|---------|-----------|----------|
| テストファイル | ~30 | ✅ 全削除可能 |
| ドキュメント | ~20 | ✅ 全削除可能 |
| デバッグ・未使用 | ~10 | ✅ 全削除可能 |
| 実行時生成ファイル | ~5 | ✅ 削除可能（再生成） |
| **総削除候補** | **~65** | **軽量化効果大** |

## 🎯 推奨アクション

### 即座に削除可能
- `v2/tests/` ディレクトリ全体
- `doc/` および `dev_log/` ディレクトリ（このファイル以外）
- `debug_*.py` ファイル群
- 未使用プロンプトファイル
- 実行時生成されるログファイル

### 保持推奨
- 本番実行必須ファイル群
- 管理スクリプト（`stop_monologue.sh` 等）
- `txt/ng_word.txt`（コメントフィルタリング用）

### 本番デプロイ時の最小構成
本番環境では、「必要なファイル・ディレクトリ」セクションに記載されたファイルのみを配置することで：
- **セキュリティ向上**: 不要なファイルによる攻撃面の削減
- **保守性向上**: 管理対象ファイルの削減
- **パフォーマンス向上**: ディスク使用量とファイルシステムの最適化

---

## 🔍 分析方法

この分析は以下の方法で実施されました：

1. **静的コード解析**: `