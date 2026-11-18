# Генерирует deploy/secrets.env со случайными паролями и копирует публичный SSH-ключ
# администратора в deploy/keys/admin.pub. Запуск из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File deploy\new-secrets.ps1

$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$secrets = Join-Path $deploy 'secrets.env'

function New-Secret([int]$bytes = 24) {
    $buf = New-Object byte[] $bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    # URL-safe base64 без символов, требующих экранирования в shell и строке подключения
    return [Convert]::ToBase64String($buf).Replace('+', 'A').Replace('/', 'B').TrimEnd('=')
}

if (Test-Path $secrets) {
    Write-Host "secrets.env уже существует — не перезаписываю: $secrets"
} else {
    $content = @(
        "DB_MIGRATOR_PASSWORD=$(New-Secret)"
        "DB_APP_PASSWORD=$(New-Secret)"
        "SECRET_KEY=$(New-Secret 32)"
        "ADMIN_USERNAME=admin"
        "ADMIN_PASSWORD=$(New-Secret 9)"
    ) -join "`n"
    [IO.File]::WriteAllText($secrets, $content + "`n", (New-Object Text.UTF8Encoding $false))
    Write-Host "Создан $secrets"
}

$sshDir = Join-Path $env:USERPROFILE '.ssh'
$pub = Join-Path $sshDir 'id_ed25519.pub'
if (-not (Test-Path $pub)) {
    New-Item -ItemType Directory -Force $sshDir | Out-Null
    ssh-keygen -t ed25519 -f (Join-Path $sshDir 'id_ed25519') -C 'musicstore-admin'
}
New-Item -ItemType Directory -Force (Join-Path $deploy 'keys') | Out-Null
Copy-Item $pub (Join-Path $deploy 'keys\admin.pub') -Force
Write-Host "Публичный ключ скопирован в deploy\keys\admin.pub"
