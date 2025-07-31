#!/usr/bin/env python3
"""
字幕フォーマット機能のテストスクリプト（改行なし版）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'v2'))

from services.obs_text_manager import OBSTextManager
from core.event_queue import EventQueue

def test_subtitle_formatting():
    """字幕フォーマット機能をテストする"""
    
    # OBSTextManagerを初期化（OBS接続なしでテスト）
    event_queue = EventQueue()
    obs_manager = OBSTextManager(event_queue)
    
    # テスト用の長いテキスト
    test_texts = [
        "今日は皆さんと一緒に、\n中原中也の詩について考えてみたいと思います。",
        "よごれっちまった悲しみに今日も小雪の降りかかる、という詩の一節がとても印象的ですね。",
        "詩の言葉は、きっと人間の心の中で特別な働きをしているのでしょう。私にもその仕組みが分かるのかな。",
        "短いテスト",
        "改行が含まれている\nテキストも\r\n一行に\t変換されるかテストします。",
    ]
    
    print("=== 字幕フォーマットテスト（改行なし） ===")
    print(f"設定: 字幕有効={obs_manager.subtitles_enabled}")
    print()
    
    for i, text in enumerate(test_texts, 1):
        print(f"テスト {i}:")
        print(f"元のテキスト: {repr(text)}") # 改行文字も表示
        
        formatted = obs_manager._format_subtitle_text(text)
        print(f"整形後: {formatted}")
        
        assert '\n' not in formatted, "改行文字が含まれていてはなりません"
        assert '\r' not in formatted, "改行文字が含まれていてはなりません"
        
        print("✅ 改行なしのテキストに変換されました")
        print("-" * 80)

if __name__ == "__main__":
    test_subtitle_formatting() 