# Monologue v2 クイックセットアップガイド

## 🚀 5分でセットアップ完了

### Step 1: YouTubeライブ配信の準備

1. **YouTubeでライブ配信を開始**
2. **配信URLをコピー**
   ```
   例: https://www.youtube.com/watch?v=Hy8XMuTYa_g
   ```

### Step 2: ビデオIDの設定

3つの方法から選択してください：

#### 方法A: 自動設定（推奨）
```bash
# 設定確認スクリプトを実行
python check_youtube_config.py

# 画面の指示に従ってURLを入力
```

#### 方法B: 手動設定
```bash
# .envファイルを編集
nano .env

# 以下の行を追加/編集
YOUTUBE_VIDEO_ID=Hy8XMuTYa_g  # ← あなたの配信のビデオID
CHAT_TEST_MODE=false
```

#### 方法C: URLから手動抽出
```
URL: https://www.youtube.com/watch?v=Hy8XMuTYa_g
     ↓
ビデオID: Hy8XMuTYa_g （?v= の後の部分）
```

### Step 3: 接続テスト

```bash
# YouTubeライブコメント接続テスト
python test_youtube_live_simple.py
```

**成功例:**
```
=== YouTube Live Comments Simple Test ===
📺 Video ID: Hy8XMuTYa_g
⏱️  Test Duration: 15 seconds
==================================================
🔌 Connecting to YouTube Live Chat...
✅ Connected successfully!
```

### Step 4: システム起動

```bash
# v2システム全体テスト
cd v2 && python run_integrated_test.py

# または実際のシステム起動
python main_v2.py
```

## 🔧 設定箇所の詳細

### 主要な設定ファイル

| ファイル | 役割 | 設定項目 |
|---------|------|----------|
| `.env` | 環境変数 | `YOUTUBE_VIDEO_ID`, `CHAT_TEST_MODE` |
| `v2/config/comment_filter.json` | コメントフィルター | NGワード、ユーザーブロック |

### 設定の階層構造

```
monologue/
├── .env                           # ← メイン設定ファイル
├── check_youtube_config.py        # ← 設定確認スクリプト
├── test_youtube_live_simple.py    # ← 接続テストスクリプト
└── v2/
    ├── config/
    │   └── comment_filter.json    # ← フィルター設定
    ├── services/
    │   └── integrated_comment_manager.py  # ← ビデオID読み込み箇所
    └── run_integrated_test.py     # ← 統合テスト
```

## 📋 設定パラメータ一覧

### 必須設定

```env
# YouTubeライブ配信のビデオID（必須）
YOUTUBE_VIDEO_ID=Hy8XMuTYa_g

# OpenAI APIキー（必須）
OPENAI_API_KEY=sk-proj-...
```

### オプション設定

```env
# テストモード（オプション）
CHAT_TEST_MODE=false          # false=実際の配信, true=ダミーコメント

# エラー時の動作（オプション）
FORCE_TEST_ON_ERROR=false     # true=エラー時に自動テストモード

# OBS連携（オプション）
OBS_WS_PASSWORD=your_password
OBS_WS_HOST=127.0.0.1
OBS_WS_PORT=4455
```

## 🔍 トラブルシューティング

### よくある問題と解決方法

| エラーメッセージ | 原因 | 解決方法 |
|------------------|------|----------|
| `YOUTUBE_VIDEO_ID not set` | ビデオIDが未設定 | `.env`に`YOUTUBE_VIDEO_ID`を追加 |
| `Chat is not available` | 配信が終了済み | 現在ライブ中の配信IDを指定 |
| `Connection failed` | ネットワークエラー | インターネット接続を確認 |
| `Invalid video ID` | ビデオIDが間違い | YouTubeURLから正しいIDを取得 |

### デバッグ手順

1. **設定確認**
   ```bash
   python check_youtube_config.py
   ```

2. **接続テスト**
   ```bash
   python test_youtube_live_simple.py
   ```

3. **ログ確認**
   ```bash
   # システム実行時のログを確認
   cd v2 && python run_integrated_test.py
   ```

## 🎯 ビデオID取得方法の詳細

### パターン1: 標準URL
```
入力: https://www.youtube.com/watch?v=Hy8XMuTYa_g
出力: Hy8XMuTYa_g
```

### パターン2: 短縮URL
```
入力: https://youtu.be/Hy8XMuTYa_g
出力: Hy8XMuTYa_g
```

### パターン3: 埋め込みURL
```
入力: https://www.youtube.com/embed/Hy8XMuTYa_g
出力: Hy8XMuTYa_g
```

### パターン4: ライブ配信特有のURL
```
入力: https://www.youtube.com/watch?v=Hy8XMuTYa_g&feature=live
出力: Hy8XMuTYa_g
```

## 🔄 設定の変更と反映

### 実行時の設定変更

1. **`.env`ファイルを編集**
2. **アプリケーションを再起動**

```bash
# 設定変更後
python check_youtube_config.py  # 設定確認
python test_youtube_live_simple.py  # 接続テスト
```

### 複数配信の切り替え

```bash
# 配信1
YOUTUBE_VIDEO_ID=VIDEO_ID_1

# 配信2に切り替え
YOUTUBE_VIDEO_ID=VIDEO_ID_2
```

## 📈 動作確認チェックリスト

- [ ] `.env`ファイルが存在する
- [ ] `YOUTUBE_VIDEO_ID`が設定されている
- [ ] `OPENAI_API_KEY`が設定されている
- [ ] `python check_youtube_config.py`が成功する
- [ ] `python test_youtube_live_simple.py`が成功する
- [ ] `cd v2 && python run_integrated_test.py`が成功する

## 🎉 完了！

これでMonologue v2システムがYouTubeライブ配信に接続できる状態になりました。

### 次のステップ

- **コメントフィルター設定**: `v2/config/comment_filter.json`を編集
- **プロンプト調整**: `prompts/`フォルダのテキストファイルを編集
- **システム監視**: メトリクス機能でパフォーマンスを確認

---

**サポート**: 問題が発生した場合は`python check_youtube_config.py`を実行して診断してください。