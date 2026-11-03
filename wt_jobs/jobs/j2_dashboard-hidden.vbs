' hidden wrapper: task WT_dashboard -> wscript (window style 0, no console flash)
' bWaitOnReturn=True is REQUIRED: task scheduler kills the instance's whole process
' tree the moment the action process exits, so wscript must stay alive holding the
' instance while httpd serves.
' stdout/stderr teed to out\j2_task.log (truncated per instance) for post-mortem.
Dim sh, cmd
Set sh = CreateObject("WScript.Shell")
cmd = "cmd.exe /c """"D:\WindTunnelSuite\wt_jobs\jobs\j2_dashboard.bat"" > ""D:\WindTunnelSuite\wt_jobs\out\j2_task.log"" 2>&1"""
sh.Run cmd, 0, True
