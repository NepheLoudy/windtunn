NUC2 - INSTALL SSH SERVER  (2 steps, 30 seconds)
=================================================

1. Plug this USB stick into the NUC.
2. Double-click:  install_ssh.bat
   - click "Yes" on the UAC prompt
   - it will open a NEW elevated window by itself

Wait until the last lines say:

   *** SSH READY ***
   service = Running   listening on port 22
   IPv4 addresses on this machine:
     192.168.138.50/24  [Ethernet]

That is success. Tell Mambo the 192.168.x.x line. Done.

-------------------------------------------------
IF SOMETHING GOES WRONG
-------------------------------------------------
"sshd.exe not found"
    -> the folder "OpenSSH" must sit right next to
       install_ssh.bat on the USB. Copy both together.

"Not running as Administrator"
    -> right-click install_ssh.bat -> Run as administrator

"SSH FAILED (service = ...)"
    -> open C:\Windows\Temp\nuc_ssh_install.log
       and send that file to Mambo.

Nothing here needs Chinese fonts, and nothing depends
on the drive letter (C:/D:/E:/F:/G: all fine).
