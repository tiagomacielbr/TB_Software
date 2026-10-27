Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Selecione o arquivo interface_clientes.py'
$dialog.Filter = 'Python (*.py)|*.py|Todos os arquivos (*.*)|*.*'
$dialog.FileName = 'interface_clientes.py'
$dialog.Multiselect = $false

if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    [System.Windows.Forms.MessageBox]::Show('Instalação cancelada. Nenhum arquivo foi selecionado.', 'TB Software')
    exit 1
}

$scriptPath = $dialog.FileName
if ([System.IO.Path]::GetFileName($scriptPath) -ne 'interface_clientes.py') {
    $answer = [System.Windows.Forms.MessageBox]::Show('O arquivo selecionado não se chama interface_clientes.py. Deseja continuar mesmo assim?', 'TB Software', 'YesNo', 'Warning')
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { exit 1 }
}

$pythonw = $null
try { $pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source } catch {}

if (-not $pythonw) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\pythonw.exe",
        "$env:ProgramFiles\Python313\pythonw.exe",
        "$env:ProgramFiles\Python312\pythonw.exe",
        "$env:ProgramFiles\Python311\pythonw.exe",
        "$env:ProgramFiles\Python310\pythonw.exe"
    )
    $pythonw = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $pythonw) {
    [System.Windows.Forms.MessageBox]::Show('Não foi possível localizar o pythonw.exe. Instale o Python e tente novamente.', 'TB Software')
    exit 1
}

$startup = [Environment]::GetFolderPath('Startup')
$vbsPath = Join-Path $startup 'TB_Software_Arranque.vbs'

$pyEscaped = $pythonw.Replace('"', '""')
$scriptEscaped = $scriptPath.Replace('"', '""')

$vbs = @"
Option Explicit
Dim shell, pythonw, scriptPath
Set shell = CreateObject("WScript.Shell")
pythonw = "$pyEscaped"
scriptPath = "$scriptEscaped"
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, False
Set shell = Nothing
"@

Set-Content -Path $vbsPath -Value $vbs -Encoding Unicode

[System.Windows.Forms.MessageBox]::Show("Arranque instalado com sucesso.`n`nArquivo selecionado:`n$scriptPath`n`nPython:`n$pythonw`n`nO TB Software será iniciado automaticamente pelo Windows sem abrir a tela preta.", 'TB Software')
