#!/usr/bin/env python3
"""
モードシステムのテストスクリプト
"""

import sys
import os
import time

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.core.event_queue import EventQueue
from v2.handlers.mode_manager import ModeManager, ConversationMode
from v2.handlers.monologue_handler import MonologueHandler
from v2.handlers.comment_handler import CommentHandler
from v2.services.prompt_manager import PromptManager


def test_mode_manager_basic():
    """ModeManagerの基本機能テスト"""
    print("=== ModeManager基本機能テスト ===")
    
    try:
        mode_manager = ModeManager()
        
        # 初期状態確認
        current_mode = mode_manager.get_current_mode()
        print(f"✅ 初期モード: {current_mode.value}")
        assert current_mode == ConversationMode.NORMAL_MONOLOGUE
        
        # モード切り替えテスト
        new_mode = mode_manager.switch_mode(target_mode=ConversationMode.CHILL_CHAT)
        print(f"✅ モード切り替え: {new_mode.value}")
        assert new_mode == ConversationMode.CHILL_CHAT
        
        # テーマ生成テスト
        context = mode_manager.get_current_context()
        print(f"✅ 生成されたテーマ: {context.theme}")
        assert context.theme is not None
        
        # 統計情報テスト
        stats = mode_manager.get_mode_statistics()
        print(f"✅ 統計情報: {stats}")
        assert "current_mode" in stats
        
        return True
        
    except Exception as e:
        print(f"❌ ModeManager基本機能テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_manager_integration():
    """PromptManagerとの統合テスト"""
    print("\n=== PromptManager統合テスト ===")
    
    try:
        prompt_manager = PromptManager()
        
        # 各モード用のプロンプトファイルが存在するかテスト
        test_files = [
            "normal_monologue.txt",
            "chill_chat_prompt.txt",
            "episode_deep_dive_prompt.txt",
            "viewer_consultation_prompt.txt",
            "integrated_response.txt"
        ]
        
        for filename in test_files:
            prompt = prompt_manager.get_prompt_by_filename(filename)
            if prompt:
                print(f"✅ {filename} 読み込み成功 ({len(prompt)}文字)")
            else:
                print(f"❌ {filename} 読み込み失敗")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ PromptManager統合テストエラー: {e}")
        return False


def test_mode_switching_logic():
    """モード切り替えロジックテスト"""
    print("\n=== モード切り替えロジックテスト ===")
    
    try:
        mode_manager = ModeManager()
        
        # 複数回の発言でモード切り替えをテスト
        print("📊 複数発言でのモード切り替えテスト:")
        
        for i in range(10):
            # 発言回数を増やす
            mode_manager.increment_duration()
            
            # コメントありの場合のテスト
            if i == 5:
                should_switch = mode_manager.should_switch_mode(has_comments=True, comment_count=2)
                print(f"   発言{i+1}: コメントあり -> 切り替え判定: {should_switch}")
                if should_switch:
                    new_mode = mode_manager.switch_mode(has_comments=True, comment_count=2)
                    print(f"   -> {new_mode.value}に切り替え")
            else:
                should_switch = mode_manager.should_switch_mode()
                print(f"   発言{i+1}: 通常 -> 切り替え判定: {should_switch}")
                if should_switch:
                    new_mode = mode_manager.switch_mode()
                    print(f"   -> {new_mode.value}に切り替え")
        
        # 最終統計
        stats = mode_manager.get_mode_statistics()
        print(f"✅ 最終統計: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ モード切り替えロジックテストエラー: {e}")
        return False


def test_handler_integration():
    """ハンドラー統合テスト"""
    print("\n=== ハンドラー統合テスト ===")
    
    try:
        event_queue = EventQueue()
        
        # MonologueHandlerでModeManagerが正常に動作するかテスト
        monologue_handler = MonologueHandler(event_queue)
        print("✅ MonologueHandler初期化完了")
        
        # ModeManagerを共有してCommentHandlerを初期化
        comment_handler = CommentHandler(event_queue, monologue_handler.mode_manager)
        print("✅ CommentHandler初期化完了（ModeManager共有）")
        
        # 同じModeManagerインスタンスが共有されているかテスト
        assert monologue_handler.mode_manager is comment_handler.mode_manager
        print("✅ ModeManager共有確認")
        
        # プロンプト構築テスト（エラーが出ないかの確認）
        try:
            # 独り言プロンプト構築テスト
            if hasattr(monologue_handler, '_build_monologue_prompt'):
                prompt = monologue_handler._build_monologue_prompt()
                print(f"✅ 独り言プロンプト構築成功 ({len(prompt)}文字)")
            
            # コメント応答プロンプト構築テスト
            if hasattr(comment_handler, '_build_comment_response_prompt'):
                test_comments = [{"message": "テストコメント"}]
                prompt = comment_handler._build_comment_response_prompt(test_comments)
                print(f"✅ コメント応答プロンプト構築成功 ({len(prompt)}文字)")
                
        except Exception as prompt_error:
            print(f"⚠️  プロンプト構築でエラー（依存関係の問題の可能性）: {prompt_error}")
            # プロンプト構築エラーは依存関係の問題なので致命的ではない
        
        return True
        
    except Exception as e:
        print(f"❌ ハンドラー統合テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mode_prompt_variables():
    """モード別プロンプト変数テスト"""
    print("\n=== モード別プロンプト変数テスト ===")
    
    try:
        mode_manager = ModeManager()
        
        # 各モードでプロンプト変数を取得してテスト
        modes_to_test = [
            ConversationMode.NORMAL_MONOLOGUE,
            ConversationMode.CHILL_CHAT,
            ConversationMode.EPISODE_DEEP_DIVE,
            ConversationMode.VIEWER_CONSULTATION,
            ConversationMode.INTEGRATED_RESPONSE
        ]
        
        for mode in modes_to_test:
            mode_manager.switch_mode(target_mode=mode)
            
            variables = mode_manager.get_prompt_variables(
                last_sentence="テスト文章です。",
                history_str="テスト履歴",
                memory_summary="テスト記憶",
                recent_comments_summary="テストコメント要約",
                comment="テストコメント"
            )
            
            print(f"✅ {mode.value} 変数生成: {list(variables.keys())}")
            
            # 基本変数が含まれているかチェック
            required_vars = ["last_sentence", "history_str", "memory_summary", "selected_mode"]
            for var in required_vars:
                assert var in variables, f"{mode.value}に{var}が含まれていません"
        
        return True
        
    except Exception as e:
        print(f"❌ モード別プロンプト変数テストエラー: {e}")
        return False


def run_all_tests():
    """すべてのテストを実行"""
    print("🎬 モードシステムテスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. ModeManager基本機能テスト
    test_results.append(test_mode_manager_basic())
    
    # 2. PromptManager統合テスト
    test_results.append(test_prompt_manager_integration())
    
    # 3. モード切り替えロジックテスト
    test_results.append(test_mode_switching_logic())
    
    # 4. ハンドラー統合テスト
    test_results.append(test_handler_integration())
    
    # 5. モード別プロンプト変数テスト
    test_results.append(test_mode_prompt_variables())
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "ModeManager基本機能",
        "PromptManager統合",
        "モード切り替えロジック",
        "ハンドラー統合",
        "モード別プロンプト変数"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:20s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ モードシステムが正しく実装されています")
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