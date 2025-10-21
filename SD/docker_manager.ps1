# ============================================================================
# Script de Construcción y Despliegue con Docker
# Sistema EV Charging Multi-PC
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("pc1", "pc2", "pc3", "all", "build", "up", "down", "logs", "status")]
    [string]$Action = "status",
    
    [Parameter(Mandatory=$false)]
    [switch]$Build,
    
    [Parameter(Mandatory=$false)]
    [switch]$Follow
)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "     DOCKER MANAGER - Sistema EV Charging" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Detectar IP local
function Get-LocalIP {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -ne "127.0.0.1"} | Select-Object -First 1).IPAddress
    return $ip
}

# Leer configuración
$networkConfigPath = ".\network_config.py"
$PC1_IP = "Unknown"
$PC2_IP = "Unknown"
$PC3_IP = "Unknown"

if (Test-Path $networkConfigPath) {
    $content = Get-Content $networkConfigPath -Raw
    
    if ($content -match 'PC1_IP = "([^"]+)"') {
        $PC1_IP = $Matches[1]
    }
    if ($content -match 'PC2_IP = "([^"]+)"') {
        $PC2_IP = $Matches[1]
    }
    if ($content -match 'PC3_IP = "([^"]+)"') {
        $PC3_IP = $Matches[1]
    }
}

$localIP = Get-LocalIP

# Determinar qué PC es este
$thisPC = "Unknown"
$composeFile = ""

if ($localIP -eq $PC2_IP) {
    $thisPC = "PC2"
    $composeFile = "docker-compose.pc2.yml"
} elseif ($localIP -eq $PC1_IP) {
    $thisPC = "PC1"
    $composeFile = "docker-compose.pc1.yml"
} elseif ($localIP -eq $PC3_IP) {
    $thisPC = "PC3"
    $composeFile = "docker-compose.pc3.yml"
}

Write-Host "🖥️  Este PC: $thisPC (IP: $localIP)" -ForegroundColor Green
Write-Host "📄 Archivo compose: $composeFile" -ForegroundColor Cyan
Write-Host ""

# Verificar Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ ERROR: Docker no está instalado o no está en PATH" -ForegroundColor Red
    Write-Host "   Instala Docker Desktop desde: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Verificar que Docker está corriendo
try {
    docker ps | Out-Null
} catch {
    Write-Host "❌ ERROR: Docker no está corriendo" -ForegroundColor Red
    Write-Host "   Inicia Docker Desktop y vuelve a intentar" -ForegroundColor Yellow
    exit 1
}

# ============================================================================
# Funciones de gestión
# ============================================================================

function Show-Status {
    param([string]$File)
    
    if (-not (Test-Path $File)) {
        Write-Host "⚠️  Archivo $File no encontrado" -ForegroundColor Yellow
        return
    }
    
    Write-Host "📊 Estado de los contenedores:" -ForegroundColor Cyan
    docker-compose -f $File ps
    Write-Host ""
    
    Write-Host "💾 Uso de recursos:" -ForegroundColor Cyan
    docker stats --no-stream
}

function Start-Services {
    param([string]$File, [bool]$BuildFlag)
    
    if (-not (Test-Path $File)) {
        Write-Host "❌ Archivo $File no encontrado" -ForegroundColor Red
        return
    }
    
    Write-Host "🚀 Iniciando servicios..." -ForegroundColor Green
    
    if ($BuildFlag) {
        Write-Host "   Construyendo imágenes..." -ForegroundColor Yellow
        docker-compose -f $File up -d --build
    } else {
        docker-compose -f $File up -d
    }
    
    Write-Host ""
    Write-Host "✅ Servicios iniciados" -ForegroundColor Green
    Show-Status $File
}

function Stop-Services {
    param([string]$File)
    
    if (-not (Test-Path $File)) {
        Write-Host "❌ Archivo $File no encontrado" -ForegroundColor Red
        return
    }
    
    Write-Host "🛑 Deteniendo servicios..." -ForegroundColor Yellow
    docker-compose -f $File down
    Write-Host "✅ Servicios detenidos" -ForegroundColor Green
}

function Show-Logs {
    param([string]$File, [bool]$FollowFlag)
    
    if (-not (Test-Path $File)) {
        Write-Host "❌ Archivo $File no encontrado" -ForegroundColor Red
        return
    }
    
    Write-Host "📋 Logs de los servicios:" -ForegroundColor Cyan
    
    if ($FollowFlag) {
        docker-compose -f $File logs -f
    } else {
        docker-compose -f $File logs --tail=50
    }
}

function Build-Images {
    param([string]$File)
    
    if (-not (Test-Path $File)) {
        Write-Host "❌ Archivo $File no encontrado" -ForegroundColor Red
        return
    }
    
    Write-Host "🔨 Construyendo imágenes..." -ForegroundColor Cyan
    docker-compose -f $File build --no-cache
    Write-Host "✅ Imágenes construidas" -ForegroundColor Green
}

# ============================================================================
# Ejecución según acción
# ============================================================================

switch ($Action) {
    "status" {
        if ($composeFile -and (Test-Path $composeFile)) {
            Show-Status $composeFile
        } else {
            Write-Host "⚠️  No se pudo determinar el archivo compose para este PC" -ForegroundColor Yellow
        }
    }
    
    "up" {
        if ($composeFile -and (Test-Path $composeFile)) {
            Start-Services $composeFile $Build
        } else {
            Write-Host "❌ No se pudo determinar el archivo compose para este PC" -ForegroundColor Red
        }
    }
    
    "down" {
        if ($composeFile -and (Test-Path $composeFile)) {
            Stop-Services $composeFile
        } else {
            Write-Host "❌ No se pudo determinar el archivo compose para este PC" -ForegroundColor Red
        }
    }
    
    "logs" {
        if ($composeFile -and (Test-Path $composeFile)) {
            Show-Logs $composeFile $Follow
        } else {
            Write-Host "❌ No se pudo determinar el archivo compose para este PC" -ForegroundColor Red
        }
    }
    
    "build" {
        if ($composeFile -and (Test-Path $composeFile)) {
            Build-Images $composeFile
        } else {
            Write-Host "❌ No se pudo determinar el archivo compose para este PC" -ForegroundColor Red
        }
    }
    
    "pc1" {
        Write-Host "🎯 Gestionando PC1..." -ForegroundColor Green
        Show-Status "docker-compose.pc1.yml"
    }
    
    "pc2" {
        Write-Host "🎯 Gestionando PC2..." -ForegroundColor Green
        Show-Status "docker-compose.pc2.yml"
    }
    
    "pc3" {
        Write-Host "🎯 Gestionando PC3..." -ForegroundColor Green
        Show-Status "docker-compose.pc3.yml"
    }
    
    "all" {
        Write-Host "🎯 Estado de todos los PCs:" -ForegroundColor Cyan
        Write-Host ""
        
        Write-Host "📍 PC1 (Driver):" -ForegroundColor Green
        if (Test-Path "docker-compose.pc1.yml") {
            docker-compose -f docker-compose.pc1.yml ps
        }
        Write-Host ""
        
        Write-Host "📍 PC2 (Central + Kafka):" -ForegroundColor Blue
        if (Test-Path "docker-compose.pc2.yml") {
            docker-compose -f docker-compose.pc2.yml ps
        }
        Write-Host ""
        
        Write-Host "📍 PC3 (Monitor):" -ForegroundColor Yellow
        if (Test-Path "docker-compose.pc3.yml") {
            docker-compose -f docker-compose.pc3.yml ps
        }
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "💡 COMANDOS DISPONIBLES:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   .\docker_manager.ps1 status          # Ver estado" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 up              # Iniciar servicios" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 up -Build       # Iniciar y construir" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 down            # Detener servicios" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 logs            # Ver logs (últimas 50 líneas)" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 logs -Follow    # Ver logs en tiempo real" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 build           # Construir imágenes" -ForegroundColor White
Write-Host "   .\docker_manager.ps1 all             # Ver estado de todos los PCs" -ForegroundColor White
Write-Host ""

if ($thisPC -eq "PC2") {
    Write-Host "🔗 Accesos rápidos (PC2):" -ForegroundColor Cyan
    Write-Host "   Kafka UI:  http://$localIP:8080" -ForegroundColor Gray
    Write-Host "   Admin:     http://$localIP:8002" -ForegroundColor Gray
} elseif ($thisPC -eq "PC1") {
    Write-Host "🔗 Acceso rápido (PC1):" -ForegroundColor Cyan
    Write-Host "   Driver:    http://$localIP:8001" -ForegroundColor Gray
} elseif ($thisPC -eq "PC3") {
    Write-Host "🔗 Acceso rápido (PC3):" -ForegroundColor Cyan
    Write-Host "   Monitor:   http://$localIP:8003" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
