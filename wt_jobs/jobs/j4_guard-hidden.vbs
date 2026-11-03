' hidden wrapper: task WT_qianli_guard -> wscript (window style 0, no console flash)
' j4_guard.bat: qianli sentinel probe+relaunch, ~30s, then exits
' bWaitOnReturn=True so the task instance outlives the 30s probe (else job-cleanup
' kills the python child mid-run when wscript exits early)
CreateObject("WScript.Shell").Run """D:\WindTunnelSuite\wt_jobs\jobs\j4_guard.bat""", 0, True
