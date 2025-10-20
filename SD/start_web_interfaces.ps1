# Script de inicio rápido para las interfaces WebSocket
# Lanza los 3 servidores en terminales separadas

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  🚀 EV CHARGING SYSTEM - Quick Start" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Verificar que estamos en el directorio correcto
if (!(Test-Path "ev_charging.db")) {
    Write-Host "❌ ERROR: Database not found!" -ForegroundColor Red
    Write-Host "Please run: python init_db.py" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "✅ Database found" -ForegroundColor Green

# Verificar dependencias
Write-Host "`nChecking dependencies..." -ForegroundColor Yellow
$pipList = pip list 2>$null
if ($pipList -match "websockets" -and $pipList -match "aiohttp") {
    Write-Host "✅ WebSocket dependencies installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Installing WebSocket dependencies..." -ForegroundColor Yellow
    pip install websockets aiohttp
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  🌐 Starting Web Interfaces..." -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Lanzar EV_Driver en nueva ventana
Write-Host "🚗 Starting Driver Dashboard (Port 8001)..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python EV_Driver\EV_Driver_WebSocket.py"
Start-Sleep -Seconds 2

# Lanzar EV_Central en nueva ventana
Write-Host "🏢 Starting Central Dashboard (Port 8002)..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python EV_Central\EV_Central_WebSocket.py"
Start-Sleep -Seconds 2

# Lanzar EV_CP_M en nueva ventana
Write-Host "📊 Starting Monitor Dashboard (Port 8003)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python EV_CP_M\EV_CP_M_WebSocket.py"
Start-Sleep -Seconds 2

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ✅ ALL SERVICES STARTED!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "📱 Open these URLs in your browser:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  🚗 Driver Dashboard:  " -NoNewline
Write-Host "http://localhost:8001" -ForegroundColor Cyan
Write-Host "  🏢 Admin Dashboard:   " -NoNewline
Write-Host "http://localhost:8002" -ForegroundColor Cyan
Write-Host "  📊 Monitor Dashboard: " -NoNewline
Write-Host "http://localhost:8003" -ForegroundColor Cyan
Write-Host ""

Write-Host "🔐 Test credentials:" -ForegroundColor Yellow
Write-Host "  driver1 / pass123" -ForegroundColor White
Write-Host "  maria_garcia / maria2025" -ForegroundColor White
Write-Host ""

Write-Host "⚠️  To stop all services, close all PowerShell windows" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
