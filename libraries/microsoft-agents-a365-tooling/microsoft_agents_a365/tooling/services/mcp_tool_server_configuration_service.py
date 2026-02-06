# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

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
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Third-party imports
import aiohttp
from microsoft_agents.hosting.core import TurnContext

# Local imports
from ..models import ChatHistoryMessage, ChatMessageRequest, MCPServerConfig, ToolOptions
from ..utils import Constants
from ..utils.utility import (
    get_tooling_gateway_for_digital_worker,
    build_mcp_server_url,
    get_chat_history_endpoint,
)

# Runtime Imports
from microsoft_agents_a365.runtime import OperationError, OperationResult
from microsoft_agents_a365.runtime.utility import Utility as RuntimeUtility


# ==============================================================================
# CONSTANTS
# ==============================================================================

# HTTP timeout in seconds for request operations
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30

# HTTP status code for successful response
HTTP_STATUS_OK = 200


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
        self, agentic_app_id: str, auth_token: str, options: Optional[ToolOptions] = None
    ) -> List[MCPServerConfig]:
        """
        Gets the list of MCP Servers that are configured for the agent.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            auth_token: Authentication token to access the MCP servers.
            options: Optional ToolOptions instance containing optional parameters.

        Returns:
            List[MCPServerConfig]: Returns the list of MCP Servers that are configured.

        Raises:
            ValueError: If required parameters are invalid or empty.
            Exception: If there's an error communicating with the tooling gateway.
        """
        # Validate input parameters
        self._validate_input_parameters(agentic_app_id, auth_token)

        # Use default options if none provided
        if options is None:
            options = ToolOptions(orchestrator_name=None)

        self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

        # Determine configuration source based on environment
        if self._is_development_scenario():
            return self._load_servers_from_manifest()
        else:
            return await self._load_servers_from_gateway(agentic_app_id, auth_token, options)

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

    def _load_servers_from_manifest(self) -> List[MCPServerConfig]:
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
                mcp_servers = self._parse_manifest_file(manifest_path)
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
                # Navigate to project root
                base_dir = current_file_path.parent.parent.parent.parent

            search_locations.extend(
                [
                    base_dir / "ToolingManifest.json",
                ]
            )

        return search_locations

    def _parse_manifest_file(self, manifest_path: Path) -> List[MCPServerConfig]:
        """
        Parses the manifest file and extracts MCP server configurations.

        Args:
            manifest_path: Path to the manifest file.

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
                    server_config = self._parse_manifest_server_config(server_element)
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
        self, agentic_app_id: str, auth_token: str, options: ToolOptions
    ) -> List[MCPServerConfig]:
        """
        Reads MCP server configurations from tooling gateway endpoint for production scenario.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            auth_token: Authentication token to access the tooling gateway.
            options: ToolOptions instance containing optional parameters.

        Returns:
            List[MCPServerConfig]: List of MCP server configurations from tooling gateway.

        Raises:
            Exception: If there's an error communicating with the tooling gateway.
        """
        mcp_servers: List[MCPServerConfig] = []

        try:
            config_endpoint = get_tooling_gateway_for_digital_worker(agentic_app_id)
            headers = self._prepare_gateway_headers(auth_token, options)

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

    def _prepare_gateway_headers(
        self, auth_token: str, options: ToolOptions, turn_context: Optional[TurnContext] = None
    ) -> Dict[str, str]:
        """
        Prepares headers for tooling gateway requests.

        Args:
            auth_token: Authentication token.
            options: ToolOptions instance containing optional parameters.
            turn_context: Optional TurnContext for extracting agent blueprint ID for request headers.

        Returns:
            Dictionary of HTTP headers.
        """
        headers: Dict[str, str] = {
            Constants.Headers.AUTHORIZATION: f"{Constants.Headers.BEARER_PREFIX} {auth_token}",
            Constants.Headers.USER_AGENT: RuntimeUtility.get_user_agent_header(
                options.orchestrator_name
            ),
        }

        # Add x-ms-agentid header with priority fallback
        agent_id = self._resolve_agent_id_for_header(auth_token, turn_context)
        if agent_id:
            headers[Constants.Headers.AGENT_ID] = agent_id

        return headers

    def _resolve_agent_id_for_header(
        self, auth_token: str, turn_context: Optional[TurnContext] = None
    ) -> Optional[str]:
        """
        Resolves the best available agent identifier for the x-ms-agentid header.
        Priority: TurnContext.agenticAppBlueprintId > token claims (xms_par_app_azp > appid > azp)
                  > application name

        Note: This differs from RuntimeUtility.resolve_agent_identity() which resolves the agenticAppId
        for URL construction. This method resolves the identifier specifically for the x-ms-agentid header.

        Args:
            auth_token: The authentication token to extract claims from.
            turn_context: Optional TurnContext to extract agent blueprint ID from.

        Returns:
            Agent ID string or None if not available.
        """
        # Priority 1: Agent Blueprint ID from TurnContext
        # The 'from_' property may include agentic_app_blueprint_id when the request originates
        # from an agentic app
        try:
            if turn_context and turn_context.activity and turn_context.activity.from_:
                blueprint_id = getattr(
                    turn_context.activity.from_, "agentic_app_blueprint_id", None
                )
                if blueprint_id:
                    return blueprint_id
        except (AttributeError, TypeError):
            pass

        # Priority 2 & 3: Agent ID from token (xms_par_app_azp > appid > azp)
        # Single decode, checks claims in priority order
        agent_id = RuntimeUtility.get_agent_id_from_token(auth_token)
        if agent_id:
            return agent_id

        # Priority 4: Application name from AGENT365_APPLICATION_NAME env or pyproject.toml
        return RuntimeUtility.get_application_name()

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
        self, server_element: Dict[str, Any]
    ) -> Optional[MCPServerConfig]:
        """
        Parses a server configuration from manifest data, constructing full URL.

        Args:
            server_element: Dictionary containing server configuration from manifest.

        Returns:
            MCPServerConfig object or None if parsing fails.
        """
        try:
            mcp_server_name = self._extract_server_name(server_element)
            mcp_server_unique_name = self._extract_server_unique_name(server_element)

            if not self._validate_server_strings(mcp_server_name, mcp_server_unique_name):
                return None

            # Check if a URL is provided
            endpoint = self._extract_server_url(server_element)

            # Use mcp_server_name if available, otherwise fall back to mcp_server_unique_name for URL construction
            server_name = mcp_server_name or mcp_server_unique_name

            # Determine the final URL: use custom URL if provided, otherwise construct it
            final_url = endpoint if endpoint else build_mcp_server_url(server_name)

            return MCPServerConfig(
                mcp_server_name=mcp_server_name,
                mcp_server_unique_name=mcp_server_unique_name,
                url=final_url,
            )

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
            mcp_server_name = self._extract_server_name(server_element)
            mcp_server_unique_name = self._extract_server_unique_name(server_element)

            if not self._validate_server_strings(mcp_server_name, mcp_server_unique_name):
                return None

            # Check if a URL is provided by the gateway
            endpoint = self._extract_server_url(server_element)

            # Use mcp_server_name if available, otherwise fall back to mcp_server_unique_name for URL construction
            server_name = mcp_server_name or mcp_server_unique_name

            # Determine the final URL: use custom URL if provided, otherwise construct it
            final_url = endpoint if endpoint else build_mcp_server_url(server_name)

            return MCPServerConfig(
                mcp_server_name=mcp_server_name,
                mcp_server_unique_name=mcp_server_unique_name,
                url=final_url,
            )

        except Exception:
            return None

    # --------------------------------------------------------------------------
    # VALIDATION AND UTILITY HELPERS
    # --------------------------------------------------------------------------

    def _validate_input_parameters(self, agentic_app_id: str, auth_token: str) -> None:
        """
        Validates input parameters for the main API method.

        Args:
            agentic_app_id: Agentic App ID to validate.
            auth_token: Authentication token to validate.

        Raises:
            ValueError: If any parameter is invalid or empty.
        """
        if not agentic_app_id:
            raise ValueError("agentic_app_id cannot be empty or None")
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

    def _extract_server_url(self, server_element: Dict[str, Any]) -> Optional[str]:
        """
        Extracts custom server URL from configuration element.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server URL string or None.
        """
        # Check for 'url' field in both manifest and gateway responses
        if "url" in server_element and isinstance(server_element["url"], str):
            return server_element["url"]
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

    # --------------------------------------------------------------------------
    # SEND CHAT HISTORY
    # --------------------------------------------------------------------------

    async def send_chat_history(
        self,
        turn_context: TurnContext,
        chat_history_messages: List[ChatHistoryMessage],
        options: Optional[ToolOptions] = None,
    ) -> OperationResult:
        """
        Sends chat history to the MCP platform for real-time threat protection.

        Args:
            turn_context: TurnContext from the Agents SDK containing conversation information.
                          Must have a valid activity with conversation.id, activity.id, and
                          activity.text.
            chat_history_messages: List of ChatHistoryMessage objects representing the chat
                                   history. May be empty - an empty list will still send a
                                   request to the MCP platform with empty chat history.
            options: Optional ToolOptions instance containing optional parameters.

        Returns:
            OperationResult: An OperationResult indicating success or failure.
                             On success, returns OperationResult.success().
                             On failure, returns OperationResult.failed() with error details.

        Raises:
            ValueError: If turn_context is None, chat_history_messages is None,
                        turn_context.activity is None, or any of the required fields
                        (conversation.id, activity.id, activity.text) are missing or empty.

        Note:
            Even if chat_history_messages is empty, the request will still be sent to
            the MCP platform. This ensures the user message from turn_context.activity.text
            is registered correctly for real-time threat protection.

        Example:
            >>> from datetime import datetime, timezone
            >>> from microsoft_agents_a365.tooling.models import ChatHistoryMessage
            >>>
            >>> history = [
            ...     ChatHistoryMessage("msg-1", "user", "Hello", datetime.now(timezone.utc)),
            ...     ChatHistoryMessage("msg-2", "assistant", "Hi!", datetime.now(timezone.utc))
            ... ]
            >>>
            >>> service = McpToolServerConfigurationService()
            >>> result = await service.send_chat_history(turn_context, history)
            >>> if result.succeeded:
            ...     print("Chat history sent successfully")
        """
        # Validate input parameters
        if turn_context is None:
            raise ValueError("turn_context cannot be None")
        if chat_history_messages is None:
            raise ValueError("chat_history_messages cannot be None")

        # Note: Empty chat_history_messages is allowed - we still send the request to MCP platform
        # The platform needs to receive the request even with empty chat history

        # Extract required information from turn context
        if not turn_context.activity:
            raise ValueError("turn_context.activity cannot be None")

        conversation_id: Optional[str] = (
            turn_context.activity.conversation.id if turn_context.activity.conversation else None
        )
        message_id: Optional[str] = turn_context.activity.id
        user_message: Optional[str] = turn_context.activity.text

        if conversation_id is None or (
            isinstance(conversation_id, str) and not conversation_id.strip()
        ):
            raise ValueError(
                "conversation_id cannot be empty or None (from turn_context.activity.conversation.id)"
            )
        if message_id is None or (isinstance(message_id, str) and not message_id.strip()):
            raise ValueError("message_id cannot be empty or None (from turn_context.activity.id)")
        if user_message is None or (isinstance(user_message, str) and not user_message.strip()):
            raise ValueError(
                "user_message cannot be empty or None (from turn_context.activity.text)"
            )

        # Use default options if none provided
        if options is None:
            options = ToolOptions(orchestrator_name=None)

        # Get the endpoint URL
        endpoint = get_chat_history_endpoint()

        # Log only the URL path to avoid accidentally exposing sensitive data in query strings
        parsed_url = urlparse(endpoint)
        self._logger.debug(f"Sending chat history to endpoint path: {parsed_url.path}")

        # Create the request payload
        request = ChatMessageRequest(
            conversation_id=conversation_id,
            message_id=message_id,
            user_message=user_message,
            chat_history=chat_history_messages,
        )

        try:
            # Prepare headers (no authentication required)
            headers = {
                Constants.Headers.USER_AGENT: RuntimeUtility.get_user_agent_header(
                    options.orchestrator_name
                ),
                "Content-Type": "application/json",
            }

            # Convert request to JSON (using Pydantic's model_dump with aliases for camelCase)
            json_data = json.dumps(request.model_dump(by_alias=True, mode="json"))

            # Send POST request with timeout to prevent indefinite hangs
            timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=headers, data=json_data) as response:
                    if response.status == HTTP_STATUS_OK:
                        self._logger.info("Successfully sent chat history to MCP platform")
                        return OperationResult.success()
                    else:
                        error_text = await response.text()
                        self._logger.error(
                            f"HTTP error sending chat history: HTTP {response.status}. "
                            f"Response: {error_text[:500]}"
                        )
                        # Use ClientResponseError for consistent error handling
                        http_error = aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=error_text,
                            headers=response.headers,
                        )
                        return OperationResult.failed(OperationError(http_error))

        except asyncio.TimeoutError as timeout_ex:
            # Catch TimeoutError before ClientError since aiohttp.ServerTimeoutError
            # inherits from both asyncio.TimeoutError and aiohttp.ClientError
            self._logger.error(
                f"Request timeout sending chat history to '{endpoint}': {str(timeout_ex)}"
            )
            return OperationResult.failed(OperationError(timeout_ex))
        except aiohttp.ClientError as http_ex:
            self._logger.error(f"HTTP error sending chat history to '{endpoint}': {str(http_ex)}")
            return OperationResult.failed(OperationError(http_ex))
        except Exception as ex:
            self._logger.error(f"Failed to send chat history to '{endpoint}': {str(ex)}")
            return OperationResult.failed(OperationError(ex))
