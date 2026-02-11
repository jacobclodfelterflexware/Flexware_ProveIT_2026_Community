"""Modbus TCP client for OpenPLC Runtime I/O access."""
import os
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# Modbus configuration
MODBUS_HOST = os.getenv("MODBUS_HOST", "YOUR_K8S_SERVICE_HOST")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Try to import pymodbus, provide fallback if not available
try:
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException
    PYMODBUS_AVAILABLE = True
except ImportError:
    PYMODBUS_AVAILABLE = False
    logger.warning("pymodbus not installed - Modbus functionality will be limited")


class ModbusClient:
    """Modbus TCP client for reading/writing PLC I/O values."""

    # OpenPLC Modbus address mapping
    # %IX (Digital Inputs) -> Discrete Inputs (Function 2)
    # %QX (Digital Outputs) -> Coils (Function 1/5)
    # %IW (Analog Inputs) -> Input Registers (Function 4)
    # %QW (Analog Outputs) -> Holding Registers (Function 3/6)
    # %MW (Memory Words) -> Holding Registers (offset 1024)

    def __init__(
        self,
        host: str = MODBUS_HOST,
        port: int = MODBUS_PORT,
    ):
        """Initialize Modbus client.

        Args:
            host: Modbus server hostname
            port: Modbus server port (default 502)
        """
        self.host = host
        self.port = port
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to the Modbus server.

        Returns:
            True if connection successful
        """
        if not PYMODBUS_AVAILABLE:
            logger.error("pymodbus not installed")
            return False

        try:
            self._client = ModbusTcpClient(host=self.host, port=self.port)
            self._connected = self._client.connect()

            if self._connected:
                logger.info(f"Connected to Modbus server at {self.host}:{self.port}")
            else:
                logger.warning(f"Failed to connect to Modbus server")

            return self._connected

        except Exception as e:
            logger.error(f"Modbus connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the Modbus server."""
        if self._client:
            self._client.close()
            self._connected = False

    def ensure_connected(self) -> bool:
        """Ensure we're connected, connect if necessary."""
        if not self._connected:
            return self.connect()
        # Check if connection is still valid
        if self._client and not self._client.is_socket_open():
            logger.warning("Modbus socket closed, reconnecting...")
            self._connected = False
            return self.connect()
        return True

    def _reconnect_on_error(self) -> bool:
        """Reconnect if connection was lost."""
        self._connected = False
        return self.connect()

    def read_coils(self, address: int, count: int = 1, retry: bool = True) -> Dict[str, Any]:
        """Read digital outputs (coils) - %QX addresses.

        Args:
            address: Starting address (0-based)
            count: Number of coils to read
            retry: Whether to retry on connection error

        Returns:
            Dict with success status and values
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected", "values": []}

        try:
            result = self._client.read_coils(address, count=count)

            if result.isError():
                # Check for connection error and retry
                if retry and "Connection" in str(result):
                    logger.warning("Connection error, retrying...")
                    if self._reconnect_on_error():
                        return self.read_coils(address, count, retry=False)
                return {
                    "success": False,
                    "message": f"Read error: {result}",
                    "values": [],
                }

            return {
                "success": True,
                "values": list(result.bits[:count]),
            }

        except Exception as e:
            logger.error(f"Error reading coils: {e}")
            if retry:
                logger.warning("Attempting reconnection...")
                if self._reconnect_on_error():
                    return self.read_coils(address, count, retry=False)
            return {"success": False, "message": str(e), "values": []}

    def write_coil(self, address: int, value: bool) -> Dict[str, Any]:
        """Write a single digital output (coil) - %QX address.

        Args:
            address: Coil address (0-based)
            value: Boolean value to write

        Returns:
            Dict with success status
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected"}

        try:
            result = self._client.write_coil(address, value)

            if result.isError():
                return {"success": False, "message": f"Write error: {result}"}

            return {"success": True, "message": f"Coil {address} set to {value}"}

        except Exception as e:
            logger.error(f"Error writing coil: {e}")
            return {"success": False, "message": str(e)}

    def read_discrete_inputs(self, address: int, count: int = 1) -> Dict[str, Any]:
        """Read digital inputs - %IX addresses.

        Args:
            address: Starting address (0-based)
            count: Number of inputs to read

        Returns:
            Dict with success status and values
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected", "values": []}

        try:
            result = self._client.read_discrete_inputs(address, count=count)

            if result.isError():
                return {
                    "success": False,
                    "message": f"Read error: {result}",
                    "values": [],
                }

            return {
                "success": True,
                "values": list(result.bits[:count]),
            }

        except Exception as e:
            logger.error(f"Error reading discrete inputs: {e}")
            return {"success": False, "message": str(e), "values": []}

    def read_holding_registers(self, address: int, count: int = 1) -> Dict[str, Any]:
        """Read holding registers - %QW/%MW addresses.

        Args:
            address: Starting address (0-based)
            count: Number of registers to read

        Returns:
            Dict with success status and values
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected", "values": []}

        try:
            result = self._client.read_holding_registers(address, count=count)

            if result.isError():
                return {
                    "success": False,
                    "message": f"Read error: {result}",
                    "values": [],
                }

            return {
                "success": True,
                "values": list(result.registers),
            }

        except Exception as e:
            logger.error(f"Error reading holding registers: {e}")
            return {"success": False, "message": str(e), "values": []}

    def write_register(self, address: int, value: int) -> Dict[str, Any]:
        """Write a single holding register - %QW/%MW address.

        Args:
            address: Register address (0-based)
            value: 16-bit integer value to write

        Returns:
            Dict with success status
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected"}

        try:
            result = self._client.write_register(address, value)

            if result.isError():
                return {"success": False, "message": f"Write error: {result}"}

            return {"success": True, "message": f"Register {address} set to {value}"}

        except Exception as e:
            logger.error(f"Error writing register: {e}")
            return {"success": False, "message": str(e)}

    def read_input_registers(self, address: int, count: int = 1) -> Dict[str, Any]:
        """Read input registers - %IW addresses.

        Args:
            address: Starting address (0-based)
            count: Number of registers to read

        Returns:
            Dict with success status and values
        """
        if not self.ensure_connected():
            return {"success": False, "message": "Not connected", "values": []}

        try:
            result = self._client.read_input_registers(address, count=count)

            if result.isError():
                return {
                    "success": False,
                    "message": f"Read error: {result}",
                    "values": [],
                }

            return {
                "success": True,
                "values": list(result.registers),
            }

        except Exception as e:
            logger.error(f"Error reading input registers: {e}")
            return {"success": False, "message": str(e), "values": []}

    def read_all_io(self, digital_inputs: int = 8, digital_outputs: int = 8,
                    analog_inputs: int = 0, analog_outputs: int = 0,
                    memory_words: int = 0) -> Dict[str, Any]:
        """Read all I/O values at once.

        Args:
            digital_inputs: Number of digital inputs to read
            digital_outputs: Number of digital outputs to read
            analog_inputs: Number of analog inputs (input registers) to read
            analog_outputs: Number of analog outputs (holding registers) to read
            memory_words: Number of memory words to read (holding registers at offset 1024)

        Returns:
            Dict with all I/O values
        """
        io_values = {
            "digital_inputs": [],
            "digital_outputs": [],
            "analog_inputs": [],
            "analog_outputs": [],
            "memory_words": [],
        }

        # Read digital inputs (%IX)
        if digital_inputs > 0:
            result = self.read_discrete_inputs(0, digital_inputs)
            if result["success"]:
                io_values["digital_inputs"] = result["values"]

        # Read digital outputs (%QX)
        if digital_outputs > 0:
            result = self.read_coils(0, digital_outputs)
            if result["success"]:
                io_values["digital_outputs"] = result["values"]

        # Read analog inputs (%IW)
        if analog_inputs > 0:
            result = self.read_input_registers(0, analog_inputs)
            if result["success"]:
                io_values["analog_inputs"] = result["values"]

        # Read analog outputs (%QW)
        if analog_outputs > 0:
            result = self.read_holding_registers(0, analog_outputs)
            if result["success"]:
                io_values["analog_outputs"] = result["values"]

        # Read memory words (%MW) - offset 1024
        if memory_words > 0:
            result = self.read_holding_registers(1024, memory_words)
            if result["success"]:
                io_values["memory_words"] = result["values"]

        return {"success": True, "io": io_values}

    def write_io(self, io_values: Dict[str, Any]) -> Dict[str, Any]:
        """Write I/O values.

        Args:
            io_values: Dict with I/O values to write
                - digital_outputs: List of (address, value) tuples
                - analog_outputs: List of (address, value) tuples
                - memory_words: List of (address, value) tuples

        Returns:
            Dict with success status
        """
        errors = []

        # Write digital outputs
        for addr, val in io_values.get("digital_outputs", []):
            result = self.write_coil(addr, val)
            if not result["success"]:
                errors.append(f"Coil {addr}: {result['message']}")

        # Write analog outputs
        for addr, val in io_values.get("analog_outputs", []):
            result = self.write_register(addr, val)
            if not result["success"]:
                errors.append(f"Register {addr}: {result['message']}")

        # Write memory words (offset 1024)
        for addr, val in io_values.get("memory_words", []):
            result = self.write_register(1024 + addr, val)
            if not result["success"]:
                errors.append(f"Memory {addr}: {result['message']}")

        if errors:
            return {"success": False, "message": "; ".join(errors)}

        return {"success": True, "message": "I/O values written successfully"}


# Singleton instance
_client: Optional[ModbusClient] = None


def get_modbus_client() -> ModbusClient:
    """Get the Modbus client singleton."""
    global _client
    if _client is None:
        _client = ModbusClient()
    return _client
