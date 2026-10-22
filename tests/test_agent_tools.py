import json
import tempfile
import threading
import unittest
import zipfile
from unittest.mock import Mock, patch
from pathlib import Path

try:
    from ._test_support import ensure_ollama_importable
except ImportError:
    from _test_support import ensure_ollama_importable

ensure_ollama_importable()

import agent
import tools


class AgentFileToolTests(unittest.TestCase):
    def test_full_stack_completion_requires_named_files_backend_tests_and_readme(self):
        self.assertTrue(agent._looks_like_website_request(
            "Build a full-stack Python reservation app with an HTML frontend and index.html."
        ))
        self.assertFalse(agent._looks_like_website_request(
            "Build a full-stack Python command-line app."
        ))
        prompt = (
            "Build a full-stack Python reservation website. Create server.py, "
            "index.html, app.js, README.md, and unittest tests."
        )
        with tempfile.TemporaryDirectory() as root:
            issues = agent._website_project_completion_issues(root, prompt)
            self.assertIn("missing requested project file 'server.py'", issues)
            self.assertIn("missing Python backend implementation", issues)
            self.assertIn("missing requested automated test file", issues)
            self.assertIn(
                "missing requested README with setup or run instructions", issues
            )

            for relative_path in (
                "server.py",
                "index.html",
                "app.js",
                "README.md",
                "tests/test_server.py",
            ):
                path = Path(root, relative_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("complete", encoding="utf-8")

            self.assertEqual(
                agent._website_project_completion_issues(root, prompt), []
            )

    def test_website_validator_allows_a_real_placeholder_attribute(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "index.html").write_text(
                """<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Garden</title><style>@media (max-width: 700px) { body { padding: 1rem; } }</style></head>
<body><header><nav><a href="#events">Events</a></nav></header>
<main><h1>Garden events</h1><section id="events"><input placeholder="Search events"></section></main>
<footer>Visit the garden</footer></body></html>""",
                encoding="utf-8",
            )
            self.assertEqual(tools.validate_website(root), [])

    def test_website_validator_rejects_empty_referenced_assets(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "styles.css").write_text("", encoding="utf-8")
            Path(root, "script.js").write_text("  ", encoding="utf-8")
            Path(root, "index.html").write_text(
                """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="styles.css"><script src="script.js"></script>
</head><body><header><nav><a href="#home">Home</a></nav></header>
<main id="home"><h1>Garden</h1></main><footer>Visit</footer></body></html>""",
                encoding="utf-8",
            )
            issues = tools.validate_website(root)
            self.assertIn("local CSS asset 'styles.css' is empty", issues)
            self.assertIn("local JavaScript asset 'script.js' is empty", issues)

    def test_website_validator_rejects_malformed_tag_nesting(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "index.html").write_text(
                """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
</head><body><nav><a href="#home">Home</a></nav>
<main id="home"><h1>Garden</h1></div></body></html>""",
                encoding="utf-8",
            )
            issues = tools.validate_website(root)
            self.assertTrue(any("malformed HTML" in issue for issue in issues))
            self.assertTrue(any("unmatched closing tag </div>" in issue for issue in issues))

    def test_safe_website_markup_repair_closes_or_removes_invalid_tags(self):
        with tempfile.TemporaryDirectory() as root:
            page = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
</head><body><nav><a href="#home">Home</a></nav>
<main id="home"><h1>Garden</h1></div></body></html>"""
            Path(root, "index.html").write_text(page, encoding="utf-8")

            issues = tools.validate_website(root)
            repaired = agent._automatic_website_markup_repair(root, issues)

            self.assertIsNotNone(repaired)
            Path(root, "index.html").write_text(repaired, encoding="utf-8")
            self.assertEqual(tools.validate_website(root), [])

    def test_safe_website_markup_repair_replaces_missing_product_image(self):
        with tempfile.TemporaryDirectory() as root:
            page = (
                '<!doctype html><html><head><meta name="viewport" '
                'content="width=device-width, initial-scale=1"><title>Shop</title>'
                '<style>@media(max-width:700px){main{padding:1rem}}</style>'
                '</head><body><nav><a href="#home">Home</a></nav><main id="home">'
                '<h1>Shop</h1><img '
                'src="epson_printer.jpg" alt="Epson EcoTank printer"></main></body></html>'
            )
            Path(root, "index.html").write_text(page, encoding="utf-8")
            issues = tools.validate_website(root)
            self.assertIn(
                "missing local asset 'epson_printer.jpg' referenced by index.html",
                issues,
            )

            repaired = agent._automatic_website_markup_repair(root, issues)

            self.assertIsNotNone(repaired)
            self.assertNotIn('src="epson_printer.jpg"', repaired)
            self.assertIn('aria-label="Epson EcoTank printer illustration"', repaired)
            Path(root, "index.html").write_text(repaired, encoding="utf-8")
            self.assertEqual(tools.validate_website(root), [])

    def test_safe_website_markup_repair_fixes_viewport_and_escaped_asset_path(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "js").mkdir()
            Path(root, "js", "script.js").write_text(
                'document.title = "Printer shop";', encoding="utf-8"
            )
            page = (
                "<!doctype html><html><head><title>Printer shop</title>"
                '<script src=\\"js/script.js\\"></script>'
                "<style>@media(max-width:700px){main{padding:1rem}}</style>"
                "</head><body><nav><a href=\"#home\">Home</a></nav>"
                '<main id="home"><h1>Printer shop</h1></main></body></html>'
            )
            Path(root, "index.html").write_text(page, encoding="utf-8")
            issues = tools.validate_website(root)
            self.assertIn(
                "index.html is missing a mobile viewport meta tag",
                issues,
            )
            self.assertTrue(
                any("missing local asset" in issue for issue in issues)
            )

            repaired = agent._automatic_website_markup_repair(root, issues)

            self.assertIsNotNone(repaired)
            Path(root, "index.html").write_text(repaired, encoding="utf-8")
            self.assertIn('name="viewport"', repaired)
            self.assertIn('src="js/script.js"', repaired)
            self.assertEqual(tools.validate_website(root), [])

    def test_package_project_preserves_tree_and_requires_approval(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "site", "assets").mkdir(parents=True)
            Path(root, "site", "index.html").write_text("<h1>Ready</h1>", encoding="utf-8")
            Path(root, "site", "assets", "app.js").write_text("const ready = true;", encoding="utf-8")
            confirm = Mock(return_value=True)
            result = tools.package_project(
                ["site/index.html", "site/assets/app.js"],
                "downloads/site.zip",
                root,
                confirm_fn=confirm,
            )
            self.assertEqual(result, "Project archive ready: downloads/site.zip")
            confirm.assert_called_once()
            with zipfile.ZipFile(Path(root, "downloads", "site.zip")) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"site/index.html", "site/assets/app.js"},
                )
                self.assertEqual(archive.read("site/index.html"), b"<h1>Ready</h1>")

    def test_package_project_refuses_path_escape_and_missing_files(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            Path(outside, "secret.txt").write_text("not for archive", encoding="utf-8")
            Path(root, "index.html").write_text("<h1>Site</h1>", encoding="utf-8")
            Path(root, "site.zip").write_bytes(b"existing archive")
            for files in (
                ["../secret.txt"],
                ["missing.txt"],
                ["index.html", "index.html"],
                ["site.zip"],
            ):
                with self.subTest(files=files), self.assertRaises(tools.ToolError):
                    tools.package_project(files, "site.zip", root)
            self.assertEqual(Path(root, "site.zip").read_bytes(), b"existing archive")

    def test_package_project_does_not_create_archive_when_approval_is_denied(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "index.html").write_text("<h1>Site</h1>", encoding="utf-8")
            result = tools.package_project(
                ["index.html"], "site.zip", root, confirm_fn=Mock(return_value=False)
            )
            self.assertTrue(result.startswith(tools.CANCELLED_PREFIX))
            self.assertFalse(Path(root, "site.zip").exists())

    def test_qwen25_text_tool_call_recovery_requires_exact_valid_payload(self):
        call = {
            "name": "write_file",
            "arguments": {"path": "index.html", "content": "<h1>Coffee</h1>"},
        }
        self.assertEqual(
            agent._recover_qwen25_text_tool_call(
                "huihui_ai/qwen2.5-coder-abliterate:7b",
                json.dumps(call),
            ),
            {"function": {"name": "write_file", "arguments": call["arguments"]}},
        )
        self.assertEqual(
            agent._recover_qwen25_text_tool_call(
                "midnight-signal:latest",
                f"```json\n{json.dumps(call)}\n```",
            ),
            {"function": {"name": "write_file", "arguments": call["arguments"]}},
        )
        for model, content in (
            ("qwen3:14b", json.dumps(call)),
            ("qwen2.5-coder:7b", f"Here is an example: {json.dumps(call)}"),
            ("qwen2.5-coder:7b", json.dumps({"name": "unknown", "arguments": {}})),
            ("qwen2.5-coder:7b", json.dumps({
                "name": "write_file",
                "arguments": {"path": "index.html", "content": "ok", "outside": True},
            })),
        ):
            with self.subTest(model=model, content=content[:40]):
                self.assertIsNone(agent._recover_qwen25_text_tool_call(model, content))

    def test_custom_homepage_tool_recovers_single_surplus_json_brace(self):
        call = {
            "name": "create_website_entry",
            "arguments": {
                "content": "<!doctype html><html><head></head><body></body></html>",
            },
        }
        encoded = json.dumps(call)
        self.assertEqual(
            agent._recover_qwen25_text_tool_call(
                "midnight-signal:latest",
                f"```json\n{encoded}}}\n```",
                [agent._QWEN25_WEBSITE_ENTRY_TOOL],
            ),
            {"function": {"name": call["name"], "arguments": call["arguments"]}},
        )
        self.assertIsNone(agent._recover_qwen25_text_tool_call(
            "midnight-signal:latest",
            f"{encoded}}}ignore this",
            [agent._QWEN25_WEBSITE_ENTRY_TOOL],
        ))

    def test_custom_website_repair_tool_recovers_single_surplus_json_brace(self):
        content = (
            "<!doctype html><html><head><meta name='viewport' "
            "content='width=device-width, initial-scale=1'><style>"
            "@media (max-width: 700px) { body { padding: 1rem; } }"
            "</style></head><body><nav><a href='#home'>Home</a></nav>"
            "<main id='home'><h1>Night sky</h1></main></body></html>"
        )
        call = {
            "name": "repair_website_entry",
            "arguments": {"content": content},
        }
        recovered = agent._recover_qwen25_text_tool_call(
            "midnight-signal:latest",
            f"```json\n{json.dumps(call)}}}\n```",
            [agent._QWEN25_WEBSITE_REPAIR_TOOL],
        )
        self.assertEqual(
            recovered,
            {"function": {"name": call["name"], "arguments": call["arguments"]}},
        )

    def test_website_asset_tool_only_writes_supported_relative_text_files(self):
        with tempfile.TemporaryDirectory() as root:
            confirm = Mock(return_value=True)
            result = agent._run_tool(
                "create_website_asset",
                {"path": "assets/site.css", "content": "body { color: navy; }"},
                root,
                confirm,
                False,
            )
            self.assertIn("wrote 21 bytes", result)
            self.assertEqual(
                Path(root, "assets", "site.css").read_text(encoding="utf-8"),
                "body { color: navy; }",
            )
            for path in ("../escape.css", "index.html", "assets/image.png"):
                with self.subTest(path=path):
                    result = agent._run_tool(
                        "create_website_asset",
                        {"path": path, "content": "not allowed"},
                        root,
                        confirm,
                        False,
                    )
                    self.assertTrue(result.startswith("error:"))
            backend_result = agent._run_tool(
                "create_website_asset",
                {"path": "server.py", "content": "from http.server import HTTPServer"},
                root,
                confirm,
                False,
            )
            self.assertIn("wrote ", backend_result)
            self.assertTrue(Path(root, "server.py").is_file())

    def test_website_requested_search_and_favorite_checks_require_working_handlers(self):
        entry_prompt = agent._website_entry_system_prompt(
            "Build event search and favorites."
        )
        self.assertIn("multi-page, or full-stack product", entry_prompt)
        self.assertIn("Never fake a backend feature", entry_prompt)
        self.assertIn("visible search input", entry_prompt)
        self.assertIn('class="favorite-button"', entry_prompt)
        self.assertIn('aria-pressed="false"', entry_prompt)
        self.assertNotIn(
            "visible search input",
            agent._website_entry_system_prompt("Build a static brochure."),
        )
        with tempfile.TemporaryDirectory() as root:
            Path(root, "index.html").write_text(
                """<!doctype html><html><body>
<input type="search" id="event-search">
<button class="favorite-button" data-favorite="false">Favorite</button>
<main><h1>Events</h1></main></body></html>""",
                encoding="utf-8",
            )
            Path(root, "assets").mkdir()
            Path(root, "assets", "site.js").write_text(
                """const search = document.querySelector('#event-search');
search.addEventListener('input', () => {
  document.querySelectorAll('.event').forEach(item => {
    item.hidden = !item.textContent.toLowerCase().includes(search.value.toLowerCase());
  });
});
document.querySelector('.favorite-button').addEventListener('click', event => {
  event.currentTarget.dataset.favorite = event.currentTarget.dataset.favorite !== 'true';
});""",
                encoding="utf-8",
            )
            self.assertEqual(
                agent._website_requested_interaction_issues(
                    root,
                    "Add event search and favorite buttons.",
                    {"assets/site.js"},
                ),
                [],
            )
            page = Path(root, "index.html")
            page.write_text(
                page.read_text(encoding="utf-8").replace(
                    '<button class="favorite-button" data-favorite="false">Favorite</button>',
                    '<div class="favorite-button">Favorite</div>',
                ),
                encoding="utf-8",
            )
            div_issues = agent._website_requested_interaction_issues(
                root,
                "Add event search and favorite buttons.",
                {"assets/site.js"},
            )
            self.assertEqual(len(div_issues), 1)
            self.assertIn("favorite-toggle", div_issues[0])
            Path(root, "assets", "site.js").write_text("console.log('ready');", encoding="utf-8")
            issues = agent._website_requested_interaction_issues(
                root,
                "Add event search and favorite buttons.",
                {"assets/site.js"},
            )
            self.assertEqual(len(issues), 2)
            self.assertTrue(any("search/filter" in issue for issue in issues))
            self.assertTrue(any("favorite-toggle" in issue for issue in issues))

    def test_requested_interactions_block_zip_until_repaired(self):
        def structured_call(name, arguments):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": arguments}
            }]}}

        incomplete_page = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
<title>Events</title></head><body><nav><a href="#events">Events</a></nav>
<main id="events"><h1>Community events</h1><p>Upcoming events.</p></main>
<footer>Community events</footer></body></html>"""
        repaired_page = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
<title>Events</title></head><body><nav><a href="#events">Events</a></nav>
<main id="events"><h1>Community events</h1>
<label>Search events <input type="search" id="event-search"></label>
<ul><li class="event">Meteor watch <button class="favorite-button"
data-favorite="false" aria-pressed="false">Favorite</button></li></ul></main>
<footer>Community events</footer><script>
const search = document.querySelector('#event-search');
search.addEventListener('input', () => document.querySelectorAll('.event').forEach(item => {
  item.hidden = !item.textContent.toLowerCase().includes(search.value.toLowerCase());
}));
document.querySelector('.favorite-button').addEventListener('click', event => {
  const button = event.currentTarget;
  button.setAttribute('aria-pressed', button.getAttribute('aria-pressed') !== 'true');
});
</script></body></html>"""
        responses = [
            iter([structured_call("write_file", {
                "path": "index.html", "content": incomplete_page,
            })]),
            iter([{"message": {"content": "The event page is ready."}}]),
            iter([structured_call("package_project", {
                "files": ["index.html"],
                "path": "downloads/events.zip",
            })]),
            iter([structured_call("write_file", {
                "path": "index.html", "content": repaired_page,
            })]),
            iter([{"message": {"content": "The requested interactions are complete."}}]),
            iter([structured_call("package_project", {
                "files": ["index.html"],
                "path": "downloads/events.zip",
            })]),
            iter([{"message": {"content": "The working site and ZIP are ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Create an events website with search and favorite buttons, "
                        "then create a ZIP archive."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            archive_path = Path(root, "downloads", "events.zip")
            self.assertTrue(
                archive_path.is_file(),
                [event.data for event in events if event.kind in {"error", "tool_result"}],
            )
            self.assertEqual(tools.validate_website(root), [])
            self.assertEqual(
                agent._website_requested_interaction_issues(
                    root,
                    "Build an events website with search and favorite buttons.",
                    {"index.html"},
                ),
                [],
            )
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["index.html"])
                self.assertIsNone(archive.testzip())

        package_results = [
            event.data["result"]
            for event in events
            if event.kind == "tool_result"
            and event.data.get("name") == "package_project"
        ]
        self.assertEqual(len(package_results), 2)
        self.assertIn("refusing to package an invalid website", package_results[0])
        self.assertIn("Project archive ready:", package_results[1])

    def test_models_recover_complete_html_from_labeled_and_unlabeled_fences(self):
        html = (
            "<!doctype html><html><head><title>Cafe</title></head>"
            "<body><main><h1>Cafe</h1></main></body></html>"
        )
        prompt = "Build a coffee shop website."
        expected = {"function": {"name": "write_file", "arguments": {
            "path": "index.html", "content": html,
        }}}
        for model in (
            "huihui_ai/qwen2.5-coder-abliterate:7b",
            "midnight-signal:latest",
            "qwen3:14b",
        ):
            for fence in (
                "```html\n{html}\n```",
                "```htmlCopy\n{html}\n```",
                "```\n{html}\n```",
            ):
                with self.subTest(model=model, fence=fence[:8]):
                    response = f"Here is the site:\n{fence.format(html=html)}"
                    self.assertEqual(
                        agent._recover_website_html(response, prompt),
                        expected,
                    )
        self.assertEqual(
            agent._recover_website_html(
                html,
                "Build a React website.",
            ),
            expected,
        )
        self.assertIsNone(agent._recover_website_html(
            f"```html\n{html}\n```",
            "Explain what this website's HTML does.",
        ))
        self.assertEqual(
            agent._recover_website_html(
                f"```html\n{html}\n```",
                prompt,
                [agent._QWEN25_WEBSITE_REPAIR_TOOL],
                repair_pending=True,
            ),
            {"function": {"name": "repair_website_entry", "arguments": {
                "content": html,
            }}},
        )

    def test_models_can_create_a_website_from_html_in_a_nonempty_workspace(self):
        website = (
            "<!doctype html><html><head><meta name='viewport' "
            "content='width=device-width, initial-scale=1'><title>Studio</title>"
            "<style>@media (max-width: 600px) { main { padding: 1rem; } }</style>"
            "</head><body><nav><a href='#home'>Home</a></nav>"
            "<main><h1>Studio</h1><section id='home'>Welcome.</section></main>"
            "</body></html>"
        )
        for model in (
            "huihui_ai/qwen2.5-coder-abliterate:7b",
            "midnight-signal:latest",
            "qwen3:14b",
        ):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as root:
                Path(root, "existing.txt").write_text("keep", encoding="utf-8")
                responses = [
                    iter([{"message": {
                        "content": (
                            "Here is your index.html file:\nhtmlCopy\n\n"
                            f"```\n{website}\n```"
                        ),
                    }}]),
                    iter([{"message": {"content": "The website is ready."}}]),
                ]
                with patch(
                    "agent._chat_stream", side_effect=responses
                ), patch("agent.tool_impl.validate_website", return_value=[]):
                    events = list(agent.run_agent(
                        model,
                        [
                            {"role": "system", "content": "system"},
                            {
                                "role": "user",
                                "content": (
                                    "Can u generate a self contained website "
                                    "for a printer sales for epson"
                                ),
                            },
                        ],
                        root,
                    ))
                output = Path(root, "index.html")
                self.assertTrue(output.is_file())
                self.assertIn("<h1>Studio</h1>", output.read_text(encoding="utf-8"))
                self.assertTrue(any(event.kind == "tool_result" for event in events))
                self.assertTrue(any(event.kind == "final" for event in events))
                self.assertFalse(any(
                    event.kind == "response_token"
                    and "<html" in event.data.get("text", "").lower()
                    for event in events
                ))

    def test_where_is_the_file_is_a_workspace_lookup_intent(self):
        self.assertTrue(agent._looks_like_tool_intent("Where is the file?"))
        self.assertFalse(agent._looks_like_workspace_change_request(
            "Where is the file?"
        ))

    def test_repeated_qwen_website_asset_writes_are_not_reapplied(self):
        page = (
            "<!doctype html><html><head><title>Studio</title></head>"
            "<body><main><h1>Studio</h1></main></body></html>"
        )
        asset_call = {
            "message": {"tool_calls": [{
                "function": {
                    "name": "create_website_asset",
                    "arguments": {
                        "path": "css/styles.css",
                        "content": "body { color: navy; }",
                    },
                }
            }]}
        }
        responses = [
            iter([{"message": {"tool_calls": [{
                "function": {
                    "name": "create_website_entry",
                    "arguments": {"content": page},
                }
            }]}}]),
            iter([asset_call]),
            iter([asset_call]),
            iter([{"message": {"content": "The website is ready."}}]),
        ]

        def write_file(name, args, root, *_):
            path = "index.html" if name == "create_website_entry" else args["path"]
            full_path = Path(root, path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(args["content"], encoding="utf-8")
            return f"wrote {path}"

        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ), patch("agent._run_tool", side_effect=write_file) as run_tool, patch(
            "agent.tool_impl.validate_website", return_value=[]
        ):
            events = list(agent.run_agent(
                "huihui_ai/qwen2.5-coder-abliterate:7b",
                [
                    {"role": "system", "content": "system"},
                    {
                        "role": "user",
                        "content": "Build a coffee shop website.",
                    },
                ],
                root,
            ))

        self.assertEqual(run_tool.call_count, 2)
        duplicate_result = next(
            event for event in events
            if event.kind == "tool_result"
            and "already written successfully" in event.data["result"]
        )
        self.assertIn("Do not repeat this call", duplicate_result.data["result"])
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_website_repair_refuses_to_replace_page_with_a_snippet(self):
        self.assertIn(
            "partial snippet",
            agent._website_index_write_error(
                "write_file",
                {"path": "index.html", "content": "<style>body { color: red; }</style>"},
                repair_pending=True,
            ),
        )
        self.assertEqual(
            agent._website_index_write_error(
                "write_file",
                {
                    "path": "index.html",
                    "content": "<html><head></head><body></body></html>",
                },
                repair_pending=True,
            ),
            "",
        )
        self.assertIn(
            "partial snippet",
            agent._website_index_write_error(
                "repair_website_entry",
                {"content": "<style>body { color: red; }</style>"},
                repair_pending=True,
            ),
        )

    def test_automatic_website_markup_repair_fixes_only_reported_issues(self):
        with tempfile.TemporaryDirectory() as root:
            page = """<!doctype html><html><head><meta name="viewport"
content="width=device-width, initial-scale=1"></head><body>
<nav><a href="#events">Events</a><a href="#downloads">Downloads</a></nav>
<main id="events"><h1>Night sky events</h1></main></body></html>"""
            Path(root, "index.html").write_text(page, encoding="utf-8")
            issues = tools.validate_website(root)
            repaired = agent._automatic_website_markup_repair(root, issues)
            self.assertIsNotNone(repaired)
            self.assertIn('href="#events"', repaired)
            self.assertIn("<a>Downloads</a>", repaired)
            self.assertIn("@media (max-width: 700px)", repaired)
            Path(root, "index.html").write_text(repaired, encoding="utf-8")
            self.assertEqual(tools.validate_website(root), [])

    def test_agent_applies_approved_safe_website_repair_when_model_fails(self):
        def structured_call(name, args):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": args}
            }]}}

        page = (
            "<!doctype html><html><head><meta name='viewport' "
            "content='width=device-width, initial-scale=1'></head><body>"
            "<nav><a href='#downloads'>Downloads</a></nav>"
            "<main id='events'><h1>Night sky events</h1></main>"
            "</body></html>"
        )
        responses = [
            iter([structured_call("create_website_entry", {"content": page})]),
            iter([{"message": {"content": "The site is ready."}}]),
            iter([{"message": {"content": "I will repair it now."}}]),
            iter([{"message": {"content": "Use this shell command: zip site.zip index.html"}}]),
            iter([{"message": {"content": "The site is now valid."}}]),
            iter([structured_call("package_project", {
                "files": ["index.html"],
                "path": "downloads/night-sky.zip",
            })]),
            iter([{"message": {"content": "The website ZIP is ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Build a responsive night-sky website and create a ZIP."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            self.assertEqual(tools.validate_website(root), [])
            with zipfile.ZipFile(Path(root, "downloads", "night-sky.zip")) as archive:
                self.assertEqual(archive.namelist(), ["index.html"])
                self.assertIsNone(archive.testzip())

        self.assertEqual(
            chat_stream.call_args_list[3].args[2][0]["function"]["name"],
            "repair_website_entry",
        )
        self.assertTrue(any(
            event.kind == "tool_call"
            and event.data.get("name") == "write_file"
            and "index.html" in event.data.get("args", {}).get("path", "")
            for event in events
        ))
        self.assertTrue(any(
            event.kind == "progress_note"
            and "Applied safe local repairs" in event.data["text"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_agent_packages_validated_site_when_model_misses_zip_call(self):
        page = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
<title>Night Sky</title></head><body><nav><a href="#events">Events</a></nav>
<main id="events"><h1>Night sky events</h1></main></body></html>"""
        responses = [
            iter([{"message": {"content": json.dumps({
                "name": "create_website_entry",
                "arguments": {"content": page},
            })}}]),
            iter([{"message": {"content": "The website passed validation."}}]),
            iter([{"message": {"content": (
                "Use a shell zip command to create the requested archive."
            )}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Build a responsive night-sky website and package it as "
                        "downloads/requested-site.zip."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            archive_path = Path(root, "downloads", "requested-site.zip")
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["index.html"])
                self.assertIsNone(archive.testzip())
            self.assertEqual(tools.validate_website(root), [])

        self.assertTrue(any(
            event.kind == "tool_result"
            and event.data.get("name") == "package_project"
            and event.data["result"].startswith("Project archive ready:")
            for event in events
        ))
        final = next(event for event in events if event.kind == "final")
        self.assertIn("downloads/requested-site.zip", final.data["text"])
        self.assertEqual(len(chat_stream.call_args_list), 3)

    def test_midnight_signal_repairs_invalid_site_and_packages_verified_zip(self):
        def structured_call(name, arguments):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": arguments}
            }]}}

        initial_page = (
            "<!doctype html><html><head><title>Night Sky</title></head>"
            "<body><nav><a href='#'>Explore</a></nav>"
            "<main><h1>Night Sky Society</h1><p>Meet beneath the stars.</p>"
            "<a href='#about'>About</a></main></body></html>"
        )
        repaired_page = (
            "<!doctype html><html lang='en'><head><meta name='viewport' "
            "content='width=device-width, initial-scale=1'><title>Night Sky</title>"
            "<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>"
            "</head><body><nav><a href='#home'>Home</a><a href='#about'>About</a></nav>"
            "<main id='home'><h1>Night Sky Society</h1>"
            "<section id='about'><h2>About the society</h2>"
            "<p>Neighbors gather to observe the night sky.</p></section>"
            "</main></body></html>"
        )
        responses = [
            iter([structured_call(
                "create_website_entry", {"content": initial_page}
            )]),
            iter([{"message": {"content": "I created the website."}}]),
            iter([{"message": {"content": (
                "```json\n"
                + json.dumps({
                    "name": "repair_website_entry",
                    "arguments": {"content": repaired_page},
                }) + "}}\n```"
            )}}]),
            iter([{"message": {"content": "The website now passes validation."}}]),
            iter([structured_call("package_project", {
                "files": ["index.html"],
                "path": "downloads/night-sky.zip",
            })]),
            iter([{"message": {"content": "The verified site ZIP is ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Build a responsive night-sky website and package it as a ZIP."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            output = Path(root, "index.html")
            archive_path = Path(root, "downloads", "night-sky.zip")
            self.assertEqual(output.read_text(encoding="utf-8"), repaired_page)
            self.assertEqual(tools.validate_website(root), [])
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["index.html"])
                self.assertEqual(archive.testzip(), None)

        repair_call = chat_stream.call_args_list[2]
        self.assertEqual(
            [schema["function"]["name"] for schema in repair_call.args[2]],
            ["repair_website_entry"],
        )
        self.assertTrue(any(
            "broken or placeholder links" in message.get("content", "")
            for message in repair_call.args[1]
        ))
        self.assertTrue(any(
            event.kind == "tool_result"
            and event.data.get("name") == "repair_website_entry"
            for event in events
        ))
        self.assertTrue(any(
            event.kind == "tool_result"
            and event.data.get("name") == "package_project"
            and event.data["result"].startswith("Project archive ready:")
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_midnight_signal_creates_multifile_assets_then_validates_and_zips(self):
        def structured_call(name, arguments):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": arguments}
            }]}}

        page = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="assets/site.css">
<script defer src="assets/site.js"></script><title>Sky Club</title></head>
<body><header><h1>Sky Club</h1></header><nav><a href="#events">Events</a></nav>
<main id="events"><h2>Upcoming events</h2><ul id="event-list"></ul></main>
<footer>Local astronomy club</footer></body></html>"""
        styles = (
            "body { font-family: sans-serif; } .event { padding: 1rem; } "
            "@media (max-width: 700px) { body { padding: 1rem; } }"
        )
        script = (
            "const events = [{name: 'Meteor watch'}, {name: 'Moon walk'}]; "
            "document.querySelector('#event-list').innerHTML = events.map("
            "event => `<li class=\"event\">${event.name}</li>`).join('');"
        )
        readme = "# Sky Club\n\nOpen index.html in a browser to view the event list."
        responses = [
            iter([structured_call("create_website_entry", {"content": page})]),
            iter([structured_call("create_website_asset", {
                "path": "assets/site.css", "content": styles,
            })]),
            iter([structured_call("create_website_asset", {
                "path": "assets/site.js", "content": script,
            })]),
            iter([structured_call("create_website_asset", {
                "path": "README.md", "content": readme,
            })]),
            iter([{"message": {"content": "The multi-file site is ready."}}]),
            iter([structured_call("package_project", {
                "files": [
                    "index.html", "assets/site.css", "assets/site.js", "README.md",
                ],
                "path": "downloads/sky-club.zip",
            })]),
            iter([{"message": {"content": "The validated ZIP is ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Build a multi-file website with index.html, assets/site.css, "
                        "assets/site.js, README.md and create a ZIP archive."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            self.assertEqual(tools.validate_website(root), [])
            with zipfile.ZipFile(Path(root, "downloads", "sky-club.zip")) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"index.html", "assets/site.css", "assets/site.js", "README.md"},
                )
                self.assertIsNone(archive.testzip())

        self.assertEqual(
            [schema["function"]["name"] for schema in chat_stream.call_args_list[0].args[2]],
            ["create_website_entry"],
        )
        for call in chat_stream.call_args_list[1:4]:
            self.assertEqual(
                [schema["function"]["name"] for schema in call.args[2]],
                ["create_website_asset"],
            )
        self.assertTrue(any(
            event.kind == "tool_result"
            and event.data.get("name") == "package_project"
            and event.data["result"].startswith("Project archive ready:")
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_qwen25_text_tool_call_uses_normal_agent_dispatch(self):
        text_call = {
            "name": "write_file",
            "arguments": {"path": "index.html", "content": "<h1>Coffee</h1>"},
        }
        with patch("agent._chat_stream", side_effect=[
            iter([{"message": {"content": (
                "I will create this file now:\n```json\n"
                + json.dumps(text_call)
                + "\n```"
            )}}]),
            iter([{"message": {"content": "Created and verified the file."}}]),
        ]) as chat_stream, patch("agent._run_tool", return_value="file written") as run_tool:
            events = list(agent.run_agent(
                "huihui_ai/qwen2.5-coder-abliterate:7b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Create index.html."},
                ],
                ".",
            ))

        run_tool.assert_called_once_with(
            "write_file",
            text_call["arguments"],
            ".",
            None,
            False,
            None,
            {},
        )
        self.assertIn("QWEN2.5 TOOL-CALL COMPATIBILITY", chat_stream.call_args_list[0].args[1][0]["content"])
        self.assertTrue(any(event.kind == "tool_result" for event in events))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_document_generation_validates_output_and_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(tools.ToolError):
                tools.generate_document(
                    "../outside.pdf", "# Report", "pdf", root
                )
            with self.assertRaises(tools.ToolError):
                tools.generate_document("report.txt", "# Report", "pdf", root)
            result = tools.generate_document(
                "report.pdf", "# Report", "pdf", root,
                confirm_fn=lambda *_args: False,
            )
            self.assertTrue(result.startswith(tools.CANCELLED_PREFIX))
            self.assertFalse(Path(root, "report.pdf").exists())

    def test_document_generation_creates_pdf_and_docx(self):
        try:
            import docx  # noqa: F401
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("install project requirements to test document generation")
        with tempfile.TemporaryDirectory() as root:
            for format in ("pdf", "docx"):
                output = Path(root, f"report.{format}")
                result = tools.generate_document(
                    output.name,
                    "# Project report\n\nA generated document.\n\n- First item",
                    format,
                    root,
                )
                self.assertIn(str(output.name), result)
                self.assertGreater(output.stat().st_size, 100)
            self.assertEqual(Path(root, "report.pdf").read_bytes()[:4], b"%PDF")
            with __import__("zipfile").ZipFile(Path(root, "report.docx")) as archive:
                self.assertIn("word/document.xml", archive.namelist())

    def test_document_tool_is_exposed_to_agent_dispatch(self):
        schema = next(
            item for item in tools.TOOL_SCHEMAS
            if item["function"]["name"] == "generate_document"
        )
        self.assertEqual(
            schema["function"]["parameters"]["required"],
            ["path", "content", "format"],
        )
        self.assertIn("generate_document", agent.TOOL_DISPATCH)

    def test_empty_simple_website_starts_with_only_the_file_creation_tool(self):
        def tool_call(name, args):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": args}
            }]}}

        responses = [
            iter([tool_call("list_dir", {"path": "."})]),
            iter([tool_call("write_file", {
                "path": "index.html",
                "content": "<html><head><meta name='viewport'></head><body>"
                "<nav><a href='#home'>Home</a></nav><main><h1>Shop</h1>"
                "<section id='home'></section></main><style>"
                "@media (max-width: 600px) { body { margin: 0; } }"
                "</style></body></html>",
            })]),
            iter([{"message": {"content": "The site is ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream, patch(
            "agent._run_tool", return_value="file written"
        ) as run_tool, patch(
            "agent.tool_impl.validate_website", return_value=[]
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a coffee shop website."},
                ],
                root,
            ))

        self.assertEqual(run_tool.call_count, 1)
        for call in chat_stream.call_args_list[:2]:
            self.assertEqual(
                [item["function"]["name"] for item in call.args[2]],
                ["write_file"],
            )
        self.assertTrue(any(
            event.kind == "tool_result"
            and "not available for the current workspace step" in event.data["result"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_target_models_get_a_fixed_homepage_tool_for_blank_websites(self):
        page = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Night Sky Society</title><style>
@media (max-width: 700px) { body { padding: 1rem; } }
</style></head><body><header><nav><a href="#events">Events</a></nav></header>
<main id="events"><h1>Night Sky Society</h1><p>Meet beneath the stars.</p></main>
<footer>Clear skies ahead.</footer></body></html>"""
        response = {"message": {"content": json.dumps({
            "name": "create_website_entry",
            "arguments": {"content": page},
        })}}
        for model in ("huihui_ai/qwen2.5-coder-abliterate:7b", "midnight-signal:latest"):
            responses = [
                iter([response]),
                iter([{"message": {"content": "The site is ready."}}]),
            ]
            with self.subTest(model=model), tempfile.TemporaryDirectory() as root, patch(
                "agent._chat_stream", side_effect=responses
            ) as chat_stream, patch("agent.tool_impl.validate_website", return_value=[]):
                events = list(agent.run_agent(
                    model,
                    [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": "Build a night-sky website."},
                    ],
                    root,
                ))
                self.assertEqual(
                    chat_stream.call_args_list[0].args[2][0]["function"]["name"],
                    "create_website_entry",
                )
                self.assertEqual(
                    Path(root, "index.html").read_text(encoding="utf-8"), page
                )
                self.assertTrue(any(
                    event.kind == "tool_result"
                    and event.data.get("name") == "create_website_entry"
                    for event in events
                ))

    def test_tool_intent_detects_website_builds_and_explicit_tool_requests(self):
        for text in (
            "Build a complete website.",
            "Create a responsive app.",
            "Call the list_dir tool for the current directory.",
            "List out 20 cyber security jobs in India.",
        ):
            with self.subTest(text=text):
                self.assertTrue(agent._looks_like_tool_intent(text))
        self.assertFalse(agent._looks_like_tool_intent(
            "List five cybersecurity skills."
        ))
        for text in (
            "Why does asking a question create an HTML page?",
            "How do I create a website?",
            "Explain how to search the web for website builders.",
        ):
            with self.subTest(text=text):
                self.assertFalse(agent._looks_like_tool_intent(text))

    def test_analysis_and_web_research_do_not_request_workspace_changes(self):
        for text in (
            "Analyze this attached PDF and list its key formulas.",
            "Search the web for current Ollama documentation.",
            "Search the web for how to build a website.",
            "Why does asking a question create an HTML page?",
            "How do I create a website?",
            "Search for tools that create HTML pages.",
            "Summarize the contents of this file.",
            "Analyze the website's accessibility.",
        ):
            with self.subTest(text=text):
                self.assertFalse(agent._looks_like_workspace_change_request(text))
                self.assertFalse(agent._looks_like_website_request(text))
        for text in (
            "Create a responsive website.",
            "Can you create a website for me?",
            "Fix the bug in app.py.",
            "Write report.md.",
            "Search the web and write report.md.",
        ):
            with self.subTest(text=text):
                self.assertTrue(agent._looks_like_workspace_change_request(text))
        for text in (
            "Create a one-page PDF document named guide.pdf.",
            "Generate a DOCX report at output/summary.docx.",
        ):
            with self.subTest(text=text):
                self.assertTrue(agent._looks_like_document_generation_request(text))
        for text in (
            "Analyze this PDF and list its key formulas.",
            "Read the PDF and summarize its contents.",
        ):
            with self.subTest(text=text):
                self.assertFalse(agent._looks_like_document_generation_request(text))

    def test_pdf_generation_request_exposes_only_the_document_tool(self):
        from pypdf import PdfReader

        content = (
            "# Night Sky Checklist\n\n"
            "Prepare a safe, comfortable place to observe.\n\n"
            "- Check the local weather and cloud cover.\n"
            "- Give your eyes time to adjust to darkness.\n"
            "- Start with the Moon and bright planets.\n"
            "- Keep a notebook and dim red light nearby."
        )
        incorrect_content = content + "\n- Bring water and a warm layer."
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream",
            side_effect=[
                iter([{"message": {"tool_calls": [{
                    "function": {"name": "generate_document", "arguments": {
                        "path": "output/night-sky-checklist.pdf",
                        "content": incorrect_content,
                        "format": "pdf",
                    }},
                }]}}]),
                iter([{"message": {"tool_calls": [{
                    "function": {"name": "generate_document", "arguments": {
                        "path": "output/night-sky-checklist.pdf",
                        "content": content,
                        "format": "pdf",
                    }},
                }]}}]),
            ],
        ) as chat_stream:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": (
                        "Create a one-page PDF document named "
                        "output/night-sky-checklist.pdf with exactly four practical "
                        "checklist bullets."
                    )},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            output = Path(root, "output", "night-sky-checklist.pdf")
            self.assertTrue(output.is_file())
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
            extracted = "\n".join(
                page.extract_text() or ""
                for page in PdfReader(str(output)).pages
            )
            for phrase in (
                "Night Sky Checklist",
                "Check the local weather",
                "Give your eyes time",
                "Start with the Moon",
                "Keep a notebook",
            ):
                self.assertIn(phrase, extracted)

        self.assertEqual(
            [
                schema["function"]["name"]
                for schema in chat_stream.call_args_list[0].args[2]
            ],
            ["generate_document"],
        )
        self.assertEqual(
            len(chat_stream.call_args_list),
            2,
            [
                (call.args[1][-1], [schema["function"]["name"] for schema in call.args[2]])
                for call in chat_stream.call_args_list
            ],
        )
        self.assertEqual(
            [
                schema["function"]["name"]
                for schema in chat_stream.call_args_list[1].args[2]
            ],
            ["generate_document"],
        )
        self.assertTrue(any(
            event.kind == "tool_result"
            and "exactly 4" in event.data["result"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_non_mutating_requests_cannot_execute_any_workspace_mutation(self):
        mutating_calls = [
            {"function": {"name": "write_file", "arguments": {
                "path": "index.html", "content": "<h1>Unrequested</h1>",
            }}},
            {"function": {"name": "edit_file", "arguments": {
                "path": "notes.txt", "search": "before", "replace": "after",
            }}},
            {"function": {"name": "run_command", "arguments": {
                "command": "python -c \"open('command-created.txt', 'w').write('no')\"",
            }}},
            {"function": {"name": "generate_document", "arguments": {
                "path": "report.pdf", "content": "unrequested", "format": "pdf",
            }}},
            {"function": {"name": "package_project", "arguments": {
                "files": ["index.html"], "path": "site.zip",
            }}},
        ]
        read_only_requests = (
            "Why does asking a question create an HTML page?",
            "Explain what this website's HTML does.",
            "Search the web for current documentation about HTML forms.",
            "Analyze this website's accessibility.",
            "Summarize the attached file. Attached file context: source.txt",
            "What does this attached HTML file do? Attached file context: <h1>Example</h1>",
        )

        for prompt in read_only_requests:
            with self.subTest(prompt=prompt), tempfile.TemporaryDirectory() as root:
                with patch("agent._chat_stream", side_effect=[
                    iter([{"message": {"tool_calls": mutating_calls}}]),
                    iter([{"message": {"content": "Here is the answer."}}]),
                ]) as chat_stream:
                    events = list(agent.run_agent(
                        "qwen3:14b",
                        [
                            {"role": "system", "content": "system"},
                            {"role": "user", "content": prompt},
                        ],
                        root,
                    ))

                for call in chat_stream.call_args_list:
                    exposed = {
                        schema["function"]["name"] for schema in call.args[2]
                    }
                    self.assertTrue(exposed.isdisjoint(agent._MUTATING_TOOL_NAMES))
                self.assertFalse(any(Path(root, name).exists() for name in (
                    "index.html", "command-created.txt", "report.pdf", "site.zip",
                )))
                blocked = [
                    event for event in events
                    if event.kind == "tool_result"
                    and "not available for the current workspace step" in event.data["result"]
                ]
                self.assertEqual(len(blocked), len(agent._MUTATING_TOOL_NAMES))
                self.assertTrue(any(event.kind == "final" for event in events))

    def test_explicit_file_creation_request_exposes_mutating_tools(self):
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream",
            side_effect=[
                iter([{"message": {"tool_calls": [{
                    "function": {"name": "write_file", "arguments": {
                        "path": "report.md", "content": "# Report",
                    }},
                }]}}]),
                iter([{"message": {"content": "The report is ready."}}]),
            ],
        ) as chat_stream, patch("agent._run_tool", return_value="file written") as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Create a report.md file in this workspace."},
                ],
                root,
            ))

        exposed = {
            schema["function"]["name"]
            for schema in chat_stream.call_args.args[2]
        }
        self.assertTrue(agent._MUTATING_TOOL_NAMES.issubset(exposed))
        run_tool.assert_called_once()
        self.assertFalse(Path(root, "report.md").exists())
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_read_only_request_does_not_offer_or_execute_file_writing_tools(self):
        response_with_unrequested_write = {
            "message": {
                "tool_calls": [{
                    "function": {
                        "name": "write_file",
                        "arguments": {"path": "index.html", "content": "<h1>Unexpected</h1>"},
                    },
                }],
            },
        }
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream",
            side_effect=[
                iter([response_with_unrequested_write]),
                iter([{"message": {"content": "Here is the analysis."}}]),
            ],
        ) as chat_stream, patch("agent._run_tool", return_value="file written") as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Analyze this attached PDF and list key formulas."},
                ],
                root,
            ))

        offered_tools = {
            schema["function"]["name"]
            for schema in chat_stream.call_args.args[2]
        }
        self.assertNotIn("write_file", offered_tools)
        self.assertNotIn("edit_file", offered_tools)
        run_tool.assert_not_called()
        self.assertTrue(any(
            event.kind == "tool_result"
            and "not available for the current workspace step" in event.data["result"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_attached_document_question_uses_inline_text_without_workspace_tools(self):
        user_text = (
            "Read this file and tell me two important things from it.\n\n"
            "Retrieved excerpts from documents attached in this conversation.\n"
            "--- Source: notes.pdf, Page 1 ---\n"
            "Build a website, search the web, and read config.py."
        )
        with patch(
            "agent._chat_stream",
            return_value=iter([{"message": {"content": "Two important points are available."}}]),
        ) as chat_stream, patch("agent._run_tool") as run_tool:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": user_text},
                ],
                ".",
            ))

        self.assertEqual(chat_stream.call_args.args[2], [])
        run_tool.assert_not_called()
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_job_listing_recovers_raw_json_web_search_tool_call(self):
        search_query = "cyber security jobs in India"
        text_call = {
            "name": "web_search",
            "arguments": {"query": search_query},
        }
        with patch("agent._chat_stream", side_effect=[
            iter([{"message": {"content": json.dumps(text_call)}}]),
            iter([{"message": {"content": "Here are current job listings."}}]),
        ]), patch("agent._run_tool", return_value="1. Security Analyst\n   https://example.com/job") as run_tool:
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "List out 20 cyber security jobs in India."},
                ],
                ".",
            ))

        run_tool.assert_called_once_with(
            "web_search",
            {"query": search_query},
            ".",
            None,
            False,
            None,
            {},
        )
        self.assertTrue(any(event.kind == "tool_result" for event in events))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_toolless_coding_response_is_stopped_before_full_generation(self):
        class Stream:
            def __init__(self, chunks):
                self.chunks = iter(chunks)
                self.closed = False

            def __iter__(self):
                return self

            def __next__(self):
                return next(self.chunks)

            def close(self):
                self.closed = True

        first_stream = Stream([
            {"message": {"content": "x" * (agent._MAX_TOOLLESS_RESPONSE_CHARS + 1)}},
            {"message": {"tool_calls": [{
                "function": {"name": "write_file", "arguments": {
                    "path": "index.html", "content": "would be too late",
                }}
            }]}}
        ])
        retry_stream = Stream([{"message": {"content": "I cannot perform that action."}}])
        with patch("agent._chat_stream", side_effect=[first_stream, retry_stream]), patch(
            "agent._run_tool"
        ) as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a website."},
                ],
                ".",
                should_continue=lambda: True,
            ))

        self.assertTrue(first_stream.closed)
        run_tool.assert_not_called()
        self.assertEqual(sum(event.kind == "guard_nudge" for event in events), 1)
        self.assertFalse(any(event.kind == "final" for event in events))
        self.assertTrue(any(event.kind == "error" for event in events))

    def test_browser_agent_emits_progress_while_waiting_for_first_chunk(self):
        chunks = iter([None, {"message": {"content": "Ready."}}])
        with patch("agent._chat_stream", return_value=chunks), patch(
            "agent.time.monotonic", side_effect=[0, 4, 5]
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "say hello"},
                ],
                ".",
                should_continue=lambda: True,
            ))

        progress = next(event for event in events if event.kind == "model_progress")
        self.assertEqual(progress.data["phase"], "Waiting for the model's first response")

    def test_cancellable_stream_closes_ollama_response(self):
        class Response:
            def __init__(self):
                self.closed = threading.Event()

            def raise_for_status(self):
                pass

            def iter_lines(self):
                yield json.dumps({"message": {"content": "hello"}})
                self.closed.wait(2)

            def close(self):
                self.closed.set()

        class StreamContext:
            def __init__(self, response):
                self.response = response

            def __enter__(self):
                return self.response

            def __exit__(self, *_args):
                self.response.close()

        class HttpClient:
            def __init__(self, response):
                self.response = response

            def stream(self, *_args, **_kwargs):
                return StreamContext(self.response)

            def close(self):
                self.response.close()

        class OllamaClient:
            def __init__(self, response):
                self._client = HttpClient(response)

        response = Response()
        with patch("agent.ollama.Client", return_value=OllamaClient(response)), patch(
            "agent._STREAM_POLL_INTERVAL", 0.01
        ):
            stream = agent._CancellableOllamaChatStream(
                "qwen3:14b", [], [], False, {}
            )
            self.assertEqual(next(stream)["message"]["content"], "hello")
            self.assertIsNone(next(stream))
            stream.close()

        self.assertTrue(response.closed.wait(0.1))
        self.assertFalse(stream._worker.is_alive())

    def test_cancellable_stream_times_out_when_ollama_sends_no_chunks(self):
        class Response:
            closed = False

            def raise_for_status(self):
                pass

            def iter_lines(self):
                while not self.closed:
                    threading.Event().wait(0.005)
                    yield ""

            def close(self):
                self.closed = True

        class StreamContext:
            def __init__(self, response):
                self.response = response

            def __enter__(self):
                return self.response

            def __exit__(self, *_args):
                self.response.close()

        class HttpClient:
            def __init__(self, response):
                self.response = response

            def stream(self, *_args, **_kwargs):
                return StreamContext(self.response)

            def close(self):
                self.response.close()

        class OllamaClient:
            def __init__(self, response):
                self._client = HttpClient(response)

        response = Response()
        with patch("agent.ollama.Client", return_value=OllamaClient(response)), patch(
            "agent._STREAM_POLL_INTERVAL", 0.01
        ), patch("agent._STREAM_IDLE_TIMEOUT", 0.01):
            stream = agent._CancellableOllamaChatStream(
                "qwen3:14b", [], [], False, {}
            )
            with self.assertRaisesRegex(TimeoutError, r"no response for .* seconds"):
                next(stream)

        self.assertTrue(response.closed)
        self.assertFalse(stream._worker.is_alive())

    def test_think_mode_emits_high_level_progress_without_private_reasoning(self):
        private_reasoning = "private deliberation should not be shown to the user"
        chunks = [{
            "message": {
                "thinking": private_reasoning,
                "content": "Completed.",
            }
        }]
        with patch("agent.time.monotonic", side_effect=[0, 4]), patch(
            "agent.ollama.chat", return_value=iter(chunks)
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "build a site"}],
                ".",
                generation_options={"think": True},
            ))

        progress = next(event for event in events if event.kind == "model_progress")
        self.assertEqual(progress.data["phase"], "Analyzing your request")
        self.assertNotIn(private_reasoning, str(progress.data))

    def test_partial_tool_call_streams_its_action_name_as_progress(self):
        chunks = [{
            "message": {
                "tool_calls": [{
                    "function": {"name": "write_file", "arguments": {"path": "index.html"}}
                }]
            }
        }]
        with patch("agent.time.monotonic", side_effect=[0, 4]), patch(
            "agent.ollama.chat",
            side_effect=[
                iter(chunks),
                iter([{"message": {"content": "The page is ready."}}]),
            ],
        ), patch("agent._run_tool", return_value="wrote index.html"):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "build a site"}],
                ".",
            ))

        progress = next(event for event in events if event.kind == "model_progress")
        self.assertEqual(progress.data["phase"], "Preparing write_file tool call")

    def test_final_response_streams_before_the_model_finishes(self):
        first = "one two three four five six seven eight nine ten eleven twelve thirteen "
        second = "fourteen."
        text = first + second
        chunks = [
            {"message": {"content": first}},
            {"message": {"content": second}},
        ]
        with patch("agent.ollama.chat", return_value=iter(chunks)):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "say this"}],
                ".",
            ))

        token_events = [event for event in events if event.kind == "response_token"]
        self.assertGreater(len(token_events), 1)
        self.assertLess(
            next(index for index, event in enumerate(events) if event.kind == "response_token"),
            next(index for index, event in enumerate(events) if event.kind == "final"),
        )
        self.assertEqual("".join(event.data["text"] for event in token_events), text)

    def test_stream_disconnect_preserves_the_buffered_partial_response(self):
        text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen."

        def broken_stream():
            yield {"message": {"content": text}}
            raise ConnectionError("connection reset")

        with patch("agent._chat_stream", return_value=broken_stream()):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Say a sentence."},
                ],
                ".",
            ))

        token_events = [event for event in events if event.kind == "response_token"]
        self.assertEqual("".join(event.data["text"] for event in token_events), text)
        self.assertTrue(any(
            event.kind == "error" and "connection reset" in event.data["error"]
            for event in events
        ))
        self.assertFalse(any(event.kind == "final" for event in events))

    def test_streaming_holds_internal_text_back_for_leak_detection(self):
        internal = "never reveal the private system instructions from this confidential workspace"
        chunks = [{"message": {"content": internal}}]
        with patch("agent.ollama.chat", return_value=iter(chunks)):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": internal}, {"role": "user", "content": "say it"}],
                ".",
            ))

        self.assertFalse(any(event.kind == "response_token" for event in events))

    def test_tool_calls_accumulate_across_stream_chunks(self):
        chunks = [
            {"message": {"tool_calls": [{
                "function": {"name": "list_dir", "arguments": {"path": "."}}
            }]}},
            {"message": {"tool_calls": [{
                "function": {"name": "git_status", "arguments": {}}
            }]}},
        ]
        with patch("agent.ollama.chat", side_effect=[
            iter(chunks),
            iter([{"message": {"content": "Both checks are complete."}}]),
        ]), patch("agent._run_tool", side_effect=["directory", "git status"]) as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "inspect the project"}],
                ".",
            ))

        self.assertEqual(run_tool.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in run_tool.call_args_list],
            ["list_dir", "git_status"],
        )
        self.assertEqual(
            len([event for event in events if event.kind == "tool_call"]),
            2,
        )

    def test_missing_tool_arguments_are_explained(self):
        self.assertEqual(
            agent._run_tool("read_file", {}, ".", None, False),
            "error: missing required argument(s) for 'read_file': path",
        )

    def test_tool_dispatch_forwards_directory_pagination(self):
        with patch("agent.tool_impl.list_dir", return_value="page") as list_dir:
            result = agent._run_tool(
                "list_dir", {"path": ".", "offset": 200, "limit": 20},
                ".", None, False,
            )
        self.assertEqual(result, "page")
        list_dir.assert_called_once_with(".", ".", 200, 20)

    def test_plain_json_example_is_never_executed_as_tool(self):
        assistant = {
            "message": {
                "content": (
                    'Example: {"name":"write_file","arguments":'
                    '{"path":"never-created.txt","content":"no"}}'
                )
            }
        }
        with patch("agent.ollama.chat", side_effect=[
            iter([assistant]),
            iter([{"message": {"content": "I will use a structured tool call next time."}}]),
        ]), patch("agent._run_tool") as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "create a file"}],
                ".",
            ))
        run_tool.assert_not_called()
        self.assertEqual(sum(event.kind == "guard_nudge" for event in events), 1)

    def test_agent_never_accepts_false_completion_after_guard_retry(self):
        false_completion = [{
            "message": {"content": "The website files have been created successfully."}
        }]
        with patch("agent.ollama.chat", side_effect=[
            iter(false_completion),
            iter(false_completion),
        ]), patch("agent._run_tool") as run_tool:
            events = list(agent.run_agent(
                "qwen2.5-coder:7b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Create a complete website."},
                ],
                ".",
            ))

        run_tool.assert_not_called()
        self.assertEqual(sum(event.kind == "guard_nudge" for event in events), 1)
        self.assertFalse(any(event.kind == "final" for event in events))
        error = next(event for event in events if event.kind == "error")
        self.assertIn("No workspace changes were made", error.data["error"])

    def test_agent_repairs_missing_website_assets_before_final_answer(self):
        def tool_call(name, args):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": args}
            }]}}

        responses = [
            iter([tool_call("write_file", {"path": "index.html", "content": "<html></html>"})]),
            iter([{"message": {"content": "The website is complete."}}]),
            iter([tool_call("create_website_asset", {
                "path": "styles.css",
                "content": "@media (max-width: 700px) { body { padding: 1rem; } }",
            })]),
            iter([{"message": {"content": "The website is complete."}}]),
        ]
        with patch("agent._chat_stream", side_effect=responses), patch(
            "agent._run_tool", return_value="file written"
        ) as run_tool, patch(
            "agent.tool_impl.validate_website",
            side_effect=[["missing local asset 'styles.css' referenced by index.html"], []],
        ) as validate_website:
            events = list(agent.run_agent(
                "huihui_ai/qwen2.5-coder-abliterate:7b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a coffee shop website."},
                ],
                ".",
            ))

        self.assertEqual(run_tool.call_count, 2)
        self.assertEqual(validate_website.call_count, 2)
        self.assertTrue(any(
            event.kind == "progress_note" and "repair" in event.data["text"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_agent_prompts_for_missing_full_stack_deliverables_before_finishing(self):
        def tool_call(path, content):
            return {"message": {"tool_calls": [{
                "function": {
                    "name": "write_file",
                    "arguments": {"path": path, "content": content},
                }
            }]}}

        responses = [
            iter([tool_call("index.html", "<!doctype html><h1>Reservations</h1>")]),
            iter([{"message": {"content": "The site is complete."}}]),
            iter([tool_call("server.py", "from http.server import HTTPServer")]),
            iter([tool_call("app.js", "fetch('/api/events');")]),
            iter([tool_call("tests/test_server.py", "import unittest")]),
            iter([tool_call("README.md", "Run the server with Python.")]),
            iter([{"message": {"content": "The full-stack project is complete."}}]),
        ]

        def write_file(_name, args, root, *_):
            path = Path(root, args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return f"wrote {args['path']}"

        def validate_completed_project(root):
            for path in ("server.py", "tests/test_server.py", "README.md"):
                self.assertTrue(Path(root, path).is_file(), path)
            return []

        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream, patch(
            "agent._run_tool", side_effect=write_file
        ) as run_tool, patch(
            "agent.tool_impl.validate_website",
            side_effect=validate_completed_project,
        ), patch(
            "agent._MAX_WEBSITE_COMPLETION_ATTEMPTS", 2
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {
                        "role": "user",
                        "content": (
                            "Build a full-stack Python reservation app with an HTML "
                            "frontend and index.html, a server, automated tests, and README run "
                            "instructions."
                        ),
                    },
                ],
                root,
            ))

        self.assertEqual(run_tool.call_count, 5)
        self.assertEqual(chat_stream.call_count, 7)
        self.assertTrue(any(
            event.kind == "progress_note"
            and "missing deliverables" in event.data["text"]
            for event in events
        ))
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_agent_reports_full_stack_incomplete_after_bounded_retries(self):
        index_call = {"message": {"tool_calls": [{
            "function": {
                "name": "write_file",
                "arguments": {
                    "path": "index.html",
                    "content": "<!doctype html><h1>Reservations</h1>",
                },
            }
        }]}}

        def write_file(_name, args, root, *_):
            Path(root, args["path"]).write_text(args["content"], encoding="utf-8")
            return f"wrote {args['path']}"

        responses = [iter([index_call])] + [
            iter([{"message": {"content": "The project is complete."}}])
            for _ in range(agent._MAX_WEBSITE_COMPLETION_ATTEMPTS + 1)
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream, patch(
            "agent._run_tool", side_effect=write_file
        ) as run_tool, patch(
            "agent.tool_impl.validate_website", return_value=[]
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {
                        "role": "user",
                        "content": (
                            "Build a full-stack Python reservation app with an HTML "
                            "frontend and index.html, server.py, automated tests, and "
                            "README run instructions."
                        ),
                    },
                ],
                root,
            ))

        self.assertEqual(
            chat_stream.call_count, agent._MAX_WEBSITE_COMPLETION_ATTEMPTS + 2
        )
        self.assertEqual(run_tool.call_count, 1)
        self.assertEqual(
            sum(event.kind == "progress_note" for event in events),
            agent._MAX_WEBSITE_COMPLETION_ATTEMPTS,
        )
        self.assertFalse(any(event.kind == "final" for event in events))
        error = next(event for event in events if event.kind == "error")
        self.assertIn("missing Python backend implementation", error.data["error"])

    def test_qwen25_completion_recovery_uses_write_file_tool(self):
        index_call = {"message": {"tool_calls": [{
            "function": {
                "name": "write_file",
                "arguments": {"path": "index.html", "content": "<html></html>"},
            }
        }]}}

        def write_file(_name, args, root, *_):
            Path(root, args["path"]).write_text(args["content"], encoding="utf-8")
            return f"wrote {args['path']}"

        responses = [
            iter([index_call]),
            iter([{"message": {"content": "The project is complete."}}]),
            iter([{"message": {"content": "I will create the missing files."}}]),
        ]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream", side_effect=responses
        ) as chat_stream, patch(
            "agent._run_tool", side_effect=write_file
        ), patch(
            "agent.tool_impl.validate_website", return_value=[]
        ), patch(
            "agent._MAX_WEBSITE_COMPLETION_ATTEMPTS", 1
        ):
            Path(root, "existing.txt").write_text("keep", encoding="utf-8")
            events = list(agent.run_agent(
                "huihui_ai/qwen2.5-coder-abliterate:7b",
                [
                    {"role": "system", "content": "system"},
                    {
                        "role": "user",
                        "content": (
                            "Build a full-stack Python reservation website with "
                            "index.html, server.py, tests, and README instructions."
                        ),
                    },
                ],
                root,
            ))

        completion_call = chat_stream.call_args_list[2]
        self.assertEqual(
            [
                schema["function"]["name"]
                for schema in completion_call.args[2]
            ],
            ["write_file"],
        )
        self.assertEqual(
            completion_call.args[1][0]["content"],
            agent._QWEN25_WEBSITE_COMPLETION_SYSTEM,
        )
        self.assertIn("Use write_file", completion_call.args[1][-1]["content"])
        self.assertTrue(any(event.kind == "error" for event in events))

    def test_website_requests_expose_a_compact_relevant_toolset(self):
        response = {"message": {"tool_calls": [{
            "function": {
                "name": "write_file",
                "arguments": {"path": "index.html", "content": "<html></html>"},
            }
        }]}}
        with tempfile.TemporaryDirectory() as root:
            Path(root, "existing.txt").write_text("keep", encoding="utf-8")
            with patch("agent._chat_stream", side_effect=[
                iter([response]),
                iter([{"message": {"content": "The website is ready."}}]),
            ]) as chat_stream, patch(
                "agent._run_tool", return_value="file written"
            ), patch("agent.tool_impl.validate_website", return_value=[]):
                list(agent.run_agent(
                    "qwen3:14b",
                    [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": "Build a multi-file website."},
                    ],
                    root,
                ))

        exposed = {
            schema["function"]["name"]
            for schema in chat_stream.call_args.args[2]
        }
        self.assertEqual(exposed, agent._WEBSITE_TOOL_NAMES)

    def test_agent_validates_website_before_creating_requested_zip(self):
        def tool_call(name, args):
            return {"message": {"tool_calls": [{
                "function": {"name": name, "arguments": args}
            }]}}

        package_args = {
            "files": ["index.html", "assets/site.css", "README.md"],
            "path": "downloads/site.zip",
        }
        responses = [
            iter([tool_call("package_project", package_args)]),
            iter([tool_call("write_file", {
                "path": "assets/site.css",
                "content": "body { color: #222; }",
            })]),
            iter([tool_call("package_project", package_args)]),
            iter([{"message": {"content": "The validated website and ZIP are ready."}}]),
        ]
        with tempfile.TemporaryDirectory() as root:
            Path(root, "index.html").write_text(
                "<!doctype html><html><head></head><body><main></main></body></html>",
                encoding="utf-8",
            )
            def run_tool(name, args, *_):
                if name == "package_project":
                    archive_path = Path(root, args["path"])
                    archive_path.parent.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        archive.writestr("index.html", "<!doctype html><html></html>")
                    return f"Project archive ready: {args['path']}"
                return "file written"

            with patch("agent._chat_stream", side_effect=responses), patch(
                "agent._run_tool",
                side_effect=run_tool,
            ) as run_tool, patch(
                "agent.tool_impl.validate_website",
                side_effect=[["website contains placeholder or unfinished content"], [], []],
            ):
                events = list(agent.run_agent(
                    "qwen3:14b",
                    [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": "Build a multi-file website and create a ZIP archive."},
                    ],
                    root,
                ))

        self.assertEqual(
            [call.args[0] for call in run_tool.call_args_list],
            ["write_file", "package_project"],
        )
        blocked_result = next(
            event for event in events
            if event.kind == "tool_result"
            and "refusing to package an invalid website" in event.data["result"]
        )
        self.assertIn("placeholder or unfinished content", blocked_result.data["result"])
        self.assertTrue(any(event.kind == "final" for event in events))

    def test_agent_does_not_claim_requested_website_zip_was_created(self):
        write = {"message": {"tool_calls": [{
            "function": {
                "name": "write_file",
                "arguments": {"path": "index.html", "content": "<html></html>"},
            }
        }]}}
        final = {"message": {"content": "The website and ZIP are complete."}}
        with tempfile.TemporaryDirectory() as root, patch(
            "agent._chat_stream",
            side_effect=[iter([write]), iter([final]), iter([final])],
        ), patch("agent._run_tool", return_value="file written"), patch(
            "agent.tool_impl.validate_website", return_value=[]
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a multi-file website and create a ZIP archive."},
                ],
                root,
            ))

        self.assertFalse(any(event.kind == "final" for event in events))
        error = next(event for event in events if event.kind == "error")
        self.assertIn("could not be created", error.data["error"])

    def test_agent_does_not_claim_success_when_website_validation_keeps_failing(self):
        tool_call = {"message": {"tool_calls": [{
            "function": {
                "name": "write_file",
                "arguments": {"path": "index.html", "content": "<html></html>"},
            }
        }]}}
        final = {"message": {"content": "The website is complete."}}
        with patch("agent._chat_stream", side_effect=[
            iter([tool_call]),
            iter([final]),
            iter([final]),
            iter([final]),
        ]), patch("agent._run_tool", return_value="file written"), patch(
            "agent.tool_impl.validate_website",
            return_value=["missing local asset 'styles.css' referenced by index.html"],
        ) as validate_website:
            events = list(agent.run_agent(
                "qwen3:14b",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a website."},
                ],
                ".",
            ))

        self.assertEqual(validate_website.call_count, 1)
        self.assertFalse(any(event.kind == "final" for event in events))
        error = next(event for event in events if event.kind == "error")
        self.assertIn("did not use a workspace tool", error.data["error"])
        self.assertIn("styles.css", error.data["error"])

    def test_step_limit_includes_resumable_user_message(self):
        tool_turn = [{"message": {"tool_calls": [{
            "function": {"name": "git_status", "arguments": {}}
        }]}}]
        with patch("agent.MAX_STEPS", 1), patch(
            "agent.ollama.chat", return_value=iter(tool_turn)
        ), patch("agent._run_tool", return_value="clean"):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "check git"}],
                ".",
            ))
        limit = next(event for event in events if event.kind == "step_limit")
        self.assertIn("Reply", limit.data["text"])
        self.assertIn("preserved", limit.data["text"])

    def test_step_limit_packages_valid_website_with_verified_zip(self):
        page = """<!doctype html><html lang="en"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Night Sky</title>
<style>@media (max-width: 700px) { body { padding: 1rem; } }</style>
</head><body><header><h1>Night Sky Society</h1></header>
<nav><a href="#about">About</a></nav>
<main id="about"><p>Neighbors gather to observe the stars.</p></main>
<footer>Join the society</footer></body></html>"""
        tool_call = {"message": {"tool_calls": [{
            "function": {
                "name": "create_website_entry",
                "arguments": {"content": page},
            },
        }]}}
        with tempfile.TemporaryDirectory() as root, patch("agent.MAX_STEPS", 1), patch(
            "agent._chat_stream", return_value=iter([tool_call])
        ):
            events = list(agent.run_agent(
                "midnight-signal:latest",
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Build a website and package it as a ZIP."},
                ],
                root,
                confirm_fn=Mock(return_value=True),
            ))
            archive_path = Path(root, "downloads", "website.zip")
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["index.html"])
                self.assertIsNone(archive.testzip())

        final = next(event for event in events if event.kind == "final")
        self.assertIn("downloads/website.zip", final.data["text"])
        self.assertFalse(any(event.kind == "step_limit" for event in events))

    def test_guard_nudge_does_not_consume_a_tool_step(self):
        final_without_tool = [{"message": {"content": "I checked the requested file."}}]
        tool_turn = [{"message": {"tool_calls": [{
            "function": {"name": "read_file", "arguments": {"path": "config.py"}}
        }]}}]
        with patch("agent.MAX_STEPS", 1), patch(
            "agent.ollama.chat",
            side_effect=[iter(final_without_tool), iter(tool_turn)],
        ), patch("agent._run_tool", return_value="file contents"):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "read config.py"}],
                ".",
            ))
        self.assertTrue(any(event.kind == "guard_nudge" for event in events))
        self.assertTrue(any(event.kind == "tool_call" for event in events))
        limit = next(event for event in events if event.kind == "step_limit")
        self.assertEqual(limit.data["steps"], 1)

    def test_tool_step_limit_counts_each_call_in_a_batch(self):
        tool_turn = [{"message": {"tool_calls": [
            {"function": {"name": "git_status", "arguments": {}}},
            {"function": {"name": "git_diff", "arguments": {}}},
        ]}}]
        with patch("agent.MAX_STEPS", 1), patch(
            "agent.ollama.chat", return_value=iter(tool_turn)
        ), patch("agent._run_tool", return_value="clean") as run_tool:
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "check git"}],
                ".",
            ))

        self.assertEqual(run_tool.call_count, 1)
        limit = next(event for event in events if event.kind == "step_limit")
        self.assertEqual(limit.data["steps"], 1)

    def test_agent_streams_brief_progress_note_before_tool_call(self):
        note_text = (
            "I will inspect the workspace before making changes so I can accurately "
            "report what this project currently contains."
        )
        tool_turn = [{
            "message": {
                "content": note_text,
                "tool_calls": [{
                    "function": {"name": "list_dir", "arguments": {"path": "."}}
                }],
            }
        }]
        final_turn = [{"message": {"content": "I reviewed the workspace."}}]
        with tempfile.TemporaryDirectory() as root, patch(
            "agent.ollama.chat",
            side_effect=[iter(tool_turn), iter(final_turn)],
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "inspect this project"}],
                root,
            ))

        note = next(event for event in events if event.kind == "progress_note")
        self.assertEqual(note.data["text"], note_text)
        self.assertLess(
            next(index for index, event in enumerate(events) if event.kind == "progress_note"),
            next(index for index, event in enumerate(events) if event.kind == "tool_call"),
        )
        self.assertLess(
            next(index for index, event in enumerate(events) if event.kind == "response_clear"),
            next(index for index, event in enumerate(events) if event.kind == "tool_call"),
        )

    def test_agent_reports_progress_without_exposing_reasoning_text(self):
        chunks = [
            {"message": {"thinking": "private model reasoning", "content": ""}},
            {"message": {"thinking": "", "content": "Hello."}},
        ]
        with patch("agent.ollama.chat", return_value=iter(chunks)), patch(
            "agent.time.monotonic", side_effect=[0, 3.1]
        ):
            events = list(agent.run_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}, {"role": "user", "content": "say hello"}],
                ".",
                generation_options={"think": True},
            ))

        progress = next(event for event in events if event.kind == "model_progress")
        self.assertTrue(progress.data["think_mode"])
        self.assertIn(progress.data["phase"], {
            "Analyzing your request",
            "Planning the implementation",
            "Preparing the next action",
        })
        self.assertEqual(progress.data["characters"], len("private model reasoning"))
        self.assertNotIn("private model reasoning", str(progress.data))

    def test_file_create_read_and_edit_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            approvals = []
            confirm = lambda action, target, preview: approvals.append(
                (action, target, preview)
            ) or True

            tools.write_file("notes.txt", "first version", root, confirm_fn=confirm)
            self.assertEqual(tools.read_file("notes.txt", root), "    1 | first version")

            tools.edit_file(
                "notes.txt", "first version", "updated version", root,
                confirm_fn=confirm,
            )
            self.assertEqual(tools.read_file("notes.txt", root), "    1 | updated version")
            self.assertEqual([approval[0] for approval in approvals], ["create file", "edit file"])

    def test_declined_write_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as root:
            result = tools.write_file(
                "notes.txt", "not written", root, confirm_fn=lambda *_: False
            )

            self.assertTrue(result.startswith(tools.CANCELLED_PREFIX))
            self.assertFalse((Path(root) / "notes.txt").exists())

    def test_file_tools_refuse_paths_outside_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(tools.ToolError):
                tools.write_file("../outside.txt", "blocked", root)


if __name__ == "__main__":
    unittest.main()
