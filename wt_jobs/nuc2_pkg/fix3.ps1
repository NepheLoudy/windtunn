# ============================================================
#  fix3.ps1 -- ASCII only.
#  Use the OS-native OpenSSH Server (matches this Windows build),
#  discard the foreign 25H2 binaries. Report: fix3.txt
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$out  = Join-Path $here 'fix3.txt'
Set-Content -Path $out -Value @("=== fix3  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  on $env:COMPUTERNAME ===") -Encoding ASCII
function L($m) { Add-Content -Path $out -Value $m -Encoding ASCII; Write-Host $m }

$sep = [string][char]92
$sysdir = 'C:\Windows\System32\OpenSSH'
$sysd   = $sysdir + $sep + 'sshd.exe'
$sysssh = $sysdir + $sep + 'ssh.exe'
$pd     = 'C:\ProgramData\ssh'
$cfg    = $pd + $sep + 'sshd_config'

L ("elevated : " + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
L ("OS build : " + [Environment]::OSVersion.Version)

L ''
L '--- 1. OS-native binaries ---'
L ("  sysdir exists      : " + (Test-Path $sysdir))
if (Test-Path $sysd) {
    $o = & $sysd -h 2>&1 | Out-String
    L ("  sshd -h rc         : " + $LASTEXITCODE)
    L ("  sshd -h first line : " + (($o -split "`r?`n")[0]))
} else { L '  NO sshd.exe in System32\OpenSSH' }
if (Test-Path $sysssh) {
    $o2 = & $sysssh -V 2>&1 | Out-String
    L ("  ssh -V rc          : " + $LASTEXITCODE)
    L ("  ssh -V             : " + (($o2 -split "`r?`n")[0]))
}

L ''
L '--- 2. service registration ---'
(& sc.exe qc sshd 2>&1) | ForEach-Object { L ("  " + $_) }

L ''
L '--- 3. get rid of the foreign 25H2 copy ---'
if (Test-Path 'C:\OpenSSH') {
    try { Remove-Item 'C:\OpenSSH' -Recurse -Force -ErrorAction Stop; L '  removed C:\OpenSSH' }
    catch { L ('  could not remove C:\OpenSSH: ' + $_.Exception.Message) }
} else { L '  C:\OpenSSH already gone' }

L ''
L '--- 4. host keys + config ---'
if (-not (Test-Path $pd)) { New-Item -ItemType Directory -Force -Path $pd | Out-Null }
$gen = $sysdir + $sep + 'ssh-keygen.exe'
if ((Test-Path $gen) -and -not (Test-Path ($pd + $sep + 'ssh_host_ed25519_key'))) {
    & $gen -A 2>&1 | ForEach-Object { L ("  " + $_) }
}
$keys = @(Get-ChildItem $pd -Filter 'ssh_host_*_key' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
L ("  host keys: " + ($(if ($keys.Count) { $keys -join ', ' } else { 'NONE' })))

if (Test-Path $cfg) {
    Copy-Item $cfg ($pd + $sep + 'sshd_config.prev') -Force
    L '  previous config saved as sshd_config.prev'
}
$lines = @(
    'Port 22',
    'ListenAddress 0.0.0.0',
    'HostKey __PROGRAMDATA__/ssh/ssh_host_rsa_key',
    'HostKey __PROGRAMDATA__/ssh/ssh_host_ecdsa_key',
    'HostKey __PROGRAMDATA__/ssh/ssh_host_ed25519_key',
    'PubkeyAuthentication yes',
    'PasswordAuthentication yes',
    'AuthorizedKeysFile .ssh/authorized_keys',
    'PermitRootLogin no',
    'Subsystem sftp sftp-server.exe',
    'UseDNS no'
)
Set-Content -Path $cfg -Value $lines -Encoding ASCII
L '  minimal sshd_config written (no Match-administrators block)'

# ACL: sshd wants SYSTEM + Administrators only
foreach ($f in @($pd) + @($keys | ForEach-Object { $pd + $sep + $_ })) {
    $isDir = (Get-Item $f -ErrorAction SilentlyContinue).PSIsContainer
    if ($isDir) {
        & icacls $f /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' /grant:r '*S-1-5-32-544:(OI)(CI)F' 2>&1 | Out-Null
    } else {
        & icacls $f /inheritance:r /grant:r '*S-1-5-18:F' /grant:r '*S-1-5-32-544:F' 2>&1 | Out-Null
    }
}
L '  ACLs set to SYSTEM + Administrators'

L ''
L '--- 5. start service ---'
(& sc.exe stop sshd 2>&1) | Out-Null
Start-Sleep -Seconds 2
(& sc.exe start sshd 2>&1) | ForEach-Object { L ("  " + $_) }
Start-Sleep -Seconds 4
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)

if ($listen.Count -eq 0) {
    L ''
    L '--- 6. foreground diagnostic of the OS sshd (8 s) ---'
    $e = $here + $sep + '_sshd3_err.txt'
    $o = $here + $sep + '_sshd3_out.txt'
    Remove-Item $e, $o -ErrorAction SilentlyContinue
    try {
        $p = Start-Process -FilePath $sysd -ArgumentList '-D', '-d', '-e' -RedirectStandardError $e -RedirectStandardOutput $o -PassThru -NoNewWindow -ErrorAction Stop
        Start-Sleep -Seconds 8
        if ($p.HasExited) { L ('  exited code = ' + $p.ExitCode) } else { $p.Kill(); L '  ran 8s -> binary OK, service layer problem' }
    } catch { L ('  Start-Process failed: ' + $_.Exception.Message) }
    if (Test-Path $e) { L '  --- stderr ---'; Get-Content $e | ForEach-Object { L ('    ' + $_) } }
    if (Test-Path $o) { L '  --- stdout ---'; Get-Content $o | ForEach-Object { L ('    ' + $_) } }
}

L ''
L '--- 7. firewall + final ---'
& netsh advfirewall firewall delete rule name="OpenSSH-Server-In" 2>&1 | Out-Null
& netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22 2>&1 | Out-Null
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
$svc = Get-Service sshd -ErrorAction SilentlyContinue
L ('  service : ' + $(if ($svc) { $svc.Status } else { 'missing' }))
L ('  port 22 : ' + $(if ($listen.Count -gt 0) { 'LISTENING' } else { 'no listener' }))
L ''
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ('  ' + $_.IPAddress + '/' + $_.PrefixLength + '  [' + $_.InterfaceAlias + ']') }
L ''
if ($listen.Count -gt 0) { L '*** SSH READY ***' } else { L '*** STILL FAILED ***' }
