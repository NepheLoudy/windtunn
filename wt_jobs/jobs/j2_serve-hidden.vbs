' J2 随用随开 (2026-11-07 曼波定): 隐藏拉起 httpd --idle-exit 30, 不常驻
' 由 j2_open.bat 在 8123 未监听时调用; 空闲 30min 无请求 httpd 自杀
CreateObject("WScript.Shell").Run """C:\Users\nebula\AppData\Local\Programs\Python\Python312\python.exe"" ""D:\WindTunnelSuite\wt_jobs\lib\httpd.py"" ""D:\WindTunnelSuite\wt_jobs\www"" 8123 --idle-exit 30", 0, False
