# WSL install via SYSTEM task v2 - avoid pipe chars in remote cmd (SSH default shell = cmd).
$ErrorActionPreference = 'Continue'
$log = 'C:\Users\lenovo\wsl_install_progress.log'
Remove-Item $log -ErrorAction SilentlyContinue

$setup = @'
$log = 'C:\Users\lenovo\wsl_install_progress.log'
function L($m) { $t = Get-Date -Format 'HH:mm:ss'; "$t $m" | Out-File $log -Append ascii }
L 'SYSTEM v2: starting wsl --install -d Ubuntu (generic name)'
$env:WSL_UTF8 = '1'
wsl --install -d Ubuntu --no-launch > C:\Users\lenovo\wsl_install_raw.log 2>&1
L ("SYSTEM: exit=" + $LASTEXITCODE)
Get-Content C:\Users\lenovo\wsl_install_raw.log -ErrorAction SilentlyContinue | Out-File $log -Append ascii
$st = wsl --status > C:\Users\lenovo\wsl_status.log 2>&1
L 'SYSTEM done'
'@
$setup | Out-File 'C:\Users\lenovo\wsl_setup_task.ps1' -Encoding ascii

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\Users\lenovo\wsl_setup_task.ps1'
Register-ScheduledTask -TaskName 'WSL_Install2' -Action $action -RunLevel Highest -User 'SYSTEM' -Force | Out-Null
Start-ScheduledTask -TaskName 'WSL_Install2'

$deadline = (Get-Date).AddSeconds(300)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    $last = Get-Content $log -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($last -match 'SYSTEM done') { break }
}
Unregister-ScheduledTask -TaskName 'WSL_Install2' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host '=== LOG ==='
Get-Content $log -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
