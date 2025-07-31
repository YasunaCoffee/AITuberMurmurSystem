#!/usr/bin/env python3
"""
コメントフィルタリング機能のテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from v2.utils.comment_filter import CommentFilter


def test_comment_filter():
    """コメントフィルター機能の総合テスト"""
    print("=== Comment Filter Test ===")
    
    # フィルター設定ファイルのパス
    config_path = "v2/config/comment_filter.json"
    
    # CommentFilterインスタンスを作成
    comment_filter = CommentFilter(config_path)
    
    # テスト用のコメントデータ
    test_comments = [
        # 正常なコメント
        {"message": "こんにちは！配信楽しいです", "author": {"name": "good_user"}},
        {"message": "今日の話面白かったです", "author": {"name": "viewer1"}},
        {"message": "ありがとうございます！", "author": {"name": "fan123"}},
        
        # NGワードを含むコメント
        {"message": "この宣伝チェックしてください", "author": {"name": "spam_user"}},
        {"message": "副業で稼げる方法教えます", "author": {"name": "scammer"}},
        {"message": "FX投資で儲かります", "author": {"name": "investment_spam"}},
        
        # URLを含むコメント
        {"message": "https://example.com をチェック", "author": {"name": "url_user"}},
        {"message": "www.spam.com 見てね", "author": {"name": "web_spam"}},
        
        # 文字数の問題
        {"message": "a", "author": {"name": "short_user"}},  # 短すぎる
        {"message": "あ" * 150, "author": {"name": "long_user"}},  # 長すぎる
        
        # 繰り返し文字
        {"message": "あああああああああ", "author": {"name": "repeat_user"}},
        {"message": "!!!!!!!!!", "author": {"name": "symbol_user"}},
        
        # 数字のみ
        {"message": "12345", "author": {"name": "number_user"}},
        
        # 大文字の連続
        {"message": "ABCDEFGHIJKLMNOP", "author": {"name": "caps_user"}},
        
        # エッジケース
        {"message": "", "author": {"name": "empty_user"}},  # 空文字
        {"message": "   ", "author": {"name": "space_user"}},  # 空白のみ
    ]
    
    print(f"📊 Filter Statistics: {comment_filter.get_statistics()}")
    print("\n🔍 Testing comments...")
    print("=" * 80)
    
    allowed_count = 0
    filtered_count = 0
    
    for i, comment in enumerate(test_comments, 1):
        result = comment_filter.filter_comment(comment)
        
        # 結果の表示
        status_icon = "✅" if result['allowed'] else "❌"
        print(f"\n[{i:2d}] {status_icon} User: {comment['author']['name']}")
        print(f"     Original: {comment['message'][:60]}{'...' if len(comment['message']) > 60 else ''}")
        
        if result['allowed']:
            print(f"     Cleaned:  {result['cleaned'][:60]}{'...' if len(result['cleaned']) > 60 else ''}")
            allowed_count += 1
        else:
            print(f"     Reason:   {result['reason']}")
            filtered_count += 1
    
    # 統計結果
    print("\n" + "=" * 80)
    print("📈 Test Results:")
    print(f"   Total Comments: {len(test_comments)}")
    print(f"   Allowed: {allowed_count}")
    print(f"   Filtered: {filtered_count}")
    print(f"   Filter Rate: {(filtered_count / len(test_comments) * 100):.1f}%")
    
    # 動的な追加/削除のテスト
    print("\n🔧 Testing dynamic operations...")
    
    # NGワードを動的に追加
    comment_filter.add_ng_word("テストNGワード")
    test_ng_comment = {"message": "テストNGワードを含むコメント", "author": {"name": "test_user"}}
    result = comment_filter.filter_comment(test_ng_comment)
    print(f"Added NG word test: {'PASS' if not result['allowed'] else 'FAIL'}")
    
    # NGワードを削除
    comment_filter.remove_ng_word("テストNGワード")
    result = comment_filter.filter_comment(test_ng_comment)
    print(f"Removed NG word test: {'PASS' if result['allowed'] else 'FAIL'}")
    
    # ブロックユーザーの追加
    comment_filter.add_blocked_user("blocked_test_user")
    blocked_comment = {"message": "普通のコメント", "author": {"name": "blocked_test_user"}}
    result = comment_filter.filter_comment(blocked_comment)
    print(f"Blocked user test: {'PASS' if not result['allowed'] else 'FAIL'}")
    
    print("\n✅ Comment filter test completed!")


def test_filter_with_real_patterns():
    """実際のスパムパターンでのテスト"""
    print("\n=== Real Spam Pattern Test ===")
    
    filter_instance = CommentFilter()
    
    # 実際のスパムパターン
    spam_patterns = [
        "チャンネル登録お願いします！",
        "相互登録しませんか？",
        "LINE追加してください: @abc123",
        "今すぐ稼げる副業の情報です",
        "投資で月100万円稼げます",
        "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥",  # 絵文字連続
        "aaaaaaaaaaaaa",  # 文字連続
        "CHECK THIS OUT: https://spam.com/offer",
        "SUBSCRIBE NOW FOR AMAZING CONTENT!!!!!",
    ]
    
    for pattern in spam_patterns:
        comment_data = {"message": pattern, "author": {"name": "spammer"}}
        result = filter_instance.filter_comment(comment_data)
        
        status = "BLOCKED" if not result['allowed'] else "ALLOWED"
        print(f"{status:8} | {pattern[:50]}{'...' if len(pattern) > 50 else ''}")
        if not result['allowed']:
            print(f"         | Reason: {result['reason']}")


if __name__ == "__main__":
    test_comment_filter()
    test_filter_with_real_patterns()