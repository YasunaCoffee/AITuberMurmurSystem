import queue
from typing import Union

from v2.core.events import Event, Command

# Type hint for items that can be put in the queue
QueueItem = Union[Event, Command]


class EventQueue:
    def __init__(self):
        self._queue = queue.Queue()

    def put(self, item: QueueItem):
        """イベントまたはコマンドをキューに追加する。"""
        self._queue.put(item)

    def get(self, block=True, timeout=None) -> QueueItem:
        """キューからイベントまたはコマンドを取得する。
        blockとtimeout引数をサポート。
        """
        return self._queue.get(block=block, timeout=timeout)

    def get_nowait(self) -> QueueItem:
        """キューからイベントまたはコマンドをノンブロッキングで取得する。
        キューが空の場合は queue.Empty 例外が発生する。
        """
        return self._queue.get_nowait()

    def empty(self) -> bool:
        """キューが空かどうかを返す。"""
        return self._queue.empty()

    def qsize(self) -> int:
        """キューのサイズを返す。"""
        return self._queue.qsize() 