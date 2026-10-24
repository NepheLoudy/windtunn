param([string]$JsonPath = "D:\WindTunnelSuite\openfoam\airframe-sweep\progress.json",
      [string]$BatchName = "扫气批次")
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class WN {
  [DllImport("user32.dll")] public static extern bool ReleaseCapture();
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern int SetWindowLong(IntPtr h, int i, int v);
}
'@

$form = New-Object System.Windows.Forms.Form
$form.Text = "progress"
$form.FormBorderStyle = "None"
$form.ShowInTaskbar = $true
$form.Size = New-Object System.Drawing.Size(340, 96)
$form.StartPosition = "Manual"
$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(($wa.Width - 350), 40)
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(28, 32, 40)
$form.Opacity = 0.92

# 无边框窗体支持"点任务栏图标最小化/还原" (正常软件行为)
$form.Add_Load({
    $GWL_STYLE = -16
    $WS_MINIMIZEBOX = 0x20000
    $cur = [WN]::GetWindowLong($form.Handle, $GWL_STYLE)
    [WN]::SetWindowLong($form.Handle, $GWL_STYLE, ($cur -bor $WS_MINIMIZEBOX)) | Out-Null
})

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.AutoSize = $false
$lblTitle.Size = New-Object System.Drawing.Size(280, 20)
$lblTitle.Location = New-Object System.Drawing.Point(10, 6)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(140, 200, 255)
$lblTitle.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9, [System.Drawing.FontStyle]::Bold)
$lblTitle.Text = "$BatchName  启动中..."
$form.Controls.Add($lblTitle)

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Size = New-Object System.Drawing.Size(320, 14)
$bar.Location = New-Object System.Drawing.Point(10, 30)
$bar.Style = "Continuous"
$form.Controls.Add($bar)

$lblInfo = New-Object System.Windows.Forms.Label
$lblInfo.AutoSize = $false
$lblInfo.Size = New-Object System.Drawing.Size(320, 40)
$lblInfo.Location = New-Object System.Drawing.Point(10, 48)
$lblInfo.ForeColor = [System.Drawing.Color]::Gainsboro
$lblInfo.Font = New-Object System.Drawing.Font("Consolas", 8.5)
$lblInfo.Text = "waiting progress.json..."
$form.Controls.Add($lblInfo)

$lblClose = New-Object System.Windows.Forms.Label
$lblClose.AutoSize = $false
$lblClose.Size = New-Object System.Drawing.Size(18, 18)
$lblClose.Location = New-Object System.Drawing.Point(320, 2)
$lblClose.ForeColor = [System.Drawing.Color]::DimGray
$lblClose.Text = "x"
$lblClose.Cursor = "Hand"
$lblClose.Add_Click({ $form.Close() })
$form.Controls.Add($lblClose)

$lblMin = New-Object System.Windows.Forms.Label
$lblMin.AutoSize = $false
$lblMin.Size = New-Object System.Drawing.Size(18, 18)
$lblMin.Location = New-Object System.Drawing.Point(302, 2)
$lblMin.ForeColor = [System.Drawing.Color]::DimGray
$lblMin.Text = "-"
$lblMin.Cursor = "Hand"
$lblMin.Add_Click({
    if ($form.Height -gt 40) {
        $script:SavedH = $form.Height
        $bar.Visible = $false
        $lblInfo.Visible = $false
        $lblTitle.Size = New-Object System.Drawing.Size(280, 18)
        $form.Height = 24
        $lblMin.Text = "+"
    } else {
        $bar.Visible = $true
        $lblInfo.Visible = $true
        $lblTitle.Size = New-Object System.Drawing.Size(320, 20)
        $form.Height = $script:SavedH
        $lblMin.Text = "-"
    }
})
$form.Controls.Add($lblMin)

# 正确的无边框拖动: ReleaseCapture + WM_NCLBUTTONDOWN(HTCAPTION)
$dragHandler = {
    if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        [WN]::ReleaseCapture() | Out-Null
        [WN]::SendMessage($form.Handle, 0xA1, [IntPtr]0x2, [IntPtr]::Zero) | Out-Null
    }
}
$form.Add_MouseDown($dragHandler)
$lblTitle.Add_MouseDown($dragHandler)

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 4000
$timer.Add_Tick({
    try {
        $j = Get-Content $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $j) {
            $pct = 0
            if ($j.total -gt 0) { $pct = [int](100 * $j.done / $j.total) }
            $bar.Value = [Math]::Min(100, $pct)
            $eta = "剩余 估算中"
            if ($j.eta_min -ge 0) {
                if ($j.eta_min -ge 60) { $eta = "剩余 ~" + [int][Math]::Floor($j.eta_min / 60) + "h" + [int]($j.eta_min % 60) + "m" }
                else { $eta = "剩余 ~" + [int]$j.eta_min + "m" }
            }
            $run = ""
            if ($j.run_min -ge 60) { $run = [string][int][Math]::Floor($j.run_min / 60) + "h" + [int]($j.run_min % 60) + "m" }
            elseif ($j.run_min -ge 0) { $run = [string][int]$j.run_min + "m" }
            if ($j.done_flag -eq 1) {
                $lblTitle.Text = "$($j.batch)  完成!"
                $lblInfo.Text = "$($j.results)"
            } else {
                $lblTitle.Text = "$($j.batch)  $pct%  ($($j.done)/$($j.total))"
                $lblInfo.Text = "当前: $($j.current)  $eta | 已运行 $run"
            }
        }
    } catch {}
})
$timer.Start()

$form.Add_Shown({ $form.Activate() })
[void]$form.ShowDialog()
