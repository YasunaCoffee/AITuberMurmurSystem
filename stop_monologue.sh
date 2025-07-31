#!/bin/bash

# コマンドライン引数チェック
FORCE_MODE=false
if [ "$1" = "-f" ] || [ "$1" = "--force" ]; then
    FORCE_MODE=true
    echo "🔥 AITuberぶつぶつシステム 強制停止中..."
else
    echo "🛑 AITuberぶつぶつシステム 停止中（終了挨拶付き）..."
    echo "💡 即座に停止したい場合: $0 --force"
fi

# プロセスを検索して表示
PROCESSES=$(ps aux | grep "python main.py" | grep -v grep)

if [ -z "$PROCESSES" ]; then
    echo "❌ 実行中のMonologue Agentが見つかりません"
    exit 1
fi

echo "📋 実行中のプロセス:"
echo "$PROCESSES"

# プロセスIDを取得
PIDS=$(echo "$PROCESSES" | awk '{print $2}')

# 各プロセスに対して停止処理
for PID in $PIDS; do
    echo "⏹️  プロセス $PID を停止中..."
    
    if [ "$FORCE_MODE" = true ]; then
        # 強制モード: 即座に終了
        echo "🔥 強制終了を実行中..."
        kill -9 $PID 2>/dev/null
        sleep 1
        if kill -0 $PID 2>/dev/null; then
            echo "❌ プロセス $PID の停止に失敗しました"
        else
            echo "✅ プロセス $PID を強制終了しました"
        fi
    else
        # 通常モード: 終了挨拶付き
        echo "🎙️  終了の挨拶を開始します..."
        
        # ファイルベースの終了リクエストを作成
        echo "graceful_shutdown_request" > shutdown_request.txt
        echo "📝 終了リクエストファイルを作成しました"
        
        # 念のため、シグナルも送信
        kill -INT $PID 2>/dev/null
        sleep 1
        kill -INT $PID 2>/dev/null
        
        # 終了処理完了を待機（タイムアウトなし）
        echo "⏳ 終了処理を待機中（自然な完了まで無制限待機）..."
        echo "🎙️  現在の音声完了後、終了挨拶を開始します..."
        echo "💡 強制停止したい場合は別ターミナルで: $0 --force"
        
        counter=0
        while kill -0 $PID 2>/dev/null; do
            counter=$((counter + 1))
            
            # 15秒毎に進捗を表示
            if [ $((counter % 15)) -eq 0 ]; then
                echo "⏱️  ${counter}秒経過: 終了処理継続中..."
            fi
            
            sleep 1
        done
        
        echo "✅ プロセス $PID が正常に終了しました（${counter}秒で完了）"
        
        # 終了後にサマリーを生成
        echo "📊 配信サマリーを生成中..."
        python3 -c "
from v2.handlers.stream_summary_handler import StreamSummaryHandler
from v2.core.event_queue import EventQueue
from v2.core.events import PrepareStreamSummary
import time

# イベントキューを作成
event_queue = EventQueue()

# StreamSummaryHandlerを初期化
handler = StreamSummaryHandler(event_queue)

# サマリー生成コマンドを作成
command = PrepareStreamSummary(task_id='shutdown_summary')

# サマリー生成を実行
handler.handle_prepare_stream_summary(command)

# 完了まで待機（簡易実装）
print('配信サマリー生成を開始しました...')
time.sleep(5)  # 処理完了を待機
print('配信サマリー生成が完了しました。')
"
    fi
done


if [ "$FORCE_MODE" = true ]; then
    echo "🎉 AITuberぶつぶつシステム の強制停止が完了しました！"
else
    echo "🎉 AITuberぶつぶつシステム の停止処理が完了しました！"
    echo "🎙️  ぶつぶつ語りの終了挨拶をお聞きいただき、ありがとうございました。"
fi 