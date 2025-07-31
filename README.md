# AITuberぶつぶつシステム

![AITuber](images/AIVTuber.png)

AITuberのための自動配信システム。テーマに基づいて自動的に話題を展開し、視聴者とインタラクティブなコミュニケーションを行います。

## 機能

- テーマベースの自動会話生成
- 視聴者コメントへの応答
- OBSと連携した字幕表示
- AivisSpeechを使用した音声合成（ボイスモデル: 蒼月ハヤテ）
- 配信サマリーの自動生成

## セットアップ

### 必要なソフトウェア

- Python 3.8以上
- Poetry（パッケージ管理）
- AivisSpeech Engine
- OBS Studio
- VB-CABLE（音声出力用）

### インストール手順

1. リポジトリのクローン：
```bash
git clone [repository-url]
cd monologue
```

2. 依存関係のインストール：
```bash
poetry install
```

3. AivisSpeechのセットアップ：
   - AivisSpeech Engineをセットアップし、起動します。
   - [蒼月ハヤテ ボイスモデル](https://hub.aivis-project.com/aivm-models/eefe1fbd-d15a-49ae-bc83-fc4aaad680e1)をダウンロードし、AivisSpeech Engineにインポートします。

4. OBSのセットアップ：
   - OBS Studioをインストール
   - WebSocketサーバーを有効化（ツール > WebSocket Server Settings）
   - テキストソースを追加（名前: "answer"）

5. VB-CABLEのセットアップ：
   - [VB-CABLE](https://vb-audio.com/Cable/)をダウンロードしてインストール
   - システムの音声出力デバイスとして設定
   - OBSでVB-CABLEを音声キャプチャデバイスとして追加

### 設定

1. `config.yaml`の設定：
```yaml
api_keys:
  openai: "your-api-key"
paths:
  voicevox: "path-to-voicevox"
```

2. テーマファイルの準備：
   - `prompts/`ディレクトリにテーマファイルを配置
   - 例: `test_theme.txt`

## 実行方法

### Windows環境

1. PowerShellを管理者として実行し、以下のコマンドで実行ポリシーを設定（初回のみ）：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

2. 起動：
```powershell
.\start_monologue.ps1
```

3. テーマを指定して起動：
```powershell
.\start_monologue.ps1 --theme test_theme.txt
```

4. 停止：
```powershell
.\stop_monologue.ps1
```

### Mac/Linux環境

1. 起動：
```bash
./start_monologue.sh
```

2. テーマを指定して起動：
```bash
./start_monologue.sh --theme test_theme.txt
```

3. 停止：
```bash
./stop_monologue.sh
```

## 参考資料

- [参考YouTube動画](https://www.youtube.com/watch?v=GvLcysqJIuk)

## トラブルシューティング

### 一般的な問題

1. AivisSpeechが起動していない：
   - AivisSpeech Engineを起動してから、プログラムを開始してください
   - エラーメッセージ: "接続エラー: HTTPConnectionPool..."

2. OBS接続エラー：
   - OBSが起動していることを確認
   - WebSocketサーバーが有効になっていることを確認
   - エラーメッセージ: "Failed to connect to OBS"

3. 音声が出力されない：
   - VB-CABLEが正しくインストールされているか確認
   - システムの音声出力デバイスがVB-CABLEになっているか確認
   - OBSでVB-CABLEからの音声をキャプチャしているか確認

### Windows固有の問題

1. スクリプト実行エラー：
   - PowerShellの実行ポリシーを確認
   - 管理者権限で実行が必要な場合あり

2. プロセス終了エラー：
   - タスクマネージャーからpythonプロセスを手動で終了

### Mac/Linux固有の問題

1. 実行権限エラー：
```bash
chmod +x start_monologue.sh stop_monologue.sh
```

2. シェルスクリプトエラー：
   - 改行コードがLF（Unix形式）になっているか確認

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は`LICENSE`ファイルをご覧ください。