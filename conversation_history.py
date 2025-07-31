import os
import json
from datetime import datetime, timezone
import re
import time
import threading
import queue
from typing import Optional, Dict, List, Any
from openai_adapter import OpenAIAdapter
from config import config
from dataclasses import dataclass, asdict

@dataclass
class ConversationEntry:
    """個別の会話エントリーを表すデータクラス"""
    timestamp: str
    user_message: str
    ai_response: str
    context: Optional[str] = None

class ConversationHistory:
    def __init__(self, openai_adapter: OpenAIAdapter, history_dir="conversation_history"):
        """
        会話履歴を管理するクラス
        
        Args:
            openai_adapter (OpenAIAdapter): 初期化済みのアダプターインスタンス
            history_dir (str): 会話履歴を保存するディレクトリ
        """
        self.history_dir = history_dir
        self.ensure_history_dir()
        self.max_recent_conversations = config.memory.max_recent_conversations
        self.compression_threshold = config.memory.compression_threshold
        
        self.openai_adapter = openai_adapter
        if self.openai_adapter:
            print("✅ ConversationHistoryがOpenAIAdapterを受け取りました")
        else:
            print(f"⚠️ ConversationHistoryがOpenAIAdapterを受け取れませんでした。圧縮機能は利用できません。")
        
        self._compression_queue = queue.Queue()
        self._compression_locks = {}
        self._compression_thread = None
        self._stop_compression_thread = False
        self._start_compression_worker()
    
    def __del__(self):
        """デストラクタ - フォールバック用（明示的なstop()を推奨）"""
        try:
            self.stop()
        except:
            pass
    
    def stop(self):
        """
        圧縮スレッドを安全に停止させるための明示的なメソッド
        """
        print("🔄 ConversationHistoryの停止処理を開始します...")
        self._stop_compression_worker()
        print("✅ ConversationHistoryの停止処理が完了しました")
    
    def _start_compression_worker(self):
        """圧縮処理用のワーカースレッドを開始"""
        if self._compression_thread is None or not self._compression_thread.is_alive():
            self._stop_compression_thread = False
            self._compression_thread = threading.Thread(
                target=self._compression_worker, 
                daemon=True, 
                name="ConversationCompressionWorker"
            )
            self._compression_thread.start()
    
    def _stop_compression_worker(self):
        """圧縮処理用のワーカースレッドを停止"""
        self._stop_compression_thread = True
        if self._compression_thread and self._compression_thread.is_alive():
            self._compression_queue.put(None)
            self._compression_thread.join(timeout=5.0)
    
    # === ▼▼▼ 最重要修正箇所 ▼▼▼ ===
    def _compression_worker(self):
        """バックグラウンドで圧縮処理を実行するワーカー。デッドロックを回避する。"""
        while not self._stop_compression_thread:
            task = None
            try:
                task = self._compression_queue.get(timeout=1.0)
                if task is None:
                    break
                
                username, history_data = task
                
                # 圧縮処理（API呼び出し）をロックの外で実行
                self._compress_and_save_history(username, history_data)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 圧縮ワーカーでエラーが発生: {e}")
            finally:
                # タスクが実際に取得できた場合のみtask_done()を呼ぶ
                if task is not None:
                    self._compression_queue.task_done()
    # === ▲▲▲ 最重要修正箇所 ▲▲▲ ===

    def ensure_history_dir(self):
        """会話履歴ディレクトリが存在することを確認"""
        if not os.path.exists(self.history_dir):
            os.makedirs(self.history_dir)
    
    def get_user_history_path(self, username):
        """ユーザーごとの履歴ファイルパスを取得"""
        safe_username = re.sub(r'[\\/*?:"<>|]', "_", username)
        return os.path.join(self.history_dir, f"{safe_username}.json")
    
    def add_conversation(self, username, message, response, user_info=None):
        """
        会話を履歴に追加
        """
        # ユーザー固有のロックを取得
        if username not in self._compression_locks:
            self._compression_locks[username] = threading.Lock()
        
        with self._compression_locks[username]:
            history = self.load_history(username)
            
            for existing_conv in history:
                if (existing_conv.get("message") == message and 
                    existing_conv.get("response") == response):
                    print(f"重複する会話を検出しました: {message}")
                    return
            
            time.sleep(0.001)
            timestamp = datetime.now().isoformat()
            
            conversation = {
                "timestamp": timestamp,
                "message": message,
                "response": response
            }
            
            if user_info:
                conversation["user_info"] = user_info
            
            history.append(conversation)
            
            # 閾値に達したら非同期圧縮をスケジュール
            if len(history) >= self.compression_threshold:
                self.save_history(username, history) # 先に保存してデータロスを防ぐ
                try:
                    history_copy = [conv.copy() for conv in history]
                    self._compression_queue.put((username, history_copy), block=False)
                    print(f"📊 {username}の会話履歴圧縮をスケジュールしました（バックグラウンド処理）")
                except queue.Full:
                    print(f"⚠️ 圧縮キューが満杯です。{username}の圧縮をスキップします")
            else:
                self.save_history(username, history)
    
    def load_history(self, username):
        """ユーザーの会話履歴を読み込む"""
        history_path = self.get_user_history_path(username)
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ 警告: {history_path} の読み込みに失敗しました。新しい履歴を作成します。")
                return []
        return []
    
    def save_history(self, username, history):
        """履歴をファイルに保存する"""
        history_path = self.get_user_history_path(username)
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ エラー: {username}の履歴保存に失敗: {e}")
    
    def get_recent_conversations(self, username, limit=5):
        """最近の会話を取得"""
        with self._compression_locks.get(username, threading.Lock()):
            history = self.load_history(username)
        return history[-limit:] if history else []
    
    def search_conversations(self, username, keyword):
        """キーワードに基づいて会話を検索"""
        with self._compression_locks.get(username, threading.Lock()):
            history = self.load_history(username)
        results = []
        keyword_lc = keyword.lower()
        
        for conversation in history:
            if (keyword_lc in conversation.get("message", "").lower() or 
                keyword_lc in conversation.get("response", "").lower() or
                keyword_lc in self._safe_dumps(conversation.get("user_info", "")).lower()):
                results.append(conversation)
        
        return results
    
    def get_user_info(self, username):
        """ユーザー情報を取得"""
        with self._compression_locks.get(username, threading.Lock()):
            history = self.load_history(username)
        if history and "user_info" in history[0]:
            return history[0]["user_info"]
        return None
    
    def update_user_info(self, username, user_info):
        """ユーザー情報を更新"""
        with self._compression_locks.get(username, threading.Lock()):
            history = self.load_history(username)
            if history:
                history[0]["user_info"] = user_info
                self.save_history(username, history)
    
    # === ▼▼▼ 最重要修正箇所 ▼▼▼ ===
    def _compress_and_save_history(self, username: str, history: List[Dict]):
        """
        API呼び出しとファイル保存を安全に分離して実行する。
        """
        # ステップ1: API呼び出しでユーザーカードを生成 (ロックの外)
        user_card = self._create_user_card_from_api(username, history)
        if not user_card:
            print(f"⚠️ {username}のユーザーカード生成に失敗したため、圧縮を中止します。")
            return

        # ステップ2: ファイル更新 (ロックの内側)
        with self._compression_locks[username]:
            try:
                # 最新の会話を取得
                recent_conversations = history[-self.max_recent_conversations:]
                
                # 圧縮後のデータ構造を作成
                compressed_history = [{
                    "timestamp": datetime.now().isoformat(),
                    "message": "会話履歴の圧縮",
                    "response": "古い会話を圧縮し、情報カード形式で要約を作成しました。",
                    "user_info": user_card
                }]
                compressed_history.extend(recent_conversations)
                
                # 履歴を保存
                self.save_history(username, compressed_history)
                print(f"✅ {username}の会話履歴圧縮が完了しました")
            except Exception as e:
                print(f"❌ {username}の会話履歴保存中にエラーが発生: {e}")

    def _create_user_card_from_api(self, username: str, history: List[Dict]) -> Optional[Dict]:
        """
        APIを呼び出してユーザーカードを生成する。この関数はロックを行わない。
        """
        if self.openai_adapter is None:
            print("❌ OpenAIAdapterが利用できません。圧縮をスキップします。")
            return None
            
        if len(history) < self.compression_threshold:
            return None # 圧縮の必要なし

        try:
            existing_info = history[0].get('user_info', '') if history else ''
            old_conversations = history[:-self.max_recent_conversations]
            
            conversations_text = ""
            for conv in old_conversations:
                conversations_text += f"ユーザー: {conv.get('message', '')}\n"
                conversations_text += f"AI: {conv.get('response', '')}\n"
                conversations_text += f"時間: {conv.get('timestamp', '')}\n\n"
            
            # 元のプロンプトを完全に維持
            prompt = f"""
以下の会話履歴と既存ユーザー情報をどちらも **エンコード→統合(固定化)** し、
配信者が次回以降すばやく想起できる「ユーザーカード」を作成してください。

### 🎯 重要：対象ユーザー特定とフィルタリング
**対象ユーザーID**: {username}

**ステップ1: ユーザー特定**
- 会話履歴から「{username}」がどのような名前・ニックネームで呼ばれているかを特定してください
- 「○○さん」「××ちゃん」「△△くん」など、様々な呼び方を検出してください
- そのユーザーの発言パターンや文体も把握してください

**ステップ2: 情報フィルタリング**
- 特定したユーザーに関連する情報**のみ**を抽出してください
- 他のユーザーに向けた発言や、他ユーザーの話題は**完全に除外**してください
- 混在する応答でも、そのユーザーに関連する部分だけを分析対象とします

### 出力時の必須ルール
1. "感情タグ"として **valence (positive / neutral / negative)** と  
   **arousal (high / medium / low)** を mood に含める。
2. **{username}が実際に口にした**短いフレーズを **cue_phrases** に最大3件保存し、  
   想起手がかりとして機能させる。ただし、他ユーザー名を含むフレーズは避け、  
   そのユーザー固有の表現や特徴的な言い回しを優先する。
3. 情報の確信度を **reliability** に {{{{high | medium | low}}}} で明示。  
   推測や曖昧な内容なら low。
4. 既存情報と矛盾・変化があれば **conflict_note** に簡潔に記載。無ければ空文字 ""。
5. JSON テンプレート以外の文字は絶対に出力しないこと。

### 出力テンプレート
{{{{
  "last_update": "（ISO8601 タイムスタンプ、自動挿入）",
  "history_note": "過去の会話を圧縮し、最新情報を統合。",
  "user_id": "{username}",
  "nickname": "ユーザーの通称・呼び名（あれば）",
  "relationship": "配信者との距離感や立ち位置を簡潔に",
  "mood": {{{{
    "valence": "positive | neutral | negative",
    "arousal": "high | medium | low"
  }}}},
  "topics": ["頻出トピック", "ネタ系歓迎"],
  "cue_phrases": ["実際の短フレーズ1", "実際の短フレーズ2", "実際の短フレーズ3"],
  "last_episode": "直近で印象的だった出来事やセリフ",
  "response_tips": [
    "このユーザーにウケる返しやリアクションのコツを複数"
  ],
  "reliability": "high | medium | low",
  "conflict_note": "矛盾がある場合のみ記載。無ければ空文字。",
  "version": "1.1"
}}}}

既存情報:
{json.dumps(existing_info, ensure_ascii=False, indent=2)}

会話履歴:
{conversations_text}

### 🔍 作業前の最終確認（内部チェック用）
1. このユーザーがどんな名前で呼ばれているか正しく特定する
2. 他ユーザーの情報を誤って含めない
3. このユーザー固有の特徴のみを抽出する
4. nickname欄には実際に呼ばれている名前を入れる

※ 上記確認を内部で完了した後、必ず上記JSON構造のみを返してください。記憶研究に基づく感情タグ、想起手がかり、信頼性管理を重視してください。
"""
            
            new_summary = self.openai_adapter.create_chat_for_response(prompt)
            
            user_card = json.loads(new_summary)
            user_card['last_update'] = datetime.now().isoformat()
            user_card['history_note'] = "過去の会話や配信コメントを要約して、最新情報に反映しました。"
            user_card['user_id'] = username
            return user_card

        except json.JSONDecodeError as e:
            print(f"❌ ユーザーカードのJSONデコードに失敗: {e}")
            return None
        except Exception as e:
            print(f"❌ ユーザーカードのAPI呼び出し中にエラーが発生しました: {e}")
            return None
    # === ▲▲▲ 最重要修正箇所 ▲▲▲ ===

    def _safe_dumps(self, obj):
        """
        オブジェクトを安全にJSON文字列に変換、既に文字列の場合はそのまま返す
        """
        return obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
