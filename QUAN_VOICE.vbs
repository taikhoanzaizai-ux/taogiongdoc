Option Explicit
Dim shell, files, root, command, code
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & root & "\windows\setup-windows.ps1"" -Profile recommended -Desktop"
code = shell.Run(command, 0, True)
If code <> 0 Then
  shell.Popup "Khong mo duoc Studio. Nhat ky: " & root & "\data\bootstrap. Hoac chay CHAN_DOAN.bat.", 0, "QUAN Voice Studio", 16
End If
