import time
import queue
import threading
from collections import deque
from typing import Optional
import re
import os
from app.openai_adapter import OpenAIAdapter
from config import config


class MemoryManager:
    """
    配信での出来事を記憶し、長期記憶として活用するクラス。
    要約と圧縮処理をバックグラウンドで非同期に実行する。
    """

    def __init__(
            self,
            llm_adapter: OpenAIAdapter,
            max_utterances=None,
            summary_interval=None,
            event_queue=None  # ★ 追加
    ):
        """
        MemoryManagerを初期化

        Args:
            llm_adapter: OpenAIアダプター
            max_utterances: 短期記憶の最大保持数（Noneの場合はconfig.yamlから取得）
            summary_interval: 要約生成間隔（秒）（Noneの場合はconfig.yamlから取得）
            event_queue: イベントキュー（v2アーキテクチャ用）
        """
        self.llm_adapter = llm_adapter
        self.event_queue = event_queue  # ★ 追加

        # --- 設定値の読み込み ---
        self.max_utterances = (
            max_utterances
            if max_utterances is not None
            else config.memory.max_utterances
        )
        self.summary_interval = (
            summary_interval
            if summary_interval is not None
            else config.memory.summary_interval
        )
        self.compression_threshold = config.memory.long_term_compression_threshold

        # --- 記憶領域 ---
        self.utterances = deque(maxlen=self.max_utterances)  # 短期記憶
        self.long_term_summary = ""                         # 長期記憶（文字列形式）
        self.total_utterances = 0
        self.last_summary_time = time.time()
        self.auto_save_path = None

        # --- 非同期処理用の設定 ---
        self.summary_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()  # 長期記憶へのアクセスを保護するロック

        # --- タスク種別の定数 ---
        self.TASK_TYPE_SUMMARY = "summary"
        self.TASK_TYPE_DAILY_SUMMARY = "daily_summary"

        # --- バックグラウンドワーカースレッドを開始 ---
        self.worker_thread = threading.Thread(
            target=self._summary_worker, daemon=True
        )
        self.worker_thread.start()

    def add_utterance(self, text: str, speaker: str = "蒼月ハヤテ"):
        """
        発言を短期記憶に追加する。
        このメソッドは即座に完了し、重い処理はバックグラウンドで行われる。

        Args:
            text: 発言内容
            speaker: 発言者名
        """
        self.utterances.append(f"{speaker}: {text}")
        self.total_utterances += 1
        self._check_and_schedule_summary()

    def _check_and_schedule_summary(self):
        """
        要約のタイミングをチェックし、条件を満たしていればタスクをキューに入れる。
        """
        current_time = time.time()

        if (current_time - self.last_summary_time > self.summary_interval and
            len(self.utterances) >= 5):

            print("🧠 長期記憶の更新をスケジュールしました。")

            # 短期記憶の内容をキューに投入
            short_term_memory_text = "\n".join(self.utterances)
            self.summary_queue.put((self.TASK_TYPE_SUMMARY, short_term_memory_text))

            # 短期記憶をクリアし、時間を更新
            self.utterances.clear()
            self.last_summary_time = current_time

    # === ▼▼▼ 最重要修正箇所 ▼▼▼ ===
    def _summary_worker(self):
        """
        バックグラウンドで要約と圧縮を実行するワーカースレッド。
        デッドロックを回避するためにロジックを再構築。
        """
        while not self.stop_event.is_set():
            try:
                task_type, data = self.summary_queue.get(timeout=1.0)
                if task_type is None: # 停止シグナル
                    break

                if task_type == self.TASK_TYPE_SUMMARY:
                    self._process_summary_task(data)
                elif task_type == self.TASK_TYPE_DAILY_SUMMARY:
                    self._process_daily_summary_task(data)

                self.summary_queue.task_done()

            except queue.Empty:
                # タイムアウトは正常。ループを継続。
                continue
            except Exception as e:
                print(f"❌ 記憶要約ワーカーでエラーが発生しました: {e}")

    def _process_summary_task(self, short_term_memory_text: str):
        """通常の要約生成タスクを処理する"""
        # --- ステップ1: 要約の生成（ロックの外） ---
        new_summary_block = self._create_summary_from_text(
            short_term_memory_text
        )
        if not new_summary_block:
            return

        text_to_compress = None

        # --- ステップ2: メモリの更新と圧縮判定（ロックの内側） ---
        with self.lock:
            time_stamp = time.strftime('%Y-%m-%d %H:%M', time.localtime())
            self.long_term_summary += (
                f"\n\n[{time_stamp}]\n{new_summary_block}"
            )

            summary_blocks = [
                s.strip() for s in self.long_term_summary.strip().split('\n\n')
                if s.strip()
            ]
            if len(summary_blocks) >= self.compression_threshold:
                text_to_compress = self.long_term_summary

            if self.auto_save_path:
                self.save_summary_to_file(self.auto_save_path, locked=True)

        # --- ステップ3: 圧縮処理の実行（ロックの外） ---
        if text_to_compress:
            self._compress_long_term_memory(text_to_compress)

    def _process_daily_summary_task(self, data: dict):
        """日次要約タスクを処理し、イベントを発行する"""
        base_dir = data["base_dir"]
        task_id = data["task_id"]

        print(f"Began processing daily summary task: {task_id}")

        summary_file_path = None
        summary_text = ""
        success = False

        try:
            with self.lock:
                if not self.long_term_summary:
                    print("💭 保存する長期記憶がありません。")
                    summary_text = "保存対象の長期記憶データがありませんでした。"
                else:
                    today = time.strftime('%Y%m%d')
                    file_name = f"summary_{today}.txt"
                    summary_file_path = os.path.join(base_dir, file_name)
                    # ファイル保存処理
                    self.save_summary_to_file(summary_file_path, locked=True)

                    # ファイルが正常に保存されたか確認
                    if os.path.exists(summary_file_path):
                        with open(
                            summary_file_path, 'r', encoding='utf-8'
                        ) as f:
                            summary_text = f.read()
                        success = True
                    else:
                        summary_text = "日次要約ファイルの保存に失敗しました。"
                        print(f"⚠️ ファイルが見つかりません: {summary_file_path}")

            if success:
                print(f"✅ 日次要約タスク完了: {summary_file_path}")
            else:
                print(f"⚠️ 日次要約タスク完了（データなしまたは保存失敗）: {task_id}")

        except Exception as e:
            summary_text = f"日次要約の保存中にエラーが発生しました: {e}"
            success = False
            print(f"❌ 日次要約タスクでエラー: {e}")

        # 完了イベントを発行
        if self.event_queue:
            from murmur.core.events import DailySummaryReady
            event = DailySummaryReady(
                task_id=task_id,
                summary_text=summary_text,
                success=success,
                file_path=summary_file_path
            )
            self.event_queue.put(event)
            print(f"📨 イベントを送信しました: {type(event).__name__}")
        else:
            print(
                "⚠️ イベントキューが設定されていないため、"
                "完了イベントは送信されません。"
            )

    def _create_summary_from_text(self, text: str) -> Optional[str]:
        """テキストから箇条書きの要約を生成する。"""
        prompt = f"""以下の配信での会話履歴を、三人称視点で3つ程度の箇条書きで簡潔に要約してください。
特に、面白い話題、視聴者との印象的なやり取りがあれば含めてください。
---
{text}
---
要約（3つ程度の箇条書き）:"""
        try:
            summary = self.llm_adapter.create_chat_for_stream_summary(prompt)
            print(f"✅ 新しい長期記憶が生成されました:\n{summary}")
            return summary
        except Exception as e:
            print(f"❌ 長期記憶の生成中にエラー: {e}")
            return None

    # === ▼▼▼ 最重要修正箇所 ▼▼▼ ===
    def _compress_long_term_memory(self, text_to_compress: str):
        """
        長期記憶をさらに要約（圧縮）し、安全に更新する。
        このメソッドはロックの外から呼び出される。
        """
        print(
            f"📚 長期記憶が{len(text_to_compress.splitlines())}行に達したため、"
            "圧縮を開始します。"
        )

        prompt = f"""以下の情報は、これまでの配信の出来事を時系列で要約したものです。
この内容全体を、さらに抽象度の高い1つの「章」のような形で要約し直してください。
個別のエピソードよりも、配信全体の大きな流れや、キャラクターの感情の変化、主要なテーマの変遷がわかるようにまとめてください。
---
{text_to_compress}
---
この配信の章の要約:"""

        try:
            # 圧縮された要約を生成 (API呼び出しはロックの外)
            compressed_summary = self.llm_adapter.create_chat_for_stream_summary(
                prompt
            )

            if compressed_summary:
                # 更新のために再度ロックを取得
                with self.lock:
                    # タイムスタンプを付けて、長期記憶を上書き
                    time_stamp = time.strftime('%Y-%m-%d', time.localtime())
                    self.long_term_summary = (
                        f"[{time_stamp}の配信概要]\n{compressed_summary}"
                    )
                    print("✅ 長期記憶の圧縮が完了しました。")

                    # 圧縮後の内容をファイルに保存
                    if self.auto_save_path:
                        self.save_summary_to_file(
                            self.auto_save_path, locked=True
                        )

        except Exception as e:
            print(f"❌ 長期記憶の圧縮中にエラー: {e}")

    def get_context_summary(self) -> str:
        """
        プロンプトに含めるための文脈サマリーを返す（スレッドセーフ）。
        """
        with self.lock:
            if not self.long_term_summary:
                return "まだ特筆すべき出来事はありません。"

            summary_parts = [s.strip() for s in self.long_term_summary.strip().split('\n\n') if s.strip()]

            # 【2026-06-24 プロンプト肥大対策（暫定）】以前は直近5セクションを丸ごと注入していたが、
            # 1セクションが巨大化（要約が圧縮されず蓄積。kioku_hayate.txtは約180KB）すると、
            # 最終プロンプトが7万トークン超になり Ollama の context窓を溢れて空応答→フィラー化していた。
            # ここでは直近3セクション＋総量を約2000字に制限して注入量を抑える。
            # ※恒久対応はベクトルDB(ruri等)で「現在の文脈に関連する記憶だけ」を top-k 検索して注入する方式へ。
            recent_summary_parts = summary_parts[-3:]
            recent_summary = "\n\n".join(recent_summary_parts)
            _MAX_SUMMARY_CHARS = 2000
            if len(recent_summary) > _MAX_SUMMARY_CHARS:
                recent_summary = "…(古い要約は省略)…\n" + recent_summary[-_MAX_SUMMARY_CHARS:]

        return f"これまでの配信での出来事の要約:\n{recent_summary}"

    def save_summary_to_file(self, file_path: str, locked: bool = False):
        """
        現在の長期記憶の要約をテキストファイルに保存する（スレッドセーフ）。

        Args:
            file_path (str): 保存先のファイルパス
            locked (bool): 既にロックを取得しているかどうかのフラグ
        """
        def _save():
            # この関数はロックの内側で実行されることを前提とします
            if not self.long_term_summary:
                return
            current_summary_content = self.long_term_summary

            try:
                dir_name = os.path.dirname(file_path)
                if dir_name and not os.path.exists(dir_name):
                    os.makedirs(dir_name)

                # get_statisticsもロックが必要なため、lockedフラグを渡します
                stats = self.get_statistics(locked=True)
                header = f"""# 長期記憶要約
# 生成日時: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}
# 総発言数: {stats['total_utterances']}
# 要約セクション数: {stats['summary_sections']}
# 最終要約時刻: {time.strftime(
    '%Y-%m-%d %H:%M:%S',
    time.localtime(stats['last_summary_time'])
)}
"""
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(header)
                    f.write("\n" + current_summary_content)

                print(f"💾 長期記憶をファイルに保存しました: {file_path}")

            except Exception as e:
                print(f"❌ 要約のファイル保存中にエラーが発生しました: {e}")

        if locked:
            _save()
        else:
            with self.lock:
                _save()

    def get_statistics(self, locked: bool = False) -> dict:
        """記憶システムの統計情報を返す"""
        def _get_stats_unsafe():
            summary_sections = len([s for s in self.long_term_summary.strip().split('\n\n') if s])
            return {
                "total_utterances": self.total_utterances,
                "current_short_term_count": len(self.utterances),
                "summary_sections": summary_sections,
                "last_summary_time": self.last_summary_time
            }

        if locked:
            return _get_stats_unsafe()
        else:
            with self.lock:
                return _get_stats_unsafe()

    def stop(self):
        """
        ワーカースレッドを安全に停止させる。アプリケーション終了時に呼び出す。
        """
        print("🔄 MemoryManagerの停止処理を開始します...")
        self.stop_event.set()
        try:
            self.summary_queue.put((None, None), timeout=1.0)  # 停止シグナル
        except queue.Full:
            pass
        self.worker_thread.join(timeout=5.0)
        print("✅ MemoryManagerが正常に停止しました。")

    def force_summarize(self):
        """手動で要約を生成する"""
        if len(self.utterances) > 0:
            print("🧠 手動要約をスケジュールします...")
            short_term_memory_text = "\n".join(self.utterances)
            self.summary_queue.put((self.TASK_TYPE_SUMMARY, short_term_memory_text))
            self.utterances.clear()
        else:
            print("💭 要約対象となる短期記憶がありません")

    def set_auto_save_path(self, file_path: str):
        """
        自動保存のパスを設定する
        """
        self.auto_save_path = file_path
        print(f"💾 自動保存パスを設定しました: {file_path}")

    def clear_memory(self):
        """記憶をクリアする（デバッグ用）"""
        with self.lock:
            self.utterances.clear()
            self.long_term_summary = ""
            self.total_utterances = 0
            self.last_summary_time = time.time()
        print("🗑️ 記憶システムをクリアしました")

    def load_summary_from_file(self, file_path: str):
        """
        保存されたファイルから長期記憶の要約を読み込む
        """
        try:
            import os
            if not os.path.exists(file_path):
                print(f"💭 保存されたファイルが見つかりません: {file_path}")
                return

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # ヘッダー部分を除外して純粋な要約データのみを読み込む
            summary_content = re.search(r'#.*\n\n(.*)', content, re.DOTALL)

            with self.lock:
                if summary_content:
                    self.long_term_summary = summary_content.group(1).strip()
                else:
                    # ヘッダーがない古い形式のファイルも考慮
                    self.long_term_summary = content.strip()

            if self.long_term_summary:
                print(f"✅ 長期記憶を {file_path} から読み込みました。")
            else:
                print(f"💭 {file_path} には有効な要約データがありませんでした。")

        except Exception as e:
            print(f"❌ 要約のファイル読み込み中にエラーが発生しました: {e}")

    def save_daily_summary(self, base_dir: str, task_id: str):
        """
        日次要約の保存タスクをワーカースレッドに依頼する。
        このメソッドは即座にリターンする。
        """
        print(f"🗓️  日次要約タスクをキューに追加しました: {task_id}")
        task_data = {"base_dir": base_dir, "task_id": task_id}
        self.summary_queue.put((self.TASK_TYPE_DAILY_SUMMARY, task_data))
