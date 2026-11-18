# ============================================================
#  NUC 算力节点 — 全控制台操作代码 (一次复制版)
#  适用: 新 NUC (装了 Windows, 已通网线)
#  场景: 你拿到一台新 NUC, 插网线后按步骤粘贴执行
#  分三段: [A]本机准备(跑一次) [B]NUC现场(管理员PS) [C]远程全自动(本机)
# ============================================================

# ─────────────────────────────────────────────
# [A] 本机准备 — 只在第一次配新 NUC 时跑一次
#    (确认 ICS + 防火墙已就绪; NUC#1 时已配过, 跳过即可)
# ─────────────────────────────────────────────
# 以管理员 PowerShell 运行:
<#
$ad = Get-NetAdapter | Where-Object { $_.MacAddress -eq '00-E0-4C-68-00-0F' }
Set-NetConnectionProfile -InterfaceIndex $ad.ifIndex -NetworkCategory Private
netsh advfirewall firewall add rule name="NUC-ICMP" dir=in action=allow protocol=icmpv4 remoteip=192.168.137.0/24
netsh advfirewall firewall add rule name="NUC-WinRM" dir=in action=allow protocol=TCP localport=5985 remoteip=192.168.137.0/24
netsh advfirewall firewall add rule name="NUC-SSH"   dir=in action=allow protocol=TCP localport=22   remoteip=192.168.137.0/24
#>
# ICS 已开过(NUC#1) — 若新 NUC 拿不到 IP, 检查: Get-NetConnectionProfile -InterfaceIndex 23

# ─────────────────────────────────────────────
# [B] NUC 现场 — 插显示器键鼠, 管理员 PowerShell, 整段粘贴
# ─────────────────────────────────────────────
<#
# 1. 有线网卡 DHCP (接本机 ICS 自动拿 192.168.137.x)
Get-NetAdapter | Where-Object MediaType -eq '802.3' | Set-NetIPInterface -Dhcp Enabled
Get-NetAdapter | Where-Object MediaType -eq '802.3' | Set-DnsClientServerAddress -ResetServerAddresses

# 2. 装 OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd; Set-Service sshd -StartupType Automatic
netsh advfirewall firewall add rule name="OpenSSH-Server-In" dir=in action=allow protocol=TCP localport=22

# 3. 放行 ICMP
netsh advfirewall firewall add rule name="Allow-ICMP" dir=in action=allow protocol=icmpv4

# 4. 显示 IP (告诉台式机侧这个 IP)
ipconfig | Select-String 'IPv4'
#>

# ─────────────────────────────────────────────
# [C] 远程全自动 — 回到台式机, Git Bash 逐段粘贴
#    把 <IP> 换成 [B] 步骤 4 拿到的 IP (如 192.168.137.29)
# ─────────────────────────────────────────────
<#
NUC_IP=<IP>                    # ←←← 改这里!
NUC_PW='cquqianli'             # ←←← NUC 密码 (如果两台一样)

# 1. 推 SSH 公钥 (免密)
cat > /tmp/nuc_askpass.sh << 'EOF'
#!/bin/sh
echo "$NUC_PW"
EOF
chmod +x /tmp/nuc_askpass.sh
export SSH_ASKPASS=/tmp/nuc_askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=dummy
PUB=$(cat ~/.ssh/id_ed25519.pub)
ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no lenovo@$NUC_IP "if not exist .ssh mkdir .ssh & echo $PUB>> .ssh\authorized_keys & echo $PUB>> C:\ProgramData\ssh\administrators_authorized_keys" < /dev/null
# 验证免密:
ssh -o BatchMode=yes lenovo@$NUC_IP "echo SSH_OK" < /dev/null

# 2. 启用 WSL 特性 + 重启 NUC (等它回来)
ssh lenovo@$NUC_IP "dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart & dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart & shutdown /r /t 5" < /dev/null
sleep 120; for i in $(seq 1 20); do ping -n 1 -w 2000 $NUC_IP | grep -q TTL= && echo BACK && break; sleep 13; done

# 3. 装 WSL 内核包 (再重启一次)
ssh lenovo@$NUC_IP "wsl --install --no-distribution > C:\wslcore.log 2>&1" < /dev/null
ssh lenovo@$NUC_IP "shutdown /r /t 5" < /dev/null
sleep 120; for i in $(seq 1 20); do ping -n 1 -w 2000 $NUC_IP | grep -q TTL= && echo BACK && break; sleep 13; done

# 4. 推 Ubuntu 镜像 (10GB, ~2min) + 导入
scp /d/nuc_ubuntu_baseline.tar lenovo@${NUC_IP}:D:/nuc_ubuntu.tar
ssh lenovo@$NUC_IP "wsl --import Ubuntu-24.04 D:\WSL\Ubuntu D:\nuc_ubuntu.tar --version 2" < /dev/null

# 5. 验证 + 领包!
ssh lenovo@$NUC_IP "wsl -d Ubuntu-24.04 -- bash -c 'source /opt/openfoam12/etc/bashrc && blockMesh -help 2>&1 | head -1 && ls /root/windtunnel'" < /dev/null
ssh lenovo@$NUC_IP "wsl -d Ubuntu-24.04 -- bash -c 'cd /root/windtunnel/openfoam/airframe-sweep/sweep_packs && bash run_pack.sh P05'" < /dev/null

# 6. 放还原工具到桌面
scp /d/WindTunnelSuite/wt_jobs/tmp/restore_factory.ps1 "lenovo@${NUC_IP}:C:/Users/lenovo/Desktop/还原出厂-交机前双击.ps1"
#>

# ─────────────────────────────────────────────
# 常用巡检 (配好后日常用)
# ─────────────────────────────────────────────
<#
NUC_IP=192.168.137.28
# 看板 (进度):
ssh lenovo@$NUC_IP "wsl -d Ubuntu-24.04 -- bash -c 'cd /root/windtunnel/openfoam/airframe-sweep/sweep_packs && bash board.sh /root/sweep_pack_work'" < /dev/null
# CPU/内存:
ssh lenovo@$NUC_IP "wsl -d Ubuntu-24.04 -- bash -c 'uptime && free -h'" < /dev/null
#>
