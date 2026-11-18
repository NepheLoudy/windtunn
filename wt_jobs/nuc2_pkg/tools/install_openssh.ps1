# ============================================================
#  install_openssh.ps1  --  ASCII-only, encoding-proof
#  Installs Windows OpenSSH Server from the sibling OpenSSH\ folder.
#  Must run elevated (install_ssh.bat handles elevation).
#  Exit codes: 0 ok / 2 not admin / 3 source missing / 4 sshd not running
# ============================================================
$ErrorActionPreference = 'Continue'
$LOG = 'C:\Windows\Temp\nuc_ssh_install.log'
try { Start-Transcript -Path $LOG -Force | Out-Null } catch { }

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }

Say ''
Say '==================================================' 'Cyan'
Say '  Windows OpenSSH Server Installer  (ASCII build)' 'Cyan'
Say '==================================================' 'Cyan'
Say ''

# ---------- 0. admin ----------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Say '[FAIL] Not running as Administrator.' 'Red'
    Say '       Right-click install_ssh.bat -> Run as administrator' 'Yellow'
    Say '       or: PowerShell (Admin) -> run this script again' 'Yellow'
    exit 2
}
Say '[ OK ] Administrator rights confirmed' 'Green'

# ---------- 1. locate OpenSSH source ----------
Say ''
Say '[1/5] Locating OpenSSH binaries ...' 'Cyan'
$cands = New-Object System.Collections.ArrayList
if ($PSScriptRoot) { [void]$cands.Add((Join-Path $PSScriptRoot 'OpenSSH')) }
foreach ($d in @(Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
    [void]$cands.Add((Join-Path $d.Root 'OpenSSH'))
}
$src = $null
foreach ($c in $cands) {
    if ($c -and (Test-Path (Join-Path $c 'sshd.exe'))) { $src = $c; break }
}
if (-not $src) {
    Say '[FAIL] sshd.exe not found in any of these locations:' 'Red'
    foreach ($c in $cands) { Say "         $c" 'DarkGray' }
    Say '       Keep the OpenSSH folder next to install_ssh.bat.' 'Yellow'
    try { Stop-Transcript | Out-Null } catch { }
    exit 3
}
Say "       source = $src" 'Gray'

# ---------- 2. copy binaries ----------
Say ''
Say '[2/5] Copying to C:\Windows\System32\OpenSSH ...' 'Cyan'
$dst = 'C:\Windows\System32\OpenSSH'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\ProgramData\ssh' | Out-Null
Copy-Item (Join-Path $src '*') $dst -Recurse -Force -ErrorAction SilentlyContinue
$n = @(Get-ChildItem $dst -File -ErrorAction SilentlyContinue).Count
if (-not (Test-Path (Join-Path $dst 'sshd.exe'))) {
    Say '[FAIL] copy failed - sshd.exe still missing' 'Red'
    try { Stop-Transcript | Out-Null } catch { }
    exit 3
}
Say "[ OK ] $n files in $dst" 'Green'

# ---------- 3. host keys ----------
Say ''
Say '[3/5] Host keys ...' 'Cyan'
Push-Location $dst
& .\ssh-keygen.exe -A 2>&1 | ForEach-Object { Say "       $_" 'DarkGray' }
$keymap = @{
    'ssh_host_rsa_key'     = @('-t', 'rsa', '-b', '3072')
    'ssh_host_ecdsa_key'   = @('-t', 'ecdsa')
    'ssh_host_ed25519_key' = @('-t', 'ed25519')
}
foreach ($k in $keymap.Keys) {
    $kp = Join-Path 'C:\ProgramData\ssh' $k
    if (-not (Test-Path $kp)) {
        Say "       missing $k -> generating" 'Yellow'
        $args2 = @('-q') + $keymap[$k] + @('-f', $kp, '-N', '""')
        & .\ssh-keygen.exe @args2 2>&1 | ForEach-Object { Say "       $_" 'DarkGray' }
    }
    if (Test-Path $kp) { Say "[ OK ] $k" 'Green' } else { Say "[FAIL] $k" 'Red' }
}
Pop-Location

# ---------- 4. sshd_config ----------
Say ''
Say '[4/5] Writing sshd_config ...' 'Cyan'
$cfgPath = 'C:\ProgramData\ssh\sshd_config'
$cfg = @(
    'Port 22',
    'AddressFamily any',
    'ListenAddress 0.0.0.0',
    'HostKey "C:\ProgramData\ssh\ssh_host_rsa_key"',
    'HostKey "C:\ProgramData\ssh\ssh_host_ecdsa_key"',
    'HostKey "C:\ProgramData\ssh\ssh_host_ed25519_key"',
    'PermitRootLogin no',
    'PubkeyAuthentication yes',
    'PasswordAuthentication yes',
    'AuthorizedKeysFile .ssh/authorized_keys',
    'Subsystem sftp sftp-server.exe',
    'UseDNS no',
    'MaxAuthTries 6'
)
if (Test-Path $cfgPath) {
    Copy-Item $cfgPath "$cfgPath.bak_$(Get-Date -Format yyyyMMddHHmmss)" -Force
    Say '       existing config backed up' 'DarkGray'
}
Set-Content -Path $cfgPath -Value $cfg -Encoding ASCII
Say '[ OK ] sshd_config written (ASCII, no encoding risk)' 'Green'

# ---------- 5. service + firewall ----------
Say ''
Say '[5/5] Registering service + firewall ...' 'Cyan'
& sc.exe stop sshd 2>&1 | Out-Null
& sc.exe delete sshd 2>&1 | Out-Null
Start-Sleep -Seconds 2
$create = & sc.exe create sshd binPath= "C:\Windows\System32\OpenSSH\sshd.exe" start= auto 2>&1
Say "       sc create : $create" 'DarkGray'
$start = & sc.exe start sshd 2>&1
Say "       sc start  : $start" 'DarkGray'
& netsh advfirewall firewall delete rule name="OpenSSH-Server-In" 2>&1 | Out-Null
& netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22 2>&1 | Out-Null
Say '[ OK ] firewall rule OpenSSH-Server-In (TCP 22)' 'Green'

# ---------- verdict ----------
Start-Sleep -Seconds 2
$svc = Get-Service sshd -ErrorAction SilentlyContinue
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
$ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
         Where-Object { $_.IPAddress -ne '127.0.0.1' } |
         ForEach-Object { "{0}/{1}  [{2}]" -f $_.IPAddress, $_.PrefixLength, $_.InterfaceAlias })

Say ''
Say '--------------------------------------------------' 'Cyan'
if ($svc -and $svc.Status -eq 'Running' -and $listen.Count -gt 0) {
    Say '   *** SSH READY ***' 'Green'
    Say "   service = $($svc.Status)   listening on port 22" 'Green'
} elseif ($svc -and $svc.Status -eq 'Running') {
    Say '   *** SERVICE RUNNING, PORT 22 NOT LISTENING YET ***' 'Yellow'
    Say '   waiting 3s ...' 'Yellow'
    Start-Sleep -Seconds 3
    $listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
    if ($listen.Count -gt 0) { Say '   *** SSH READY ***' 'Green' }
    else { Say "   service=$($svc.Status) but no listener - check $LOG" 'Red' }
} else {
    $st = if ($svc) { $svc.Status } else { 'not installed' }
    Say "   *** SSH FAILED (service = $st) ***" 'Red'
    Say "   see $LOG" 'Yellow'
}
Say ''
Say '   IPv4 addresses on this machine:' 'Cyan'
if ($ips.Count -eq 0) { Say '     (none - NIC has no IP)' 'Red' }
foreach ($a in $ips) { Say "     $a" 'White' }
Say '--------------------------------------------------' 'Cyan'
Say ''
Say "   log: $LOG" 'DarkGray'
Say '   -> tell Mambo the 137.x / 138.x line above' 'Yellow'
Say ''
try { Stop-Transcript | Out-Null } catch { }

if ($svc -and $svc.Status -eq 'Running' -and $listen.Count -gt 0) { exit 0 } else { exit 4 }
