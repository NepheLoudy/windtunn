# ============================================================
#  fix6.ps1 -- ASCII source / UTF8 report.
#  Windows OpenSSH refuses host keys that are "too open":
#  owner must be Administrators/SYSTEM and only SYSTEM+Admins in DACL.
#  ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$sep  = [string][char]92
$out  = $here + $sep + 'fix6.txt'
Set-Content -Path $out -Value @("=== fix6  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding UTF8
function L($m) { Add-Content -Path $out -Value $m -Encoding UTF8; Write-Host $m }

$pd  = 'C:\ProgramData\ssh'
$sys = 'C:\Windows\System32\OpenSSH'
$sysd = $sys + $sep + 'sshd.exe'

L ("elevated : " + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))

# reset leftovers
& schtasks /delete /tn sshd_task /f 2>&1 | Out-Null
& sc.exe stop sshd 2>&1 | Out-Null
Get-Process sshd -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

L ''
L '--- 1. ACL/owner BEFORE ---'
(& icacls $pd 2>&1) | ForEach-Object { L ('  ' + $_) }
$keys = @(Get-ChildItem $pd -Filter 'ssh_host_*_key' -File -ErrorAction SilentlyContinue)
foreach ($k in $keys) {
    $o = (Get-Acl $k.FullName).Owner
    L ('  ' + $k.Name + '   owner=' + $o)
    (& icacls $k.FullName 2>&1) | ForEach-Object { L ('      ' + $_) }
}

L ''
L '--- 2. fix owner + DACL ---'
(& icacls $pd /setowner '*S-1-5-32-544' 2>&1) | ForEach-Object { L ('  dir  ' + $_) }
(& icacls $pd /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' /grant:r '*S-1-5-32-544:(OI)(CI)F' 2>&1) | ForEach-Object { L ('  dir  ' + $_) }
foreach ($k in $keys) {
    (& icacls $k.FullName /setowner '*S-1-5-32-544' 2>&1) | ForEach-Object { L ('  ' + $k.Name + ' ' + $_) }
    (& icacls $k.FullName /inheritance:r /grant:r '*S-1-5-18:F' /grant:r '*S-1-5-32-544:F' 2>&1) | ForEach-Object { L ('  ' + $k.Name + ' ' + $_) }
}

L ''
L '--- 3. ACL/owner AFTER ---'
foreach ($k in $keys) {
    $o = (Get-Acl $k.FullName).Owner
    L ('  ' + $k.Name + '   owner=' + $o)
}
if ($keys.Count -gt 0) { (& icacls ($keys[0].FullName) 2>&1) | ForEach-Object { L ('  sample: ' + $_) } }

L ''
L '--- 4. start service ---'
(& sc.exe start sshd 2>&1) | ForEach-Object { L ('  ' + $_) }
Start-Sleep -Seconds 5
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
L ('  port 22 : ' + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))
$svc = Get-Service sshd -ErrorAction SilentlyContinue
L ('  service : ' + $(if ($svc) { $svc.Status } else { 'missing' }))

# ---------- 5. still dead -> capture sshd stderr as SYSTEM again ----------
if ($listen.Count -eq 0) {
    L ''
    L '--- 5. regenerate host keys AS SYSTEM, then start ---'
    Get-ChildItem $pd -Filter 'ssh_host_*_key*' -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    $klog = 'D:' + $sep + 'keygen_run.txt'
    Remove-Item $klog -ErrorAction SilentlyContinue
    $argLine = '/c ""' + $sys + $sep + 'ssh-keygen.exe" -A >> ' + $klog + ' 2>&1"'
    try {
        $a = New-ScheduledTaskAction -Execute 'C:\Windows\System32\cmd.exe' -Argument $argLine
        $p = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName 'ssh_keygen' -Action $a -Principal $p -Force -ErrorAction Stop | Out-Null
        Start-ScheduledTask -TaskName 'ssh_keygen' -ErrorAction Stop
        Start-Sleep -Seconds 6
        & schtasks /delete /tn ssh_keygen /f 2>&1 | Out-Null
        if (Test-Path $klog) { Get-Content $klog | ForEach-Object { L ('  keygen: ' + $_) } }
    } catch { L ('  keygen task failed: ' + $_.Exception.Message) }
    $keys2 = @(Get-ChildItem $pd -Filter 'ssh_host_*_key' -File -ErrorAction SilentlyContinue)
    L ('  keys now: ' + ($(if ($keys2.Count) { ($keys2 | ForEach-Object { $_.Name + ' owner=' + (Get-Acl $_.FullName).Owner }) -join ' | ' } else { 'NONE' })))

    L ''
    L '--- 6. start again ---'
    (& sc.exe start sshd 2>&1) | ForEach-Object { L ('  ' + $_) }
    Start-Sleep -Seconds 5
    $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
    L ('  port 22 : ' + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))

    if ($listen.Count -eq 0) {
        L ''
        L '--- 7. capture sshd stderr under SYSTEM ---'
        $rlog = 'D:' + $sep + 'sshd_run2.txt'
        Remove-Item $rlog -ErrorAction SilentlyContinue
        $argLine2 = '/c ""' + $sysd + '" -D -d -e >> ' + $rlog + ' 2>&1"'
        try {
            $a2 = New-ScheduledTaskAction -Execute 'C:\Windows\System32\cmd.exe' -Argument $argLine2
            $p2 = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
            Register-ScheduledTask -TaskName 'sshd_probe' -Action $a2 -Principal $p2 -Force -ErrorAction Stop | Out-Null
            Start-ScheduledTask -TaskName 'sshd_probe' -ErrorAction Stop
            Start-Sleep -Seconds 7
            & schtasks /delete /tn sshd_probe /f 2>&1 | Out-Null
            Get-Process sshd -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            if (Test-Path $rlog) { Get-Content $rlog | Select-Object -Last 30 | ForEach-Object { L ('  ' + $_) } }
        } catch { L ('  probe failed: ' + $_.Exception.Message) }
        $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
    }
}

L ''
L '--- 8. final ---'
$svc = Get-Service sshd -ErrorAction SilentlyContinue
L ('  service : ' + $(if ($svc) { $svc.Status } else { 'missing' }))
L ('  port 22 : ' + $(if ($listen.Count) { 'LISTENING' } else { 'no listener' }))
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ('  ' + $_.IPAddress + '/' + $_.PrefixLength + '  [' + $_.InterfaceAlias + ']') }
L ''
if ($listen.Count) { L '*** SSH READY ***' } else { L '*** STILL FAILED ***' }
