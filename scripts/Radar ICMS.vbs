' Radar ICMS - atalho de duplo clique, sem janela de console.
' Fica na raiz da pasta de rede:  Radar ICMS.vbs, programa\ (pacote .zip + versao.txt), dados\
' O programa roda de uma COPIA LOCAL (%LOCALAPPDATA%\RadarICMS\app): rodar o Python direto
' da rede leva varios minutos. Se a copia local faltar ou for de outra versao, ela e
' instalada/atualizada aqui, a partir do pacote da rede. So o banco fica na rede.
' Tudo em VBScript + tar.exe (o PowerShell e bloqueado quando chamado por .vbs em algumas
' maquinas). ASCII puro: sem acentos.
Option Explicit

Const TITULO = "Radar ICMS"

Dim sh, fso, raiz, rede, base, localApp, python, local, ambiente
Dim aviso, resultado, textoAviso
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Modo aviso: esta mesma .vbs, chamada por si mesma, so mostra uma mensagem (e e encerrada
' pela principal quando a copia termina). Assim o aviso nao bloqueia a preparacao.
If WScript.Arguments.Count >= 2 Then
    If WScript.Arguments(0) = "/aviso" Then
        MsgBox WScript.Arguments(1), 64, TITULO
        WScript.Quit 0
    End If
End If

raiz = fso.GetParentFolderName(WScript.ScriptFullName)
rede = raiz & "\programa"
base = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\RadarICMS"
localApp = base & "\app"
python = localApp & "\python\pythonw.exe"

Function VersaoDe(arquivo)
    Dim f
    VersaoDe = ""
    If fso.FileExists(arquivo) Then
        Set f = fso.OpenTextFile(arquivo, 1)
        If Not f.AtEndOfStream Then VersaoDe = Trim(f.ReadLine())
        f.Close
    End If
End Function

Sub Registrar(texto)
    Dim f
    On Error Resume Next
    If Not fso.FolderExists(base) Then fso.CreateFolder base
    Set f = fso.OpenTextFile(base & "\atualizacao.log", 8, True)
    f.WriteLine Now & " " & texto
    f.Close
End Sub

Function Atualizada()
    Atualizada = fso.FileExists(python) And (VersaoDe(base & "\versao.txt") = VersaoDe(rede & "\versao.txt"))
End Function

' Volta a pasta antiga ao lugar quando a atualizacao falha no meio.
Sub Restaurar(velho)
    On Error Resume Next
    If fso.FolderExists(velho) And Not fso.FolderExists(localApp) Then fso.MoveFolder velho, localApp
End Sub

Sub Apagar(caminho)
    On Error Resume Next
    If fso.FileExists(caminho) Then fso.DeleteFile caminho, True
    If fso.FolderExists(caminho) Then fso.DeleteFolder caminho, True
End Sub

' Instala/atualiza a copia local. Devolve 0 = pronta, 3 = copia local em uso (segue com ela),
' 1 = falha (detalhes em atualizacao.log).
Function Preparar()
    Dim trava, espera, versaoRede, pacote, zipLocal, novo, velho, tar, codigo, f
    Preparar = 1
    trava = base & "\atualizando.lock"
    zipLocal = base & "\pacote.zip"
    novo = base & "\app.novo"
    velho = base & "\app.velho"
    tar = sh.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\tar.exe"

    On Error Resume Next
    If Not fso.FolderExists(base) Then fso.CreateFolder base

    ' Dois cliques seguidos: o segundo espera o primeiro terminar (a pasta .lock e a trava).
    espera = 0
    Do
        Err.Clear
        fso.CreateFolder trava
        If Err.Number = 0 Then Exit Do
        Err.Clear
        If fso.FolderExists(trava) Then
            If DateDiff("n", fso.GetFolder(trava).DateLastModified, Now) > 25 Then Apagar trava
        End If
        WScript.Sleep 2000
        espera = espera + 2
        If espera > 1500 Then
            Registrar "FALHA: outra atualizacao demorou demais"
            Exit Function
        End If
    Loop
    If Atualizada() Then
        Apagar trava
        Preparar = 0
        Exit Function
    End If

    versaoRede = VersaoDe(rede & "\versao.txt")
    Registrar "Atualizando '" & VersaoDe(base & "\versao.txt") & "' -> '" & versaoRede & "'"
    pacote = rede & "\programa-" & versaoRede & ".zip"
    Apagar zipLocal
    Apagar novo
    Restaurar velho
    Apagar velho

    ' Primeiro a pasta antiga: mover falha por inteiro (nada apagado pela metade) se alguem
    ' estiver usando a ferramenta (o Windows trava o Python em uso). Assim nao se copia o
    ' pacote a toa; se algo falhar adiante, ela volta ao lugar.
    If fso.FolderExists(localApp) Then
        Err.Clear
        fso.MoveFolder localApp, velho
        If Err.Number <> 0 Then
            Registrar "Copia local em uso, atualizacao adiada: " & Err.Description
            Err.Clear
            Apagar trava
            Preparar = 3
            Exit Function
        End If
    End If

    Err.Clear
    fso.CopyFile pacote, zipLocal, True
    If Err.Number <> 0 Then
        Registrar "FALHA ao copiar o pacote: " & Err.Description
        Restaurar velho: Apagar trava
        Exit Function
    End If
    fso.CreateFolder novo
    codigo = sh.Run("""" & tar & """ -xf """ & zipLocal & """ -C """ & novo & """", 0, True)
    If codigo <> 0 Or Not fso.FileExists(novo & "\python\pythonw.exe") Then
        Registrar "FALHA ao extrair o pacote (tar.exe codigo " & codigo & ")"
        Apagar novo: Apagar zipLocal: Restaurar velho: Apagar trava
        Exit Function
    End If

    Err.Clear
    fso.MoveFolder novo, localApp
    If Err.Number <> 0 Then
        Registrar "FALHA ao instalar a copia local: " & Err.Description
        Restaurar velho: Apagar trava
        Exit Function
    End If
    Set f = fso.CreateTextFile(base & "\versao.txt", True)
    f.WriteLine versaoRede
    f.Close
    Apagar zipLocal
    Apagar velho
    Apagar trava
    Registrar "Pronto: " & versaoRede
    Preparar = 0
End Function

If Not fso.FileExists(rede & "\versao.txt") Then
    MsgBox "Pacote do programa nao encontrado em:" & vbCrLf & rede & vbCrLf & vbCrLf & _
           "Peca a quem mantem a ferramenta para rodar scripts\montar_rede.ps1.", 16, TITULO
    WScript.Quit 1
End If

If Not Atualizada() Then
    If Not fso.FileExists(python) Then
        textoAviso = "Preparando o Radar ICMS pela primeira vez neste computador. Isso pode levar alguns minutos e so acontece agora. Este aviso fecha sozinho quando terminar."
    Else
        textoAviso = "Atualizando o Radar ICMS. Isso pode levar alguns minutos. Este aviso fecha sozinho."
    End If
    ' Aviso nao bloqueante; se a maquina bloquear a abertura, apenas nao aparece.
    Set aviso = Nothing
    On Error Resume Next
    Set aviso = sh.Exec("wscript.exe //nologo """ & WScript.ScriptFullName & """ /aviso """ & textoAviso & """")
    On Error GoTo 0

    resultado = Preparar()

    On Error Resume Next
    If Not (aviso Is Nothing) Then aviso.Terminate
    On Error GoTo 0

    ' 3 = copia local em uso por outra sessao: segue com ela (o iniciar.py reabre o servidor).
    If resultado <> 0 And resultado <> 3 Then
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
