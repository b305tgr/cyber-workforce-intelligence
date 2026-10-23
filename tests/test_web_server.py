import unittest
import base64
import io
import json
import os
import http.client
import http.client
import threading
import urllib.error
import urllib.parse
import urllib.request
import tempfile
import zipfile
from pathlib import Path
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from ._test_support import ensure_ollama_importable
except ImportError:
    from _test_support import ensure_ollama_importable

ensure_ollama_importable()

import agent
import document_rag
import web_server


class AgentStatusTests(unittest.TestCase):
    @staticmethod
    def fake_embedding(model, input):
        return {
            "embeddings": [
                [0.0, 1.0] if "saturn" in text.casefold() else [1.0, 0.0]
                for text in input
            ]
        }

    def setUp(self):
        embedding_patcher = patch(
            "web_server.ollama.embed",
            side_effect=self.fake_embedding,
            create=True,
        )
        self.embedding_mock = embedding_patcher.start()
        self.addCleanup(embedding_patcher.stop)

    def test_product_pages_and_brand_asset_are_served_from_fixed_routes(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            expected = {
                "/": ("text/html", b"Make room for"),
                "/home": ("text/html", b"Make room for"),
                "/studio": ("text/html", b'class="app-shell"'),
                "/studio/": ("text/html", b'class="app-shell"'),
                "/about": ("text/html", b"Your model, your machine"),
                "/contact": ("text/html", b"Prepare a feedback note"),
                "/site.css": ("text/css", b"site-hero"),
                "/site.js": ("text/javascript", b"feedback-form"),
                "/assets/midnight-signal-logo.png": ("image/png", b"\x89PNG\r\n\x1a\n"),
            }
            for path, (content_type, marker) in expected.items():
                with self.subTest(path=path), urllib.request.urlopen(base_url + path) as response:
                    body = response.read()
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.headers["Content-Type"].startswith(content_type))
                    self.assertIn(marker, body)
                    if path in {"/studio", "/studio/"}:
                        self.assertIn(b'id="messages"', body)
                        self.assertIn(b'id="prompt-input"', body)
                        self.assertIn(b"What are we working on?", body)
                        self.assertIn(b'id="studio-empty-state"', body)
                        self.assertIn(b'aria-label="Public website"', body)
                        self.assertIn(b'href="/">Home page', body)
                        self.assertIn(b'id="settings-nav"', body)
                        self.assertNotIn(b"Big ideas,", body)
                        self.assertNotIn(b'id="welcome"', body)
                    elif path in {"/", "/home"}:
                        self.assertNotIn(b'class="app-shell"', body)
            with self.assertRaises(urllib.error.HTTPError) as response:
                urllib.request.urlopen(base_url + "/../README.md")
            self.assertEqual(response.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_model_picker_hides_deepseek_and_embedding_only_models(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            models = [
                {"model": "qwen3:14b"},
                {"model": "deepseek-coder-v2:16b"},
                {"model": "embeddinggemma:latest"},
                {"model": "huihui_ai/qwen2.5-coder-abliterate:7b"},
            ]
            with (
                patch("web_server.ollama.list", return_value={"models": models}),
                patch("web_server._model_capabilities", return_value=({"tools"}, None)),
            ):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/api/status"
                ) as response:
                    payload = json.loads(response.read())
            self.assertEqual(
                payload["models"],
                ["huihui_ai/qwen2.5-coder-abliterate:7b", "qwen3:14b"],
            )
            self.assertEqual(
                payload["recommended_agent_model"],
                "huihui_ai/qwen2.5-coder-abliterate:7b",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_mcp_status_reports_local_config_without_starting_servers(self):
        status = {
            "config_path": "C:\\Users\\tester\\AppData\\Roaming\\MidnightSignal\\mcp_servers.json",
            "configured_servers": ["local-search"],
            "sdk_available": True,
            "error": "",
        }
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch(
                "web_server.mcp_integration.configuration_summary",
                return_value=status,
            ) as summary:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/api/mcp-status"
                ) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), status)
                summary.assert_called_once_with()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_chat_api_rejects_hidden_chat_models(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({
                "model": "deepseek-coder-v2:16b",
                "messages": [{"role": "user", "content": "Hello"}],
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/chat",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request)
            self.assertEqual(rejected.exception.code, 400)
            self.assertIn("not available for chat", rejected.exception.read().decode())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_website_preview_is_workspace_scoped_and_sandboxed(self):
        with tempfile.TemporaryDirectory() as workspace:
            site = Path(workspace, "demo")
            site.mkdir()
            Path(site, "index.html").write_text(
                '<!doctype html><link rel="stylesheet" href="site.css"><h1>Preview</h1>',
                encoding="utf-8",
            )
            Path(site, "site.css").write_text("body { color: rebeccapurple; }", encoding="utf-8")
            Path(site, "private.env").write_text("not for preview", encoding="utf-8")
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}/api/site-preview/demo/"
                with patch.object(web_server, "_workspace_root", workspace):
                    with urllib.request.urlopen(base_url + "index.html") as response:
                        html = response.read()
                        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
                        self.assertIn("sandbox allow-scripts", response.headers["Content-Security-Policy"])
                        self.assertIn(b"<h1>Preview</h1>", html)
                    with urllib.request.urlopen(base_url + "site.css") as response:
                        self.assertTrue(response.headers["Content-Type"].startswith("text/css"))
                        self.assertIn(b"rebeccapurple", response.read())
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(base_url + "private.env")
                    self.assertEqual(rejected.exception.code, 415)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_agent_emits_a_preview_ready_event_for_generated_html(self):
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "index.html").write_text(
                "<!doctype html><title>Preview</title>", encoding="utf-8"
            )
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({
                    "model": "test-agent",
                    "messages": [{"role": "user", "content": "Build a website."}],
                }).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/agent",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                fake_events = iter([
                    agent.AgentEvent(
                        "tool_call",
                        name="create_website_entry",
                        args={"content": "<!doctype html>"},
                    ),
                    agent.AgentEvent(
                        "tool_result",
                        name="create_website_entry",
                        result="wrote 34 bytes to index.html",
                    ),
                    agent.AgentEvent("final", text="The page is ready."),
                ])
                with (
                    patch("web_server._workspace_root", workspace),
                    patch("web_server._model_capabilities", return_value=({"tools"}, None)),
                    patch("web_server.run_agent", return_value=fake_events),
                ):
                    with urllib.request.urlopen(request) as response:
                        events = [
                            json.loads(line)
                            for line in response.read().decode("utf-8").splitlines()
                        ]
                preview = next(event for event in events if event["type"] == "preview_ready")
                self.assertEqual(preview["path"], "index.html")
                website_file = next(
                    event for event in events
                    if event["type"] == "website_file_ready"
                )
                self.assertEqual(website_file["file_path"], "index.html")
                self.assertEqual(website_file["file_name"], "index.html")
                self.assertEqual(
                    website_file["download_url"],
                    "/api/file-download?path=index.html",
                )
                with patch("web_server._workspace_root", workspace):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{server.server_port}"
                        f"{website_file['download_url']}"
                    ) as response:
                        self.assertIn(
                            "attachment;", response.headers["Content-Disposition"]
                        )
                        self.assertIn(
                            "<title>Preview</title>", response.read().decode()
                        )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_agent_emits_a_download_event_for_verified_generated_documents(self):
        with tempfile.TemporaryDirectory() as workspace:
            report = Path(workspace, "reports", "summary.pdf")
            report.parent.mkdir()
            report.write_bytes(b"%PDF-test")
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({
                    "model": "test-agent",
                    "messages": [{"role": "user", "content": "Create a PDF report."}],
                }).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/agent",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                fake_events = iter([
                    agent.AgentEvent(
                        "tool_call",
                        name="generate_document",
                        args={"path": "reports/summary.pdf", "format": "pdf"},
                    ),
                    agent.AgentEvent(
                        "tool_result",
                        name="generate_document",
                        result="generated PDF document at reports/summary.pdf",
                    ),
                    agent.AgentEvent("final", text="The report is ready."),
                ])
                with (
                    patch("web_server._workspace_root", workspace),
                    patch("web_server._model_capabilities", return_value=({"tools"}, None)),
                    patch("web_server.run_agent", return_value=fake_events),
                ):
                    with urllib.request.urlopen(request) as response:
                        events = [
                            json.loads(line)
                            for line in response.read().decode("utf-8").splitlines()
                        ]
                download = next(event for event in events if event["type"] == "document_ready")
                self.assertEqual(download["document_path"], "reports/summary.pdf")
                self.assertEqual(download["document_name"], "summary.pdf")
                self.assertEqual(
                    download["download_url"],
                    "/api/file-download?path=reports%2Fsummary.pdf",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_document_embeddings_use_the_hidden_local_embedding_model(self):
        response = {"embeddings": [[0.25, -0.5]]}
        with patch("web_server.ollama.embed", return_value=response, create=True) as embed:
            vectors = web_server._embed_document("notes.txt", "Short local note.")
        self.assertEqual(vectors, [[0.25, -0.5]])
        embed.assert_called_once_with(
            model="embeddinggemma:latest",
            input=["Short local note."],
        )

    def test_packaged_project_tool_result_emits_download_ready_event(self):
        with tempfile.TemporaryDirectory() as workspace:
            archive_path = Path(workspace, "site", "garden.zip")
            archive_path.parent.mkdir()
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("index.html", "<h1>Garden</h1>")
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({
                    "model": "test-agent",
                    "messages": [{"role": "user", "content": "Build a website."}],
                }).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/agent",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                fake_events = iter([
                    agent.AgentEvent(
                        "tool_result",
                        name="package_project",
                        result="Project archive ready: site/garden.zip",
                    ),
                    agent.AgentEvent("final", text="The project is ready."),
                ])
                with (
                    patch("web_server._workspace_root", workspace),
                    patch("web_server._model_capabilities", return_value=({"tools"}, None)),
                    patch("web_server.run_agent", return_value=fake_events),
                ):
                    with urllib.request.urlopen(request) as response:
                        events = [
                            json.loads(line)
                            for line in response.read().decode("utf-8").splitlines()
                        ]
                download = next(event for event in events if event["type"] == "download_ready")
                self.assertEqual(download["archive_path"], "site/garden.zip")
                self.assertEqual(download["archive_name"], "garden.zip")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_packaged_project_result_without_archive_does_not_advertise_download(self):
        with tempfile.TemporaryDirectory() as workspace:
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({
                    "model": "test-agent",
                    "messages": [{"role": "user", "content": "Build a website."}],
                }).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/agent",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                fake_events = iter([
                    agent.AgentEvent(
                        "tool_result",
                        name="package_project",
                        result="Project archive ready: downloads/missing.zip",
                    ),
                    agent.AgentEvent("final", text="The project is ready."),
                ])
                with (
                    patch("web_server._workspace_root", workspace),
                    patch("web_server._model_capabilities", return_value=({"tools"}, None)),
                    patch("web_server.run_agent", return_value=fake_events),
                ):
                    with urllib.request.urlopen(request) as response:
                        events = [
                            json.loads(line)
                            for line in response.read().decode("utf-8").splitlines()
                        ]
                self.assertFalse(any(event["type"] == "download_ready" for event in events))
                package_result = next(
                    event for event in events
                    if event["type"] == "tool_result"
                    and event.get("name") == "package_project"
                )
                self.assertTrue(package_result["result"].startswith("error:"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_blank_attachment_request_is_rejected_with_clear_prompt(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "  ",
                    "attachments": [{
                        "name": "notes.txt",
                        "size": 4,
                        "content": "test",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/chat",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as response:
                urllib.request.urlopen(request)
            self.assertEqual(response.exception.code, 400)
            payload = json.loads(response.exception.read())
            self.assertIn("Add a request", payload["error"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_project_zip_download_is_scoped_to_selected_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            archive_path = Path(workspace, "site.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("index.html", "<h1>Ready</h1>")
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(web_server, "_workspace_root", workspace):
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{server.server_port}/api/download?path=site.zip",
                        headers={"Origin": f"http://127.0.0.1:{server.server_port}"},
                    )
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers["Content-Type"], "application/zip")
                        self.assertIn("attachment;", response.headers["Content-Disposition"])
                        with zipfile.ZipFile(io.BytesIO(response.read())) as downloaded:
                            self.assertEqual(downloaded.read("index.html"), b"<h1>Ready</h1>")

                    escaped = urllib.request.Request(
                        f"http://127.0.0.1:{server.server_port}/api/download?path=..%2Foutside.zip",
                        headers={"Origin": f"http://127.0.0.1:{server.server_port}"},
                    )
                    with self.assertRaises(urllib.error.HTTPError) as response:
                        urllib.request.urlopen(escaped)
                    self.assertEqual(response.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_agent_upload_context_explains_pdf_text_is_inline(self):
        from reportlab.pdfgen import canvas

        pdf_buffer = io.BytesIO()
        document = canvas.Canvas(pdf_buffer)
        document.drawString(72, 720, "Ohm's law: V = IR.")
        document.save()
        pdf_bytes = pdf_buffer.getvalue()
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({
                "model": "test-agent",
                "mode": "agent",
                "messages": [{
                    "role": "user",
                    "content": "What formula is in the attachment?",
                    "attachments": [{
                        "name": "formula.pdf",
                        "size": len(pdf_bytes),
                        "content": base64.b64encode(pdf_bytes).decode("ascii"),
                        "encoding": "base64",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/agent",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with (
                patch("web_server._model_capabilities", return_value=({"tools"}, None)),
                patch(
                    "web_server.run_agent",
                    return_value=iter([agent.AgentEvent("final", text="V = IR")]),
                ) as run_agent,
            ):
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    response.read()
            history = run_agent.call_args.kwargs["history"]
            self.assertIn("Relevant excerpts from locally indexed", history[0]["content"])
            self.assertIn("Do not use web search or workspace-reading tools", history[0]["content"])
            self.assertIn("Source: formula.pdf, Page 1", history[-1]["content"])
            self.assertIn("V = IR", history[-1]["content"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_first_lines_request_includes_verbatim_opening_lines(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        response = iter([{"message": {"content": "Here are the first lines."}, "done": True}])
        with (
            patch.object(web_server, "_document_index", document_rag.LocalDocumentIndex()),
            patch("web_server.ollama.chat", return_value=response) as chat,
        ):
            thread.start()
            try:
                source = "[Page 1]\nICSE CLASS 10 PHYSICS\n\nMoment = Force × distance\n"
                body = json.dumps({
                    "chat_id": "opening-lines",
                    "model": "midnight-signal:latest",
                    "messages": [{
                        "role": "user",
                        "content": "List the first 4 lines from this file.",
                        "attachments": [{
                            "name": "formula.txt",
                            "size": len(source.encode("utf-8")),
                            "content": source,
                            "encoding": "text",
                        }],
                    }],
                }).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/chat",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request) as http_response:
                    http_response.read()

                user_content = chat.call_args.kwargs["messages"][-1]["content"]
                self.assertIn("Preserve these source lines verbatim", user_content)
                self.assertIn("[Page 1]\nICSE CLASS 10 PHYSICS\n\nMoment = Force × distance", user_content)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_text_encoded_pdf_returns_refresh_message_instead_of_size_error(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "Read this PDF.",
                    "attachments": [{
                        "name": "formula.pdf",
                        "size": 79,
                        "content": "%PDF-1.7",
                        "encoding": "text",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/chat",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as response:
                urllib.request.urlopen(request)
            self.assertEqual(response.exception.code, 415)
            message = json.loads(response.exception.read())["error"]
            self.assertIn("Refresh Midnight Signal", message)
            self.assertNotIn("50 MB", message)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_server_extracts_text_from_uploaded_pdf_for_model_context(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("install project requirements to test PDF extraction")
        pdf_buffer = io.BytesIO()
        document = canvas.Canvas(pdf_buffer)
        document.drawString(72, 720, "Page one physics: V = IR.")
        document.showPage()
        document.drawString(72, 720, "Page two physics: P = VI.")
        document.save()
        pdf_bytes = pdf_buffer.getvalue()
        encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "Find the important formulas.",
                    "attachments": [{
                        "name": "physics.pdf",
                        "size": len(pdf_bytes),
                        "content": encoded_pdf,
                        "encoding": "base64",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/chat",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with patch(
                "web_server.ollama.chat",
                return_value=iter([{"message": {"content": "Found the formulas."}, "done": True}]),
            ) as chat:
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    response.read()
            forwarded = chat.call_args.kwargs["messages"][-1]["content"]
            self.assertIn("Source: physics.pdf, Page 1", forwarded)
            self.assertIn("Page one physics: V = IR.", forwarded)
            self.assertIn("Source: physics.pdf, Page 2", forwarded)
            self.assertIn("Page two physics: P = VI.", forwarded)
            self.assertNotIn(encoded_pdf, forwarded)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_pdf_extraction_reports_password_and_scanned_document_limits(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("install project requirements to test PDF extraction")
        empty_buffer = io.BytesIO()
        canvas.Canvas(empty_buffer).save()
        with self.assertRaisesRegex(web_server.PDFAttachmentError, "No readable text"):
            web_server._extract_pdf_text(empty_buffer.getvalue())
        with self.assertRaisesRegex(web_server.PDFAttachmentError, "valid PDF"):
            web_server._extract_pdf_text(b"not a PDF")

    def test_image_only_pdf_uses_local_ocr_and_keeps_page_number(self):
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        image = Image.new("RGB", (1200, 240), "white")
        font_path = Path(r"C:\Windows\Fonts\arial.ttf")
        font = (
            ImageFont.truetype(str(font_path), 52)
            if font_path.is_file()
            else ImageFont.load_default(size=52)
        )
        ImageDraw.Draw(image).text((35, 65), "ORBITAL PERIOD 365 DAYS", fill="black", font=font)
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        pdf_buffer = io.BytesIO()
        document = canvas.Canvas(pdf_buffer, pagesize=(900, 180))
        document.drawImage(
            ImageReader(io.BytesIO(image_buffer.getvalue())),
            0, 0, width=900, height=180,
        )
        document.save()

        extracted = web_server._extract_pdf_text(pdf_buffer.getvalue())
        self.assertIn("[Page 1]", extracted)
        self.assertIn("ORBITAL PERIOD", extracted.upper())
        self.assertIn("365", extracted)

    def test_attachment_rag_is_reused_for_followups_and_isolated_by_chat(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        responses = [
            iter([{"message": {"content": "Document received."}, "done": True}]),
            iter([{"message": {"content": "The resistance is 4 ohms."}, "done": True}]),
            iter([{"message": {"content": "No document was attached."}, "done": True}]),
        ]
        with patch.object(
            web_server,
            "_document_index",
            document_rag.LocalDocumentIndex(),
        ), patch("web_server.ollama.chat", side_effect=responses) as chat:
            thread.start()
            try:
                source = (
                    "Physics notes. The resistor has a resistance of 4 ohms. "
                    + "This is general reference material about circuits and measurements. " * 12
                    + "A separate section describes Saturn's rings."
                )

                def send(chat_id, messages):
                    body = json.dumps({
                        "chat_id": chat_id,
                        "model": "midnight-signal:latest",
                        "messages": messages,
                    }).encode("utf-8")
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{server.server_port}/api/chat",
                        data=body,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": f"http://127.0.0.1:{server.server_port}",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(request) as response:
                        response.read()

                send("chat-a", [{
                    "role": "user",
                    "content": "Keep this physics note for my next question.",
                    "attachments": [{
                        "name": "physics.txt",
                        "size": len(source.encode("utf-8")),
                        "content": source,
                        "encoding": "text",
                    }],
                }])
                send("chat-a", [
                    {"role": "user", "content": "Keep this physics note for my next question."},
                    {"role": "assistant", "content": "Document received."},
                    {"role": "user", "content": "What is the resistor's resistance?"},
                ])
                send("chat-b", [{
                    "role": "user",
                    "content": "What is the resistor's resistance?",
                }])

                followup = chat.call_args_list[1].kwargs["messages"][-1]["content"]
                other_chat = chat.call_args_list[2].kwargs["messages"][-1]["content"]
                self.assertIn("Source: physics.txt", followup)
                self.assertIn("4 ohms", followup)
                self.assertNotIn("Saturn", followup)
                self.assertNotIn("Source: physics.txt", other_chat)
                self.assertEqual(self.embedding_mock.call_count, 3)
                self.assertTrue(all(
                    call.kwargs["model"] == "embeddinggemma:latest"
                    for call in self.embedding_mock.call_args_list
                ))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_browser_upload_limit_is_100_mib_and_server_rejects_oversized_bodies(self):
        self.assertEqual(web_server.MAX_ATTACHMENT_BYTES, 100 * 1024 * 1024)
        self.assertEqual(
            web_server.MAX_REQUEST_BYTES,
            2 * web_server.MAX_ATTACHMENT_BYTES + web_server.MAX_REQUEST_OVERHEAD_BYTES,
        )
        self.assertGreater(
            web_server.MAX_REQUEST_BYTES,
            2 * web_server.MAX_ATTACHMENT_BYTES,
        )

        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=3
            )
            connection.putrequest("POST", "/api/chat")
            connection.putheader("Host", f"127.0.0.1:{server.server_port}")
            connection.putheader(
                "Origin", f"http://127.0.0.1:{server.server_port}"
            )
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(web_server.MAX_REQUEST_BYTES + 1))
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            self.assertIn("100 MiB", json.loads(response.read())["error"])
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_server_rejects_attachment_text_over_retrieval_limit(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            attachment_size = 50 * 1024 * 1024
            attachment_content = "x" * attachment_size
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "Read the attached file.",
                    "attachments": [{
                        "name": "maximum.txt",
                        "size": attachment_size,
                        "content": attachment_content,
                    }],
                }],
            }).encode("utf-8")
            self.assertGreater(len(body), attachment_size)
            self.assertLessEqual(len(body), web_server.MAX_REQUEST_BYTES)
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/chat",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with patch("web_server.ollama.chat") as chat:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 413)
                self.assertIn(
                    "12 MiB per-conversation retrieval limit",
                    error.exception.read().decode("utf-8"),
                )
                chat.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_server_rejects_attachments_over_100_mib(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/chat"
            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "Read the attached file.",
                    "attachments": [{
                        "name": "too-large.txt",
                        "size": web_server.MAX_ATTACHMENT_BYTES + 1,
                        "content": "",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request)
            self.assertEqual(rejected.exception.code, 413)
            self.assertIn("100 MiB", json.loads(rejected.exception.read())["error"])

            body = json.dumps({
                "messages": [{
                    "role": "user",
                    "content": "Read the attached file.",
                    "attachments": [{
                        "name": "oversized.txt",
                        "size": 1,
                        "content": "more bytes than declared",
                    }],
                }],
            }).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request)
            self.assertEqual(rejected.exception.code, 413)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_agent_response_events_are_streamed_without_a_duplicate_final(self):
        handler = object.__new__(web_server.MidnightSignalHandler)
        events = []
        agent_events = [
            agent.AgentEvent("response_token", text="A streamed response."),
            agent.AgentEvent("final", text="A streamed response."),
        ]
        with patch("web_server.run_agent", return_value=iter(agent_events)):
            handler._stream_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}],
                {},
                lambda event: events.append(event) or True,
            )

        self.assertEqual(
            [event for event in events if event.get("type") == "token"],
            [{"type": "token", "text": "A streamed response."}],
        )
        self.assertEqual(events[-1]["type"], "done")

    def test_agent_keeps_unlimited_reply_token_setting(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        captured_options = {}

        def capture_agent_stream(handler, model, messages, options, send_event, **kwargs):
            captured_options.update(options)
            send_event({"type": "done"})

        try:
            body = json.dumps({
                "model": "huihui_ai/qwen2.5-coder-abliterate:7b",
                "messages": [{"role": "user", "content": "Create a website"}],
                "options": {**web_server.app.DEFAULT_OPTIONS, "num_predict": -1},
            }).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/agent",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with (
                patch("web_server._model_capabilities", return_value=(["tools"], None)),
                patch.object(
                    web_server.MidnightSignalHandler,
                    "_stream_agent",
                    new=capture_agent_stream,
                ),
            ):
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    response.read()
            self.assertEqual(captured_options["num_predict"], -1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_step_limit_is_sent_as_a_user_visible_final_message(self):
        handler = object.__new__(web_server.MidnightSignalHandler)
        events = []
        with patch("web_server.run_agent", return_value=iter([
            agent.AgentEvent("step_limit", steps=24, text="Continue the task."),
        ])):
            handler._stream_agent(
                "qwen3:14b",
                [{"role": "system", "content": "system"}],
                {},
                lambda event: events.append(event) or True,
            )

        self.assertIn(
            {"type": "step_limit", "text": "Continue the task."},
            events,
        )

    def test_agent_status_uses_friendly_progress_copy(self):
        self.assertEqual(
            web_server._agent_status_text("thinking", "qwen3:14b"),
            "Gathering the pieces for your next step…",
        )
        self.assertEqual(
            web_server._agent_status_text("reasoning_progress", "qwen3:14b"),
            "Connecting the details…",
        )

    def test_agent_status_ignores_unrecognized_events(self):
        self.assertEqual(web_server._agent_status_text("tool_result", "qwen3:14b"), "")

    def test_agent_prompt_skips_generic_chat_guidance_but_keeps_security_rules(self):
        compact = web_server.app.load_system_prompt(
            "agent", include_response_guidance=False
        )
        standard = web_server.app.load_system_prompt("agent")

        self.assertIn("structured workspace tools", compact)
        self.assertIn("sensible content and visual direction", compact)
        self.assertIn("placeholder links", compact)
        self.assertIn("self-contained index.html with inline CSS and JavaScript", compact)
        self.assertIn("do not invent extra HTML pages", compact)
        self.assertIn("create every referenced file", compact)
        self.assertIn("server-side behavior", compact)
        self.assertIn("Ask one focused question only", compact)
        self.assertIn("support factual claims with Markdown links to the source URLs", compact)
        self.assertIn(web_server.app.security.SECURITY_PREAMBLE, compact)
        self.assertNotIn("RESPONSE LENGTH", compact)
        self.assertIn("RESPONSE LENGTH", standard)

    def test_origin_and_host_checks_reject_cross_site_and_dns_rebinding_hosts(self):
        self.assertTrue(web_server._is_local_host("127.0.0.1:8765", 8765))
        self.assertTrue(web_server._is_local_host("localhost:8765", 8765))
        self.assertFalse(web_server._is_local_host("attacker.example:8765", 8765))
        self.assertFalse(web_server._is_local_host("127.0.0.1:8766", 8765))
        self.assertTrue(web_server._is_trusted_origin("http://127.0.0.1:8765", 8765))
        self.assertFalse(web_server._is_trusted_origin("https://127.0.0.1:8765", 8765))
        self.assertFalse(web_server._is_trusted_origin("http://attacker.example:8765", 8765))
        self.assertFalse(web_server._is_trusted_origin("null", 8765))

    def test_phone_access_accepts_only_private_ip_hosts_and_matching_origins(self):
        self.assertTrue(web_server._is_lan_host("192.168.1.42:8765", 8765))
        self.assertTrue(web_server._is_lan_host("10.0.0.2:8765", 8765))
        self.assertFalse(web_server._is_lan_host("example.com:8765", 8765))
        self.assertFalse(web_server._is_lan_host("8.8.8.8:8765", 8765))
        self.assertFalse(web_server._is_lan_host("169.254.1.2:8765", 8765))
        self.assertTrue(web_server._is_lan_origin(
            "http://192.168.1.42:8765", 8765, "192.168.1.42"
        ))
        self.assertFalse(web_server._is_lan_origin(
            "http://192.168.1.43:8765", 8765, "192.168.1.42"
        ))
        self.assertFalse(web_server._is_lan_origin(
            "http://example.com:8765", 8765, "192.168.1.42"
        ))

    def test_lan_api_requires_valid_session_cookie_or_token_header(self):
        handler = object.__new__(web_server.MidnightSignalHandler)
        handler.client_address = ("192.168.1.15", 40000)
        handler.server = SimpleNamespace(
            server_port=8765,
            allow_lan=True,
            access_token="private-token",
        )
        handler.headers = Message()

        self.assertTrue(handler._is_lan_request())
        self.assertFalse(handler._lan_authorized())
        handler.headers["Cookie"] = "midnight_access=private-token"
        self.assertTrue(handler._lan_authorized())
        handler.headers.replace_header("Cookie", "midnight_access=wrong-token")
        self.assertFalse(handler._lan_authorized())
        handler.headers["X-Midnight-Access"] = "private-token"
        self.assertTrue(handler._lan_authorized())
        handler.headers.replace_header("X-Midnight-Access", "wrong-token")
        self.assertFalse(handler._lan_authorized())

    def test_lan_access_link_sets_cookie_and_unlocks_browser_api(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        server.allow_lan = True
        server.access_token = "test-access-token"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        host = f"192.168.1.42:{port}"
        try:
            with patch.object(
                web_server.MidnightSignalHandler, "_is_lan_request", return_value=True
            ), patch("web_server.ollama.list", return_value={"models": []}):
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request(
                    "GET",
                    "/?access=test-access-token",
                    headers={"Host": host},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 303)
                self.assertEqual(
                    response.getheader("Location"),
                    "/studio/#midnight-access=test-access-token",
                )
                set_cookie = response.getheader("Set-Cookie")
                self.assertIn("SameSite=Lax", set_cookie)
                cookie = set_cookie.split(";", 1)[0]
                response.read()

                connection.request(
                    "GET", "/studio/", headers={"Host": host, "Cookie": cookie}
                )
                landing = connection.getresponse()
                self.assertEqual(landing.status, 200)
                self.assertEqual(landing.getheader("Content-Type"), "text/html; charset=utf-8")
                self.assertIn(b"/app.js", landing.read())

                connection.request(
                    "GET", "/?access=stale-token", headers={"Host": host}
                )
                stale_link = connection.getresponse()
                self.assertEqual(stale_link.status, 403)
                stale_link.read()

                connection.request("GET", "/api/status", headers={"Host": host})
                unauthorized = connection.getresponse()
                self.assertEqual(unauthorized.status, 403)
                unauthorized.read()

                connection.request(
                    "GET", "/api/status",
                    headers={"Host": host, "Cookie": cookie},
                )
                authorized = connection.getresponse()
                self.assertEqual(authorized.status, 200)
                self.assertEqual(json.loads(authorized.read())["models"], [])

                connection.request(
                    "GET",
                    "/api/status",
                    headers={
                        "Host": host,
                        "X-Midnight-Access": "test-access-token",
                    },
                )
                header_authorized = connection.getresponse()
                self.assertEqual(header_authorized.status, 200)
                header_authorized.read()
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_confirmation_timeout_is_configurable_and_bounded(self):
        with patch.dict("os.environ", {"MIDNIGHT_SIGNAL_CONFIRMATION_TIMEOUT": "900"}):
            self.assertEqual(web_server._configured_confirmation_timeout(), 900)
        with patch.dict("os.environ", {"MIDNIGHT_SIGNAL_CONFIRMATION_TIMEOUT": "10"}):
            self.assertEqual(web_server._configured_confirmation_timeout(), 600)
        with patch.dict("os.environ", {"MIDNIGHT_SIGNAL_CONFIRMATION_TIMEOUT": "not-a-number"}):
            self.assertEqual(web_server._configured_confirmation_timeout(), 600)

    def test_phone_access_url_formats_ipv6_hosts(self):
        self.assertEqual(web_server._format_url_host("192.168.1.20"), "192.168.1.20")
        self.assertEqual(web_server._format_url_host("fd00::20"), "[fd00::20]")

    def test_private_lan_address_prefers_active_default_route(self):
        route_socket = Mock()
        route_socket.getsockname.return_value = ("192.168.29.21", 0)
        with patch("web_server.socket.socket", return_value=route_socket):
            self.assertEqual(web_server._private_lan_addresses(), ["192.168.29.21"])
        route_socket.close.assert_called_once()

    def test_mobile_qr_only_serves_current_phone_access_url(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        previous_mobile_server = web_server._mobile_server
        fake_mobile_server = SimpleNamespace(
            allow_lan=True, access_token="active-token", server_port=8766
        )
        active_url = "http://192.168.1.20:8766/?access=active-token"
        web_server._mobile_server = fake_mobile_server
        try:
            with patch("web_server._private_lan_addresses", return_value=["192.168.1.20"]), \
                    patch("web_server._mobile_qr_svg", return_value=b"<svg></svg>") as make_qr:
                request_url = (
                    f"http://127.0.0.1:{server.server_port}/api/mobile-qr"
                    f"?url={urllib.parse.quote(active_url, safe='')}"
                )
                with urllib.request.urlopen(request_url) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                    self.assertEqual(response.read(), b"<svg></svg>")
                make_qr.assert_called_once_with(active_url)
        finally:
            web_server._mobile_server = previous_mobile_server
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_conversation_title_endpoint_uses_local_model(self):
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/title",
                data=json.dumps({
                    "model": "qwen3:14b",
                    "prompt": "Explain how the workspace browser works",
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{server.server_port}",
                },
                method="POST",
            )
            with patch(
                "web_server.ollama.chat",
                return_value={"message": {"content": '"Workspace Browser Guide"'}},
            ) as generate:
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["title"], "Workspace Browser Guide")
                generate.assert_called_once()
                self.assertIs(generate.call_args.kwargs["think"], False)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_workspace_browser_lists_previews_and_downloads_scoped_files(self):
        with tempfile.TemporaryDirectory() as workspace:
            subfolder = Path(workspace, "site")
            subfolder.mkdir()
            (subfolder / "index.html").write_text("<h1>Ready</h1>", encoding="utf-8")
            (subfolder / "project.zip").write_bytes(b"PK\x03\x04test")
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                with patch.object(web_server, "_workspace_root", workspace):
                    listing = urllib.request.Request(
                        f"{origin}/api/files",
                        headers={"Origin": origin},
                    )
                    with urllib.request.urlopen(listing) as response:
                        entries = json.loads(response.read())["entries"]
                    self.assertEqual(entries[0]["name"], "site")
                    self.assertEqual(entries[0]["type"], "directory")

                    preview = urllib.request.Request(
                        f"{origin}/api/file-preview?path=site%2Findex.html",
                        headers={"Origin": origin},
                    )
                    with urllib.request.urlopen(preview) as response:
                        self.assertEqual(
                            json.loads(response.read())["content"], "<h1>Ready</h1>"
                        )

                    download = urllib.request.Request(
                        f"{origin}/api/file-download?path=site%2Fproject.zip",
                        headers={"Origin": origin},
                    )
                    with urllib.request.urlopen(download) as response:
                        self.assertEqual(response.read(), b"PK\x03\x04test")
                        self.assertIn("attachment;", response.headers["Content-Disposition"])

                    escaped = urllib.request.Request(
                        f"{origin}/api/files?path=..%2Foutside",
                        headers={"Origin": origin},
                    )
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(escaped)
                    self.assertEqual(rejected.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_agent_file_undo_restores_only_when_agent_version_is_unchanged(self):
        with tempfile.TemporaryDirectory() as workspace:
            server = web_server.ThreadingHTTPServer(
                ("127.0.0.1", 0), web_server.MidnightSignalHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                with patch.object(web_server, "_workspace_root", workspace):
                    target = Path(workspace, "change.txt")
                    target.write_text("before", encoding="utf-8")
                    before = web_server._capture_undo_before(workspace, "change.txt")
                    target.write_text("after", encoding="utf-8")
                    token = web_server._store_undo_snapshot(workspace, before, str(target))
                    request = urllib.request.Request(
                        f"{origin}/api/undo",
                        data=json.dumps({"id": token}).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Origin": origin,
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(json.loads(response.read())["undone"], "change.txt")
                    self.assertEqual(target.read_text(encoding="utf-8"), "before")

                    before = web_server._capture_undo_before(workspace, "change.txt")
                    target.write_text("agent version", encoding="utf-8")
                    token = web_server._store_undo_snapshot(workspace, before, str(target))
                    target.write_text("user edit", encoding="utf-8")
                    stale = urllib.request.Request(
                        f"{origin}/api/undo",
                        data=json.dumps({"id": token}).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Origin": origin,
                        },
                        method="POST",
                    )
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(stale)
                    self.assertEqual(rejected.exception.code, 409)
                    self.assertEqual(target.read_text(encoding="utf-8"), "user edit")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_agent_stream_emits_undo_action_after_confirmed_file_write(self):
        with tempfile.TemporaryDirectory() as workspace:
            target = Path(workspace, "created.txt")

            def fake_run_agent(**kwargs):
                args = {"path": "created.txt", "content": "new content"}
                yield agent.AgentEvent("tool_call", name="write_file", args=args)
                self.assertTrue(kwargs["confirm_fn"]("create file", "created.txt", "new content"))
                target.write_text("new content", encoding="utf-8")
                yield agent.AgentEvent(
                    "tool_result", name="write_file", result="wrote 11 bytes to created.txt"
                )
                yield agent.AgentEvent("final", text="The file is ready.")

            events = []
            with (
                patch.object(web_server, "_workspace_root", workspace),
                patch("web_server.run_agent", side_effect=fake_run_agent),
            ):
                web_server.MidnightSignalHandler._stream_agent(
                    None,
                    "test-model",
                    [{"role": "user", "content": "Create a file."}],
                    {"permission_mode": "allow_all"},
                    events.append,
                )

            tool_result = next(event for event in events if event["type"] == "tool_result")
            self.assertEqual(tool_result["changed_path"], "created.txt")
            self.assertRegex(tool_result["undo_id"], r"^[a-f0-9]{32}$")
            self.assertTrue(target.exists())
            self.assertEqual(
                web_server._restore_undo_snapshot(tool_result["undo_id"], workspace),
                "created.txt",
            )
            self.assertFalse(target.exists())

    def test_capability_errors_are_not_cached(self):
        web_server._model_capability_cache.clear()
        with patch("web_server.ollama.show", side_effect=[
            RuntimeError("temporary Ollama failure"),
            {"capabilities": ["tools"]},
        ]) as show:
            failed = web_server._model_capabilities("test-model")
            recovered = web_server._model_capabilities("test-model")
        self.assertEqual(failed[0], [])
        self.assertIn("temporary", failed[1])
        self.assertEqual(recovered, (["tools"], ""))
        self.assertEqual(show.call_count, 2)

    def test_chat_continues_only_when_model_reports_generation_limit(self):
        self.assertTrue(web_server.app._reply_needs_continuation("cut off", "length"))
        for text in ("Reply ends in a comma,", "The next word is to", "```js\nunfinished"):
            with self.subTest(text=text):
                self.assertFalse(web_server.app._reply_needs_continuation(text, "stop"))

    def test_default_workspace_is_separate_and_selected_workspace_persists(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as root:
            default_root = web_server._default_workspace_root(home)
            self.assertEqual(
                default_root,
                str(Path(home) / "Documents" / "Midnight Signal Workspace"),
            )
            self.assertNotEqual(
                os.path.realpath(default_root),
                os.path.realpath(web_server.app.SCRIPT_DIR),
            )

            settings_path = str(Path(home) / "config" / "workspace.json")
            missing_settings = str(Path(home) / "config" / "missing.json")
            self.assertEqual(
                web_server._load_workspace_root(missing_settings, home),
                default_root,
            )
            web_server._persist_workspace_root(root, settings_path)
            self.assertEqual(web_server._load_workspace_root(settings_path), root)

    def test_server_startup_creates_the_configured_workspace(self):
        with tempfile.TemporaryDirectory() as home:
            workspace = Path(web_server._default_workspace_root(home))
            with patch.object(web_server, "_workspace_root", str(workspace)), \
                    patch("web_server.ThreadingHTTPServer") as server_factory, \
                    patch("web_server.threading.Timer"), \
                    patch("web_server.webbrowser.open"), \
                    patch("web_server._stop_mobile_access"):
                server = server_factory.return_value
                server.server_port = 8770
                server.serve_forever.side_effect = KeyboardInterrupt
                web_server.serve()
            self.assertTrue(workspace.is_dir())

    def test_workspace_api_rejects_cross_site_requests_and_accepts_local_choice(self):
        server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.MidnightSignalHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original_root = web_server._workspace_root
        persist_patcher = patch("web_server._persist_workspace_root")
        persist_workspace = persist_patcher.start()
        url = f"http://127.0.0.1:{server.server_port}/api/workspace"
        try:
            request = urllib.request.Request(
                url,
                data=b'{"path":"."}',
                headers={
                    "Content-Type": "application/json",
                    "Origin": "http://attacker.example",
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request)
            self.assertEqual(rejected.exception.code, 403)
            self.assertEqual(web_server._workspace_root, original_root)

            with tempfile.TemporaryDirectory() as root:
                body = json.dumps({"path": root}).encode("utf-8")
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{server.server_port}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.loads(response.read())["workspace"], root)
                self.assertEqual(web_server._workspace_root, root)
                persist_workspace.assert_called_once_with(root)
        finally:
            web_server._workspace_root = original_root
            persist_patcher.stop()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_phone_access_is_started_for_local_ui_and_can_be_revoked(self):
        web_server._stop_mobile_access(SimpleNamespace(allow_lan=False))
        server = web_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), web_server.MidnightSignalHandler
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api/mobile-access"
        origin = f"http://127.0.0.1:{server.server_port}"

        def post(action, request_origin=origin):
            request = urllib.request.Request(
                url,
                data=json.dumps({"action": action}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Origin": request_origin,
                },
                method="POST",
            )
            return urllib.request.urlopen(request)

        try:
            with patch("web_server._private_lan_addresses", return_value=["192.168.1.20"]):
                with post("start") as response:
                    started = json.loads(response.read())
                self.assertTrue(started["enabled"])
                self.assertEqual(len(started["links"]), 1)
                self.assertIn("192.168.1.20:", started["links"][0])
                self.assertIn("access=", started["links"][0])
                self.assertIsNotNone(web_server._mobile_server)

                with post("status") as response:
                    self.assertEqual(json.loads(response.read()), started)

                with post("stop") as response:
                    stopped = json.loads(response.read())
                self.assertEqual(stopped, {"enabled": False, "links": []})
                self.assertIsNone(web_server._mobile_server)

            with self.assertRaises(urllib.error.HTTPError) as rejected:
                post("start", "http://attacker.example")
            self.assertEqual(rejected.exception.code, 403)
        finally:
            web_server._stop_mobile_access(server)
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
