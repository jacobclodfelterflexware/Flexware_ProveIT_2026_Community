"""Enterprise system data models and simulators for 50 systems (ERP, MES, SCADA, DCS, WMS, AGV)."""
import random
import time
import json
from enum import Enum
from typing import Dict, Any, List


class EnterpriseSystemType(Enum):
    """Types of enterprise systems."""
    ERP = "erp"
    MES = "mes"
    SCADA = "scada"
    DCS = "dcs"
    WMS = "wms"
    AGV_CONTROLLER = "agv_controller"
    AMR_FLEET = "amr_fleet"
    QUALITY_SYSTEM = "quality_system"
    MAINTENANCE_SYSTEM = "maintenance_system"


class ERPModule(Enum):
    """ERP module types."""
    PRODUCTION_PLANNING = "production_planning"
    INVENTORY = "inventory"
    PROCUREMENT = "procurement"
    SALES_ORDER = "sales_order"
    QUALITY_MANAGEMENT = "quality_management"


class EnterpriseSystem:
    """Simulated enterprise system asset."""

    def __init__(
        self,
        system_id: str,
        system_type: EnterpriseSystemType,
        vendor: str,
        use_uns_topic: bool = True
    ):
        """Initialize enterprise system.

        Args:
            system_id: Unique system identifier
            system_type: Type of enterprise system
            vendor: System vendor/product name
            use_uns_topic: Whether to use UNS topic structure
        """
        self.system_id = system_id
        self.system_type = system_type
        self.vendor = vendor
        self.use_uns_topic = use_uns_topic

        # System health
        self.cpu_usage = random.uniform(20, 40)
        self.memory_usage = random.uniform(30, 50)
        self.active_connections = random.randint(10, 100)
        self.response_time_ms = random.uniform(50, 200)

        # Initialize type-specific data
        self._init_type_specific_data()

    def _init_type_specific_data(self):
        """Initialize data specific to system type."""
        if self.system_type == EnterpriseSystemType.ERP:
            self.open_orders = random.randint(50, 500)
            self.inventory_items = random.randint(1000, 10000)
            self.pending_shipments = random.randint(20, 200)
            self.module = random.choice(list(ERPModule))

        elif self.system_type == EnterpriseSystemType.MES:
            self.active_work_orders = random.randint(10, 100)
            self.completed_today = random.randint(50, 500)
            self.in_progress = random.randint(5, 50)
            self.rejected_count = random.randint(0, 20)
            self.batch_id = f"BATCH-{random.randint(1000, 9999)}"

        elif self.system_type == EnterpriseSystemType.SCADA:
            self.tag_count = random.randint(500, 5000)
            self.alarms_active = random.randint(0, 15)
            self.alarms_today = random.randint(10, 100)
            self.plc_connections = random.randint(5, 50)
            self.scan_rate_ms = random.randint(100, 1000)

        elif self.system_type == EnterpriseSystemType.DCS:
            self.control_loops = random.randint(50, 500)
            self.loops_in_manual = random.randint(0, 10)
            self.process_variables = random.randint(200, 2000)
            self.alarms_active = random.randint(0, 20)
            self.controller_health = "good"

        elif self.system_type == EnterpriseSystemType.WMS:
            self.inventory_locations = random.randint(500, 5000)
            self.active_picks = random.randint(10, 100)
            self.pending_putaways = random.randint(5, 50)
            self.shipments_today = random.randint(20, 200)
            self.inventory_accuracy = random.uniform(0.95, 0.99)

        elif self.system_type in [EnterpriseSystemType.AGV_CONTROLLER, EnterpriseSystemType.AMR_FLEET]:
            self.total_vehicles = random.randint(5, 50)
            self.vehicles_active = random.randint(3, 40)
            self.vehicles_charging = random.randint(1, 10)
            self.vehicles_idle = random.randint(0, 5)
            self.vehicles_fault = random.randint(0, 2)
            self.missions_completed = random.randint(100, 1000)
            self.missions_pending = random.randint(5, 50)

        elif self.system_type == EnterpriseSystemType.QUALITY_SYSTEM:
            self.inspections_today = random.randint(50, 500)
            self.passed = random.randint(45, 480)
            self.failed = random.randint(5, 20)
            self.pending_review = random.randint(0, 10)
            self.defect_rate = random.uniform(0.01, 0.05)

        elif self.system_type == EnterpriseSystemType.MAINTENANCE_SYSTEM:
            self.work_orders_open = random.randint(20, 200)
            self.work_orders_completed_today = random.randint(5, 50)
            self.preventive_due = random.randint(10, 100)
            self.emergency_repairs = random.randint(0, 5)
            self.mtbf_hours = random.uniform(500, 2000)

    def update_data(self):
        """Update system data with realistic changes."""
        # Update common metrics
        self.cpu_usage += random.uniform(-5, 5)
        self.cpu_usage = max(10, min(95, self.cpu_usage))

        self.memory_usage += random.uniform(-3, 3)
        self.memory_usage = max(20, min(90, self.memory_usage))

        self.active_connections += random.randint(-5, 5)
        self.active_connections = max(1, self.active_connections)

        self.response_time_ms += random.uniform(-20, 20)
        self.response_time_ms = max(10, min(5000, self.response_time_ms))

        # Update type-specific data
        if self.system_type == EnterpriseSystemType.ERP:
            if random.random() < 0.1:
                self.open_orders += random.randint(-5, 10)
                self.open_orders = max(0, self.open_orders)
            if random.random() < 0.05:
                self.pending_shipments += random.randint(-3, 5)
                self.pending_shipments = max(0, self.pending_shipments)

        elif self.system_type == EnterpriseSystemType.MES:
            if random.random() < 0.15:
                # Complete a work order
                if self.in_progress > 0:
                    self.in_progress -= 1
                    self.completed_today += 1
            if random.random() < 0.1:
                # Start new work order
                self.in_progress += 1
                self.active_work_orders += 1

        elif self.system_type == EnterpriseSystemType.SCADA:
            if random.random() < 0.05:
                # New alarm
                self.alarms_active += random.randint(0, 2)
                self.alarms_today += random.randint(0, 2)
            if random.random() < 0.08 and self.alarms_active > 0:
                # Clear alarm
                self.alarms_active -= 1

        elif self.system_type == EnterpriseSystemType.DCS:
            if random.random() < 0.03:
                # Loop mode change
                self.loops_in_manual += random.randint(-1, 1)
                self.loops_in_manual = max(0, min(self.control_loops // 10, self.loops_in_manual))

        elif self.system_type == EnterpriseSystemType.WMS:
            if random.random() < 0.2:
                self.active_picks += random.randint(-5, 8)
                self.active_picks = max(0, self.active_picks)
            if random.random() < 0.1:
                self.shipments_today += random.randint(0, 3)

        elif self.system_type in [EnterpriseSystemType.AGV_CONTROLLER, EnterpriseSystemType.AMR_FLEET]:
            if random.random() < 0.1:
                # Update vehicle states
                total = self.total_vehicles
                self.vehicles_active += random.randint(-2, 3)
                self.vehicles_charging += random.randint(-1, 2)
                self.vehicles_idle += random.randint(-1, 2)

                # Ensure totals are reasonable
                self.vehicles_active = max(0, min(total, self.vehicles_active))
                self.vehicles_charging = max(0, min(total - self.vehicles_active, self.vehicles_charging))
                self.vehicles_idle = max(0, total - self.vehicles_active - self.vehicles_charging - self.vehicles_fault)

            if random.random() < 0.15:
                # Complete missions
                completed = random.randint(0, 3)
                self.missions_completed += completed
                self.missions_pending = max(0, self.missions_pending - completed)

        elif self.system_type == EnterpriseSystemType.QUALITY_SYSTEM:
            if random.random() < 0.1:
                # New inspection
                self.inspections_today += 1
                if random.random() < 0.95:
                    self.passed += 1
                else:
                    self.failed += 1
                self.defect_rate = self.failed / max(1, self.inspections_today)

        elif self.system_type == EnterpriseSystemType.MAINTENANCE_SYSTEM:
            if random.random() < 0.08:
                # Complete work order
                if self.work_orders_open > 0:
                    self.work_orders_open -= 1
                    self.work_orders_completed_today += 1

    def get_mqtt_topic(self, metric: str, enterprise: str) -> str:
        """Generate MQTT topic based on configuration.

        Args:
            metric: Metric name
            enterprise: Enterprise name

        Returns:
            MQTT topic string
        """
        if self.use_uns_topic:
            # UNS format: enterprise/systems/system_type/system_id/metric
            return f"{enterprise}/systems/{self.system_type.value}/{self.system_id}/{metric}"
        else:
            # Flat format: system_type/system_id/metric
            return f"{self.system_type.value}/{self.system_id}/{metric}"

    def get_data(self) -> Dict[str, Any]:
        """Get current system data.

        Returns:
            Dictionary with system data
        """
        base_data = {
            "timestamp": int(time.time() * 1000),
            "system_id": self.system_id,
            "system_type": self.system_type.value,
            "vendor": self.vendor,
            "cpu_usage": round(self.cpu_usage, 2),
            "memory_usage": round(self.memory_usage, 2),
            "active_connections": self.active_connections,
            "response_time_ms": round(self.response_time_ms, 1)
        }

        # Add type-specific data
        if self.system_type == EnterpriseSystemType.ERP:
            base_data.update({
                "module": self.module.value,
                "open_orders": self.open_orders,
                "inventory_items": self.inventory_items,
                "pending_shipments": self.pending_shipments
            })

        elif self.system_type == EnterpriseSystemType.MES:
            base_data.update({
                "active_work_orders": self.active_work_orders,
                "completed_today": self.completed_today,
                "in_progress": self.in_progress,
                "rejected_count": self.rejected_count,
                "batch_id": self.batch_id
            })

        elif self.system_type == EnterpriseSystemType.SCADA:
            base_data.update({
                "tag_count": self.tag_count,
                "alarms_active": self.alarms_active,
                "alarms_today": self.alarms_today,
                "plc_connections": self.plc_connections,
                "scan_rate_ms": self.scan_rate_ms
            })

        elif self.system_type == EnterpriseSystemType.DCS:
            base_data.update({
                "control_loops": self.control_loops,
                "loops_in_manual": self.loops_in_manual,
                "process_variables": self.process_variables,
                "alarms_active": self.alarms_active,
                "controller_health": self.controller_health
            })

        elif self.system_type == EnterpriseSystemType.WMS:
            base_data.update({
                "inventory_locations": self.inventory_locations,
                "active_picks": self.active_picks,
                "pending_putaways": self.pending_putaways,
                "shipments_today": self.shipments_today,
                "inventory_accuracy": round(self.inventory_accuracy, 4)
            })

        elif self.system_type in [EnterpriseSystemType.AGV_CONTROLLER, EnterpriseSystemType.AMR_FLEET]:
            base_data.update({
                "total_vehicles": self.total_vehicles,
                "vehicles_active": self.vehicles_active,
                "vehicles_charging": self.vehicles_charging,
                "vehicles_idle": self.vehicles_idle,
                "vehicles_fault": self.vehicles_fault,
                "missions_completed": self.missions_completed,
                "missions_pending": self.missions_pending
            })

        elif self.system_type == EnterpriseSystemType.QUALITY_SYSTEM:
            base_data.update({
                "inspections_today": self.inspections_today,
                "passed": self.passed,
                "failed": self.failed,
                "pending_review": self.pending_review,
                "defect_rate": round(self.defect_rate, 4)
            })

        elif self.system_type == EnterpriseSystemType.MAINTENANCE_SYSTEM:
            base_data.update({
                "work_orders_open": self.work_orders_open,
                "work_orders_completed_today": self.work_orders_completed_today,
                "preventive_due": self.preventive_due,
                "emergency_repairs": self.emergency_repairs,
                "mtbf_hours": round(self.mtbf_hours, 1)
            })

        return base_data


def create_enterprise_systems(num_systems: int = 50) -> List[EnterpriseSystem]:
    """Create a fleet of diverse enterprise systems.

    Args:
        num_systems: Number of systems to create (default 50)

    Returns:
        List of EnterpriseSystem instances
    """
    systems = []

    # System type distribution and vendor mapping
    system_configs = [
        (EnterpriseSystemType.ERP, 5, ["SAP", "Oracle", "Microsoft Dynamics", "Infor", "Epicor"]),
        (EnterpriseSystemType.MES, 8, ["Wonderware", "Rockwell FactoryTalk", "Siemens Opcenter", "Parsec", "AVEVA MES"]),
        (EnterpriseSystemType.SCADA, 10, ["Ignition", "Wonderware", "Siemens WinCC", "GE iFIX", "Rockwell RSView"]),
        (EnterpriseSystemType.DCS, 8, ["Siemens PCS7", "Honeywell Experion", "Emerson DeltaV", "ABB 800xA", "Yokogawa Centum"]),
        (EnterpriseSystemType.WMS, 4, ["Manhattan", "Blue Yonder", "SAP EWM", "Oracle WMS"]),
        (EnterpriseSystemType.AGV_CONTROLLER, 5, ["Balyo", "Seegrid", "Fetch Robotics", "MiR Fleet", "AutoGuide"]),
        (EnterpriseSystemType.AMR_FLEET, 0, []),  # Will be added to AGV count
        (EnterpriseSystemType.QUALITY_SYSTEM, 5, ["InfinityQS", "Minitab", "ETQ Reliance", "MasterControl", "Arena QMS"]),
        (EnterpriseSystemType.MAINTENANCE_SYSTEM, 5, ["IBM Maximo", "SAP PM", "Infor EAM", "Fiix", "eMaint"]),
    ]

    system_id = 1
    for system_type, count, vendors in system_configs:
        for i in range(count):
            vendor = random.choice(vendors) if vendors else "Generic"
            use_uns = random.random() < 0.6  # 60% UNS, 40% flat topics

            sys_id = f"{system_type.value}_{system_id:03d}"

            system = EnterpriseSystem(
                system_id=sys_id,
                system_type=system_type,
                vendor=vendor,
                use_uns_topic=use_uns
            )

            systems.append(system)
            system_id += 1

            if system_id > num_systems:
                return systems

    return systems
