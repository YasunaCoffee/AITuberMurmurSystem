# -*- coding: utf-8 -*-
"""
アプリケーション全体の設定を管理するモジュール。

設定ファイル (config.yaml) と環境変数 (.env) から情報を読み込み、
シングルトンオブジェクト `config` を通じてどこからでも参照できるようにします。
"""
import os
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

# --- ヘルパークラスの定義 ---
class _AttrDict(dict):
    """
    辞書キーを属性としてアクセスできるようにするユーティリティクラス。
    ネストされた辞書も再帰的に属性アクセス可能にします。
    例: d['key'] の代わりに d.key と書ける。
    """
    def __init__(self, *args, **kwargs):
        super(_AttrDict, self).__init__(*args, **kwargs)
        # 辞書内の値がさらに辞書である場合、それも_AttrDictに変換する
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = _AttrDict(value)
        # __dict__に自分自身を代入することで、属性アクセスを実現する
        self.__dict__ = self
    
    # 補足: getメソッドなどでキーが存在しない場合にNoneが返るため、安全なアクセスが可能


class _Config:
    """
    設定ファイルを読み込み、管理するシングルトンクラス。

    アプリケーション起動時に一度だけインスタンスが生成され、
    以降は同じインスタンスが返されます。
    """
    # --- クラス定数の定義 ---
    _CONFIG_FILENAME = 'config.yaml'
    _ENV_FILENAME = '.env'

    # バリデーション用の設定
    _REQUIRED_API_KEYS = ('openai', 'youtube_video_id')
    _REQUIRED_PATHS = ('prompts', 'txt', 'summary')
    
    # --- シングルトン実装 ---
    _instance: Optional['_Config'] = None

    def __new__(cls) -> '_Config':
        if cls._instance is None:
            cls._instance = super(_Config, cls).__new__(cls)
            # 初回インスタンス生成時のみ設定を読み込む
            cls._instance._load_all_configs()
        return cls._instance

    def _load_all_configs(self):
        """設定ファイルと環境変数をすべて読み込み、インスタンス属性として設定する。"""
        # 1. プロジェクトのベースディレクトリを決定
        # このファイル(`config.py`)の場所を基準とする
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # 2. .env ファイルから環境変数を読み込む
        env_path = os.path.join(self.BASE_DIR, self._ENV_FILENAME)
        load_dotenv(env_path)

        # 3. config.yaml ファイルを読み込む
        config_path = os.path.join(self.BASE_DIR, self._CONFIG_FILENAME)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"'{self._CONFIG_FILENAME}' not found in the project root.")
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config_data: Dict[str, Any] = yaml.safe_load(f) or {}

        # 4. 各設定セクションを動的に読み込む
        #    これにより、yamlに新しいセクションを追加するだけで自動的に属性として追加される
        for section, data in self._config_data.items():
            if section == 'paths':
                # 'paths' セクションは特別扱いし、絶対パスに変換
                handler = self._build_absolute_paths
            elif section == 'api_keys':
                # 'api_keys' セクションも特別扱いし、環境変数から値を取得
                handler = self._load_api_keys_from_env
            else:
                # その他のセクションはそのまま属性アクセス可能な辞書に変換
                handler = lambda d: _AttrDict(d)
            
            setattr(self, section, handler(data))

    def _build_absolute_paths(self, path_config: Dict[str, str]) -> _AttrDict:
        """'paths' セクションの相対パスを絶対パスに変換する。"""
        absolute_paths = {
            key: os.path.join(self.BASE_DIR, relative_path)
            for key, relative_path in path_config.items()
        }
        return _AttrDict(absolute_paths)

    def _load_api_keys_from_env(self, key_config: Dict[str, str]) -> _AttrDict:
        """'api_keys' セクションで指定された環境変数名からAPIキーを読み込む。"""
        api_keys = {
            name: os.getenv(env_var_name)
            for name, env_var_name in key_config.items()
        }
        return _AttrDict(api_keys)

    def reload_config(self) -> bool:
        """
        設定ファイルを再読み込みする。
        これにより、アプリケーションを再起動せずに設定変更を反映できる。
        """
        print("[*] [Config] Reloading configuration files...")
        try:
            self._load_all_configs()
            print("[OK] [Config] Configuration reloaded successfully.")
            # 再読み込み後に再度ステータスを表示
            print_config_status()
            return True
        except Exception as e:
            print(f"[!] [Config] Failed to reload configuration: {e}")
            return False

    def get_config_info(self) -> Dict[str, Any]:
        """デバッグ用に、現在の設定情報のサマリーを返す。"""
        api_keys_dict = dict(self.api_keys)
        return {
            'base_dir': self.BASE_DIR,
            'config_sections': list(self._config_data.keys()),
            'api_keys_loaded': {key: value is not None for key, value in api_keys_dict.items()},
            'debug_settings': dict(self.debug)
        }

    def validate_config(self) -> List[str]:
        """
        設定内容の妥当性をチェックし、問題点のリストを返す。
        
        Returns:
            問題点を説明する文字列のリスト。問題がなければ空のリストを返す。
        """
        issues = []
        
        # 必須APIキーの存在チェック
        for key in self._REQUIRED_API_KEYS:
            if not self.api_keys.get(key):
                issues.append(f"Required API key '{key}' is not set in .env file.")
        
        # 必須ディレクトリ/パスの存在チェック
        for dir_key in self._REQUIRED_PATHS:
            path = self.paths.get(dir_key)
            if not path:
                issues.append(f"Path setting for '{dir_key}' is missing in config.yaml.")
            elif not os.path.exists(path):
                issues.append(f"Required path '{dir_key}' ('{path}') does not exist.")
        
        return issues

# --- シングルトンインスタンスの生成 ---
# このモジュールがインポートされた時点でインスタンスが生成され、
# `config` という名前でどこからでも参照可能になる。
config = _Config()

# --- モジュールインポート時に実行される処理 ---
def print_config_status():
    """設定の読み込み状況とバリデーション結果をコンソールに表示する。"""
    separator = "=" * 50
    print(f"\n{separator}")
    print("[+] Configuration System Initialized")
    print(separator)
    
    issues = config.validate_config()
    if issues:
        print("[!] Configuration Issues Found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("[OK] Configuration check: All OK.")
    
    info = config.get_config_info()
    api_keys_loaded_count = sum(info['api_keys_loaded'].values())
    total_api_keys = len(info['api_keys_loaded'])

    print(f"[*] Base Directory: {info['base_dir']}")
    print(f"[*] Loaded Sections: {', '.join(info['config_sections'])}")
    print(f"[*] API Keys Status: {api_keys_loaded_count}/{total_api_keys} loaded.")
    print(separator + "\n")

# このモジュールが他のスクリプトからインポートされた時にのみ、ステータスを表示する。
# `python config.py` のように直接実行した場合は表示しない。
if __name__ != "__main__":
    print_config_status()