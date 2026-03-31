import obsws_python as obs
import os
import time
import threading
from dotenv import load_dotenv
from typing import Optional
from config import config

class OBSAdapter:
    def __init__(self) -> None:
        load_dotenv()
        # 設定ファイルからOBS接続情報を取得
        password = config.api_keys.obs_ws_password
        host = config.api_keys.obs_ws_host
        port = config.api_keys.obs_ws_port
        
        if password is None or host is None or port is None:
            raise Exception("⚠️ OBSの設定がされていません。環境変数を確認してください。")
        
        self.host = host
        self.port = int(port)
        self.password = password
        self.ws = None
        self.is_connected = False
        self.connection_lock = threading.Lock()
        
        # 自動再接続設定
        self.max_retries = config.network.max_retries
        self.retry_delay = config.network.retry_delay
        self.connection_timeout = config.network.connection_timeout
        
        # 初期接続を試行
        self._connect()

    def _connect(self) -> bool:
        """OBSに接続する内部メソッド"""
        with self.connection_lock:
            try:
                print("🔗 OBS WebSocketに接続中...")
                self.ws = obs.ReqClient(
                    host=self.host, 
                    port=self.port, 
                    password=self.password,
                    timeout=self.connection_timeout
                )
                
                # 接続テスト
                version_info = self.ws.get_version()
                if version_info:
                    self.is_connected = True
                    print(f"✅ OBS接続成功 (OBS Studio v{version_info.obs_version})")
                    return True
                else:
                    self.is_connected = False
                    print("❌ OBS接続失敗: バージョン情報取得不可")
                    return False
                    
            except Exception as e:
                self.is_connected = False
                print(f"❌ OBS接続失敗: {e}")
                if self.ws:
                    try:
                        # ReqClientには disconnect メソッドがないため、close() またはデストラクタに任せる
                        self.ws = None
                    except:
                        pass
                return False

    def _ensure_connection(self) -> bool:
        """接続を確保する（必要に応じて再接続）"""
        if self.is_connected and self.ws:
            # 接続テスト
            try:
                self.ws.get_version()
                return True
            except:
                print("⚠️ OBS接続が切断されました")
                self.is_connected = False
        
        # 再接続を試行
        print("🔄 OBS再接続を試行中...")
        for attempt in range(self.max_retries):
            print(f"   再接続試行 {attempt + 1}/{self.max_retries}")
            if self._connect():
                return True
            if attempt < self.max_retries - 1:
                print(f"   {self.retry_delay:.1f}秒待機...")
                time.sleep(self.retry_delay)
        
        print("❌ OBS再接続に失敗しました")
        return False

    def _safe_obs_call(self, operation_name: str, operation_func, *args, **kwargs):
        """OBS操作を安全に実行する内部メソッド"""
        if not self._ensure_connection():
            print(f"⚠️ OBS操作スキップ ({operation_name}): 接続不可")
            return False
        
        try:
            result = operation_func(*args, **kwargs)
            print(f"✅ OBS操作成功: {operation_name}")
            return result
        except obs.error.OBSSDKTimeoutError as e:
            print(f"⚠️ OBS操作タイムアウト ({operation_name}): {e}")
            return False
        except obs.error.OBSSDKRequestError as e:
            print(f"⚠️ OBS操作リクエストエラー ({operation_name}): {e}")
            return False
        except Exception as e:
            print(f"⚠️ OBS操作失敗 ({operation_name}): {e}")
            # 接続エラーの可能性があるため接続状態をリセット
            self.is_connected = False
            return False

    def set_question(self, text: str):
        """質問テキストをOBSに設定"""
        if not text:
            text = ""
        return self._safe_obs_call(
            "Question設定",
            lambda: self.ws.set_input_settings(name="Question", settings={"text": text}, overlay=True)
        )

    def set_answer(self, text: str):
        """回答テキストをOBSに設定"""
        if not text:
            text = ""
        return self._safe_obs_call(
            "Answer設定",
            lambda: self.ws.set_input_settings(name="Answer", settings={"text": text}, overlay=True)
        )

    def set_image_source(self, image_path: str, source_name: str = "ImageSource"):
        """画像ソースをOBSに設定"""
        if not os.path.exists(image_path):
            print(f"⚠️ 画像ファイルが見つかりません: {image_path}")
            return False
        
        settings = {"file": image_path}
        return self._safe_obs_call(
            f"画像ソース設定 ({source_name})",
            lambda: self.ws.set_source_settings(source_name=source_name, settings=settings)
        )

    def set_current_scene(self, scene_name: str):
        """現在のシーンを切り替え"""
        return self._safe_obs_call(
            f"シーン切り替え ({scene_name})",
            lambda: self.ws.set_current_program_scene(scene_name)
        )

    def set_current_transition(self, transition_name: str):
        """トランジションを設定"""
        return self._safe_obs_call(
            f"トランジション設定 ({transition_name})",
            lambda: self.ws.set_current_scene_transition(transition_name)
        )

    def set_transition_duration(self, duration_ms: int):
        """トランジション持続時間を設定"""
        return self._safe_obs_call(
            f"トランジション持続時間設定 ({duration_ms}ms)",
            lambda: self.ws.set_current_scene_transition_duration(duration_ms)
        )

    def set_selected_comment(self, message: str):
        """コメント本文のみをOBSに表示するメソッド"""
        if not message:
            message = ""
        return self._safe_obs_call(
            "選択コメント設定",
            lambda: self.ws.set_input_settings(name="SelectedComment", settings={"text": message}, overlay=True)
        )

    def clear_selected_comment(self):
        """コメント表示をクリアするメソッド"""
        return self.set_selected_comment("")
    
    def set_summary(self, summary: str):
        """要約テキストをOBSに設定するメソッド"""
        if not summary:
            summary = ""
        return self._safe_obs_call(
            "要約設定",
            lambda: self.ws.set_input_settings(name="Summary", settings={"text": summary}, overlay=True)
        )

    def clear_summary(self):
        """要約表示をクリアするメソッド"""
        return self.set_summary("")
    
    def get_connection_status(self) -> dict:
        """接続状態を取得"""
        return {
            "is_connected": self.is_connected,
            "host": self.host,
            "port": self.port
        }
    
    def test_connection(self) -> bool:
        """接続テストを実行"""
        print("🧪 OBS接続テストを実行中...")
        return self._ensure_connection()
    
    def disconnect(self):
        """OBSから切断"""
        with self.connection_lock:
            if self.ws:
                try:
                    # ReqClientには disconnect メソッドがないため、close() またはデストラクタに任せる
                    self.ws = None
                    self.is_connected = False
                    print("✅ OBSから切断しました")
                except Exception as e:
                    print(f"⚠️ OBS切断中にエラー: {e}")
                finally:
                    self.ws = None
                    self.is_connected = False

if __name__ == '__main__':
    try:
        obsAdapter = OBSAdapter()
        
        # 接続テスト
        if obsAdapter.test_connection():
            print("✅ OBS接続テスト成功")
            
            # トランジションを「フェード」に設定し、持続期間を「1000ms」に設定
            obsAdapter.set_current_transition("フェード")
            obsAdapter.set_transition_duration(1000)
            
            import random
            question_text = "Questionの番号は" + str(random.randint(0,100)) + "になりました"
            obsAdapter.set_question(question_text)
            answer_text = "Answerの番号は" + str(random.randint(0,100)) + "になりました"
            obsAdapter.set_answer(answer_text)
            
            # 例としてシーンを切り替える
            obsAdapter.set_current_scene("待機画面")
        else:
            print("❌ OBS接続テスト失敗")
            
    except Exception as e:
        print(f"❌ OBSAdapterテスト中にエラー: {e}")
    finally:
        try:
            if obsAdapter:
                obsAdapter.disconnect()
        except Exception as e:
            print(f"⚠️ 終了処理中にエラー: {e}")