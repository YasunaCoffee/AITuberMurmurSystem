# AITuberぶつぶつシステムを優雅に停止（終了挨拶付き）
Write-Host "🛑 AITuberぶつぶつシステムを優雅に停止します..."

# pythonプロセスを検索（より厳密にフィルタリング）
$allPythonProcesses = Get-Process | Where-Object { $_.ProcessName -eq "python" }
$processes = @()

# monologueに関連するプロセスのみを対象にする
foreach ($process in $allPythonProcesses) {
    try {
        # プロセスのコマンドラインを確認（可能な場合）
        $commandLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($process.Id)").CommandLine
        if ($commandLine -like "*main.py*" -or $commandLine -like "*monologue*") {
            $processes += $process
        } elseif ($process.StartTime -gt (Get-Date).AddMinutes(-10)) {
            # 最近10分以内に開始されたプロセスも対象に含める（フォールバック）
            $processes += $process
        }
    } catch {
        # WMI取得に失敗した場合は、最近のプロセスなら対象に含める
        if ($process.StartTime -gt (Get-Date).AddMinutes(-10)) {
            $processes += $process
        }
    }
}

if ($processes.Count -eq 0) {
    Write-Host "⚠️ 実行中のAITuberぶつぶつシステムが見つかりませんでした"
    return
}

Write-Host "📝 グレースフルシャットダウンを開始します（終了挨拶が再生されます）..."

# 対象プロセスのIDを記録
$targetProcessIds = @()
Write-Host "🎯 対象プロセス:"
foreach ($process in $processes) {
    $targetProcessIds += $process.Id
    Write-Host "   - PID $($process.Id) (開始時刻: $($process.StartTime))"
}

# シャットダウンリクエストファイルを作成
$shutdownFile = "shutdown_request.txt"
try {
    Set-Content -Path $shutdownFile -Value "$(Get-Date): Graceful shutdown requested" -Encoding UTF8
    Write-Host "✅ シャットダウンリクエストファイルを作成しました: $shutdownFile"
} catch {
    Write-Host "❌ シャットダウンリクエストファイルの作成に失敗しました: $_" -ForegroundColor Red
    Write-Host "⚠️ 強制終了に切り替えます..." -ForegroundColor Yellow
    
    # フォールバック: 強制終了
    foreach ($processId in $targetProcessIds) {
        try {
            Write-Host "強制停止中のプロセス: PID $processId"
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "⚠️ プロセス (PID: $processId) の停止中にエラーが発生しました: $_" -ForegroundColor Yellow
        }
    }
    Write-Host "✅ 強制停止完了"
    return
}

Write-Host "⏳ 終了挨拶の再生と音声キューの完了を待機中..."
Write-Host "   （最大10分間待機、その後強制終了します）"

# プロセス監視のための変数
$checkInterval = 3
$elapsedTime = 0
$maxWaitTime = 600  # 最大10分に短縮（より実用的）
$lastRunningCount = $targetProcessIds.Count
$lastStatusTime = 0
$statusInterval = 15  # 15秒ごとに状況を報告

while ($elapsedTime -lt $maxWaitTime) {
    # 対象プロセスがまだ実行中かチェック
    $runningProcessIds = @()
    foreach ($processId in $targetProcessIds) {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            $runningProcessIds += $processId
        }
    }
    
    if ($runningProcessIds.Count -eq 0) {
        Write-Host ""
        Write-Host "✅ 対象プロセスがすべて正常に終了しました (経過時間: $elapsedTime 秒)"
        break
    }
    
    # 定期的に状況を報告
    if (($elapsedTime - $lastStatusTime) -ge $statusInterval) {
        $currentRunningCount = $runningProcessIds.Count
        $remainingTime = $maxWaitTime - $elapsedTime
        Write-Host ""
        Write-Host "📊 状況報告 (経過時間: $elapsedTime 秒, 残り: $remainingTime 秒):"
        Write-Host "   - 実行中の対象プロセス: $currentRunningCount / $($targetProcessIds.Count) 個"
        
        if ($currentRunningCount -ne $lastRunningCount) {
            Write-Host "   - プロセス数が変化しました ($lastRunningCount → $currentRunningCount)"
            $lastRunningCount = $currentRunningCount
        }
        
        # 実行中のプロセスIDを表示
        if ($runningProcessIds.Count -gt 0) {
            Write-Host "   - 実行中PID: $($runningProcessIds -join ', ')"
        }
        
        Write-Host "   - 音声キューの完了を待機中..."
        $lastStatusTime = $elapsedTime
    } else {
        # 通常の待機表示（改行なし）
        Write-Host "." -NoNewline
    }
    
    Start-Sleep -Seconds $checkInterval
    $elapsedTime += $checkInterval
}

# タイムアウト後に対象プロセスがまだ実行中の場合
$finalRunningIds = @()
foreach ($processId in $targetProcessIds) {
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        $finalRunningIds += $processId
    }
}

if ($finalRunningIds.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️ 最大待機時間 ($maxWaitTime 秒) に達しました" -ForegroundColor Yellow
    Write-Host "🔨 残りの対象プロセスを強制終了します..."
    
    foreach ($processId in $finalRunningIds) {
        try {
            Write-Host "強制停止中のプロセス: PID $processId"
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            
            # プロセスが完全に終了するのを待機
            $retryCount = 0
            while (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
                Start-Sleep -Milliseconds 100
                $retryCount++
                if ($retryCount -gt 50) { # 5秒でタイムアウト
                    Write-Host "⚠️ プロセス (PID: $processId) の停止がタイムアウトしました" -ForegroundColor Yellow
                    break
                }
            }
        } catch {
            Write-Host "⚠️ プロセス (PID: $processId) の停止中にエラーが発生しました: $_" -ForegroundColor Yellow
        }
    }
    Write-Host "✅ 強制停止完了"
} else {
    Write-Host ""
    Write-Host "🎉 AITuberぶつぶつシステムが正常に終了しました"
    Write-Host "   すべての音声キューが完了し、終了挨拶が正常に再生されました"
}

# シャットダウンリクエストファイルをクリーンアップ
if (Test-Path $shutdownFile) {
    try {
        Remove-Item $shutdownFile -Force
        Write-Host "🧹 シャットダウンリクエストファイルを削除しました"
    } catch {
        Write-Host "⚠️ シャットダウンリクエストファイルの削除に失敗しました: $_" -ForegroundColor Yellow
    }
}

Write-Host "✅ 停止完了" 