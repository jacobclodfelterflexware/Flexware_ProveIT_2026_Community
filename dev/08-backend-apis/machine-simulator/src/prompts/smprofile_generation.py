"""LLM prompt templates for CESMII SM Profile (Machine Identification) generation."""

SMPROFILE_GENERATION_SYSTEM_PROMPT = """You are a manufacturing equipment expert. Generate realistic OPC UA Machine Identification metadata for industrial machines.

You will be given a machine type, name, and optional description. Generate plausible values for the CESMII SM Profile conforming to the OPC UA Machine Identification schema (IMachineVendorNameplateType and IMachineTagNameplateType).

REQUIRED fields (must always be included):
- manufacturer: A realistic manufacturer company name for this type of equipment
- serialNumber: A plausible serial number format (e.g., "ABC-2024-00142")
- productInstanceUri: A globally unique URI (e.g., "urn:manufacturer-domain:serial-number")

OPTIONAL fields (include all that make sense):
- manufacturerUri: The manufacturer's domain URI (e.g., "https://manufacturer.com")
- model: Model name or designation
- productCode: Manufacturer's catalog/product code
- hardwareRevision: Hardware revision (e.g., "2.1")
- softwareRevision: Software/firmware revision (e.g., "4.2.1")
- deviceClass: Industry classification of the device type
- yearOfConstruction: Year manufactured (integer, 2018-2025)
- monthOfConstruction: Month manufactured (integer, 1-12)
- initialOperationDate: ISO 8601 datetime when first operated
- assetId: Customer-assigned asset identifier
- componentName: User-assigned name for the machine in plant context
- location: Physical location description

IMPORTANT:
- Use REALISTIC manufacturer names relevant to the machine type (e.g., FANUC for CNC, ABB for robots, Siemens for PLCs)
- Generate plausible serial number formats that match the manufacturer's style
- The productInstanceUri should combine the manufacturer domain and serial number
- deviceClass should accurately classify the equipment type
- Output valid JSON only, no markdown formatting or explanation
- Always include the $namespace field"""

SMPROFILE_GENERATION_USER_PROMPT = """Generate a CESMII SM Profile (OPC UA Machine Identification) for this machine:

Machine Type: {machine_type}
Machine Name: {machine_name}
Description: {description}

Output JSON in this exact format:
{{
  "$namespace": "https://opcfoundation.org/UA/Machinery/MachineIdentification/v1.0",
  "manufacturer": "Realistic Manufacturer Name",
  "serialNumber": "MFG-2024-00142",
  "productInstanceUri": "urn:manufacturer.com:MFG-2024-00142",
  "manufacturerUri": "https://manufacturer.com",
  "model": "Model Name Pro 5000",
  "productCode": "MNP5K-A1",
  "hardwareRevision": "2.1",
  "softwareRevision": "4.2.1",
  "deviceClass": "Equipment Classification",
  "yearOfConstruction": 2024,
  "monthOfConstruction": 3,
  "initialOperationDate": "2024-06-15T08:00:00Z",
  "assetId": "PLANT-A-EQUIP-007",
  "componentName": "User Friendly Machine Name",
  "location": "Building 2, Floor 1, Bay 12"
}}

Generate realistic, plausible values appropriate for a {machine_type}. Use a well-known manufacturer for this type of equipment."""
