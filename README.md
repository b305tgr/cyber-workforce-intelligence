<div align="center">

# 🌒 Midnight Signal

**A cinematic, local terminal AI — built on Ollama.**

Created by **Aditya Tomar**.

True word-by-word streaming, a live truecolor gradient UI with switchable
themes, synthesized sound effects, persistent sessions, a project
**radar** scanner, live model/sampling controls, and a real tool-calling
**agent mode** that reads, writes, edits files, runs shell commands, and
inspects git — with confirmation prompts and an optional "yolo" mode.

[![Base model](https://img.shields.io/badge/base%20model-qwen2.5--coder--abliterate%3A7b-orange)](#)
[![Runs on](https://img.shields.io/badge/runs%20on-Ollama-black)](#)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-blue)](#)
[![License](https://img.shields.io/badge/uncensored-by%20design-red)](#)

</div>

---

> **Unrestricted by design.** This is the core idea behind Midnight Signal:
> it runs on an **abliterated** base model, and the system prompts add no
> refusal language, no safety lecturing, and no filtering on top of it.
> Ask it anything — you get the model's own answer, not a wrapper's opinion
> of what you're allowed to ask. No leash, no filter, fully local.

**Base model:** `huihui_ai/qwen2.5-coder-abliterate:7b`

## Project handoff and roadmap — 2026-10-20

This section is the current project handoff. Read it before changing code,
preserve existing user work, and update this section and its checklist when
work is completed. The roadmap is **not complete**; do not skip tests or claim
unverified work.

### Product and architecture context

- Midnight Signal is a local-first Python/Ollama application with a terminal
  interface and a vanilla JavaScript/CSS browser interface. The browser backend
  and API routes are in `web_server.py`; browser files are in `web/`; agent
  policy/tool selection and streaming are mainly in `agent.py`; tool schemas
  and workspace/web operations are in `tools.py`; agent policy is also in
  `system_prompts/agent.txt`.
- The default web server binds to `127.0.0.1:8765`. Phone access is an optional,
  temporary, token-protected private-LAN listener. Keep localhost-only as the
  default, retain origin/host checks, and do not weaken the trusted-network
  safeguards.
- The browser stores conversations and preferences locally. Attachments are
  limited to five files and 100 MiB total. PDFs are extracted locally with
  `pypdf`; image-only pages use local PyMuPDF/RapidOCR OCR. Extracted text is
  indexed locally for bounded, chat-scoped retrieval. EmbeddingGemma provides
  semantic ranking when available; keyword ranking is the local fallback.
- Models present during the latest local check: `embeddinggemma:latest`,
  `ministral-3:8b`, `midnight-signal:latest`, `qwen3:14b`,
  `deepseek-coder-v2:16b`, and
  `huihui_ai/qwen2.5-coder-abliterate:7b`. Availability depends on the local
  Ollama installation. DeepSeek and embedding-only models are intentionally
  excluded from the browser chat model picker.
- Keep changes focused, preserve the terminal UI, avoid adding dependencies
  unless necessary, and update tests and this status section with each
  completed roadmap item.

### Product-overhaul checklist

- **COMPLETE** — `/` is the public product homepage; About and Contact remain
  separate pages; `/studio` opens directly into the chat workspace, without
  embedding a duplicate public homepage or marketing welcome screen. Phone-
  access redirects open Studio directly.
- **COMPLETE** — DeepSeek and EmbeddingGemma are hidden from the chat model
  picker. This does not uninstall or modify any model in Ollama.
- **COMPLETE** — Agent progress uses concise, task-focused status copy rather
  than exposing a model-waiting message; the Studio empty chat now has its own
  compact animated intro and animated progress indicator, separate from the
  public homepage.
- **COMPLETE** — Show generated HTML pages in a sandboxed chat preview, provide
  a verified workspace-scoped HTML download, and retain ZIP downloads when
  requested.
- **COMPLETE** — Surface successfully generated PDF and DOCX files as
  workspace-scoped download links in the chat.
- **COMPLETE** — Use local `embeddinggemma` for document retrieval when
  available, without listing it as a chat model; show when the workflow falls
  back to keyword search. The selected generative model authors document
  content because embedding models cannot write prose or produce DOCX/PDF
  files.
- **COMPLETE** — Improve settings with clearer sampling help, reliable scrolling,
  and accessible MCP configuration and warning status. Desktop settings content
  is browser-verified; the broader mobile/accessibility review remains open.
- **COMPLETE** — Add opt-in stdio MCP client support through the official
  Python SDK. Configured MCP calls require existing user approval; no external
  server is enabled by default.
- **IN PROGRESS** — The local Qwen 2.5 full-stack trial still does not complete.
  The Epson website trial created `index.html`, CSS, and JavaScript, but the
  HTML contained an escaped script URL and omitted the mobile viewport; the
  model stopped before repairing either issue, and no backend, tests, or ZIP
  were produced. Safe local repairs for those exact validation findings now
  have regression coverage, but the live Qwen trial has not yet been rerun.
  In a separate Epson trial, `midnight-signal:latest` generated the site files
  and passed `validate_website` with no issues.

### Implemented so far

- Major Studio visual refresh: warm orange/copper accent system, espresso
  sidebar, redesigned split hero, clearer prompt-card hierarchy, refined
  composer, and coordinated settings surfaces. The public Home/About/Contact
  pages use the same warm orange palette. Browser geometry checks found no
  horizontal overflow at 320, 390, or 1440px.
- Browser app foundations also include custom keyboard-operable mode/model
  pickers, sampling and appearance settings, themes, command palette and slash
  commands, responsive styling, and font loading with system fallbacks.
- The Settings drawer explains the sampling controls, keeps its sticky action
  bar from obscuring the last options, and reports MCP configuration state.
  Keyboard and mobile layout checks are recorded in the latest validation.
- Optional local MCP integration uses the official `mcp` Python SDK over
  stdio. Configure trusted servers in the path shown under
  **Settings → External tools · MCP** using a JSON object shaped like:

  ```json
  {
    "servers": [
      {
        "name": "my-tools",
        "command": "python",
        "args": ["C:\\path\\to\\mcp_server.py"],
        "env": {},
        "cwd": "C:\\path\\to"
      }
    ]
  }
  ```

  Restart Studio after updating the file. Configured MCP processes are launched
  only when Coding agent mode needs tools. Each MCP call uses the existing
  approval flow; **Allow all** also permits MCP calls without prompts. MCP
  servers are powerful local processes and are not confined to the selected
  workspace, so only configure servers and actions you trust. No server or
  third-party account is enabled automatically. The `mcp` dependency is
  installed only on Python 3.10+; older supported Python versions retain the
  built-in tool set without MCP.
- Added a public home page at `/`, standalone About and Contact pages, shared
  responsive site styling, a separate Studio at `/studio`, and a locally
  generated PNG brand mark.
  The feedback form only prepares a local text note and does not submit data.
  New routes and the PNG asset use an explicit server allowlist.
- Local chat, saved conversation history, retry/continue actions, prompt copy
  and edit/resend, response regeneration with up to five browsable versions,
  chat pin/archive/filter/restore/branch, editable prompt templates, and
  attachment previews.
- Browser uploads support five files and 100 MiB total. PDF data is sent
  without the earlier base64/text size corruption; selectable PDF text is
  extracted locally. Attaching a file without a prompt asks for intent and
  does not submit an assumed task.
- The agent prompt and tool filtering distinguish chat/research/file-analysis
  requests from explicit workspace changes. Workspace mutations are intended
  only for direct workspace-change requests. Analytical/question wording is
  excluded from the tool-intent retry path, and regression cases cover common
  website/HTML question phrases. Continue expanding this coverage when new
  misclassifications are reported.
- The Coding agent can inspect a workspace, review Git changes, make approved
  file changes, and package explicitly selected project files into a
  workspace-scoped downloadable ZIP. Successfully generated PDF/DOCX
  documents are verified inside the selected workspace and surfaced as chat
  downloads. Website instructions call for complete, runnable results,
  validation, and ZIP packaging when a multi-file project is appropriate.
  Generated HTML files can also be previewed inside chat in a sandboxed
  frame; the workspace path is restricted, and the preview CSP blocks network
  connections and form submission.
- Scanned PDFs can be OCR'd locally with PyMuPDF and RapidOCR (up to 50
  image-only pages per PDF); selectable text continues to use `pypdf`.
  Attachment excerpts are indexed in memory per conversation and retrieved
  locally with EmbeddingGemma semantic ranking when installed, with source and
  page labels. If the model is unavailable, the UI says it is using local
  keyword ranking. The index is
  bounded, expires after two hours of inactivity, and is cleared when the
  server restarts.
- The workspace browser supports bounded directory listings, text preview,
  download, and read-only Git review. Guarded Undo can reverse eligible agent
  writes/edits only when the file still matches the captured post-change
  version; it refuses stale changes.
- Phone-access dialog starts/stops the temporary private-network listener,
  displays a locally generated QR for each current one-time URL, and keeps a
  copyable link as a fallback. Address discovery prefers the active default
  network route to avoid advertising virtual-adapter addresses. The one-time
  landing cookie uses `SameSite=Lax`; a short-lived tab session also carries the
  access token in a same-origin request header as a fallback for phone browsers
  that reject the redirect cookie. Cross-site requests remain rejected.
  Expired or unauthorized sessions tell the user to scan a fresh code.
  The current PC's Wi-Fi profile was detected as **Public**, which can also
  block inbound connections until the trusted Wi-Fi profile is changed to
  Private and Python is allowed through Windows Firewall on Private networks
  only.
- New conversations asynchronously request a concise title from the selected
  local Ollama model after the first successful answer. If title generation
  fails, the chat remains "New conversation"; manually renamed titles are not
  overwritten.
- Agent activity cards can be collapsed after work completes, remain expanded
  when an approval is needed or an action is active, and show clickable links
  for web-search/fetch results.
- Agent stream recovery, error messages, and unfinished trailing Markdown
  marker handling have been improved. These areas still need the broader
  audit listed below.
- Generated HTML artifacts that were in the repository root were moved to
  `samples/`; do not put generated sample websites or test output back in the
  project root.

### Completed in the latest UI/phone pass

- Added a locally generated, revocable phone QR code and fixed phone links to
  prefer the active Wi-Fi route. Added phone troubleshooting steps for trusted
  Wi-Fi, Windows Private network profile/firewall, and router client isolation.
- Changed the phone access cookie to `SameSite=Lax` so a top-level scan-link
  redirect can establish the session; unauthorized-session messaging now asks
  the user to reopen the current QR/link.
- Removed prompt-snippet conversation titles. New chats request a short title
  from the selected local model after a successful first response, without
  delaying that response or overriding a manual rename.
- Tightened the Coding agent's workspace-mutation heuristic so question,
  analysis, and research phrasing does not enable write tools; expanded prompt
  regression cases.
- Made completed agent activity collapsible and web search/fetch URLs clickable.
- QR SVG creation, active-link validation, default-route address preference,
  title endpoint, read-only intent, and cookie behavior have regression tests.
  Browser verification confirmed the QR loads and fits at 320px; physical phone
  access still needs to be checked after the Windows network/firewall settings
  are corrected.

### Earlier verification baseline

- Python suite: **129 tests passed, 1 skipped** (`.venv\Scripts\python.exe -m
  unittest discover -s tests -v`).
- Python compilation for the touched implementation and test modules,
  `node --check web\app.js`, and `git diff --check` passed after the final
  website-interaction and document-generation changes.
- PDF extraction/page-label tests (4) and document-generation tests (3) passed.
  Both target models answered a page-labeled PDF analysis prompt correctly.
- A controlled browser check verified the approved-write/Undo flow restores
  the original file. The latest custom-model multi-file ZIP passed structural
  validation and integrity checks, as detailed below.
- Browser checks exercised phone start/link/revoke, response-version browsing,
  attachment preview, and no horizontal overflow at 320px. Earlier checks
  exercised prompt copy/edit, conversation organization, templates, and
  attachment-only intent behavior. A live Qwen3 title was generated and
  persisted after reload; a delayed-title browser simulation confirmed a
  manual rename is retained, and a simulated HTTP 503 leaves the default
  "New conversation" title intact.
- Existing live checks with both `huihui_ai/qwen2.5-coder-abliterate:7b` and
  `midnight-signal:latest` created and validated a self-contained cafe website.
  ZIP tool/download behavior was checked separately.
- Latest isolated multi-file trials with both `midnight-signal:latest` and
  `huihui_ai/qwen2.5-coder-abliterate:7b` produced `index.html`,
  `assets/site.css`, `assets/site.js`, and an integrity-checked ZIP. The
  request-specific validator requires search/filter handlers and native
  favorite buttons with a toggling state; incomplete results are sent through
  the repair path and cannot be packaged as complete.
- Browser smoke tests on each model's exact generated site confirmed the
  search returns one matching event and zero for a non-match. Clicking a
  favorite button changes its `aria-pressed` state and visible styling while
  preserving the event title. The archive contents and ZIP integrity were
  also checked for both trials.
- Both target models also generated a one-page PDF through the agent from a
  prompt requiring a title, introduction, and exactly four checklist items.
  `pypdf` verified the PDF signature, one-page output, and extracted content;
  requested exact list counts are checked before a file is written. PDF-only
  requests expose only the document-generation tool and finish after a
  successful output, preventing repeated calls from overwriting the document.
- Selectable-text PDF uploads now include explicit `[Page N]` markers in the
  local model context. Both target models answered a page-labeled Ohm's-law
  question correctly (3 A, citing page 1). Local OCR and chat-scoped retrieval
  now cover image-only pages and follow-up questions without re-uploading.
  OCR output and retrieved excerpts are local, bounded, and labeled with
  source pages when available.
- Phone access has not been verified from a separate physical phone. The
  machine's Wi-Fi network profile is currently Public; advise switching it to
  Private only when it is a trusted network, then allow Python through the
  firewall on Private networks. A full mobile-device and accessibility audit
  has not been completed.

### Completed after the handoff

- Rechecked workspace intent filtering and defensive tool dispatch together.
  New regression tests cover questions, explanations, web lookup, website
  analysis, and attachment questions attempting all five mutating tools; none
  are exposed or executed, and no files are created. An explicit file-creation
  request still exposes and dispatches the write tool. No user reproduction of
  the earlier unwanted `index.html` creation was available, so its original
  cause remains unknown.
- Fixed agent streaming to flush buffered partial response text after a
  disconnect, while still checking the complete text for internal-content
  leakage. A disconnect regression test verifies the full partial text remains
  visible alongside the actionable error.
- Fixed the browser header at viewports up to 380px by wrapping actions onto a
  second row. Browser checks at 320px verified no horizontal overflow and
  keyboard access to the workspace browser. Code-copy buttons now have
  language-specific screen-reader names and announce successful copying.
- Added source previews to web search results and agent guidance to cite source
  titles and URLs. Agent activity now distinguishes failed, approval-pending,
  declined, and expired states; code-copy controls also announce successful
  copies accessibly.
- Verified title race and failure behavior in the browser: a manually entered
  title survives a delayed generated-title response, and a simulated HTTP 503
  leaves the default title unchanged. A real Qwen3-generated title persisted
  across reload.
- Fixed website ZIP delivery reliability: website validation now runs before a
  `package_project` request is allowed to create an archive, and an explicitly
  requested ZIP cannot be reported complete unless packaging succeeds.
  Regression tests cover refusing an invalid site archive, allowing packaging
  after repair, and refusing false ZIP-completion claims.
- Completed an isolated multi-file packaging check. A Qwen3-generated site was
  repaired with workspace-scoped file tools, passed website validation, and
  was repackaged into an integrity-checked ZIP containing exactly the four
  project files. The browser rendered the site, event buttons populated the
  RSVP form, local-only confirmation worked, and the 320px layout had no
  horizontal overflow. The app endpoint returned the exact ZIP with correct
  attachment headers; browser-native download completion remains unverified.
- An earlier Qwen2.5 multi-file/ZIP trial passed structural checks but lacked
  meaningful behavior. A single-page smoke test passed validation and
  packaging, but the later larger multi-page and full-stack trials failed to
  complete their requested deliverables; see the in-progress checklist above.
- Added page labels to extracted selectable PDF text and regression coverage
  for multi-page extraction. Both target models correctly analyzed a page-
  labeled PDF excerpt in chat. PDF and DOCX generation continue to be covered
  by the document-tool tests.
- Added local OCR for image-only PDF pages and bounded, in-memory RAG over
  attachments within a conversation. Later turns retrieve relevant excerpts
  with source/page labels without resending earlier uploads. The index is
  cleared on server restart and expires after two idle hours. API tests cover
  follow-up retrieval and chat isolation; oversized extracted text now returns
  an explicit 413 instead of being silently evicted from the 12 MiB-per-chat
  index.
- Added a fixed-path homepage tool and a focused repair tool for Qwen2.5 and
  `midnight-signal:latest`, with bounded recovery for their observed malformed
  JSON tool calls. Repairs still pass normal write approval and website
  validation; a live single-page site was validated, packaged, and browser-
  checked for its requested search and favorite interactions.
- Added a separate, extension-limited website-asset tool for these models so
  they can create linked CSS, JavaScript, pages, data, and README files without
  rewriting `index.html`. If a model still cannot fix a broken in-page link or
  add responsive CSS after retrying, the agent can apply those narrow,
  approval-gated repairs and revalidate before packaging.
- Explicit-stack web-app requests now check user-named project files and the
  presence of requested Python backend, automated-test, and README files. The
  agent prompts for missing deliverables at most twice and then reports an
  incomplete project instead of implying success. This checks file presence,
  not backend behavior or test execution; the live Qwen 2.5 full-stack trial
  still failed its completion gate.
- Completed a browser end-to-end Undo check using an isolated test server:
  approved a file overwrite, used the activity card's Undo action, and verified
  that the original file contents were restored. This exercises the UI/API
  workflow, not a live model-generated edit.
- Hardened website ZIP completion at the 24-tool boundary. If a requested
  archive has not been made when the model exhausts its tool budget, the agent
  validates the website and packages only files created during that run through
  the normal approval flow. It reports completion only after the archive is
  present, non-empty, and passes ZIP integrity checks. The server also verifies
  the archive in the selected workspace before exposing a download link.
- Improved attachment question handling: read-only questions about an uploaded
  document no longer expose web-search or workspace-reading tools, and exact
  "first N lines" requests use the original extracted text rather than ranked
  RAG chunks. Source lines, including blank lines and page labels, are preserved
  for the model to present in order. Regression tests cover exact lines,
  attachment/chat isolation, ZIP integrity, and step-limit packaging.
- Verification after these fixes: **135 tests passed, 1 skipped**. Python
  compilation, `node --check web\app.js`, and `git diff --check` also passed.
- In the latest phone-access pass, the live UI created a QR code, returned an
  active status (HTTP 200), and revoked the listener successfully (HTTP 200,
  disabled). The two focused phone-access and cookie-session regression tests
  passed. A keyboard focus trap was added for modal dialogs; browser checks
  verified forward/reverse Tab wrapping, Escape dismissal, and focus restoration.
- Fixed phone chat startup on HTTP LAN origins where `crypto.randomUUID` is not
  available. Conversation and branch IDs now use a UUID-compatible local
  fallback. A live LAN-origin browser test with `crypto.randomUUID` disabled
  sent a prompt and received the exact response from `midnight-signal:latest`.
- An initial full-suite rerun under low-memory conditions hit an ONNX
  `bad allocation` in image-only PDF OCR and a `MemoryError` in the large
  attachment-request test (about 750 MB was available). Both tests passed when
  rerun in isolation after memory recovered, followed by a clean full-suite
  rerun: **135 tests passed, 1 skipped**.
- Polished the welcome screen with an animated signal mark, local-first
  capability cards, multi-file website/PDF entry points, and an expandable
  explanation of how local chat, workspace tools, and optional web research
  work. Removed externally hosted Google Fonts so the interface does not need
  a third-party font request and remains usable offline.
- Added contextual, time-based progress copy for ordinary chat while the local
  model is responding; it reflects the user's request and does not expose or
  fabricate private chain-of-thought. Response progress now clears when answer
  text arrives. Refined conversation-search labeling and stopped scanning
  attachment payloads during each keystroke; message content and attachment
  names remain searchable.
- Declared `opencv-python` directly because scanned-PDF OCR imports `cv2`.
  Installing the PDF/OCR packages already listed in `requirements.txt` exposed
  this missing runtime dependency; the scanned-PDF OCR regression now passes.
- Final validation for this pass: **135 tests run, 2 skipped, all others
  passed**; Python compilation, `node --check web\app.js`, and
  `git diff --check` passed. Live browser checks confirmed the refreshed home
  screen, connected local-model status, reduced-motion behavior, and no
  horizontal overflow at 320px. A delayed-response browser check showed
  request-specific progress text while the response was pending.
- Expanded the welcome experience into a consistent product site: animated PNG
  brand mark/favicon, multicolor capability cards, site navigation, standalone
  About and Contact pages, skip links, responsive layouts, and reduced-motion
  support. Static routes remain explicitly allowlisted. The local feedback
  form now prepares a reviewable text note and shows a direct download link;
  it does not transmit the form contents.
- Fixed the app welcome mark placement and narrow topbar wrapping. Browser
  checks found no horizontal overflow on the home screen at 320, 390, 520,
  768, and 1440px, and on About and Contact at 320, 360, 375, 390, 520, 768,
  and 1440px. The 320px pass verified the site navigation wraps instead of
  clipping. The local model reported connected during the home-screen check.
  The feedback form created a blob download link with the expected filename;
  the browser harness did not report a native download event, so completed
  file saving was not independently verified.
- Latest validation after the website-recovery and markup-repair changes:
  **158 tests run, 1 skipped, all others passed**. Regression checks cover
  casual "can u" website requests, unlabeled HTML fences, non-empty workspaces,
  duplicate Qwen asset calls, missing product images, escaped local asset URLs,
  missing mobile viewports, and direct HTML downloads. Python compilation,
  `node --check web\app.js`, and `git diff --check` passed.
- Browser verification opened the Settings drawer and confirmed its model,
  appearance, sound, approval, MCP, and advanced sections. The already-running
  browser service returned HTTP 404 for `/api/mcp-status`; the current server
  source has that route and a passing endpoint test, so live MCP status should
  be rechecked after restarting the service.
- The already-running Studio process at `127.0.0.1:8765` predates the latest
  backend fixes. Restart Studio before retesting website generation, HTML
  recovery, or workspace-scoped downloads so the running process loads the
  updated Python modules.

### Remaining work and environment-dependent checks

#### P1: Design and high-impact browser UX

- The product-facing home, About, and Contact pages, multicolor palette,
  animated logo, site navigation, reduced-motion styling, and small-screen
  layout are implemented and browser-checked. Continue the broader interaction
  and accessibility review of the app's activity cards, approvals, downloads,
  composer, sidebars, and pickers.
- Conversation content search is available locally across titles, messages,
  progress notes, and tool activity; attachment names are searchable without
  scanning binary or large uploaded payloads. Conversation folders/project
  groups remain an optional follow-up.
- Complete a focused mobile/accessibility review: keyboard-only navigation,
  focus visibility, screen-reader names/roles, contrast, touch target sizing,
  attachment chips, approval cards, composer, sidebars, and pickers. Modal
  dialogs now constrain Tab navigation and restore focus on close; site pages
  have skip links and labeled form fields. This pass checked responsive
  overflow, but a full assistive-technology and physical-device review remains.

#### P1: Reliability and project delivery

- Existing tests cover partial/disconnected streams, cancellation, and
  malformed website output; Ollama capability lookup errors are not cached and
  recover on retry. Continue the audit for malformed/partial NDJSON, Markdown
  edge cases, and large conversation rendering; preserve partial responses and
  actionable errors.
- **Model website/app quality:** the single-page smoke test passed, but the
  latest isolated Qwen 2.5 full-stack trial still produced no backend, tests,
  or ZIP. The bounded completion gate correctly reports missing deliverables;
  generation quality and semantic backend/API checks remain open.
- The browser Undo interaction is now verified with a controlled test server;
  retain server coverage for stale-change refusal and workspace scoping.

#### P2: Physical phone connection

- Verify phone access from a physical phone after confirming the Wi-Fi is
  trusted, setting its profile to Private, and allowing Python through the
  Private-network firewall only. This machine currently reports a Public Wi-Fi
  profile, so its profile and firewall were left unchanged; physical-phone
  access remains unverified. Do not change the localhost-only default.
- Do not claim the roadmap is finished while this trusted-network check and
  the listed UX/reliability follow-ups remain.

### Handoff rules

- Start by checking `git status` and reading this handoff plus relevant code and
  tests. The worktree may contain existing user changes; never revert unrelated
  changes or overwrite generated/user files.
- Make changes in the implementation and tests, not only in this checklist,
  when the user has asked for implementation.
- Do not commit unless explicitly requested. Do not add a dependency without
  explaining why and updating the correct dependency manifest.
- Keep README status current: move completed items out of TODO only after
  implementation and verification, record test counts and model outcomes, and
  list anything that could not be tested.

## Screenshots

<p align="center">
  <img src="assets/screenshot-banner.png" alt="Midnight Signal boot banner and default mode chat" width="850">
</p>

<p align="center">
  <em>Boot banner, live gradient UI, and per-reply usage line — v2.2, mode: default</em>
</p>

<p align="center">
  <img src="assets/screenshot-help.png" alt="Midnight Signal /help menu showing commands, modes, and agent tools" width="850">
</p>

<p align="center">
  <em><code>/help</code> — full command list, modes, and agent tools</em>
</p>

---

## Contents

0. [AI contributor quickstart](#ai-contributor-quickstart)
1. [Quick install](#1-quick-install)
2. [Manual install](#2-manual-install)
3. [Run it](#3-run-it)
4. [Browser interface](#4-browser-interface)
5. [Commands](#5-commands)
6. [Modes](#6-modes)
7. [Agent mode — how it works](#7-agent-mode--how-it-works)
8. [Adding new modes](#8-adding-new-modes)
9. [Usage bars, sparklines, sound, and themes](#9-usage-bars-sparklines-sound-and-themes)
10. [File overview](#10-file-overview)
11. [Troubleshooting](#11-troubleshooting)

---

## AI contributor quickstart

This section is the project handoff for coding agents and new contributors.
Midnight Signal is a local Python application with a terminal UI and a
localhost-only browser UI. Ollama runs the models; the project owns the
conversation handling, coding-agent loop, tool permissions, and UI.

### Request flow

```text
Browser: web/app.js -> web_server.py -> agent.py -> tools.py -> selected workspace
Terminal: midnight_signal.py ---------------------> agent.py -> tools.py
```

- `web/app.js` owns browser chat, local conversation history, streaming events,
  workspace selection, model selection, and approval controls.
- `web_server.py` validates browser requests, streams chat/agent events, and
  applies the browser's approval choice.
- `midnight_signal.py` is the terminal entry point and also contains the
  non-agent chat behavior.
- `agent.py` runs the multi-step model/tool loop for both interfaces. It
  decides when to inspect or edit, dispatches tool calls, and checks generated
  websites for missing local files, broken/placeholder links, unfinished
  content, semantic page structure, and responsive CSS.
-   `tools.py` implements workspace reads/writes, project ZIP packaging, document
  generation, shell commands, git inspection, and public web search/fetch. Workspace paths are scoped to
  the selected root; writes, commands, and public web requests use the caller's
  confirmation flow.
- `system_prompts/agent.txt` controls coding-agent behavior. `Modelfile`
  applies only to the custom `midnight-signal:latest` Ollama model; the app
  sends runtime prompts to every selected model.
- `tests/` contains the Python regression suite. `web/` contains the browser
  interface. `scripts/install.*` create `.venv` and install `requirements.txt`.

### Working on the project

1. Read the relevant implementation and tests before changing behavior. Keep
   terminal and browser behavior consistent when touching shared agent logic.
2. Keep file and command operations inside the selected workspace; never
   bypass the existing approval callbacks or safety checks.
3. Run the focused test file while iterating, then run the complete Python
   suite before handing off:

   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   node --check web\app.js
   git diff --check
   ```

   On macOS/Linux, use `python -m unittest discover -s tests -v`.
4. When changing browser behavior, check both the server event payloads and
   `web/app.js` handling. Do not claim the browser has visually tested a page
   unless a browser preview was actually used.
5. Update this README when user-facing commands, install requirements, models,
   tools, or architecture change.

### Model and file-generation expectations

Qwen2.5 Coder 7B Q4 is the fast local agent target. Tool support reported by
Ollama means the model accepts tool schemas; it does not guarantee every
response will use them correctly. The agent supports native structured tool
calls and, for Qwen2.5/custom `midnight-signal` models, a narrowly validated
JSON tool-call compatibility format. Recovered calls still pass through the
same workspace checks and user approvals. Responses that do not match a
provided tool and its argument schema are not executed.

The agent should infer scope from an ordinary prompt. For a simple static site,
it can create a runnable site with sensible defaults. For a request requiring
React/TypeScript, a backend, persistence, or other project files, it should
inspect the workspace and create the files and configuration the chosen stack
actually needs. `write_file` creates text-based source and configuration files.
No model is guaranteed to deliver a production-ready full-stack application
without verification, available services, and any required credentials.

Qwen-Agent was tested as an integration prototype, but it is not a runtime
dependency: its function-call loop did not fit the app's approval, cancellation,
and browser-streaming paths, and version 0.0.34 hit an `extra=None` bug on the
Qwen-specific tool-call path. The app keeps its own agent loop and handles the
limited Qwen JSON call format directly, without installing or monkey-patching
Qwen-Agent.

---

## 1. Quick install

The installer checks Python and Ollama, creates a virtual environment,
downloads the base model, builds `midnight-signal` from the `Modelfile`,
and runs a health check — all in one go.

**macOS / Linux**
```bash
git clone https://github.com/17413-maker/MIDNIGHTSIGNAL.git
cd MIDNIGHTSIGNAL
./scripts/install.sh
./run.sh
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/17413-maker/MIDNIGHTSIGNAL.git
cd MIDNIGHTSIGNAL
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
.\run.ps1
```

Something not working? Run the doctor:

```bash
python midnight_signal.py --doctor
```

It checks Python, the `ollama` package, the Ollama server, both models,
tool-calling support, truecolor, and audio output — and prints the exact
command to fix whatever's missing.

## 2. Manual install

If you'd rather do it by hand, or the installer script doesn't fit your
setup:

```bash
# 1. Ollama running, base model pulled
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b

# 2. Python environment
cd midnight-signal
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Build the custom model
ollama create midnight-signal -f Modelfile
ollama list                      # confirm "midnight-signal" is there

# 4. Run it
python midnight_signal.py
```

Your model must support **tool calling** for `agent` mode to work (recent
Qwen2.5-coder builds do); `--doctor` tells you either way. The other five
modes work with any chat model.

## 3. Run it

```bash
python midnight_signal.py            # fresh session
python midnight_signal.py --web      # local browser interface
python midnight_signal.py --resume   # continue the autosaved session
python midnight_signal.py --doctor   # check the install, print fixes
python midnight_signal.py --no-sound # start muted, this run only
python midnight_signal.py --version
```

You'll get a boot sequence, a gradient banner, and a prompt:

```
▌ you ›
```

Type normally to chat — replies stream in word by word, exactly like
`ollama run`. Use `/` commands to control the terminal.

## 4. Browser interface

Run `python midnight_signal.py --web` (Windows: `.\run.ps1 --web`) to
start the browser UI at `http://127.0.0.1:8765`. It binds to localhost
only, uses the installed Ollama models, and does not send chat data to a
remote service. The server opens the page automatically; stop it with
Ctrl+C in the terminal. Use `--web-port 9000` to select a different port.

The browser UI includes streaming local chat, installed-model selection,
date-grouped and searchable conversations saved in the browser, conversation
renaming, Markdown export, response regeneration, file attachments, Markdown
and code rendering, custom keyboard-accessible mode/model pickers, a responsive
warm-light theme, and a command palette (Ctrl/⌘+K). DM Sans, DM Mono, and
Manrope use local system fallbacks; the interface makes no third-party font
requests. The conversation list uses a windowed view above 100 matching chats,
and filename search avoids scanning large attachment contents.
Attach up to five text/code files or PDFs, totaling 100 MiB. PDFs are converted
to selectable text locally using `pypdf` (up to 200 pages and 2 MiB extracted
text per PDF), with `[Page N]` labels included for page-specific analysis.
Pages without selectable text are rendered and OCR'd locally with PyMuPDF and
RapidOCR, up to 50 such pages per PDF; each rendered page is limited to 20
million pixels. Install the updated `requirements.txt` and restart the server
to enable OCR.
Attachment text is chunked and indexed per conversation. When available,
EmbeddingGemma creates local vectors for semantic ranking; otherwise the
agent uses local keyword ranking. Follow-up prompts in the same chat retrieve
up to eight relevant excerpts (at most 12,000 characters), with filename and
page citations. The in-memory index allows up to 20 documents and 12 MiB per
chat, up to 32 chats and 64 MiB total; idle entries expire after two hours and
a server restart clears the index.
If files are attached without a request, the composer asks what to do and does
not submit them until you add instructions. For multi-file websites or apps,
the Coding agent can show generated HTML in a sandboxed in-chat preview and
create a workspace-scoped ZIP; use the preview for a quick look or download the
archive to run the complete project locally.
Press `/` in the empty
composer to browse slash commands, or type `/help`, `/new`, `/clear`, `/export`,
`/settings`, `/theme [name]`, `/mode [name]`, `/workspace`, `/stats`, or
`/search [text]` and press Enter. Press `?` outside a text field for the shortcut
cheatsheet.

Open **Settings** for temperature, top-p, top-k, repeat penalty, context and
reply-token limits; warm light/dark/high-contrast and six accent themes; audio
feedback and volume; the default agent approval mode; and sidebar persistence.
The default sampling values preserve the original web behavior. Settings and
conversation history stay in browser storage; history is mirrored to IndexedDB
and falls back to IndexedDB when localStorage is full or the history grows past
4 MiB. If both stores fail, the UI warns you to export. Use the per-chat export
button or **Settings → Export all conversations** to download Markdown before
clearing browser data. The full transcript remains available locally;
each model request includes up to the latest 30 user/assistant messages, while
older messages remain in browser history but are not automatically sent as
model context. In Coding agent mode, recent tool names, arguments, and bounded
results are also included as historical context so follow-up requests can
continue prior work. The interface keeps this activity separate from the
assistant's visible answer. Coding agent status labels display concise task
progress, active tools, and approval state as work proceeds; final answers
stream as they are generated, while the interface does not expose the model's
private reasoning channel. Select **Coding agent** to
let the model inspect this project, search
and read files, edit files, and run project commands. File writes and shell
commands require an in-browser approval with a preview; the agent is scoped to the project
directory shown in the top bar. Click the workspace path in the top bar to
select another existing local directory. Reads and model requests stay on this
computer through Ollama. In Coding agent mode, the agent can also search
Bing for current information and fetch readable text from public webpages.
Each search query or URL requires approval before it is sent
externally (except when you explicitly choose **Allow all**); do not approve
queries containing private code or secrets. Private/local network addresses
and nonstandard web ports are blocked, and fetched page contents are treated
as untrusted input.

By default, the browser server is available only on the laptop. To connect a
phone on the same trusted Wi-Fi, click the phone icon in the browser top bar,
choose **Start phone access**, then open or copy one of the private-network
links shown there. This starts a separate temporary LAN listener and requires
the one-time token for API access; the main server remains localhost-only.
Choose **Stop phone access** to revoke it, or close Midnight Signal to stop it.
Do not share the link or use this on public Wi-Fi. If the phone cannot connect,
allow Python through the laptop's private-network firewall and confirm both
devices are on the same Wi-Fi.

For a complete website, describe the goal normally; you do not need to list
every page, feature, or style detail. The Coding agent chooses sensible
defaults, builds a polished responsive experience with working navigation and
controls, and runs the project's checks in the shown workspace. It can create
and edit project files and run commands with the selected approval mode. The
agent can research public web pages, but it does not control a browser to click
through or visually inspect the finished page; open the local preview yourself
to review its appearance.

With `qwen3:14b` selected, the **Fast / Think** control switches Ollama's
Qwen3 thinking mode on or off for chat and Coding agent requests. Fast mode is
the default for quicker responses. Think mode uses additional reasoning and
usually takes longer, while surfacing high-level live progress stages. Both
modes show progress notes and actual tool activity; the model's private
reasoning text is not displayed.

Coding agent mode has a per-chat **Approvals** selector:

- **Ask each time** (default) pauses before every file write/edit and command.
- **Auto safe only** runs a small allowlist of read-only status/version checks
  without prompting; edits and all other commands still require approval.
- **Allow all** skips per-action prompts for this chat after an explicit
  browser confirmation. Workspace path scoping and blocked dangerous command
  patterns remain active; web searches/page fetches may send queries or URLs
  to external websites, so review actions in the visible activity log.

Browser approval prompts wait up to 10 minutes by default. Set
`MIDNIGHT_SIGNAL_CONFIRMATION_TIMEOUT` to a value from 30 to 3600 seconds to
change this limit for the server process.

#### Creating and finding files

To create a real file on disk, select **Coding agent** mode and a model marked
**agent tools** (for example, `midnight-signal:latest` if it has that label).
Chat/Coder mode can suggest or generate code in its response, but does not
write workspace files. `qwen3:14b` is available for Coding agent only when
Ollama reports that it supports tools.

Before asking, check the workspace path in the top bar: new files are created
inside that folder, at the path you request. For example, ask: “Create
`hello.txt` in the workspace containing `Hello`.” With **Ask each time**
selected, approve the proposed file-write action. A successful write creates
the file on your computer; it is not merely text displayed in the chat. The
assistant should report what it created and the path, and the activity log
shows the tool action. Find the file in the selected workspace folder using
your file manager or the app's workspace listing.

The coding agent can also generate formatted PDF and DOCX files from
Markdown. For example, ask it to “create a PDF report at `reports/summary.pdf`”
or “make a DOCX proposal at `proposal.docx`.” Generated documents are saved
inside the selected workspace and require the usual write approval.

If the request ends with a message such as “The model did not call a workspace
tool” or “No workspace changes were made,” the file was not created. Select a
model marked **agent tools** and try again. If no installed model has that
label, install or select a model that Ollama reports as supporting tools.

Shorter prompts and Fast mode are the best choices when responsiveness
matters. Agent requests use at least an 8K context and a 4,096-token generation
budget by default so tool calls can carry useful file edits without spending
time on unbounded model output; selecting `-1` in Settings opts into the
model's maximum output. If the model produces a plain-text answer instead of
using tools for a workspace task, the agent retries with a corrective
tool-only instruction and reports failure rather than claiming work was
completed. Qwen2.5 and the custom `midnight-signal` model also have a
strictly validated JSON-call fallback; recovered calls still use the same
workspace and approval protections.
Ordinary chat keeps a bounded reply budget (1,536 tokens for 14B/16B Fast
mode, 3,072 in Think mode; 2,048 for smaller models).

`qwen3:14b` is the intended larger agent-model option; install it with
`ollama pull qwen3:14b`. The browser enables it for Coding agent mode only
after Ollama confirms tool support. Until then, use an installed model marked
**agent tools** (such as `midnight-signal:latest`). Both larger models may
need CPU/RAM offloading on an 8 GB GPU and 16 GB system memory, so generation
speed depends on how much of the model Ollama can keep on the GPU.

The browser model picker intentionally omits DeepSeek and embedding-only
models. `embeddinggemma` is reserved for local semantic document retrieval
when installed; it is not a chat or writing model. The selected chat model
continues to generate document content, which the workspace tools can format
as PDF or DOCX.

The `Modelfile` defines only `midnight-signal:latest` and its raw-CLI fallback.
The browser app sends its agent instructions separately to whichever model is
selected, so changing the `Modelfile` does not change raw tags such as
`qwen3:14b`. Rebuild the custom model after editing the file with
`ollama create midnight-signal -f Modelfile`.

No separate Qwen-Agent package is required for this application: Midnight
Signal provides its own coding-agent loop, approval flow, streaming, and
cancellation. Qwen-Agent was tested as a prototype; version 0.0.34 hit an
`extra=None` bug on the Qwen-specific function-call path and does not directly
provide the app's permission/UI flow. Midnight Signal accepts a strictly
validated Qwen2.5 JSON-call fallback instead, with calls still routed through
the normal protections. Qwen-Agent is not a model plugin that enables tools in
Ollama. Confirm native model support with `ollama show <model>` and look for
`tools` under Capabilities.
Large structured file-write calls may not produce visible partial arguments
while Ollama is generating them; the UI reports its current stage and stops a
request after five minutes without a model response.

## 5. Commands

Replies stream **word by word**, printed the instant each one arrives —
the same feel as `ollama run`, not a dump of the whole reply at once.
Markdown (headings, bullets, **bold**, *italic*, `code`, fenced code
blocks, tables) is styled live as it streams. Press **Ctrl+C** mid-reply
to stop generation and keep what was produced. Start a message with
`"""` for multi-line input and finish it with `"""`. Up-arrow history and
Tab completion for `/commands` are built in (persisted across runs).

After every reply you get one quiet usage line:

```
38.2 tok/s · 142 gen · 1.8k prompt · ctx ━━────────  23% · 0.4s first token
```

(speed · tokens generated · prompt tokens · context-window fill · time to
first token). The `ctx` figure turns amber past 60% and red past 85%.
`/context` shows the full bar plus a system / conversation / free breakdown.

| Command           | What it does                                              |
|-------------------|------------------------------------------------------------|
| `/help`           | Full gradient help menu — commands, modes, agent tools     |
| `/mode <name>`    | Switch mode, with a cinematic "signal lock" animation      |
| `/model [name]`   | Show or switch the Ollama model live                       |
| `/models`         | List locally installed models                              |
| `/set [key val]`  | Tune sampling, context size (`num_ctx`), and reply-token ceiling (`num_predict`) |
| `/system [text]`  | Show, override, or `reset` the system prompt               |
| `/retry`          | Regenerate the last reply                                  |
| `/undo`           | Remove the last exchange                                   |
| `/file <path>`    | Attach a text file (up to 80KB) to the conversation        |
| `/compact`        | Summarize the history with the model to free up context    |
| `/context`        | Context-window usage bar                                   |
| `/stats`          | Session totals: turns, tokens generated, average speed    |
| `/radar [path]`   | Project radar: languages, heavy files, recent edits, TODO/FIXME markers, git state |
| `/save [name]`    | Save the conversation                                      |
| `/load <name>`    | Restore a conversation (`last` = the autosave)             |
| `/sessions`       | List saved conversations                                   |
| `/export [file]`  | Export the conversation as markdown                        |
| `/copy`           | Copy the last reply to the clipboard                       |
| `/sound [on\|off]` | Toggle sound effects · `/sound vol 0-100` · `/sound test`  |
| `/theme [name]`   | Colour theme · `/theme auto` gives each mode its own        |
| `/statusbar`      | Toggle the status line (mode · dir · git branch · ctx) above the prompt |
| `/search <term>`  | Search this conversation for a word or phrase              |
| `/diff [path]`    | Show `git diff` for the working directory (read-only)      |
| `/banner`         | Reprint the main banner                                    |
| `/clear`          | Clear the screen and reprint the banner                    |
| `/status`         | Mode, model, working directory, yolo state, uptime         |
| `/cd <path>`      | Change the working directory used by agent mode and `/radar` |
| `/ls [path]`      | List the working directory (or a subpath)                  |
| `/pwd`            | Print the current working directory                        |
| `/yolo`           | Toggle yolo mode — skips confirmations in agent mode       |
| `/exit`, `/quit`  | Elegant goodbye and exit                                   |

Sessions live in `~/.midnight_signal/sessions/` as plain JSON, and the
conversation is autosaved to `last` after every reply.

## 6. Modes

| Mode      | Command          | Personality / purpose                                   |
|-----------|------------------|-----------------------------------------------------------|
| Default   | `/mode default`  | Balanced, calm, quietly sharp — the home voice             |
| Hacker    | `/mode hacker`   | Ethical hacking / CTF / cybersecurity, precise, terse       |
| Fun       | `/mode fun`      | Chaotic, meme-y, playful, over-the-top                      |
| Coder     | `/mode coder`    | Pure coding — concise, correct, minimal fluff               |
| Lore      | `/mode lore`     | Story / roleplay / narrative, atmospheric                   |
| Agent     | `/mode agent`    | Full tool-calling agent (see below)                          |

Switching modes resets the conversation and loads a fresh system prompt
from `system_prompts/<mode>.txt`.

Replies adapt to the requested level of detail: ask for a short answer to
keep it brief, or request detail for a fuller explanation. By default,
`num_predict` is `-1`, disabling the fixed output-token cap. Set
`/set num_predict <tokens>` to choose a cap; use `/set num_predict -1` to
remove it again. The model can still stop when its answer is complete, and
the 16,384-token context window remains a separate limit on how much
conversation it can consider at once. If a streamed reply is interrupted
or Ollama reports it stopped at the token limit, Midnight Signal tries to
continue it automatically up to two times.
For explicitly large code requests, it also retries when the model calls
its own answer a basic or simplified substitute. If you request a line
count, it checks whether the generated code is substantially short and
prompts up to two times for useful, non-duplicated additions.

For code-generation requests, Midnight Signal is instructed to produce the
requested implementation rather than replacing it with an outline. The
bundled 7B model still has capability limits; larger or more complex
projects may benefit from a larger code model and should be tested before
relying on the generated code.

## 7. Agent mode — how it works

`agent` mode gives the model real tools, driven by a multi-step
read → reason → act → verify loop (`agent.py`):

- **read_file(path)** — read a file with line numbers
- **read_file(path, start_line, end_line)** — read a focused range (up to
  200 lines), useful for keeping large files within a local model's context.
  Longer files return a continuation line number for the next read.
- **write_file(path, content)** — create or fully overwrite a file
- **edit_file(path, search, replace)** — precise, unique search & replace
  (refuses if `search` isn't found exactly once, so it never guesses)
- **list_dir(path)** — list a directory
- **run_command(command)** — run a shell command in the working directory,
  180s timeout, terminates its process tree on timeout or cancellation, and
  refuses known-destructive patterns (`rm -rf /`, disk-format commands,
  fork bombs, and selected Windows destructive commands)
- **git_status()** / **git_diff(path)** — read-only git inspection
- **search_files(query, path)** — search workspace text, including hidden
  project folders
- **web_search(query)** / **web_fetch(url)** — search Bing and read public
  webpages after confirmation

Every `write_file`, `edit_file`, and `run_command` call shows you exactly
what it's about to do (a diff for edits, the full command for shell calls)
and asks **[y/N]** before proceeding — unless you've toggled **yolo mode**
with `/yolo`, in which case it proceeds automatically. If you answer **n**,
the model is told you declined and not to retry; if it tries the exact same
action again anyway, the turn stops instead of asking you a second time.
Read-only tools (`read_file`, `list_dir`, `git_status`, `git_diff`) never ask.

Use `/cd` in the terminal or click the workspace path in the browser to point
the agent at the project directory you want it working in; all tool paths are
resolved relative to it and sandboxed — the agent can't write outside that
directory tree.

The loop stops automatically after 24 tool-call steps per turn as a safety
backstop; if it hits that limit mid-task, the chat shows the completed work
and you can send a follow-up to continue.

Agent tool calls, progress, and final answers stream as they happen. The
model's private reasoning text is not displayed.

To create a clean source archive without `.git`, virtual environments, cache
files, or `.env` files, run:

```bash
python scripts/package.py
```

The archive is written to `dist/MIDNIGHTSIGNAL-source.zip`. Use
`python scripts/package.py --force` to replace an existing archive.

## 8. Adding new modes

No code changes needed:

1. Create `system_prompts/<your_mode>.txt` with the personality/system prompt.
2. (Optional) add a description to `MODE_DESCRIPTIONS` in
   `midnight_signal.py` for a nicer `/help` line — otherwise it still works
   with a generic description.
3. Run `/mode <your_mode>` — it's auto-discovered from the folder.

Note: only give a mode agent-style tool access by naming it exactly
`agent` (that's the mode `midnight_signal.py` routes through the tool
loop) or by editing `midnight_signal.py`'s routing if you want a second
tool-enabled mode.

## 9. Usage bars, sparklines, sound, and themes

Every token/context display uses a fuel-gauge-style bar with eighth-block
precision (`▏▎▍▌▋▊▉█`) instead of a coarse one-block-per-cell bar, so it
fills smoothly rather than in visible steps, with a bright leading edge
and soft bracket caps (`╢…╟`). You'll see it in the footer under every
reply and in `/context`, which also breaks total usage down into a
stacked bar — system prompt, conversation, and free space, each their own
shade:

```
CONTEXT WINDOW   52%
╢█████████████████████████·······················╟
■ system 1,720    ■ conversation 2,580    ■ free 3,892
```

`/stats` adds a **speed sparkline** — a one-line bar-height history of
your last ~40 replies' tokens/sec, so you can see a session's speed trend
at a glance instead of just the running average.

Every sound is synthesized on the fly (sine/bell/square tones with an
envelope) and cached as tiny WAVs under `~/.midnight_signal/sounds` — no
audio files ship with the project. Playback uses whatever's already on
your system (macOS: `afplay`; Windows: built-in `winsound`; Linux:
`paplay`/`pw-play`/`aplay`/`sox`/`ffplay`, whichever is found first). With
none of those installed, only the important moments fall back to a plain
terminal bell.

| Event | Sound |
|---|---|
| Startup | rising arpeggio into a bell |
| Mode or theme switch | fast downward sweep → click → locked-on ping |
| First token of a reply | a soft blip |
| Agent calls a tool | two quick rising ticks |
| Confirmation waiting for you | a two-note question |
| You approve / decline | bright upward blip / soft downward step |
| Something fails | a low buzzy thud |
| A long reply or task finishes | a glassy two-bell chime |
| Context nearly full, etc. | a gentle heads-up bell |
| Exit | a long falling sweep |

- `/sound` — show sound status
- `/sound on` / `/sound off` — toggle (saved for next launch)
- `/sound vol 0-100` — set volume (saved)
- `/sound test` — play every sound in order, with a label for each
- `python midnight_signal.py --no-sound` — start muted for just this run

Six built-in **themes** repaint every gradient in the UI at once —
banners, bars, the prompt, spinners, the footer:

| Theme | Feel |
|---|---|
| `sunset` | orange → amber → coral → red (the default) |
| `ember` | deep red-orange, warmer and darker |
| `cyber` | magenta → violet → blue → cyan |
| `matrix` | green, terminal-classic |
| `ice` | blue → cyan → white, cool |
| `noir` | white → grey, no color at all |

- `/theme` — list all themes with a live swatch of each
- `/theme <name>` — pin a theme (saved for next launch)
- `/theme auto` — release the pin: each mode wears its own theme
  automatically (`hacker` → matrix, `fun` → cyber, `coder` → ice, `lore` →
  ember, `default`/`agent` → sunset)

## 10. File overview

```
midnight-signal/
├── Modelfile                  # Ollama model definition (base + fallback SYSTEM)
├── requirements.txt
├── run.sh, run.ps1            # launchers (use the .venv if the installer made one)
├── web_server.py              # local browser chat server (optional trusted-LAN access)
├── web/
│   ├── index.html             # browser chat interface
│   ├── app.css                # Midnight Signal theme and responsive layout
│   └── app.js                 # local chat, streaming, and browser-side sessions
├── scripts/
│   ├── install.sh             # macOS/Linux one-shot installer
│   ├── install.ps1            # Windows one-shot installer
│   └── package.py             # source ZIP builder (excludes .git/.venv)
├── samples/                   # standalone sample outputs, not app entry points
├── system_prompts/
│   ├── default.txt
│   ├── hacker.txt
│   ├── fun.txt
│   ├── coder.txt
│   ├── lore.txt
│   └── agent.txt
├── ui.py                      # gradients, themes, animations, banners, word-by-word stream painter
├── sounds.py                  # synthesized sound effects (no audio files, no pip deps)
├── doctor.py                  # `--doctor` install/health checker
├── session.py                 # save / load / export conversations + settings
├── radar.py                   # /radar project scanner
├── security.py                # keeps replies from leaking the system prompt / tool schema
├── tools.py                   # agent tool implementations + JSON schemas
├── agent.py                   # multi-step tool-calling agent loop
├── midnight_signal.py         # CLI entry point — ties everything together
├── CHANGELOG.md
├── tests/                     # Python regression tests
└── README.md
```

## 11. Troubleshooting

- **`[signal error]` on every message** — the model probably isn't built.
  Run `ollama create midnight-signal -f Modelfile` again and confirm with
  `ollama list`.
- **Agent mode never calls tools / errors about tools** — your Ollama
  version or the base model build doesn't support tool calling. Update
  Ollama and re-pull the base model, or check `--doctor`.
- **Colors look wrong / raw escape codes show up** — your terminal doesn't
  support 24-bit truecolor. Modern terminals (iTerm2, Windows Terminal,
  GNOME Terminal, Alacritty, kitty) do; legacy `cmd.exe` may not.
- **`edit_file` keeps refusing** — its `search` text must match the file
  exactly once. Include a bit more surrounding context in the search text
  to make it unique, or ask the agent to `read_file` first.
- **Slow first response** — normal; Ollama loads the model into memory on
  first use.
- **No sound, or only a terminal beep** — run `python midnight_signal.py
  --doctor` to see which audio player it found (or didn't). On Linux,
  install one of `pulseaudio-utils`, `alsa-utils`, `sox`, or `ffmpeg`.
- **A message that ends in a single unmatched `*` with nothing after it**
  can render as if that character vanished, instead of showing it
  literally — a streaming can't-know-yet edge case at the very end of a
  reply. Cosmetic only; it doesn't affect anything else on the line.

---

Built for a private, local, no-cloud-required terminal AI experience.
