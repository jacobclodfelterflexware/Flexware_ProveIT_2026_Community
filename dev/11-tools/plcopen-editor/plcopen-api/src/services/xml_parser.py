"""PLCopen XML parsing and generation service."""
import logging
from datetime import datetime
from typing import Optional
from lxml import etree

from api.schemas import (
    ProjectSummary,
    POUSummary,
    VariableSummary,
    ConfigurationSummary,
)

logger = logging.getLogger(__name__)


class PLCopenParser:
    """Parser for PLCopen XML documents."""

    PLCOPEN_NS = "http://www.plcopen.org/xml/tc6_0201"
    XHTML_NS = "http://www.w3.org/1999/xhtml"
    XSD_NS = "http://www.w3.org/2001/XMLSchema"

    LANGUAGE_TAGS = ["FBD", "LD", "SFC", "ST", "IL"]

    def parse(self, xml_content: str) -> ProjectSummary:
        """
        Parse PLCopen XML and extract project summary.

        Args:
            xml_content: Raw XML string

        Returns:
            ProjectSummary with extracted information
        """
        doc = etree.fromstring(xml_content.encode("utf-8"))
        ns = doc.nsmap.get(None, self.PLCOPEN_NS)

        # Extract file header
        file_header = self._find(doc, "fileHeader", ns)
        content_header = self._find(doc, "contentHeader", ns)

        project = ProjectSummary(
            name=(
                content_header.get("name", "Unnamed")
                if content_header is not None
                else "Unnamed"
            ),
            company_name=(
                file_header.get("companyName") if file_header is not None else None
            ),
            product_name=(
                file_header.get("productName") if file_header is not None else None
            ),
            product_version=(
                file_header.get("productVersion") if file_header is not None else None
            ),
            creation_date=(
                file_header.get("creationDateTime") if file_header is not None else None
            ),
            modification_date=(
                content_header.get("modificationDateTime")
                if content_header is not None
                else None
            ),
        )

        # Extract POUs
        pous = self._find(doc, "pous", ns)
        if pous is not None:
            for pou_elem in pous:
                if self._local_name(pou_elem) == "pou":
                    pou = self._parse_pou(pou_elem, ns)
                    if pou:
                        project.pous.append(pou)

        # Extract configurations
        configurations = self._find(doc, "configurations", ns)
        if configurations is not None:
            for config_elem in configurations:
                if self._local_name(config_elem) == "configuration":
                    config = self._parse_configuration(config_elem, ns)
                    if config:
                        project.configurations.append(config)

        # Extract data types
        data_types = self._find(doc, "dataTypes", ns)
        if data_types is not None:
            for dt in data_types:
                name = dt.get("name")
                if name:
                    project.data_types.append(name)

        return project

    def _find(self, elem, name: str, ns: str):
        """Find element with namespace fallback."""
        if ns:
            result = elem.find(f".//{{{ns}}}{name}")
        else:
            result = elem.find(f".//{name}")
        if result is None:
            # Fallback: search by local name using XPath
            results = elem.xpath(f".//*[local-name()='{name}']")
            result = results[0] if results else None
        return result

    def _local_name(self, elem) -> str:
        """Get local name without namespace."""
        return etree.QName(elem.tag).localname

    def _parse_pou(self, pou_elem, ns: str) -> Optional[POUSummary]:
        """Parse a POU element."""
        name = pou_elem.get("name")
        pou_type = pou_elem.get("pouType")

        if not name:
            return None

        # Determine language from body
        body = self._find(pou_elem, "body", ns)
        language = "Unknown"
        if body is not None:
            for lang in self.LANGUAGE_TAGS:
                if self._find(body, lang, ns) is not None:
                    language = lang
                    break

        pou = POUSummary(
            name=name,
            pou_type=pou_type or "unknown",
            language=language,
        )

        # Parse variables from interface
        interface = self._find(pou_elem, "interface", ns)
        if interface is not None:
            pou.variables.extend(
                self._parse_variables(interface, ns, "inputVars", "input")
            )
            pou.variables.extend(
                self._parse_variables(interface, ns, "outputVars", "output")
            )
            pou.variables.extend(
                self._parse_variables(interface, ns, "localVars", "local")
            )
            pou.variables.extend(
                self._parse_variables(interface, ns, "inOutVars", "inOut")
            )

        return pou

    def _parse_variables(
        self, interface, ns: str, container: str, scope: str
    ) -> list:
        """Parse variables from a variable container."""
        variables = []
        container_elem = self._find(interface, container, ns)
        if container_elem is not None:
            for var_elem in container_elem:
                if self._local_name(var_elem) == "variable":
                    var_name = var_elem.get("name")
                    if var_name:
                        # Get type
                        type_elem = self._find(var_elem, "type", ns)
                        var_type = "ANY"
                        if type_elem is not None and len(type_elem) > 0:
                            var_type = self._local_name(type_elem[0])

                        variables.append(
                            VariableSummary(name=var_name, type=var_type, scope=scope)
                        )
        return variables

    def _parse_configuration(
        self, config_elem, ns: str
    ) -> Optional[ConfigurationSummary]:
        """Parse a configuration element."""
        name = config_elem.get("name")
        if not name:
            return None

        config = ConfigurationSummary(name=name)

        for resource in config_elem:
            if self._local_name(resource) == "resource":
                res_name = resource.get("name")
                if res_name:
                    config.resources.append(res_name)

        return config

    def create_empty_project(self, project_name: str) -> str:
        """
        Create an empty PLCopen project XML.

        Args:
            project_name: Name for the project

        Returns:
            PLCopen XML string
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        return f"""<?xml version='1.0' encoding='utf-8'?>
<project xmlns:xhtml="{self.XHTML_NS}" xmlns:xsd="{self.XSD_NS}" xmlns="{self.PLCOPEN_NS}">
  <fileHeader companyName="Unknown" productName="PLCopen API" productVersion="1" creationDateTime="{now}"/>
  <contentHeader name="{project_name}" modificationDateTime="{now}">
    <coordinateInfo>
      <fbd>
        <scaling x="10" y="10"/>
      </fbd>
      <ld>
        <scaling x="10" y="10"/>
      </ld>
      <sfc>
        <scaling x="10" y="10"/>
      </sfc>
    </coordinateInfo>
  </contentHeader>
  <types>
    <dataTypes/>
    <pous/>
  </types>
  <instances>
    <configurations>
      <configuration name="Config0">
        <resource name="Res0"/>
      </configuration>
    </configurations>
  </instances>
</project>"""

    def normalize(self, xml_content: str) -> str:
        """
        Normalize PLCopen XML (parse and re-serialize).

        Args:
            xml_content: Raw XML string

        Returns:
            Normalized XML string with consistent formatting
        """
        doc = etree.fromstring(xml_content.encode("utf-8"))
        return etree.tostring(
            doc, pretty_print=True, xml_declaration=True, encoding="utf-8"
        ).decode("utf-8")
