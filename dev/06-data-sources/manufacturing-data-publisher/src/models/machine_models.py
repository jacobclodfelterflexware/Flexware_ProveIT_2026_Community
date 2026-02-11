"""Machine asset data models and simulators for 100 manufacturing assets."""
import random
import time
import json
from enum import Enum
from typing import Dict, Any


class MachineState(Enum):
    """Machine operational states."""
    STARTUP = "startup"
    RUNNING = "running"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    EMERGENCY_STOP = "emergency_stop"


class MachineType(Enum):
    """Types of manufacturing machines."""
    CNC_MILL = "cnc_mill"
    CNC_LATHE = "cnc_lathe"
    ROBOT = "robot"
    CONVEYOR = "conveyor"
    WELDER = "welder"
    PRESS = "press"
    GRINDER = "grinder"
    LASER_CUTTER = "laser_cutter"
    PRINTER_3D = "3d_printer"
    ASSEMBLY_STATION = "assembly_station"
    AGV = "agv"
    MILL = "mill"


class MachineAsset:
    """Simulated manufacturing machine asset."""

    def __init__(
        self,
        asset_id: str,
        machine_type: MachineType,
        area: str,
        line: str,
        cell: str,
        use_uns_topic: bool = True
    ):
        """Initialize machine asset.

        Args:
            asset_id: Unique asset identifier
            machine_type: Type of machine
            area: Manufacturing area (ISA-95)
            line: Production line
            cell: Work cell
            use_uns_topic: Whether to use UNS topic structure
        """
        self.asset_id = asset_id
        self.machine_type = machine_type
        self.area = area
        self.line = line
        self.cell = cell
        self.use_uns_topic = use_uns_topic

        # State management
        self.state = MachineState.IDLE
        self.state_start_time = time.time()

        # Telemetry variables with realistic initial values
        self.temperature = random.uniform(20.0, 25.0)  # Celsius
        self.vibration = random.uniform(0.1, 0.5)  # mm/s
        self.speed = 0.0  # RPM or units/min
        self.power_consumption = random.uniform(0.5, 2.0)  # kW
        self.cycle_count = 0
        self.runtime_hours = random.uniform(1000, 5000)
        self.good_parts = random.randint(5000, 50000)
        self.bad_parts = random.randint(10, 500)
        self.current_oee = random.uniform(0.75, 0.95)

        # Machine-specific parameters
        self._set_machine_parameters()

    def _set_machine_parameters(self):
        """Set machine-specific operating parameters."""
        params = {
            MachineType.CNC_MILL: {
                "max_speed": 8000,  # RPM
                "max_temp": 65.0,
                "max_vibration": 2.0,
                "max_power": 15.0,
            },
            MachineType.CNC_LATHE: {
                "max_speed": 3000,
                "max_temp": 60.0,
                "max_vibration": 1.5,
                "max_power": 12.0,
            },
            MachineType.ROBOT: {
                "max_speed": 100,  # cycles/hour
                "max_temp": 50.0,
                "max_vibration": 0.8,
                "max_power": 5.0,
            },
            MachineType.CONVEYOR: {
                "max_speed": 60,  # m/min
                "max_temp": 45.0,
                "max_vibration": 1.0,
                "max_power": 3.0,
            },
            MachineType.WELDER: {
                "max_speed": 30,  # welds/hour
                "max_temp": 80.0,
                "max_vibration": 0.5,
                "max_power": 20.0,
            },
            MachineType.PRESS: {
                "max_speed": 45,  # strokes/min
                "max_temp": 55.0,
                "max_vibration": 3.0,
                "max_power": 25.0,
            },
            MachineType.GRINDER: {
                "max_speed": 6000,
                "max_temp": 70.0,
                "max_vibration": 2.5,
                "max_power": 8.0,
            },
            MachineType.LASER_CUTTER: {
                "max_speed": 100,  # cuts/hour
                "max_temp": 40.0,
                "max_vibration": 0.3,
                "max_power": 6.0,
            },
            MachineType.PRINTER_3D: {
                "max_speed": 150,  # mm/s
                "max_temp": 220.0,  # Hotend temp
                "max_vibration": 0.4,
                "max_power": 0.5,
            },
            MachineType.ASSEMBLY_STATION: {
                "max_speed": 80,  # units/hour
                "max_temp": 30.0,
                "max_vibration": 0.2,
                "max_power": 2.0,
            },
            MachineType.AGV: {
                "max_speed": 2.0,  # m/s
                "max_temp": 45.0,
                "max_vibration": 0.6,
                "max_power": 4.0,
            },
            MachineType.MILL: {
                "max_speed": 5000,
                "max_temp": 65.0,
                "max_vibration": 2.2,
                "max_power": 18.0,
            },
        }

        self.params = params.get(self.machine_type, {
            "max_speed": 1000,
            "max_temp": 60.0,
            "max_vibration": 1.5,
            "max_power": 10.0,
        })

    def update_state(self):
        """Update machine state based on time and random events."""
        elapsed = time.time() - self.state_start_time

        # State transition logic
        if self.state == MachineState.STARTUP:
            if elapsed > random.uniform(5, 15):
                self.state = MachineState.RUNNING
                self.state_start_time = time.time()

        elif self.state == MachineState.RUNNING:
            # Random chance of transitioning to other states
            rand = random.random()
            if rand < 0.001:  # 0.1% chance of fault
                self.state = MachineState.FAULT
                self.state_start_time = time.time()
            elif rand < 0.005 and elapsed > 300:  # 0.5% chance of idle after 5 min
                self.state = MachineState.IDLE
                self.state_start_time = time.time()
            elif rand < 0.002 and elapsed > 3600:  # Maintenance after 1 hour
                self.state = MachineState.MAINTENANCE
                self.state_start_time = time.time()

        elif self.state == MachineState.IDLE:
            if elapsed > random.uniform(30, 120):
                self.state = MachineState.STARTUP
                self.state_start_time = time.time()

        elif self.state == MachineState.MAINTENANCE:
            if elapsed > random.uniform(300, 900):  # 5-15 min maintenance
                self.state = MachineState.STARTUP
                self.state_start_time = time.time()

        elif self.state == MachineState.FAULT:
            if elapsed > random.uniform(60, 300):  # 1-5 min to clear fault
                self.state = MachineState.STARTUP
                self.state_start_time = time.time()

    def update_telemetry(self):
        """Update telemetry values based on current state."""
        # Base values depend on state
        if self.state == MachineState.RUNNING:
            target_speed = self.params["max_speed"] * random.uniform(0.7, 0.95)
            target_temp = self.params["max_temp"] * random.uniform(0.6, 0.85)
            target_vibration = self.params["max_vibration"] * random.uniform(0.4, 0.7)
            target_power = self.params["max_power"] * random.uniform(0.6, 0.9)

            # Increment cycle count
            if random.random() < 0.1:  # 10% chance per update
                self.cycle_count += 1
                if random.random() < 0.97:  # 97% good parts
                    self.good_parts += 1
                else:
                    self.bad_parts += 1

        elif self.state == MachineState.STARTUP:
            target_speed = self.params["max_speed"] * random.uniform(0.2, 0.5)
            target_temp = self.temperature + random.uniform(1, 3)
            target_vibration = self.params["max_vibration"] * random.uniform(0.3, 0.6)
            target_power = self.params["max_power"] * random.uniform(0.4, 0.7)

        elif self.state == MachineState.FAULT:
            target_speed = 0
            target_temp = max(25, self.temperature - random.uniform(0.5, 1.5))
            target_vibration = self.params["max_vibration"] * random.uniform(1.2, 2.0)  # High vibration
            target_power = self.params["max_power"] * random.uniform(0.1, 0.3)

        else:  # IDLE, MAINTENANCE, EMERGENCY_STOP
            target_speed = 0
            target_temp = max(25, self.temperature - random.uniform(0.5, 2.0))  # Cool down
            target_vibration = self.params["max_vibration"] * random.uniform(0.05, 0.15)
            target_power = self.params["max_power"] * random.uniform(0.05, 0.2)

        # Smooth transitions with noise
        self.speed = self.speed * 0.8 + target_speed * 0.2 + random.uniform(-5, 5)
        self.temperature = self.temperature * 0.9 + target_temp * 0.1 + random.uniform(-0.5, 0.5)
        self.vibration = self.vibration * 0.85 + target_vibration * 0.15 + random.uniform(-0.05, 0.05)
        self.power_consumption = self.power_consumption * 0.8 + target_power * 0.2 + random.uniform(-0.2, 0.2)

        # Ensure values stay positive
        self.speed = max(0, self.speed)
        self.temperature = max(20, self.temperature)
        self.vibration = max(0, self.vibration)
        self.power_consumption = max(0, self.power_consumption)

        # Update runtime
        if self.state == MachineState.RUNNING:
            self.runtime_hours += (1.0 / 3600.0)  # Assuming 1 second updates

        # Calculate OEE (simplified)
        availability = 0.95 if self.state == MachineState.RUNNING else 0.0
        performance = min(1.0, self.speed / (self.params["max_speed"] * 0.8)) if self.speed > 0 else 0
        quality = self.good_parts / max(1, self.good_parts + self.bad_parts)
        self.current_oee = availability * performance * quality

    def get_mqtt_topic(self, metric: str, enterprise: str, site: str) -> str:
        """Generate MQTT topic based on configuration.

        Args:
            metric: Metric name (e.g., 'temperature', 'state')
            enterprise: Enterprise name (ISA-95)
            site: Site name (ISA-95)

        Returns:
            MQTT topic string
        """
        if self.use_uns_topic:
            # UNS format: enterprise/site/area/line/cell/asset_id/metric
            return f"{enterprise}/{site}/{self.area}/{self.line}/{self.cell}/{self.asset_id}/{metric}"
        else:
            # Flat format: machine/asset_id/metric
            return f"machine/{self.asset_id}/{metric}"

    def get_telemetry_data(self) -> Dict[str, Any]:
        """Get current telemetry data as dictionary.

        Returns:
            Dictionary with telemetry values
        """
        return {
            "timestamp": int(time.time() * 1000),  # milliseconds
            "asset_id": self.asset_id,
            "machine_type": self.machine_type.value,
            "state": self.state.value,
            "temperature": round(self.temperature, 2),
            "vibration": round(self.vibration, 3),
            "speed": round(self.speed, 1),
            "power_consumption": round(self.power_consumption, 2),
            "cycle_count": self.cycle_count,
            "runtime_hours": round(self.runtime_hours, 1),
            "good_parts": self.good_parts,
            "bad_parts": self.bad_parts,
            "oee": round(self.current_oee, 3),
            "area": self.area,
            "line": self.line,
            "cell": self.cell
        }

    def get_state_data(self) -> Dict[str, Any]:
        """Get current state data.

        Returns:
            Dictionary with state information
        """
        return {
            "timestamp": int(time.time() * 1000),
            "asset_id": self.asset_id,
            "state": self.state.value,
            "state_duration": int(time.time() - self.state_start_time)
        }


def create_machine_fleet(num_machines: int = 100) -> list[MachineAsset]:
    """Create a fleet of diverse manufacturing machines.

    Args:
        num_machines: Number of machines to create (default 100)

    Returns:
        List of MachineAsset instances
    """
    fleet = []

    # Distribution of machine types
    machine_distribution = [
        (MachineType.CNC_MILL, 15),
        (MachineType.ROBOT, 12),
        (MachineType.CONVEYOR, 10),
        (MachineType.WELDER, 8),
        (MachineType.PRESS, 8),
        (MachineType.AGV, 6),
        (MachineType.CNC_LATHE, 6),
        (MachineType.MILL, 6),
        (MachineType.GRINDER, 5),
        (MachineType.LASER_CUTTER, 5),
        (MachineType.PRINTER_3D, 4),
        (MachineType.ASSEMBLY_STATION, 15),
    ]

    # Manufacturing areas
    areas = ["stamping", "assembly", "welding", "machining", "finishing"]
    lines = ["line-a", "line-b", "line-c", "line-d"]
    cells = ["cell-01", "cell-02", "cell-03", "cell-04", "cell-05"]

    machine_id = 1
    for machine_type, count in machine_distribution:
        for i in range(count):
            area = random.choice(areas)
            line = random.choice(lines)
            cell = random.choice(cells)
            use_uns = random.random() < 0.7  # 70% UNS, 30% flat topics

            asset_id = f"{machine_type.value}_{machine_id:03d}"

            machine = MachineAsset(
                asset_id=asset_id,
                machine_type=machine_type,
                area=area,
                line=line,
                cell=cell,
                use_uns_topic=use_uns
            )

            fleet.append(machine)
            machine_id += 1

            if machine_id > num_machines:
                return fleet

    return fleet
