# Liga o Sextante no Windows: confere o Docker, cria a configuração na primeira
# vez, sobe os programas, abre a tela de conexão do WhatsApp e cria o atalho
# Sextante na área de trabalho.
# Chamado pelo INICIAR.bat. Pode rodar quantas vezes quiser: o que já foi
# configurado não é perguntado de novo.
#
# Compatível com o Windows PowerShell 5.1 (o que já vem no Windows).

$ErrorActionPreference = 'Continue'
$pasta = Split-Path -Parent $PSScriptRoot
Set-Location $pasta

function Passo([string]$texto) {
    Write-Host ''
    Write-Host "==> $texto" -ForegroundColor Cyan
}

function Falha([string]$texto) {
    Write-Host ''
    Write-Host "PAROU: $texto" -ForegroundColor Red
    exit 1
}

# Sem BOM: o docker compose leria a primeira variável do .env com o BOM no nome.
function Gravar([string]$caminho, [string]$texto) {
    $texto = $texto -replace "`r`n", "`n"
    [IO.File]::WriteAllText((Join-Path $pasta $caminho), $texto, (New-Object Text.UTF8Encoding($false)))
}

function Definir([string]$texto, [string]$chave, [string]$valor) {
    $valor = $valor.Replace('$', '$$')
    return $texto -replace "(?m)^$chave=[^\r\n]*", "$chave=$valor"
}

function DockerPronto {
    & docker info 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
}

# --- 1. Docker ---------------------------------------------------------------
Passo 'Conferindo o Docker Desktop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Start-Process 'https://www.docker.com/products/docker-desktop/'
    Falha 'O Docker Desktop não está instalado. Abri a página de download: instale com as opções padrão, reinicie o PC se ele pedir e rode o INICIAR.bat de novo.'
}
if (-not (DockerPronto)) {
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $exe) {
        Write-Host 'Abrindo o Docker Desktop. Pode levar até 2 minutos...'
        Start-Process $exe
    }
    for ($i = 0; $i -lt 40 -and -not (DockerPronto); $i++) { Start-Sleep -Seconds 5 }
    if (-not (DockerPronto)) {
        Falha 'O Docker Desktop não respondeu. Abra ele, espere o ícone da baleia ficar parado e rode o INICIAR.bat de novo.'
    }
}
Write-Host 'Docker funcionando.'

# --- 2. Configuração (só na primeira vez) ------------------------------------
if (-not (Test-Path '.env')) {
    Passo 'Primeira vez: criando a configuração'
    $env_ = Get-Content '.env.example' -Raw -Encoding UTF8
    foreach ($chave in 'POSTGRES_PASSWORD', 'PROSPECTOR_API_TOKEN', 'EVOLUTION_APIKEY') {
        $env_ = Definir $env_ $chave ([guid]::NewGuid().ToString('N'))
    }
    Write-Host ''
    Write-Host 'E-mail de prospecção (opcional). Use um Gmail NOVO, só para isso, com senha de app.'
    Write-Host 'Passo a passo no WINDOWS.md, item 2. Para usar só WhatsApp, aperte Enter.'
    $gmail = (Read-Host 'Gmail de prospecção').Trim()
    if ($gmail) {
        $senha = (Read-Host 'Senha de app do Gmail (16 letras)') -replace '\s', ''
        foreach ($chave in 'SMTP_USER', 'SMTP_FROM', 'IMAP_USER') { $env_ = Definir $env_ $chave $gmail }
        foreach ($chave in 'SMTP_PASSWORD', 'IMAP_PASSWORD') { $env_ = Definir $env_ $chave $senha }
    }
    Gravar '.env' $env_
    Write-Host 'Configuração salva em .env (o robô começa em SIMULAÇÃO: não envia nada).'
}

if (-not (Test-Path 'prospeccao.yaml')) {
    Copy-Item 'prospeccao.example.yaml' 'prospeccao.yaml'
}
$yaml = Get-Content 'prospeccao.yaml' -Raw -Encoding UTF8
if ($yaml -match '55DDDNUMERO') {
    Write-Host ''
    Write-Host 'Seu WhatsApp PESSOAL recebe o aviso quando um lead responder com interesse.'
    do {
        $numero = (Read-Host 'Seu WhatsApp com DDD (ex.: 11 99999-8888)') -replace '\D', ''
        if ($numero.Length -in 10, 11) { $numero = "55$numero" }
        $ok = $numero -match '^55\d{10,11}$'
        if (-not $ok) { Write-Host 'Número inválido. Digite o DDD e o número.' -ForegroundColor Yellow }
    } until ($ok)
    Gravar 'prospeccao.yaml' ($yaml.Replace('55DDDNUMERO', $numero))
    Write-Host "Aviso de lead vai para +$numero."
}

# --- 3. Subir ----------------------------------------------------------------
Passo 'Montando e ligando os programas (na primeira vez leva uns 10 minutos)'
& docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Falha 'O docker compose falhou. Copie as mensagens acima e mande para o Claude.' }

Passo 'Preparando o banco de dados'
& docker compose run --rm cli init
if ($LASTEXITCODE -ne 0) { Falha 'Não consegui preparar o banco. Copie as mensagens acima e mande para o Claude.' }

# --- 4. WhatsApp -------------------------------------------------------------
Passo 'Preparando o WhatsApp'
$conectou = $false
for ($i = 0; $i -lt 6 -and -not $conectou; $i++) {
    if ($i -gt 0) { Write-Host 'O WhatsApp ainda está subindo, tentando de novo em 15 segundos...'; Start-Sleep -Seconds 15 }
    & docker compose run --rm cli whatsapp-conectar
    $conectou = $LASTEXITCODE -eq 0
}
$apikey = ((Get-Content '.env') | Where-Object { $_ -like 'EVOLUTION_APIKEY=*' }) -replace '^EVOLUTION_APIKEY=', ''
if ($conectou) {
    Start-Process 'http://localhost:8081/manager'
    Write-Host ''
    Write-Host 'Abri o painel do WhatsApp no navegador. Para entrar:' -ForegroundColor Green
    Write-Host '  Server URL: http://localhost:8081'
    Write-Host "  API Key:    $apikey"
    Write-Host 'Na instância "prospeccao", clique em Conectar e leia o QR code com o celular'
    Write-Host 'do CHIP DE PROSPECÇÃO (WhatsApp > Aparelhos conectados > Conectar um aparelho).'
} else {
    Write-Host 'Não consegui preparar o WhatsApp agora. Rode o INICIAR.bat de novo daqui a alguns minutos.' -ForegroundColor Yellow
}

# --- 5. Atalho na área de trabalho -------------------------------------------
Passo 'Criando o atalho Sextante na área de trabalho'
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $atalho = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Sextante.lnk'))
    $atalho.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $atalho.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $pasta 'scripts\abrir.ps1') + '"'
    $atalho.WorkingDirectory = $pasta
    $atalho.IconLocation = (Join-Path $pasta 'sextante.ico') + ',0'
    $atalho.WindowStyle = 7
    $atalho.Description = 'Abre o painel do Sextante'
    $atalho.Save()
    Write-Host 'Pronto: clique duas vezes em "Sextante" na área de trabalho para abrir o painel.'
} catch {
    Write-Host "Não consegui criar o atalho ($($_.Exception.Message)). O painel abre pelo endereço abaixo." -ForegroundColor Yellow
}

# --- 6. Pronto ---------------------------------------------------------------
Passo 'Situação atual'
& docker compose run --rm cli funil

Write-Host ''
Write-Host 'O robô está ligado em SIMULAÇÃO: faz tudo, menos enviar.' -ForegroundColor Green
Write-Host 'Agora ele baixa a base da Receita (~8 GB, pode levar 1 hora) e seleciona as empresas.'
Write-Host 'Pode fechar esta janela: ele continua rodando. Acompanhe pelo atalho Sextante.'
Write-Host 'Para ligar o envio de verdade, veja o WINDOWS.md, item 7.'

& (Join-Path $PSScriptRoot 'abrir.ps1')
