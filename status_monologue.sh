#!/bin/bash

echo "📊 AITuberぶつぶつシステム ステータス確認"
echo "=================================="

# プロセス状況確認
PROCESSES=$(ps aux | grep "python main.py" | grep -v grep)

if [ -z "$PROCESSES" ]; then
    echo "🔴 ステータス: 停止中"
    echo ""
    echo "🚀 起動方法: ./start_monologue.sh"
else
    echo "🟢 ステータス: 実行中"
    echo ""
    echo "📋 実行中のプロセス:"
    echo "$PROCESSES"
    echo ""
    
    # メモリ使用量とCPU使用率を表示
    echo "💾 リソース使用状況:"
    echo "$PROCESSES" | awk '{printf "   CPU: %s%%  メモリ: %s%%  PID: %s\n", $3, $4, $2}'
    echo ""
    
    # ログファイルの状況
    if [ -f "monologue.log" ]; then
        LOG_SIZE=$(du -h monologue.log | cut -f1)
        LOG_LINES=$(wc -l < monologue.log)
        echo "📄 ログファイル状況:"
        echo "   ファイル: monologue.log"
        echo "   サイズ: $LOG_SIZE"
        echo "   行数: $LOG_LINES 行"
        echo ""
        
        echo "📝 最新ログ (最後の5行):"
        echo "----------------------------------------"
        tail -5 monologue.log 2>/dev/null || echo "   ログ読み込みエラー"
        echo "----------------------------------------"
    else
        echo "📄 ログファイル: 見つかりません"
    fi
    
    echo ""
    echo "🛑 停止方法:"
    echo "   - 終了挨拶付き: ./stop_monologue.sh"
    echo "   - 即座に停止: ./stop_monologue.sh --force"
    echo "📄 ログ監視: tail -f monologue.log"
fi

echo ""
echo "🔧 利用可能なコマンド:"
echo "   ./start_monologue.sh        - アプリ起動"
echo "   ./stop_monologue.sh         - 終了挨拶付きで停止"
echo "   ./stop_monologue.sh --force - 即座に強制停止"
echo "   ./status_monologue.sh       - ステータス確認"
echo "   tail -f monologue.log       - リアルタイムログ" 