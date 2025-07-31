#!/usr/bin/env python3
"""
YouTubeビデオID設定確認スクリプト
現在の設定状態を確認し、問題があれば解決方法を提示
"""

import os
import re
from dotenv import load_dotenv
from pathlib import Path

def check_youtube_config():
    """YouTube設定の確認と診断"""
    print("=== YouTubeビデオID設定確認 ===")
    print()
    
    # 1. .envファイルの存在確認
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .envファイルが見つかりません")
        print("   解決方法: .env.templateをコピーして.envファイルを作成してください")
        print("   コマンド: cp .env.template .env")
        return False
    else:
        print("✅ .envファイルが存在します")
    
    # 2. 環境変数の読み込み
    load_dotenv()
    
    # 3. YOUTUBE_VIDEO_IDの確認
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    if not video_id:
        print("❌ YOUTUBE_VIDEO_IDが設定されていません")
        print("   解決方法: .envファイルでYOUTUBE_VIDEO_IDを設定してください")
        print("   例: YOUTUBE_VIDEO_ID=Hy8XMuTYa_g")
        return False
    else:
        print(f"✅ YOUTUBE_VIDEO_ID: {video_id}")
        
        # ビデオIDの形式確認
        if is_valid_youtube_video_id(video_id):
            print("✅ ビデオIDの形式は正しいです")
        else:
            print("⚠️  ビデオIDの形式が不正の可能性があります")
            print("   YouTubeビデオIDは通常11文字の英数字とハイフン、アンダースコアで構成されます")
    
    # 4. その他の設定確認
    chat_test_mode = os.getenv('CHAT_TEST_MODE', 'false')
    force_test_on_error = os.getenv('FORCE_TEST_ON_ERROR', 'false')
    
    print(f"📋 CHAT_TEST_MODE: {chat_test_mode}")
    print(f"📋 FORCE_TEST_ON_ERROR: {force_test_on_error}")
    
    # 5. OpenAI API設定確認
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        print("⚠️  OPENAI_API_KEYが設定されていません")
        print("   システム動作にはOpenAI APIキーが必要です")
    else:
        print("✅ OPENAI_API_KEYが設定されています")
    
    # 6. OBS設定確認（オプション）
    obs_password = os.getenv('OBS_WS_PASSWORD')
    if obs_password:
        print("✅ OBS WebSocket設定が見つかりました")
    else:
        print("📋 OBS WebSocket設定が未設定（オプション）")
    
    print()
    print("=== 設定完了確認 ===")
    
    # 必須設定のチェック
    required_settings = {
        'YOUTUBE_VIDEO_ID': video_id,
        'OPENAI_API_KEY': openai_key
    }
    
    missing_settings = [key for key, value in required_settings.items() if not value]
    
    if missing_settings:
        print("❌ 以下の必須設定が不足しています:")
        for setting in missing_settings:
            print(f"   - {setting}")
        return False
    else:
        print("✅ すべての必須設定が完了しています")
        return True

def is_valid_youtube_video_id(video_id):
    """YouTubeビデオIDの形式が正しいかチェック"""
    # YouTubeビデオIDは通常11文字の英数字、ハイフン、アンダースコア
    pattern = r'^[a-zA-Z0-9_-]{11}$'
    return re.match(pattern, video_id) is not None

def extract_video_id_from_url(url):
    """YouTubeURLからビデオIDを抽出"""
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def interactive_setup():
    """対話的な設定セットアップ"""
    print("\n=== 対話的設定セットアップ ===")
    
    # YouTubeURLの入力
    print("\n1. YouTubeライブ配信のURLを入力してください:")
    print("   例: https://www.youtube.com/watch?v=Hy8XMuTYa_g")
    url = input("URL: ").strip()
    
    if url:
        video_id = extract_video_id_from_url(url)
        if video_id:
            print(f"✅ ビデオIDを抽出しました: {video_id}")
            
            # .envファイルの更新
            update_env_file('YOUTUBE_VIDEO_ID', video_id)
            print("✅ .envファイルを更新しました")
        else:
            print("❌ URLからビデオIDを抽出できませんでした")
            print("   手動でビデオIDを入力してください:")
            video_id = input("ビデオID: ").strip()
            if video_id:
                update_env_file('YOUTUBE_VIDEO_ID', video_id)
    
    # テストモードの設定
    print("\n2. テストモードを使用しますか？")
    print("   true: ダミーコメントでテスト")
    print("   false: 実際のライブ配信に接続")
    test_mode = input("テストモード (true/false) [false]: ").strip() or 'false'
    update_env_file('CHAT_TEST_MODE', test_mode)
    
    print("\n✅ 設定が完了しました！")

def update_env_file(key, value):
    """環境変数ファイルを更新"""
    env_file = Path('.env')
    
    if env_file.exists():
        # 既存の.envファイルを読み込み
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 該当する行を更新
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}\n'
                updated = True
                break
        
        # 新しい設定を追加
        if not updated:
            lines.append(f'{key}={value}\n')
        
        # ファイルに書き戻し
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    else:
        # 新しい.envファイルを作成
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')

def show_usage_examples():
    """使用例の表示"""
    print("\n=== 使用例 ===")
    print()
    
    print("1. 基本的な接続テスト:")
    print("   python test_youtube_live_simple.py")
    print()
    
    print("2. v2システム統合テスト:")
    print("   cd v2 && python run_integrated_test.py")
    print()
    
    print("3. コメントフィルターテスト:")
    print("   python test_comment_filter.py")
    print()
    
    print("4. システム全体の実行:")
    print("   python main_v2.py")

def main():
    """メイン実行関数"""
    config_ok = check_youtube_config()
    
    if not config_ok:
        print("\n設定を自動で行いますか？ (y/n): ", end="")
        response = input().lower().strip()
        if response == 'y':
            interactive_setup()
            # 再チェック
            print("\n" + "="*50)
            check_youtube_config()
        else:
            print("\n手動で.envファイルを編集してください")
            return
    
    show_usage_examples()
    
    print("\n=== 設定確認完了 ===")
    print("システムの準備が整いました！")

if __name__ == "__main__":
    main()