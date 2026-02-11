"""OpenPLC Runtime REST API client."""
import os
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# OpenPLC Runtime configuration
OPENPLC_HOST = os.getenv("OPENPLC_HOST", "YOUR_K8S_SERVICE_HOST")
OPENPLC_PORT = int(os.getenv("OPENPLC_PORT", "YOUR_API_PORT"))
OPENPLC_USER = os.getenv("OPENPLC_USER", "openplc")
OPENPLC_PASS = os.getenv("OPENPLC_PASS", "openplc")


class OpenPLCClient:
    """Client for OpenPLC Runtime REST API."""

    def __init__(
        self,
        host: str = OPENPLC_HOST,
        port: int = OPENPLC_PORT,
        username: str = OPENPLC_USER,
        password: str = OPENPLC_PASS,
    ):
        """Initialize OpenPLC client.

        Args:
            host: OpenPLC Runtime hostname
            port: OpenPLC Runtime port
            username: Login username
            password: Login password
        """
        self.base_url = f"http://{host}:{port}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._logged_in = False

    def login(self) -> bool:
        """Login to OpenPLC Runtime.

        Returns:
            True if login successful
        """
        try:
            # First, get the login page to extract CSRF token
            login_page = self.session.get(f"{self.base_url}/")

            # Extract CSRF token from form
            csrf_token = None
            if "csrf_token" in login_page.text:
                import re
                match = re.search(r"name='csrf_token'\s*/?\s*value='([^']+)'|value='([^']+)'\s*name='csrf_token'", login_page.text)
                if match:
                    csrf_token = match.group(1) or match.group(2)

            login_data = {
                "username": self.username,
                "password": self.password,
            }
            if csrf_token:
                login_data["csrf_token"] = csrf_token

            response = self.session.post(
                f"{self.base_url}/login",
                data=login_data,
                allow_redirects=True,
            )

            # OpenPLC redirects to dashboard on successful login
            # Check if we ended up on dashboard or if "Dashboard" is in response
            if response.status_code == 200 and ("dashboard" in response.url or "Dashboard" in response.text):
                self._logged_in = True
                logger.info("Successfully logged into OpenPLC Runtime")
                return True

            logger.warning(f"Login failed with status {response.status_code}")
            return False

        except requests.RequestException as e:
            logger.error(f"Failed to connect to OpenPLC: {e}")
            return False

    def ensure_logged_in(self) -> bool:
        """Ensure we're logged in, login if necessary."""
        if not self._logged_in:
            return self.login()
        return True

    def upload_program(
        self,
        st_code: str,
        program_name: str = "LLM_Program",
        description: str = "Program uploaded via API",
    ) -> Dict[str, Any]:
        """Upload a Structured Text program to OpenPLC.

        This is a three-step process:
        1. POST to /upload-program with the .st file - returns form with prog_file and epoch_time
        2. POST to /upload-program-action with prog_name, prog_descr, prog_file, epoch_time
        3. Follow redirect to /compile-program to trigger compilation

        Args:
            st_code: IEC 61131-3 Structured Text code
            program_name: Name for the program
            description: Program description

        Returns:
            Dict with success status and message
        """
        if not self.ensure_logged_in():
            return {"success": False, "message": "Failed to login to OpenPLC"}

        try:
            import re
            import time

            # Step 1: Get the programs page to get CSRF token
            programs_page = self.session.get(f"{self.base_url}/programs")
            csrf_token = None
            if "csrf_token" in programs_page.text:
                match = re.search(r"value='([^']+)'\s*name='csrf_token'", programs_page.text)
                if match:
                    csrf_token = match.group(1)

            # Step 2: Upload the file (this takes us to Program Info page)
            files = {
                "file": (f"{program_name}.st", st_code, "text/plain"),
            }
            data = {}
            if csrf_token:
                data["csrf_token"] = csrf_token

            response = self.session.post(
                f"{self.base_url}/upload-program",
                files=files,
                data=data,
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Upload failed with status {response.status_code}",
                }

            # Step 3: Extract prog_file, epoch_time, and CSRF token from the Program Info page
            program_info_csrf = None
            prog_file = None
            epoch_time = None

            # Extract CSRF token
            csrf_match = re.search(r"value='([^']+)'\s*name='csrf_token'", response.text)
            if csrf_match:
                program_info_csrf = csrf_match.group(1)

            # Extract prog_file (the random filename assigned by OpenPLC)
            prog_file_match = re.search(r"name='prog_file'\s*value='([^']+)'|value='([^']+)'\s*name='prog_file'", response.text)
            if prog_file_match:
                prog_file = prog_file_match.group(1) or prog_file_match.group(2)

            # Extract epoch_time
            epoch_match = re.search(r"name='epoch_time'\s*value='([^']+)'|value='([^']+)'\s*name='epoch_time'", response.text)
            if epoch_match:
                epoch_time = epoch_match.group(1) or epoch_match.group(2)

            if not prog_file:
                logger.error(f"Could not extract prog_file from upload response")
                return {
                    "success": False,
                    "message": "Could not extract program file from upload response",
                }

            # Use current epoch time if not found
            if not epoch_time:
                epoch_time = str(int(time.time()))

            # Step 4: Submit to upload-program-action to add to database and trigger compile
            compile_data = {
                "prog_name": program_name,
                "prog_descr": description,
                "prog_file": prog_file,
                "epoch_time": epoch_time,
            }
            if program_info_csrf:
                compile_data["csrf_token"] = program_info_csrf

            logger.info(f"Submitting program action: prog_file={prog_file}, epoch_time={epoch_time}")

            compile_response = self.session.post(
                f"{self.base_url}/upload-program-action",
                data=compile_data,
                allow_redirects=True,  # Follow redirect to /compile-program
            )

            if compile_response.status_code == 200:
                content = compile_response.text.lower()

                # Check if we're on the compiling page or compilation finished
                if "compiling" in content:
                    # Wait for compilation to complete
                    logger.info("Compilation in progress, waiting...")
                    for _ in range(30):  # Wait up to 30 seconds
                        time.sleep(1)
                        status_resp = self.session.get(f"{self.base_url}/compilation-logs")
                        if "DONE" in status_resp.text or "error" in status_resp.text.lower():
                            break

                    # Check final status
                    final_status = self.session.get(f"{self.base_url}/compilation-logs")
                    if "error" in final_status.text.lower():
                        return {
                            "success": False,
                            "message": "Compilation failed",
                            "details": final_status.text[:500],
                        }

                return {
                    "success": True,
                    "message": "Program uploaded and compiled successfully",
                    "prog_file": prog_file,
                }

            return {
                "success": False,
                "message": f"Compilation failed with status {compile_response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Failed to upload program: {e}")
            return {"success": False, "message": str(e)}

    def start_plc(self) -> Dict[str, Any]:
        """Start the PLC runtime.

        Returns:
            Dict with success status
        """
        if not self.ensure_logged_in():
            return {"success": False, "message": "Failed to login to OpenPLC"}

        try:
            response = self.session.get(f"{self.base_url}/start_plc")

            if response.status_code == 200:
                return {"success": True, "message": "PLC started"}

            return {
                "success": False,
                "message": f"Start failed with status {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Failed to start PLC: {e}")
            return {"success": False, "message": str(e)}

    def stop_plc(self) -> Dict[str, Any]:
        """Stop the PLC runtime.

        Returns:
            Dict with success status
        """
        if not self.ensure_logged_in():
            return {"success": False, "message": "Failed to login to OpenPLC"}

        try:
            response = self.session.get(f"{self.base_url}/stop_plc")

            if response.status_code == 200:
                return {"success": True, "message": "PLC stopped"}

            return {
                "success": False,
                "message": f"Stop failed with status {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Failed to stop PLC: {e}")
            return {"success": False, "message": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get PLC runtime status.

        Returns:
            Dict with runtime status info
        """
        if not self.ensure_logged_in():
            return {"success": False, "status": "unknown", "message": "Failed to login"}

        try:
            response = self.session.get(f"{self.base_url}/dashboard")

            if response.status_code == 200:
                content = response.text.lower()
                if "running" in content:
                    status = "running"
                elif "stopped" in content:
                    status = "stopped"
                elif "compiling" in content:
                    status = "compiling"
                else:
                    status = "unknown"

                return {
                    "success": True,
                    "status": status,
                }

            return {
                "success": False,
                "status": "unknown",
                "message": f"Status check failed: {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Failed to get status: {e}")
            return {"success": False, "status": "error", "message": str(e)}

    def get_programs(self) -> Dict[str, Any]:
        """Get list of uploaded programs.

        Returns:
            Dict with programs list
        """
        if not self.ensure_logged_in():
            return {"success": False, "programs": [], "message": "Failed to login"}

        try:
            response = self.session.get(f"{self.base_url}/programs")

            if response.status_code == 200:
                # Parse program list from HTML response
                # This is a simple implementation - OpenPLC doesn't have a JSON API
                return {
                    "success": True,
                    "programs": [],  # Would need HTML parsing
                    "message": "Program list retrieved",
                }

            return {
                "success": False,
                "programs": [],
                "message": f"Failed to get programs: {response.status_code}",
            }

        except requests.RequestException as e:
            logger.error(f"Failed to get programs: {e}")
            return {"success": False, "programs": [], "message": str(e)}


# Singleton instance
_client: Optional[OpenPLCClient] = None


def get_openplc_client() -> OpenPLCClient:
    """Get the OpenPLC client singleton."""
    global _client
    if _client is None:
        _client = OpenPLCClient()
    return _client
