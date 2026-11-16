<#
.SYNOPSIS
  Monta (ou atualiza) a pasta de rede do Radar ICMS.

.EXAMPLE
  .\scripts\montar_rede.ps1 -Destino "\\servidor\arquivos\Radar ICMS"

  Monta o programa (codigo + Python portatil com as dependencias) numa pasta LOCAL desta
  maquina, empacota num unico .zip e publica em Destino\programa\, junto com
  Destino\Radar ICMS.vbs e Destino\dados\. Cada usuario, ao abrir o .vbs, baixa o pacote
  para a propria maquina (so quando a versao muda). Rodar de novo publica uma versao nova
  e preserva dados\. Pode rodar com a ferramenta em uso: ninguem executa arquivos da rede.
  Requer internet na maquina de quem monta (Python, pip e dependencias).
#>
param(
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$VersaoPython = "3.14.6"
)
$ErrorActionPreference = "Stop"

$raizRepo = Split-Path -Parent $PSScriptRoot
$pasta = Join-Path $env:LOCALAPPDATA "RadarICMS-montagem"   # local: montar na rede seria lento
$app = Join-Path $pasta "app"
$py = Join-Path $app "python"
$tmp = Join-Path $env:TEMP "radar_icms_montagem"
$programa = Join-Path $Destino "programa"
New-Item -ItemType Directory -Force $app, $tmp, $programa, (Join-Path $Destino "dados") | Out-Null

# 1. Codigo versionado (HEAD): sem .git, sem banco, sem cache. Apaga o codigo antigo
#    (menos o python\) para nao sobrar arquivo de versao anterior.
if (git -C $raizRepo status --porcelain) {
    Write-Warning "Ha alteracoes nao commitadas: so o que esta em HEAD vai para o pacote."
}
Get-ChildItem $app -Force | Where-Object { $_.Name -ne "python" } |
    Remove-Item -Recurse -Force
$zipCodigo = Join-Path $tmp "codigo.zip"
Remove-Item $zipCodigo -Force -ErrorAction SilentlyContinue   # nunca reaproveitar zip antigo
git -C $raizRepo archive --format=zip -o $zipCodigo HEAD
if ($LASTEXITCODE -ne 0) { throw "Falha no passo 1: git archive nao gerou o codigo." }
Expand-Archive $zipCodigo -DestinationPath $app -Force

# 2. Python portatil (embeddable), so na primeira vez.
if (-not (Test-Path (Join-Path $py "python.exe"))) {
    $zipPython = Join-Path $tmp "python-embed.zip"
    Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$VersaoPython/python-$VersaoPython-embed-amd64.zip" -OutFile $zipPython
    Expand-Archive $zipPython -DestinationPath $py -Force

    # O ._pth restringe o sys.path: inclui a pasta do codigo (..), o site-packages e o site.
    $pth = Get-ChildItem $py -Filter "python*._pth" | Select-Object -First 1
    Set-Content $pth.FullName -Encoding ascii -Value @(
        "$($pth.BaseName).zip", ".", "..", "Lib\site-packages", "import site")

    $getPip = Join-Path $tmp "get-pip.py"
    Invoke-WebRequest -UseBasicParsing "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
    & (Join-Path $py "python.exe") $getPip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "Falha no passo 2: instalacao do pip (get-pip.py)." }
}

# 3. Dependencias, sempre pelo requirements.txt (fonte unica das versoes).
& (Join-Path $py "python.exe") -m pip install -r (Join-Path $app "requirements.txt") --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Falha no passo 3: pip install -r requirements.txt." }

# 4. Teste de fumaca: as bibliotecas importam no Python portatil.
& (Join-Path $py "python.exe") -c "import streamlit, pdfplumber, openpyxl; print('Python portatil OK')"
if ($LASTEXITCODE -ne 0) { throw "Falha no passo 4: teste de fumaca do Python portatil." }

# 5. Pacote unico (.zip) e publicacao na rede. O pacote tem nome com a versao e o
#    versao.txt e gravado por ultimo: quem le versao.txt sempre encontra o pacote inteiro.
$versaoApp = (& (Join-Path $py "python.exe") -c "import sys; sys.path.insert(0, r'$app'); from core.versao import VERSAO_APP; print(VERSAO_APP)").Trim()
$hash = (git -C $raizRepo rev-parse --short HEAD).Trim()
$versao = "{0}-{1}-{2:yyyyMMddHHmmss}" -f $versaoApp, $hash, (Get-Date)
$zipPacote = Join-Path $tmp "programa-$versao.zip"
& "$env:SystemRoot\System32\tar.exe" -a -c -f $zipPacote -C $app .
if ($LASTEXITCODE -ne 0) { throw "Falha no passo 5: tar.exe nao gerou o pacote." }

$destinoPacote = Join-Path $programa "programa-$versao.zip"
Copy-Item $zipPacote "$destinoPacote.tmp" -Force
Move-Item "$destinoPacote.tmp" $destinoPacote -Force
Set-Content (Join-Path $programa "versao.txt") -Value $versao -Encoding ascii
# pacotes de versoes anteriores (quem ainda estiver lendo um deles pode impedir a remocao: ignora)
Get-ChildItem $programa -Filter "programa-*.zip" | Where-Object { $_.Name -ne "programa-$versao.zip" } |
    Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item $zipPacote, $zipCodigo -Force -ErrorAction SilentlyContinue

# 6. Atalho na raiz da pasta de rede.
Copy-Item (Join-Path $raizRepo "scripts\Radar ICMS.vbs") (Join-Path $Destino "Radar ICMS.vbs") -Force

if (Test-Path (Join-Path $Destino "app")) {
    Write-Warning "A pasta '$Destino\app' e do modelo antigo e nao e mais usada: pode apagar."
}
Write-Host "Pronto: $Destino (versao $versao). Peca aos usuarios para criarem um atalho para Radar ICMS.vbs na area de trabalho."
