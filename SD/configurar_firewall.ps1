# Script para configurar firewall en PC2 (Central)
# Ejecutar como Administrador

Write-Host "🔥 Configurando Firewall para despliegue multi-PC..." -ForegroundColor Cyan

# Verificar privilegios de administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host "   Clic derecho -> Ejecutar como administrador" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Privilegios de administrador confirmados" -ForegroundColor Green

# Puerto 9092 - Kafka Broker
Write-Host "📡 Configurando puerto 9092 (Kafka Broker)..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Kafka Broker - EV Charging" `
    -Direction Inbound `
    -LocalPort 9092 `
    -Protocol TCP `
    -Action Allow `
    -Profile Any `
    -ErrorAction SilentlyContinue
Write-Host "   ✅ Puerto 9092 configurado" -ForegroundColor Green

# Puerto 5000 - Central Server
Write-Host "🏢 Configurando puerto 5000 (Central Server)..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Central Server - EV Charging" `
    -Direction Inbound `
    -LocalPort 5000 `
    -Protocol TCP `
    -Action Allow `
    -Profile Any `
    -ErrorAction SilentlyContinue
Write-Host "   ✅ Puerto 5000 configurado" -ForegroundColor Green

# Puerto 8002 - Admin Dashboard
Write-Host "🌐 Configurando puerto 8002 (Admin Dashboard)..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Admin Dashboard - EV Charging" `
    -Direction Inbound `
    -LocalPort 8002 `
    -Protocol TCP `
    -Action Allow `
    -Profile Any `
    -ErrorAction SilentlyContinue
Write-Host "   ✅ Puerto 8002 configurado" -ForegroundColor Green

# Puerto 8080 - Kafka UI
Write-Host "📊 Configurando puerto 8080 (Kafka UI)..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "Kafka UI - EV Charging" `
    -Direction Inbound `
    -LocalPort 8080 `
    -Protocol TCP `
    -Action Allow `
    -Profile Any `
    -ErrorAction SilentlyContinue
Write-Host "   ✅ Puerto 8080 configurado" -ForegroundColor Green

Write-Host ""
Write-Host "✅ Firewall configurado correctamente!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Puertos abiertos:" -ForegroundColor Cyan
Write-Host "   - 5000: Central Server"
Write-Host "   - 8002: Admin Dashboard"
Write-Host "   - 8080: Kafka UI"
Write-Host "   - 9092: Kafka Broker"
Write-Host ""
Write-Host "🎯 Ahora los otros PCs pueden conectarse a este PC!" -ForegroundColor Green

