---
name: aituber-character
description: AITuberのキャラクター定義 YAML（characters/*.yaml）を新規作成・編集・検証するときに使う。「新しいキャラを作りたい」「声(speaker_id/style)を変えたい」「ペルソナを差し替えたい」「キャラYAMLが正しいか検証して」などのとき。identity/voice/prompts/memory の各フィールド・必須/任意・バリデーション規則、aituber character validate / info を案内する。
---

# キャラクター定義 YAML の作成・検証

`characters/*.yaml` は AITuber の人格・声・プロンプト・記憶を 1 ファイルに集約した定義。システムから分離され、起動時に `--character` か `config.yaml` の `character.yaml_path` で切り替えられる。

## 使いどころ

- 新規作成は **`characters/hayate.yaml` を複製して編集**するのが基本（既定キャラ・全フィールドが揃った参照実装）。
- 声だけ変える、ペルソナ（プロンプト）を差し替える、別名を足す、なども本 skill の対象。
- 編集後は必ず `validate` / `info` で確認する（下記）。

## 構造（4 必須セクション）

トップレベルは `identity` / `voice` / `prompts` / `memory` の 4 セクションが**必須**（欠落で `ValueError`）。`schema_version` は任意で、未知のトップレベルキー・各セクション内の未知フィールドは無視される（`murmur/models/character.py` の `_subset_for_dataclass`）。

### identity（基本情報）

| フィールド | 必須/任意 | 型 | 既定値 | 備考 |
| --- | --- | --- | --- | --- |
| `name` | 必須 | str | — | 空不可（空で `ValueError`）。`Character.name` はこれを返す |
| `description` | 必須 | str | — | キャラ説明 |
| `hashtag` | 任意 | str | `""` | 配信用ハッシュタグ |
| `display_aliases` | 任意 | list/tuple | `()` | 会話ログで AI 発言とみなす別名。list/tuple 以外は `TypeError` |

### voice（音声合成）

`speaker_id` / `style_id` は **int**。値は AivisSpeech のスピーカー（インポート済みボイスモデル）に対応する（合成は `app/aivis_speech_adapter.py` が VoiceConfig を JSON 化して `config.audio.synthesis.aivis_url` へ送る）。

| フィールド | 必須/任意 | 型 | 既定値 |
| --- | --- | --- | --- |
| `speaker_id` | 必須 | int | — |
| `speaker_uuid` | 必須 | str | — |
| `speaker_name` | 必須 | str | — |
| `style_id` | 必須 | int | — |
| `style_name` | 必須 | str | — |
| `style_type` | 必須 | str | — |
| `speed_scale` | 任意 | float | `1.0` |
| `pitch_scale` | 任意 | float | `0.0` |
| `intonation_scale` | 任意 | float | `1.0` |
| `volume_scale` | 任意 | float | `1.0` |
| `pre_phoneme_length` | 任意 | float | `0.1` |
| `post_phoneme_length` | 任意 | float | `0.1` |
| `tempo_dynamics_scale` | 任意 | float | `1.0` |

### prompts（プロンプトファイルパス）

各値は**リポジトリルート相対のテキストファイルパス**（`prompts/` 配下など）。

| フィールド | 必須/任意 | 備考 |
| --- | --- | --- |
| `persona_prompt` | 必須 | 人格定義テキストへのパス |
| `master_prompt` | 必須 | 共通指示テキストへのパス |
| `monologue_prompt` | 任意 | 独り言プロンプト |
| `greeting_prompt` | 任意 | 開始挨拶 |
| `ending_prompt` | 任意 | 終了挨拶 |

### memory（記憶ファイルパス）

各値はリポジトリルート相対のテキストファイルパス（`txt/` 配下など）。

| フィールド | 必須/任意 | 備考 |
| --- | --- | --- |
| `memory_file` | 必須 | 長期記憶ファイル |
| `history_file` | 任意 | 発言履歴ファイル |

## バリデーション規則（要点）

- `identity` / `voice` / `prompts` / `memory` のいずれかが欠落 → `ValueError`。
- `name` が空 → `ValueError`。
- `display_aliases` は list/tuple のみ（list は内部で tuple 化）。それ以外は `TypeError`。
- `speaker_id` / `style_id` は int。
- 未知キー（トップレベル・セクション内）は無視される。`schema_version` は任意。
- 空ファイル・ルートが map でない場合も `ValueError`。

## 検証・確認コマンド

新規 YAML を書いたら、まず構文・必須フィールドを検証する。

```bash
poetry run aituber character validate characters/<name>.yaml
```

成功すると `OK: <name> (<path>)` を表示する。`path` はリポジトリルート相対も可で、相対入力時は絶対化したパス、絶対入力時はそのまま表示される。

読み込み結果を確認する。

```bash
poetry run aituber character info --yaml characters/<name>.yaml
```

出力は先頭に `YAML: <path>`、続けて name / description / hashtag / speaker_id / speaker_name の順。`display_aliases` は設定（非空）のときのみ最後に表示される。`--yaml` 省略時は既定キャラ（`config.yaml` の `character.yaml_path`）を表示する。

## 既定キャラの切り替え

- 永続的に変えるなら `config.yaml` の `character.yaml_path`（既定 `"characters/hayate.yaml"`）を編集。
- 一時的に変えるなら起動時に上書き：

```bash
poetry run aituber run --character characters/<name>.yaml
```

`info` で確認するときは `--yaml` で同様に上書きできる。`prompts`/`memory` のパスはいずれも `config.BASE_DIR`（リポジトリルート）基準で解決される。

## 新規作成の手順（Claude が行うこと）

1. `characters/hayate.yaml` を `characters/<name>.yaml` に複製。
2. `identity` を新キャラに合わせて書き換え（`name` は空にしない）。
3. `voice` を対象 AivisSpeech スピーカーの `speaker_id` / `speaker_uuid` / `speaker_name` / `style_id` / `style_name` / `style_type` に合わせる。
4. `prompts` / `memory` の各テキストファイルをリポジトリルート相対パスで用意・指定（存在するパスにする）。
5. `poetry run aituber character validate characters/<name>.yaml` と `... character info --yaml ...` で確認。
6. 既定にするなら `config.yaml` の `character.yaml_path` を更新。

## 関連

- [[aituber-run]] — 起動と `--character` / `--theme` の指定、`status`/`stop`。
- [[aituber-theme]] — テーマファイル（`prompts/*.txt`）の作成と指定。
- 参照ファイル: `characters/hayate.yaml`（参照実装）, `murmur/models/character.py`（データモデル・バリデーション）, `murmur/runtime/character_runtime.py`（読み込み・パス解決）, `aituber/cli.py`（`character info`/`validate`）, `config.yaml`（`character.yaml_path`）。
- 参照 doc: `doc/persona_prompt_integration_guide.md`, `doc/package_layout.md`。
