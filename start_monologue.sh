#!/bin/bash

echo "🚀 AITuberぶつぶつシステム 起動中..."

# 既存のプロセスをチェック
EXISTING=$(ps aux | grep "python main.py" | grep -v grep)

if [ ! -z "$EXISTING" ]; then
    echo "⚠️  既に実行中のAITuberぶつぶつシステムが見つかりました:"
    echo "$EXISTING"
    echo ""
    read -p "既存のプロセスを停止して新しく起動しますか？ (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🛑 既存プロセスを停止中..."
        ./stop_monologue.sh
        sleep 2
    else
        echo "❌ 起動をキャンセルしました"
        exit 1
    fi
fi

# 引数のパース（テーマ指定など）
ARGS=""
if [ ! -z "$1" ]; then
    if [ "$1" = "--theme" ] && [ ! -z "$2" ]; then
        ARGS="--theme $2"
        echo "🎨 テーマ: $2"
    fi
fi

echo "📋 実行コマンド: python main.py $ARGS"
echo "💡 停止方法:"
echo "   - 別ターミナルで: ./stop_monologue.sh"
echo "   - またはプロセス強制終了: pkill -f 'python main.py'"
echo ""
echo "🎬 開始します（ログが表示されます）..."
echo "=================================================="

# バックグラウンドで実行し、プロセスIDを記録
nohup python main.py $ARGS > monologue.log 2>&1 &
MAIN_PID=$!

echo "✅ AITuberぶつぶつシステム が起動しました (PID: $MAIN_PID)"
echo "📄 ログファイル: monologue.log"
echo "🛑 停止コマンド: ./stop_monologue.sh"

# ログの最初の部分を表示
sleep 2
echo ""
echo "📊 起動ログ (最初の20行):"
echo "------------------------------------------------"
tail -20 monologue.log 2>/dev/null || echo "ログファイルの読み込み待機中..."

echo ""
echo "🎉 起動完了！リアルタイムログを見るには: tail -f monologue.log" 