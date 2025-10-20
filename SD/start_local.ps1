# 🚀 INICIO RÁPIDO LOCAL (Sin Kafka)
# Este script inicia todos los componentes para prueba local SIN Kafka

Write-Host "🚀 DESPLIEGUE LOCAL - Sistema EV Charging" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Variables
$PROJECT_DIR = "C:\Users\luisb\Desktop\SD\SD"
$VENV_PYTHON = "C:\Users\luisb\Desktop\SD\.venv\Scripts\python.exe"

# Función para abrir terminal
function Start-Component {
    param(
        [string]$Title,
        [string]$Script,
        [string]$Color
    )
    
    Write-Host "▶️  Iniciando: $Title" -ForegroundColor $Color
    
    $command = "cd '$PROJECT_DIR' ; `$host.UI.RawUI.WindowTitle = '$Title' ; & '$VENV_PYTHON' '$Script'"
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command
    
    Start-Sleep -Seconds 2
}

Write-Host "⚠️  NOTA: Este script omite Kafka para prueba rápida local" -ForegroundColor Yellow
Write-Host "   Los eventos no se publicarán en Kafka, pero las interfaces funcionarán" -ForegroundColor Yellow
Write-Host ""
Write-Host "📋 Se abrirán 4 terminales:" -ForegroundColor Green
Write-Host "   1. EV_Central (puerto 8002)" -ForegroundColor Green
Write-Host "   2. EV_CP_E Engine (puerto 5004)" -ForegroundColor Green
Write-Host "   3. EV_CP_M Monitor (puerto 8003)" -ForegroundColor Green
Write-Host "   4. EV_Driver (puerto 8001)" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host ""
Write-Host "🔄 Iniciando componentes..." -ForegroundColor Cyan
Write-Host ""

# Iniciar componentes en orden
Start-Component -Title "EV_Central WebSocket" -Script "EV_Central\EV_Central_WebSocket.py" -Color "Blue"
Start-Component -Title "EV_CP_E Engine" -Script "EV_CP_E\EV_CP_E.py" -Color "Yellow"
Start-Component -Title "EV_CP_M Monitor" -Script "EV_CP_M\EV_CP_M_WebSocket.py" -Color "Green"
Start-Component -Title "EV_Driver" -Script "EV_Driver\EV_Driver_WebSocket.py" -Color "Magenta"

Write-Host ""
Write-Host "✅ Todos los componentes iniciados!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Accede a las interfaces web:" -ForegroundColor Cyan
Write-Host "   🚗 Driver:  http://localhost:8001" -ForegroundColor Magenta
Write-Host "   👨‍💼 Admin:   http://localhost:8002" -ForegroundColor Blue
Write-Host "   📊 Monitor: http://localhost:8003" -ForegroundColor Green
Write-Host ""
Write-Host "👤 Login de prueba:" -ForegroundColor Yellow
Write-Host "   Usuario: user01" -ForegroundColor Yellow
Write-Host "   Contraseña: password" -ForegroundColor Yellow
Write-Host ""
Write-Host "⏹️  Para detener: Cierra cada terminal con Ctrl+C" -ForegroundColor Red
Write-Host ""
Write-Host "Presiona cualquier tecla para abrir navegador..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Abrir navegador con las 3 interfaces
Start-Process "http://localhost:8001"
Start-Sleep -Seconds 1
Start-Process "http://localhost:8002"
Start-Sleep -Seconds 1
Start-Process "http://localhost:8003"

Write-Host ""
Write-Host "✨ ¡Sistema desplegado localmente!" -ForegroundColor Green
Write-Host ""
