# ============================================================================
# Script de Prueba Local - Sistema EV Charging
# ============================================================================
# Este script configura y arranca TODO el sistema en un solo PC (localhost)
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "     🧪 PRUEBA LOCAL - Sistema EV Charging" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Paso 1: Verificar Docker
# ============================================================================

Write-Host "🔍 Verificando Docker Desktop..." -ForegroundColor Yellow

$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Docker Desktop no está corriendo" -ForegroundColor Red
    Write-Host "   Por favor, inicia Docker Desktop y vuelve a ejecutar este script" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Docker está corriendo" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Paso 2: Configurar network_config.py para localhost
# ============================================================================

Write-Host "🔧 Configurando network_config.py para localhost..." -ForegroundColor Yellow

$networkConfigPath = ".\network_config.py"

if (Test-Path $networkConfigPath) {
    $content = Get-Content $networkConfigPath -Raw
    
    # Reemplazar IPs con localhost
    $content = $content -replace 'PC1_IP = ".*"', 'PC1_IP = "localhost"'
    $content = $content -replace 'PC2_IP = ".*"', 'PC2_IP = "localhost"'
    $content = $content -replace 'PC3_IP = ".*"', 'PC3_IP = "localhost"'
    
    $content | Set-Content $networkConfigPath -Encoding UTF8
    
    Write-Host "✅ network_config.py configurado para localhost" -ForegroundColor Green
} else {
    Write-Host "❌ ERROR: network_config.py no encontrado" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# Paso 3: Inicializar Base de Datos
# ============================================================================

Write-Host "📦 Inicializando base de datos..." -ForegroundColor Yellow

if (Test-Path ".\ev_charging.db") {
    Write-Host "⚠️  Base de datos ya existe, saltando inicialización" -ForegroundColor Yellow
} else {
    python init_db.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ERROR: No se pudo inicializar la base de datos" -ForegroundColor Red
        Write-Host "   Asegúrate de tener Python instalado" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "✅ Base de datos inicializada" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Paso 4: Limpiar contenedores anteriores (si existen)
# ============================================================================

Write-Host "🧹 Limpiando contenedores anteriores..." -ForegroundColor Yellow

docker-compose -f docker-compose.local.yml down 2>$null
Write-Host "✅ Limpieza completada" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Paso 5: Construir e Iniciar Contenedores
# ============================================================================

Write-Host "🚀 Construyendo e iniciando contenedores..." -ForegroundColor Yellow
Write-Host "   Esto puede tomar 3-5 minutos la primera vez..." -ForegroundColor Cyan
Write-Host ""

docker-compose -f docker-compose.local.yml up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ ERROR: No se pudieron iniciar los contenedores" -ForegroundColor Red
    Write-Host "   Revisa los logs con: docker-compose -f docker-compose.local.yml logs" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "✅ Contenedores iniciados" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Paso 6: Esperar a que los servicios estén listos
# ============================================================================

Write-Host "⏳ Esperando a que los servicios estén listos (60 segundos)..." -ForegroundColor Yellow

for ($i = 1; $i -le 60; $i++) {
    Write-Progress -Activity "Iniciando servicios..." -Status "Segundos transcurridos: $i/60" -PercentComplete ($i/60*100)
    Start-Sleep -Seconds 1
}

Write-Progress -Activity "Iniciando servicios..." -Completed
Write-Host ""

# ============================================================================
# Paso 7: Verificar Estado
# ============================================================================

Write-Host "🔍 Verificando estado de los contenedores..." -ForegroundColor Yellow
Write-Host ""

docker-compose -f docker-compose.local.yml ps

Write-Host ""

# ============================================================================
# Paso 8: Verificar que los servicios están accesibles
# ============================================================================

Write-Host "🧪 Probando acceso a los servicios..." -ForegroundColor Yellow
Write-Host ""

$services = @(
    @{Name="Kafka UI"; Port=8080},
    @{Name="Admin Dashboard"; Port=8002},
    @{Name="Driver Dashboard"; Port=8001},
    @{Name="Monitor Dashboard"; Port=8003}
)

foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$($service.Port)" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host "  ✅ $($service.Name) (puerto $($service.Port)): Accesible" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  $($service.Name) (puerto $($service.Port)): No responde aún" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# Finalizar
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "✅ ¡Sistema iniciado correctamente!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "🌐 ACCEDE A LAS INTERFACES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Kafka UI:         http://localhost:8080" -ForegroundColor White
Write-Host "   Admin Dashboard:  http://localhost:8002" -ForegroundColor White
Write-Host "   Driver Dashboard: http://localhost:8001" -ForegroundColor White
Write-Host "   Monitor:          http://localhost:8003" -ForegroundColor White
Write-Host ""

Write-Host "👤 USUARIOS DE PRUEBA:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   user1 / pass1  (€150.00)" -ForegroundColor White
Write-Host "   user2 / pass2  (€200.00)" -ForegroundColor White
Write-Host "   user3 / pass3  (€75.50)" -ForegroundColor White
Write-Host ""

Write-Host "📋 COMANDOS ÚTILES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Ver logs:      docker-compose -f docker-compose.local.yml logs -f" -ForegroundColor Gray
Write-Host "   Ver estado:    docker-compose -f docker-compose.local.yml ps" -ForegroundColor Gray
Write-Host "   Detener todo:  docker-compose -f docker-compose.local.yml down" -ForegroundColor Gray
Write-Host "   Reiniciar:     docker-compose -f docker-compose.local.yml restart" -ForegroundColor Gray
Write-Host ""

Write-Host "📚 GUÍA COMPLETA: PRUEBA_LOCAL.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan

# Preguntar si abrir el navegador
Write-Host ""
$openBrowser = Read-Host "¿Abrir los dashboards en el navegador? (S/N)"

if ($openBrowser -eq 'S' -or $openBrowser -eq 's') {
    Write-Host ""
    Write-Host "🌐 Abriendo navegador..." -ForegroundColor Yellow
    
    Start-Process "http://localhost:8001"
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:8002"
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:8003"
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:8080"
    
    Write-Host "✅ Pestañas abiertas" -ForegroundColor Green
}

Write-Host ""
Write-Host "¡Disfruta probando el sistema! 🎉" -ForegroundColor Green
Write-Host ""
