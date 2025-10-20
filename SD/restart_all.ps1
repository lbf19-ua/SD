# ===================================================================
# Script de reinicio para todos los servidores EV Charging
# ===================================================================

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "            🔄 REINICIANDO SERVIDORES EV CHARGING" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Activar el entorno virtual
$venvPath = "..\.venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "✅ Activando entorno virtual..." -ForegroundColor Green
    & $venvPath
} else {
    Write-Host "❌ No se encontró el entorno virtual en .venv" -ForegroundColor Red
    Write-Host "Ruta buscada: $venvPath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host "  Puertos utilizados:" -ForegroundColor Yellow
Write-Host "  - Driver:  http://localhost:8001" -ForegroundColor Yellow
Write-Host "  - Central: http://localhost:8002" -ForegroundColor Yellow
Write-Host "  - Monitor: http://localhost:8003" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host ""

# Iniciar los 3 servidores en ventanas separadas
Write-Host "🚀 Iniciando servidores..." -ForegroundColor Cyan
Write-Host ""

# Driver
Write-Host "  📱 Iniciando EV Driver..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; ..\.venv\Scripts\Activate.ps1; python .\EV_Driver\EV_Driver_WebSocket.py"
Start-Sleep -Seconds 2

# Central
Write-Host "  🏢 Iniciando EV Central..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; ..\.venv\Scripts\Activate.ps1; python .\EV_Central\EV_Central_WebSocket.py"
Start-Sleep -Seconds 2

# Monitor
Write-Host "  📊 Iniciando EV Monitor..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; ..\.venv\Scripts\Activate.ps1; python .\EV_CP_M\EV_CP_M_WebSocket.py"
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  ✅ Todos los servidores iniciados en ventanas separadas" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "📌 Interfaces web disponibles:" -ForegroundColor Cyan
Write-Host "  - Driver:  http://localhost:8001" -ForegroundColor White
Write-Host "  - Central: http://localhost:8002" -ForegroundColor White
Write-Host "  - Monitor: http://localhost:8003" -ForegroundColor White
Write-Host ""
Write-Host "🔐 Credenciales admin:" -ForegroundColor Yellow
Write-Host "  Usuario: lbf19" -ForegroundColor White
Write-Host "  Contraseña: lbf19" -ForegroundColor White
Write-Host ""
