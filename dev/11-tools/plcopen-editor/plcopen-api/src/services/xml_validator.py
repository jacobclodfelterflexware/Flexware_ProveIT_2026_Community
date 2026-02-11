"""PLCopen XML validation service."""
import logging
from lxml import etree

from api.schemas import ValidationResult, ValidationError

logger = logging.getLogger(__name__)


class PLCopenValidator:
    """Validator for PLCopen XML documents."""

    # Required elements in a valid PLCopen project
    REQUIRED_ELEMENTS = [
        "fileHeader",
        "contentHeader",
        "types",
    ]

    # Required attributes
    REQUIRED_FILE_HEADER_ATTRS = [
        "companyName",
        "productName",
        "productVersion",
        "creationDateTime",
    ]
    REQUIRED_CONTENT_HEADER_ATTRS = ["name"]

    def validate(self, xml_content: str) -> ValidationResult:
        """
        Validate PLCopen XML content.

        Args:
            xml_content: Raw XML string

        Returns:
            ValidationResult with is_valid flag and any errors
        """
        errors = []
        warnings = []

        # Step 1: Check if it's well-formed XML
        try:
            doc = etree.fromstring(xml_content.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationError(line=e.lineno, column=e.offset, message=str(e.msg))
                ],
            )

        # Step 2: Check root element
        root_tag = etree.QName(doc.tag).localname
        if root_tag != "project":
            errors.append(
                ValidationError(
                    message=f"Root element must be 'project', found '{root_tag}'",
                    element="root",
                )
            )
            return ValidationResult(is_valid=False, errors=errors)

        # Step 3: Check namespace
        ns = doc.nsmap.get(None, "")
        if ns and "plcopen.org" not in ns:
            warnings.append(f"Non-standard namespace: {ns}")

        # Step 4: Check required elements
        for elem_name in self.REQUIRED_ELEMENTS:
            found = self._find_element(doc, elem_name, ns)
            if found is None:
                errors.append(
                    ValidationError(
                        message=f"Missing required element: {elem_name}",
                        element=elem_name,
                    )
                )

        # Step 5: Validate fileHeader attributes
        file_header = self._find_element(doc, "fileHeader", ns)
        if file_header is not None:
            for attr in self.REQUIRED_FILE_HEADER_ATTRS:
                if file_header.get(attr) is None:
                    errors.append(
                        ValidationError(
                            message=f"fileHeader missing required attribute: {attr}",
                            element="fileHeader",
                        )
                    )

        # Step 6: Validate contentHeader
        content_header = self._find_element(doc, "contentHeader", ns)
        if content_header is not None:
            for attr in self.REQUIRED_CONTENT_HEADER_ATTRS:
                if content_header.get(attr) is None:
                    errors.append(
                        ValidationError(
                            message=f"contentHeader missing required attribute: {attr}",
                            element="contentHeader",
                        )
                    )

        # Step 7: Validate POUs structure
        pous = self._find_element(doc, "pous", ns)
        if pous is not None:
            for pou in pous:
                if etree.QName(pou.tag).localname == "pou":
                    pou_errors = self._validate_pou(pou, ns)
                    errors.extend(pou_errors)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _find_element(self, doc, name: str, ns: str):
        """Find element with or without namespace."""
        if ns:
            elem = doc.find(f".//{{{ns}}}{name}")
        else:
            elem = doc.find(f".//{name}")
        if elem is None:
            # Fallback: search by local name using XPath
            results = doc.xpath(f".//*[local-name()='{name}']")
            elem = results[0] if results else None
        return elem

    def _validate_pou(self, pou, ns: str) -> list:
        """Validate a POU element."""
        errors = []

        # Check required attributes
        pou_name = pou.get("name")
        pou_type = pou.get("pouType")

        if not pou_name:
            errors.append(
                ValidationError(message="POU missing 'name' attribute", element="pou")
            )

        if not pou_type:
            errors.append(
                ValidationError(
                    message=f"POU '{pou_name}' missing 'pouType' attribute",
                    element=f"pou[@name='{pou_name}']",
                )
            )
        elif pou_type not in ["program", "function", "functionBlock"]:
            errors.append(
                ValidationError(
                    message=f"POU '{pou_name}' has invalid pouType: {pou_type}",
                    element=f"pou[@name='{pou_name}']",
                )
            )

        # Check for body element
        body = self._find_element(pou, "body", ns)
        if body is None:
            errors.append(
                ValidationError(
                    message=f"POU '{pou_name}' missing 'body' element",
                    element=f"pou[@name='{pou_name}']",
                )
            )

        return errors
