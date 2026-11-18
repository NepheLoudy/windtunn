# ============================================================
#  fix5.ps1 -- ASCII source / UTF8 report.
#  Run sshd as SYSTEM with stdout+stderr redirected to a file.
#  This both (a) reveals the session-0 crash reason and
#  (b) doubles as a persistent workaround if it stays up.
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$sep  = [string][char]92
$out  = $here + $sep + 'fix5.txt'
$run  = 'D:' + $sep + 'sshd_run.txt'
Set-Content -Path $out -Value @("=== fix5  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding UTF8
function L($m) { Add-Content -Path $out -Value $m -Encoding UTF8; Write-Host $m }

L ("elevated : " + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))

# clean previous state
& schtasks /delete /tn sshd_task /f 2>&1 | Out-Null
& sc.exe stop sshd 2>&1 | Out-Null
Get-Process sshd -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item $run -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# task: cmd.exe /c ""<sshd>" -D -d -e >> D:\sshd_run.txt 2>&1"
$cmdArg = '/c ""C:\Windows\System32\OpenSSH\sshd.exe" -D -d -e >> ' + $run + ' 2>&1"'
L ''
L '--- registering task ---'
L ("  arg = " + $cmdArg)
try {
    $act = New-ScheduledTaskAction -Execute 'C:\Windows\System32\cmd.exe' -Argument $cmdArg
    $trg = New-ScheduledTaskTrigger -AtStartup
    $prn = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName 'sshd_task' -Action $act -Trigger $trg -Principal $prn -Settings $set -Force -ErrorAction Stop | Out-Null
    L '  registered'
    Start-ScheduledTask -TaskName 'sshd_task' -ErrorAction Stop
    L '  started'
} catch { L ('  FAILED: ' + $_.Exception.Message) }

Start-Sleep -Seconds 6
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
L ('  port 22 : ' + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))

if ($listen.Count -eq 0) {
    Start-Sleep -Seconds 4
    $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
    L ('  port 22 (retry) : ' + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))
}

L ''
L '--- sshd output captured under SYSTEM ---'
if (Test-Path $run) {
    L ('  size = ' + (Get-Item $run).Length)
    Get-Content $run -ErrorAction SilentlyContinue | Select-Object -Last 40 | ForEach-Object { L ('  ' + $_) }
} else { L '  (no output file - process never even started)' }

L ''
L '--- task state ---'
try {
    $t = Get-ScheduledTask -TaskName 'sshd_task' -ErrorAction Stop
    $i = Get-ScheduledTaskInfo -TaskName 'sshd_task' -ErrorAction Stop
    L ('  state=' + $t.State + '  lastResult=' + $i.LastTaskResult + '  lastRun=' + $i.LastRunTime)
} catch { L ('  ' + $_.Exception.Message) }
Get-Process sshd -ErrorAction SilentlyContinue | ForEach-Object { L ('  sshd pid=' + $_.Id) }

L ''
L '--- final ---'
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ('  ' + $_.IPAddress + '/' + $_.PrefixLength + '  [' + $_.InterfaceAlias + ']') }
L ''
if ($listen.Count) { L '*** SSH READY ***' } else { L '*** STILL FAILED ***' }
