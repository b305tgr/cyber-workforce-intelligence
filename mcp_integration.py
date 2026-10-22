"""Opt-in stdio MCP client for explicitly configured local tool servers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV = "MIDNIGHT_SIGNAL_MCP_CONFIG"
MAX_CONFIG_BYTES = 64 * 1024
MAX_SERVERS = 8
MAX_TOOLS = 40
MAX_TOOL_SCHEMA_BYTES = 16 * 1024
MAX_TOOL_ARGUMENTS_BYTES = 64 * 1024
MAX_TOOL_OUTPUT_CHARS = 30_000
TOOL_TIMEOUT_SECONDS = 30


class MCPConfigurationError(ValueError):
    """The opt-in MCP configuration is invalid."""


class MCPToolError(RuntimeError):
    """An MCP server could not be queried or returned an error."""


@dataclass(frozen=True)
class MCPServer:
    name: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    cwd: str | None


@dataclass(frozen=True)
class MCPTool:
    server: MCPServer
    name: str
    exposed_name: str
    description: str
    schema: dict[str, Any]


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "MidnightSignal" / "mcp_servers.json"
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "midnight-signal" / "mcp_servers.json"


def _as_text_list(value: Any, field: str, server_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 128:
        raise MCPConfigurationError(
            f"MCP server {server_name!r}: {field} must be a list of at most 128 strings"
        )
    if any(not isinstance(item, str) or "\0" in item for item in value):
        raise MCPConfigurationError(
            f"MCP server {server_name!r}: {field} values must be text without NUL characters"
        )
    return tuple(value)


def load_servers(path: Path | None = None) -> list[MCPServer]:
    config_file = path or config_path()
    try:
        raw = config_file.read_bytes()
    except FileNotFoundError:
        return []
    except OSError as error:
        raise MCPConfigurationError(
            f"Could not read MCP configuration at {config_file}: {error}"
        ) from error
    if len(raw) > MAX_CONFIG_BYTES:
        raise MCPConfigurationError(
            f"MCP configuration exceeds the {MAX_CONFIG_BYTES // 1024} KiB limit"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MCPConfigurationError(
            f"MCP configuration at {config_file} must be valid UTF-8 JSON: {error}"
        ) from error
    if not isinstance(payload, dict) or set(payload) != {"servers"}:
        raise MCPConfigurationError(
            'MCP configuration must contain only a top-level "servers" array'
        )
    entries = payload["servers"]
    if not isinstance(entries, list) or len(entries) > MAX_SERVERS:
        raise MCPConfigurationError(
            f'"servers" must be a list of at most {MAX_SERVERS} local servers'
        )

    servers = []
    names = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) - {"name", "command", "args", "env", "cwd"}:
            raise MCPConfigurationError(
                f"MCP server entry {index + 1} has invalid fields"
            )
        name = entry.get("name")
        command = entry.get("command")
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name)
            or name in names
        ):
            raise MCPConfigurationError(
                f"MCP server entry {index + 1} needs a unique name using letters, numbers, _ or -"
            )
        if not isinstance(command, str) or not command.strip() or "\0" in command:
            raise MCPConfigurationError(
                f"MCP server {name!r} needs a non-empty command"
            )
        args = _as_text_list(entry.get("args", []), "args", name)
        env = entry.get("env", {})
        if (
            not isinstance(env, dict)
            or len(env) > 64
            or any(
                not isinstance(key, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                or not isinstance(value, str)
                or "\0" in value
                for key, value in env.items()
            )
        ):
            raise MCPConfigurationError(
                f"MCP server {name!r}: env must map at most 64 environment variable names to strings"
            )
        cwd = entry.get("cwd")
        if cwd is not None and (
            not isinstance(cwd, str) or not cwd.strip() or "\0" in cwd
        ):
            raise MCPConfigurationError(
                f"MCP server {name!r}: cwd must be a non-empty path string"
            )
        names.add(name)
        servers.append(MCPServer(name, command, args, dict(env), cwd))
    return servers


def _exposed_name(server_name: str, tool_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", f"mcp__{server_name}__{tool_name}")
    if len(normalized) <= 64:
        return normalized
    suffix = hashlib.sha256(
        f"{server_name}\0{tool_name}".encode("utf-8")
    ).hexdigest()[:10]
    return f"{normalized[:53]}_{suffix}"


def _model_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        result = model_dump(by_alias=True, exclude_none=True)
        return result if isinstance(result, dict) else {}
    return {}


def _tool_schema(server: MCPServer, tool: Any) -> MCPTool:
    tool_data = _model_dict(tool)
    name = tool_data.get("name")
    description = tool_data.get("description") or ""
    schema = tool_data.get("inputSchema") or {"type": "object", "properties": {}}
    if (
        not isinstance(name, str)
        or not name
        or len(name) > 160
        or not isinstance(description, str)
        or not isinstance(schema, dict)
        or schema.get("type", "object") != "object"
        or not isinstance(schema.get("properties", {}), dict)
    ):
        raise MCPToolError(f"MCP server {server.name!r} returned an invalid tool definition")
    try:
        if len(json.dumps(schema, ensure_ascii=True).encode("utf-8")) > MAX_TOOL_SCHEMA_BYTES:
            raise MCPToolError(
                f"MCP tool {server.name}.{name} has a schema larger than 16 KiB"
            )
    except (TypeError, ValueError) as error:
        raise MCPToolError(
            f"MCP tool {server.name}.{name} returned a non-JSON schema"
        ) from error
    return MCPTool(
        server=server,
        name=name,
        exposed_name=_exposed_name(server.name, name),
        description=description[:2000],
        schema=schema,
    )


def ollama_schema(tool: MCPTool) -> dict[str, Any]:
    description = tool.description.strip() or "No description provided."
    return {
        "type": "function",
        "function": {
            "name": tool.exposed_name,
            "description": (
                f"MCP server {tool.server.name}; not restricted to the selected "
                "workspace and requires explicit user approval. "
                f"{description}"
            )[:2000],
            "parameters": tool.schema,
        },
    }


def validate_tool_arguments(tool: MCPTool, arguments: dict[str, Any]) -> str | None:
    try:
        argument_size = len(
            json.dumps(arguments, ensure_ascii=True).encode("utf-8")
        )
    except (TypeError, ValueError):
        return "MCP tool arguments must contain JSON-compatible values"
    if argument_size > MAX_TOOL_ARGUMENTS_BYTES:
        return "MCP tool arguments exceed the 64 KiB limit"
    properties = tool.schema.get("properties", {})
    required = tool.schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
        return "MCP tool has an invalid required-arguments schema"
    missing = [key for key in required if key not in arguments]
    if missing:
        return f"missing required argument(s): {', '.join(missing)}"
    if tool.schema.get("additionalProperties") is False:
        unexpected = [key for key in arguments if key not in properties]
        if unexpected:
            return f"unexpected argument(s): {', '.join(unexpected)}"
    return None


def configuration_summary() -> dict[str, Any]:
    try:
        servers = load_servers()
        error = ""
    except MCPConfigurationError as exception:
        servers = []
        error = str(exception)
    try:
        import mcp  # noqa: F401
    except ImportError:
        sdk_available = False
    else:
        sdk_available = sys.version_info >= (3, 10)
    return {
        "config_path": str(config_path()),
        "configured_servers": [server.name for server in servers],
        "sdk_available": sdk_available,
        "error": error,
    }


def discover_tools() -> tuple[list[dict[str, Any]], dict[str, MCPTool], list[str]]:
    try:
        servers = load_servers()
    except MCPConfigurationError as error:
        return [], {}, [str(error)]
    if not servers:
        return [], {}, []
    if sys.version_info < (3, 10):
        return [], {}, [
            "MCP servers are configured, but the official MCP SDK requires Python 3.10 or newer."
        ]
    try:
        import anyio
        from mcp import Client, StdioServerParameters
    except ImportError as error:
        return [], {}, [
            f"MCP servers are configured, but the MCP SDK is unavailable: {error}"
        ]

    schemas = []
    tools_by_name: dict[str, MCPTool] = {}
    warnings = []
    for server in servers:
        params = StdioServerParameters(
            command=server.command,
            args=list(server.args),
            env=server.env or None,
            cwd=server.cwd,
        )

        async def list_server_tools():
            with anyio.fail_after(TOOL_TIMEOUT_SECONDS):
                async with Client(params) as client:
                    result = await client.list_tools()
                    return result.tools

        try:
            discovered = anyio.run(list_server_tools)
        except Exception as error:
            warnings.append(
                f"Could not connect to MCP server {server.name!r}: {error}"
            )
            continue
        for discovered_tool in discovered:
            if len(schemas) >= MAX_TOOLS:
                warnings.append(
                    f"MCP tool discovery is limited to {MAX_TOOLS} tools; additional tools were omitted."
                )
                break
            try:
                tool = _tool_schema(server, discovered_tool)
            except MCPToolError as error:
                warnings.append(str(error))
                continue
            if tool.exposed_name in tools_by_name:
                warnings.append(
                    f"Skipped MCP tool {server.name}.{tool.name}: its exposed name collides with another tool."
                )
                continue
            tools_by_name[tool.exposed_name] = tool
            schemas.append(ollama_schema(tool))
    return schemas, tools_by_name, warnings


def _render_tool_result(result: Any) -> str:
    result_data = _model_dict(result)
    contents = result_data.get("content", [])
    text_parts = [
        block["text"]
        for block in map(_model_dict, contents if isinstance(contents, list) else [])
        if isinstance(block.get("text"), str)
    ]
    structured = result_data.get("structuredContent")
    if text_parts:
        rendered = "\n".join(text_parts)
    elif structured is not None:
        rendered = json.dumps(structured, ensure_ascii=False, indent=2)
    else:
        rendered = "The MCP tool returned no text or structured content."
    if result_data.get("isError"):
        raise MCPToolError(rendered[:MAX_TOOL_OUTPUT_CHARS])
    if len(rendered) > MAX_TOOL_OUTPUT_CHARS:
        rendered = rendered[:MAX_TOOL_OUTPUT_CHARS] + "\n… output truncated"
    return rendered


def call_tool(tool: MCPTool, arguments: dict[str, Any]) -> str:
    if not isinstance(arguments, dict):
        raise MCPToolError("MCP tool arguments must be a JSON object")
    try:
        import anyio
        from mcp import Client, StdioServerParameters
    except ImportError as error:
        raise MCPToolError(f"The MCP SDK is unavailable: {error}") from error
    params = StdioServerParameters(
        command=tool.server.command,
        args=list(tool.server.args),
        env=tool.server.env or None,
        cwd=tool.server.cwd,
    )

    async def invoke():
        with anyio.fail_after(TOOL_TIMEOUT_SECONDS):
            async with Client(params) as client:
                current_tools = await client.list_tools()
                if not any(
                    getattr(current, "name", None) == tool.name
                    for current in current_tools.tools
                ):
                    raise MCPToolError(
                        f"MCP server {tool.server.name!r} no longer provides {tool.name!r}"
                    )
                result = await client.call_tool(tool.name, arguments)
                return _render_tool_result(result)

    try:
        return anyio.run(invoke)
    except MCPToolError:
        raise
    except Exception as error:
        raise MCPToolError(
            f"MCP server {tool.server.name!r} failed while running {tool.name!r}: {error}"
        ) from error
