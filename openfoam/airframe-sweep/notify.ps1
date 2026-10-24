param([string]$Title = "提醒", [string]$Body = "")
$ErrorActionPreference = "SilentlyContinue"
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml = "<toast scenario='reminder'><visual><binding template='ToastText02'><text id='1'>$Title</text><text id='2'>$Body</text></binding></visual><audio src='ms-winsoundevent:Notification.Default'/></toast>"
$x.LoadXml($xml)
$t = New-Object Windows.UI.Notifications.ToastNotification $x
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe").Show($t)
Write-Output "toast-ok"
