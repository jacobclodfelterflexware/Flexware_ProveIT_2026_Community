"""MQTT client utility with automatic reconnection."""
import paho.mqtt.client as mqtt
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client wrapper with automatic reconnection."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        username: str,
        password: str,
        client_id: str,
        qos: int = 1
    ):
        """Initialize MQTT client.

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            username: MQTT username
            password: MQTT password
            client_id: Unique client ID
            qos: Quality of Service level (0, 1, or 2)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.qos = qos
        self.client: Optional[mqtt.Client] = None
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker {self.broker_host}:{self.broker_port}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")

    def _on_publish(self, client, userdata, mid):
        """Callback for when a message is published."""
        logger.debug(f"Message {mid} published successfully")

    def connect(self):
        """Connect to MQTT broker with automatic reconnection."""
        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.username_pw_set(self.username, self.password)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            logger.info(f"Connecting to MQTT broker {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()

            # Wait for connection
            timeout = 30
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self.connected:
                raise ConnectionError(f"Failed to connect to MQTT broker within {timeout}s")

            logger.info(f"Successfully connected to {self.broker_host}:{self.broker_port}")
            return True

        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def publish(self, topic: str, payload: str, retain: bool = False):
        """Publish a message to the MQTT broker.

        Args:
            topic: MQTT topic
            payload: Message payload (JSON string)
            retain: Whether to retain the message on the broker
        """
        if not self.connected or not self.client:
            logger.warning(f"Not connected to MQTT broker. Message not published to {topic}")
            return False

        try:
            result = self.client.publish(
                topic=topic,
                payload=payload,
                qos=self.qos,
                retain=retain
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload[:100]}...")
                return True
            else:
                logger.warning(f"Failed to publish to {topic}. Return code: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info(f"Disconnected from {self.broker_host}:{self.broker_port}")

    def is_connected(self):
        """Check if client is connected."""
        return self.connected
