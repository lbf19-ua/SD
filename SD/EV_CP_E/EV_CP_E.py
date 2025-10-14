import socket
import threading
import time
import random
import sys
import os
import json
from queue import Queue
from kafka import KafkaProducer

# -----------------------------------------------------------------------------
# Carga de configuración
# -----------------------------------------------------------------------------
# Estructura esperada en network_config.py:
# ENGINE_CONFIG = {
#     "central_ip": "127.0.0.1",
#     "central_port": 5000,
#     "engine_id": "CP01",
#     "engine_ip": "0.0.0.0",
#     "engine_port": 5100,
#     "location": "Alicante-01",
#     "price_eur_kwh": 0.35,
#     "kafka_broker": "localhost:9092",
#     "kafka_topic_engine": "engine-events"
# }
# -----------------------------------------------------------------------------

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network_config import ENGINE_CONFIG

# Kafka
KAFKA_BROKER = ENGINE_CONFIG.get('kafka_broker', 'localhost:9092')
KAFKA_TOPIC_PRODUCE = ENGINE_CONFIG.get('kafka_topic_engine', 'engine-events')


# -----------------------------------------------------------------------------
# Utilidades de línea
# -----------------------------------------------------------------------------
def send_line(sock: socket.socket, msg: str):
    """Envía una línea terminada en \\n (protocolo texto)."""
    try:
        sock.sendall((msg + "\n").encode("utf-8"))
    except Exception as e:
        print(f"[ENGINE] send_line error: {e}")


def recv_line(sock: socket.socket, timeout=None) -> str:
    """
    Lee hasta '\\n'. Devuelve '' si timeout o desconexión.
    OJO: Si el servidor no manda '\\n', esto esperará hasta timeout.
    """
    sock.settimeout(timeout)
    data = b""
    try:
        while not data.endswith(b"\n"):
            chunk = sock.recv(1024)
            if not chunk:
                return ""
            data += chunk
        return data.decode("utf-8").strip()
    except socket.timeout:
        return ""


# -----------------------------------------------------------------------------
# Clase EV_CP_E (Engine)
# -----------------------------------------------------------------------------
class EV_CP_E:
    def __init__(self,
                 central_ip=None,
                 central_port=None,
                 engine_id=None):
        # Identidad + Central
        self.engine_id = engine_id or ENGINE_CONFIG.get("engine_id", "Engine_001")
        self.central_ip = central_ip or ENGINE_CONFIG['central_ip']
        self.central_port = central_port or ENGINE_CONFIG['central_port']

        # Servidor health para Monitor
        self.engine_ip = ENGINE_CONFIG.get("engine_ip", "0.0.0.0")
        self.engine_port = ENGINE_CONFIG.get("engine_port", 5100)

        # Metadatos
        self.location = ENGINE_CONFIG.get("location", "Alicante-01")
        self.price_eur_kwh = float(ENGINE_CONFIG.get("price_eur_kwh", 0.35))

        # Estado
        self.state_lock = threading.Lock()
        self.state = "IDLE"          # IDLE | READY | CHARGING | PARADO | FAULT
        self.connected = False
        self.stop_event = threading.Event()

        # Sesión de carga
        self.current_client = None
        self.kwh_acc = 0.0
        self.eur_acc = 0.0
        self.last_pwr = 0.0

        # Comunicación con Central
        self.central_sock = None
        self.outgoing_cmd_q = Queue()

        # Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    # -------------------------------------------------------------------------
    # Arranque principal
    # -------------------------------------------------------------------------
    def start(self):
        """
        Arranca:
          - Health server (para Monitor)
          - Conexión y bucles con Central (listener/sender/telemetry)
          - CLI local (plug/unplug/stop/resume/fault/recover/status)
        """
        print(f"[ENGINE] {self.engine_id} starting")
        print(f"[ENGINE] Central at {self.central_ip}:{self.central_port}")
        print(f"[ENGINE] Health at  {self.engine_ip}:{self.engine_port}")
        print(f"[ENGINE] Kafka broker: {KAFKA_BROKER} -> topic '{KAFKA_TOPIC_PRODUCE}'")

        # Health server para Monitor
        threading.Thread(target=self._health_server_loop,
                         name="EVCP_E_HEALTH", daemon=True).start()

        # Conexión con Central en bucle (reintentos)
        threading.Thread(target=self._central_connect_and_loop,
                         name="EVCP_E_CENTRAL", daemon=True).start()

        # CLI local
        threading.Thread(target=self._local_cli_loop,
                         name="EVCP_E_CLI", daemon=True).start()

        # Espera activa
        try:
            while not self.stop_event.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[ENGINE] Shutting down...")
        finally:
            self.stop_event.set()
            try:
                if self.central_sock:
                    self.central_sock.close()
            except:
                pass

    # -------------------------------------------------------------------------
    # Comunicación con Central
    # -------------------------------------------------------------------------
    def _central_connect_and_loop(self):
        while not self.stop_event.is_set():
            try:
                print(f"[ENGINE] Connecting to CENTRAL {self.central_ip}:{self.central_port} ...")
                with socket.create_connection((self.central_ip, self.central_port), timeout=10) as s:
                    self.central_sock = s
                    self.connected = True

                    # 1) Mensaje de identificación simple (compatibilidad con tu Central actual)
                    ident_msg = f"EV_CP_E {self.engine_id} ready for charging operations"
                    s.sendall(ident_msg.encode())
                    # Recibir respuesta (tu Central actual no manda '\n', así que usamos recv fijo)
                    try:
                        s.settimeout(3.0)
                        resp = s.recv(1024)
                        if resp:
                            print(f"[ENGINE] Response from Central: {resp.decode(errors='ignore')}")
                    except socket.timeout:
                        pass

                    # 2) Registro formal (protocolo línea)
                    reg = f"CP_REGISTER#{self.engine_id}#LOC={self.location}#PRICE={self.price_eur_kwh}"
                    send_line(s, reg)
                    self._kafka_event("register", {"register": reg})

                    # 3) Lanza hilos: listener/sender/telemetry
                    listener = threading.Thread(target=self._central_listener, args=(s,), daemon=True)
                    sender = threading.Thread(target=self._central_sender, args=(s,), daemon=True)
                    telem = threading.Thread(target=self._telemetry_loop, daemon=True)

                    listener.start()
                    sender.start()
                    telem.start()

                    # 4) Bucle de vida de la conexión
                    while self.connected and not self.stop_event.is_set():
                        time.sleep(0.5)

            except (ConnectionRefusedError, OSError) as e:
                print(f"[ENGINE] CENTRAL not reachable ({e}). Reconnecting in 2s...")
                time.sleep(2)
            finally:
                self.connected = False
                self.central_sock = None

    def _central_listener(self, s: socket.socket):
        """Recibe órdenes de la central (AUTH / CMD STOP|RESUME / ...)."""
        print("[ENGINE] Central listener started")
        while not self.stop_event.is_set() and self.connected:
            line = recv_line(s, timeout=1.0)  # requiere que CENTRAL envíe '\n'
            if not line:
                continue
            print(f"[ENGINE] <- CENTRAL: {line}")

            if line.startswith("AUTH#"):
                # AUTH#CP_ID#CLIENT_ID#OK
                parts = line.split("#")
                if len(parts) >= 4 and parts[3] == "OK":
                    cp_id = parts[1]
                    client_id = parts[2]
                    if cp_id == self.engine_id:
                        with self.state_lock:
                            if self.state == "IDLE":
                                self.state = "READY"
                                self.current_client = client_id
                                self.kwh_acc = 0.0
                                self.eur_acc = 0.0
                                self.last_pwr = 0.0
                                print(f"[ENGINE] AUTH OK -> READY (client {client_id})")
                                self._kafka_event("auth_ok", {"client": client_id})

            elif line.startswith("CMD#"):
                # CMD#CP_ID#STOP | CMD#CP_ID#RESUME
                try:
                    _, cp_id, cmd = line.split("#", 2)
                except ValueError:
                    continue
                if cp_id == self.engine_id:
                    if cmd == "STOP":
                        self._cmd_stop()
                    elif cmd == "RESUME":
                        self._cmd_resume()

    def _central_sender(self, s: socket.socket):
        """Saca de la cola y envía a CENTRAL como líneas con '\\n'."""
        while not self.stop_event.is_set() and self.connected:
            try:
                msg = self.outgoing_cmd_q.get(timeout=0.5)
            except:
                continue
            try:
                send_line(s, msg)
                self._kafka_event("to_central", {"msg": msg})
            except Exception as e:
                print(f"[ENGINE] Error sending to CENTRAL: {e}")

    # -------------------------------------------------------------------------
    # Telemetría y ciclo de carga
    # -------------------------------------------------------------------------
    def _telemetry_loop(self):
        """Si está CHARGING, envía TELEM# cada 1s y acumula kWh/€."""
        print("[ENGINE] Telemetry loop started")
        last_ts = time.time()
        while not self.stop_event.is_set():
            time.sleep(1.0)
            if not self.connected:
                last_ts = time.time()
                continue

            with self.state_lock:
                st = self.state
                client = self.current_client

            now = time.time()
            dt_s = max(0.0, now - last_ts)
            last_ts = now

            if st == "CHARGING" and client:
                pwr = round(3.0 + random.random() * 4.0, 2)  # 3–7 kW
                dkwh = pwr * (dt_s / 3600.0)
                self.kwh_acc += dkwh
                self.eur_acc = self.kwh_acc * self.price_eur_kwh
                self.last_pwr = pwr

                telem = f"TELEM#{self.engine_id}#PWR={pwr}#EUR={self.eur_acc:.2f}"
                self.outgoing_cmd_q.put(telem)
                self._kafka_event("telem", {"pwr": pwr, "eur": round(self.eur_acc, 2)})

    # -------------------------------------------------------------------------
    # Health server (para EV_CP_M)
    # -------------------------------------------------------------------------
    def _health_server_loop(self):
        """Servidor TCP ligero para atender al Monitor (PING/OK y KO forzado)."""
        print(f"[ENGINE] Health server listening on {self.engine_ip}:{self.engine_port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.engine_ip, self.engine_port))
            srv.listen(5)
            while not self.stop_event.is_set():
                try:
                    srv.settimeout(1.0)
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=self._handle_monitor_conn, args=(conn, addr),
                                 daemon=True).start()

    def _handle_monitor_conn(self, conn: socket.socket, addr):
        """Responde PINGs del monitor: CP_HEALTH#CP_ID#PING -> OK/KO, o FORCED_KO."""
        with conn:
            while not self.stop_event.is_set():
                line = recv_line(conn, timeout=2.0)
                if not line:
                    return
                if line.startswith("CP_HEALTH#"):
                    # Espera: CP_HEALTH#CP_ID#PING
                    parts = line.split("#")
                    if len(parts) >= 3 and parts[2] == "PING":
                        with self.state_lock:
                            ko = (self.state == "FAULT")
                        resp = f"CP_HEALTH#{self.engine_id}#" + ("KO" if ko else "OK")
                        send_line(conn, resp)
                elif line == "FORCE_KO":
                    self._force_fault("Monitor forced KO")

    # -------------------------------------------------------------------------
    # Acciones y comandos (locales y de la central)
    # -------------------------------------------------------------------------
    def _action_plug(self):
        """Simula enchufar: READY -> CHARGING + CHARGE_START"""
        with self.state_lock:
            if self.state != "READY":
                print("[ENGINE] Can't plug: not in READY")
                return
            self.state = "CHARGING"
            client = self.current_client
        ts = int(time.time())
        msg = f"CHARGE_START#{self.engine_id}#{client}#ts={ts}"
        self.outgoing_cmd_q.put(msg)
        self._kafka_event("charge_start", {"client": client})
        print("[ENGINE] Charging started (CHARGING)")

    def _action_unplug(self):
        """Simula desenchufar: CHARGING -> IDLE + CHARGE_END"""
        with self.state_lock:
            if self.state != "CHARGING":
                print("[ENGINE] Can't unplug: not CHARGING")
                return
            client = self.current_client
            kwh = self.kwh_acc
            eur = self.eur_acc
            # Reset
            self.state = "IDLE"
            self.current_client = None
            self.kwh_acc = 0.0
            self.eur_acc = 0.0
            self.last_pwr = 0.0
        msg = f"CHARGE_END#{self.engine_id}#{client}#kWh={kwh:.3f}#EUR={eur:.2f}"
        self.outgoing_cmd_q.put(msg)
        self._kafka_event("charge_end", {"client": client, "kWh": round(kwh, 3), "EUR": round(eur, 2)})
        print("[ENGINE] Charging finished -> IDLE")

    def _cmd_stop(self):
        """Central: STOP -> PARADO (corta carga si estaba)"""
        with self.state_lock:
            if self.state == "CHARGING":
                client = self.current_client
                kwh, eur = self.kwh_acc, self.eur_acc
                self.outgoing_cmd_q.put(f"CHARGE_END#{self.engine_id}#{client}#kWh={kwh:.3f}#EUR={eur:.2f}")
            self.state = "PARADO"
            self.current_client = None
            self.kwh_acc = 0.0
            self.eur_acc = 0.0
            self.last_pwr = 0.0
        self._kafka_event("cmd_stop", {})
        print("[ENGINE] -> PARADO (Out of Order)")

    def _cmd_resume(self):
        """Central: RESUME -> IDLE"""
        with self.state_lock:
            if self.state == "PARADO":
                self.state = "IDLE"
        self._kafka_event("cmd_resume", {})
        print("[ENGINE] -> IDLE (resumed)")

    def _force_fault(self, reason: str):
        """Avería simulada: pone FAULT y notifica a Central."""
        with self.state_lock:
            self.state = "FAULT"
        self._kafka_event("fault", {"reason": reason})
        print("[ENGINE] -> FAULT (avería simulada). Si estaba cargando, se considera cortada.")
        self.outgoing_cmd_q.put(f"CP_FAULT#{self.engine_id}")

    def _recover_from_fault(self):
        """Recuperación desde FAULT -> IDLE y notifica a Central."""
        with self.state_lock:
            if self.state == "FAULT":
                self.state = "IDLE"
                self._kafka_event("recover", {})
                print("[ENGINE] FAULT -> IDLE (recuperado)")
                self.outgoing_cmd_q.put(f"CP_RECOVER#{self.engine_id}")

    # -------------------------------------------------------------------------
    # CLI local para probar sin GUI
    # -------------------------------------------------------------------------
    def _local_cli_loop(self):
        help_txt = "Commands: plug | unplug | stop | resume | fault | recover | status | help"
        print("[ENGINE][CLI] " + help_txt)
        while not self.stop_event.is_set():
            try:
                cmd = input().strip().lower()
            except EOFError:
                return
            if cmd == "plug":
                self._action_plug()
            elif cmd == "unplug":
                self._action_unplug()
            elif cmd == "stop":
                self._cmd_stop()
            elif cmd == "resume":
                self._cmd_resume()
            elif cmd == "fault":
                self._force_fault("Local fault requested")
            elif cmd == "recover":
                self._recover_from_fault()
            elif cmd == "status":
                with self.state_lock:
                    print(f"[ENGINE] state={self.state} client={self.current_client} kWh={self.kwh_acc:.3f} €={self.eur_acc:.2f}")
            elif cmd == "help":
                print("[ENGINE][CLI] " + help_txt)

    # -------------------------------------------------------------------------
    # Kafka helper
    # -------------------------------------------------------------------------
    def _kafka_event(self, action, extra: dict):
        try:
            payload = {
                "engine_id": self.engine_id,
                "action": action,
                "ts": time.time(),
                **extra
            }
            self.producer.send(KAFKA_TOPIC_PRODUCE, payload)
            self.producer.flush()
        except Exception as e:
            print(f"[ENGINE] Kafka error: {e}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    engine = EV_CP_E(
        central_ip=ENGINE_CONFIG['central_ip'],
        central_port=ENGINE_CONFIG['central_port'],
        engine_id=ENGINE_CONFIG.get('engine_id', 'Engine_Test_001')
    )
    engine.start()
