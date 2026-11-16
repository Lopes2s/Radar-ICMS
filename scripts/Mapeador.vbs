' Mapeador Tributario PR - atalho de duplo clique, sem janela de console.
' Fica na raiz da pasta de rede:  Mapeador.vbs, app\ (codigo + python\), dados\
Option Explicit

Dim sh, fso, raiz, python, local, ambiente
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

raiz = fso.GetParentFolderName(WScript.ScriptFullName)
python = raiz & "\app\python\pythonw.exe"

If Not fso.FileExists(python) Then
    MsgBox "Python portatil nao encontrado em:" & vbCrLf & python & vbCrLf & vbCrLf & _
           "Peca a quem mantem a ferramenta para rodar scripts\montar_rede.ps1.", 16, _
           "Mapeador Tributario PR"
    WScript.Quit 1
End If

local = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MapeadorPR"
Set ambiente = sh.Environment("Process")
ambiente("MAPEADOR_DADOS") = raiz & "\dados"           ' banco e backups: na rede
ambiente("MAPEADOR_LOCAL") = local                      ' marcador do servidor: nesta maquina
ambiente("MAPEADOR_LOGS") = local & "\logs"             ' logs: nesta maquina
ambiente("MAPEADOR_MODO_ATALHO") = "1"                  ' botao Encerrar + desliga se ociosa
ambiente("MAPEADOR_SEM_AUTOINSTALL") = "1"              ' nunca tenta instalar pelo pip
ambiente("PYTHONDONTWRITEBYTECODE") = "1"               ' varios usuarios, uma pasta: sem .pyc

' 0 = janela oculta; False = nao espera terminar
sh.Run """" & python & """ """ & raiz & "\app\iniciar.py""", 0, False
