# ============================================================
#  ssh_fix.ps1 -- ASCII only. Diagnose sshd 1053, repair ACLs, retest.
#  Report: <script dir>\ssh_fix.txt   (Mambo reads it remotely)
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$out  = Join-Path $here 'ssh_fix.txt'
Set-Content -Path $out -Value @("=== ssh fix  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding ASCII
function L($m) { Add-Content -Path $out -Value $m -Encoding ASCII; Write-Host $m }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { L '[FAIL] not elevated'; exit 2 }
L '[OK] elevated'

$sshd = 'C:\OpenSSH\sshd.exe'
$pd   = 'C:\ProgramData\ssh'
$cfg  = Join-Path $pd 'sshd_config'
L ("sshd.exe exists : " + (Test-Path $sshd))
L ("config  exists : " + (Test-Path $cfg))
L ("config  size   : " + $(if (Test-Path $cfg) { (Get-Item $cfg).Length } else { 0 }))

L ''
L '--- sc qc sshd ---'
(& sc.exe qc sshd 2>&1) | ForEach-Object { L ("  " + $_) }

L ''
L '--- sc start (attempt 1) ---'
(& sc.exe start sshd 2>&1) | ForEach-Object { L ("  " + $_) }
Start-Sleep -Seconds 3
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)

if ($listen.Count -eq 0) {
    L ''
    L '--- foreground diag: sshd -D -d -e (6 s) ---'
    $errF = Join-Path $here '_sshd_err.txt'
    $outF = Join-Path $here '_sshd_out.txt'
    Remove-Item $errF, $outF -ErrorAction SilentlyContinue
    try {
        $p = Start-Process -FilePath $sshd -ArgumentList '-D', '-d', '-e' -RedirectStandardError $errF -RedirectStandardOutput $outF -PassThru -NoNewWindow -ErrorAction Stop
        Start-Sleep -Seconds 6
        if ($p.HasExited) { L ("  exited, code = " + $p.ExitCode) }
        else { $p.Kill(); L '  still running after 6s (means the binary itself is fine)' }
    } catch { L ("  Start-Process failed: " + $_.Exception.Message) }
    if (Test-Path $errF) { L '  --- stderr ---'; Get-Content $errF | ForEach-Object { L ("    " + $_) } }
    if (Test-Path $outF) { L '  --- stdout ---'; Get-Content $outF | ForEach-Object { L ("    " + $_) } }

    L ''
    L '--- host key ACL before ---'
    foreach ($k in @('ssh_host_rsa_key', 'ssh_host_ecdsa_key', 'ssh_host_ed25519_key', 'ssh_host_dsa_key')) {
        $f = Join-Path $pd $k
        if (Test-Path $f) {
            (& icacls $f 2>&1) | ForEach-Object { L ("  " + $_) }
        }
    }

    L ''
    L '--- repairing ACLs (System + Administrators only) ---'
    (& icacls $pd /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' /grant:r '*S-1-5-32-544:(OI)(CI)F' 2>&1) | ForEach-Object { L ("  " + $_) }
    foreach ($k in @('ssh_host_rsa_key', 'ssh_host_ecdsa_key', 'ssh_host_ed25519_key', 'ssh_host_dsa_key')) {
        $f = Join-Path $pd $k
        if (Test-Path $f) {
            (& icacls $f /inheritance:r /grant:r '*S-1-5-18:F' /grant:r '*S-1-5-32-544:F' 2>&1) | Out-Null
            L ("  fixed " + $k)
        }
    }

    L ''
    L '--- restart service ---'
    (& sc.exe stop sshd 2>&1) | Out-Null
    Start-Sleep -Seconds 3
    (& sc.exe start sshd 2>&1) | ForEach-Object { L ("  " + $_) }
    Start-Sleep -Seconds 4
    $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)

    if ($listen.Count -eq 0) {
        L ''
        L '--- still dead: second foreground run ---'
        Remove-Item $errF, $outF -ErrorAction SilentlyContinue
        try {
            $p2 = Start-Process -FilePath $sshd -ArgumentList '-D', '-e' -RedirectStandardError $errF -RedirectStandardOutput $outF -PassThru -NoNewWindow -ErrorAction Stop
            Start-Sleep -Seconds 6
            if ($p2.HasExited) { L ("  exited, code = " + $p2.ExitCode) } else { $p2.Kill(); L '  running after 6s' }
        } catch { L ("  Start-Process failed: " + $_.Exception.Message) }
        if (Test-Path $errF) { L '  --- stderr ---'; Get-Content $errF | ForEach-Object { L ("    " + $_) } }
    }
}

L ''
L '--- verdict ---'
$svc = Get-Service sshd -ErrorAction SilentlyContinue
L ("  service : " + $(if ($svc) { $svc.Status } else { 'missing' }))
L ("  port 22 : " + $(if ($listen.Count -gt 0) { 'LISTENING' } else { 'no listener' }))
try { (& sc.exe qc sshd 2>&1) | ForEach-Object { L ("  " + $_) } } catch { }

L ''
L '--- IPv4 ---'
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ("  " + $_.IPAddress + "/" + $_.PrefixLength + "  [" + $_.InterfaceAlias + "]") }

if ($listen.Count -gt 0) { L ''; L '*** SSH READY ***' }
Add-Content -Path $out -Value '' -Encoding ASCII
