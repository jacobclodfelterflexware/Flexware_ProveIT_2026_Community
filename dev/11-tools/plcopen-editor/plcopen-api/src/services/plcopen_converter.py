"""PLCopen XML to IEC 61131-3 Structured Text converter."""
import logging
from typing import Dict, List, Optional, Tuple
from lxml import etree

logger = logging.getLogger(__name__)

# PLCopen namespace
NS = {"plc": "http://www.plcopen.org/xml/tc6_0201"}


class PLCopenToSTConverter:
    """Convert PLCopen XML to IEC 61131-3 Structured Text."""

    def __init__(self, xml_content: str):
        """Initialize converter with PLCopen XML content."""
        self.xml_content = xml_content
        self.root = None
        self.variables: Dict[str, Dict] = {}
        self.connections: Dict[int, List[int]] = {}
        self.elements: Dict[int, Dict] = {}

    def convert(self) -> str:
        """Convert PLCopen XML to Structured Text.

        Returns:
            IEC 61131-3 Structured Text code
        """
        try:
            self.root = etree.fromstring(self.xml_content.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Invalid XML: {e}")

        st_code = []

        # Process all POUs
        pous = self._find_pous()
        for pou in pous:
            pou_st = self._convert_pou(pou)
            st_code.append(pou_st)

        # Add configuration
        config_st = self._generate_configuration(pous)
        st_code.append(config_st)

        return "\n\n".join(st_code)

    def _find_pous(self) -> List[etree._Element]:
        """Find all POU elements in the XML."""
        # Try with namespace
        pous = self.root.xpath("//plc:pou", namespaces=NS)
        if not pous:
            # Try without namespace
            pous = self.root.xpath("//*[local-name()='pou']")
        return pous

    def _convert_pou(self, pou: etree._Element) -> str:
        """Convert a single POU to Structured Text."""
        pou_name = pou.get("name", "UnnamedPOU")
        pou_type = pou.get("pouType", "program").upper()

        # Extract variables
        variables = self._extract_variables(pou)

        # Extract body logic
        body_logic = self._extract_body_logic(pou)

        # Build ST code
        lines = []
        lines.append(f"{pou_type} {pou_name}")

        # Variable declarations
        if variables:
            lines.append("VAR")
            for var_name, var_info in variables.items():
                var_type = var_info.get("type", "BOOL")
                address = var_info.get("address", "")
                initial = var_info.get("initial", "")

                decl = f"    {var_name}"
                if address:
                    decl += f" AT {address}"
                decl += f" : {var_type}"
                if initial:
                    decl += f" := {initial}"
                decl += ";"
                lines.append(decl)
            lines.append("END_VAR")

        lines.append("")

        # Body logic
        if body_logic:
            lines.extend(body_logic)
        else:
            lines.append("    (* No logic defined *)")

        lines.append("")
        lines.append(f"END_{pou_type}")

        return "\n".join(lines)

    def _extract_variables(self, pou: etree._Element) -> Dict[str, Dict]:
        """Extract variables from POU interface."""
        variables = {}

        # Find interface/localVars
        interface = pou.find("plc:interface", namespaces=NS)
        if interface is None:
            # Use xpath for complex predicate
            results = pou.xpath(".//*[local-name()='interface']")
            interface = results[0] if results else None

        if interface is None:
            return variables

        # Process all variable sections
        for var_section in interface:
            section_name = etree.QName(var_section).localname

            for var in var_section:
                if etree.QName(var).localname == "variable":
                    var_name = var.get("name", "")
                    if not var_name:
                        continue

                    var_info = {"type": "BOOL"}  # Default type

                    # Get type - use xpath for complex predicate
                    type_results = var.xpath(".//*[local-name()='type']")
                    if type_results and len(type_results[0]) > 0:
                        type_name = etree.QName(type_results[0][0]).localname
                        var_info["type"] = type_name.upper()

                    # Get address if present
                    address = var.get("address", "")
                    if address:
                        var_info["address"] = address

                    # Get initial value - use xpath for complex predicate
                    initial_results = var.xpath(".//*[local-name()='initialValue']")
                    if initial_results:
                        simple_val_results = initial_results[0].xpath(".//*[local-name()='simpleValue']")
                        if simple_val_results:
                            var_info["initial"] = simple_val_results[0].get("value", "")

                    variables[var_name] = var_info

        return variables

    def _extract_body_logic(self, pou: etree._Element) -> List[str]:
        """Extract and convert body logic to ST statements."""
        lines = []

        body = pou.find("plc:body", namespaces=NS)
        if body is None:
            # Use xpath for complex predicate
            body_results = pou.xpath(".//*[local-name()='body']")
            body = body_results[0] if body_results else None

        if body is None or len(body) == 0:
            return lines

        # Get the body type (SFC, FBD, LD, ST)
        body_content = body[0]
        body_type = etree.QName(body_content).localname.upper()

        if body_type == "ST":
            # Already Structured Text - extract directly
            st_text = body_content.text or ""
            lines.extend(["    " + line for line in st_text.strip().split("\n")])

        elif body_type in ("SFC", "FBD"):
            # Convert graphical elements to ST
            lines.extend(self._convert_graphical_body(body_content))

        elif body_type == "LD":
            # Convert ladder logic to ST
            lines.extend(self._convert_ladder_body(body_content))

        return lines

    def _convert_graphical_body(self, body: etree._Element) -> List[str]:
        """Convert SFC/FBD body to ST statements."""
        lines = []

        # Build element map
        elements = {}
        connections = {}  # target_id -> [source_ids]

        for elem in body:
            local_id = elem.get("localId")
            if local_id:
                local_id = int(local_id)
                elem_type = etree.QName(elem).localname

                expression = ""
                expr_results = elem.xpath(".//*[local-name()='expression']")
                if expr_results and expr_results[0].text:
                    expression = expr_results[0].text.strip()

                elements[local_id] = {
                    "type": elem_type,
                    "expression": expression,
                    "negated": elem.get("negated", "false") == "true",
                    "element": elem,
                }

                # Extract connections - use xpath for complex predicates
                for conn_in in elem.xpath(".//*[local-name()='connectionPointIn']"):
                    for conn in conn_in.xpath(".//*[local-name()='connection']"):
                        ref_id = conn.get("refLocalId")
                        if ref_id:
                            ref_id = int(ref_id)
                            if local_id not in connections:
                                connections[local_id] = []
                            connections[local_id].append(ref_id)

        # Generate assignments based on connections
        for target_id, source_ids in connections.items():
            target = elements.get(target_id, {})
            target_expr = target.get("expression", "")
            target_type = target.get("type", "")

            if not target_expr:
                continue

            # Build source expression
            source_exprs = []
            for source_id in source_ids:
                source = elements.get(source_id, {})
                source_expr = source.get("expression", "")
                if source_expr:
                    if source.get("negated"):
                        source_expr = f"NOT {source_expr}"
                    source_exprs.append(source_expr)

            if source_exprs and target_type in ("outVariable", "inOutVariable"):
                if len(source_exprs) == 1:
                    assignment = source_exprs[0]
                else:
                    # Multiple inputs - AND them together
                    assignment = " AND ".join(source_exprs)

                if target.get("negated"):
                    assignment = f"NOT ({assignment})"

                lines.append(f"    {target_expr} := {assignment};")

        return lines if lines else ["    (* Graphical logic - manual conversion may be needed *)"]

    def _convert_ladder_body(self, body: etree._Element) -> List[str]:
        """Convert ladder diagram body to ST statements."""
        lines = []

        # Extract contacts, coils, and connections
        contacts = {}
        coils = {}

        for elem in body:
            local_id = elem.get("localId")
            if not local_id:
                continue
            local_id = int(local_id)
            elem_type = etree.QName(elem).localname

            var_results = elem.xpath(".//*[local-name()='variable']")
            var_name = var_results[0].text.strip() if var_results and var_results[0].text else ""
            negated = elem.get("negated", "false") == "true"

            if elem_type == "contact":
                contacts[local_id] = {
                    "variable": var_name,
                    "negated": negated,
                }
            elif elem_type == "coil":
                coils[local_id] = {
                    "variable": var_name,
                    "negated": negated,
                }

                # Get inputs to this coil - use xpath for complex predicates
                inputs = []
                for conn_in in elem.xpath(".//*[local-name()='connectionPointIn']"):
                    for conn in conn_in.xpath(".//*[local-name()='connection']"):
                        ref_id = conn.get("refLocalId")
                        if ref_id:
                            inputs.append(int(ref_id))

                # Build condition from inputs
                conditions = []
                for input_id in inputs:
                    if input_id in contacts:
                        contact = contacts[input_id]
                        cond = contact["variable"]
                        if contact["negated"]:
                            cond = f"NOT {cond}"
                        conditions.append(cond)

                if conditions:
                    condition = " AND ".join(conditions)
                    if negated:
                        lines.append(f"    {var_name} := NOT ({condition});")
                    else:
                        lines.append(f"    {var_name} := {condition};")

        return lines if lines else ["    (* Ladder logic - manual conversion may be needed *)"]

    def _generate_configuration(self, pous: List[etree._Element]) -> str:
        """Generate CONFIGURATION block for the ST program."""
        lines = []
        lines.append("CONFIGURATION Config0")
        lines.append("  RESOURCE Res0 ON PLC")
        lines.append("    TASK MainTask(INTERVAL := T#20ms, PRIORITY := 0);")

        for i, pou in enumerate(pous):
            pou_name = pou.get("name", f"POU{i}")
            pou_type = pou.get("pouType", "program")
            if pou_type.lower() == "program":
                lines.append(f"    PROGRAM instance{i} WITH MainTask : {pou_name};")

        lines.append("  END_RESOURCE")
        lines.append("END_CONFIGURATION")

        return "\n".join(lines)


def convert_plcopen_to_st(xml_content: str) -> str:
    """Convert PLCopen XML to IEC 61131-3 Structured Text.

    Args:
        xml_content: PLCopen XML content as string

    Returns:
        IEC 61131-3 Structured Text code
    """
    converter = PLCopenToSTConverter(xml_content)
    return converter.convert()
