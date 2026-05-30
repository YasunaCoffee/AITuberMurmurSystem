# Claude Code Skills（AITuberMurmurSystem）

このリポジトリで [Claude Code](https://docs.claude.com/claude-code) を使うときの開発・運用支援 skill 群です。各 skill は `<name>/SKILL.md` に置かれ、フロントマターの `description` に書かれた状況（「」内の発話例など）に合致すると自動的に参照されます。手動で呼ぶ場合は `/<name>`。

これらは Claude Code 向けの開発支援であり、パッケージ本体（z-aituber）の挙動には影響しません。

| skill | 使うとき |
|-------|----------|
| [`aituber-onboarding`](aituber-onboarding/SKILL.md) | **初めてのセットアップ**。前提ソフト→clone→`poetry install`→`.env`→AivisSpeech/OBS/仮想オーディオ→検証→初回起動まで初心者向けに案内（最初の入口） |
| [`aituber-run`](aituber-run/SKILL.md) | 起動・停止・状態確認などの運用（`poetry run aituber run/stop/status`、`--theme`/`--character`/`--detach`） |
| [`aituber-character`](aituber-character/SKILL.md) | キャラクター定義 YAML（`characters/*.yaml`）の作成・編集・検証 |
| [`aituber-theme`](aituber-theme/SKILL.md) | テーマファイル（`prompts/*.txt`）の作成・編集・指定 |
| [`aituber-dev`](aituber-dev/SKILL.md) | 機能追加（イベント駆動・責務分離）と TDD・テスト実行 |
| [`aituber-diagnose`](aituber-diagnose/SKILL.md) | 環境・設定の不調の切り分け（AivisSpeech / OBS / YouTube / OpenAI） |
| [`aituber-release`](aituber-release/SKILL.md) | リリースノート（`RELEASE_NOTES.md`）とバージョン更新 |

## 補足

- 本文・出力は日本語（リポジトリの `.claude/CLAUDE.md` が日本語応答を指定）。
- 記載のコマンド・パス・フィールド名は実装（`aituber/cli.py`, `murmur/core/events.py`, `murmur/models/character.py`, `config.yaml` ほか）に合わせて検証済み。コードを変更したら該当 skill も更新してください。
- skill 間は `[[skill-name]]` で相互参照しています。
