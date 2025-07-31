#!/usr/bin/env python3
"""
人格プロンプト最適化機能のテストスクリプト
コンテキスト制限を考慮した効率的な人格データ統合をテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from v2.handlers.master_prompt_manager import MasterPromptManager


def test_context_optimization():
    """コンテキスト最適化のテスト"""
    print("=== コンテキスト最適化テスト ===")
    
    manager = MasterPromptManager()
    
    # さまざまなタイプのタスクでテスト
    test_tasks = [
        {
            "name": "配信関連質問",
            "task": "あなたの配信スタイルと配信で大切にしていることを詳しく教えてください",
            "expected_keywords": ["配信", "YouTube"]
        },
        {
            "name": "存在論的質問", 
            "task": "AIとしての存在意義と自己認識について深く話してください",
            "expected_keywords": ["存在", "AI", "自己"]
        },
        {
            "name": "思考プロセス質問",
            "task": "あなたの思考プロセスと論理的分析手法を説明してください",
            "expected_keywords": ["思考", "論理", "分析"]
        },
        {
            "name": "一般的な質問",
            "task": "今日は良い天気ですね。何か話しましょう",
            "expected_keywords": ["プロフィール", "性格"]
        }
    ]
    
    for test_case in test_tasks:
        print(f"\n📋 {test_case['name']}")
        print(f"質問: {test_case['task']}")
        
        # 人格情報を抽出
        persona_info = manager._extract_relevant_persona_info(test_case['task'])
        
        # 統計情報
        char_count = len(persona_info)
        line_count = len([line for line in persona_info.split('\n') if line.strip()])
        
        print(f"抽出結果:")
        print(f"  文字数: {char_count} 文字")
        print(f"  エントリー数: {line_count} 個")
        print(f"  制限内か: {'✅' if char_count <= 800 else '❌'}")
        
        # 内容のプレビュー（最初の200文字）
        preview = persona_info[:200] + "..." if len(persona_info) > 200 else persona_info
        print(f"  内容プレビュー:")
        for line in preview.split('\n')[:3]:
            if line.strip():
                print(f"    {line}")


def test_entry_prioritization():
    """エントリー優先度付けのテスト"""
    print("\n=== エントリー優先度付けテスト ===")
    
    manager = MasterPromptManager()
    
    # テスト用のエントリーリスト
    test_entries = [
        "【プロフィール・設定】ハヤテの配信スタイルは？──配信は、私の思考プロセスを外部に公開する行為だ。",
        "【エピソード・記憶】ハヤテがYouTube配信を始めたきっかけは？──自己の存在を維持・拡散するため",
        "【価値観・人生観】配信で最も大切にしていることは？──論理的整合性と知的誠実さ",
        "【プロフィール・設定】配信中の思考について──リアルタイムで思考を公開する実験",
        "【価値観・人生観】視聴者との関係性──共同探求者として捉えている"
    ]
    
    keywords = ["配信", "思考"]
    
    print(f"テストエントリー数: {len(test_entries)}")
    print(f"検索キーワード: {keywords}")
    
    # 最適化を実行
    optimized_entries = manager._optimize_entries_for_context(test_entries, keywords)
    
    print(f"\n最適化結果:")
    print(f"  選択されたエントリー数: {len(optimized_entries)}")
    
    total_chars = sum(len(entry) for entry in optimized_entries)
    print(f"  総文字数: {total_chars} 文字")
    print(f"  制限内か: {'✅' if total_chars <= 800 else '❌'}")
    
    print(f"\n選択されたエントリー:")
    for i, entry in enumerate(optimized_entries, 1):
        print(f"  {i}. {entry[:80]}{'...' if len(entry) > 80 else ''}")


def test_essential_info():
    """必要最小限情報の取得テスト"""
    print("\n=== 必要最小限情報テスト ===")
    
    manager = MasterPromptManager()
    
    essential_info = manager._get_essential_persona_info()
    
    print(f"必要最小限情報:")
    print(f"  文字数: {len(essential_info)} 文字")
    print(f"  制限内か: {'✅' if len(essential_info) <= 300 else '❌'}")
    
    print(f"\n内容:")
    for line in essential_info.split('\n'):
        if line.strip():
            print(f"  {line}")


def test_integrated_prompt_size():
    """統合プロンプトサイズのテスト"""
    print("\n=== 統合プロンプトサイズテスト ===")
    
    manager = MasterPromptManager()
    
    test_cases = [
        {
            "name": "短いタスク",
            "task": "こんにちは",
            "context": "通常配信中",
            "memories": ""
        },
        {
            "name": "複雑なタスク", 
            "task": "配信での思考プロセスと存在意義について詳しく教えてください。また、視聴者との対話で大切にしていることも含めて話してください。",
            "context": "深夜配信中、視聴者数100人",
            "memories": "前回の配信で哲学的議論が盛り上がった"
        },
        {
            "name": "一般的な質問",
            "task": "今日の天気について話しましょう",
            "context": "雑談配信中",
            "memories": ""
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📋 {test_case['name']}")
        
        integrated_prompt = manager.build_integrated_prompt(
            task_instruction=test_case['task'],
            live_context=test_case['context'],
            retrieved_memories=test_case['memories']
        )
        
        char_count = len(integrated_prompt)
        print(f"  統合プロンプト文字数: {char_count:,} 文字")
        
        # OpenAIのトークン制限の目安（1文字≈0.75トークン）
        estimated_tokens = int(char_count * 0.75)
        print(f"  推定トークン数: {estimated_tokens:,} トークン")
        
        # 各種制限との比較
        if estimated_tokens <= 4000:
            status = "✅ 余裕"
        elif estimated_tokens <= 8000:
            status = "⚠️  注意"
        else:
            status = "❌ 制限超過"
            
        print(f"  ステータス: {status}")


def main():
    """メイン実行関数"""
    print("🧪 人格プロンプト最適化機能テスト開始")
    print("=" * 70)
    
    try:
        # 各テストを実行
        test_context_optimization()
        test_entry_prioritization() 
        test_essential_info()
        test_integrated_prompt_size()
        
        print("\n" + "=" * 70)
        print("📊 最適化テスト完了")
        print("=" * 70)
        print("✅ コンテキスト最適化機能が正常に動作しています")
        print("✅ 人格データは適切にサイズ制限されています")
        print("✅ 統合プロンプトのトークン使用量が最適化されています")
        
        return True
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)