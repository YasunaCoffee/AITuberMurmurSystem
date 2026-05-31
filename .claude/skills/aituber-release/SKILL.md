---
name: aituber-release
description: AITuberぶつぶつシステム（z-aituber）のリリースノートを書く・バージョンを上げるときに使う。「リリースノートを書いて」「変更履歴を更新」「バージョンを上げたい」「リリース準備」などのとき。RELEASE_NOTES.md の書式（バージョン見出し・セクション・互換/移行表）、pyproject.toml の version 2か所、README の参照を案内する。
---

# リリースノートとバージョン更新

ユーザー向け変更履歴 `RELEASE_NOTES.md` の更新と、パッケージバージョンの引き上げを行う。読者はエンドユーザー（運用者）であり、技術的なディレクトリ構成や内部設計は `doc/` へ誘導する。現行版は **1.1.0**。

## 使いどころ

- 「リリースノートを書いて」「変更履歴を更新」「リリース準備」→ `RELEASE_NOTES.md` に新しいバージョン見出しを追加。
- 「バージョンを上げたい」→ `pyproject.toml` の version 2か所と `RELEASE_NOTES.md` を更新。

## 1. 変更点を拾う

直近のリリース見出し（例: `## 1.1.0`）以降のコミット履歴・差分から変更点を集める。このリポジトリではタグ運用は行っていないため、基点は「前回リリースのコミット」（直近のリリース見出しに対応するコミット）を使う。基点が分からないときはまず `git log --oneline` でコミットを眺めて当たりをつける。

```bash
git log --oneline
git log --oneline <前回リリースのコミット>..HEAD
git diff <前回リリースのコミット>..HEAD -- pyproject.toml RELEASE_NOTES.md
```

拾った変更を「ユーザー目線」で整理する。判断基準:

- 何が変わったか（新しいサブコマンド、キャラ定義、設定項目、運用手順など）。
- 移行が要るか（旧コマンド・旧パスからの読み替え）。
- 内部実装の詳細（イベント配線、ハンドラ構造など）は書かず、必要なら `doc/` の該当ドキュメントへリンクで誘導する。

## 2. RELEASE_NOTES.md に追記する

冒頭の概要文の下、`---` の直後に、新しいバージョン見出しを既存より上（新しい順）に置く。書式は既存の `## 1.1.0` セクションに倣う。

- 見出し: `## X.Y.Z（YYYY-MM〜MM 等）`。直下にそのリリースの一言概要（`pyproject.toml` のパッケージ版に言及）。
- セクション（あるものだけ・既存に倣う）:
  - `### CLI（\`poetry run aituber\`）` … サブコマンドや引数の追加・変更。
  - `### キャラクター（Character YAML）` … `characters/*.yaml` まわりの変更。
  - パッケージ／ルート整理など構成の変更（例: `### パッケージ名 \`murmur\``、`### \`app/\` と \`scripts/\``）。
  - `### 運用上の注意` … Windows 差異、依存追加など運用時の留意点。
  - `### 互換・移行` … 「以前 / いま」の2列表で読み替えを示す。
- 各バージョンセクションは前後を `---` で区切る。
- 末尾の `## それ以前` は残す（古い経緯のまとめ）。

互換・移行表の例（既存の書式）:

```markdown
### 互換・移行

| 以前 | いま |
|------|------|
| `python main.py` | 引き続き有効。`poetry run aituber run` も可 |
```

## 3. バージョンを上げる

`pyproject.toml` の version は **2か所** にあり、両方を必ず同じ値に更新する（片方だけにしない）。

```toml
[project]
version = "X.Y.Z"   # 1か所目

[tool.poetry]
version = "X.Y.Z"   # 2か所目
```

更新後に両方が揃っているか確認する。

```bash
grep -n '^version' pyproject.toml
```

## 4. README の参照を確認する

`README.md` は `RELEASE_NOTES.md` と `doc/package_layout.md` を参照している。リンクが切れていないか、最新の説明と矛盾がないか確認する。

```bash
grep -n -i 'RELEASE_NOTES\|package_layout' README.md
```

## 5. リリース前チェック

リリース前にテストが全成功することを確認する。

```bash
poetry run pytest murmur/tests/
```

テストの実行・失敗の調査は [[aituber-dev]] を参照。

## 関連

- [[aituber-dev]] — テスト実行・開発原則（リリース前の全テスト確認）。
- [[aituber-character]] — キャラ定義変更時の検証（リリースノートの記載根拠）。
- 参照ファイル: `RELEASE_NOTES.md`, `pyproject.toml`, `README.md`, `doc/package_layout.md`
- 技術詳細の誘導先（`doc/` 代表例）: `doc/theme_system_guide.md`, `doc/graceful_shutdown_system.md` ほか `doc/` 配下の該当ドキュメント。
