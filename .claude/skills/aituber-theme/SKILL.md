---
name: aituber-theme
description: AITuberのテーマファイル（prompts/*.txt の思考実験プロトコル）を作成・編集するときに使う。「新しいテーマを作りたい」「この小説/詩で配信したい」「テーマファイルの書き方は?」「テーマを指定して試したい」などのとき。テーマ構造、prompts/ への配置、--theme / config.theme.current_theme_file での指定、推奨文字数・テスト方法を案内する。
---

# テーマファイルの作成・編集

## 使いどころ

テーマファイルは、特定の文学作品やトピックに沿って配信内容を方向づけるためのテキスト（`prompts/*.txt`）。詩・小説・思考実験など「今日はこの作品で配信したい」を実現する。本体はテーマファイルの内容を朗読し、それを起点にモノローグ（独り言）を展開する。新規作成、既存テーマの編集、起動時の指定までをこの skill で扱う。

## テーマファイルの構造

`doc/theme_system_guide.md` が規定する「思考実験プロトコル」形式は次のとおり（理想形のテンプレート）。次のセクションを順に並べる。

```markdown
# 【思考実験プロトコル】Case:XXX - タイトル

[Objective: 実験目的]
実験の目的や背景を記述

[Hypothesis: 仮説]
分析する仮説や理論を記述

[Input Data: 入力データ]
（原典：作品名・作者名）
実際のテキストデータ（詩や小説の引用など）

[Analysis & Observation Log: 分析と観測ログ]
思考プロセスの例を記述

[Query to External Nodes: 外部ノードへの質問]
視聴者への質問や対話を促すテキスト
```

ポイント:
- `# 【…】Case:XXX - タイトル` の見出しで始める。`Case:001` のように連番にすると整理しやすい。
- `[Input Data]` には必ず原典（作品名・作者名）を明記し、引用本文を置く。
- `[Query to External Nodes]` で視聴者への問いかけを入れると配信が対話的になる。

### 実ファイルとのギャップ（重要）

上はあくまで doc が示すテンプレートで、`prompts/` 配下の実ファイルは見出し名・セクション名・必須/任意の扱いが揺れている。手本として実ファイルを読むときは次を踏まえる。

- 見出し `# 【思考実験プロトコル】` を使うファイルは `prompts/` 配下に**1つも無い**。`[Hypothesis]` を含むファイルも**無い**。`[Query to External Nodes]` を含むのは `prompts/yogore_nakahara.txt` のみ。
- **最も完全な実例は `prompts/poem.txt`**（中原中也「よごれっちまった悲しみに」）。ただし見出しは `# 【詩的言語探索記録】Case:00 - …`、セクションは `[Objective]` / `[Observation]` / `[Input Data]` / `[Analysis & Observation Log: 分析と水槽からの考察]` / `[Question to Everyone]` という**別バリエーション（詩的言語探索記録形式）**で、`[Hypothesis]` と `[Query to External Nodes]` は含まない。「思考実験プロトコル」形式そのものの手本ではない点に注意。
- `prompts/yogore_nakahara.txt` は `[Analysis & Observation Log]` と `[Query to External Nodes]` だけを持つ**断片**（見出し・`[Objective]`・`[Input Data]` 等は無い）。`[Query to External Nodes]` の書き方の参考にはなる。
- つまり `[Hypothesis]` や `[Query to External Nodes]` は実ファイルでは省略・改称されうる。新規作成では上のテンプレートに沿いつつ、各セクション名は実ファイルに合わせて適宜読み替えてよい。

## 配置と推奨量

- 置き場所: `prompts/` ディレクトリ直下に `.txt` で作成（例: `prompts/my_novel.txt`）。
- 文字コード: UTF-8（他のエンコーディングだと読み込まれない）。
- 分量: 1000〜2000 文字程度（朗読時間を考慮）。日本語では文字数基準を優先する。
  - `doc/theme_system_guide.md` は「推奨2KB以下」とも書くが、日本語マルチバイトでは 2KB ≒ UTF-8 で約 670 字相当で、1000〜2000 字とは両立しない。実例 `prompts/poem.txt` 自身も 1253 字・約 3.3KB で 2KB を超えているため、バイト数は目安にせず文字数で見ればよい。

## 指定方法（3 通り）

1. コマンドライン引数（最優先・お試しに最適）

```bash
poetry run aituber run --theme prompts/my_novel.txt
```

2. `config.yaml` の `theme` セクション

```yaml
theme:
  default_theme_file: "prompts/poem.txt"   # 既定のテーマファイル
  current_theme_file: null                 # 現在使用中。null なら default_theme_file を使用
```

`current_theme_file` を指定すればそれが使われ、`null` のときは `default_theme_file`（既定 `prompts/poem.txt`）が使われる。

3. ランタイムで動的に変更

```python
# MonologueHandler のインスタンスが利用可能な場合
monologue_handler.set_theme_file("prompts/new_theme.txt")
```

## config.theme の主パラメータ

```yaml
theme:
  min_theme_duration: 60        # 最小テーマ継続時間（秒）
  max_theme_duration: 120       # 最大テーマ継続時間（秒）
  min_interest_score: 6         # テーマ開始の最小スコア
  continuation_threshold: 5     # 継続判定の最小スコア
  default_theme_file: "prompts/poem.txt"
  current_theme_file: null
```

## 作ったら起動して試す

ファイルを作成・編集したら `--theme` で起動して挙動を確認する。

```bash
poetry run aituber run --theme prompts/my_novel.txt
```

起動・停止・ログ確認の詳細は [[aituber-run]] を参照。書き方の手本としては、最も完全な実例 `prompts/poem.txt`（中原中也「よごれっちまった悲しみに」。ただし「詩的言語探索記録形式」の別バリエーション）と、`[Query to External Nodes]` を含む唯一のファイル `prompts/yogore_nakahara.txt`（断片）の両方を読むとよい。詳しくは上の「実ファイルとのギャップ」を参照。

## 関連

- [[aituber-run]] — 作ったテーマで起動・停止・状態確認する
- [[aituber-character]] — キャラクター定義（prompts/ の各種プロンプトとの関係）
- doc: `doc/theme_system_guide.md` — テーマシステムの全体仕様（テンプレートの理想形）
- 例: `prompts/poem.txt` — 最も完全な実例（詩的言語探索記録形式の別バリエーション）
- 例: `prompts/yogore_nakahara.txt` — `[Query to External Nodes]` を含む唯一の実ファイル（断片）
- 設定: `config.yaml` の `theme` セクション
