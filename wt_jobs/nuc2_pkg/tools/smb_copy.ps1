$sw = [Diagnostics.Stopwatch]::StartNew()
$src = 'D:\nuc_ubuntu_baseline.tar'
$dst = '\\192.168.137.28\nuc_d\nuc_ubuntu_baseline.tar'
Write-Host "src: $src"
Write-Host "dst: $dst"
Copy-Item -LiteralPath $src -Destination $dst -Force
$sw.Stop()
Write-Host ('COPY DONE in ' + [math]::Round($sw.Elapsed.TotalSeconds) + 's')
$f = Get-Item -LiteralPath $dst
Write-Host ('size: ' + [math]::Round($f.Length/1GB,1) + ' GB')
