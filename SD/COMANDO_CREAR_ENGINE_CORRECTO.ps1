# ============================================================================
# COMANDO PARA CREAR UNA NUEVA INSTANCIA DE ENGINE (CP_005)
# ============================================================================
# EJECUTAR EN PC3
# ============================================================================

# 1. Asegúrate de estar en el directorio correcto
Set-Location "C:\Users\luisb\Desktop\SD_FINAL\SD\SD"

# 2. Verifica que las imágenes estén construidas
Write-Host "Verificando imágenes Docker..." -ForegroundColor Yellow
docker images | Select-String "ev-cp-engine"

# Si no existe la imagen, construirla primero:
# docker-compose -f docker-compose.pc3.yml build ev-cp-engine-001

# 3. Obtener la IP de PC2 desde el .env o network_config.py
# Si tienes archivo .env, leer desde ahí:
if (Test-Path .\.env) {
    $envContent = Get-Content .\.env
    $kafkaBroker = ($envContent | Select-String "KAFKA_BROKER=").ToString().Split('=')[1]
} else {
    # O usar el valor por defecto de network_config.py
    $kafkaBroker = "192.168.1.235:9092"
}

Write-Host "Usando Kafka Broker: $kafkaBroker" -ForegroundColor Cyan

# 4. Crear la nueva instancia de Engine
Write-Host "`nCreando Engine CP_005..." -ForegroundColor Green

docker run -d --name ev-cp-engine-005 `
  --network ev-network `
  -p 5104:5104 `
  -e CP_ID=CP_005 `
  -e LOCATION="Parking Central" `
  -e HEALTH_PORT=5104 `
  -e KAFKA_BROKER=$kafkaBroker `
  -e PYTHONUNBUFFERED=1 `
  -v "${PWD}\ev_charging.db:/app/ev_charging.db" `
  -v "${PWD}\network_config.py:/app/network_config.py" `
  -v "${PWD}\database.py:/app/database.py" `
  -v "${PWD}\event_utils.py:/app/event_utils.py" `
  --restart unless-stopped `
  ev-cp-engine-001 `
  python -u EV_CP_E.py --no-cli --cp-id CP_005 --location "Parking Central" --health-port 5104 --kafka-broker $kafkaBroker

# 5. Verificar que se creó correctamente
Start-Sleep -Seconds 3

Write-Host "`nVerificando estado del contenedor..." -ForegroundColor Yellow
docker ps --filter "name=ev-cp-engine-005"

Write-Host "`nVerificando logs..." -ForegroundColor Yellow
docker logs ev-cp-engine-005 --tail 20

Write-Host "`n✅ Engine CP_005 creado. Accede al dashboard en:" -ForegroundColor Green
Write-Host "   http://localhost:5104" -ForegroundColor Cyan

