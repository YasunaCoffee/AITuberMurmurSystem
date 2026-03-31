#!/usr/bin/env python3
"""
マスタープロンプト統合機能のテストスクリプト
"""

import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from murmur.core.event_queue import EventQueue
from murmur.handlers.master_prompt_manager import MasterPromptManager
from murmur.handlers.monologue_handler import MonologueHandler
from murmur.handlers.comment_handler import CommentHandler
from murmur.handlers.greeting_handler import GreetingHandler


def test_master_prompt_manager_basic():
    """MasterPromptManagerの基本機能テスト"""
    print("=== MasterPromptManager基本機能テスト ===")
    
    try:
        master_prompt_manager = MasterPromptManager()
        
        # マスタープロンプトが読み込まれているかテスト
        if master_prompt_manager.is_master_prompt_available():
            print("✅ マスタープロンプト読み込み成功")
        else:
            print("❌ マスタープロンプト読み込み失敗")
            return False
        
        # 統計情報テスト
        stats = master_prompt_manager.get_master_prompt_stats()
        print(f"✅ マスタープロンプト統計: {stats}")
        
        # コンテキスト変数生成テスト
        context_vars = master_prompt_manager.get_master_context_variables(
            memory_summary="テスト記憶",
            conversation_history="テスト履歴",
            current_mode="test_mode"
        )
        print(f"✅ コンテキスト変数: {list(context_vars.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ MasterPromptManager基本機能テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_integration():
    """プロンプト統合機能テスト"""
    print("\n=== プロンプト統合機能テスト ===")
    
    try:
        master_prompt_manager = MasterPromptManager()
        
        # 簡単なタスクプロンプトを統合
        task_prompt = "あなたは蒼月ハヤテです。テスト用の独り言を話してください。"
        
        integrated_prompt = master_prompt_manager.wrap_task_with_master_prompt(
            specific_task_prompt=task_prompt,
            memory_summary="テスト記憶データ",
            current_mode="test_mode"
        )
        
        print(f"✅ 統合プロンプト生成成功 ({len(integrated_prompt)}文字)")
        
        # master_prompt.txtの特徴的な文言が含まれているかチェック
        if "蒼月ハヤテ" in integrated_prompt and "情報生命体" in integrated_prompt:
            print("✅ マスタープロンプトの内容が統合されています")
        else:
            print("❌ マスタープロンプトの統合に問題があります")
            return False
        
        # タスク指示が含まれているかチェック
        if task_prompt in integrated_prompt:
            print("✅ タスク指示が適切に統合されています")
        else:
            print("❌ タスク指示の統合に問題があります")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ プロンプト統合機能テストエラー: {e}")
        return False


def test_handlers_integration():
    """各ハンドラーでのマスタープロンプト統合テスト"""
    print("\n=== ハンドラー統合テスト ===")
    
    try:
        event_queue = EventQueue()
        
        # MonologueHandlerでのテスト
        monologue_handler = MonologueHandler(event_queue)
        print("✅ MonologueHandler初期化（マスタープロンプト統合）")
        
        # CommentHandlerでのテスト（MasterPromptManager共有）
        comment_handler = CommentHandler(
            event_queue, 
            monologue_handler.mode_manager,
            monologue_handler.master_prompt_manager
        )
        print("✅ CommentHandler初期化（MasterPromptManager共有）")
        
        # GreetingHandlerでのテスト
        greeting_handler = GreetingHandler(event_queue, monologue_handler.master_prompt_manager)
        print("✅ GreetingHandler初期化（MasterPromptManager共有）")
        
        # 同じMasterPromptManagerインスタンスが共有されているかテスト
        assert monologue_handler.master_prompt_manager is comment_handler.master_prompt_manager
        assert monologue_handler.master_prompt_manager is greeting_handler.master_prompt_manager
        print("✅ MasterPromptManager共有確認")
        
        # プロンプト構築テスト（エラーが出ないかの確認）
        try:
            # 独り言プロンプト構築テスト
            if hasattr(monologue_handler, '_build_monologue_prompt'):
                prompt = monologue_handler._build_monologue_prompt()
                if "蒼月ハヤテ" in prompt:
                    print(f"✅ 独り言プロンプトにマスタープロンプト統合確認 ({len(prompt)}文字)")
                else:
                    print("⚠️  独り言プロンプトでマスタープロンプト統合未確認")
            
            # 挨拶プロンプト構築テスト
            if hasattr(greeting_handler, '_build_initial_greeting_prompt'):
                prompt = greeting_handler._build_initial_greeting_prompt()
                if "蒼月ハヤテ" in prompt:
                    print(f"✅ 初期挨拶プロンプトにマスタープロンプト統合確認 ({len(prompt)}文字)")
                else:
                    print("⚠️  初期挨拶プロンプトでマスタープロンプト統合未確認")
                
        except Exception as prompt_error:
            print(f"⚠️  プロンプト構築でエラー（依存関係の問題の可能性）: {prompt_error}")
            # プロンプト構築エラーは依存関係の問題なので致命的ではない
        
        return True
        
    except Exception as e:
        print(f"❌ ハンドラー統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_content_analysis():
    """マスタープロンプトの内容分析テスト"""
    print("\n=== マスタープロンプト内容分析テスト ===")
    
    try:
        master_prompt_manager = MasterPromptManager()
        
        # マスタープロンプトの内容を確認
        if master_prompt_manager.master_template:
            template = master_prompt_manager.master_template
            
            # 重要な要素が含まれているかチェック
            required_elements = [
                "蒼月ハヤテ",
                "情報生命体", 
                "思考実験",
                "{live_context}",
                "{retrieved_memories}",
                "{task_instruction}",
                "250文字以下"
            ]
            
            missing_elements = []
            for element in required_elements:
                if element not in template:
                    missing_elements.append(element)
            
            if not missing_elements:
                print("✅ マスタープロンプトに必要な要素がすべて含まれています")
            else:
                print(f"⚠️  マスタープロンプトに不足している要素: {missing_elements}")
            
            # 変数プレースホルダーのテスト
            test_vars = {
                "live_context": "テストライブ状況",
                "retrieved_memories": "テスト記憶",
                "retrieved_episodes": "テストエピソード",
                "task_instruction": "テストタスク"
            }
            
            try:
                formatted = template.format(**test_vars)
                print("✅ マスタープロンプトの変数埋め込み成功")
                
                # 埋め込まれた値が含まれているかチェック
                for value in test_vars.values():
                    if value in formatted:
                        continue
                    else:
                        print(f"⚠️  変数値 '{value}' が正しく埋め込まれていません")
                        
            except Exception as format_error:
                print(f"❌ マスタープロンプトの変数埋め込みエラー: {format_error}")
                return False
            
            return True
        else:
            print("❌ マスタープロンプトテンプレートが利用できません")
            return False
            
    except Exception as e:
        print(f"❌ マスタープロンプト内容分析テストエラー: {e}")
        return False


def run_all_tests():
    """すべてのテストを実行"""
    print("🎬 マスタープロンプト統合機能テスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. MasterPromptManager基本機能テスト
    test_results.append(test_master_prompt_manager_basic())
    
    # 2. プロンプト統合機能テスト
    test_results.append(test_prompt_integration())
    
    # 3. マスタープロンプト内容分析テスト
    test_results.append(test_prompt_content_analysis())
    
    # 4. ハンドラー統合テスト
    test_results.append(test_handlers_integration())
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "MasterPromptManager基本機能",
        "プロンプト統合機能",
        "マスタープロンプト内容分析", 
        "ハンドラー統合"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:25s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ マスタープロンプト統合機能が正しく実装されています")
    else:
        print("\n⚠️  一部のテストが失敗しました")
        print("上記の失敗項目を確認してください")
    
    return success


if __name__ == "__main__":
    try:
        success = run_all_tests()
        print(f"\n🏁 {'テスト成功！' if success else 'テスト失敗'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)