# Script de verificación de conectividad - Ejecutar en PC del Driver

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "  Verificación de Conectividad" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

$centralIP = "172.20.10.8"
$kafkaPort = 9092

# 1. Verificar ping
Write-Host "1. Ping a Central ($centralIP)..." -ForegroundColor Yellow
$pingResult = Test-Connection -ComputerName $centralIP -Count 2 -Quiet
if ($pingResult) {
    Write-Host "   ✅ Ping OK" -ForegroundColor Green
} else {
    Write-Host "   ❌ No hay conectividad" -ForegroundColor Red
    Write-Host "   → Verifica que ambos PCs estén en la misma red" -ForegroundColor Yellow
}

# 2. Verificar puerto Kafka
Write-Host "`n2. Puerto Kafka ($centralIP`:$kafkaPort)..." -ForegroundColor Yellow
$kafkaResult = Test-NetConnection -ComputerName $centralIP -Port $kafkaPort -InformationLevel Quiet -WarningAction SilentlyContinue
if ($kafkaResult) {
    Write-Host "   ✅ Puerto 9092 accesible" -ForegroundColor Green
} else {
    Write-Host "   ❌ Puerto 9092 NO accesible" -ForegroundColor Red
    Write-Host "   → Verifica firewall en PC2 (Central)" -ForegroundColor Yellow
}

# 3. Verificar dependencias Python
Write-Host "`n3. Dependencias Python..." -ForegroundColor Yellow
try {
    $kafka = python -c "import kafka; print('kafka-python')" 2>&1
    $websockets = python -c "import websockets; print('websockets')" 2>&1
    $aiohttp = python -c "import aiohttp; print('aiohttp')" 2>&1
    
    Write-Host "   ✅ Kafka: Instalado" -ForegroundColor Green
    Write-Host "   ✅ WebSockets: Instalado" -ForegroundColor Green
    Write-Host "   ✅ aiohttp: Instalado" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Dependencias faltantes" -ForegroundColor Red
    Write-Host "   → Ejecuta: pip install kafka-python websockets aiohttp" -ForegroundColor Yellow
}

# 4. Verificar network_config.py
Write-Host "`n4. Verificando network_config.py..." -ForegroundColor Yellow
if (Test-Path "network_config.py") {
    $content = Get-Content "network_config.py" -Raw
    if ($content -match "PC2_IP = [`"']172.20.10.8[`"']") {
        Write-Host "   ✅ PC2_IP configurado correctamente" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  PC2_IP NO es 172.20.10.8" -ForegroundColor Yellow
        Write-Host "   → Actualiza network_config.py" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ network_config.py no encontrado" -ForegroundColor Red
}

# Resumen
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

if ($pingResult -and $kafkaResult) {
    Write-Host "✅ Conexión OK - Puedes ejecutar el Driver" -ForegroundColor Green
    Write-Host "`nEjecuta:" -ForegroundColor Cyan
    Write-Host "   cd EV_Driver" -ForegroundColor White
    Write-Host "   python EV_Driver_WebSocket.py" -ForegroundColor White
} else {
    Write-Host "❌ Hay problemas de conectividad" -ForegroundColor Red
    Write-Host "`nSiguiente paso:" -ForegroundColor Cyan
    Write-Host "   1. Verifica que el Central esté corriendo" -ForegroundColor White
    Write-Host "   2. Abre el firewall en el PC del Central (puerto 9092)" -ForegroundColor White
    Write-Host "   3. Verifica que ambos PCs estén en la misma red" -ForegroundColor White
}

Write-Host ""


