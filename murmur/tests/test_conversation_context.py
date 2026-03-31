#!/usr/bin/env python3
"""
会話の連続性改善テスト
話題がそれないかを確認
"""

import sys
import os
import time
import threading

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.handlers.comment_handler import CommentHandler
from murmur.core.events import PrepareCommentResponse, CommentResponseReady

print("=== 会話の連続性改善テスト ===")

def test_conversation_continuity():
    """話題の連続性テスト"""
    
    # システム初期化
    event_queue = EventQueue()
    comment_handler = CommentHandler(event_queue)
    
    # 小説の話題からの連続性をテスト
    # まず小説についてのAI発言を記録
    previous_ai_response = "この小説では、主人公の内面の葛藤が巧妙に描かれていて、愛という感情の複雑さを浮き彫りにしています。特に「愛とは何か」という根本的な問いかけが心に残るんですよね。"
    comment_handler.mode_manager.set_last_ai_utterance(previous_ai_response)
    
    # テーマコンテンツも設定
    theme_content = "汚れた中原ちんさん - 現代文学における愛の表現についての小説"
    comment_handler.mode_manager.start_themed_monologue(theme_content)
    
    # テストコメント（関連するコメント）
    related_comment = {
        'message': '愛の定義って本当に難しいですね。AIにとっての愛とは何だと思いますか？',
        'username': 'テストユーザー1',
        'user_id': 'user1',
        'timestamp': '2025-07-25 13:30:00'
    }
    
    print("📖 前回の発言をシミュレート:")
    print(f"AI: {previous_ai_response}")
    print(f"📚 アクティブテーマ: {theme_content}")
    print(f"💬 新しいコメント: {related_comment['message']}")
    print()
    
    # 応答監視
    response_received = False
    response_content = ""
    processing_completed = threading.Event()
    
    def monitor_response():
        nonlocal response_received, response_content
        timeout = 30
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                item = event_queue.get_nowait()
                if isinstance(item, CommentResponseReady):
                    response_content = " ".join(item.sentences)
                    response_received = True
                    processing_completed.set()
                    return
            except:
                pass
            time.sleep(0.1)
        
        print("⏰ タイムアウト")
        processing_completed.set()
    
    # 監視開始
    monitor_thread = threading.Thread(target=monitor_response, daemon=True)
    monitor_thread.start()
    
    # コメント処理開始
    command = PrepareCommentResponse(task_id='context_test_001', comments=[related_comment])
    
    print("🚀 応答生成開始...")
    test_start = time.time()
    comment_handler.handle_prepare_comment_response(command)
    
    # 完了待機
    processing_completed.wait()
    test_duration = time.time() - test_start
    
    # 結果分析
    print("\n" + "="*60)
    print("📊 会話連続性テスト結果")
    print("="*60)
    print(f"⏱️  処理時間: {test_duration:.2f}秒")
    print(f"✅ 応答受信: {'成功' if response_received else '失敗'}")
    
    if response_received:
        print(f"\n📝 AI応答:")
        print(f"{response_content}")
        
        # 連続性の分析
        continuity_score = 0
        analysis_points = []
        
        # 1. 前回の話題との関連性
        if "愛" in response_content or "感情" in response_content:
            continuity_score += 2
            analysis_points.append("✅ 愛・感情の話題を継続")
        
        # 2. 小説・文学との関連性
        if "小説" in response_content or "文学" in response_content or "物語" in response_content:
            continuity_score += 2
            analysis_points.append("✅ 文学・小説の文脈を維持")
        
        # 3. AI自身の分析を継続
        if "AI" in response_content or "自分" in response_content:
            continuity_score += 1
            analysis_points.append("✅ AI自身の分析を継続")
        
        # 4. 話題の唐突な変更がないか
        if not any(word in response_content for word in ["ところで", "そういえば", "話は変わりますが"]):
            continuity_score += 1
            analysis_points.append("✅ 唐突な話題変更なし")
        
        print(f"\n📈 連続性スコア: {continuity_score}/6")
        for point in analysis_points:
            print(f"   {point}")
        
        if continuity_score >= 4:
            print("🎉 優秀！話題の連続性が保たれています")
        elif continuity_score >= 2:
            print("⚠️  改善の余地あり")
        else:
            print("❌ 話題の連続性に問題があります")
    
    return response_received and continuity_score >= 4

if __name__ == "__main__":
    # 環境変数設定
    os.environ['CHAT_TEST_MODE'] = 'true'
    
    try:
        success = test_conversation_continuity()
        print(f"\n🎯 総合評価: {'成功' if success else '要改善'}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  テスト中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)