#!/usr/bin/env python3
"""
Script de prueba de concurrencia para EV Charging System
Simula múltiples usuarios cargando simultáneamente en diferentes CPs
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

# Configuración
DRIVER_WS_URL = "ws://localhost:8001/ws"

# Datos de prueba: 10 usuarios
TEST_USERS = [
    {"username": "driver1", "password": "pass123"},
    {"username": "driver2", "password": "pass456"},
    {"username": "maria_garcia", "password": "maria2025"},
    {"username": "lbf19", "password": "lbf19"},
    {"username": "test1", "password": "test123"},
    {"username": "test2", "password": "test123"},
    {"username": "test3", "password": "test123"},
    {"username": "test4", "password": "test123"},
    {"username": "test5", "password": "test123"},
    {"username": "admin", "password": "admin123"},
]

# CPs específicos para cada usuario (opcional, si no se especifica se asigna automáticamente)
ASSIGNED_CPS = [
    "CP_001", "CP_002", "CP_003", "CP_004", "CP_005",
    "CP_006", "CP_007", "CP_008", "CP_009", "CP_010"
]


class ChargingSession:
    """Representa una sesión de carga de un usuario"""
    
    def __init__(self, user_index, username, password, cp_id=None):
        self.user_index = user_index
        self.username = username
        self.password = password
        self.cp_id = cp_id
        self.ws = None
        self.session_id = None
        self.start_time = None
        self.end_time = None
        self.success = False
        self.error = None
        self.energy = 0
        self.cost = 0
    
    async def connect(self):
        """Conecta al servidor WebSocket"""
        try:
            self.ws = await websockets.connect(DRIVER_WS_URL)
            print(f"[{self.user_index:02d}] ✅ {self.username} conectado")
            return True
        except Exception as e:
            self.error = f"Connection error: {e}"
            print(f"[{self.user_index:02d}] ❌ {self.username} error de conexión: {e}")
            return False
    
    async def login(self):
        """Realiza el login"""
        try:
            await self.ws.send(json.dumps({
                "type": "login",
                "username": self.username,
                "password": self.password
            }))
            
            response = await asyncio.wait_for(self.ws.recv(), timeout=15.0)
            data = json.loads(response)
            
            if data.get("type") == "login_response" and data.get("success"):
                print(f"[{self.user_index:02d}] 🔐 {self.username} login exitoso (Balance: €{data['user']['balance']:.2f})")
                return True
            else:
                self.error = f"Login failed: {data.get('message', 'Unknown')}"
                print(f"[{self.user_index:02d}] ❌ {self.username} login fallido: {self.error}")
                return False
        except Exception as e:
            self.error = f"Login error: {e}"
            print(f"[{self.user_index:02d}] ❌ {self.username} error en login: {e}")
            return False
    
    async def start_charging(self):
        """Inicia la carga"""
        try:
            self.start_time = time.time()
            
            # Si tiene CP específico, solicitar ese; si no, dejar que el sistema asigne
            if self.cp_id:
                msg = {
                    "type": "request_charging_at_cp",
                    "username": self.username,
                    "cp_id": self.cp_id
                }
                print(f"[{self.user_index:02d}] ⚡ {self.username} solicitando carga en {self.cp_id}...")
            else:
                msg = {
                    "type": "request_charging",
                    "username": self.username
                }
                print(f"[{self.user_index:02d}] ⚡ {self.username} solicitando carga (auto-asignación)...")
            
            await self.ws.send(json.dumps(msg))
            
            # Esperar respuesta con timeout más largo para concurrencia
            response = await asyncio.wait_for(self.ws.recv(), timeout=20.0)
            data = json.loads(response)
            
            if data.get("type") == "charging_started":
                self.session_id = data.get("session_id")
                self.cp_id = data.get("cp_id")
                print(f"[{self.user_index:02d}] ✅ {self.username} carga iniciada en {self.cp_id} (sesión {self.session_id})")
                return True
            else:
                self.error = f"Charging failed: {data.get('message', 'Unknown')}"
                print(f"[{self.user_index:02d}] ❌ {self.username} carga fallida: {self.error}")
                return False
        except Exception as e:
            self.error = f"Start charging error: {e}"
            print(f"[{self.user_index:02d}] ❌ {self.username} error al iniciar carga: {e}")
            return False
    
    async def wait_charging(self, duration=5):
        """Espera durante la carga"""
        print(f"[{self.user_index:02d}] ⏳ {self.username} cargando en {self.cp_id} por {duration}s...")
        await asyncio.sleep(duration)
    
    async def stop_charging(self):
        """Detiene la carga"""
        try:
            await self.ws.send(json.dumps({
                "type": "stop_charging",
                "username": self.username
            }))
            
            # Esperar respuesta con timeout más largo
            response = await asyncio.wait_for(self.ws.recv(), timeout=15.0)
            data = json.loads(response)
            
            self.end_time = time.time()
            duration = self.end_time - self.start_time
            
            if data.get("type") == "charging_stopped":
                self.energy = data.get("energy", 0)
                self.cost = data.get("cost", 0)
                self.success = True
                print(f"[{self.user_index:02d}] 🏁 {self.username} carga completada: {self.energy:.2f} kWh, €{self.cost:.2f} ({duration:.1f}s)")
                return True
            else:
                self.error = f"Stop failed: {data.get('message', 'Unknown')}"
                print(f"[{self.user_index:02d}] ⚠️  {self.username} error al detener: {self.error}")
                return False
        except Exception as e:
            self.error = f"Stop charging error: {e}"
            print(f"[{self.user_index:02d}] ❌ {self.username} error al detener carga: {e}")
            return False
    
    async def close(self):
        """Cierra la conexión"""
        if self.ws:
            await self.ws.close()


async def run_charging_session(user_index, username, password, cp_id=None, charge_duration=5):
    """Ejecuta una sesión completa de carga para un usuario"""
    session = ChargingSession(user_index, username, password, cp_id)
    
    # Conectar
    if not await session.connect():
        return session
    
    # Login
    if not await session.login():
        await session.close()
        return session
    
    # Iniciar carga
    if not await session.start_charging():
        await session.close()
        return session
    
    # Esperar durante la carga
    await session.wait_charging(charge_duration)
    
    # Detener carga
    await session.stop_charging()
    
    # Cerrar conexión
    await session.close()
    
    return session


async def test_concurrent_charging(num_users=10, charge_duration=5, assign_specific_cps=True):
    """
    Prueba de carga concurrente con múltiples usuarios
    
    Args:
        num_users: Número de usuarios simultáneos (máx 10)
        charge_duration: Duración de cada sesión de carga en segundos
        assign_specific_cps: Si True, asigna CPs específicos; si False, deja que el sistema asigne
    """
    print("=" * 80)
    print(f"🧪 TEST DE CONCURRENCIA - {num_users} USUARIOS SIMULTÁNEOS")
    print("=" * 80)
    print(f"⏱️  Duración de carga: {charge_duration} segundos")
    print(f"📍 Asignación de CPs: {'Específica' if assign_specific_cps else 'Automática'}")
    print(f"🔗 Servidor: {DRIVER_WS_URL}")
    print("=" * 80)
    print()
    
    # Limitar a los usuarios disponibles
    num_users = min(num_users, len(TEST_USERS))
    
    # Crear tareas para todos los usuarios
    tasks = []
    for i in range(num_users):
        user = TEST_USERS[i]
        cp_id = ASSIGNED_CPS[i] if assign_specific_cps and i < len(ASSIGNED_CPS) else None
        
        task = run_charging_session(
            user_index=i + 1,
            username=user["username"],
            password=user["password"],
            cp_id=cp_id,
            charge_duration=charge_duration
        )
        tasks.append(task)
    
    # Ejecutar todas las sesiones en paralelo
    print(f"🚀 Iniciando {num_users} sesiones simultáneas...\n")
    start_time = time.time()
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Analizar resultados
    print("\n" + "=" * 80)
    print("📊 RESULTADOS DEL TEST")
    print("=" * 80)
    
    successful = 0
    failed = 0
    total_energy = 0
    total_cost = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[{i+1:02d}] ❌ Excepción: {result}")
            failed += 1
        elif isinstance(result, ChargingSession):
            if result.success:
                successful += 1
                total_energy += result.energy
                total_cost += result.cost
            else:
                failed += 1
                print(f"[{i+1:02d}] ❌ {result.username} falló: {result.error}")
    
    print(f"\n✅ Exitosas: {successful}/{num_users}")
    print(f"❌ Fallidas:  {failed}/{num_users}")
    print(f"⚡ Energía total: {total_energy:.2f} kWh")
    print(f"💰 Costo total: €{total_cost:.2f}")
    print(f"⏱️  Tiempo total: {total_duration:.2f}s")
    print(f"📈 Throughput: {num_users/total_duration:.2f} usuarios/segundo")
    
    print("=" * 80)
    
    return results


async def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test de concurrencia para EV Charging System")
    parser.add_argument("-n", "--num-users", type=int, default=10, 
                       help="Número de usuarios simultáneos (1-10, default: 10)")
    parser.add_argument("-d", "--duration", type=int, default=5,
                       help="Duración de carga en segundos (default: 5)")
    parser.add_argument("--auto-assign", action="store_true",
                       help="Usar asignación automática de CPs en lugar de específica")
    
    args = parser.parse_args()
    
    await test_concurrent_charging(
        num_users=args.num_users,
        charge_duration=args.duration,
        assign_specific_cps=not args.auto_assign
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
