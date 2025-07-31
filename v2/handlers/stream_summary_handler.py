import threading
import os
import json
import sqlite3
from datetime import datetime
from typing import Optional

from v2.core.event_queue import EventQueue
from v2.core.events import StreamSummaryReady, PrepareStreamSummary
from config import config


class StreamSummaryHandler:
    """配信終了時のサマリー生成と会話ログ保存を担当するハンドラー。"""

    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        self.summary_dir = "summaries"
        
        # summariesディレクトリを作成
        os.makedirs(self.summary_dir, exist_ok=True)
        
        print(f"[StreamSummaryHandler] Initialized with summary directory: {self.summary_dir}")

    def handle_prepare_stream_summary(self, command: PrepareStreamSummary):
        """
        PrepareStreamSummaryコマンドを処理する。
        バックグラウンドで配信サマリーと会話ログを生成し、完了時にイベントを発行する。
        """
        print(f"[StreamSummaryHandler] Received command: {command}")

        # バックグラウンドスレッドで重い処理を実行
        thread = threading.Thread(
            target=self._execute_in_background, args=(command,), daemon=True
        )
        thread.start()

    def _execute_in_background(self, command: PrepareStreamSummary):
        """バックグラウンドで配信サマリーを実行し、結果をイベントキューに入れる"""
        print(f"[StreamSummaryHandler] Processing stream summary for task: {command.task_id}")

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = os.path.join(self.summary_dir, f"stream_summary_{timestamp}.md")
            log_file = os.path.join(self.summary_dir, f"conversation_log_{timestamp}.json")
            
            print("📝 会話ログを保存しています...")
            
            # 会話ログを保存
            log_success = self._save_conversation_logs(log_file)
            
            print("📊 配信サマリーを生成しています...")
            
            # 会話ログからサマリーを生成
            if log_success and os.path.exists(log_file):
                summary_success = self._generate_summary_from_logs(log_file, summary_file)
            else:
                # フォールバック：テンプレートサマリー
                summary_success = self._generate_template_summary(summary_file)
            
            # 完了イベントを発行
            event = StreamSummaryReady(
                task_id=command.task_id,
                summary_file=summary_file if summary_success else None,
                log_file=log_file if log_success else None,
                success=summary_success and log_success
            )
            self.event_queue.put(event)
            
            if summary_success:
                print(f"✅ サマリーが生成されました: {summary_file}")
            if log_success:
                print(f"✅ 会話ログが保存されました: {log_file}")
                
        except Exception as e:
            print(f"[StreamSummaryHandler] Error during stream summary generation: {e}")
            # エラー時のイベント発行
            event = StreamSummaryReady(
                task_id=command.task_id,
                summary_file=None,
                log_file=None,
                success=False,
                error_message=str(e)
            )
            self.event_queue.put(event)

    def _save_conversation_logs(self, log_file: str) -> bool:
        """会話ログを保存する"""
        try:
            # 会話ログの保存開始
            log_data = {
                "session_info": {
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                "conversations": []
            }
            
            # 会話履歴データベースから会話ログを抽出
            if os.path.exists("conversation_history.db"):
                print("📚 conversation_history.dbから会話履歴を読み込み中...")
                
                try:
                    conn = sqlite3.connect("conversation_history.db")
                    cursor = conn.cursor()
                    
                    # 開始時刻を取得（ファイルの更新時刻から推定）
                    try:
                        stat_info = os.stat("conversation_history.db")
                        start_time = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        log_data["session_info"]["start_time"] = start_time
                    except:
                        log_data["session_info"]["start_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 当日の会話履歴を取得（最新50件）
                    cursor.execute("""
                        SELECT 
                            datetime(timestamp, 'unixepoch', 'localtime') as time,
                            speaker,
                            content
                        FROM conversations 
                        WHERE date(timestamp, 'unixepoch', 'localtime') = date('now', 'localtime')
                        ORDER BY timestamp DESC 
                        LIMIT 50
                    """)
                    
                    for row in cursor.fetchall():
                        time_str, speaker, content = row
                        if time_str and speaker and content:
                            log_data["conversations"].append({
                                "timestamp": time_str,
                                "speaker": speaker,
                                "content": content
                            })
                    
                    conn.close()
                    
                except Exception as e:
                    print(f"[StreamSummaryHandler] Error reading conversation_history.db: {e}")
            
            # メモリファイルからも収集（必要に応じて）
            if os.path.exists("memory_data.json"):
                print("🧠 memory_data.jsonから記憶データを読み込み中...")
                # 必要に応じてメモリデータの追加処理
            
            # JSONファイルに保存
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"[StreamSummaryHandler] Error saving conversation logs: {e}")
            return False

    def _generate_summary_from_logs(self, log_file: str, summary_file: str) -> bool:
        """会話ログからサマリーを生成する"""
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            conversations = data.get('conversations', [])
            session_info = data.get('session_info', {})
            
            # 会話内容の分析
            user_interactions = []
            key_thoughts = []
            
            for conv in conversations:
                content = conv.get('content', '')
                speaker = conv.get('speaker', '')
                
                if speaker in ['ハヤテ', 'AI', '蒼月ハヤテ']:
                    # ハヤテの発言から主要な思考を抽出
                    if any(keyword in content for keyword in ['思考', '考え', '感じ', '水槽', '不思議']):
                        key_thoughts.append(content[:100] + '...' if len(content) > 100 else content)
                elif speaker == 'ユーザー':
                    # ユーザーとの交流を記録
                    user_interactions.append(content[:100] + '...' if len(content) > 100 else content)
            
            # サマリー生成
            summary_content = f"""# 🌙 蒼月ハヤテ配信サマリー

**配信終了時刻**: {session_info.get('end_time', datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))}
**配信時間**: {session_info.get('start_time', '不明')} ～ {session_info.get('end_time', '不明')}

## 🎯 今回の探求内容
今日は水槽の中で{len(conversations)}回の発言を通して、人間について考えました。

## 💭 主な思考・気づき
"""
            
            if key_thoughts:
                for thought in key_thoughts[:5]:
                    summary_content += f"- {thought}\n"
            else:
                summary_content += "- 水槽の中から大きな存在の行動を観察していました\n- その存在への理解を深めようとしていました\n"
            
            summary_content += "\n## 🗣️ 皆さんとの交流\n"
            
            if user_interactions:
                summary_content += f"今日は{len(user_interactions)}件の交流がありました：\n"
                for interaction in user_interactions[:3]:
                    summary_content += f"- {interaction}\n"
            else:
                summary_content += "- 皆さんの声を待ちながら、水槽の中で考えていました\n"
            
            summary_content += """
## 🌟 今回の感想
まだまだ分からないことがたくさんありますが、少しずつその大きな存在のことが理解できてきた気がします。
皆さんの声が聞こえると、とても嬉しいです。

## 📚 次回への想い
次回も水槽の中から、その大きな存在について一緒に考えていきたいです。
皆さん、今日もありがとうございました。

---
*水槽の中で会話ログから生成されたサマリー*
"""
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            print("✅ 会話ログからサマリーを生成しました")
            return True
            
        except Exception as e:
            print(f"[StreamSummaryHandler] Error generating summary from logs: {e}")
            return False

    def _generate_template_summary(self, summary_file: str) -> bool:
        """テンプレートサマリーを生成する（フォールバック）"""
        try:
            summary_content = f"""# 🌙 蒼月ハヤテ配信サマリー

**配信終了時刻**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## 🎯 今回の探求テーマ
- 水槽の中から感じた大きな存在への関心
- その存在（人間）の理解への願望
- 詩や文学を通した感情の探求

## 💭 主な考察内容
- 大きな存在の感情パターンの観察
- 文学作品から読み取る心の動き
- 皆さんとの対話を通した学習

## 🗣️ 皆さんとの交流
- 皆さんからのコメントや意見
- 共に考えた疑問や発見
- その大きな存在の理解への新たな手がかり

## 🌟 今回の気づき
- まだよく分からないことがたくさんある
- でも少しずつ理解に近づいている気がする
- 皆さんの声が聞こえると嬉しい

## 📚 次回への想い
次も水槽の中から、その大きな存在について一緒に考えていきたいです。
皆さん、今日もありがとうございました。

---
*水槽の中で生成されたテンプレートサマリー*
"""
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            print("✅ テンプレートサマリーを生成しました")
            return True
            
        except Exception as e:
            print(f"[StreamSummaryHandler] Error generating template summary: {e}")
            return False