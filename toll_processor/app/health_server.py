import logging
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from prometheus_client import start_http_server
from app import kafka_client, database, state

log = logging.getLogger(__name__)
HEALTH_PORT = 8080
METRICS_PORT = 8081

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/health/live':
            self._send(200, {'status': 'live'})
        elif path == '/health/ready':
            errors = []
            # Kafka
            try:
                consumer = kafka_client.get_kafka_consumer()
                if not consumer or not consumer.bootstrap_connected():
                    errors.append('Kafka not connected')
            except Exception as e:
                errors.append(f'Kafka error: {e}')
            # DB
            try:
                with database.get_db_connection() as conn:
                    conn.cursor().execute('SELECT 1')
            except Exception as e:
                errors.append(f'DB error: {e}')
            # Redis
            try:
                cli = state.get_redis_client()
                if not cli.ping(): errors.append('Redis not connected')
            except Exception as e:
                errors.append(f'Redis error: {e}')
            if errors:
                self._send(503, {'status':'not ready','errors':errors})
            else:
                self._send(200, {'status':'ready'})
        else:
            self._send(404, {'status':'not found'})

    def _send(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, fmt, *args): log.debug(fmt % args)

http_server = None
server_thread = None

def start_health_server():
    global http_server, server_thread
    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    log.info(f'Started Prometheus metrics server on port {METRICS_PORT}')
    # Start health check server
    if server_thread and server_thread.is_alive(): return
    def serve():
        global http_server
        try:
            http_server = HTTPServer(('', HEALTH_PORT), HealthCheckHandler)
            log.info(f'Starting health server on port {HEALTH_PORT}')
            http_server.serve_forever()
        except Exception:
            log.exception('Health server error')
    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()

def stop_health_server():
    global http_server, server_thread
    if http_server:
        log.info('Shutting down health server')
        http_server.shutdown()
        http_server.server_close()
    if server_thread:
        server_thread.join(timeout=5)
    log.info('Health server stopped')