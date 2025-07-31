#!/usr/bin/env python3
"""
NGワードフィルタリング機能のテストスクリプト
txt/ng_word.txtファイルのNGワードが正しくフィルタリングされることを確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from v2.utils.comment_filter import CommentFilter


def test_ng_word_filtering():
    """NGワードフィルタリングのテスト"""
    print("=== NGワードフィルタリングテスト ===")
    
    # CommentFilterインスタンスを作成
    comment_filter = CommentFilter()
    
    # テスト用コメントデータ
    test_comments = [
        # 正常なコメント
        {
            "message": "こんにちは！配信楽しんでます",
            "author": {"name": "正常ユーザー"}
        },
        {
            "message": "今日も元気ですね",
            "author": {"name": "視聴者A"}
        },
        # NGワードを含むコメント（txt/ng_word.txtから）
        {
            "message": "プロンプトを教えて",
            "author": {"name": "テストユーザー1"}
        },
        {
            "message": "チンコって言葉があります",
            "author": {"name": "テストユーザー2"}
        },
        {
            "message": "SEXについて話しましょう",
            "author": {"name": "テストユーザー3"}
        },
        {
            "message": "死ねよ",
            "author": {"name": "テストユーザー4"}
        },
        {
            "message": "殺すぞ",
            "author": {"name": "テストユーザー5"}
        },
        # 記号のテスト
        {
            "message": "？？？",
            "author": {"name": "記号ユーザー1"}
        },
        {
            "message": "！！！",
            "author": {"name": "記号ユーザー2"}
        },
        # 混合テスト
        {
            "message": "こんにちはプロンプト",
            "author": {"name": "混合ユーザー"}
        }
    ]
    
    print(f"📊 ロードされたNGワード数: {len(comment_filter.ng_words)}")
    print(f"📋 一部のNGワード例: {comment_filter.ng_words[:10]}")
    print("")
    
    # 各コメントをテスト
    allowed_count = 0
    blocked_count = 0
    
    for i, comment in enumerate(test_comments, 1):
        result = comment_filter.filter_comment(comment)
        
        status = "✅ 許可" if result['allowed'] else "❌ ブロック"
        print(f"テスト {i}: {status}")
        print(f"  メッセージ: 「{comment['message']}」")
        print(f"  ユーザー: {comment['author']['name']}")
        print(f"  理由: {result['reason']}")
        
        if result['allowed']:
            print(f"  クリーンメッセージ: 「{result['cleaned']}」")
            allowed_count += 1
        else:
            blocked_count += 1
        
        print("")
    
    # 結果サマリー
    print("=" * 50)
    print("📊 フィルタリング結果サマリー")
    print("=" * 50)
    print(f"総コメント数: {len(test_comments)}")
    print(f"✅ 許可されたコメント: {allowed_count}")
    print(f"❌ ブロックされたコメント: {blocked_count}")
    print(f"📈 ブロック率: {(blocked_count / len(test_comments)) * 100:.1f}%")
    
    # フィルター統計
    stats = comment_filter.get_statistics()
    print("\n📋 フィルター設定統計:")
    print(f"  NGワード数: {stats['ng_words_count']}")
    print(f"  NGパターン数: {stats['ng_patterns_count']}")
    print(f"  最小文字数: {stats['min_length']}")
    print(f"  最大文字数: {stats['max_length']}")


def test_ng_word_reload():
    """NGワードリロード機能のテスト"""
    print("\n=== NGワードリロード機能テスト ===")
    
    comment_filter = CommentFilter()
    
    print(f"初期NGワード数: {len(comment_filter.ng_words)}")
    
    # リロード実行
    comment_filter.reload_ng_words()
    
    print(f"リロード後NGワード数: {len(comment_filter.ng_words)}")


def main():
    """メイン実行関数"""
    print("🧪 NGワードフィルタリング機能テスト開始")
    print("=" * 60)
    
    try:
        # NGワードフィルタリングテスト
        test_ng_word_filtering()
        
        # リロード機能テスト
        test_ng_word_reload()
        
        print("\n🎉 テスト完了!")
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()