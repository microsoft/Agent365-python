# Copyright (c) Microsoft. All rights reserved.

"""
MCP Tool Server Configuration Service.

This module provides the implementation of the MCP (Model Context Protocol)
tool server configuration service that communicates with the tooling gateway to
discover and configure MCP tool servers.

The service supports both development and production scenarios:
- Development: Reads configuration from ToolingManifest.json
- Production: Retrieves configuration from tooling gateway endpoint
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports
import aiohttp

# Local imports
from ..models import MCPServerConfig
from ..utils import Constants
from ..utils.utility import (
    get_tooling_gateway_for_digital_worker,
    build_mcp_server_url,
    get_use_environment_id,
)


# ==============================================================================
# MAIN SERVICE CLASS
# ==============================================================================


class McpToolServerConfigurationService:
    """
    Provides services for MCP tool server configuration management.

    This service handles discovery and configuration of MCP (Model Context Protocol)
    tool servers from multiple sources:
    - Development: Local ToolingManifest.json files
    - Production: Remote tooling gateway endpoints
    """

    # --------------------------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------------------------

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MCP Tool Server Configuration Service.

        Args:
            logger: Logger instance for logging operations. If None, creates a new logger.
        """
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    async def list_tool_servers(
        self, agentic_app_id: str, environment_id: str, auth_token: str
    ) -> List[MCPServerConfig]:
        """
        Gets the list of MCP Servers that are configured for the agent.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            environment_id: Environment ID for the environment.
            auth_token: Authentication token to access the MCP servers.

        Returns:
            List[MCPServerConfig]: Returns the list of MCP Servers that are configured.

        Raises:
            ValueError: If required parameters are invalid or empty.
            Exception: If there's an error communicating with the tooling gateway.
        """
        # Validate input parameters
        self._validate_input_parameters(agentic_app_id, environment_id, auth_token)

        if get_use_environment_id():
            self._logger.info(
                f"Listing MCP tool servers for agent {agentic_app_id} in environment {environment_id}"
            )
        else:
            self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

        # Determine configuration source based on environment
        if self._is_development_scenario():
            return self._load_servers_from_manifest(environment_id)
        else:
            return await self._load_servers_from_gateway(agentic_app_id, environment_id, auth_token)

    # --------------------------------------------------------------------------
    # ENVIRONMENT DETECTION
    # --------------------------------------------------------------------------

    def _is_development_scenario(self) -> bool:
        """
        Determines if this is a development scenario.

        Returns:
            bool: True if running in development mode, False otherwise.
        """
        environment = os.getenv("ENVIRONMENT", "Development")

        is_dev = environment.lower() == "development"
        self._logger.debug(f"Environment: {environment}, Development scenario: {is_dev}")
        return is_dev

    # --------------------------------------------------------------------------
    # DEVELOPMENT: MANIFEST-BASED CONFIGURATION
    # --------------------------------------------------------------------------

    def _load_servers_from_manifest(self, environment_id: str) -> List[MCPServerConfig]:
        """
        Reads MCP server configurations from ToolingManifest.json in the application's content root.

        The manifest file should be located at: [ProjectRoot]/ToolingManifest.json

        Example ToolingManifest.json structure:
        {
          "mcpServers": [
            {
              "mcpServerName": "mailMCPServer",
              "mcpServerUniqueName": "mcp_MailTools"
            },
            {
              "mcpServerName": "sharePointMCPServer",
              "mcpServerUniqueName": "mcp_SharePointTools"
            }
          ]
        }

        Args:
            environment_id: Environment ID to construct full URLs.

        Returns:
            List[MCPServerConfig]: List of MCP server configurations from manifest.

        Raises:
            Exception: If manifest file cannot be read or parsed.
        """
        mcp_servers: List[MCPServerConfig] = []

        try:
            manifest_path = self._find_manifest_file()

            if manifest_path and manifest_path.exists():
                self._logger.info(f"Loading MCP servers from: {manifest_path}")
                mcp_servers = self._parse_manifest_file(manifest_path, environment_id)
            else:
                self._log_manifest_search_failure()

        except Exception as e:
            raise Exception(
                f"Failed to read MCP servers from ToolingManifest.json: {str(e)}"
            ) from e

        return mcp_servers

    def _find_manifest_file(self) -> Optional[Path]:
        """
        Searches for ToolingManifest.json in various common locations.

        Returns:
            Path to manifest file if found, None otherwise.
        """
        search_locations = self._get_manifest_search_locations()

        for potential_path in search_locations:
            self._logger.debug(f"Checking for manifest at: {potential_path}")
            if potential_path.exists():
                self._logger.info(f"Found manifest at: {potential_path}")
                return potential_path
            else:
                self._logger.debug(f"Manifest not found at: {potential_path}")

        return None

    def _get_manifest_search_locations(self) -> List[Path]:
        """
        Gets list of potential locations for ToolingManifest.json.

        Returns:
            List of Path objects to search for the manifest file.
        """
        current_dir = Path.cwd()
        search_locations = []

        # Current working directory
        search_locations.append(current_dir / "ToolingManifest.json")

        # Parent directory
        search_locations.append(current_dir.parent / "ToolingManifest.json")

        # Script location and project root
        if __file__:
            if hasattr(sys, "_MEIPASS"):
                # Running as PyInstaller bundle
                base_dir = Path(sys._MEIPASS)
            else:
                # Running as normal Python script
                current_file_path = Path(__file__)
                # Navigate from kairo/tooling/common/services/ to project root
                base_dir = current_file_path.parent.parent.parent.parent

            search_locations.extend(
                [
                    base_dir / "ToolingManifest.json",
                ]
            )

        return search_locations

    def _parse_manifest_file(
        self, manifest_path: Path, environment_id: str
    ) -> List[MCPServerConfig]:
        """
        Parses the manifest file and extracts MCP server configurations.

        Args:
            manifest_path: Path to the manifest file.
            environment_id: Environment ID for URL construction.

        Returns:
            List of parsed MCP server configurations.
        """
        mcp_servers: List[MCPServerConfig] = []

        with open(manifest_path, "r", encoding="utf-8") as file:
            json_content = file.read()

        print(f"📄 Manifest content: {json_content}")
        manifest_data = json.loads(json_content)

        if "mcpServers" in manifest_data:
            print("✅ Found 'mcpServers' section in ToolingManifest.json")
            self._logger.info("Found 'mcpServers' section in ToolingManifest.json")
            mcp_servers_data = manifest_data["mcpServers"]

            if isinstance(mcp_servers_data, list):
                print(f"📊 Processing {len(mcp_servers_data)} server entries")
                for server_element in mcp_servers_data:
                    print(f"🔧 Processing server element: {server_element}")
                    server_config = self._parse_manifest_server_config(
                        server_element, environment_id
                    )
                    if server_config is not None:
                        print(
                            f"✅ Created server config: {server_config.mcp_server_name} -> {server_config.mcp_server_unique_name}"
                        )
                        mcp_servers.append(server_config)
                    else:
                        print(f"❌ Failed to parse server config from: {server_element}")
        else:
            print("❌ No 'mcpServers' section found in ToolingManifest.json")

        print(f"📊 Final result: Loaded {len(mcp_servers)} MCP server configurations")
        self._logger.info(f"Loaded {len(mcp_servers)} MCP server configurations")

        return mcp_servers

    def _log_manifest_search_failure(self) -> None:
        """Logs information about failed manifest file search."""
        search_locations = self._get_manifest_search_locations()

        print("❌ ToolingManifest.json not found. Checked locations:")
        for path in search_locations:
            print(f"   - {path}")

        self._logger.info(
            f"ToolingManifest.json not found. Checked {len(search_locations)} locations"
        )
        self._logger.info(
            "Please ensure ToolingManifest.json exists in your project's output directory."
        )

    # --------------------------------------------------------------------------
    # PRODUCTION: GATEWAY-BASED CONFIGURATION
    # --------------------------------------------------------------------------

    async def _load_servers_from_gateway(
        self, agentic_app_id: str, environment_id: str, auth_token: str
    ) -> List[MCPServerConfig]:
        """
        Reads MCP server configurations from tooling gateway endpoint for production scenario.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            environment_id: Environment ID for the environment.
            auth_token: Authentication token to access the tooling gateway.

        Returns:
            List[MCPServerConfig]: List of MCP server configurations from tooling gateway.

        Raises:
            Exception: If there's an error communicating with the tooling gateway.
        """
        mcp_servers: List[MCPServerConfig] = []

        try:
            config_endpoint = get_tooling_gateway_for_digital_worker(agentic_app_id)
            headers = self._prepare_gateway_headers(auth_token, environment_id)

            self._logger.info(f"Calling tooling gateway endpoint: {config_endpoint}")

            async with aiohttp.ClientSession() as session:
                async with session.get(config_endpoint, headers=headers) as response:
                    if response.status == 200:
                        mcp_servers = await self._parse_gateway_response(response)
                        self._logger.info(
                            f"Retrieved {len(mcp_servers)} MCP tool servers from tooling gateway"
                        )
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")

        except aiohttp.ClientError as http_ex:
            error_msg = f"Failed to connect to MCP configuration endpoint: {str(http_ex)}"
            self._logger.error(error_msg)
            raise Exception(error_msg) from http_ex
        except json.JSONDecodeError as json_ex:
            error_msg = f"Failed to parse MCP server configuration response: {str(json_ex)}"
            self._logger.error(error_msg)
            raise Exception(error_msg) from json_ex
        except Exception as e:
            error_msg = f"Failed to read MCP servers from endpoint: {str(e)}"
            self._logger.error(error_msg)
            raise Exception(error_msg) from e

        return mcp_servers

    def _prepare_gateway_headers(self, auth_token: str, environment_id: str) -> Dict[str, str]:
        """
        Prepares headers for tooling gateway requests.

        Args:
            auth_token: Authentication token.
            environment_id: Environment ID.

        Returns:
            Dictionary of HTTP headers.
        """
        if get_use_environment_id():
            return {
                "Authorization": f"{Constants.Headers.BEARER_PREFIX} {auth_token}",
                Constants.Headers.ENVIRONMENT_ID: environment_id,
            }
        return {
            "Authorization": f"{Constants.Headers.BEARER_PREFIX} {auth_token}",
        }

    async def _parse_gateway_response(
        self, response: aiohttp.ClientResponse
    ) -> List[MCPServerConfig]:
        """
        Parses the response from the tooling gateway.

        Args:
            response: HTTP response from the gateway.

        Returns:
            List of parsed MCP server configurations.
        """
        mcp_servers: List[MCPServerConfig] = []

        response_text = await response.text()
        config_data = json.loads(response_text)

        if "mcpServers" in config_data and isinstance(config_data["mcpServers"], list):
            for server_element in config_data["mcpServers"]:
                server_config = self._parse_gateway_server_config(server_element)
                if server_config is not None:
                    mcp_servers.append(server_config)

        return mcp_servers

    # --------------------------------------------------------------------------
    # CONFIGURATION PARSING HELPERS
    # --------------------------------------------------------------------------

    def _parse_manifest_server_config(
        self, server_element: Dict[str, Any], environment_id: str
    ) -> Optional[MCPServerConfig]:
        """
        Parses a server configuration from manifest data, constructing full URL.

        Args:
            server_element: Dictionary containing server configuration from manifest.
            environment_id: Environment ID to construct full URL.

        Returns:
            MCPServerConfig object or None if parsing fails.
        """
        try:
            name = self._extract_server_name(server_element)
            server_name = self._extract_server_unique_name(server_element)

            if not self._validate_server_strings(name, server_name):
                return None

            # Construct full URL using environment utilities
            full_url = build_mcp_server_url(environment_id, server_name)

            return MCPServerConfig(mcp_server_name=name, mcp_server_unique_name=full_url)

        except Exception:
            return None

    def _parse_gateway_server_config(
        self, server_element: Dict[str, Any]
    ) -> Optional[MCPServerConfig]:
        """
        Parses a server configuration from gateway response data.

        Args:
            server_element: Dictionary containing server configuration from gateway.

        Returns:
            MCPServerConfig object or None if parsing fails.
        """
        try:
            name = self._extract_server_name(server_element)
            endpoint = self._extract_server_unique_name(server_element)

            if not self._validate_server_strings(name, endpoint):
                return None

            return MCPServerConfig(mcp_server_name=name, mcp_server_unique_name=endpoint)

        except Exception:
            return None

    # --------------------------------------------------------------------------
    # VALIDATION AND UTILITY HELPERS
    # --------------------------------------------------------------------------

    def _validate_input_parameters(
        self, agentic_app_id: str, environment_id: str, auth_token: str
    ) -> None:
        """
        Validates input parameters for the main API method.

        Args:
            agentic_app_id: Agentic App ID to validate.
            environment_id: Environment ID to validate.
            auth_token: Authentication token to validate.

        Raises:
            ValueError: If any parameter is invalid or empty.
        """
        if not agentic_app_id:
            raise ValueError("agentic_app_id cannot be empty or None")
        if get_use_environment_id() and not environment_id:
            raise ValueError("environment_id cannot be empty or None")
        if not auth_token:
            raise ValueError("auth_token cannot be empty or None")

    def _extract_server_name(self, server_element: Dict[str, Any]) -> Optional[str]:
        """
        Extracts server name from configuration element.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server name string or None.
        """
        if "mcpServerName" in server_element and isinstance(server_element["mcpServerName"], str):
            return server_element["mcpServerName"]
        return None

    def _extract_server_unique_name(self, server_element: Dict[str, Any]) -> Optional[str]:
        """
        Extracts server unique name from configuration element.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server unique name string or None.
        """
        if "mcpServerUniqueName" in server_element and isinstance(
            server_element["mcpServerUniqueName"], str
        ):
            return server_element["mcpServerUniqueName"]
        return None

    def _validate_server_strings(self, name: Optional[str], unique_name: Optional[str]) -> bool:
        """
        Validates that server name and unique name are valid strings.

        Args:
            name: Server name to validate.
            unique_name: Server unique name to validate.

        Returns:
            True if both strings are valid, False otherwise.
        """
        return name is not None and name.strip() and unique_name is not None and unique_name.strip()
