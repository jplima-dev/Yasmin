Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
ScriptPath = Fso.BuildPath(Fso.GetParentFolderName(WScript.ScriptFullName), "iniciar_yasm.bat")
LauncherPath = Fso.BuildPath(Fso.BuildPath(Fso.GetParentFolderName(WScript.ScriptFullName), "Agent"), "launcher.py")
If Not Fso.FileExists(ScriptPath) Or Not Fso.FileExists(LauncherPath) Then
    MsgBox "Inicializador ou Agent\launcher.py nao encontrado ao lado deste arquivo.", 16, "Yasmin"
    WScript.Quit 1
End If
WshShell.Run Chr(34) & ScriptPath & Chr(34), 0, False
