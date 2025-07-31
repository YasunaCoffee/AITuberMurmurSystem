"""
コメントフィルタリング機能
YouTubeライブコメントに対してNGワードや不適切コンテンツのフィルタリングを実行
"""

import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


class CommentFilter:
    """コメントのフィルタリングを行うクラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.ng_words: List[str] = []
        self.ng_patterns: List[re.Pattern] = []
        self.allowed_users: List[str] = []
        self.blocked_users: List[str] = []
        self.min_comment_length = 1
        self.max_comment_length = 200
        
        # 部分一致のオプション設定
        self.strict_matching = True  # 厳密な部分一致（現在の動作）
        self.word_boundary_checking = False  # 単語境界チェック（誤検知を減らす）
        
        # デフォルト設定の読み込み
        self._load_default_filters()
        
        # カスタム設定があれば読み込み
        if config_path:
            self.load_config(config_path)
    
    def _load_default_filters(self):
        """デフォルトのフィルタリング設定を読み込み"""
        # 基本的なNGワード
        default_ng_words = [
            "スパム", "宣伝", "広告", "アンチ", "荒らし",
            "死ね", "消えろ", "うざい", "きもい", "ブス",
            "詐欺", "騙", "違法", "犯罪", "殺"
        ]
        
        # 英語のNGワード
        english_ng_words = [
            "spam", "advertisement", "scam", "fake", "bot",
            "hate", "kill", "die", "stupid", "ugly"
        ]
        
        # txt/ng_word.txtからNGワードを読み込み
        ng_words_from_file = self._load_ng_words_from_file()
        
        self.ng_words = default_ng_words + english_ng_words + ng_words_from_file
        
        # 正規表現パターン（URL、連続文字など）
        self.ng_patterns = [
            re.compile(r'https?://[^\s]+', re.IGNORECASE),  # URL
            re.compile(r'(.)\1{4,}'),  # 同じ文字の5回以上連続
            re.compile(r'[!@#$%^&*]{3,}'),  # 記号の連続
            re.compile(r'^\d+$'),  # 数字のみ
            re.compile(r'[A-Z]{10,}'),  # 大文字の連続
        ]
    
    def _load_ng_words_from_file(self) -> List[str]:
        """txt/ng_word.txtファイルからNGワードを読み込み"""
        ng_words = []
        ng_word_file = Path("txt/ng_word.txt")
        
        try:
            if ng_word_file.exists():
                with open(ng_word_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip()
                        # 空行をスキップ、#単体はNGワードとして扱う
                        if word:
                            # #で始まるが#単体でない場合のみコメント行として扱う
                            if word.startswith('#') and len(word) > 1:
                                continue  # コメント行をスキップ
                            ng_words.append(word)
                print(f"[CommentFilter] NGワードファイルから {len(ng_words)} 個のワードを読み込みました")
            else:
                print(f"[CommentFilter] NGワードファイルが見つかりません: {ng_word_file}")
        except Exception as e:
            print(f"[CommentFilter] NGワードファイル読み込みエラー: {e}")
        
        return ng_words
    
    def load_config(self, config_path: str):
        """設定ファイルからフィルタリング設定を読み込み"""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # NGワードの追加
                if 'ng_words' in config:
                    self.ng_words.extend(config['ng_words'])
                
                # ユーザーリストの設定
                if 'allowed_users' in config:
                    self.allowed_users = config['allowed_users']
                
                if 'blocked_users' in config:
                    self.blocked_users = config['blocked_users']
                
                # 文字数制限
                if 'min_comment_length' in config:
                    self.min_comment_length = config['min_comment_length']
                
                if 'max_comment_length' in config:
                    self.max_comment_length = config['max_comment_length']
                
                # マッチングモード設定
                if 'matching_mode' in config:
                    mode = config['matching_mode']
                    if mode == 'strict':
                        self.set_matching_mode(strict=True, word_boundary=False)
                    elif mode == 'word_boundary':
                        self.set_matching_mode(strict=False, word_boundary=True)
                    elif mode == 'standard':
                        self.set_matching_mode(strict=False, word_boundary=False)
                
        except Exception as e:
            print(f"Warning: Failed to load filter config: {e}")
    
    def filter_comment(self, comment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        コメントをフィルタリングして結果を返す
        
        Args:
            comment_data: コメントデータ（message, author情報を含む）
        
        Returns:
            フィルタリング結果を含む辞書
            {
                'allowed': bool,  # コメントが許可されるか
                'reason': str,    # 拒否された場合の理由
                'original': dict, # 元のコメントデータ
                'cleaned': str    # クリーニング後のメッセージ（allowedがTrueの場合）
            }
        """
        message = comment_data.get('message', '')
        author_name = comment_data.get('author', {}).get('name', '')
        
        # 1. ユーザーベースのフィルタリング
        if self.blocked_users and author_name in self.blocked_users:
            return {
                'allowed': False,
                'reason': f'ブロックされたユーザー: {author_name}',
                'original': comment_data,
                'cleaned': ''
            }
        
        # 許可ユーザーリストがある場合、それ以外は拒否
        if self.allowed_users and author_name not in self.allowed_users:
            return {
                'allowed': False,
                'reason': f'許可リストにないユーザー: {author_name}',
                'original': comment_data,
                'cleaned': ''
            }
        
        # 2. 文字数チェック
        if len(message) < self.min_comment_length:
            return {
                'allowed': False,
                'reason': f'コメントが短すぎます（{len(message)}文字）',
                'original': comment_data,
                'cleaned': ''
            }
        
        if len(message) > self.max_comment_length:
            return {
                'allowed': False,
                'reason': f'コメントが長すぎます（{len(message)}文字）',
                'original': comment_data,
                'cleaned': ''
            }
        
        # 3. NGワードチェック
        message_lower = message.lower()
        for ng_word in self.ng_words:
            if self._check_ng_word_match(message_lower, ng_word.lower()):
                return {
                    'allowed': False,
                    'reason': f'NGワードを含んでいます: {ng_word}',
                    'original': comment_data,
                    'cleaned': ''
                }
        
        # 4. 正規表現パターンチェック
        for pattern in self.ng_patterns:
            if pattern.search(message):
                return {
                    'allowed': False,
                    'reason': f'不適切なパターンを含んでいます: {pattern.pattern}',
                    'original': comment_data,
                    'cleaned': ''
                }
        
        # 5. コメントのクリーニング
        cleaned_message = self._clean_message(message)
        
        return {
            'allowed': True,
            'reason': 'フィルタリング通過',
            'original': comment_data,
            'cleaned': cleaned_message
        }
    
    def _clean_message(self, message: str) -> str:
        """コメントメッセージのクリーニング"""
        # 余分な空白を削除
        cleaned = re.sub(r'\s+', ' ', message.strip())
        
        # 特殊文字の正規化
        cleaned = re.sub(r'[‼！]{2,}', '！', cleaned)
        cleaned = re.sub(r'[？?]{2,}', '？', cleaned)
        
        return cleaned
    
    def _check_ng_word_match(self, message_lower: str, ng_word_lower: str) -> bool:
        """NGワードマッチングのロジック（設定に応じて厳密さを調整）"""
        if self.strict_matching:
            # 厳密な部分一致（現在の動作）
            return ng_word_lower in message_lower
        elif self.word_boundary_checking:
            # 単語境界を考慮した部分一致（誤検知を減らす）
            import re
            # 日本語と英語の単語境界を考慮
            pattern = rf'(?:^|[^\w]){re.escape(ng_word_lower)}(?:[^\w]|$)'
            return bool(re.search(pattern, message_lower, re.IGNORECASE))
        else:
            # デフォルトは厳密な部分一致
            return ng_word_lower in message_lower
    
    def set_matching_mode(self, strict: bool = True, word_boundary: bool = False):
        """マッチングモードを設定"""
        self.strict_matching = strict
        self.word_boundary_checking = word_boundary
        if word_boundary:
            self.strict_matching = False  # 単語境界チェック時は厳密マッチを無効
        
        mode_desc = "厳密な部分一致" if strict else ("単語境界チェック" if word_boundary else "標準")
        print(f"[CommentFilter] マッチングモード: {mode_desc}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """フィルタリング設定の統計情報を取得"""
        matching_mode = "厳密な部分一致" if self.strict_matching else ("単語境界チェック" if self.word_boundary_checking else "標準")
        return {
            'ng_words_count': len(self.ng_words),
            'ng_patterns_count': len(self.ng_patterns),
            'allowed_users_count': len(self.allowed_users),
            'blocked_users_count': len(self.blocked_users),
            'min_length': self.min_comment_length,
            'max_length': self.max_comment_length,
            'matching_mode': matching_mode
        }
    
    def add_ng_word(self, word: str):
        """NGワードを動的に追加"""
        if word not in self.ng_words:
            self.ng_words.append(word)
    
    def remove_ng_word(self, word: str):
        """NGワードを削除"""
        if word in self.ng_words:
            self.ng_words.remove(word)
    
    def add_blocked_user(self, username: str):
        """ブロックユーザーを追加"""
        if username not in self.blocked_users:
            self.blocked_users.append(username)
    
    def remove_blocked_user(self, username: str):
        """ブロックユーザーを削除"""
        if username in self.blocked_users:
            self.blocked_users.remove(username)
    
    def reload_ng_words(self):
        """NGワードファイルを再読み込み"""
        print("[CommentFilter] NGワードファイルを再読み込み中...")
        
        # 基本的なNGワード
        default_ng_words = [
            "スパム", "宣伝", "広告", "アンチ", "荒らし",
            "死ね", "消えろ", "うざい", "きもい", "ブス",
            "詐欺", "騙", "違法", "犯罪", "殺"
        ]
        
        # 英語のNGワード
        english_ng_words = [
            "spam", "advertisement", "scam", "fake", "bot",
            "hate", "kill", "die", "stupid", "ugly"
        ]
        
        # ファイルからNGワードを再読み込み
        ng_words_from_file = self._load_ng_words_from_file()
        
        # NGワードリストを更新
        self.ng_words = default_ng_words + english_ng_words + ng_words_from_file
        print(f"[CommentFilter] NGワード再読み込み完了: 合計 {len(self.ng_words)} 個")


def create_default_filter_config(config_path: str):
    """デフォルトのフィルター設定ファイルを作成"""
    default_config = {
        "ng_words": [
            "カスタムNGワード1",
            "カスタムNGワード2"
        ],
        "allowed_users": [],
        "blocked_users": [
            "spam_user",
            "troll_user"
        ],
        "min_comment_length": 2,
        "max_comment_length": 150
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    print(f"Default filter config created at: {config_path}")


if __name__ == "__main__":
    # テスト用のコード
    filter_instance = CommentFilter()
    
    test_comments = [
        {"message": "こんにちは！", "author": {"name": "test_user"}},
        {"message": "スパムです", "author": {"name": "spam_user"}},
        {"message": "https://spam.com", "author": {"name": "url_user"}},
        {"message": "あああああああああ", "author": {"name": "repeat_user"}},
        {"message": "普通のコメントです", "author": {"name": "normal_user"}},
    ]
    
    print("=== Comment Filter Test ===")
    for comment in test_comments:
        result = filter_instance.filter_comment(comment)
        print(f"Message: {comment['message'][:20]}...")
        print(f"Allowed: {result['allowed']}")
        print(f"Reason: {result['reason']}")
        print("---")