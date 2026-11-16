' Radar ICMS - atalho de duplo clique, sem janela de console.
' Fica na raiz da pasta de rede:  Radar ICMS.vbs, programa\ (pacote .zip + versao.txt), dados\
' O programa roda de uma COPIA LOCAL (%LOCALAPPDATA%\RadarICMS\app): rodar o Python direto
' da rede leva varios minutos. Se a copia local faltar ou for de outra versao, ela e
' instalada/atualizada aqui, a partir do pacote da rede. So o banco fica na rede.
Option Explicit

Const TITULO = "Radar ICMS"

Dim sh, fso, raiz, rede, base, localApp, python, local, ambiente
Dim comando, codigo, aviso
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

raiz = fso.GetParentFolderName(WScript.ScriptFullName)
rede = raiz & "\programa"
base = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\RadarICMS"
localApp = base & "\app"
python = localApp & "\python\pythonw.exe"

If Not fso.FileExists(rede & "\versao.txt") Then
    MsgBox "Pacote do programa nao encontrado em:" & vbCrLf & rede & vbCrLf & vbCrLf & _
           "Peca a quem mantem a ferramenta para rodar scripts\montar_rede.ps1.", 16, TITULO
    WScript.Quit 1
End If

Function VersaoDe(arquivo)
    Dim f
    VersaoDe = ""
    If fso.FileExists(arquivo) Then
        Set f = fso.OpenTextFile(arquivo, 1)
        If Not f.AtEndOfStream Then VersaoDe = Trim(f.ReadLine())
        f.Close
    End If
End Function

If (Not fso.FileExists(python)) Or (VersaoDe(base & "\versao.txt") <> VersaoDe(rede & "\versao.txt")) Then
    ' Aviso nao bloqueante enquanto copia (pode levar alguns minutos). Se o mshta
    ' estiver bloqueado na maquina, apenas nao aparece.
    Set aviso = Nothing
    On Error Resume Next
    If Not fso.FileExists(python) Then
        Set aviso = sh.Exec("mshta.exe ""about:<title>Radar ICMS</title><body style='font:15px Segoe UI;margin:24px'>Preparando o Radar ICMS pela primeira vez neste computador...<br>Isso pode levar alguns minutos e so acontece agora. Esta janela fecha sozinha.</body><script>window.resizeTo(520,170)</script>""")
    Else
        Set aviso = sh.Exec("mshta.exe ""about:<title>Radar ICMS</title><body style='font:15px Segoe UI;margin:24px'>Atualizando o Radar ICMS...<br>Esta janela fecha sozinha.</body><script>window.resizeTo(520,150)</script>""")
    End If
    On Error GoTo 0

    comando = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & _
              rede & "\atualizar_local.ps1"" -Rede """ & rede & """ -Local """ & base & """"
    codigo = sh.Run(comando, 0, True)

    On Error Resume Next
    If Not (aviso Is Nothing) Then aviso.Terminate
    On Error GoTo 0

    ' 3 = copia local em uso por outra sessao: segue com ela (o iniciar.py reabre o servidor).
    If codigo <> 0 And codigo <> 3 Then
        MsgBox "Nao foi possivel preparar o Radar ICMS neste computador." & vbCrLf & vbCrLf & _
               "Detalhes em:" & vbCrLf & base & "\atualizacao.log", 16, TITULO
        WScript.Quit 1
    End If
    If Not fso.FileExists(python) Then
        MsgBox "Python local nao encontrado em:" & vbCrLf & python, 16, TITULO
        WScript.Quit 1
    End If
End If

local = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\MapeadorPR"
Set ambiente = sh.Environment("Process")
ambiente("MAPEADOR_DADOS") = raiz & "\dados"           ' banco e backups: na rede
ambiente("MAPEADOR_LOCAL") = local                      ' marcador do servidor: nesta maquina
ambiente("MAPEADOR_LOGS") = local & "\logs"             ' logs: nesta maquina
ambiente("MAPEADOR_MODO_ATALHO") = "1"                  ' botao Encerrar + desliga se ociosa
ambiente("MAPEADOR_SEM_AUTOINSTALL") = "1"              ' nunca tenta instalar pelo pip

' 0 = janela oculta; False = nao espera terminar
sh.Run """" & python & """ """ & localApp & "\iniciar.py""", 0, False
