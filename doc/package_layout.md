# パッケージ構成（`murmur`）

## 変更の経緯

旧 `v2/` ディレクトリは歴史的に「Monologue Agent v2」向けコードとして置かれていましたが、バージョン番号がパッケージ名に残ると「いまが v2 なのか」「v3 はどこか」が分かりにくいため、**Python パッケージ名を `murmur` に統一**しました（リポジトリ名 AITuber**Murmur**System に合わせた名前です）。

CLI 用の **`aituber`** パッケージとは役割が異なります。

| パッケージ / ディレクトリ | 役割 |
|---------------------------|------|
| `aituber/` | エントリ（`poetry run aituber`）、プロセス操作など |
| `murmur/` | 本番アプリ本体（コントローラ、ハンドラ、サービス、モデル） |
| `app/` | LLM・音声・長期記憶・会話履歴など、ルートに置いていた共通モジュール |
| `scripts/` | リポジトリルート基準で動かすユーティリティ（例: YouTube 設定確認） |
| ルートの `main.py` / `config.py` | エントリと設定ローダ（`config.yaml` 等のパス解決のためルートに維持） |

ドキュメント内の「Monologue Agent v2」などの**製品呼称**は、要件定義書などに残っている場合があります。コード上の import パスは `murmur.*` および `app.*` を指します。

## ディレクトリの目安

- `murmur/controllers/` … メイン制御
- `murmur/handlers/` … モノローグ・コメント・挨拶など
- `murmur/services/` … 音声・OBS・プロンプト等
- `murmur/core/` … イベントキュー・ログ・メトリクス
- `murmur/state/` … 状態管理
- `murmur/runtime/` … キャラクター読み込みなど
- `murmur/models/` … データモデル（キャラクター YAML 等）
- `murmur/tests/` … テスト

詳細な依存関係は `file_dependency_analysis.md` を参照してください（文中の `v2/` は `murmur/` と読み替え）。
