param([string]$JsonPath = "D:\WindTunnelSuite\openfoam\airframe-sweep\progress.json",
      [string]$BatchName = "扫气批次")
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "progress"
$form.FormBorderStyle = "None"
$form.Size = New-Object System.Drawing.Size(340, 96)
$form.StartPosition = "Manual"
$form.Location = New-Object System.Drawing.Point(([System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Width - 350), 40)
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(28, 32, 40)
$form.Opacity = 0.92

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.AutoSize = $false
$lblTitle.Size = New-Object System.Drawing.Size(320, 20)
$lblTitle.Location = New-Object System.Drawing.Point(10, 6)
$lblTitle.ForeColor = [System.Drawing.Color]::FromArgb(140, 200, 255)
$lblTitle.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9, [System.Drawing.FontStyle]::Bold)
$lblTitle.Text = "$BatchName  启动中..."
$form.Controls.Add($lblTitle)

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Size = New-Object System.Drawing.Size(320, 14)
$bar.Location = New-Object System.Drawing.Point(10, 30)
$bar.Style = "Continuous"
$bar.ForeColor = [System.Drawing.Color]::FromArgb(80, 180, 120)
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
$lblClose.Size = New-Object System.Drawing.Size(20, 18)
$lblClose.Location = New-Object System.Drawing.Point(318, 2)
$lblClose.ForeColor = [System.Drawing.Color]::DimGray
$lblClose.Text = "x"
$lblClose.Cursor = "Hand"
$lblClose.Add_Click({ $form.Close() })
$form.Controls.Add($lblClose)

# 拖动无边框窗体
$form.Add_MouseDown({ $form.Drag() })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 4000
$timer.Add_Tick({
    try {
        $j = Get-Content $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $j) {
            $pct = 0
            if ($j.total -gt 0) { $pct = [int](100 * $j.done / $j.total) }
            $bar.Value = [Math]::Min(100, $pct)
            $eta = ""
            if ($j.eta_min -ge 0) {
                if ($j.eta_min -ge 60) { $eta = [string][int][Math]::Floor($j.eta_min / 60) + "h" + [int]($j.eta_min % 60) + "m" }
                else { $eta = [string][int]$j.eta_min + "m" }
                $eta = "剩余 ~$eta"
            } else { $eta = "剩余 估算中" }
            $run = ""
            if ($j.run_min -ge 60) { $run = [string][int][Math]::Floor($j.run_min / 60) + "h" + [int]($j.run_min % 60) + "m" }
            elseif ($j.run_min -ge 0) { $run = [string][int]$j.run_min + "m" }
            $lblTitle.Text = "$($j.batch)  $pct%  ($($j.done)/$($j.total))"
            $lblInfo.Text = "当前: $($j.current)`r${eta} | 已运行 $run | $j.step"
            if ($j.done_flag -eq 1) { $lblInfo.Text = "完成! $run`r$results" }
        }
    } catch {}
})
$timer.Start()

$form.Add_Shown({ $form.Activate() })
[void]$form.ShowDialog()
