"""Main application entry point for manufacturing data publisher."""
import logging
import signal
import sys
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from config import Config
from utils.mqtt_client import MQTTClient
from publishers.machine_publisher import MachinePublisher
from publishers.enterprise_publisher import EnterprisePublisher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Kubernetes health probes."""

    def log_message(self, format, *args):
        """Suppress default logging to reduce noise."""
        pass

    def do_GET(self):
        """Handle GET requests for health checks."""
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            # Get stats from publishers if available
            stats = {
                "status": "healthy",
                "timestamp": int(time.time() * 1000)
            }

            if hasattr(self.server, 'machine_publisher'):
                stats['machine_stats'] = self.server.machine_publisher.get_stats()

            if hasattr(self.server, 'enterprise_publisher'):
                stats['enterprise_stats'] = self.server.enterprise_publisher.get_stats()

            self.wfile.write(json.dumps(stats).encode())
        else:
            self.send_response(404)
            self.end_headers()


class DataPublisherApp:
    """Main application coordinating data publishers."""

    def __init__(self):
        """Initialize application."""
        self.mqtt_uncurated = None
        self.machine_publisher = None
        self.enterprise_publisher = None
        self.health_server = None
        self.health_thread = None
        self.running = False

    def setup_mqtt_clients(self):
        """Set up MQTT client connections."""
        logger.info("Setting up MQTT client...")

        # Uncurated broker connection only
        # Curated data flows through the curated-republisher pipeline
        self.mqtt_uncurated = MQTTClient(
            broker_host=Config.MQTT_BROKER_UNCURATED_HOST,
            broker_port=Config.MQTT_BROKER_UNCURATED_PORT,
            username=Config.MQTT_USERNAME,
            password=Config.MQTT_PASSWORD,
            client_id="data-publisher-uncurated",
            qos=Config.MQTT_QOS
        )

        # Connect to broker
        if not self.mqtt_uncurated.connect():
            logger.error("Failed to connect to uncurated MQTT broker")
            sys.exit(1)

        logger.info("MQTT client connected successfully")

    def setup_publishers(self):
        """Set up data publishers."""
        logger.info("Setting up data publishers...")

        # Machine publisher (uncurated only)
        self.machine_publisher = MachinePublisher(
            None,  # No curated broker - data flows through curation pipeline
            self.mqtt_uncurated
        )
        self.machine_publisher.initialize_machines()

        # Enterprise system publisher (uncurated only)
        self.enterprise_publisher = EnterprisePublisher(
            None,  # No curated broker - data flows through curation pipeline
            self.mqtt_uncurated
        )
        self.enterprise_publisher.initialize_systems()

        logger.info("Publishers initialized successfully")

    def start_health_server(self):
        """Start minimal HTTP server for health checks."""
        logger.info(f"Starting health check server on port {Config.HEALTH_CHECK_PORT}...")

        self.health_server = HTTPServer(
            ("0.0.0.0", Config.HEALTH_CHECK_PORT),
            HealthCheckHandler
        )

        # Attach publishers to server for stats access
        self.health_server.machine_publisher = self.machine_publisher
        self.health_server.enterprise_publisher = self.enterprise_publisher

        # Run server in separate thread
        self.health_thread = threading.Thread(
            target=self.health_server.serve_forever,
            daemon=True,
            name="HealthServer"
        )
        self.health_thread.start()

        logger.info(f"Health check server running on port {Config.HEALTH_CHECK_PORT}")

    def start(self):
        """Start the application."""
        logger.info("=" * 60)
        logger.info("Manufacturing Data Publisher")
        logger.info("=" * 60)

        # Display configuration
        Config.display()

        # Set up components
        self.setup_mqtt_clients()
        self.setup_publishers()
        self.start_health_server()

        # Start publishers
        logger.info("Starting data publishers...")
        self.machine_publisher.start()
        self.enterprise_publisher.start()

        self.running = True
        logger.info("=" * 60)
        logger.info("Application started successfully")
        logger.info("Publishing data to MQTT brokers...")
        logger.info("=" * 60)

    def stop(self):
        """Stop the application."""
        if not self.running:
            return

        logger.info("Shutting down application...")
        self.running = False

        # Stop publishers
        if self.machine_publisher:
            self.machine_publisher.stop()

        if self.enterprise_publisher:
            self.enterprise_publisher.stop()

        # Disconnect MQTT client
        if self.mqtt_uncurated:
            self.mqtt_uncurated.disconnect()

        # Stop health server
        if self.health_server:
            self.health_server.shutdown()

        logger.info("Application stopped")

    def run(self):
        """Run the application (blocking)."""
        self.start()

        # Keep running until interrupted
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)


def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create and run application
    app = DataPublisherApp()
    try:
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
