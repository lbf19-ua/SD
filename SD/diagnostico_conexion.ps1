# Script de diagnóstico para verificar conexión entre Driver y Central

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Diagnóstico de Conexión: Driver ↔ Central" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar que los contenedores están corriendo
Write-Host "1. Verificando contenedores..." -ForegroundColor Yellow
$driver = docker ps -a | Select-String "ev-driver" | Select-Object -First 1
$central = docker ps -a | Select-String "ev-central" | Select-Object -First 1

if ($driver -and $central) {
    Write-Host "✅ Contenedores encontrados" -ForegroundColor Green
    Write-Host "   Driver: $driver"
    Write-Host "   Central: $central"
} else {
    Write-Host "❌ Contenedores no encontrados" -ForegroundColor Red
}
Write-Host ""

# 2. Verificar conectividad a Kafka
Write-Host "2. Verificando conectividad a Kafka en PC2..." -ForegroundColor Yellow
$kafkaIP = "192.168.1.235"
$kafkaPort = 9092

$result = Test-NetConnection -ComputerName $kafkaIP -Port $kafkaPort -InformationLevel Quiet -WarningAction SilentlyContinue
if ($result) {
    Write-Host "✅ Conexión a Kafka OK ($kafkaIP:$kafkaPort)" -ForegroundColor Green
} else {
    Write-Host "❌ No se puede conectar a Kafka en $kafkaIP:$kafkaPort" -ForegroundColor Red
    Write-Host "   Verifica que PC2 está encendido y Kafka está corriendo" -ForegroundColor Yellow
}
Write-Host ""

# 3. Ver logs del Driver
Write-Host "3. Últimos logs del Driver:" -ForegroundColor Yellow
Write-Host "   (Buscando envíos a Kafka y respuestas recibidas)" -ForegroundColor Gray
Write-Host "---" -ForegroundColor DarkGray
docker logs ev-driver --tail 30 2>&1 | Select-String -Pattern "Kafka broker|Solicitando|✅|AUTHORIZATION|📨|📤|Error" | ForEach-Object { Write-Host $_ }
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# 4. Ver logs de Central
Write-Host "4. Últimos logs de Central:" -ForegroundColor Yellow
Write-Host "   (Buscando recepción de eventos y publicaciones)" -ForegroundColor Gray
Write-Host "---" -ForegroundColor DarkGray
docker logs ev-central --tail 30 2>&1 | Select-String -Pattern "Kafka|AUTHORIZATION|📨|📤|Published|Received|Error|Consumer|producer" | ForEach-Object { Write-Host $_ }
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# 5. Verificar topics de Kafka
Write-Host "5. Verificando topics de Kafka..." -ForegroundColor Yellow
Write-Host "   Abre http://192.168.1.235:8080 en tu navegador" -ForegroundColor Cyan
Write-Host "   Busca los topics: driver-events, central-events" -ForegroundColor Cyan
Write-Host ""

# 6. Resumen
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Si ves:" -ForegroundColor Yellow
Write-Host "  ✅ [DRIVER] 🔐 Solicitando autorización" -ForegroundColor Green
Write-Host "  ❌ Pero NO ves [CENTRAL] 📨 Received event" -ForegroundColor Red
Write-Host "  → Central no está recibiendo los mensajes" -ForegroundColor Red
Write-Host ""
Write-Host "Si ves:" -ForegroundColor Yellow
Write-Host "  ✅ [CENTRAL] 📨 Received event" -ForegroundColor Green
Write-Host "  ❌ Pero NO ves [CENTRAL] 📤 Published" -ForegroundColor Red
Write-Host "  → Central no está enviando respuestas" -ForegroundColor Red
Write-Host ""
Write-Host "Si ves TODO:" -ForegroundColor Yellow
Write-Host "  ✅ [DRIVER] 🔐 Solicitando" -ForegroundColor Green
Write-Host "  ✅ [CENTRAL] 📨 Received" -ForegroundColor Green
Write-Host "  ✅ [CENTRAL] 📤 Published" -ForegroundColor Green
Write-Host "  ✅ [DRIVER] ✅ Central autorizó" -ForegroundColor Green
Write-Host "  → ¡TODO FUNCIONA! 🎉" -ForegroundColor Green
Write-Host ""




