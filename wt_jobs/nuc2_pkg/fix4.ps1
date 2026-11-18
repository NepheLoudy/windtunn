# ============================================================
#  fix4.ps1 -- ASCII source, UTF8 report. Port 22 is the goal.
#  1) capture why the sshd SERVICE dies   2) fallback: scheduled task
#  Report: fix4.txt (UTF-8)
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$sep  = [string][char]92
$out  = $here + $sep + 'fix4.txt'
Set-Content -Path $out -Value @("=== fix4  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding UTF8
function L($m) { Add-Content -Path $out -Value $m -Encoding UTF8; Write-Host $m }

$sysd = 'C:\Windows\System32\OpenSSH\sshd.exe'
$pd   = 'C:\ProgramData\ssh'

L ("elevated : " + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
L ("OS build : " + [Environment]::OSVersion.Version)

# ---------- 1. service attempt, watch it die ----------
L ''
L '--- 1. service start, 12 s watch ---'
(& sc.exe stop sshd 2>&1) | Out-Null
Start-Sleep -Seconds 2
(& sc.exe start sshd 2>&1) | ForEach-Object { L ("  " + $_) }
for ($i = 1; $i -le 6; $i++) {
    Start-Sleep -Seconds 2
    $s = (Get-Service sshd -ErrorAction SilentlyContinue)
    $p = @(Get-Process sshd -ErrorAction SilentlyContinue)
    L ("  t+{0,2}s : service={1}  processes={2}" -f ($i * 2), $(if ($s) { $s.Status } else { 'missing' }), $p.Count)
    if ($p.Count -gt 0) { L ("           pid=" + (($p | ForEach-Object { $_.Id }) -join ',')) }
}
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
L ("  port 22 : " + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))

# ---------- 2. why did it die ----------
if ($listen.Count -eq 0) {
    L ''
    L '--- 2. Service Control Manager events, last 15 min ---'
    try {
        Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = (Get-Date).AddMinutes(-15) } -ErrorAction Stop |
            Where-Object { $_.ProviderName -like '*Service Control Manager*' -or $_.ProviderName -like '*OpenSSH*' } |
            Select-Object -First 20 |
            ForEach-Object { L ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] id=" + $_.Id + "  " + $_.Message) }
    } catch { L ("  (log: " + $_.Exception.Message + ")") }

    L ''
    L '--- 3. OpenSSH operational log ---'
    try {
        Get-WinEvent -LogName 'Microsoft-Windows-OpenSSH/Operational' -MaxEvents 15 -ErrorAction Stop |
            ForEach-Object { L ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] " + $_.Message) }
    } catch { L ("  (no OpenSSH log: " + $_.Exception.Message + ")") }

    L ''
    L '--- 4. sshd log dir ---'
    $ld = $pd + $sep + 'logs'
    if (Test-Path $ld) {
        Get-ChildItem $ld -ErrorAction SilentlyContinue | ForEach-Object {
            L ("  --- " + $_.Name)
            Get-Content $_.FullName -Tail 25 | ForEach-Object { L ("    " + $_) }
        }
    } else { L '  no logs dir' }
}

# ---------- 5. fallback: scheduled task running sshd -D as SYSTEM ----------
if ($listen.Count -eq 0) {
    L ''
    L '--- 5. fallback: scheduled task sshd_task (SYSTEM, at startup) ---'
    try {
        & schtasks /delete /tn sshd_task /f 2>&1 | Out-Null
        $act = New-ScheduledTaskAction -Execute $sysd -Argument '-D'
        $trg = New-ScheduledTaskTrigger -AtStartup
        $prn = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
        Register-ScheduledTask -TaskName 'sshd_task' -Action $act -Trigger $trg -Principal $prn -Settings $set -Force -ErrorAction Stop | Out-Null
        L '  task registered'
        Start-ScheduledTask -TaskName 'sshd_task' -ErrorAction Stop
        L '  task started'
        Start-Sleep -Seconds 5
        $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
        L ("  port 22 after task : " + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))
        $ti = Get-ScheduledTaskInfo -TaskName 'sshd_task' -ErrorAction SilentlyContinue
        if ($ti) { L ("  task last result   : " + $ti.LastTaskResult) }
        Get-Process sshd -ErrorAction SilentlyContinue | ForEach-Object { L ("  sshd pid " + $_.Id) }
    } catch { L ("  task fallback failed: " + $_.Exception.Message) }
}

# ---------- 6. final ----------
L ''
L '--- 6. final ---'
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
$svc = Get-Service sshd -ErrorAction SilentlyContinue
L ("  service : " + $(if ($svc) { $svc.Status } else { 'missing' }))
L ("  port 22 : " + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))
L ''
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ('  ' + $_.IPAddress + '/' + $_.PrefixLength + '  [' + $_.InterfaceAlias + ']') }
L ''
if ($listen.Count) { L '*** SSH READY ***' } else { L '*** STILL FAILED ***' }
