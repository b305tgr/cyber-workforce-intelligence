import unittest
import os
import tempfile
import string
import subprocess
from unittest.mock import Mock, patch

try:
    from ._test_support import ensure_ollama_importable
except ImportError:
    from _test_support import ensure_ollama_importable

ensure_ollama_importable()

import tools
import agent


class WebToolTests(unittest.TestCase):
    def test_page_parser_extracts_text_and_ignores_scripts(self):
        title, text, links = tools._parse_web_page(
            '<html><title>Docs</title><script>ignore this</script>'
            '<body><h1>Hello</h1><a href="/guide">Guide</a></body></html>',
            "text/html; charset=utf-8",
        )
        self.assertEqual(title, "Docs")
        self.assertIn("Hello", text)
        self.assertNotIn("ignore this", text)
        self.assertEqual(links[0]["href"], "/guide")

    def test_search_parser_finds_results_and_snippets(self):
        title, text, links = tools._parse_web_page(
            '<a class="result__a" href="https://example.com/docs">Docs</a>'
            '<a class="result__snippet">Useful reference</a>',
            "text/html",
        )
        results = [link for link in links if "result__a" in link["class"]]
        snippets = [link for link in links if "result__snippet" in link["class"]]
        self.assertEqual(" ".join(results[0]["text"]), "Docs")
        self.assertEqual(" ".join(snippets[0]["text"]), "Useful reference")

    def test_search_parser_extracts_text_snippet_elements(self):
        _, _, links = tools._parse_web_page(
            '<a class="result__a" href="https://example.com/docs">Docs</a>'
            '<p class="b_lineclamp2">A useful preview for the result.</p>',
            "text/html",
        )
        snippets = [link for link in links if "result__snippet" in link["class"]]
        self.assertEqual(len(snippets), 1)
        self.assertEqual(" ".join(snippets[0]["text"]), "A useful preview for the result.")

    @patch("tools._request_public_page")
    def test_web_search_requires_approval_and_formats_results(self, request_page):
        request_page.return_value = (
            '<a href="https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9kb2Nz">'
            'Docs</a>',
            "text/html",
            "https://www.bing.com/search?q=Docs",
        )
        approvals = []
        result = tools.web_search(
            "Python documentation",
            confirm_fn=lambda action, target, preview: approvals.append(
                (action, target, preview)
            ) or True,
        )
        self.assertEqual(approvals[0][0:2], ("search the public web", "Python documentation"))
        self.assertIn("https://example.com/docs", result)
        self.assertTrue(request_page.call_args.args[0].startswith("https://www.bing.com/search?"))
        request_page.assert_called_once()

    @patch("tools._request_public_page")
    def test_web_search_includes_result_preview(self, request_page):
        request_page.return_value = (
            '<a class="result__a" href="https://example.com/docs">Docs</a>'
            '<p class="b_lineclamp2">A useful preview for the result.</p>',
            "text/html",
            "https://www.bing.com/search?q=Docs",
        )
        result = tools.web_search("Docs", confirm_fn=lambda *_: True)
        self.assertIn("Docs", result)
        self.assertIn("https://example.com/docs", result)
        self.assertIn("A useful preview for the result.", result)

    @patch("tools._request_public_page")
    def test_denied_search_does_not_make_request(self, request_page):
        result = tools.web_search("public query", confirm_fn=lambda *_: False)
        self.assertTrue(result.startswith(tools.CANCELLED_PREFIX))
        request_page.assert_not_called()

    @patch("tools.socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("93.184.216.34", 443))
    ])
    @patch("tools._request_public_page")
    def test_web_fetch_requires_approval_and_extracts_page(self, request_page, resolve_host):
        request_page.return_value = (
            "<title>Reference</title><p>Readable content</p>",
            "text/html",
            "https://example.com/docs",
        )
        approvals = []
        result = tools.web_fetch(
            "https://example.com/docs",
            confirm_fn=lambda action, target, preview: approvals.append(
                (action, target, preview)
            ) or True,
        )
        self.assertEqual(approvals[0][0:2], ("fetch public webpage", "https://example.com/docs"))
        self.assertIn("Title: Reference", result)
        self.assertIn("Readable content", result)
        request_page.assert_called_once()
        resolve_host.assert_called_once()

    def test_blocks_loopback_and_nonstandard_ports(self):
        with self.assertRaises(tools.ToolError):
            tools._validated_web_target("http://127.0.0.1/")
        with self.assertRaises(tools.ToolError):
            tools._validated_web_target("https://example.com:8443/")

    def test_validate_website_reports_and_clears_broken_local_references(self):
        with tempfile.TemporaryDirectory() as root:
            index = os.path.join(root, "index.html")
            with open(index, "w", encoding="utf-8") as page:
                page.write(
                    '<html><head><link rel="stylesheet" href="styles.css"></head>'
                    '<body><a href="#">Home</a><a href="#menu">Menu</a>'
                    '<script src="script.js"></script><img src="hero.jpg">'
                    '<!-- Menu content will go here --></body></html>'
                )

            issues = tools.validate_website(root)
            self.assertIn("index.html is missing a mobile viewport meta tag", issues)
            self.assertIn("index.html is missing a semantic <main> content region", issues)
            self.assertIn("index.html is missing semantic <nav> site navigation", issues)
            self.assertIn("index.html is missing its primary <h1> heading", issues)
            self.assertIn("index.html has no local or inline CSS for a responsive layout", issues)
            self.assertIn("website contains placeholder or unfinished content", issues)
            self.assertTrue(any("placeholder link" in issue for issue in issues))
            self.assertTrue(any("broken in-page link '#menu'" in issue for issue in issues))
            self.assertTrue(any("missing local asset 'styles.css'" in issue for issue in issues))
            self.assertTrue(any("missing local asset 'script.js'" in issue for issue in issues))
            self.assertTrue(any("missing local asset 'hero.jpg'" in issue for issue in issues))

            with open(index, "w", encoding="utf-8") as page:
                page.write(
                    '<html><head><meta name="viewport" content="width=device-width">'
                    '<link rel="stylesheet" href="styles.css"></head><body>'
                    '<nav><a href="#menu">Menu</a></nav><main><section id="menu">'
                    '<h1>Coffee</h1></section></main><script src="script.js"></script>'
                    '<img src="hero.jpg"></body></html>'
                )
            for name, content in (
                (
                    "styles.css",
                    "body { background: url('hero.jpg'); } "
                    "@media (max-width: 600px) { body { margin: 0; } }",
                ),
                ("script.js", "document.documentElement.dataset.ready = 'true';"),
                ("hero.jpg", "image"),
            ):
                with open(os.path.join(root, name), "w", encoding="utf-8") as asset:
                    asset.write(content)

            self.assertEqual(tools.validate_website(root), [])

    @patch("tools.socket.getaddrinfo")
    def test_blocks_public_host_resolving_to_private_ip(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("192.168.1.10", 443))]
        with self.assertRaises(tools.ToolError):
            tools._validated_web_target("https://internal.example/")

    @patch("tools.socket.getaddrinfo")
    def test_denied_fetch_does_not_resolve_or_contact_host(self, getaddrinfo):
        result = tools.web_fetch("https://example.com/", confirm_fn=lambda *_: False)
        self.assertTrue(result.startswith(tools.CANCELLED_PREFIX))
        getaddrinfo.assert_not_called()

    def test_web_tools_are_registered_for_agent_and_model(self):
        schema_names = {
            schema["function"]["name"] for schema in tools.TOOL_SCHEMAS
        }
        self.assertTrue({"web_search", "web_fetch"} <= schema_names)
        self.assertTrue({"web_search", "web_fetch"} <= set(agent.TOOL_DISPATCH))

    def test_bing_decoder_rejects_internal_search_navigation(self):
        self.assertIsNone(
            tools._decode_bing_redirect(
                "https://www.bing.com/ck/a?u=a1L3NlYXJjaA"
            )
        )

    def test_write_file_serializes_json_values(self):
        with tempfile.TemporaryDirectory() as root:
            tools.write_file("package.json", {"scripts": {"test": "node --test"}}, root)
            with open(os.path.join(root, "package.json"), encoding="utf-8") as file:
                self.assertEqual(
                    file.read(),
                    '{\n  "scripts": {\n    "test": "node --test"\n  }\n}',
                )

    def test_read_file_accepts_numeric_string_line_ranges(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "sample.txt"), "w", encoding="utf-8") as file:
                file.write("one\ntwo\nthree\n")
            result = tools.read_file("sample.txt", root, "2", "2")
            self.assertTrue(result.startswith("    2 | two"))
            self.assertIn("request start_line=3", result)

    def test_read_file_caps_default_output_and_suggests_continuation(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "large.txt"), "w", encoding="utf-8") as file:
                file.write("line\n" * (tools.MAX_READ_LINES + 1))
            result = tools.read_file("large.txt", root)
        self.assertIn(f"request start_line={tools.MAX_READ_LINES + 1}", result)
        self.assertEqual(result.count(" | line"), tools.MAX_READ_LINES)

    def test_directory_listing_pages_entries(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("a.txt", "b.txt", "c.txt"):
                with open(os.path.join(root, name), "w", encoding="utf-8") as file:
                    file.write(name)
            page = tools.list_dir(".", root, 1, 1)
            self.assertIn("b.txt", page)
            self.assertIn("Showing entries 2-2 of 3", page)
            self.assertIn("offset=2", page)

    def test_search_files_rejects_empty_query(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(tools.ToolError, "query must be non-empty"):
                tools.search_files("  ", ".", root)

    def test_git_diff_uses_literal_argument_array(self):
        completed = subprocess.CompletedProcess(["git"], 0, b"", b"")
        with tempfile.TemporaryDirectory() as root, patch(
            "tools.subprocess.run", return_value=completed
        ) as run:
            tools.git_diff(root, "name; calc.exe")
        self.assertEqual(run.call_args.args[0][0:3], ["git", "--literal-pathspecs", "diff"])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.args[0][-1], "name; calc.exe")

    def test_edit_file_refuses_non_utf8_without_modifying_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "binary.txt")
            original = b"\xff\xfe"
            with open(path, "wb") as file:
                file.write(original)
            with self.assertRaises(tools.ToolError):
                tools.edit_file("binary.txt", "x", "y", root)
            with open(path, "rb") as file:
                self.assertEqual(file.read(), original)

    def test_edit_file_matches_and_preserves_crlf_line_endings(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "windows.txt")
            with open(path, "wb") as file:
                file.write(b"one\r\ntwo\r\nthree\r\n")
            tools.edit_file("windows.txt", "two\n", "TWO\n", root)
            with open(path, "rb") as file:
                self.assertEqual(file.read(), b"one\r\nTWO\r\nthree\r\n")

    def test_safe_path_refuses_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            target = os.path.join(outside, "secret.txt")
            link = os.path.join(root, "external.txt")
            with open(target, "w", encoding="utf-8") as file:
                file.write("outside")
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable")
            with self.assertRaises(tools.ToolError):
                tools.read_file("external.txt", root)

    @unittest.skipUnless(os.name == "nt", "cross-drive paths are Windows-only")
    def test_safe_path_handles_cross_drive_paths(self):
        with tempfile.TemporaryDirectory() as root:
            root_drive = os.path.splitdrive(root)[0].upper()
            other_drive = next(f"{drive}:\\" for drive in string.ascii_uppercase
                               if f"{drive}:" != root_drive)
            with self.assertRaises(tools.ToolError):
                tools.read_file(other_drive + "outside.txt", root)

    def test_search_invalid_regex_falls_back_to_literal_and_visits_dot_folders(self):
        with tempfile.TemporaryDirectory() as root:
            hidden = os.path.join(root, ".config")
            os.makedirs(hidden)
            with open(os.path.join(hidden, "settings.txt"), "w", encoding="utf-8") as file:
                file.write("literal foo( expression\n")
            results = tools.search_files("foo(", ".", root)
            self.assertTrue(results.startswith(os.path.join(".config", "settings.txt")))
        self.assertIn("literal foo(", results)

    def test_command_timeout_and_disconnect_terminate_process_tree(self):
        process = Mock()
        process.pid = 123
        process.returncode = -9
        process.communicate.side_effect = [
            subprocess.TimeoutExpired("command", 1),
            (b"", b""),
        ]
        process.stdout = None
        process.stderr = None
        with tempfile.TemporaryDirectory() as root, patch(
            "tools.subprocess.Popen", return_value=process
        ), patch("tools._terminate_process_tree") as terminate:
            result = tools.run_command(
                "long-build", root, yolo=True, should_continue=lambda: False
            )
        terminate.assert_called_once_with(process)
        self.assertIn("request was aborted", result)

    def test_known_destructive_windows_commands_are_blocked_even_in_yolo_mode(self):
        with tempfile.TemporaryDirectory() as root, patch("tools.subprocess.Popen") as popen:
            with self.assertRaises(tools.ToolError):
                tools.run_command(
                    "Remove-Item -Recurse -Force C:\\important",
                    root,
                    yolo=True,
                )
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
