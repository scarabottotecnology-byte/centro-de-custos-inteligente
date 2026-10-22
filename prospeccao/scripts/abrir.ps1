# Abre o painel do Sextante. É o que o atalho da área de trabalho chama.
# Roda escondido: liga o Docker e o robô se estiverem parados e abre o painel
# no navegador. Se algo der errado, avisa numa janela.
#
# Compatível com o Windows PowerShell 5.1 (o que já vem no Windows).

$ErrorActionPreference = 'Continue'
$pasta = Split-Path -Parent $PSScriptRoot
Set-Location $pasta

function Aviso([string]$texto) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($texto, 'Sextante', 'OK', 'Warning') | Out-Null
    exit 1
}

function DockerPronto {
    & docker info 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
}

function Valor([string]$chave) {
    $linha = (Get-Content '.env') | Where-Object { $_ -like "$chave=*" } | Select-Object -First 1
    if ($linha) { return ($linha -replace "^$chave=", '').Trim() }
    return ''
}

# Primeira vez: a configuração é feita pelo INICIAR.bat, que faz as perguntas.
if (-not (Test-Path '.env')) {
    Start-Process (Join-Path $pasta 'INICIAR.bat') -WorkingDirectory $pasta
    exit 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Aviso 'O Docker Desktop não está instalado. Rode o INICIAR.bat, na pasta do Sextante, que ele mostra o que fazer.'
}
if (-not (DockerPronto)) {
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $exe) { Start-Process $exe }
    for ($i = 0; $i -lt 40 -and -not (DockerPronto); $i++) { Start-Sleep -Seconds 5 }
    if (-not (DockerPronto)) {
        Aviso 'O Docker Desktop não respondeu. Abra ele, espere o ícone da baleia ficar parado e clique no atalho de novo.'
    }
}

& docker compose up -d 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Aviso 'Não consegui ligar o robô. Rode o INICIAR.bat, na pasta do Sextante, e mande a tela para o Claude.'
}

# PROSPECTOR_PORT pode ser "8000" ou "127.0.0.1:8000"; o que importa é a porta.
$porta = (Valor 'PROSPECTOR_PORT') -replace '^.*:', ''
if (-not $porta) { $porta = '8000' }
$base = "http://localhost:$porta"

$pronto = $false
for ($i = 0; $i -lt 30 -and -not $pronto; $i++) {
    try {
        Invoke-WebRequest "$base/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
        $pronto = $true
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $pronto) {
    Aviso 'O robô ligou, mas o painel não respondeu. Espere um minuto e clique no atalho de novo.'
}

# O token vai depois do #: fica no navegador e não passa pela rede.
$token = [uri]::EscapeDataString((Valor 'PROSPECTOR_API_TOKEN'))
Start-Process "$base/painel#t=$token"
