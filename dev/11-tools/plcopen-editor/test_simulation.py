#!/usr/bin/env python3
"""
End-to-end test script for PLCopen XML simulation.

This script demonstrates:
1. Creating a PLCopen XML project
2. Saving it via the API
3. Loading it into OpenPLC Runtime
4. Starting the simulation
5. Writing I/O values
6. Reading and verifying outputs

Usage:
    python3 test_simulation.py [--api-host API_HOST]
"""
import argparse
import json
import time
import requests

# Default API endpoint
DEFAULT_API = "http://YOUR_REGISTRY_IP"

# Test PLCopen XML program using memory words
# This program implements: MW2 = 1 if (MW0 > 0 AND MW1 == 0) else 0
# Memory words (%MW) can be read/written via Modbus holding registers at offset 1024
TEST_XML = '<?xml version="1.0" encoding="utf-8"?><project xmlns="http://www.plcopen.org/xml/tc6_0201"><fileHeader companyName="Test" productName="SimulationTest" productVersion="1.0" creationDateTime="2026-01-13T12:00:00"/><contentHeader name="Simulation Test Program"/><types><dataTypes/><pous><pou name="TestProgram" pouType="program"><interface><localVars><variable name="Input1" address="%MW0"><type><INT/></type></variable><variable name="Input2" address="%MW1"><type><INT/></type></variable><variable name="Output1" address="%MW2"><type><INT/></type></variable></localVars></interface><body><ST>IF Input1 &gt; 0 AND Input2 = 0 THEN Output1 := 1; ELSE Output1 := 0; END_IF;</ST></body></pou></pous></types><instances><configurations><configuration name="Config0"><resource name="Res0"><task name="MainTask" priority="0" interval="T#20ms"><pouInstance name="Test" typeName="TestProgram"/></task></resource></configuration></configurations></instances></project>'


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_step(step_num, text):
    print(f"\n[Step {step_num}] {text}")


def print_result(success, message):
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"  {status}: {message}")


def test_simulation(api_host):
    """Run the complete simulation test."""
    base_url = f"{api_host}/api/plcopen"
    
    print_header("PLCopen XML Simulation Test")
    print(f"API Host: {api_host}")
    
    # Step 1: Test API connectivity
    print_step(1, "Testing API connectivity")
    try:
        r = requests.get(f"{api_host}/health", timeout=5)
        print_result(r.status_code == 200, f"Health check: {r.json()}")
    except Exception as e:
        print_result(False, f"Cannot reach API: {e}")
        return False
    
    # Step 2: Stop any existing simulation
    print_step(2, "Stopping any existing simulation")
    r = requests.post(f"{base_url}/simulate/stop")
    print_result(True, f"Stop result: {r.json()['status'] if 'status' in r.json() else r.json()}")
    
    # Step 3: Save the test project
    print_step(3, "Saving test project")
    r = requests.post(
        f"{base_url}/projects",
        json={"name": "SimulationTest", "xml_content": TEST_XML}
    )
    result = r.json()
    if not result.get("success"):
        print_result(False, f"Failed to save project: {result}")
        return False
    
    project_id = result["project"]["id"]
    print_result(True, f"Project saved with ID: {project_id}")
    
    # Step 4: Convert XML to Structured Text (preview)
    print_step(4, "Converting XML to Structured Text")
    r = requests.post(
        f"{base_url}/simulate/convert",
        json={"xml_content": TEST_XML}
    )
    result = r.json()
    if result.get("success"):
        print_result(True, "Conversion successful")
        print("\n  Generated Structured Text:")
        for line in result["st_code"].split("\n"):
            print(f"    {line}")
    else:
        print_result(False, f"Conversion failed: {result.get('message')}")
        return False
    
    # Step 5: Load project into simulator
    print_step(5, "Loading project into OpenPLC Runtime")
    r = requests.post(
        f"{base_url}/simulate/load",
        json={"project_id": project_id}
    )
    result = r.json()
    print_result(result.get("success", False), result.get("message", "Unknown error"))
    if not result.get("success"):
        return False
    
    # Step 6: Start simulation
    print_step(6, "Starting PLC simulation")
    r = requests.post(f"{base_url}/simulate/start")
    result = r.json()
    print_result(result.get("success", False), f"Status: {result.get('status', 'unknown')}")
    if not result.get("success"):
        return False
    
    # Wait for PLC to stabilize
    time.sleep(1)
    
    # Step 7: Verify initial state using memory words
    print_step(7, "Verifying initial I/O state (memory words)")
    r = requests.get(f"{base_url}/simulate/io", params={"memory_words": 3})
    result = r.json()
    mem_words = result.get("memory_words", [])
    print(f"  Memory words [MW0,MW1,MW2]: {mem_words[:3] if len(mem_words) >= 3 else mem_words}")

    initial_ok = len(mem_words) >= 3 and all(w == 0 for w in mem_words[:3])
    print_result(initial_ok, "All memory words initially 0")

    # Step 8: Test case 1 - Set Input1=1, Input2=0
    print_step(8, "Test Case 1: Input1=1, Input2=0")
    print("  Expected: Output1 = 1 (because Input1>0 AND Input2=0)")

    # Reset memory words first (addresses 1024+0, 1024+1 for MW0, MW1)
    requests.post(f"{base_url}/simulate/io/register/1024", params={"value": 0})
    requests.post(f"{base_url}/simulate/io/register/1025", params={"value": 0})
    time.sleep(0.3)

    # Set Input1 (MW0) = 1
    requests.post(f"{base_url}/simulate/io/register/1024", params={"value": 1})
    time.sleep(1.0)  # Wait for multiple PLC scan cycles

    # Read memory words
    r = requests.get(f"{base_url}/simulate/io", params={"memory_words": 3})
    mem_words = r.json().get("memory_words", [])
    print(f"  Memory words [MW0,MW1,MW2]: {mem_words[:3] if len(mem_words) >= 3 else mem_words}")

    expected = 1  # Output should be 1
    actual = mem_words[2] if len(mem_words) >= 3 else None
    print_result(actual == expected, f"Output1 (MW2) = {actual} (expected {expected})")

    # Step 9: Test case 2 - Set Input1=1, Input2=1
    print_step(9, "Test Case 2: Input1=1, Input2=1")
    print("  Expected: Output1 = 0 (because Input2 != 0)")

    # Set Input2 (MW1) = 1
    requests.post(f"{base_url}/simulate/io/register/1025", params={"value": 1})
    time.sleep(0.5)

    r = requests.get(f"{base_url}/simulate/io", params={"memory_words": 3})
    mem_words = r.json().get("memory_words", [])
    print(f"  Memory words [MW0,MW1,MW2]: {mem_words[:3] if len(mem_words) >= 3 else mem_words}")

    expected = 0  # Output should be 0
    actual = mem_words[2] if len(mem_words) >= 3 else None
    print_result(actual == expected, f"Output1 (MW2) = {actual} (expected {expected})")

    # Step 10: Test case 3 - Set Input1=0, Input2=0
    print_step(10, "Test Case 3: Input1=0, Input2=0")
    print("  Expected: Output1 = 0 (because Input1 = 0)")

    requests.post(f"{base_url}/simulate/io/register/1024", params={"value": 0})
    requests.post(f"{base_url}/simulate/io/register/1025", params={"value": 0})
    time.sleep(0.5)

    r = requests.get(f"{base_url}/simulate/io", params={"memory_words": 3})
    mem_words = r.json().get("memory_words", [])
    print(f"  Memory words [MW0,MW1,MW2]: {mem_words[:3] if len(mem_words) >= 3 else mem_words}")

    expected = 0  # Output should be 0
    actual = mem_words[2] if len(mem_words) >= 3 else None
    print_result(actual == expected, f"Output1 (MW2) = {actual} (expected {expected})")
    
    # Step 11: Stop simulation
    print_step(11, "Stopping simulation")
    r = requests.post(f"{base_url}/simulate/stop")
    result = r.json()
    print_result(result.get("success", False), f"Status: {result.get('status', 'unknown')}")
    
    # Summary
    print_header("Test Complete")
    print("\nThe simulation system is working correctly if all tests passed.")
    print("\nAPI Endpoints Available:")
    print(f"  POST {base_url}/simulate/convert  - Convert XML to ST")
    print(f"  POST {base_url}/simulate/load     - Load project")
    print(f"  POST {base_url}/simulate/start    - Start PLC")
    print(f"  POST {base_url}/simulate/stop     - Stop PLC")
    print(f"  GET  {base_url}/simulate/status   - Get status")
    print(f"  GET  {base_url}/simulate/io       - Read I/O")
    print(f"  POST {base_url}/simulate/io/coil/N?value=true|false - Write coil")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test PLCopen XML simulation")
    parser.add_argument("--api-host", default=DEFAULT_API, help="API host URL")
    args = parser.parse_args()
    
    success = test_simulation(args.api_host)
    exit(0 if success else 1)
