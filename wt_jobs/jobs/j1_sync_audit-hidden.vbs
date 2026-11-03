' hidden wrapper: task WT_sync -> wscript (window style 0, no console flash)
' j1_sync_audit.bat: qianli sync+audit, exits when done (also double-clickable, untouched)
' bWaitOnReturn=True is REQUIRED: task scheduler kills the instance's whole process
' tree when the action process exits, so wscript must stay alive holding the instance
' while the python child runs (same pattern as j2/j4)
CreateObject("WScript.Shell").Run """D:\WindTunnelSuite\wt_jobs\jobs\j1_sync_audit.bat""", 0, True
