# 🚗 INICIO MANUAL DE SERVICIOS - Sin Kafka

Write-Host "🚀 Sistema EV Charging - Despliegue Local" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  Kafka no está disponible - modo sin eventos" -ForegroundColor Yellow
Write-Host ""

Write-Host "✅ EV_Central ya está corriendo en puerto 8002" -ForegroundColor Green
Write-Host "   http://localhost:8002" -ForegroundColor Blue
Write-Host ""

Write-Host "📋 Para completar el despliegue, abre 2 terminales más:" -ForegroundColor Cyan
Write-Host ""

Write-Host "Terminal 1 - Monitor:" -ForegroundColor Green
Write-Host "  cd C:\Users\luisb\Desktop\SD\SD" -ForegroundColor Gray
Write-Host "  C:\Users\luisb\Desktop\SD\.venv\Scripts\python.exe EV_CP_M\EV_CP_M_WebSocket.py" -ForegroundColor Gray
Write-Host ""

Write-Host "Terminal 2 - Driver:" -ForegroundColor Magenta
Write-Host "  cd C:\Users\luisb\Desktop\SD\SD" -ForegroundColor Gray  
Write-Host "  C:\Users\luisb\Desktop\SD\.venv\Scripts\python.exe EV_Driver\EV_Driver_WebSocket.py" -ForegroundColor Gray
Write-Host ""

Write-Host "🌐 Acceso a interfaces:" -ForegroundColor Cyan
Write-Host "  Driver:  http://localhost:8001" -ForegroundColor Magenta
Write-Host "  Admin:   http://localhost:8002" -ForegroundColor Blue
Write-Host "  Monitor: http://localhost:8003" -ForegroundColor Green
Write-Host ""

Write-Host "👤 Login:" -ForegroundColor Yellow
Write-Host "  Usuario: user01" -ForegroundColor Gray
Write-Host "  Password: password" -ForegroundColor Gray
Write-Host ""
