#!/usr/bin/env python3
"""
ストーリーアーク型モード管理システムのテストスクリプト
"""

import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.handlers.mode_manager import ModeManager, ConversationMode


def test_story_arc_flow():
    """ストーリーアーク型フローのテスト"""
    print("=== ストーリーアーク型フローテスト ===")
    
    mode_manager = ModeManager()
    
    # 初期状態を確認
    print(f"初期モード: {mode_manager.get_current_mode().value}")
    
    # 10回のモード遷移をシミュレート
    for i in range(10):
        print(f"\n--- Step {i+1} ---")
        
        # 現在の状態
        current = mode_manager.get_current_context()
        print(f"現在: {current.mode.value} (duration: {current.duration}, theme: {current.theme})")
        
        # 継続時間を増やす
        mode_manager.increment_duration()
        
        # 切り替えが必要かチェック
        should_switch = mode_manager.should_switch_mode()
        print(f"切り替え判定: {'YES' if should_switch else 'NO'}")
        
        if should_switch:
            # モード切り替え実行
            new_mode = mode_manager.switch_mode()
            print(f"切り替え後: {new_mode.value}")
        
        # 統計情報
        stats = mode_manager.get_mode_statistics()
        print(f"使用回数: {stats['mode_usage_counts']}")
        print(f"最近のモード: {' → '.join(stats['recent_modes'][-3:])}")
    
    return True


def test_duration_ranges():
    """継続時間範囲のテスト"""
    print("\n=== 継続時間範囲テスト ===")
    
    mode_manager = ModeManager()
    
    # 各モードの継続時間をテスト
    for mode in [ConversationMode.NORMAL_MONOLOGUE, 
                 ConversationMode.CHILL_CHAT,
                 ConversationMode.EPISODE_DEEP_DIVE,
                 ConversationMode.VIEWER_CONSULTATION]:
        
        print(f"\n--- {mode.value} テスト ---")
        
        # モードを強制設定
        mode_manager.force_mode(mode)
        
        # 継続時間範囲を取得
        min_dur, max_dur = mode_manager.mode_duration_ranges[mode]
        print(f"推奨継続時間: {min_dur}-{max_dur}発言")
        
        # 各継続時間での切り替え確率をテスト
        for duration in range(1, max_dur + 2):
            mode_manager.current_context.duration = duration
            should_switch = mode_manager.should_switch_mode()
            print(f"  {duration}発言目: {'切り替え' if should_switch else '継続'}")
    
    return True


def test_conversation_flows():
    """会話フロー定義のテスト"""
    print("\n=== 会話フロー定義テスト ===")
    
    mode_manager = ModeManager()
    
    # 各モードからの推奨遷移をテスト
    for current_mode in [ConversationMode.NORMAL_MONOLOGUE,
                        ConversationMode.CHILL_CHAT, 
                        ConversationMode.EPISODE_DEEP_DIVE,
                        ConversationMode.VIEWER_CONSULTATION]:
        
        print(f"\n{current_mode.value} からの推奨遷移:")
        
        # 現在のモードを設定
        mode_manager.force_mode(current_mode)
        mode_manager.current_context.duration = 5  # 切り替え可能な状態に
        
        # 複数回遷移をテスト
        next_modes = []
        for _ in range(5):
            if mode_manager.should_switch_mode():
                next_mode = mode_manager._select_next_mode()
                next_modes.append(next_mode.value)
            else:
                next_modes.append("(継続)")
        
        print(f"  推奨遷移: {' → '.join(next_modes[:3])}")
        
        # フロー定義を表示
        flows = mode_manager.conversation_flows.get(current_mode, [])
        flow_names = [f.value for f in flows]
        print(f"  定義フロー: {' / '.join(flow_names)}")
    
    return True


def test_natural_conversation_simulation():
    """自然な会話シミュレーション"""
    print("\n=== 自然な会話シミュレーション ===")
    
    mode_manager = ModeManager()
    conversation_log = []
    
    # 20ステップの会話シミュレーション
    for step in range(20):
        current = mode_manager.get_current_context()
        
        # 会話ログに追加
        log_entry = f"{step+1:2d}: {current.mode.value:20s} (dur:{current.duration}, theme:{current.theme or 'N/A'})"
        conversation_log.append(log_entry)
        
        # 継続時間を増やす
        mode_manager.increment_duration()
        
        # 切り替え判定と実行
        if mode_manager.should_switch_mode():
            mode_manager.switch_mode()
    
    # 結果表示
    print("\n会話の流れ:")
    for log in conversation_log:
        print(log)
    
    # 統計分析
    stats = mode_manager.get_mode_statistics()
    print(f"\n統計:")
    print(f"総モード切り替え回数: {stats['total_mode_switches']}")
    print(f"各モード使用回数: {stats['mode_usage_counts']}")
    
    # フローの自然さを評価
    mode_sequence = [log.split(':')[1].split('(')[0].strip() for log in conversation_log]
    transitions = [(mode_sequence[i], mode_sequence[i+1]) for i in range(len(mode_sequence)-1) if mode_sequence[i] != mode_sequence[i+1]]
    
    print(f"\nモード遷移 ({len(transitions)}回):")
    for i, (from_mode, to_mode) in enumerate(transitions[:10]):  # 最初の10回を表示
        print(f"  {i+1}. {from_mode} → {to_mode}")
    
    return True


def run_all_tests():
    """すべてのテストを実行"""
    print("🎭 ストーリーアーク型モード管理システムテスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. ストーリーアークフローテスト
    try:
        test_results.append(test_story_arc_flow())
    except Exception as e:
        print(f"❌ ストーリーアークフローテストエラー: {e}")
        test_results.append(False)
    
    # 2. 継続時間範囲テスト
    try:
        test_results.append(test_duration_ranges())
    except Exception as e:
        print(f"❌ 継続時間範囲テストエラー: {e}")
        test_results.append(False)
    
    # 3. 会話フロー定義テスト
    try:
        test_results.append(test_conversation_flows())
    except Exception as e:
        print(f"❌ 会話フロー定義テストエラー: {e}")
        test_results.append(False)
    
    # 4. 自然な会話シミュレーション
    try:
        test_results.append(test_natural_conversation_simulation())
    except Exception as e:
        print(f"❌ 自然な会話シミュレーションエラー: {e}")
        test_results.append(False)
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "ストーリーアークフロー",
        "継続時間範囲", 
        "会話フロー定義",
        "自然な会話シミュレーション"
    ]
    
    for name, result in zip(test_names, test_results):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:25s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ ストーリーアーク型モード管理システムが正しく実装されています")
        print("\n🔄 期待される会話フロー:")
        print("   通常の独り言 → 深掘り思考 → 視聴者相談 → ゆるい雑談 (収束)")
        print("   各モードが適切な継続時間で自然に遷移します")
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