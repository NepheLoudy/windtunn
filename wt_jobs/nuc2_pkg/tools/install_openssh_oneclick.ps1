# ============================================================
#  NUC OpenSSH 一键安装 (右键 "使用 PowerShell 运行", 需管理员)
#  自动提权 + 拷文件 + host key + 配置 + 注册服务 + 防火墙
# ============================================================
$ErrorActionPreference = 'Continue'

# 0. 自动提权
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host ''
Write-Host '=== NUC OpenSSH 一键安装 ===' -ForegroundColor Cyan

# 1. 建目录
Write-Host '[1/5] 创建目录...' -ForegroundColor Cyan
foreach ($d in @('C:\Windows\System32\OpenSSH', 'C:\ProgramData\ssh')) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    Write-Host "  OK: $d"
}

# 2. 拷文件
Write-Host '[2/5] 拷贝 OpenSSH...' -ForegroundColor Cyan
# 源目录优先级: 脚本同级的 OpenSSH\ (U盘插任意盘符都能用) -> D:\OpenSSH -> 全盘搜
$src = Join-Path $PSScriptRoot 'OpenSSH'
if (Test-Path "$src\sshd.exe") {
    Write-Host "  源: 脚本同级 $src"
} else {
    $src = 'D:\OpenSSH'
    if (-not (Test-Path "$src\sshd.exe")) {
        Write-Host '  D:\OpenSSH 不完整 — 在 C:\ D:\ 搜索...' -ForegroundColor Yellow
        $alt = Get-ChildItem -Path 'C:\', 'D:\' -Filter 'sshd.exe' -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($alt) { $src = $alt.DirectoryName; Write-Host "  找到: $src" }
    }
}
if (-not (Test-Path "$src\sshd.exe")) {
    Write-Host '  FATAL: 找不到 sshd.exe' -ForegroundColor Red
    Read-Host '按回车退出'
    exit 1
}
Copy-Item "$src\*" 'C:\Windows\System32\OpenSSH\' -Recurse -Force
$cnt = (Get-ChildItem 'C:\Windows\System32\OpenSSH' | Measure-Object).Count
Write-Host "  OK: $cnt 个文件 -> C:\Windows\System32\OpenSSH\"

# 3. host key
Write-Host '[3/5] 生成 host key...' -ForegroundColor Cyan
Set-Location 'C:\Windows\System32\OpenSSH'
$output = & .\ssh-keygen.exe -A 2>&1 | Out-String
Write-Host "  $output"

# 4. sshd_config
Write-Host '[4/5] 写配置...' -ForegroundColor Cyan
$cfgPath = 'C:\ProgramData\ssh\sshd_config'
if (-not (Test-Path $cfgPath)) {
    $cfg = "Port 22`nProtocol 2`nHostKey C:\ProgramData\ssh\ssh_host_rsa_key`nHostKey C:\ProgramData\ssh\ssh_host_ecdsa_key`nHostKey C:\ProgramData\ssh\ssh_host_ed25519_key`nPermitRootLogin no`nMaxAuthTries 6`nAuthorizedKeysFile .ssh/authorized_keys`nPasswordAuthentication yes`nPubkeyAuthentication yes`nSubsystem sftp sftp-server.exe`n"
    $cfg | Out-File $cfgPath -Encoding ascii
    Write-Host '  OK: sshd_config 创建'
} else { Write-Host '  OK: 已存在' }

# 5. 服务+防火墙
Write-Host '[5/5] 注册服务...' -ForegroundColor Cyan
sc.exe stop sshd 2>$null | Out-Null
sc.exe delete sshd 2>$null | Out-Null
Start-Sleep -Seconds 2
$rc = sc.exe create sshd binPath= "C:\Windows\System32\OpenSSH\sshd.exe" start= auto 2>&1
Write-Host "  create: $rc"
$rc2 = net start sshd 2>&1 | Out-String
Write-Host "  start: $rc2"
netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22 | Out-Null
Write-Host '  防火墙 OK'

# 验证
Write-Host ''
$svc = Get-Service sshd -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq 'Running') {
    Write-Host '=== sshd RUNNING ===' -ForegroundColor Green
    $ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
             Where-Object { $_.IPAddress -like '192.168.138.*' -or $_.IPAddress -like '192.168.137.*' } |
             ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength) [$($_.InterfaceAlias)]" })
    if ($ips.Count -gt 0) {
        foreach ($a in $ips) { Write-Host "SSH: $a  port 22" -ForegroundColor Green }
    } else {
        Write-Host '  !! 网线网段没有 IP（137/138 都没匹配）' -ForegroundColor Red
        Write-Host '  本机全部 IPv4 地址：' -ForegroundColor Yellow
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host ("    {0}/{1}  [{2}]" -f $_.IPAddress, $_.PrefixLength, $_.InterfaceAlias) }
        Write-Host '  -> 把上面这几行念给我，我在本机侧补 IP/NAT' -ForegroundColor Yellow
    }
} else {
    Write-Host "=== sshd $($svc.Status) ===" -ForegroundColor Yellow
}
Read-Host '按回车关闭'
