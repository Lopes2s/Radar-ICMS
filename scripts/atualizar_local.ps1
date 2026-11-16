<#
.SYNOPSIS
  Instala ou atualiza a copia LOCAL do Radar ICMS a partir do pacote da pasta de rede.
  Chamado pelo "Radar ICMS.vbs"; o usuario nao o executa.

  Codigos de saida: 0 = copia local pronta (atualizada ou ja estava);
                    3 = a copia local esta em uso e nao pode ser trocada agora;
                    1 = falha (detalhes em <Local>\atualizacao.log).
#>
param(
    [Parameter(Mandatory = $true)][string]$Rede,    # <pasta de rede>\programa
    [Parameter(Mandatory = $true)][string]$Local    # %LOCALAPPDATA%\RadarICMS
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Local | Out-Null
$log = Join-Path $Local "atualizacao.log"
$app = Join-Path $Local "app"
$arquivoVersao = Join-Path $Local "versao.txt"

function Registrar($texto) {
    Add-Content -LiteralPath $log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $texto)
}

$mutex = New-Object System.Threading.Mutex($false, "Local\RadarICMS-Atualizacao")
$temMutex = $false
try {
    # Dois cliques seguidos: o segundo espera o primeiro terminar e depois confere de novo.
    $temMutex = $mutex.WaitOne([TimeSpan]::FromMinutes(20))
    if (-not $temMutex) { throw "Outra atualizacao demorou demais." }

    $versaoRede = (Get-Content -LiteralPath (Join-Path $Rede "versao.txt") -Raw).Trim()
    if (-not $versaoRede) { throw "versao.txt vazio em $Rede" }
    $versaoLocal = ""
    if (Test-Path -LiteralPath $arquivoVersao) {
        $versaoLocal = (Get-Content -LiteralPath $arquivoVersao -Raw).Trim()
    }
    if ($versaoLocal -eq $versaoRede -and (Test-Path (Join-Path $app "python\pythonw.exe"))) { exit 0 }

    Registrar "Atualizando '$versaoLocal' -> '$versaoRede'"
    $pacote = Join-Path $Rede "programa-$versaoRede.zip"
    $zipLocal = Join-Path $Local "pacote.zip"
    $novo = Join-Path $Local "app.novo"
    Remove-Item -LiteralPath $zipLocal -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $novo -Recurse -Force -ErrorAction SilentlyContinue

    Copy-Item -LiteralPath $pacote -Destination $zipLocal -Force
    New-Item -ItemType Directory -Force $novo | Out-Null
    & "$env:SystemRoot\System32\tar.exe" -xf $zipLocal -C $novo
    if ($LASTEXITCODE -ne 0) { throw "tar.exe falhou ao extrair o pacote." }
    if (-not (Test-Path (Join-Path $novo "python\pythonw.exe"))) { throw "Pacote incompleto (sem python\pythonw.exe)." }

    # Trocar a pasta antiga: renomear falha por inteiro (sem apagar nada pela metade) se
    # alguem estiver usando a ferramenta (o Windows trava o Python em uso).
    $velho = Join-Path $Local "app.velho"
    Remove-Item -LiteralPath $velho -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $app) {
        try {
            Rename-Item -LiteralPath $app -NewName "app.velho"
        } catch {
            Registrar "Copia local em uso, atualizacao adiada: $($_.Exception.Message)"
            Remove-Item -LiteralPath $novo -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $zipLocal -Force -ErrorAction SilentlyContinue
            exit 3
        }
    }
    Rename-Item -LiteralPath $novo -NewName "app"
    Set-Content -LiteralPath $arquivoVersao -Value $versaoRede -Encoding ascii
    Remove-Item -LiteralPath $zipLocal -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $velho -Recurse -Force -ErrorAction SilentlyContinue
    Registrar "Pronto: $versaoRede"
    exit 0
} catch {
    Registrar "FALHA: $($_.Exception.Message)"
    exit 1
} finally {
    if ($temMutex) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
