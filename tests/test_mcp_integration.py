import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from ._test_support import ensure_ollama_importable
except ImportError:
    from _test_support import ensure_ollama_importable

ensure_ollama_importable()

import agent
import mcp_integration


class MCPIntegrationTests(unittest.TestCase):
    def test_stdio_server_tools_are_discovered_and_called_with_official_sdk(self):
        server_script = Path(__file__).with_name("mcp_echo_server.py")
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "mcp_servers.json")
            config.write_text(json.dumps({
                "servers": [{
                    "name": "echo",
                    "command": sys.executable,
                    "args": [str(server_script)],
                    "cwd": str(server_script.parent.parent),
                }],
            }), encoding="utf-8")
            with patch.dict(os.environ, {mcp_integration.CONFIG_ENV: str(config)}):
                schemas, tools_by_name, warnings = mcp_integration.discover_tools()
                self.assertEqual(warnings, [])
                self.assertEqual(len(schemas), 1)
                schema = schemas[0]["function"]
                self.assertEqual(schema["name"], "mcp__echo__echo_text")
                self.assertIn("requires explicit user approval", schema["description"])
                tool = tools_by_name[schema["name"]]
                self.assertIsNone(
                    mcp_integration.validate_tool_arguments(tool, {"text": "hello"})
                )
                self.assertIn(
                    "missing required argument",
                    mcp_integration.validate_tool_arguments(tool, {}),
                )
                self.assertIn(
                    "64 KiB",
                    mcp_integration.validate_tool_arguments(
                        tool, {"text": "x" * mcp_integration.MAX_TOOL_ARGUMENTS_BYTES}
                    ),
                )
                self.assertEqual(
                    mcp_integration.call_tool(tool, {"text": "hello"}),
                    "echo: hello",
                )

    def test_mcp_calls_use_the_existing_approval_callback(self):
        tool = mcp_integration.MCPTool(
            server=mcp_integration.MCPServer("sample", "python", (), {}, None),
            name="lookup",
            exposed_name="mcp__sample__lookup",
            description="Look up a value",
            schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
        with patch(
            "agent.mcp_integration.call_tool", return_value="found"
        ) as call_tool:
            denied = agent._run_tool(
                tool.exposed_name,
                {"query": "private"},
                ".",
                Mock(return_value=False),
                False,
                mcp_tools={tool.exposed_name: tool},
            )
            self.assertTrue(denied.startswith("CANCELLED_BY_USER"))
            call_tool.assert_not_called()

            approval = Mock(return_value=True)
            result = agent._run_tool(
                tool.exposed_name,
                {"query": "public"},
                ".",
                approval,
                False,
                mcp_tools={tool.exposed_name: tool},
            )
            self.assertEqual(result, "found")
            approval.assert_called_once()
            call_tool.assert_called_once_with(tool, {"query": "public"})

    def test_mcp_configuration_rejects_extra_fields_and_shell_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "mcp_servers.json")
            config.write_text(json.dumps({
                "servers": [{
                    "name": "unsafe",
                    "command": "python && echo unsafe",
                    "args": [],
                    "shell": True,
                }],
            }), encoding="utf-8")
            with self.assertRaises(mcp_integration.MCPConfigurationError):
                mcp_integration.load_servers(config)

    def test_missing_mcp_configuration_means_no_external_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_config = Path(directory, "missing.json")
            with patch(
                "mcp_integration.config_path", return_value=missing_config
            ):
                self.assertEqual(mcp_integration.load_servers(), [])
                self.assertEqual(mcp_integration.discover_tools(), ([], {}, []))


if __name__ == "__main__":
    unittest.main()
