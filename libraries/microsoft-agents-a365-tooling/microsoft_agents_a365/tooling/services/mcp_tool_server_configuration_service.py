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
import uuid
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

# Third-party imports
import aiohttp
from microsoft_agents.hosting.core import Authorization, TurnContext

# Local imports
from ..models import ChatHistoryMessage, ChatMessageRequest, MCPServerConfig, ToolOptions
from ..utils import Constants
from ..utils.utility import (
    ATG_APP_ID,
    ATG_APP_ID_URI,
    build_mcp_server_url,
    get_chat_history_endpoint,
    get_mcp_platform_authentication_scope,
    get_tooling_gateway_for_digital_worker,
    is_development_environment,
    resolve_token_scope_for_server,
)

# Runtime Imports
from microsoft_agents_a365.runtime import OperationError, OperationResult
from microsoft_agents_a365.runtime.utility import Utility as RuntimeUtility


# ==============================================================================
# TYPES
# ==============================================================================

# Callable that acquires an auth token for a given server and scope.
# Returns the raw token string (without Bearer prefix), or None if unavailable.
# Used by _attach_per_audience_tokens to decouple token acquisition strategy
# (dev env-var reads vs. production OBO exchange) from token attachment logic.
TokenAcquirer = Callable[["MCPServerConfig", str], Awaitable[Optional[str]]]


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
        self,
        agentic_app_id: str,
        auth_token: Optional[str] = None,
        options: Optional[ToolOptions] = None,
        authorization: Optional[Authorization] = None,
        auth_handler_name: Optional[str] = None,
        turn_context: Optional[TurnContext] = None,
    ) -> List[MCPServerConfig]:
        """
        Gets the list of MCP Servers that are configured for the agent.

        When ``authorization``, ``auth_handler_name``, and ``turn_context`` are all provided,
        per-audience OAuth tokens are acquired for each server after discovery:
        - V1 servers (no ``audience`` field) share the shared ATG token (one exchange).
        - V2 servers each receive a token scoped to their own audience GUID.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            auth_token: Authentication token used for gateway discovery.
            options: Optional ToolOptions instance containing optional parameters.
            authorization: Optional Authorization context for per-audience token exchange.
            auth_handler_name: Optional auth handler name used with ``authorization``.
            turn_context: Optional TurnContext used with ``authorization``.

        Returns:
            List[MCPServerConfig]: Returns the list of MCP Servers that are configured,
            each with an ``Authorization`` header attached when auth context is provided.

        Raises:
            ValueError: If required parameters are invalid or empty.
            Exception: If there's an error communicating with the tooling gateway or
                       a per-audience token exchange fails.
        """
        # Validate input parameters
        self._validate_input_parameters(agentic_app_id, auth_token)

        # Use default options if none provided
        if options is None:
            options = ToolOptions(orchestrator_name=None)

        self._logger.info(f"Listing MCP tool servers for agent {agentic_app_id}")

        # Determine configuration source and token acquirer based on environment.
        if self._is_development_scenario():
            servers = self._load_servers_from_manifest()
            # Dev: read pre-acquired tokens from env vars (no OBO exchange).
            # BEARER_TOKEN_<MCPSERVERNAME_UPPER> takes precedence; BEARER_TOKEN is the fallback.
            acquire: TokenAcquirer = self._create_dev_token_acquirer()
        else:
            servers = await self._load_servers_from_gateway(
                agentic_app_id, auth_token, options, turn_context
            )
            if (
                authorization is not None
                and auth_handler_name is not None
                and turn_context is not None
            ):
                # Prod: acquire per-audience tokens via OBO for each unique server audience.
                # V1 servers share the shared ATG token; V2 servers each get their own audience token.
                acquire = self._create_obo_token_acquirer(
                    authorization, auth_handler_name, turn_context
                )
            else:
                # Legacy call without auth context — guard against V2 servers.
                # V2 servers require per-audience OBO exchange; returning them without a
                # token would cause silent 401s downstream. Raise early with a clear
                # migration hint so callers know which parameters to add.
                v2_servers = [s for s in servers if self._is_v2_server(s)]
                if v2_servers:
                    names = ", ".join(
                        s.mcp_server_name or s.mcp_server_unique_name for s in v2_servers
                    )
                    raise Exception(
                        f"MCP servers [{names}] require per-audience token exchange (V2) but "
                        "no authorization context was provided. Pass authorization, "
                        "auth_handler_name, and turn_context to list_tool_servers()."
                    )
                return servers

        servers = await self._attach_per_audience_tokens(servers, acquire)
        return servers

    # --------------------------------------------------------------------------
    # ENVIRONMENT DETECTION
    # --------------------------------------------------------------------------

    def _is_development_scenario(self) -> bool:
        """
        Determines if this is a development scenario.

        Delegates to ``is_development_environment()`` from utility so all callers
        use the same env-var resolution order.

        Returns:
            bool: True if running in development mode, False otherwise.
        """
        is_dev = is_development_environment()
        self._logger.debug(f"Development scenario: {is_dev}")
        return is_dev

    def _is_v2_server(self, server: MCPServerConfig) -> bool:
        """
        Returns True if the server requires a per-audience token (V2).

        V2 servers carry a distinct ``audience`` that is neither the shared ATG AppId
        (bare GUID or ``api://`` URI form) nor the sentinel value ``"default"``.
        Uses the same normalization as ``resolve_token_scope_for_server`` so the
        V1/V2 classification is always consistent.
        """
        if server.audience is None:
            return False
        audience = server.audience.strip().lower()
        return audience != "default" and audience != ATG_APP_ID and audience != ATG_APP_ID_URI

    def _create_dev_token_acquirer(self) -> TokenAcquirer:
        """
        Returns a ``TokenAcquirer`` that reads pre-acquired tokens from environment variables.

        The CLI (``a365 develop get-token``) writes tokens to the environment before the agent
        starts. Resolution order per server:

        1. ``BEARER_TOKEN_<MCP_SERVER_NAME_UPPER>`` — per-server token
        2. ``BEARER_TOKEN`` — shared fallback token

        Tokens are returned **without** a ``Bearer `` prefix. If the env var already contains
        a ``Bearer `` prefix (any casing), it is stripped so that
        ``_attach_per_audience_tokens`` does not produce ``Authorization: Bearer Bearer …``.

        A WARNING is emitted when the shared ``BEARER_TOKEN`` is used for a V2 server
        whose resolved scope differs from the shared ATG scope, because the shared token
        is audience-locked and will cause a 401 against that server's endpoint.

        Returns:
            TokenAcquirer: Async callable ``(server, scope) → Optional[str]``.
        """
        shared_scope = get_mcp_platform_authentication_scope()[0]

        async def acquire(server: MCPServerConfig, scope: str) -> Optional[str]:
            server_name = server.mcp_server_name or ""
            per_server_key = f"BEARER_TOKEN_{server_name.upper()}"
            has_per_server = per_server_key in os.environ
            token = os.environ.get(per_server_key) or os.environ.get("BEARER_TOKEN")
            if not token:
                return None
            if token and not has_per_server and scope != shared_scope:
                self._logger.warning(
                    f"Dev: MCP server '{server_name}' requires scope '{scope}' "
                    f"but only BEARER_TOKEN is set. The shared token is scoped to "
                    f"a different audience and will likely cause a 401. "
                    f"Set {per_server_key} to a token acquired for the correct audience."
                )
            # Strip an existing "Bearer " prefix (case-insensitive) so the caller
            # always receives a raw token and the Authorization header is never doubled.
            if token.lower().startswith("bearer "):
                token = token[7:]
            self._logger.debug(
                f"Attached {'per-server' if has_per_server else 'shared'} "
                f"dev token for '{server.mcp_server_name}'"
            )
            return token

        return acquire

    def _create_obo_token_acquirer(
        self,
        authorization: Authorization,
        auth_handler_name: str,
        turn_context: TurnContext,
    ) -> TokenAcquirer:
        """
        Returns a ``TokenAcquirer`` that performs an OBO token exchange per unique scope.

        V1 servers (no ``audience`` field) share the shared ATG-scoped token (one exchange).
        V2 servers each receive a token scoped to their own audience GUID.

        Args:
            authorization: Authorization context for token exchange.
            auth_handler_name: Auth handler name to pass to the token exchange.
            turn_context: TurnContext to pass to the token exchange.

        Returns:
            TokenAcquirer: Async callable ``(server, scope) → str`` (raises on failure).
        """

        async def acquire(server: MCPServerConfig, scope: str) -> Optional[str]:
            self._logger.debug(
                f"Acquiring OBO token for MCP server '{server.mcp_server_name}' (scope: {scope})"
            )
            token_result = await authorization.exchange_token(
                turn_context, [scope], auth_handler_name
            )
            if token_result is None or not token_result.token:
                raise Exception(
                    f"Failed to obtain token for MCP server '{server.mcp_server_name}'"
                    f" (scope: {scope})"
                )
            return token_result.token

        return acquire

    async def _attach_per_audience_tokens(
        self,
        servers: List[MCPServerConfig],
        acquire: TokenAcquirer,
    ) -> List[MCPServerConfig]:
        """
        Acquire one token per unique audience scope and attach ``Authorization: Bearer`` headers.

        Caches acquired tokens by scope so each unique audience triggers exactly one
        ``acquire`` call regardless of how many servers share that scope.

        V1 servers (no ``audience`` field) all share one token exchange.
        V2 servers each receive a token scoped to their own audience GUID.

        Args:
            servers: List of MCP server configs returned from discovery.
            acquire: ``TokenAcquirer`` callable returned by ``_create_dev_token_acquirer`` or
                     ``_create_obo_token_acquirer``. Receives ``(server, scope)`` and returns
                     the raw token string (no Bearer prefix), or ``None`` if unavailable.

        Returns:
            List[MCPServerConfig]: New list of server configs with ``Authorization`` headers set
            where a token was available.

        Raises:
            Exception: If the OBO acquirer fails for any server (propagated from ``acquire``).
        """
        token_cache: Dict[str, Optional[str]] = {}  # scope → raw token (None = not available)
        result: List[MCPServerConfig] = []

        for server in servers:
            scope = resolve_token_scope_for_server(server)

            if scope not in token_cache:
                token_cache[scope] = await acquire(server, scope)

            token = token_cache[scope]
            if token:
                merged_headers: Dict[str, str] = dict(server.headers) if server.headers else {}
                merged_headers[Constants.Headers.AUTHORIZATION] = (
                    f"{Constants.Headers.BEARER_PREFIX} {token}"
                )
                final_headers: Optional[Dict[str, str]] = merged_headers
            else:
                # No token acquired — preserve original headers (including None) unchanged.
                final_headers = dict(server.headers) if server.headers else None

            result.append(dataclass_replace(server, headers=final_headers))

        return result

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
        try:
            search_locations = self._get_manifest_search_locations()
            manifest_path = self._find_manifest_file(search_locations)

            if manifest_path is not None:
                self._logger.info(f"Loading MCP servers from: {manifest_path}")
                return self._parse_manifest_file(manifest_path)

            self._logger.info(
                f"ToolingManifest.json not found. Checked {len(search_locations)} locations"
            )
            for path in search_locations:
                self._logger.debug(f"  Checked: {path}")
            self._logger.info(
                "Please ensure ToolingManifest.json exists in your project's output directory."
            )
            return []

        except Exception as e:
            raise Exception(
                f"Failed to read MCP servers from ToolingManifest.json: {str(e)}"
            ) from e

    def _find_manifest_file(self, search_locations: List[Path]) -> Optional[Path]:
        """
        Searches for ToolingManifest.json in the provided locations.

        Args:
            search_locations: Ordered list of paths to check.

        Returns:
            Path to manifest file if found, None otherwise.
        """
        for potential_path in search_locations:
            self._logger.debug(f"Checking for manifest at: {potential_path}")
            if potential_path.exists():
                self._logger.info(f"Found manifest at: {potential_path}")
                return potential_path

        return None

    def _get_manifest_search_locations(self) -> List[Path]:
        """
        Gets the ordered list of candidate paths for ToolingManifest.json.

        Searches the current working directory and its parent only. File-relative
        path traversal is not used because it is unreliable for installed packages.

        Returns:
            List of Path objects to search for the manifest file.
        """
        current_dir = Path.cwd()
        return [
            current_dir / "ToolingManifest.json",
            current_dir.parent / "ToolingManifest.json",
        ]

    def _parse_manifest_file(self, manifest_path: Path) -> List[MCPServerConfig]:
        """
        Parses the manifest file and extracts MCP server configurations.

        Args:
            manifest_path: Path to the manifest file.

        Returns:
            List of parsed MCP server configurations.
        """
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest_data = json.load(file)

        if "mcpServers" not in manifest_data:
            self._logger.warning("No 'mcpServers' section found in ToolingManifest.json")
            return []

        self._logger.info("Found 'mcpServers' section in ToolingManifest.json")
        mcp_servers_data = manifest_data["mcpServers"]

        if not isinstance(mcp_servers_data, list):
            self._logger.warning("'mcpServers' in ToolingManifest.json is not a list — skipping")
            return []

        self._logger.debug(f"Processing {len(mcp_servers_data)} server entries from manifest")
        mcp_servers: List[MCPServerConfig] = []
        for server_element in mcp_servers_data:
            server_config = self._parse_server_config(server_element)
            if server_config is not None:
                mcp_servers.append(server_config)

        self._logger.info(f"Loaded {len(mcp_servers)} MCP server configurations from manifest")
        return mcp_servers

    # --------------------------------------------------------------------------
    # PRODUCTION: GATEWAY-BASED CONFIGURATION
    # --------------------------------------------------------------------------

    async def _load_servers_from_gateway(
        self,
        agentic_app_id: str,
        auth_token: str,
        options: ToolOptions,
        turn_context: Optional[TurnContext] = None,
    ) -> List[MCPServerConfig]:
        """
        Reads MCP server configurations from tooling gateway endpoint for production scenario.

        Args:
            agentic_app_id: Agentic App ID for the agent.
            auth_token: Authentication token to access the tooling gateway.
            options: ToolOptions instance containing optional parameters.
            turn_context: Optional TurnContext used to derive the correlation ID from
                          ``activity.id``. A new UUID is generated when not provided.

        Returns:
            List[MCPServerConfig]: List of MCP server configurations from tooling gateway.

        Raises:
            Exception: If there's an error communicating with the tooling gateway.
        """
        try:
            config_endpoint = get_tooling_gateway_for_digital_worker(agentic_app_id)
            headers = self._prepare_gateway_headers(auth_token, options, turn_context)

            self._logger.info(f"Calling tooling gateway endpoint: {config_endpoint}")

            timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(config_endpoint, headers=headers) as response:
                    if response.status == 200:
                        mcp_servers = await self._parse_gateway_response(response)
                        self._logger.info(
                            f"Retrieved {len(mcp_servers)} MCP tool servers from tooling gateway"
                        )
                        return mcp_servers
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

    def _prepare_gateway_headers(
        self, auth_token: str, options: ToolOptions, turn_context: Optional[TurnContext] = None
    ) -> Dict[str, str]:
        """
        Prepares headers for tooling gateway requests.

        Args:
            auth_token: Authentication token.
            options: ToolOptions instance containing optional parameters.
            turn_context: Optional TurnContext for extracting agent blueprint ID and
                          correlation ID from ``activity.id``.

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

        # Add x-ms-correlation-id: prefer activity.id from TurnContext, fall back to a new UUID
        correlation_id = self._resolve_correlation_id(turn_context)
        headers[Constants.Headers.CORRELATION_ID] = correlation_id
        self._logger.debug(f"Gateway request correlation ID: {correlation_id}")

        return headers

    def _resolve_correlation_id(self, turn_context: Optional[TurnContext] = None) -> str:
        """
        Resolves the correlation ID to attach to outbound gateway requests.

        Uses ``turn_context.activity.id`` when available so the gateway log entry can be
        correlated with the inbound activity. Falls back to a newly generated UUID4 when
        no context is provided.

        Args:
            turn_context: Optional TurnContext to extract the activity ID from.

        Returns:
            str: Correlation ID string (non-empty).
        """
        try:
            if (
                turn_context is not None
                and turn_context.activity is not None
                and turn_context.activity.id
            ):
                return turn_context.activity.id
        except (AttributeError, TypeError):
            pass

        return str(uuid.uuid4())

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

        Supports two response shapes:
        - Wrapped: ``{"mcpServers": [...]}``
        - Raw array: ``[...]`` (legacy V1 gateway format)

        Args:
            response: HTTP response from the gateway.

        Returns:
            List of parsed MCP server configurations.
        """
        config_data = await response.json(content_type=None)

        server_elements: Optional[List[object]] = None
        if isinstance(config_data, list):
            # Raw array format (legacy V1 gateway returns bare array)
            self._logger.debug("Gateway returned raw array response")
            server_elements = config_data
        elif isinstance(config_data, dict) and isinstance(config_data.get("mcpServers"), list):
            # Wrapped format: {"mcpServers": [...]}
            self._logger.debug("Gateway returned wrapped mcpServers response")
            server_elements = config_data["mcpServers"]
        else:
            self._logger.warning(
                'Unexpected gateway response format: expected a list or {"mcpServers": [...]}'
            )
            return []

        mcp_servers: List[MCPServerConfig] = []
        for server_element in server_elements:
            if isinstance(server_element, dict):
                server_config = self._parse_server_config(server_element)
                if server_config is not None:
                    mcp_servers.append(server_config)

        return mcp_servers

    # --------------------------------------------------------------------------
    # CONFIGURATION PARSING HELPERS
    # --------------------------------------------------------------------------

    def _parse_server_config(self, server_element: Dict[str, object]) -> Optional[MCPServerConfig]:
        """
        Parses a server configuration from manifest or gateway response data.

        Handles both development (manifest) and production (gateway) payloads —
        the two sources share the same JSON field schema.

        Args:
            server_element: Dictionary containing server configuration.

        Returns:
            MCPServerConfig object, or None if the element is invalid or unparseable.
        """
        try:
            mcp_server_name = self._extract_server_name(server_element)
            mcp_server_unique_name = self._extract_server_unique_name(server_element)

            if not self._validate_server_strings(mcp_server_name, mcp_server_unique_name):
                return None

            endpoint = self._extract_server_url(server_element)
            # Use mcp_server_name if available, otherwise fall back to mcp_server_unique_name
            server_name = mcp_server_name or mcp_server_unique_name
            final_url = endpoint if endpoint else build_mcp_server_url(server_name)

            scope_raw = server_element.get("scope")
            scope = (
                None
                if not scope_raw or (isinstance(scope_raw, str) and scope_raw.lower() == "null")
                else str(scope_raw)
            )

            audience_raw = server_element.get("audience")
            audience = (
                None
                if not audience_raw
                or (isinstance(audience_raw, str) and audience_raw.lower() == "default")
                else str(audience_raw)
            )

            publisher_raw = server_element.get("publisher")
            publisher = str(publisher_raw) if publisher_raw is not None else None

            return MCPServerConfig(
                mcp_server_name=mcp_server_name,
                mcp_server_unique_name=mcp_server_unique_name,
                url=final_url,
                audience=audience,
                scope=scope,
                publisher=publisher,
            )

        except Exception as exc:
            self._logger.warning(
                f"Failed to parse server config from element {server_element!r}: {exc}"
            )
            return None

    # --------------------------------------------------------------------------
    # VALIDATION AND UTILITY HELPERS
    # --------------------------------------------------------------------------

    def _validate_input_parameters(self, agentic_app_id: str, auth_token: Optional[str]) -> None:
        """
        Validates input parameters for the main API method.

        In development mode, servers are loaded from ToolingManifest.json rather than
        the gateway, so neither ``agentic_app_id`` nor ``auth_token`` is required.
        Validation is therefore skipped in dev mode to allow token-free local development.

        Args:
            agentic_app_id: Agentic App ID to validate (required in production).
            auth_token: Authentication token to validate (required in production).

        Raises:
            ValueError: If any required parameter is invalid or empty (production only).
        """
        if self._is_development_scenario():
            return
        if not agentic_app_id:
            raise ValueError("agentic_app_id cannot be empty or None")
        if not auth_token:
            raise ValueError("auth_token cannot be empty or None")

    def _extract_server_name(self, server_element: Dict[str, object]) -> Optional[str]:
        """
        Extracts server name from configuration element.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server name string or None.
        """
        value = server_element.get("mcpServerName")
        return value if isinstance(value, str) else None

    def _extract_server_unique_name(self, server_element: Dict[str, object]) -> Optional[str]:
        """
        Extracts server unique name from configuration element.

        Falls back to ``mcpServerName`` when ``mcpServerUniqueName`` is absent.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server unique name string or None.
        """
        value = server_element.get("mcpServerUniqueName")
        if isinstance(value, str):
            return value
        # Fall back to mcpServerName when mcpServerUniqueName is absent
        fallback = server_element.get("mcpServerName")
        return fallback if isinstance(fallback, str) else None

    def _extract_server_url(self, server_element: Dict[str, object]) -> Optional[str]:
        """
        Extracts custom server URL from configuration element.

        Args:
            server_element: Configuration dictionary.

        Returns:
            Server URL string or None.
        """
        value = server_element.get("url")
        return value if isinstance(value, str) else None

    def _validate_server_strings(self, name: Optional[str], unique_name: Optional[str]) -> bool:
        """
        Validates that server name and unique name are non-empty strings.

        Args:
            name: Server name to validate.
            unique_name: Server unique name to validate.

        Returns:
            True if both strings are valid, False otherwise.
        """
        return (
            name is not None
            and bool(name.strip())
            and unique_name is not None
            and bool(unique_name.strip())
        )

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
