# 📦 INSTALACIÓN AUTOMÁTICA DE PAQUETES DURANTE DOCKER-COMPOSE

## ✅ Configuración Actualizada

Todos los Dockerfiles ahora instalan automáticamente los paquetes especificados en `requirements.txt` durante el build.

---

## 🔧 ¿Qué se ha corregido?

### 1. **Dockerfiles Corregidos**

Los siguientes Dockerfiles ahora copian correctamente `requirements.txt` desde el contexto raíz:

- ✅ `EV_Driver/Dockerfile`
- ✅ `EV_CP_M/Dockerfile`  
- ✅ `EV_Central/Dockerfile` (ya estaba correcto)

### 2. **Contexto de Build**

Todos los `docker-compose.yml` usan el contexto raíz (`.`) para que Docker pueda copiar `requirements.txt`:

```yaml
build:
  context: .          # ← Directorio raíz SD/
  dockerfile: EV_Driver/Dockerfile
```

### 3. **Instalación Automática**

Cuando ejecutes `docker-compose build` o `docker-compose up --build`, verás:

```bash
Step 1/10 : COPY requirements.txt /app/requirements.txt
Step 2/10 : RUN pip install --no-cache-dir -r requirements.txt
...
Installing kafka-python==2.0.2
Installing websockets==12.0
Installing aiohttp==3.9.1
...
Successfully installed kafka-python-2.0.2 websockets-12.0 aiohttp-3.9.1 ...
```

---

## 📋 Paquetes Instalados

El archivo `requirements.txt` incluye:

```txt
# Kafka Client
kafka-python==2.0.2

# WebSocket Server
websockets==12.0
aiohttp==3.9.1

# Dependencias de aiohttp
aiosignal==1.3.1
frozenlist==1.4.0
multidict==6.0.4
yarl==1.9.2
attrs==23.1.0

# Async support
async-timeout==4.0.3

# Terminal colors
colorama==0.4.6
```

---

## 🚀 Cómo se Instalan

### Durante el Build

Cuando ejecutes:

```powershell
# PC2
docker-compose -f docker-compose.pc2.yml up -d --build

# PC1
docker-compose -f docker-compose.pc1.yml up -d --build

# PC3
docker-compose -f docker-compose.pc3.yml up -d --build
```

**Docker automáticamente:**

1. Copia `requirements.txt` desde el directorio raíz (`SD/`)
2. Ejecuta `pip install -r requirements.txt` dentro del contenedor
3. Instala todos los paquetes en una capa cacheable

### Líneas en cada Dockerfile

```dockerfile
# Copiar requirements primero (para aprovechar cache de Docker)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
```

**Ventaja:** Docker cachea las capas. Si `requirements.txt` no cambia, no reinstala los paquetes.

---

## 📂 Estructura Esperada

Para que funcione correctamente, ejecuta docker-compose **desde el directorio SD/**:

```
SD/
├── requirements.txt              ← Desde aquí se copia
├── docker-compose.pc1.yml
├── docker-compose.pc2.yml
├── docker-compose.pc3.yml
│
├── EV_Driver/
│   └── Dockerfile                ← Copia requirements.txt
│
├── EV_Central/
│   └── Dockerfile                ← Copia requirements.txt
│
└── EV_CP_M/
    └── Dockerfile                ← Copia requirements.txt
```

---

## ✅ Verificación

### 1. Ver paquetes instalados en el contenedor

```powershell
# Conectarse al contenedor
docker exec -it ev-central bash

# Ver paquetes instalados
pip list

# Deberías ver:
# kafka-python       2.0.2
# websockets         12.0
# aiohttp            3.9.1
# aiosignal          1.3.1
# ...
```

### 2. Verificar durante el build

```powershell
docker-compose -f docker-compose.pc2.yml build

# Deberías ver en la salida:
# => [internal] load build definition from Dockerfile
# => [internal] load .dockerignore
# => [internal] load metadata for docker.io/library/python:3.11-slim
# => [1/10] FROM docker.io/library/python:3.11-slim
# ...
# => [4/10] COPY requirements.txt /app/requirements.txt
# => [5/10] RUN pip install --no-cache-dir -r requirements.txt
# Collecting kafka-python==2.0.2
# Installing collected packages: kafka-python, websockets, aiohttp...
```

---

## 🛠️ Troubleshooting

### ❌ Error: "requirements.txt not found"

**Causa:** Ejecutaste docker-compose desde un subdirectorio.

**Solución:**
```powershell
# Desde el directorio correcto
cd C:\Users\luisb\Desktop\SD\SD

# Ahora ejecuta
docker-compose -f docker-compose.pc2.yml up -d --build
```

### ❌ Error: "COPY failed"

**Causa:** Dockerfile tiene rutas incorrectas.

**Solución:** Ya corregido. Los Dockerfiles ahora usan:
```dockerfile
COPY requirements.txt /app/requirements.txt  # ✓ Correcto
# NO:
# COPY ../requirements.txt /app/requirements.txt  # ✗ Incorrecto
```

### ❌ Paquetes no se instalan

**Verificar:**
```powershell
# Ver el contenido de requirements.txt
cat requirements.txt

# Ver qué copia Docker
docker-compose -f docker-compose.pc2.yml build --progress=plain
```

---

## 📝 Resumen

✅ **Antes:** Las dependencias no se instalaban automáticamente  
✅ **Ahora:** Se instalan automáticamente con `docker-compose build`

✅ **Ventajas:**
- Sin necesidad de instalar manualmente
- Se recrea el entorno limpio cada vez
- Independiente del sistema operativo
- Reproducible en cualquier máquina

✅ **Archivos Modificados:**
- `EV_Driver/Dockerfile` - Corregidas rutas de COPY
- `EV_CP_M/Dockerfile` - Corregidas rutas de COPY
- `docker-compose.pc2.yml` - Corregido depends_on duplicado

---

## 🎯 Próximos Pasos

1. **Limpiar builds anteriores:**
   ```powershell
   docker-compose -f docker-compose.pc2.yml down
   docker system prune -a  # Opcional: limpiar todo
   ```

2. **Rebuild completo:**
   ```powershell
   docker-compose -f docker-compose.pc2.yml up -d --build
   ```

3. **Verificar logs:**
   ```powershell
   docker-compose -f docker-compose.pc2.yml logs
   ```

**¡Listo! Los paquetes se instalarán automáticamente en cada build.** 🎉

---

*Última actualización: 2025*

