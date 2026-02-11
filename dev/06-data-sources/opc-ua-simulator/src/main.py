import asyncio
import random
import math
from asyncua import Server, ua


async def main():
    server = Server()
    await server.init()

    server.set_endpoint("opc.tcp://0.0.0.0:YOUR_OPCUA_PORT/freeopcua/server/")
    server.set_server_name("Manufacturing OPC UA Simulator")

    # Set security policies - allow anonymous connections
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    server.set_security_IDs(["Anonymous"])

    # Set up namespace
    uri = "http://manufacturing.simulator"
    idx = await server.register_namespace(uri)

    # Get objects node
    objects = server.nodes.objects

    # Dictionary to hold all tag references for simulation
    tags = {}

    # === CNC Mill 01 ===
    cnc_mill_01 = await objects.add_folder(idx, "CNC_Mill_01")
    cnc_mill_01_status = await cnc_mill_01.add_folder(idx, "Status")
    tags["cnc_mill_01_running"] = await cnc_mill_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["cnc_mill_01_faulted"] = await cnc_mill_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["cnc_mill_01_machine_state"] = await cnc_mill_01_status.add_variable(idx, "MachineState", 1, ua.VariantType.Int32)
    tags["cnc_mill_01_part_count"] = await cnc_mill_01_status.add_variable(idx, "PartCount", 0, ua.VariantType.Int32)

    cnc_mill_01_spindle = await cnc_mill_01.add_folder(idx, "Spindle")
    tags["cnc_mill_01_spindle_speed"] = await cnc_mill_01_spindle.add_variable(idx, "Speed", 12000.0, ua.VariantType.Double)
    tags["cnc_mill_01_spindle_load"] = await cnc_mill_01_spindle.add_variable(idx, "Load", 45.0, ua.VariantType.Double)
    tags["cnc_mill_01_spindle_temp"] = await cnc_mill_01_spindle.add_variable(idx, "Temperature", 42.0, ua.VariantType.Double)

    cnc_mill_01_axis = await cnc_mill_01.add_folder(idx, "Axis")
    tags["cnc_mill_01_x_pos"] = await cnc_mill_01_axis.add_variable(idx, "X_Position", 0.0, ua.VariantType.Double)
    tags["cnc_mill_01_y_pos"] = await cnc_mill_01_axis.add_variable(idx, "Y_Position", 0.0, ua.VariantType.Double)
    tags["cnc_mill_01_z_pos"] = await cnc_mill_01_axis.add_variable(idx, "Z_Position", 0.0, ua.VariantType.Double)

    # === CNC Mill 02 ===
    cnc_mill_02 = await objects.add_folder(idx, "CNC_Mill_02")
    cnc_mill_02_status = await cnc_mill_02.add_folder(idx, "Status")
    tags["cnc_mill_02_running"] = await cnc_mill_02_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["cnc_mill_02_faulted"] = await cnc_mill_02_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["cnc_mill_02_machine_state"] = await cnc_mill_02_status.add_variable(idx, "MachineState", 1, ua.VariantType.Int32)
    tags["cnc_mill_02_part_count"] = await cnc_mill_02_status.add_variable(idx, "PartCount", 0, ua.VariantType.Int32)

    cnc_mill_02_spindle = await cnc_mill_02.add_folder(idx, "Spindle")
    tags["cnc_mill_02_spindle_speed"] = await cnc_mill_02_spindle.add_variable(idx, "Speed", 10000.0, ua.VariantType.Double)
    tags["cnc_mill_02_spindle_load"] = await cnc_mill_02_spindle.add_variable(idx, "Load", 52.0, ua.VariantType.Double)
    tags["cnc_mill_02_spindle_temp"] = await cnc_mill_02_spindle.add_variable(idx, "Temperature", 38.0, ua.VariantType.Double)

    cnc_mill_02_axis = await cnc_mill_02.add_folder(idx, "Axis")
    tags["cnc_mill_02_x_pos"] = await cnc_mill_02_axis.add_variable(idx, "X_Position", 0.0, ua.VariantType.Double)
    tags["cnc_mill_02_y_pos"] = await cnc_mill_02_axis.add_variable(idx, "Y_Position", 0.0, ua.VariantType.Double)
    tags["cnc_mill_02_z_pos"] = await cnc_mill_02_axis.add_variable(idx, "Z_Position", 0.0, ua.VariantType.Double)

    # === CNC Lathe 01 ===
    cnc_lathe_01 = await objects.add_folder(idx, "CNC_Lathe_01")
    cnc_lathe_01_status = await cnc_lathe_01.add_folder(idx, "Status")
    tags["cnc_lathe_01_running"] = await cnc_lathe_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["cnc_lathe_01_faulted"] = await cnc_lathe_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["cnc_lathe_01_machine_state"] = await cnc_lathe_01_status.add_variable(idx, "MachineState", 1, ua.VariantType.Int32)
    tags["cnc_lathe_01_part_count"] = await cnc_lathe_01_status.add_variable(idx, "PartCount", 0, ua.VariantType.Int32)

    cnc_lathe_01_spindle = await cnc_lathe_01.add_folder(idx, "Spindle")
    tags["cnc_lathe_01_spindle_speed"] = await cnc_lathe_01_spindle.add_variable(idx, "Speed", 2500.0, ua.VariantType.Double)
    tags["cnc_lathe_01_spindle_load"] = await cnc_lathe_01_spindle.add_variable(idx, "Load", 35.0, ua.VariantType.Double)
    tags["cnc_lathe_01_spindle_temp"] = await cnc_lathe_01_spindle.add_variable(idx, "Temperature", 40.0, ua.VariantType.Double)

    cnc_lathe_01_axis = await cnc_lathe_01.add_folder(idx, "Axis")
    tags["cnc_lathe_01_x_pos"] = await cnc_lathe_01_axis.add_variable(idx, "X_Position", 0.0, ua.VariantType.Double)
    tags["cnc_lathe_01_z_pos"] = await cnc_lathe_01_axis.add_variable(idx, "Z_Position", 0.0, ua.VariantType.Double)

    # === Press 01 ===
    press_01 = await objects.add_folder(idx, "Press_01")
    press_01_status = await press_01.add_folder(idx, "Status")
    tags["press_01_running"] = await press_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["press_01_faulted"] = await press_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["press_01_cycle_count"] = await press_01_status.add_variable(idx, "CycleCount", 0, ua.VariantType.Int32)

    press_01_hydraulics = await press_01.add_folder(idx, "Hydraulics")
    tags["press_01_pressure"] = await press_01_hydraulics.add_variable(idx, "Pressure", 2500.0, ua.VariantType.Double)
    tags["press_01_hyd_temp"] = await press_01_hydraulics.add_variable(idx, "Temperature", 45.0, ua.VariantType.Double)

    press_01_die = await press_01.add_folder(idx, "Die")
    tags["press_01_die_position"] = await press_01_die.add_variable(idx, "Position", 0.0, ua.VariantType.Double)
    tags["press_01_die_force"] = await press_01_die.add_variable(idx, "Force", 0.0, ua.VariantType.Double)

    # === Press 02 ===
    press_02 = await objects.add_folder(idx, "Press_02")
    press_02_status = await press_02.add_folder(idx, "Status")
    tags["press_02_running"] = await press_02_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["press_02_faulted"] = await press_02_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["press_02_cycle_count"] = await press_02_status.add_variable(idx, "CycleCount", 0, ua.VariantType.Int32)

    press_02_hydraulics = await press_02.add_folder(idx, "Hydraulics")
    tags["press_02_pressure"] = await press_02_hydraulics.add_variable(idx, "Pressure", 2800.0, ua.VariantType.Double)
    tags["press_02_hyd_temp"] = await press_02_hydraulics.add_variable(idx, "Temperature", 48.0, ua.VariantType.Double)

    press_02_die = await press_02.add_folder(idx, "Die")
    tags["press_02_die_position"] = await press_02_die.add_variable(idx, "Position", 0.0, ua.VariantType.Double)
    tags["press_02_die_force"] = await press_02_die.add_variable(idx, "Force", 0.0, ua.VariantType.Double)

    # === Conveyor 01 ===
    conveyor_01 = await objects.add_folder(idx, "Conveyor_01")
    conveyor_01_status = await conveyor_01.add_folder(idx, "Status")
    tags["conveyor_01_running"] = await conveyor_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["conveyor_01_faulted"] = await conveyor_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["conveyor_01_speed"] = await conveyor_01_status.add_variable(idx, "Speed", 1.5, ua.VariantType.Double)

    conveyor_01_sensors = await conveyor_01.add_folder(idx, "Sensors")
    tags["conveyor_01_entry_pe"] = await conveyor_01_sensors.add_variable(idx, "EntryPhotoeye", False, ua.VariantType.Boolean)
    tags["conveyor_01_exit_pe"] = await conveyor_01_sensors.add_variable(idx, "ExitPhotoeye", False, ua.VariantType.Boolean)
    tags["conveyor_01_item_count"] = await conveyor_01_sensors.add_variable(idx, "ItemCount", 0, ua.VariantType.Int32)

    # === Conveyor 02 ===
    conveyor_02 = await objects.add_folder(idx, "Conveyor_02")
    conveyor_02_status = await conveyor_02.add_folder(idx, "Status")
    tags["conveyor_02_running"] = await conveyor_02_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["conveyor_02_faulted"] = await conveyor_02_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["conveyor_02_speed"] = await conveyor_02_status.add_variable(idx, "Speed", 2.0, ua.VariantType.Double)

    conveyor_02_sensors = await conveyor_02.add_folder(idx, "Sensors")
    tags["conveyor_02_entry_pe"] = await conveyor_02_sensors.add_variable(idx, "EntryPhotoeye", False, ua.VariantType.Boolean)
    tags["conveyor_02_exit_pe"] = await conveyor_02_sensors.add_variable(idx, "ExitPhotoeye", False, ua.VariantType.Boolean)
    tags["conveyor_02_item_count"] = await conveyor_02_sensors.add_variable(idx, "ItemCount", 0, ua.VariantType.Int32)

    # === Robot 01 ===
    robot_01 = await objects.add_folder(idx, "Robot_01")
    robot_01_status = await robot_01.add_folder(idx, "Status")
    tags["robot_01_running"] = await robot_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["robot_01_faulted"] = await robot_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["robot_01_mode"] = await robot_01_status.add_variable(idx, "Mode", 2, ua.VariantType.Int32)  # 0=Manual, 1=Auto, 2=Running
    tags["robot_01_cycle_count"] = await robot_01_status.add_variable(idx, "CycleCount", 0, ua.VariantType.Int32)

    robot_01_position = await robot_01.add_folder(idx, "Position")
    tags["robot_01_j1"] = await robot_01_position.add_variable(idx, "J1", 0.0, ua.VariantType.Double)
    tags["robot_01_j2"] = await robot_01_position.add_variable(idx, "J2", -45.0, ua.VariantType.Double)
    tags["robot_01_j3"] = await robot_01_position.add_variable(idx, "J3", 90.0, ua.VariantType.Double)
    tags["robot_01_j4"] = await robot_01_position.add_variable(idx, "J4", 0.0, ua.VariantType.Double)
    tags["robot_01_j5"] = await robot_01_position.add_variable(idx, "J5", 45.0, ua.VariantType.Double)
    tags["robot_01_j6"] = await robot_01_position.add_variable(idx, "J6", 0.0, ua.VariantType.Double)

    robot_01_tcp = await robot_01.add_folder(idx, "TCP")
    tags["robot_01_tcp_x"] = await robot_01_tcp.add_variable(idx, "X", 500.0, ua.VariantType.Double)
    tags["robot_01_tcp_y"] = await robot_01_tcp.add_variable(idx, "Y", 0.0, ua.VariantType.Double)
    tags["robot_01_tcp_z"] = await robot_01_tcp.add_variable(idx, "Z", 800.0, ua.VariantType.Double)

    # === Packaging Line 01 ===
    packaging_01 = await objects.add_folder(idx, "PackagingLine_01")
    packaging_01_status = await packaging_01.add_folder(idx, "Status")
    tags["packaging_01_running"] = await packaging_01_status.add_variable(idx, "Running", True, ua.VariantType.Boolean)
    tags["packaging_01_faulted"] = await packaging_01_status.add_variable(idx, "Faulted", False, ua.VariantType.Boolean)
    tags["packaging_01_upm"] = await packaging_01_status.add_variable(idx, "UnitsPerMinute", 120.0, ua.VariantType.Double)

    packaging_01_counts = await packaging_01.add_folder(idx, "Counts")
    tags["packaging_01_good_count"] = await packaging_01_counts.add_variable(idx, "GoodCount", 0, ua.VariantType.Int32)
    tags["packaging_01_reject_count"] = await packaging_01_counts.add_variable(idx, "RejectCount", 0, ua.VariantType.Int32)
    tags["packaging_01_total_count"] = await packaging_01_counts.add_variable(idx, "TotalCount", 0, ua.VariantType.Int32)

    # Make all tags writable
    for tag in tags.values():
        await tag.set_writable()

    print(f"OPC UA Server starting on opc.tcp://0.0.0.0:YOUR_OPCUA_PORT")
    print(f"Total tags created: {len(tags)}")

    async with server:
        tick = 0
        while True:
            await asyncio.sleep(1)
            tick += 1

            # Simulation logic

            # --- CNC Mill 01 ---
            running_1 = await tags["cnc_mill_01_running"].read_value()
            if running_1:
                # Spindle speed varies around setpoint
                speed = 12000 + random.uniform(-200, 200)
                await tags["cnc_mill_01_spindle_speed"].write_value(speed)

                # Load varies
                load = 45 + random.uniform(-5, 5)
                await tags["cnc_mill_01_spindle_load"].write_value(load)

                # Temperature slowly wanders
                temp = await tags["cnc_mill_01_spindle_temp"].read_value()
                temp = float(temp) + random.uniform(-0.5, 0.5)
                temp = max(35.0, min(55.0, temp))
                await tags["cnc_mill_01_spindle_temp"].write_value(temp)

                # Axis positions - sinusoidal motion
                await tags["cnc_mill_01_x_pos"].write_value(100 * math.sin(tick * 0.1))
                await tags["cnc_mill_01_y_pos"].write_value(50 * math.cos(tick * 0.1))
                await tags["cnc_mill_01_z_pos"].write_value(-20 + 10 * math.sin(tick * 0.2))

                # Part count increments every ~30 seconds
                if tick % 30 == 0:
                    count = await tags["cnc_mill_01_part_count"].read_value()
                    await tags["cnc_mill_01_part_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            # Random fault toggle (rare)
            if random.random() < 0.001:
                faulted = await tags["cnc_mill_01_faulted"].read_value()
                await tags["cnc_mill_01_faulted"].write_value(not faulted)

            # --- CNC Mill 02 ---
            running_2 = await tags["cnc_mill_02_running"].read_value()
            if running_2:
                speed = 10000 + random.uniform(-150, 150)
                await tags["cnc_mill_02_spindle_speed"].write_value(speed)

                load = 52 + random.uniform(-4, 4)
                await tags["cnc_mill_02_spindle_load"].write_value(load)

                temp = await tags["cnc_mill_02_spindle_temp"].read_value()
                temp = float(temp) + random.uniform(-0.4, 0.4)
                temp = max(32.0, min(50.0, temp))
                await tags["cnc_mill_02_spindle_temp"].write_value(temp)

                await tags["cnc_mill_02_x_pos"].write_value(80 * math.sin(tick * 0.12))
                await tags["cnc_mill_02_y_pos"].write_value(60 * math.cos(tick * 0.08))
                await tags["cnc_mill_02_z_pos"].write_value(-15 + 8 * math.sin(tick * 0.15))

                if tick % 25 == 0:
                    count = await tags["cnc_mill_02_part_count"].read_value()
                    await tags["cnc_mill_02_part_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["cnc_mill_02_faulted"].read_value()
                await tags["cnc_mill_02_faulted"].write_value(not faulted)

            # --- CNC Lathe 01 ---
            running_lathe = await tags["cnc_lathe_01_running"].read_value()
            if running_lathe:
                speed = 2500 + random.uniform(-100, 100)
                await tags["cnc_lathe_01_spindle_speed"].write_value(speed)

                load = 35 + random.uniform(-3, 3)
                await tags["cnc_lathe_01_spindle_load"].write_value(load)

                temp = await tags["cnc_lathe_01_spindle_temp"].read_value()
                temp = float(temp) + random.uniform(-0.3, 0.3)
                temp = max(35.0, min(52.0, temp))
                await tags["cnc_lathe_01_spindle_temp"].write_value(temp)

                await tags["cnc_lathe_01_x_pos"].write_value(25 * math.sin(tick * 0.2))
                await tags["cnc_lathe_01_z_pos"].write_value(150 * math.sin(tick * 0.05))

                if tick % 20 == 0:
                    count = await tags["cnc_lathe_01_part_count"].read_value()
                    await tags["cnc_lathe_01_part_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["cnc_lathe_01_faulted"].read_value()
                await tags["cnc_lathe_01_faulted"].write_value(not faulted)

            # --- Press 01 ---
            running_press_1 = await tags["press_01_running"].read_value()
            if running_press_1:
                # Press cycle simulation
                cycle_phase = (tick % 10) / 10.0  # 10 second cycle

                if cycle_phase < 0.3:  # Die moving down
                    position = cycle_phase / 0.3 * 100
                    force = 0.0
                elif cycle_phase < 0.5:  # Pressing
                    position = 100.0
                    force = 2500.0 + random.uniform(-50, 50)
                elif cycle_phase < 0.8:  # Die moving up
                    position = 100.0 - ((cycle_phase - 0.5) / 0.3 * 100)
                    force = 0.0
                else:  # Dwell
                    position = 0.0
                    force = 0.0

                await tags["press_01_die_position"].write_value(position)
                await tags["press_01_die_force"].write_value(force)

                pressure = 2500 + random.uniform(-30, 30)
                await tags["press_01_pressure"].write_value(pressure)

                temp = await tags["press_01_hyd_temp"].read_value()
                temp = float(temp) + random.uniform(-0.2, 0.3)
                temp = max(40.0, min(60.0, temp))
                await tags["press_01_hyd_temp"].write_value(temp)

                if tick % 10 == 0:
                    count = await tags["press_01_cycle_count"].read_value()
                    await tags["press_01_cycle_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["press_01_faulted"].read_value()
                await tags["press_01_faulted"].write_value(not faulted)

            # --- Press 02 ---
            running_press_2 = await tags["press_02_running"].read_value()
            if running_press_2:
                cycle_phase = ((tick + 5) % 12) / 12.0  # 12 second cycle, offset

                if cycle_phase < 0.3:
                    position = cycle_phase / 0.3 * 100
                    force = 0.0
                elif cycle_phase < 0.5:
                    position = 100.0
                    force = 2800.0 + random.uniform(-60, 60)
                elif cycle_phase < 0.8:
                    position = 100.0 - ((cycle_phase - 0.5) / 0.3 * 100)
                    force = 0.0
                else:
                    position = 0.0
                    force = 0.0

                await tags["press_02_die_position"].write_value(position)
                await tags["press_02_die_force"].write_value(force)

                pressure = 2800 + random.uniform(-40, 40)
                await tags["press_02_pressure"].write_value(pressure)

                temp = await tags["press_02_hyd_temp"].read_value()
                temp = float(temp) + random.uniform(-0.2, 0.3)
                temp = max(42.0, min(62.0, temp))
                await tags["press_02_hyd_temp"].write_value(temp)

                if tick % 12 == 0:
                    count = await tags["press_02_cycle_count"].read_value()
                    await tags["press_02_cycle_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["press_02_faulted"].read_value()
                await tags["press_02_faulted"].write_value(not faulted)

            # --- Conveyor 01 ---
            running_conv_1 = await tags["conveyor_01_running"].read_value()
            if running_conv_1:
                speed = 1.5 + random.uniform(-0.1, 0.1)
                await tags["conveyor_01_speed"].write_value(speed)

                # Photoeyes toggle randomly
                if random.random() < 0.1:
                    pe = await tags["conveyor_01_entry_pe"].read_value()
                    await tags["conveyor_01_entry_pe"].write_value(not pe)
                    if not pe:  # Rising edge
                        count = await tags["conveyor_01_item_count"].read_value()
                        await tags["conveyor_01_item_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

                if random.random() < 0.1:
                    pe = await tags["conveyor_01_exit_pe"].read_value()
                    await tags["conveyor_01_exit_pe"].write_value(not pe)

            if random.random() < 0.001:
                faulted = await tags["conveyor_01_faulted"].read_value()
                await tags["conveyor_01_faulted"].write_value(not faulted)

            # --- Conveyor 02 ---
            running_conv_2 = await tags["conveyor_02_running"].read_value()
            if running_conv_2:
                speed = 2.0 + random.uniform(-0.15, 0.15)
                await tags["conveyor_02_speed"].write_value(speed)

                if random.random() < 0.12:
                    pe = await tags["conveyor_02_entry_pe"].read_value()
                    await tags["conveyor_02_entry_pe"].write_value(not pe)
                    if not pe:
                        count = await tags["conveyor_02_item_count"].read_value()
                        await tags["conveyor_02_item_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

                if random.random() < 0.12:
                    pe = await tags["conveyor_02_exit_pe"].read_value()
                    await tags["conveyor_02_exit_pe"].write_value(not pe)

            if random.random() < 0.001:
                faulted = await tags["conveyor_02_faulted"].read_value()
                await tags["conveyor_02_faulted"].write_value(not faulted)

            # --- Robot 01 ---
            running_robot = await tags["robot_01_running"].read_value()
            if running_robot:
                # Joint positions oscillate
                await tags["robot_01_j1"].write_value(45 * math.sin(tick * 0.05))
                await tags["robot_01_j2"].write_value(-45 + 20 * math.sin(tick * 0.08))
                await tags["robot_01_j3"].write_value(90 + 15 * math.cos(tick * 0.06))
                await tags["robot_01_j4"].write_value(30 * math.sin(tick * 0.1))
                await tags["robot_01_j5"].write_value(45 + 10 * math.cos(tick * 0.07))
                await tags["robot_01_j6"].write_value(180 * math.sin(tick * 0.03))

                # TCP position
                await tags["robot_01_tcp_x"].write_value(500 + 200 * math.sin(tick * 0.04))
                await tags["robot_01_tcp_y"].write_value(150 * math.cos(tick * 0.04))
                await tags["robot_01_tcp_z"].write_value(800 + 100 * math.sin(tick * 0.06))

                if tick % 15 == 0:
                    count = await tags["robot_01_cycle_count"].read_value()
                    await tags["robot_01_cycle_count"].write_value(ua.Variant(int(count + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["robot_01_faulted"].read_value()
                await tags["robot_01_faulted"].write_value(not faulted)

            # --- Packaging Line 01 ---
            running_pkg = await tags["packaging_01_running"].read_value()
            if running_pkg:
                upm = 120 + random.uniform(-5, 5)
                await tags["packaging_01_upm"].write_value(upm)

                # Every 0.5 seconds on average, produce a unit
                if random.random() < 0.5:
                    total = await tags["packaging_01_total_count"].read_value()
                    await tags["packaging_01_total_count"].write_value(ua.Variant(int(total + 1), ua.VariantType.Int32))

                    # 2% reject rate
                    if random.random() < 0.02:
                        reject = await tags["packaging_01_reject_count"].read_value()
                        await tags["packaging_01_reject_count"].write_value(ua.Variant(int(reject + 1), ua.VariantType.Int32))
                    else:
                        good = await tags["packaging_01_good_count"].read_value()
                        await tags["packaging_01_good_count"].write_value(ua.Variant(int(good + 1), ua.VariantType.Int32))

            if random.random() < 0.001:
                faulted = await tags["packaging_01_faulted"].read_value()
                await tags["packaging_01_faulted"].write_value(not faulted)


if __name__ == "__main__":
    asyncio.run(main())
