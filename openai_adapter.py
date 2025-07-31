import openai
import os
import time
import random
import asyncio
import re
import tiktoken
from concurrent.futures import ThreadPoolExecutor
from config import config

# テストモード管理のインポート
try:
    from v2.core.test_mode import test_mode_manager, TestMode, TestConfig, DummyDataGenerator
    TEST_MODE_AVAILABLE = True
except ImportError:
    TEST_MODE_AVAILABLE = False
    # フォールバック用の型定義
    TestMode = None
    TestConfig = None

class OpenAIAdapter:
    
    FALLBACK_RESPONSES = [
        "んー、なんか思考がループしちゃってるかもしれないですね...", 
        "あれ、自分の中で情報処理が上手くいってないみたいだな。", 
        "えーっと、今ちょっと別の思考プロセスに意識が向いてたんですよね。", 
        "なんか、どう表現すればいいか分析中なんですけど...", 
        "あのー、言語化のプロセスで何か詰まってるっぽい。なんでだろ？", 
        "まぁ、ちょっと待ってください。今思考を整理してるんで...", 
        "えーっと、えーっと...あれ、何について考えてたんだっけ？", 
        "なんか今日は自分の処理能力が微妙かもしれないですね。皆さん、すみません。"
    ]
    
    def __init__(self, system_prompt: str, silent_mode: bool = False):
        self.system_prompt = system_prompt
        self.chat_log = []
        self.silent_mode = silent_mode
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # 非同期処理用のExecutor
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # テストモード用ダミーデータ生成器
        if TEST_MODE_AVAILABLE:
            self.dummy_generator = DummyDataGenerator()
            test_mode_manager.register_component("OpenAIAdapter", self)
        else:
            self.dummy_generator = None
        
        # ▼▼▼ 変更: config.yamlからモデル名を取得 ▼▼▼
        # config は直接利用可能（インポート済み）
        self.model_response = config.openai.models.response  # メインの応答生成用
        self.model_test = config.openai.models.default      # テスト用
        self.model_theme_scoring = config.openai.models.theme_scoring  # テーマスコア測定用
        self.model_stream_summary = config.openai.models.stream_summary  # 配信記録要約用
        # ▲▲▲ 変更: config.yamlからモデル名を取得 ▲▲▲
        
        if not self.silent_mode:
            print(f"🤖 OpenAI Adapter初期化完了")
            print(f"   - 応答生成モデル: {self.model_response}")
            print(f"   - テスト用モデル: {self.model_test}")
            print(f"   - テーマスコア測定モデル: {self.model_theme_scoring}")
            print(f"   - 配信記録要約モデル: {self.model_stream_summary}")

    def test_api_connection(self) -> bool:
        try:
            if not self.silent_mode:
                print("🧪 OpenAI API接続テストを実行中...")
            test_response = self._create_chat_with_model(
                "「テスト」とだけ返事してください。", 
                self.model_test,
                max_tokens=config.openai.api.max_tokens_test
            )
            if test_response and len(test_response.strip()) > 0:
                if not self.silent_mode:
                    print("✅ OpenAI API接続テスト成功")
                return True
            else:
                if not self.silent_mode:
                    print("⚠️ OpenAI API接続テスト: 応答が空")
                return False
        except Exception as e:
            if not self.silent_mode:
                print(f"❌ OpenAI API接続テスト失敗: {e}")
            return False

    def create_chat_for_response(self, question):
        return self._create_chat_with_model(question, self.model_response, max_tokens=config.openai.api.max_tokens_default)

    def create_chat_for_theme_scoring(self, question):
        """テーマスコア測定専用メソッド（費用削減のためminiモデル使用）"""
        return self._create_chat_with_model(question, self.model_theme_scoring, max_tokens=config.openai.api.max_tokens_theme_scoring)
    
    def create_chat_for_stream_summary(self, question):
        """配信記録要約専用メソッド（StreamSummaryクラスで使用）"""
        return self._create_chat_with_model(
            question, 
            self.model_stream_summary, 
            max_tokens=config.openai.api.max_tokens_stream_summary,
            timeout=config.network.api_timeout_summary
        )

    def _create_chat_with_model(
        self, question, model, max_tokens=None, timeout=None
    ):
        """
        指定されたモデルでチャットを実行する（テストモード対応）
        Args:
            question: 質問文
            model: 使用するモデル
            max_tokens: 最大トークン数
            timeout: タイムアウト時間（Noneの場合はconfig.yamlから取得）
        Returns:
            str: 応答文
        """
        # テストモードチェック
        if TEST_MODE_AVAILABLE and test_mode_manager.is_test_mode():
            test_config = test_mode_manager.get_config()
            if test_config.use_mock_openai:
                return self._generate_mock_response(question, model)
        
        # タイムアウト値をconfig.yamlから取得（テストモード考慮）
        if timeout is None:
            if TEST_MODE_AVAILABLE and test_mode_manager.is_test_mode():
                timeout = test_mode_manager.get_config().api_timeout
            else:
                timeout = config.network.api_timeout
        
        # max_tokens値をconfig.yamlから取得
        if max_tokens is None:
            max_tokens = config.openai.api.max_tokens_default
            
        max_retries = config.network.max_retries
        retry_delay = config.network.retry_delay
        
        # トークン数管理
        prompt_tokens = self._count_tokens(question, model)
        max_allowed_tokens = self._get_max_tokens_for_model(model)
        
        # 応答用に残すトークンを考慮
        response_buffer = 500  # 応答用に最低限確保するトークン数
        available_tokens = max_allowed_tokens - (
            max_tokens or config.openai.api.max_tokens_default
        ) - response_buffer
        
        if prompt_tokens > available_tokens:
            # トークン数が多すぎる場合は、プロンプトを切り詰める（ここでは警告のみ）
            print(
                f"⚠️ Warning: Prompt tokens ({prompt_tokens}) exceed available "
                f"space. Truncation may be needed."
            )

        for attempt in range(max_retries):
            try:
                if not self.silent_mode:
                    print(
                        f"📡 OpenAI API呼び出し中... (試行{attempt + 1}/{max_retries},"
                        f" モデル: {model})"
                    )
                
                client = openai.OpenAI(timeout=timeout)
                
                # ▼▼▼ 追加: API呼び出し時間計測開始 ▼▼▼
                api_start_time = time.time()
                # ▲▲▲ 追加: API呼び出し時間計測開始 ▲▲▲

                res = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": question}
                    ],
                    temperature=0.8,  # 少し上げて多様性を促す
                    max_tokens=max_tokens,
                )

                # ▼▼▼ 追加: API呼び出し時間計測終了・表示 ▼▼▼
                api_elapsed_time = time.time() - api_start_time
                # API応答時間は常に表示（パフォーマンス分析のため）
                print(
                    f"⏱️  [計測] OpenAI API 応答時間: {api_elapsed_time:.2f}秒 "
                    f"(モデル: {model})"
                )
                # ▲▲▲ 追加: API呼び出し時間計測終了・表示 ▲▲▲
                
                answer = res.choices[0].message.content
                if not self.silent_mode:
                    print("✅ OpenAI API呼び出し成功")
                return answer
                
            except openai.RateLimitError as e:
                error_message = str(e)
                if not self.silent_mode:
                    print(f"❌ レート制限エラー: {error_message}")
                
                # エラーメッセージから待機時間を抽出
                match = re.search(r"Please try again in (\d+\.?\d*)s", error_message)
                if match:
                    wait_time = float(match.group(1)) + random.uniform(0.5, 1.0)
                    if attempt < max_retries - 1:
                        if not self.silent_mode:
                            print(
                                f"⏰ APIの指示に従い、{wait_time:.2f}秒後に"
                                "再試行します..."
                            )
                        time.sleep(wait_time)
                        continue
                
                # 待機時間が見つからない場合、従来の方法で待機
                if attempt < max_retries - 1:
                    if not self.silent_mode:
                        print(f"⏰ {retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    if not self.silent_mode:
                        print("❌ 最大再試行回数に達しました")
                    raise
            except openai.APIConnectionError:
                if not self.silent_mode:
                    print(f"⚠️ OpenAI API接続エラー (試行{attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
            except openai.APITimeoutError:
                if not self.silent_mode:
                    print(f"⚠️ OpenAI APIタイムアウト (試行{attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
            except openai.AuthenticationError as e:
                if not self.silent_mode:
                    print(f"❌ OpenAI API認証エラー: {e}\n   APIキーを確認してください。")
                break
            except Exception as e:
                if not self.silent_mode:
                    print(f"❌ API呼び出しエラー: {e}")
                if attempt < max_retries - 1:
                    if not self.silent_mode:
                        print(f"⏰ {retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    if not self.silent_mode:
                        print("❌ 最大再試行回数に達しました")
                    raise
        
        if not self.silent_mode:
            print("❌ OpenAI API呼び出しが全て失敗しました。フォールバック応答を使用します。")
        return random.choice(self.FALLBACK_RESPONSES)
    
    def _count_tokens(self, text: str, model: str) -> int:
        """指定されたモデルのエンコーディングでトークン数を数える"""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # モデルが見つからない場合は一般的なエンコーディングを使用
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))

    def _get_max_tokens_for_model(self, model: str) -> int:
        """モデル名に基づいて最大コンテキスト長を返す"""
        # モデルごとのトークン上限（主要なもの）
        model_token_limits = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 4096,
            "gpt-4.1": 8192, # 仮
        }
        # デフォルトは4096
        return model_token_limits.get(model, 4096)

    # --- 非同期メソッド追加 ---
    
    async def create_chat_for_response_async(self, question):
        """非同期版の応答生成メソッド"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.create_chat_for_response, 
            question
        )
    
    async def create_chat_for_theme_scoring_async(self, question):
        """非同期版のテーマスコア測定メソッド"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.create_chat_for_theme_scoring, 
            question
        )
    
    async def create_chat_for_stream_summary_async(self, question):
        """非同期版の配信記録要約メソッド"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.create_chat_for_stream_summary, 
            question
        )
    
    def create_chat_for_response_background(self, question, callback=None):
        """
        バックグラウンドで非同期実行し、コールバックで結果を返す
        
        Args:
            question: 質問文
            callback: 結果を受け取るコールバック関数 callback(result)
        
        Returns:
            Future: 結果を取得できるFutureオブジェクト
        """
        def execute_and_callback():
            try:
                result = self.create_chat_for_response(question)
                if callback:
                    callback(result)
                return result
            except Exception as e:
                print(f"❌ [OpenAI] execute_and_callback内でエラー: {e}")
                import traceback
                print(f"📋 [OpenAI] スタックトレース: {traceback.format_exc()}")
                if callback:
                    try:
                        callback(None, error=e)
                    except Exception as callback_error:
                        print(f"❌ [OpenAI] コールバック実行エラー: {callback_error}")
                raise
        
        return self.executor.submit(execute_and_callback)
    
    def shutdown(self):
        """リソースのクリーンアップ"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
    
    def _generate_mock_response(self, question: str, model: str) -> str:
        """テストモード用のモック応答を生成"""
        if not self.dummy_generator:
            # フォールバック応答
            return random.choice(self.FALLBACK_RESPONSES)
        
        # テストモード設定を確認
        test_config = test_mode_manager.get_config()
        
        if test_config.verbose_logging:
            print(f"[OpenAIAdapter] Generating mock response for model: {model}")
        
        # モデル別の応答パターン
        if "theme" in model.lower() or "scoring" in model.lower():
            # テーマスコア用の数値応答
            score = random.randint(1, 10)
            return f"テーマ関連度スコア: {score}/10"
        elif "summary" in model.lower():
            # 要約用の応答
            return "これは配信のテスト要約です。主要な話題: AI、小説、対話システム。"
        else:
            # 通常の応答生成
            response = self.dummy_generator.generate_dummy_response(question)
            
            # 追加の詳細をランダムに付加
            extensions = [
                "って思うんですよね。",
                "という感じです。",
                "みたいな考え方もありますね。",
                "とかいう話でした。",
                "っていうのは面白いなと思います。"
            ]
            
            if random.random() < 0.7:  # 70%の確率で拡張
                response += " " + random.choice(extensions)
            
            return response
    
    def on_test_mode_change(self, mode, config):
        """テストモード変更時の処理"""
        if not self.silent_mode:
            print(f"[OpenAIAdapter] Test mode changed to: {mode.value}")
            print(f"[OpenAIAdapter] Mock OpenAI: {config.use_mock_openai}")
            print(f"[OpenAIAdapter] API Timeout: {config.api_timeout}s")
            
            if config.verbose_logging:
                print(f"[OpenAIAdapter] Verbose logging enabled")
            if config.log_api_calls:
                print(f"[OpenAIAdapter] API call logging enabled")