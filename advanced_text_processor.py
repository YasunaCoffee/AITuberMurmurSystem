import re
from typing import List, Optional, Tuple
import logging

from config import config # 修正: get_configではなくconfigを直接インポート

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 新しい、より安全な実装 ---

# 設定を一度だけ読み込む
# 修正: configオブジェクトから属性として直接アクセス
text_processing_config = config.text_processing
MAX_LENGTH = text_processing_config.max_length
MIN_MERGE_LENGTH = text_processing_config.min_merge_length

# 区切り文字の正規表現をより安全なものに
SENTENCE_DELIMITERS = re.compile(r'[。？！\n]')

def process_comment_response_text(text: str) -> List[str]:
    """
    LLMが生成した応答テキストを、音声合成に適した短い文に分割する。
    URLなどの特殊な形式を保護し、安全な分割処理を行う。
    """
    # 1. URLを一時的にプレースホルダーに置換
    urls = re.findall(r'https?://\S+', text)
    for i, url in enumerate(urls):
        text = text.replace(url, f"__URL_{i}__")

    # 2. 基本的な分割
    segments = SENTENCE_DELIMITERS.split(text)
    
    # 3. 各セグメントを処理
    processed_segments = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        
        # 長すぎるセグメントをさらに分割
        if len(segment) > MAX_LENGTH:
            processed_segments.extend(_split_long_sentence(segment, MAX_LENGTH))
        else:
            processed_segments.append(segment)

    # 4. 短いセグメントを結合
    merged_segments = _merge_short_segments(processed_segments, MIN_MERGE_LENGTH)

    # 5. URLを元に戻す
    final_segments = []
    for segment in merged_segments:
        for i, url in enumerate(urls):
            segment = segment.replace(f"__URL_{i}__", url)
        final_segments.append(segment)
    
    if not final_segments:
        logger.warning(f"テキスト処理の結果、空のリストが生成されました。入力: '{text}'")
        return []
    
    return final_segments

def _split_long_sentence(sentence: str, max_len: int) -> List[str]:
    """長文を句読点や括弧を考慮して分割する"""
    parts = []
    current_pos = 0
    while len(sentence) - current_pos > max_len:
        split_pos = -1
        # 読点、スペース、括弧の終わりなどを分割候補とする
        delimiters = [',', '、', ' ', ']', '』', '）']
        for delim in delimiters:
            pos = sentence.rfind(delim, current_pos, current_pos + max_len)
            if pos > split_pos:
                split_pos = pos
        
        if split_pos == -1 or split_pos <= current_pos:
            # 区切り文字が見つからなければ、強制的に分割
            split_pos = current_pos + max_len
        
        parts.append(sentence[current_pos:split_pos + 1].strip())
        current_pos = split_pos + 1
        
    remaining = sentence[current_pos:].strip()
    if remaining:
        parts.append(remaining)
    return parts

def _merge_short_segments(segments: List[str], min_len: int) -> List[str]:
    """短いセグメントを前のセグメントと結合する"""
    if not segments:
        return []
    
    merged = [segments[0]]
    for i in range(1, len(segments)):
        # 前のセグメントが短く、かつ現在のセグメントも長すぎない場合
        if len(merged[-1]) < min_len and len(merged[-1]) + len(segments[i]) < MAX_LENGTH:
            merged[-1] += " " + segments[i]
        else:
            merged.append(segments[i])
    return merged

# --- 古い、問題のあった実装はすべて削除 ---