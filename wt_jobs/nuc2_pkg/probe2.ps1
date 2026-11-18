# ============================================================
#  probe2.ps1 -- ASCII only. Why does sshd.exe die instantly?
#  Report: <script dir>\probe2.txt
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$out  = Join-Path $here 'probe2.txt'
Set-Content -Path $out -Value @("=== probe2  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding ASCII
function L($m) { Add-Content -Path $out -Value $m -Encoding ASCII; Write-Host $m }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
L ("elevated : " + $isAdmin)

$sshd = 'C:\OpenSSH\sshd.exe'
L ''
L '--- 1. binary integrity ---'
if (Test-Path $sshd) {
    $i = Get-Item $sshd
    L ("  size      : " + $i.Length + "   (expect 1336832)")
    L ("  md5       : " + (Get-FileHash $sshd -Algorithm MD5).Hash)
    L ("  version   : " + $i.VersionInfo.FileVersion + " / " + $i.VersionInfo.ProductVersion)
    L ("  signature : " + (Get-AuthenticodeSignature $sshd).Status)
    L ("  alt stream: " + (@(Get-Item $sshd -Stream * -ErrorAction SilentlyContinue | ForEach-Object { $_.Stream }) -join ','))
} else { L '  MISSING' }

L ''
L '--- 2. can it even run? ---'
$o = & $sshd -h 2>&1 | Out-String
L ("  sshd -h output: [" + $o.Trim() + "]")
L ("  LASTEXITCODE  : " + $LASTEXITCODE)
$o2 = & 'C:\OpenSSH\ssh.exe' -V 2>&1 | Out-String
L ("  ssh -V output : [" + $o2.Trim() + "]")
L ("  LASTEXITCODE  : " + $LASTEXITCODE)

L ''
L '--- 3. all files in C:\OpenSSH ---'
Get-ChildItem 'C:\OpenSSH' -ErrorAction SilentlyContinue | ForEach-Object { L ("  " + $_.Name + "  " + $_.Length) }

L ''
L '--- 4. event log: Service Control Manager / errors, last 40 min ---'
$since = (Get-Date).AddMinutes(-40)
try {
    Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = $since } -ErrorAction Stop |
        Where-Object { $_.ProviderName -like '*Service Control Manager*' } |
        Select-Object -First 25 |
        ForEach-Object { L ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] id=" + $_.Id + "  " + ($_.Message -replace "`r`n", ' ')) }
} catch { L ("  (system log: " + $_.Exception.Message + ")") }

L ''
L '--- 5. event log: Application errors, last 40 min ---'
try {
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $since } -ErrorAction Stop |
        Select-Object -First 25 |
        ForEach-Object { L ("  [" + $_.TimeCreated.ToString('HH:mm:ss') + "] " + $_.ProviderName + " id=" + $_.Id + "  " + ($_.Message -replace "`r`n", ' ')) }
} catch { L ("  (app log: " + $_.Exception.Message + ")") }

L ''
L '--- 6. security products / Smart App Control ---'
try {
    $mp = Get-MpComputerStatus -ErrorAction Stop
    L ("  Defender realtime : " + $mp.RealTimeProtectionEnabled)
    L ("  Defender AMSI     : " + $mp.AMServiceEnabled)
} catch { L ("  Defender query failed: " + $_.Exception.Message) }
$sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -Name VerifiedAndReputablePolicyState -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
L ("  SmartAppControl    : " + $(if ($null -eq $sac) { 'n/a' } else { $sac }) + "   (0=off 1=on 2=eval)")
try {
    Get-CimInstance -Namespace 'root\SecurityCenter2' -ClassName AntiVirusProduct -ErrorAction Stop |
        ForEach-Object { L ("  AV product        : " + $_.displayName) }
} catch { L '  AV product query failed' }

L ''
L '--- 7. is C:\OpenSSH blocked by an execution policy / zone? ---'
$z = Get-Item $sshd -Stream Zone.Identifier -ErrorAction SilentlyContinue
L ("  Zone.Identifier   : " + $(if ($z) { 'PRESENT (mark of the web!)' } else { 'none' }))

L ''
L '--- 8. internet reachability (WU) ---'
$net = (Test-NetConnection 'www.microsoft.com' -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded
L ("  www.microsoft.com:443 = " + $net)

L ''
L '--- 9. attempt official install via Windows capability ---'
$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cap) {
    L ("  capability : " + $cap.Name + "   state=" + $cap.State)
    if ($cap.State -ne 'Installed' -and $net) {
        L '  removing our hand-made service first ...'
        (& sc.exe stop sshd 2>&1) | Out-Null
        (& sc.exe delete sshd 2>&1) | ForEach-Object { L ("    " + $_) }
        Start-Sleep -Seconds 2
        L '  installing capability (may take 1-3 min) ...'
        try {
            $r = Add-WindowsCapability -Online -Name $cap.Name -ErrorAction Stop
            L ("    result: RestartNeeded=" + $r.RestartNeeded)
        } catch { L ("    Add-WindowsCapability FAILED: " + $_.Exception.Message) }
        Start-Sleep -Seconds 2
        $svc2 = Get-Service sshd -ErrorAction SilentlyContinue
        L ("    service now: " + $(if ($svc2) { $svc2.Status } else { 'missing' }))
        if ($svc2) {
            try { Start-Service sshd -ErrorAction Stop; L '    Start-Service OK' } catch { L ("    Start-Service failed: " + $_.Exception.Message) }
            & netsh advfirewall firewall delete rule name="OpenSSH-Server-In" 2>&1 | Out-Null
            & netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22 2>&1 | Out-Null
            Start-Sleep -Seconds 3
        }
    }
} else { L '  capability query returned nothing' }

L ''
L '--- 10. final port check ---'
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
L ("  port 22 : " + $(if ($listen.Count -gt 0) { 'LISTENING' } else { 'no listener' }))
$svcF = Get-Service sshd -ErrorAction SilentlyContinue
L ("  service : " + $(if ($svcF) { $svcF.Status } else { 'missing' }))

L ''
L '=== end ==='
Write-Host ''
Write-Host ("report -> " + $out)
