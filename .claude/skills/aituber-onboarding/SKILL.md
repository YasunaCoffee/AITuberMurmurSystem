---
name: aituber-onboarding
description: AITuberぶつぶつシステム（z-aituber）を初めてセットアップするときに使う。「初めて使う」「セットアップして」「環境構築を手伝って」「ゼロから動かしたい」「初回起動まで導いて」「インストール手順は?」などのとき。前提ソフト導入→clone→poetry install→.env 作成→AivisSpeech/OBS/仮想オーディオ準備→設定検証→初回起動、までを初心者向けに順番に案内する。
---

# はじめてのセットアップ（オンボーディング）

このシステムを**初めて動かす人**を、前提ソフトの導入から初回起動まで一本道で案内する skill。各ステップは「やること → 確認方法 → つまずいたら」の順で進める。詰まったら [[aituber-diagnose]]、起動できたら日々の操作は [[aituber-run]] へ。

Claude へ: ユーザーの OS（Windows / Mac / Linux）を確認し、各ステップを **1つずつ** 提示して、その都度「できたか」を確認してから次へ進む。一気に全部流さない。

## 全体像（必要なもの）

| 種類 | 何 | 必須 | 用途 |
|------|----|------|------|
| ランタイム | Python 3.11 以上 | ✅ | 本体 |
| パッケージ管理 | Poetry | ✅ | 依存インストール・`aituber` コマンド |
| 取得 | Git | ✅ | リポジトリ取得 |
| 音声合成 | AivisSpeech Engine + 蒼月ハヤテ ボイスモデル | ✅ | しゃべる声 |
| API | OpenAI API キー | ✅ | 文章生成 |
| 配信 | OBS Studio（WebSocket 有効化＋テキストソース） | ✅ | 字幕・配信 |
| 音声経路 | 仮想オーディオ（Windows: VB-CABLE 等 / Mac: BlackHole 等） | ✅ | 声を OBS へ送る |
| 配信先 | YouTube ライブ（ビデオ ID） | コメント応答に必要 | 視聴者コメント取得 |

> まず外部接続を減らした**テストモードで起動確認**し（ステップ7）、その後に OBS・YouTube を本接続する流れが安全。

## ステップ1: 前提ソフトを入れる

- **Python 3.11+**: `python --version`（または `python3 --version`）で 3.11 以上を確認。環境に応じて `python` / `python3` を使い分ける（以降のコマンドも同様）。
- **Poetry**: 公式手順でインストール。`poetry --version` で確認。
- **Git**: `git --version` で確認。
- **AivisSpeech Engine** / **OBS Studio** / **仮想オーディオ** は後のステップで設定するので、ここではインストールだけ済ませる。

確認: 上の 3 コマンドがすべてバージョンを返せば OK。

## ステップ2: 取得して依存をインストール

```bash
git clone https://github.com/YasunaCoffee/AITuberMurmurSystem.git
cd AITuberMurmurSystem
poetry install
```

確認: `poetry run aituber --help` がサブコマンド一覧（run / stop / status / shutdown / character）を表示すれば OK。

## ステップ3: `.env` を作って鍵を入れる

API キーなどの**実値は `.env` に書く**。`config.yaml` の `api_keys` は**環境変数名だけ**を書く欄なので**触らない**（既定で `openai: OPENAI_API_KEY` のように対応付けてある）。

```bash
cp .env.template .env
```

`.env` を編集して設定する（`.env.template` のコメントに従う）:

- `OPENAI_API_KEY`（必須）… <https://platform.openai.com/api-keys> で取得。
- `YOUTUBE_VIDEO_ID`（必須）… ライブ配信 URL `https://www.youtube.com/watch?v=XXXXXXXXXXX` の `v=` 以降 11 文字。`validate_config()` は必須扱いなので未設定だと警告が出るが、テストモード（ステップ9）はダミーコメントを使うため、動作確認だけなら実在するライブ ID でなくてよい。
- `OBS_WS_PASSWORD` / `OBS_WS_HOST`（既定 `127.0.0.1`）/ `OBS_WS_PORT`（既定 `4455`）（必須）… ステップ5 の OBS 設定値に合わせる。
- `AIVIS_SPEECH_API_KEY`（任意・空でよい）。

> `.env` は秘密情報。Git にコミットしないこと（`.gitignore` 済み）。

確認: ステップ6 の検証コマンドで読めているか確かめる。

## ステップ4: 必須ディレクトリを作る

**クローン直後は `summary/` が存在しない。** 一方 `config.validate_config()` は `prompts` / `txt` / `summary` の実在を要求するので、起動前に必ず作成する（`prompts/` `txt/` は同梱済み）。

```bash
mkdir -p summary conversation_history
```

確認: `ls -d prompts txt summary` がすべて表示されれば OK。

## ステップ5: AivisSpeech（声）を準備

1. **AivisSpeech Engine を起動**する。
2. 蒼月ハヤテ ボイスモデルを Engine に**インポート**する: <https://hub.aivis-project.com/aivm-models/eefe1fbd-d15a-49ae-bc83-fc4aaad680e1>（既定キャラ `characters/hayate.yaml`、speaker_id 1）。
3. 本体は `config.yaml` の `audio.synthesis.aivis_url`（既定 `http://127.0.0.1:10101`）へ接続する。Engine のアドレスがこれと一致しているか確認。

確認: ブラウザ等で `http://127.0.0.1:10101/version` が応答すれば Engine は起きている。別キャラを使うなら [[aituber-character]] を参照。

## ステップ6: OBS（字幕・配信）を準備

1. OBS で **WebSocket Server を有効化**（「ツール → WebSocket サーバー設定」）。パスワード/ポートを控え、`.env` の `OBS_WS_*` と一致させる。
2. 字幕用に **テキスト（GDI+）ソースを追加し、ソース名を `Answer`** にする（本体は `set_input_settings(name="Answer", ...)` で更新する。**大文字始まりに注意**）。
3. **最小構成は `Answer` テキストソース1つでよい。** `Question` / `SelectedComment` / `Summary` というソース名も実装にあり（`murmur/obs_adaper.py`）、対応機能を使うときに追加する。
4. 字幕連携の有効/無効は `config.yaml` の `obs_subtitles.enabled`（既定 `true`）。

## ステップ7: 音声を OBS へ流す（仮想オーディオ）

1. **仮想オーディオデバイス**（Windows: VB-CABLE / Mac: BlackHole など）をインストール。
2. それを**システムの音声出力デバイス**に設定（AivisSpeech の再生先が OBS に届くようにする）。
3. OBS の「音声入力キャプチャ」で同じ仮想デバイスを取り込む。
4. 再生先デバイスは `config.yaml` の `audio.playback.default_output_device_id`（既定は固定値 `3`）で指定する。**自分の環境のデバイス ID と一致しないことが多い**ので、声が出ない／違うデバイスに出るときはこの値を見直す。

確認: 「ローカルでは聞こえるのに OBS に乗らない」ときは、再生先デバイスと OBS の取り込みデバイスが一致しているかを見る。

## ステップ8: 設定を検証する

```bash
# キャラ定義が読めるか
poetry run aituber character validate characters/hayate.yaml
poetry run aituber character info

# 設定全体の妥当性（必須 api_keys と paths を検査。空リストなら OK）
poetry run python -c "from config import config; print(config.validate_config() or 'All OK')"

# YouTube 設定（.env の存在・ID 形式・キーの有無）
poetry run python scripts/check_youtube_config.py
```

確認: `character validate` が `OK: 蒼月ハヤテ (...)` を返し、`validate_config()` が `All OK` を返せば設定はそろっている。問題が出たら指摘どおりに `.env`／ディレクトリを直す。詳しい切り分けは [[aituber-diagnose]]。

## ステップ9: 初回起動

まず**外部接続を減らしたテストモード**で配線を確認すると安全（YouTube はダミーコメント、OpenAI/音声はモックに切り替わる）。

```bash
# テストモード（環境変数で指定）— Mac/Linux
CHAT_TEST_MODE=true poetry run aituber run
```

Windows では環境変数の付け方が異なる（または `.env` に `CHAT_TEST_MODE=true` を書く）:

```powershell
# PowerShell
$env:CHAT_TEST_MODE="true"; poetry run aituber run
```
```bat
:: コマンドプロンプト
set CHAT_TEST_MODE=true && poetry run aituber run
```

イベントが流れて落ちないことを確認できたら、本番起動する。

```bash
# 本番（前景・Ctrl+C で停止）
poetry run aituber run

# テーマを指定して起動する例
poetry run aituber run --theme prompts/poem.txt
```

停止は別ターミナルで `poetry run aituber stop`（強制は `--force`）。起動・停止・状態・バックグラウンドの詳しい運用は [[aituber-run]]。

## つまずいたら / 次のステップ

- **動かない・接続できない・音や字幕が出ない** → [[aituber-diagnose]]（症状別の対応表あり）。
- **日々の起動・停止・状態確認** → [[aituber-run]]。
- **自分のキャラを作る** → [[aituber-character]]。
- **配信テーマを作る** → [[aituber-theme]]。

## 関連

- [[aituber-run]] — 起動・停止・状態・バックグラウンド運用
- [[aituber-diagnose]] — 環境・設定の不調の切り分け
- [[aituber-character]] — キャラクター定義 YAML
- [[aituber-theme]] — テーマファイル
- 参照: `README.md`（セットアップ）, `doc/quick_setup_guide.md`（YouTube 設定）, `.env.template`, `config.yaml`, `aituber/cli.py`
