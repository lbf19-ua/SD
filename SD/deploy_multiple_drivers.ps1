# ============================================================================
# Script para Desplegar Múltiples Drivers Simultáneamente
# ============================================================================
# Uso: .\deploy_multiple_drivers.ps1 -Count 5
# ============================================================================

param(
    [int]$Count = 3,
    [int]$StartPort = 8001,
    [string]$KafkaBroker = ""
)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "     DESPLIEGUE DE MÚLTIPLES DRIVERS" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Leer configuración de red
$networkConfigPath = ".\network_config.py"
$PC2_IP = "localhost"

if (Test-Path $networkConfigPath) {
    $content = Get-Content $networkConfigPath -Raw
    if ($content -match 'PC2_IP = "([^"]+)"') {
        $PC2_IP = $Matches[1]
    }
}

if ($KafkaBroker -eq "") {
    $KafkaBroker = "$PC2_IP:9092"
}

Write-Host "🖥️  Kafka Broker: $KafkaBroker" -ForegroundColor Green
Write-Host "📊 Drivers a desplegar: $Count" -ForegroundColor Yellow
Write-Host "🚪 Puerto inicial: $StartPort" -ForegroundColor Yellow
Write-Host ""

# Verificar que existe la imagen
Write-Host "🔍 Verificando imagen Docker..." -ForegroundColor Cyan
$imageExists = docker images | Select-String "ev-driver"

if (-not $imageExists) {
    Write-Host "❌ Imagen ev-driver no encontrada" -ForegroundColor Red
    Write-Host "   Construyendo imagen..." -ForegroundColor Yellow
    docker-compose -f docker-compose.pc1.yml build
}

Write-Host ""
Write-Host "🚀 Desplegando Drivers..." -ForegroundColor Green
Write-Host ""

# Desplegar N Drivers
$deployed = @()
for ($i = 0; $i -lt $Count; $i++) {
    $port = $StartPort + $i
    $container = "ev-driver-$i"
    
    Write-Host "Desplegando Driver $($i+1)/$Count en puerto $port..." -ForegroundColor Cyan
    
    # Detener si ya existe
    docker stop $container 2>$null | Out-Null
    docker rm $container 2>$null | Out-Null
    
    # Crear contenedor
    docker run -d `
        --name $container `
        --network host `
        -v ${PWD}/ev_charging.db:/app/data/ev_charging.db `
        -v ${PWD}/network_config.py:/app/network_config.py `
        -v ${PWD}/database.py:/app/database.py `
        -v ${PWD}/event_utils.py:/app/event_utils.py `
        -e WS_PORT=$port `
        -e KAFKA_BROKER=$KafkaBroker `
        -e PYTHONUNBUFFERED=1 `
        --restart unless-stopped `
        ev-driver:latest 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Driver $($i+1) desplegado: $container (puerto $port)" -ForegroundColor Green
        $deployed += @{
            Container = $container
            Port = $port
            URL = "http://localhost:$port"
        }
    } else {
        Write-Host "   ❌ Error al desplegar Driver $($i+1)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "✅ DESPLIEGUE COMPLETADO" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Mostrar URLs
Write-Host "🔗 URLs de acceso:" -ForegroundColor Cyan
foreach ($driver in $deployed) {
    Write-Host "   Driver $($driver.Container): $($driver.URL)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📊 Estado de contenedores:" -ForegroundColor Cyan
docker ps | Select-String "ev-driver"

Write-Host ""
Write-Host "💡 Comandos útiles:" -ForegroundColor Yellow
Write-Host "   docker logs ev-driver-0    # Ver logs del Driver 1" -ForegroundColor Gray
Write-Host "   docker stop ev-driver-1   # Detener un Driver específico" -ForegroundColor Gray
Write-Host "   docker ps | findstr ev-driver  # Ver todos los Drivers" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan

