# ============================================================
#  NUC 算力节点 — 一键还原出厂 (交还前双击)
#  还原内容: WSL2 全部卸载 + 项目文件清洗 + 环境剥离 + 恢复初始状态
#  用法: 右键 "使用 PowerShell 运行" (需管理员, 会自动提权)
# ============================================================
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Continue'
$host.UI.RawUI.WindowTitle = 'NUC 还原出厂'

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ' NUC 算力节点 — 还复出厂工具' -ForegroundColor Cyan
Write-Host ' 将执行:' -ForegroundColor Yellow
Write-Host '   1. 卸载 WSL2 + 全部 Linux 发行版 (含虚拟磁盘)' -ForegroundColor Yellow
Write-Host '   2. 禁用 WSL/虚拟机平台 Windows 特性' -ForegroundColor Yellow
Write-Host '   3. 清洗项目文件 (仓库/几何/任务包/结果)' -ForegroundColor Yellow
Write-Host '   4. 卸载 OpenSSH Server, 移除远程公钥' -ForegroundColor Yellow
Write-Host '   5. 还原网络设置 (防火墙规则/网络类别)' -ForegroundColor Yellow
Write-Host '   6. 清理计划任务/临时文件' -ForegroundColor Yellow
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''
$confirm = Read-Host '确认还原? 此操作不可逆 (输入 YES 继续)'
if ($confirm -ne 'YES') { Write-Host '已取消'; exit 0 }

$log = "$env:USERPROFILE\Desktop\factory_reset_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
function L($m) { $m | Tee-Object -FilePath $log -Append }
function Step($n, $t) { Write-Host ''; Write-Host "[$n/6] $t" -ForegroundColor Cyan; L "=== [$n] $t ===" }

# ---------- 1. WSL2 全卸 ----------
Step 1 '卸载 WSL2 + 发行版'
wsl --shutdown 2>$null
$distros = wsl --list --quiet 2>$null | Where-Object { $_ -and $_.Trim() }
foreach ($d in $distros) {
    $dn = $d.Trim() -replace "`0", ''
    if ($dn) {
        L "  unregister: $dn"
        wsl --unregister $dn 2>$null
    }
}
Get-AppxPackage -Name '*WindowsSubsystemForLinux*' -ErrorAction SilentlyContinue | Remove-AppxPackage -ErrorAction SilentlyContinue
Get-AppxPackage -Name '*Ubuntu*' -ErrorAction SilentlyContinue | Remove-AppxPackage -ErrorAction SilentlyContinue
L '  WSL 发行版与商店包已卸载'

# ---------- 2. 禁用特性 ----------
Step 2 '禁用 WSL/虚拟机特性'
dism /online /disable-feature /featurename:Microsoft-Windows-Subsystem-Linux /norestart 2>$null | Out-Null
dism /online /disable-feature /featurename:VirtualMachinePlatform /norestart 2>$null | Out-Null
L '  特性已禁用 (重启后完全生效)'

# ---------- 3. 项目文件清洗 ----------
Step 3 '清洗项目文件'
$targets = @(
    "$env:USERPROFILE\sweep_pack_work",
    "$env:USERPROFILE\windtunn",
    "$env:USERPROFILE\windtunnel",
    "$env:USERPROFILE\.ssh\authorized_keys",
    "C:\ProgramData\ssh\administrators_authorized_keys",
    "$env:USERPROFILE\wsl_install_progress.log",
    "$env:USERPROFILE\wsl_setup_task.ps1",
    "$env:USERPROFILE\nuc1_wsl_install.ps1",
    "$env:USERPROFILE\nuc_net_setup.log",
    "$env:USERPROFILE\nuc_pushkey.ps1",
    "$env:USERPROFILE\nuc_capture.ps1",
    "$env:USERPROFILE\nuc_parse.ps1",
    "$env:USERPROFILE\nuc.etl",
    "$env:USERPROFILE\nuc_capture.txt",
    "$env:USERPROFILE\nuc_parse_result.txt",
    "$env:USERPROFILE\wslcore.log",
    "$env:USERPROFILE\wsl_install_raw.log",
    "$env:USERPROFILE\wsl_status.log",
    "$env:USERPROFILE\wv.txt",
    "$env:USERPROFILE\st.txt",
    "$env:USERPROFILE\st2.txt",
    "$env:USERPROFILE\f1.txt",
    "$env:USERPROFILE\f2.txt",
    "$env:USERPROFILE\f3.txt",
    "$env:USERPROFILE\ubuntu_install.log",
    "$env:USERPROFILE\setup_nuc_net.ps1",
    "$env:USERPROFILE\nuc_net_fix2.ps1",
    "$env:USERPROFILE\nuc_net_fix2.txt"
)
foreach ($t in $targets) {
    if (Test-Path $t) {
        L "  删除: $t"
        Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Get-ChildItem "$env:LOCALAPPDATA\Packages" -Directory -ErrorAction SilentlyContinue |
    Where-Object Name -match 'Ubuntu|WSL|Linux' |
    ForEach-Object { L "  删除: $_"; Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
L '  项目文件清洗完成'

# ---------- 4. 卸载 OpenSSH + 移除公钥 ----------
Step 4 '卸载 OpenSSH Server'
Stop-Service sshd -Force -ErrorAction SilentlyContinue
Set-Service sshd -StartupType Disabled -ErrorAction SilentlyContinue
Remove-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' -ErrorAction SilentlyContinue | Out-Null
Stop-Service WinRM -Force -ErrorAction SilentlyContinue
Set-Service WinRM -StartupType Disabled -ErrorAction SilentlyContinue
L '  SSH/WinRM 已卸载或禁用'

# ---------- 5. 网络还原 ----------
Step 5 '还原网络设置'
$rules = @('Allow-ICMP','Allow-SSH','WinRM-HTTP','NUC-ICMP','NUC-WinRM','NUC-SSH','NUC-SMB','OpenSSH-Server-In')
foreach ($r in $rules) {
    netsh advfirewall firewall delete rule name=$r 2>$null | Out-Null
}
L '  防火墙规则已清理'

# ---------- 6. 计划任务/临时 ----------
Step 6 '清理计划任务与临时文件'
$tasks = @('WSL_Auto_Install','WSL_Install2')
foreach ($t in $tasks) {
    Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
}
Remove-Item "$env:TEMP\nuc_askpass.cmd" -Force -ErrorAction SilentlyContinue
L '  计划任务与临时文件已清理'

Write-Host ''
Write-Host '============================================' -ForegroundColor Green
Write-Host ' 还原完成! 日志: ' -NoNewline -ForegroundColor Green
Write-Host $log -ForegroundColor White
Write-Host ' 建议: 重启一次 NUC 让特性禁用完全生效' -ForegroundColor Yellow
Write-Host '============================================' -ForegroundColor Green
Write-Host ''
Read-Host '按回车关闭'
