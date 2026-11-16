<#
.SYNOPSIS
  Monta (ou atualiza) a pasta de rede do Radar ICMS.

.EXAMPLE
  .\scripts\montar_rede.ps1 -Destino "\\servidor\arquivos\Radar ICMS"

  Cria Destino\app (codigo + Python portatil com as dependencias), Destino\dados e
  Destino\Radar ICMS.vbs. Rodar de novo atualiza o codigo e as dependencias e
  preserva dados\, app\python\ e app\.streamlit\secrets.toml.
  Requer internet na maquina de quem monta (Python, pip e dependencias).
  Recusa atualizar se a ferramenta estiver em uso em qualquer maquina (o Windows trava
  python.exe/pythonw.exe enquanto alguem os usa): peca para todos clicarem em
  "Encerrar ferramenta". -Forcar ignora a checagem.
#>
param(
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$VersaoPython = "3.14.6",
    [switch]$Forcar          # atualiza mesmo com a ferramenta em uso (nao recomendado)
)
$ErrorActionPreference = "Stop"

$raizRepo = Split-Path -Parent $PSScriptRoot
$app = Join-Path $Destino "app"
$py = Join-Path $app "python"
$tmp = Join-Path $env:TEMP "mapeador_montagem"
New-Item -ItemType Directory -Force $app, (Join-Path $Destino "dados"), $tmp | Out-Null

# 0. Ferramenta em uso? Abrir o executavel para escrita falha se QUALQUER maquina o
#    estiver rodando a partir da rede.
function Test-EmUso($arquivo) {
    try {
        $f = [IO.File]::Open($arquivo, 'Open', 'ReadWrite', 'None')
        $f.Close()
        return $false
    } catch [UnauthorizedAccessException] {
        throw "Sem permissao de escrita em $arquivo."
    } catch [IO.IOException] {
        return $true
    }
}
if (-not $Forcar) {
    foreach ($exe in "python.exe", "pythonw.exe") {
        $caminho = Join-Path $py $exe
        if ((Test-Path $caminho) -and (Test-EmUso $caminho)) {
            throw "A ferramenta esta em uso. Peca a todos para clicarem em 'Encerrar ferramenta' e rode de novo."
        }
    }
}

# 1. Codigo versionado (HEAD): sem .git, sem banco, sem cache.
if (git -C $raizRepo status --porcelain) {
    Write-Warning "Ha alteracoes nao commitadas: so o que esta em HEAD vai para a rede."
}
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

# 4. Atalho na raiz da pasta de rede.
Copy-Item (Join-Path $raizRepo "scripts\Radar ICMS.vbs") (Join-Path $Destino "Radar ICMS.vbs") -Force

# 5. Teste de fumaca: as bibliotecas importam no Python portatil.
& (Join-Path $py "python.exe") -c "import streamlit, pdfplumber, openpyxl; print('Python portatil OK')"
if ($LASTEXITCODE -ne 0) { throw "Falha no passo 5: teste de fumaca do Python portatil." }
Write-Host "Pronto: $Destino. Peca aos usuarios para criarem um atalho para Radar ICMS.vbs na area de trabalho."
