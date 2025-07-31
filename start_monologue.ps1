# AITuberぶつぶつシステム 起動スクリプト
Write-Host "🚀 AITuberぶつぶつシステム 起動中..."

# 既存のプロセスをチェック
$existing = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%python%main.py%'"
if ($existing) {
    Write-Host "⚠️  既に実行中のAITuberぶつぶつシステムが見つかりました:"
    $existing | Select-Object ProcessId, CommandLine | Format-Table
    Write-Host ""
    $reply = Read-Host "既存のプロセスを停止して新しく起動しますか？ (y/N)"
    if ($reply -match "^[Yy]$") {
        Write-Host "🛑 既存プロセスを停止中..."
        # stop_monologue.ps1はジョブを停止できないため、プロセスIDで直接停止する
        $existing | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Write-Host "✅ 既存プロセスを停止しました。"
        Start-Sleep -Seconds 2
    } else {
        Write-Host "❌ 起動をキャンセルしました"
        exit 1
    }
}

# 引数のパース（テーマ指定など）
$command = "poetry"
$argumentList = @("run", "python", "main.py")
if ($args.Count -ge 2 -and $args[0] -eq "--theme") {
    $theme = $args[1]
    $argumentList += "--theme", $theme
    Write-Host "🎨 テーマ: $theme"
}

$fullCommand = "$command $($argumentList -join ' ')"
Write-Host "📋 実行コマンド: $fullCommand"
Write-Host "💡 停止方法:"
Write-Host "   - 別ターミナルで: .\stop_monologue.ps1"
Write-Host ""
Write-Host "🎬 開始します（ログが表示されます）..."
Write-Host "=================================================="

# バックグラウンドジョブとして実行し、出力をリダイレクト
$logFile = "monologue.log"
$scriptBlock = [scriptblock]::Create("$fullCommand *>&1 | Tee-Object -FilePath $logFile -Append")
$job = Start-Job -ScriptBlock $scriptBlock

Write-Host "✅ AITuberぶつぶつシステム がジョブとして起動しました (Job ID: $($job.Id))"
Write-Host "📄 ログファイル: $logFile"
Write-Host "🛑 停止コマンド: .\stop_monologue.ps1"

# ログの最後の部分を表示
Start-Sleep -Seconds 3 # ジョブの開始とログファイルへの書き込みを少し待つ
Write-Host ""
Write-Host "📊 起動ログ (最後の20行):"
Write-Host "------------------------------------------------"
if (Test-Path $logFile) {
    try {
        Get-Content -Path $logFile -Last 20 -ErrorAction Stop
    } catch {
        Write-Host "ログファイルは存在しますが、まだ内容がありません。"
    }
} else {
    Write-Host "ログファイルの生成を待機中..."
}

Write-Host ""
Write-Host "🎉 起動完了！リアルタイムログを見るには: Get-Content $logFile -Wait"
Write-Host "   ジョブの状態を確認するには: Get-Job"
Write-Host "   ジョブを停止するには: Stop-Job -Id $($job.Id)" 