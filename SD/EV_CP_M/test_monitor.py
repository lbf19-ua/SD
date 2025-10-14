#!/usr/bin/env python3
"""
Script de prueba para EV_CP_M (Monitor)
Permite probar diferentes escenarios del monitor
"""

import sys
import os
import time
import threading
import socket

# Añadir el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from EV_CP_M import EV_CP_M

class MockEngine:
    """Mock del Engine para simular diferentes respuestas"""
    
    def __init__(self, port=5001, response_mode="OK"):
        self.port = port
        self.response_mode = response_mode
        self.running = False
        self.server_thread = None
        self.response_count = 0
        
    def start(self):
        """Inicia el servidor mock del Engine"""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        print(f"[MOCK ENGINE] Started on port {self.port} with response mode: {self.response_mode}")
        
    def stop(self):
        """Para el servidor mock"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=1)
        print(f"[MOCK ENGINE] Stopped")
        
    def _run_server(self):
        """Ejecuta el servidor mock"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            server_socket.settimeout(1)  # Timeout para poder parar el servidor
            
            print(f"[MOCK ENGINE] Listening on port {self.port}")
            
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    with conn:
                        self._handle_client(conn, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[MOCK ENGINE] Error: {e}")
                        
    def _handle_client(self, conn, addr):
        """Maneja una conexión de cliente"""
        try:
            data = conn.recv(1024)
            if not data:
                return
                
            message = data.decode().strip()
            print(f"[MOCK ENGINE] Received: {message}")
            
            self.response_count += 1
            
            # Determinar la respuesta basada en el modo
            if self.response_mode == "OK":
                response = "OK"
            elif self.response_mode == "KO":
                response = "KO"
            elif self.response_mode == "INTERMITENT":
                # Alternar entre OK y KO cada 3 respuestas
                response = "OK" if (self.response_count // 3) % 2 == 0 else "KO"
            elif self.response_mode == "DELAYED_KO":
                # OK por las primeras 5 respuestas, luego KO
                response = "OK" if self.response_count <= 5 else "KO"
            else:
                response = "OK"
                
            conn.sendall(response.encode())
            print(f"[MOCK ENGINE] Sent: {response}")
            
        except Exception as e:
            print(f"[MOCK ENGINE] Error handling client: {e}")

class MockCentral:
    """Mock del Central para simular autenticación"""
    
    def __init__(self, port=5000):
        self.port = port
        self.running = False
        self.server_thread = None
        
    def start(self):
        """Inicia el servidor mock del Central"""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        print(f"[MOCK CENTRAL] Started on port {self.port}")
        
    def stop(self):
        """Para el servidor mock"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=1)
        print(f"[MOCK CENTRAL] Stopped")
        
    def _run_server(self):
        """Ejecuta el servidor mock"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            server_socket.settimeout(1)
            
            print(f"[MOCK CENTRAL] Listening on port {self.port}")
            
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    with conn:
                        self._handle_client(conn, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[MOCK CENTRAL] Error: {e}")
                        
    def _handle_client(self, conn, addr):
        """Maneja una conexión de cliente"""
        try:
            data = conn.recv(1024)
            if not data:
                return
                
            message = data.decode().strip()
            print(f"[MOCK CENTRAL] Received: {message}")
            
            if "registration request" in message:
                response = "Authentication successful"
            elif "ENGINE_FAILURE" in message:
                response = "Failure report received"
            else:
                response = "OK"
                
            conn.sendall(response.encode())
            print(f"[MOCK CENTRAL] Sent: {response}")
            
        except Exception as e:
            print(f"[MOCK CENTRAL] Error handling client: {e}")

def test_basic_connection():
    """Prueba básica de conexión"""
    print("\n=== TEST: Basic Connection ===")
    
    # Iniciar mocks
    mock_central = MockCentral(5000)
    mock_engine = MockEngine(5001, "OK")
    
    mock_central.start()
    mock_engine.start()
    
    time.sleep(1)  # Esperar a que los servidores inicien
    
    # Probar monitor
    monitor = EV_CP_M(
        central_ip='localhost',
        central_port=5000,
        engine_ip='localhost', 
        engine_port=5001,
        cp_id='CP_TEST_001'
    )
    
    result = monitor.test_connection()
    print(f"Connection test result: {'PASSED' if result else 'FAILED'}")
    
    # Limpiar
    mock_central.stop()
    mock_engine.stop()

def test_engine_failure_detection():
    """Prueba detección de fallos del Engine"""
    print("\n=== TEST: Engine Failure Detection ===")
    
    # Iniciar mocks
    mock_central = MockCentral(5000)
    mock_engine = MockEngine(5001, "DELAYED_KO")  # OK al principio, luego KO
    
    mock_central.start()
    mock_engine.start()
    
    time.sleep(1)
    
    # Configurar monitor
    monitor = EV_CP_M(
        central_ip='localhost',
        central_port=5000,
        engine_ip='localhost',
        engine_port=5001,
        cp_id='CP_TEST_002'
    )
    
    monitor.initialize_kafka_producer()
    
    # Conectar y empezar monitoreo
    if monitor.connect_to_central() and monitor.connect_to_engine():
        monitor.start_monitoring()
        
        print("Monitor running for 15 seconds to test failure detection...")
        time.sleep(15)
        
        monitor.stop_monitoring()
    
    # Limpiar
    mock_central.stop()
    mock_engine.stop()

def test_intermitent_failures():
    """Prueba fallos intermitentes"""
    print("\n=== TEST: Intermitent Failures ===")
    
    # Iniciar mocks
    mock_central = MockCentral(5000)
    mock_engine = MockEngine(5001, "INTERMITENT")  # Alternar OK/KO
    
    mock_central.start()
    mock_engine.start()
    
    time.sleep(1)
    
    # Configurar monitor
    monitor = EV_CP_M(
        central_ip='localhost',
        central_port=5000,
        engine_ip='localhost',
        engine_port=5001,
        cp_id='CP_TEST_003'
    )
    
    monitor.initialize_kafka_producer()
    
    # Conectar y empezar monitoreo
    if monitor.connect_to_central() and monitor.connect_to_engine():
        monitor.start_monitoring()
        
        print("Monitor running for 20 seconds to test intermitent failures...")
        time.sleep(20)
        
        monitor.stop_monitoring()
    
    # Limpiar
    mock_central.stop()
    mock_engine.stop()

def main():
    """Función principal"""
    print("EV_CP_M Test Suite")
    print("==================")
    
    try:
        test_basic_connection()
        test_engine_failure_detection()
        test_intermitent_failures()
        
        print("\n=== ALL TESTS COMPLETED ===")
        
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nError running tests: {e}")

if __name__ == "__main__":
    main()