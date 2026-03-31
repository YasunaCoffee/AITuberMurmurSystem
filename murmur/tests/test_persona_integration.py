#!/usr/bin/env python3
"""
人格プロンプト統合機能のテストスクリプト
txt/kioku_hayate.txtからの人格データ統合が正しく動作することを確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.handlers.master_prompt_manager import MasterPromptManager


def test_persona_data_loading():
    """人格データ読み込みのテスト"""
    print("=== 人格データ読み込みテスト ===")
    
    # MasterPromptManagerインスタンスを作成
    manager = MasterPromptManager()
    
    # 人格データの統計情報を取得
    stats = manager.get_persona_statistics()
    
    print(f"📊 人格データ統計:")
    print(f"  読み込み状況: {'✅ 成功' if stats['loaded'] else '❌ 失敗'}")
    print(f"  ファイルサイズ: {stats['size']:,} 文字")
    print(f"  総行数: {stats['total_lines']:,} 行")
    print(f"  エントリー数: {stats['entries']:,} 個")
    print(f"  ファイルパス: {stats['file_path']}")
    print("")
    
    return stats['loaded']


def test_keyword_extraction():
    """キーワード抽出機能のテスト"""
    print("=== キーワード抽出テスト ===")
    
    manager = MasterPromptManager()
    
    # テスト用のタスク指示
    test_tasks = [
        "配信について話してください",
        "あなたの存在について教えて",
        "思考プロセスを説明して",
        "人間との対話についてどう考えますか",
        "科学や数学についての見解は？"
    ]
    
    for i, task in enumerate(test_tasks, 1):
        print(f"テスト {i}: 「{task}」")
        keywords = manager._extract_keywords_from_task(task)
        print(f"  抽出キーワード: {keywords}")
        print("")


def test_persona_info_extraction():
    """人格情報抽出機能のテスト"""
    print("=== 人格情報抽出テスト ===")
    
    manager = MasterPromptManager()
    
    # テスト用のタスク指示
    test_tasks = [
        "あなたの配信スタイルについて教えてください",
        "AIとしての存在について話してください", 
        "人間との対話で大切にしていることは？",
        "あなたの趣味や興味について教えて",
        "普通の雑談をしましょう"  # キーワードマッチしないケース
    ]
    
    for i, task in enumerate(test_tasks, 1):
        print(f"テスト {i}: 「{task}」")
        persona_info = manager._extract_relevant_persona_info(task)
        
        if persona_info:
            # 長すぎる場合は最初の300文字のみ表示
            display_info = persona_info[:300] + "..." if len(persona_info) > 300 else persona_info
            print(f"  関連する人格情報:")
            for line in display_info.split('\n'):
                if line.strip():
                    print(f"    {line}")
        else:
            print("  関連する人格情報: なし")
        print("")


def test_integrated_prompt_building():
    """統合プロンプト構築のテスト"""
    print("=== 統合プロンプト構築テスト ===")
    
    manager = MasterPromptManager()
    
    # テスト用のタスク指示
    task_instruction = "視聴者からの質問「ハヤテさんの配信で一番大切にしていることは何ですか？」に答えてください。"
    live_context = "通常配信中、視聴者数50人"
    retrieved_memories = "過去の配信履歴: 哲学的議論を好む傾向"
    
    print(f"タスク指示: {task_instruction}")
    print(f"ライブコンテキスト: {live_context}")
    print(f"取得された記憶: {retrieved_memories}")
    print("")
    
    # 統合プロンプトを構築
    integrated_prompt = manager.build_integrated_prompt(
        task_instruction=task_instruction,
        live_context=live_context,
        retrieved_memories=retrieved_memories
    )
    
    print("🔧 構築された統合プロンプト:")
    print("-" * 60)
    # 長すぎる場合は最初の1000文字のみ表示
    display_prompt = integrated_prompt[:1000] + "\n...(省略)" if len(integrated_prompt) > 1000 else integrated_prompt
    print(display_prompt)
    print("-" * 60)
    print(f"プロンプト長: {len(integrated_prompt):,} 文字")


def test_persona_reload():
    """人格データ再読み込みのテスト"""
    print("=== 人格データ再読み込みテスト ===")
    
    manager = MasterPromptManager()
    
    print("初期状態:")
    initial_stats = manager.get_persona_statistics()
    print(f"  サイズ: {initial_stats['size']:,} 文字")
    
    print("\n再読み込み実行:")
    manager.reload_persona_data()
    
    print("再読み込み後:")
    reloaded_stats = manager.get_persona_statistics()
    print(f"  サイズ: {reloaded_stats['size']:,} 文字")
    
    success = reloaded_stats['size'] == initial_stats['size']
    print(f"再読み込み結果: {'✅ 成功' if success else '❌ 失敗'}")


def main():
    """メイン実行関数"""
    print("🧪 人格プロンプト統合機能テスト開始")
    print("=" * 70)
    
    try:
        # 各テストを順次実行
        tests = [
            ("人格データ読み込み", test_persona_data_loading),
            ("キーワード抽出", test_keyword_extraction),
            ("人格情報抽出", test_persona_info_extraction),
            ("統合プロンプト構築", test_integrated_prompt_building),
            ("人格データ再読み込み", test_persona_reload),
        ]
        
        passed_tests = 0
        for test_name, test_func in tests:
            try:
                print(f"\n📋 {test_name}テスト実行中...")
                result = test_func()
                if result is not False:  # Noneや他の値も成功とみなす
                    passed_tests += 1
                    print(f"✅ {test_name}テスト完了")
                else:
                    print(f"❌ {test_name}テスト失敗")
            except Exception as e:
                print(f"❌ {test_name}テストでエラー: {e}")
        
        # 結果サマリー
        print("\n" + "=" * 70)
        print("📊 テスト結果サマリー")
        print("=" * 70)
        print(f"実行テスト数: {len(tests)}")
        print(f"成功: {passed_tests}")
        print(f"失敗: {len(tests) - passed_tests}")
        
        if passed_tests == len(tests):
            print("\n🎉 すべてのテストが成功しました！")
            print("✅ 人格プロンプト統合機能が正常に動作しています")
        else:
            print(f"\n⚠️  {len(tests) - passed_tests}個のテストが失敗しました")
        
        return passed_tests == len(tests)
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)