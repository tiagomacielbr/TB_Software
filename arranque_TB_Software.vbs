Option Explicit
Dim fso, shell, appDir, scriptPath, pythonw
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

appDir = "__APP_DIR__"
scriptPath = fso.BuildPath(appDir, "interface_clientes.py")

If Not fso.FileExists(scriptPath) Then
    MsgBox "O arquivo interface_clientes.py não foi encontrado em:" & vbCrLf & appDir, vbExclamation, "TB Software"
    WScript.Quit 1
End If

' Procura o pythonw.exe sem abrir o CMD.
pythonw = LocalizarPythonw(fso, shell)

If pythonw = "" Then
    MsgBox "Não foi possível localizar o pythonw.exe. Verifique a instalação do Python.", vbCritical, "TB Software"
    WScript.Quit 2
End If

shell.CurrentDirectory = appDir
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, False

Function LocalizarPythonw(fso, shell)
    Dim paths, pasta, candidato, pathEnv, partes, i
    LocalizarPythonw = ""

    ' 1. Pastas mais comuns de instalação do Python no Windows.
    paths = Array( _
        shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python314\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python313\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python312\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python311\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python314\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python313\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python312\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Python311\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Python314\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Python313\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Python312\pythonw.exe", _
        shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Python311\pythonw.exe" _
    )

    For Each candidato In paths
        If fso.FileExists(candidato) Then
            LocalizarPythonw = candidato
            Exit Function
        End If
    Next

    ' 2. Procura diretamente nas pastas do PATH, sem usar cmd.exe.
    pathEnv = shell.ExpandEnvironmentStrings("%PATH%")
    partes = Split(pathEnv, ";")
    For i = 0 To UBound(partes)
        pasta = Trim(partes(i))
        If Len(pasta) > 0 Then
            If Right(pasta, 1) = "\" Then
                candidato = pasta & "pythonw.exe"
            Else
                candidato = pasta & "\pythonw.exe"
            End If
            If fso.FileExists(candidato) Then
                LocalizarPythonw = candidato
                Exit Function
            End If
        End If
    Next
End Function
