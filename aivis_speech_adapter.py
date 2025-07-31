import json
import requests
import io
import soundfile
import numpy as np
from typing import Tuple, Optional
import time
from requests.exceptions import RequestException, ConnectionError, Timeout
from config import config

class AivisSpeechAdapter:
    """
    AivisSpeechエンジンを使用した音声合成アダプター
    VOICEVOX APIに準拠した実装
    """
    
    # API リクエストの設定（config.yamlから取得）

    def __init__(self):
        """
        キャラクター設定の初期化
        AivisSpeechエンジン用の設定に更新
        """
        self.character_configs = self._initialize_character_configs()
        self._test_connection()
        self._validate_speaker_config()

    def _initialize_character_configs(self) -> dict:
        """
        キャラクター設定の初期化
        
        Returns:
            dict: キャラクター設定辞書
        """
        return {
            'hayate': {
                'speaker_id': 1,  # 蒼月ハヤテを話者1として設定
                'speaker_uuid': 'a82fc628-f166-427f-b568-4c4f94921629',
                'speaker_name': '蒼月ハヤテ',
                'style_id': 593129376,  # ハヤテのスタイルID（ノーマル）
                'style_name': 'ノーマル',
                'style_type': 'talk',
                'speed_scale': 0.96,  # 標準速度
                'pitch_scale': 0.0,  # 標準ピッチ
                'intonation_scale': 1.0,  # 標準抑揚
                'volume_scale': 1.0,  # 標準音量
                'pre_phoneme_length': 0.1,  # 前音素長
                'post_phoneme_length': 0.1,  # 後音素長
                'output_sampling_rate': config.audio.synthesis.output_sampling_rate,
                'output_stereo': config.audio.synthesis.output_stereo,
                'tempo_dynamics_scale': 1.8  # テンポの緩急を制御するパラメーター（デフォルト: 1.0）
            }
        }

    def _test_connection(self):
        """
        AivisSpeechエンジンへの接続テスト
        """
        try:
            response = requests.get(f"{config.audio.synthesis.aivis_url}/version")
            response.raise_for_status()
            print("AivisSpeechエンジンに接続できました")
        except Exception as e:
            print(f"警告: AivisSpeechエンジンへの接続に失敗しました: {str(e)}")
            print("音声合成が正常に動作しない可能性があります")

    def _validate_speaker_config(self):
        """
        話者設定の検証
        """
        try:
            response = requests.get(f"{config.audio.synthesis.aivis_url}/speakers")
            response.raise_for_status()
            speakers = response.json()
            
            # 話者の存在確認
            hayate_config = self.character_configs['hayate']
            self._verify_speaker_exists(speakers, hayate_config)
            
        except Exception as e:
            print(f"警告: 話者設定の検証に失敗しました: {str(e)}")

    def _verify_speaker_exists(self, speakers_list: list, character_config: dict):
        """
        指定された話者の存在確認
        
        Args:
            speakers_list (list): 利用可能な話者のリスト
            character_config (dict): 確認するキャラクター設定
        """
        speaker_found = False
        
        for speaker in speakers_list:
            if speaker['speaker_uuid'] == character_config['speaker_uuid']:
                speaker_found = True
                # スタイルの存在確認
                if not self._verify_style_exists(speaker['styles'], character_config['style_id']):
                    print(f"警告: スタイルID {character_config['style_id']} が見つかりません")
                break
        
        if not speaker_found:
            print(f"警告: 話者UUID {character_config['speaker_uuid']} が見つかりません")

    def _verify_style_exists(self, styles_list: list, target_style_id: int) -> bool:
        """
        指定されたスタイルの存在確認
        
        Args:
            styles_list (list): 利用可能なスタイルのリスト
            target_style_id (int): 確認するスタイルID
            
        Returns:
            bool: スタイルが存在する場合True
        """
        for style in styles_list:
            if style['id'] == target_style_id:
                return True
        return False

    def get_voice(self, text: str, speaker_id: int) -> Tuple[np.ndarray, int]:
        """
        テキストを音声に変換する
        
        Args:
            text (str): 変換するテキスト
            speaker_id (int): 話者ID（互換性のため維持）
            
        Returns:
            Tuple[np.ndarray, int]: 音声データとサンプルレート
            
        Raises:
            ValueError: 未知のspeaker_idが指定された場合
            RequestException: APIリクエストに失敗した場合
        """
        # 全体の処理時間計測開始
        total_start_time = time.time()
        
        # キャラクター設定の取得
        character_config = self._get_character_config(speaker_id)
        
        try:
            # 1. AudioQueryの取得
            audio_query = self._get_audio_query(text, character_config)
            
            # 2. 音声パラメータの設定
            configured_audio_query = self._configure_audio_parameters(audio_query, character_config)
            
            # 3. 音声合成の実行
            audio_data, sample_rate = self._synthesize_audio(configured_audio_query, character_config)
            
            # 全体の処理時間計測終了・結果表示
            total_elapsed_time = time.time() - total_start_time
            print(f"⏱️  [計測] AivisSpeech get_voice() 合計時間: {total_elapsed_time:.2f}秒")
            
            return audio_data, sample_rate

        except (ConnectionError, Timeout) as e:
            print(f"接続エラー: {str(e)}")
            raise
        except RequestException as e:
            print(f"AivisSpeech API request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error details: {e.response.text}")
            raise

    def _get_character_config(self, speaker_id: int) -> dict:
        """
        話者IDに対応するキャラクター設定を取得
        
        Args:
            speaker_id (int): 話者ID
            
        Returns:
            dict: キャラクター設定
            
        Raises:
            ValueError: 未知のspeaker_idが指定された場合
        """
        character_key = self.get_character_key(speaker_id)
        if character_key is None:
            raise ValueError(f"Unknown speaker_id: {speaker_id}")
        
        return self.character_configs[character_key]

    def _get_audio_query(self, text: str, character_config: dict) -> dict:
        """
        AudioQueryを取得
        
        Args:
            text (str): 変換するテキスト
            character_config (dict): キャラクター設定
            
        Returns:
            dict: AudioQueryレスポンス
        """
        query_params = {
            'text': text,
            'speaker': character_config['style_id']  # style_idを整数値として使用
        }
        
        # AudioQuery時間計測開始
        query_start_time = time.time()
        
        response = requests.post(
            f"{config.audio.synthesis.aivis_url}/audio_query",
            params=query_params,
            timeout=8  # 終了処理対応：音声合成に適切な時間を確保
        )
        response.raise_for_status()
        
        # AudioQuery時間計測終了・結果表示
        query_elapsed_time = time.time() - query_start_time
        print(f"   ⏱️  [計測] AivisSpeech AudioQuery 時間: {query_elapsed_time:.2f}秒")
        
        return response.json()

    def _configure_audio_parameters(self, audio_query: dict, character_config: dict) -> dict:
        """
        AudioQueryに音声パラメータを設定
        
        Args:
            audio_query (dict): 元のAudioQuery
            character_config (dict): キャラクター設定
            
        Returns:
            dict: パラメータ設定済みのAudioQuery
        """
        audio_query.update({
            'speedScale': character_config['speed_scale'],
            'pitchScale': character_config['pitch_scale'],
            'intonationScale': character_config['intonation_scale'],
            'volumeScale': character_config['volume_scale'],
            'prePhonemeLength': character_config['pre_phoneme_length'],
            'postPhonemeLength': character_config['post_phoneme_length'],
            'outputSamplingRate': character_config['output_sampling_rate'],
            'outputStereo': character_config['output_stereo'],
            'tempoDynamicsScale': character_config['tempo_dynamics_scale']  # テンポの緩急パラメーターを追加
        })
        
        return audio_query

    def _synthesize_audio(self, audio_query: dict, character_config: dict) -> Tuple[np.ndarray, int]:
        """
        音声合成を実行
        
        Args:
            audio_query (dict): 設定済みのAudioQuery
            character_config (dict): キャラクター設定
            
        Returns:
            Tuple[np.ndarray, int]: 音声データとサンプルレート
        """
        synthesis_params = {
            'speaker': character_config['style_id']  # style_idを整数値として使用
        }
        
        # Synthesis時間計測開始
        synth_start_time = time.time()
        
        response = requests.post(
            f"{config.audio.synthesis.aivis_url}/synthesis",
            params=synthesis_params,
            json=audio_query,
            headers={"accept": "audio/wav"},
            timeout=12  # 終了処理対応：音声合成に適切な時間を確保
        )
        response.raise_for_status()

        # Synthesis時間計測終了・結果表示
        synth_elapsed_time = time.time() - synth_start_time
        print(f"   ⏱️  [計測] AivisSpeech Synthesis 時間: {synth_elapsed_time:.2f}秒")

        # 音声データの変換と正規化
        return self._process_audio_data(response.content)

    def _process_audio_data(self, audio_content: bytes) -> Tuple[np.ndarray, int]:
        """
        音声データの処理と正規化
        
        Args:
            audio_content (bytes): 音声データ（WAV形式）
            
        Returns:
            Tuple[np.ndarray, int]: 処理済み音声データとサンプルレート
        """
        audio_stream = io.BytesIO(audio_content)
        data, sample_rate = soundfile.read(audio_stream)
        
        # 音声データの正規化
        if np.max(np.abs(data)) > 0:
            data = data / np.max(np.abs(data))
        
        return data, sample_rate

    def get_character_key(self, speaker_id: int) -> Optional[str]:
        """
        話者IDからキャラクターキーを取得する
        
        Args:
            speaker_id (int): 話者ID
            
        Returns:
            Optional[str]: キャラクターキー（見つからない場合はNone）
        """
        for character_key, character_config in self.character_configs.items():
            if character_config['speaker_id'] == speaker_id:
                return character_key
        return None

if __name__ == "__main__":
    # テスト用コード
    aivis = AivisSpeechAdapter()
    test_texts = [
        "おー。また名曲が生まれちゃったか。じっくり分析してみよう。",
        "こんにちは！今日も元気に配信していきましょう！",
        "えーっと、そうですね。その質問について考えてみましょう。"
    ]

    for speaker_id in [1]:  # 蒼月ハヤテ(ID:1)のテスト
        print(f"\nTesting speaker {speaker_id}:")
        character_key = aivis.get_character_key(speaker_id)
        if character_key:
            character_name = aivis.character_configs[character_key]['speaker_name']
            print(f"キャラクター名: {character_name}")
        
        for text in test_texts:
            try:
                print(f"Processing text: {text}")
                data, sample_rate = aivis.get_voice(text, speaker_id)
                print(f"Sample Rate: {sample_rate}")
                output_file = f'output_speaker_{speaker_id}_{hash(text)}.wav'
                soundfile.write(output_file, data, sample_rate)
                print(f"音声ファイルが '{output_file}' に保存されました。")
            except Exception as e:
                print(f"Error processing text for speaker {speaker_id}: {str(e)}") 