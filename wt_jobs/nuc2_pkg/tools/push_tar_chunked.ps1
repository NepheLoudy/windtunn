# Chunked push: split tar into 1GB parts, scp each (resumable), verify sizes.
$ErrorActionPreference = 'Continue'
$src = 'D:\nuc_ubuntu_baseline.tar'
$remote = 'lenovo@192.168.137.28'
$rdir = 'D:/nuc_parts'
$total = (Get-Item $src).Length
$CH = 1GB
$parts = [math]::Ceiling($total / $CH)
Write-Host "total $([math]::Round($total/1GB,2)) GB -> $parts parts"

# remote mkdir
ssh -o StrictHostKeyChecking=no $remote "if not exist D:\nuc_parts mkdir D:\nuc_parts" | Out-Null

$ok = 0
for ($i = 0; $i -lt $parts; $i++) {
    $pi = '{0:D3}' -f $i
    $lsrc = "D:\nuc_parts\part_$pi"
    $fail = 0
    while ($fail -lt 3) {
        # extract part i from source via fsutil (no split cmd on PS) - use .NET stream
        if (-not (Test-Path $lsrc)) {
            $in = [System.IO.File]::OpenRead($src)
            $out = [System.IO.File]::Create($lsrc)
            $in.Position = [long]$i * $CH
            $remain = [math]::Min($CH, $total - $in.Position)
            $buf = New-Object byte[] (4MB)
            while ($remain -gt 0) {
                $n = $in.Read($buf, 0, [math]::Min($buf.Length, $remain))
                if ($n -le 0) { break }
                $out.Write($buf, 0, $n)
                $remain -= $n
            }
            $out.Close(); $in.Close()
        }
        $lsz = (Get-Item $lsrc).Length
        # push
        scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 $lsrc "${remote}:${rdir}/part_$pi"
        # verify remote size
        $rsz = [long](ssh -o StrictHostKeyChecking=no $remote "for %F in (D:\nuc_parts\part_$pi) do @echo %~zF")
        if ($rsz -eq $lsz) { Write-Host "part $pi OK ($lsz)"; $ok++; break }
        else { Write-Host "part $pi mismatch (local=$lsz remote=$rsz) retry $($fail+1)"; $fail++ }
    }
    if ($fail -ge 3) { Write-Host "PART $pi FAILED 3x - ABORT"; exit 1 }
    Remove-Item $lsrc -Force -ErrorAction SilentlyContinue
}
Write-Host "ALL $ok/$parts parts pushed"
# remote: merge + import
Write-Host '=== remote merge ==='
ssh $remote "cmd /c copy /b D:\nuc_parts\part_* D:\nuc_ubuntu_baseline.tar" | Select-Object -Last 1
ssh $remote "cmd /c for %F in (D:\nuc_ubuntu_baseline.tar) do @echo merged=%~zF"
