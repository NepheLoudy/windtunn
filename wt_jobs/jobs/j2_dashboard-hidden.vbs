' hidden wrapper: task WT_dashboard -> wscript (window style 0, no console flash)
' bWaitOnReturn=True is REQUIRED: task scheduler kills the instance's whole process
' tree the moment the action process exits, so wscript must stay alive holding the
' instance while httpd serves.
' stdout/stderr teed to out\j2_task.log (truncated per instance) for post-mortem.
' 2026-11-07 闸门: 随用随开改制 (曼波定) — 任务本体禁用需管理员权限未遂,
' flag 存在即空转秒退。手动开启走 j2_open.bat (不经本文件)。
' 恢复任务: 删 D:\WindTunnelSuite\wt_jobs\j2_task_disabled.flag 后再启用任务。
If CreateObject("Scripting.FileSystemObject").FileExists("D:\WindTunnelSuite\wt_jobs\j2_task_disabled.flag") Then WScript.Quit
Dim sh, cmd
Set sh = CreateObject("WScript.Shell")
cmd = "cmd.exe /c """"D:\WindTunnelSuite\wt_jobs\jobs\j2_dashboard.bat"" > ""D:\WindTunnelSuite\wt_jobs\out\j2_task.log"" 2>&1"""
sh.Run cmd, 0, True
