# Monologue Agent v2 - 優雅な終了システム ドキュメント

## 📋 概要

Monologue Agent v2では、ユーザーフレンドリーな終了体験を提供するため、**終了挨拶機能**を中核とした優雅な終了システムを実装しています。

### 🎯 実現された機能

- **終了挨拶付き停止**: アプリケーション終了時に音声による挨拶
- **即座停止モード**: 緊急時のための高速強制終了
- **外部プロセス管理**: ターミナルコマンドによる確実な制御
- **視覚的フィードバック**: 絵文字とカラーを使った分かりやすい操作体験

---

## 🚀 基本操作

### アプリケーション起動
```bash
./start_monologue.sh
```
- バックグラウンドでの自動起動
- 既存プロセスの自動検出・置換
- 起動ログの即座確認

### 終了挨拶付き停止（推奨）
```bash
./stop_monologue.sh
```
- 🎙️ **終了の挨拶を開始**
- ⏳ **15秒間の適切な待機**（音声再生完了まで）
- 🎉 **丁寧な完了メッセージ**

### 即座停止（緊急時）
```bash
./stop_monologue.sh --force
```
- 🔥 **即座に強制終了**
- ⚡ **1秒以内で完了**
- 待機時間なし

### ステータス確認
```bash
./status_monologue.sh
```
- 📊 **実行状況の詳細表示**
- 💾 **リソース使用量確認**
- 📄 **ログファイル情報**

---

## 🔧 技術的実装詳細

### シグナル処理の改善

#### `main.py`のシグナルハンドラー
```python
def signal_handler(signum, frame):
    print(f"\n[Main] Signal {signum} received. Initiating shutdown...")
    if 'state_manager' in globals():
        state_manager.is_running = False
    # 音声処理を即座に停止
    if 'audio_manager' in globals():
        print("[Main] Stopping audio processing immediately...")
        audio_manager.stop()
    # KeyboardInterrupt例外を発生させて、メインループのexcept節で処理する
    raise KeyboardInterrupt()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### 音声合成タイムアウト最適化

**`aivis_speech_adapter.py`の調整**:
- `audio_query`: 8秒（終了処理に適切な時間確保）
- `synthesis`: 12秒（音声合成完了まで余裕を持った設定）

### プロセス管理の改良

#### 段階的停止プロセス
1. **SIGINT送信** (Ctrl+Cと同等)
2. **複数回シグナル送信**（確実性向上）
3. **15秒間の丁寧な待機**
4. **強制終了**（SIGKILL）によるフォールバック

---

## 📊 操作モード比較

| **項目** | **通常停止** | **強制停止** |
|----------|-------------|-------------|
| **コマンド** | `./stop_monologue.sh` | `./stop_monologue.sh --force` |
| **終了挨拶** | ✅ あり | ❌ なし |
| **停止時間** | 最大15秒 | 即座（1秒以内） |
| **データ保存** | 安全 | 強制（リスクあり） |
| **推奨用途** | 通常終了 | 緊急時・デバッグ |

---

## 🛠️ トラブルシューティング

### よくある問題と解決方法

#### 問題1: 終了挨拶が流れない
**原因**: 音声合成エンジン（AivisSpeech）との接続問題
**解決**: 
```bash
# 強制停止で一旦終了
./stop_monologue.sh --force

# AivisSpeechエンジンの確認
curl http://127.0.0.1:10101/docs

# 再起動
./start_monologue.sh
```

#### 問題2: プロセスが停止しない
**原因**: 長時間実行中のHTTPリクエスト
**解決**:
```bash
# 複数回強制停止を試行
./stop_monologue.sh --force
./stop_monologue.sh --force

# または直接プロセス終了
pkill -9 -f "python main.py"
```

#### 問題3: 複数プロセスが起動している
**原因**: 前回の終了が不完全
**解決**:
```bash
# 全プロセス確認
ps aux | grep "python main.py"

# 全て強制終了
pkill -f "python main.py"

# クリーンな再起動
./start_monologue.sh
```

---

## 🔍 ログ解析

### 正常な終了パターン
```
[Main] Signal 2 received. Initiating shutdown...
[Main] Stopping audio processing immediately...
🎙️ 終了の挨拶を開始します...
✅ プロセス XXXX が正常に終了しました（Xs秒で完了）
```

### 強制終了パターン
```
🔥 強制終了を実行中...
✅ プロセス XXXX を強制終了しました
```

### 異常パターン
```
⚠️ 15秒経過: 強制終了を実行します
🔥 プロセス XXXX を強制終了しました
```

---

## 📈 パフォーマンス指標

### 正常終了時の目標値
- **応答時間**: 3-8秒以内
- **完了時間**: 15秒以内
- **成功率**: 95%以上

### 強制終了時の目標値
- **応答時間**: 1秒以内
- **完了時間**: 2秒以内  
- **成功率**: 100%

---

## 🌟 今後の改善予定

### Phase 2 機能拡張
- [ ] **カスタム終了メッセージ**: ユーザー固有の挨拶
- [ ] **終了理由の記録**: なぜ終了したかの履歴
- [ ] **グレースフル再起動**: 終了→即座再起動の自動化

### Phase 3 高度な機能
- [ ] **終了予告機能**: X分後に終了するアナウンス
- [ ] **リモート停止**: 他のデバイスからの停止操作
- [ ] **終了統計**: 終了パターンの分析とレポート

---

## 💡 ベストプラクティス

### 日常的な利用
1. **通常終了を基本とする**: `./stop_monologue.sh`
2. **定期的なステータス確認**: `./status_monologue.sh`
3. **ログの定期チェック**: `tail -f monologue.log`

### 開発・デバッグ時
1. **強制停止を活用**: `./stop_monologue.sh --force`
2. **プロセス状況の詳細確認**: `ps aux | grep python`
3. **ログファイルのクリア**: 必要に応じて`rm monologue.log`

### 本番運用時
1. **終了挨拶を最優先**: ユーザー体験の向上
2. **異常終了の監視**: ログパターンの定期確認
3. **自動復旧の準備**: cron等での定期チェック

---

## 📚 関連ドキュメント

- [V2アーキテクチャ原則](requirement_definition_v2.md)
- [テストモードガイド](test_mode_guide.md)
- [クイックセットアップガイド](quick_setup_guide.md)

---

## 📝 変更履歴

| **バージョン** | **日付** | **変更内容** |
|----------------|----------|-------------|
| v1.0 | 2025-07-26 | 初版リリース：基本的な終了挨拶機能 |
| v1.1 | 2025-07-26 | 強制停止モード追加 |
| v1.2 | 2025-07-26 | シグナル処理改善・複数回送信対応 |

---

*このドキュメントは Monologue Agent v2 の優雅な終了システムについて詳細に説明しています。*  
*質問や改善提案がありましたら、開発チームまでお知らせください。* 🚀✨ 