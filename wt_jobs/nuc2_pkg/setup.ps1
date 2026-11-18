# ============================================================
#  setup.ps1  --  ASCII only.  Installs sshd from .\OpenSSH
#  Destination: C:\OpenSSH   (NEVER touches C:\Windows\System32)
#  Log: <script dir>\install_log.txt  (+ best-effort copy to \\192.168.138.50\nuc_d\setup_nuc)
# ============================================================
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$log  = Join-Path $here 'install_log.txt'
$ts   = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Set-Content -Path $log -Value @("=== NUC SSH installer $ts ===") -Encoding ASCII

function L($m, $c = 'Gray') {
    Write-Host $m -ForegroundColor $c
    Add-Content -Path $log -Value $m -Encoding ASCII
}

L ''
L '==================================================' 'Cyan'
L '  NUC2 SSH installer  (installs to C:\OpenSSH)'     'Cyan'
L '==================================================' 'Cyan'
L "  script dir : $here"
L "  computer   : $env:COMPUTERNAME"
L "  user       : $env:USERNAME"

# ---- 0. admin ----
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    L '[FAIL] Not elevated. Open an Administrator terminal and run again.' 'Red'
    L '       Win+X -> Terminal (Admin) -> C:\setup_nuc\setup.bat' 'Yellow'
    exit 2
}
L '[ OK ] elevated' 'Green'

# ---- 1. source ----
$src = Join-Path $here 'OpenSSH'
if (-not (Test-Path (Join-Path $src 'sshd.exe'))) {
    L "[FAIL] missing $src\sshd.exe" 'Red'
    exit 3
}
L "[ OK ] source : $src"

# ---- 2. copy ----
$dst = 'C:\OpenSSH'
$pd  = 'C:\ProgramData\ssh'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
New-Item -ItemType Directory -Force -Path $pd  | Out-Null
Copy-Item (Join-Path $src '*') $dst -Recurse -Force -ErrorAction SilentlyContinue
if (-not (Test-Path (Join-Path $dst 'sshd.exe'))) {
    L '[FAIL] copy failed - sshd.exe not in C:\OpenSSH' 'Red'
    exit 3
}
L ("[ OK ] copied {0} files -> {1}" -f @(Get-ChildItem $dst -File).Count, $dst) 'Green'

# ---- 3. sshd_config ----
$cfg = Join-Path $pd 'sshd_config'
if (Test-Path $cfg) { Copy-Item $cfg "$cfg.bak_$(Get-Date -f yyyyMMddHHmmss)" -Force; L '       old config backed up' }
@(
    'Port 22'
    'AddressFamily any'
    'ListenAddress 0.0.0.0'
    'HostKey "C:\ProgramData\ssh\ssh_host_rsa_key"'
    'HostKey "C:\ProgramData\ssh\ssh_host_ecdsa_key"'
    'HostKey "C:\ProgramData\ssh\ssh_host_ed25519_key"'
    'PermitRootLogin no'
    'PubkeyAuthentication yes'
    'PasswordAuthentication yes'
    'AuthorizedKeysFile .ssh/authorized_keys'
    'Subsystem sftp sftp-server.exe'
    'UseDNS no'
) | Set-Content -Path $cfg -Encoding ASCII
L '[ OK ] sshd_config written (ASCII)' 'Green'

# ---- 4. host keys ----
& (Join-Path $dst 'ssh-keygen.exe') -A 2>&1 | ForEach-Object { L "       $_" 'DarkGray' }
$keys = @(Get-ChildItem $pd -Filter 'ssh_host_*_key' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
if ($keys.Count -ge 1) { L ("[ OK ] host keys: " + ($keys -join ', ')) 'Green' }
else { L '[FAIL] no host keys generated' 'Red' }

# ---- 5. service ----
& sc.exe stop sshd 2>&1 | Out-Null
& sc.exe delete sshd 2>&1 | Out-Null
Start-Sleep -Seconds 1
$c = & sc.exe create sshd binPath= "C:\OpenSSH\sshd.exe" start= auto 2>&1
L "       sc create : $c" 'DarkGray'
$s = & sc.exe start sshd 2>&1
L "       sc start  : $s" 'DarkGray'
& netsh advfirewall firewall delete rule name="OpenSSH-Server-In" 2>&1 | Out-Null
& netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22 2>&1 | Out-Null
L '[ OK ] firewall TCP 22' 'Green'

# ---- 6. verdict ----
Start-Sleep -Seconds 2
$svc    = Get-Service sshd -ErrorAction SilentlyContinue
$listen = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue)
L ''
L '--------------------------------------------------' 'Cyan'
if ($listen.Count -gt 0) { L '   *** SSH READY ***' 'Green' }
else {
    L '   *** SSH FAILED ***' 'Red'
    L ("   service = " + $(if ($svc) { $svc.Status } else { 'not installed' })) 'Red'
    L ("   log = " + $log) 'Yellow'
}
L ''
L '   IPv4:' 'Cyan'
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -ne '127.0.0.1' } |
    ForEach-Object { L ("     {0}/{1}  [{2}]" -f $_.IPAddress, $_.PrefixLength, $_.InterfaceAlias) 'White' }
L '--------------------------------------------------' 'Cyan'
L ''

# ---- 7. push log back to the share so Mambo never has to report it ----
$unc = '\\192.168.138.50\nuc_d\install_log.txt'
try { Copy-Item $log $unc -Force -ErrorAction Stop; Write-Host "log mirrored to $unc" -ForegroundColor DarkGray }
catch { Write-Host "log mirror failed (harmless): $($_.Exception.Message)" -ForegroundColor DarkGray }

if ($listen.Count -gt 0) { exit 0 } else { exit 4 }
