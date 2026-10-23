(() => {
  "use strict";

  // Keep the QR bootstrap token in memory as well as sessionStorage. Some
  // phone browsers can reject sessionStorage (or clear it during the
  // redirect), which otherwise leaves the page looking loaded while every
  // API request is rejected as an unauthorized phone session.
  let phoneAccessToken = new URLSearchParams(location.hash.slice(1))
    .get("midnight-access") || "";
  if (phoneAccessToken) {
    try {
      sessionStorage.setItem("midnight-signal-phone-access", phoneAccessToken);
      history.replaceState(null, "", `${location.pathname}${location.search}`);
    } catch (error) {
      console.warn("Temporary phone session storage is unavailable; using the in-memory session:", error);
    }
  }
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    let phoneToken = phoneAccessToken;
    try {
      phoneToken = sessionStorage.getItem("midnight-signal-phone-access") || phoneToken;
    } catch (error) {
      // The in-memory bootstrap token is still valid for this page session.
      console.warn("Could not read the temporary phone session from storage; using the in-memory session.");
    }
    if (!phoneToken) return nativeFetch(input, init);
    try {
      const requestUrl = typeof input === "string" ? input : input.url;
      if (new URL(requestUrl, location.href).origin !== location.origin) {
        return nativeFetch(input, init);
      }
      const headers = new Headers(init.headers || (typeof Request !== "undefined" && input instanceof Request
        ? input.headers : undefined));
      headers.set("X-Midnight-Access", phoneToken);
      return nativeFetch(input, { ...init, headers });
    } catch (error) {
      console.error("Could not authorize the phone request:", error);
      return nativeFetch(input, init);
    }
  };

  const STORAGE_KEY = "midnight-signal-web-v1";
  const ACTIVE_CHAT_KEY = `${STORAGE_KEY}-active`;
  const SETTINGS_KEY = `${STORAGE_KEY}-settings`;
  const HISTORY_SAVED_AT_KEY = `${STORAGE_KEY}-saved-at`;
  const MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024;
  const TEXT_ATTACHMENT_EXTENSIONS = new Set([
    ".txt", ".md", ".json", ".py", ".js", ".ts", ".tsx", ".jsx", ".html",
    ".css", ".yml", ".yaml", ".toml", ".xml", ".sql", ".sh", ".ps1",
  ]);
  const LOCAL_HISTORY_LIMIT = 4 * 1024 * 1024;
  const DEFAULT_OPTIONS = { temperature: 0.7, top_p: 0.9, top_k: 40, repeat_penalty: 1.1, num_ctx: 16384, num_predict: 4096 };
  const DEFAULT_PREFERENCES = {
    version: 2,
    options: { ...DEFAULT_OPTIONS },
    theme: "light",
    sound: false,
    volume: 45,
    permission_mode: "manual",
    sidebar_collapsed: false,
  };
  const MODE_DETAILS = {
    default: { icon: "✦", description: "A balanced, general-purpose assistant.", best: "Best for everyday questions and exploration." },
    agent: { icon: "⌘", description: "Reads and changes files with local tools.", best: "Best for building and verifying workspace changes." },
    coder: { icon: "</>", description: "Focused coding help and technical explanations.", best: "Best for code drafts, debugging, and reviews." },
    fun: { icon: "✳", description: "A lively, playful conversation style.", best: "Best for brainstorming and creative prompts." },
    hacker: { icon: "⌁", description: "A direct, technical security-minded voice.", best: "Best for authorized defensive security work." },
    lore: { icon: "◈", description: "Imaginative storytelling and world-building.", best: "Best for fiction, characters, and settings." },
  };
  const $ = (selector) => document.querySelector(selector);

  function createLocalId() {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.randomUUID === "function") return cryptoApi.randomUUID();

    const bytes = new Uint8Array(16);
    if (typeof cryptoApi?.getRandomValues === "function") {
      cryptoApi.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index += 1) {
        bytes[index] = Math.floor(Math.random() * 256);
      }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  async function readAttachment(file) {
    const extension = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || "";
    if (extension === ".pdf" || file.type === "application/pdf") {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const chunks = [];
      for (let offset = 0; offset < bytes.length; offset += 32768) {
        chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)));
      }
      return {
        name: file.name,
        size: file.size,
        content: btoa(chunks.join("")),
        encoding: "base64",
      };
    }
    const content = typeof file.text === "function" ? await file.text() : file.content;
    if (typeof content !== "string") throw new Error(`Could not read the attached file ${file.name}`);
    return { name: file.name, size: file.size, content, encoding: "text" };
  }

  function loadPreferences() {
    try {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "null");
      if (!saved || typeof saved !== "object") {
        return { ...DEFAULT_PREFERENCES, options: { ...DEFAULT_OPTIONS } };
      }
      const options = { ...DEFAULT_OPTIONS };
      for (const [key, bounds] of Object.entries({
        temperature: [0, 2], top_p: [0, 1], top_k: [1, 1000],
        repeat_penalty: [0.5, 2], num_ctx: [512, 131072], num_predict: [-1, 32768],
      })) {
        const value = Number(saved.options?.[key]);
        if (Number.isFinite(value) && value >= bounds[0] && value <= bounds[1]) {
          options[key] = value;
        }
      }
      if (!Number.isInteger(saved.version) || saved.version < 2) {
        if (Number(saved.options?.num_ctx) === 8192) options.num_ctx = DEFAULT_OPTIONS.num_ctx;
        if (Number(saved.options?.num_predict) === 2048) options.num_predict = DEFAULT_OPTIONS.num_predict;
      }
      const themes = ["light", "dark", "high-contrast", "sunset", "ember", "cyber", "matrix", "ice", "noir", "auto"];
      return {
        version: 2,
        options,
        theme: themes.includes(saved.theme) ? saved.theme : DEFAULT_PREFERENCES.theme,
        sound: saved.sound === true,
        volume: Number.isFinite(saved.volume) ? Math.min(100, Math.max(0, saved.volume)) : DEFAULT_PREFERENCES.volume,
        permission_mode: ["manual", "auto_safe", "allow_all"].includes(saved.permission_mode)
          ? saved.permission_mode : "manual",
        sidebar_collapsed: saved.sidebar_collapsed === true,
      };
    } catch (error) {
      console.error("Could not load web preferences:", error);
      setTimeout(() => showToast("Saved settings could not be loaded; using defaults."), 0);
      return { ...DEFAULT_PREFERENCES, options: { ...DEFAULT_OPTIONS } };
    }
  }

  let preferences = loadPreferences();
  let historyDatabasePromise = null;
  let historyWriteQueue = Promise.resolve();
  let localHistoryUnavailable = false;
  let indexedDbUnavailable = false;
  const elements = {
    sidebar: $("#sidebar"),
    mainPanel: $(".main-panel"),
    conversationList: $("#conversation-list"),
    historyFilter: $("#history-filter"),
    chatScroll: $("#chat-scroll"),
    emptyState: $("#studio-empty-state"),
    messages: $("#messages"),
    input: $("#prompt-input"),
    send: $("#send-button"),
    mode: $("#mode-select"),
    model: $("#model-select"),
    exportChat: $("#export-chat"),
    status: $("#server-status"),
    toast: $("#toast"),
    historySearch: $("#history-search"),
    workspace: $("#workspace-pill"),
    workspaceName: $("#workspace-name"),
    fileInput: $("#file-input"),
    attachments: $("#attachments"),
    attachmentPrompt: $("#attachment-prompt"),
    promptTemplates: $("#prompt-templates"),
    templateToggle: $("#template-toggle"),
    editMessageBanner: $("#edit-message-banner"),
    cancelEditMessage: $("#cancel-edit-message"),
    thinkingControl: $("#thinking-control"),
    thinking: $("#thinking-select"),
    permissionControl: $("#permission-control"),
    permission: $("#permission-select"),
    composerNote: $("#composer-note"),
    paletteBackdrop: $("#palette-backdrop"),
    paletteSearch: $("#palette-search"),
    paletteList: $("#palette-list"),
    settingsButton: $("#settings-button"),
    settingsBackdrop: $("#settings-backdrop"),
    settingsForm: $("#settings-form"),
    mcpStatus: $("#settings-mcp-status"),
    mcpConfigPath: $("#settings-mcp-config-path"),
    copyMcpConfigPath: $("#copy-mcp-config-path"),
    soundVolume: $("#sound-volume"),
    mobileAccessButton: $("#mobile-access-button"),
    mobileAccessBackdrop: $("#mobile-access-backdrop"),
    mobileAccessLinks: $("#mobile-access-links"),
    mobileAccessStart: $("#start-mobile-access"),
    mobileAccessStop: $("#stop-mobile-access"),
    workspaceBrowserButton: $("#workspace-browser-button"),
    workspaceBrowserBackdrop: $("#workspace-browser-backdrop"),
    workspaceFileList: $("#workspace-file-list"),
    workspaceBrowserPath: $("#workspace-browser-path"),
    workspaceFilePreview: $("#workspace-file-preview"),
  };

  let appStatus = {
    modes: ["default"],
    models: [],
    model: "",
    workspace: "",
    agent_models: [],
    recommended_agent_model: "",
  };
  let chats = loadChats();
  let activeChatId = loadActiveChatId();
  let requestController = null;
  let streaming = false;
  let preparingMessage = false;
  let streamRenderTimer = null;
  const streamActivityIndexes = new Set();
  let statusSignature = "";
  let toastTimer = null;
  let sidebarRenderScheduled = false;
  let modelSelectionMade = false;
  let attachedFiles = [];
  let editingMessage = null;
  const activeConfirmations = new Set();
  let paletteReturnFocus = null;
  let paletteIndex = 0;
  let phoneAccessEnabled = false;
  let workspaceRelativePath = "";

  const paletteCommands = [
    { label: "Start a new chat", detail: "Ctrl K", run: () => newChat() },
    { label: "Search conversations", detail: "Sidebar", run: () => elements.historySearch.focus() },
    { label: "Toggle conversation sidebar", detail: "Navigation", run: () => toggleSidebar() },
    { label: "Choose workspace", detail: "Local folder", run: () => chooseWorkspace() },
    { label: "Browse workspace files", detail: "Local files and ZIPs", run: () => openWorkspaceBrowser() },
    { label: "Open settings", detail: "Preferences", run: () => openSettings() },
    { label: "Export current chat", detail: "Markdown", run: () => exportChat() },
    { label: "Export all conversations", detail: "Markdown", run: () => $("#export-history").click() },
    { label: "/new", detail: "Start a new chat", run: () => newChat() },
    { label: "/export", detail: "Export current chat", run: () => exportChat() },
    { label: "/settings", detail: "Open preferences", run: () => openSettings() },
    { label: "/help", detail: "Show shortcuts and slash commands", run: () => showHelp() },
    { label: "/stats", detail: "Show local model status", run: () => showModelStatus() },
    { label: "/theme", detail: "Open theme settings", run: () => openSettings("theme") },
    { label: "/workspace", detail: "Choose workspace folder", run: () => chooseWorkspace() },
    { label: "/clear", detail: "Start a new chat", run: () => newChat() },
    { label: "/search", detail: "Search conversations", run: () => elements.historySearch.focus() },
    ...["agent", "coder", "default", "fun", "hacker", "lore"].map((mode) => ({
      label: `/mode ${mode}`,
      detail: "Switch mode",
      run: () => {
        if (!(appStatus.modes || []).includes(mode)) showToast(`Mode unavailable: ${mode}`);
        else {
          elements.mode.value = mode;
          elements.mode.dispatchEvent(new Event("change", { bubbles: true }));
        }
      },
    })),
    { label: "Focus message composer", detail: "Write a message", run: () => elements.input.focus() },
  ];

  function renderPalette() {
    const query = elements.paletteSearch.value.trim().toLowerCase();
    const dynamicCommands = [
      ...(appStatus.modes || []).map((mode) => ({
        label: `Switch to ${mode} mode`,
        detail: "Mode",
        run: () => {
          elements.mode.value = mode;
          elements.mode.dispatchEvent(new Event("change", { bubbles: true }));
        },
      })),
      ...chats.slice(0, 8).map((chat) => ({
        label: chat.title || "New conversation",
        detail: `${chat.mode} · ${formatAge(chat.updated)}`,
        run: () => selectChat(chat.id),
      })),
    ];
    const commands = [...paletteCommands, ...dynamicCommands].filter((command) =>
      `${command.label} ${command.detail}`.toLowerCase().includes(query)
    );
    elements.paletteList.replaceChildren();
    if (!commands.length) {
      const empty = document.createElement("div");
      empty.className = "palette-empty";
      empty.textContent = "No matching commands";
      elements.paletteList.append(empty);
      return;
    }
    paletteIndex = Math.min(paletteIndex, commands.length - 1);
    commands.forEach((command, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `palette-item${index === paletteIndex ? " active" : ""}`;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(index === paletteIndex));
      button.innerHTML = `<span>${escapeHtml(command.label)}</span><small>${escapeHtml(command.detail)}</small>`;
      button.addEventListener("mouseenter", () => {
        paletteIndex = index;
        elements.paletteList.querySelectorAll(".palette-item").forEach((item, itemIndex) => {
          item.classList.toggle("active", itemIndex === index);
          item.setAttribute("aria-selected", String(itemIndex === index));
        });
      });
      button.addEventListener("click", () => {
        closePalette();
        command.run();
      });
      elements.paletteList.append(button);
    });
  }

  function openPalette(initialQuery = "") {
    paletteReturnFocus = document.activeElement;
    elements.paletteSearch.value = initialQuery;
    paletteIndex = 0;
    renderPalette();
    elements.paletteBackdrop.hidden = false;
    elements.paletteSearch.focus();
  }

  function closePalette(restoreFocus = true) {
    elements.paletteBackdrop.hidden = true;
    if (restoreFocus && paletteReturnFocus instanceof HTMLElement) paletteReturnFocus.focus();
  }

  function movePaletteSelection(delta) {
    const options = [...elements.paletteList.querySelectorAll(".palette-item")];
    if (!options.length) return;
    paletteIndex = (paletteIndex + delta + options.length) % options.length;
    options.forEach((option, index) => {
      option.classList.toggle("active", index === paletteIndex);
      option.setAttribute("aria-selected", String(index === paletteIndex));
    });
    options[paletteIndex].scrollIntoView({ block: "nearest" });
  }

  function createCustomPicker(select, wrapper, kind) {
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "picker-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", select.getAttribute("aria-label"));
    trigger.setAttribute("aria-controls", `picker-menu-${kind}`);
    const label = document.createElement("span");
    label.className = "picker-label";
    const detail = document.createElement("span");
    detail.className = "picker-detail";
    const menu = document.createElement("div");
    menu.className = `picker-menu picker-menu-${kind}`;
    menu.id = `picker-menu-${kind}`;
    menu.setAttribute("role", "listbox");
    menu.setAttribute("aria-label", select.getAttribute("aria-label"));
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("viewBox", "0 0 20 20");
    chevron.setAttribute("aria-hidden", "true");
    chevron.classList.add("chevron");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "m5 7.5 5 5 5-5");
    chevron.append(path);
    trigger.append(label, detail, chevron);
    wrapper.insertBefore(trigger, select);
    wrapper.append(menu);
    select.classList.add("native-picker-source");
    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    let options = [];
    let currentIndex = -1;
    const close = (restoreFocus = false) => {
      wrapper.classList.remove("picker-open");
      trigger.setAttribute("aria-expanded", "false");
      if (restoreFocus) trigger.focus();
    };
    const focusOption = (index) => {
      if (!options.length) return;
      currentIndex = (index + options.length) % options.length;
      options[currentIndex].focus();
    };
    const selectOption = (option) => {
      if (!option || option.disabled) return;
      select.value = option.dataset.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      close(true);
    };
    const refresh = () => {
      const selected = select.selectedOptions[0];
      label.textContent = kind === "mode"
        ? selected?.textContent || selected?.value || "Choose"
        : selected?.value || "Choose";
      detail.textContent = kind === "model" && selected
        ? (selected.textContent.includes("agent tools") ? "AGENT" : "CHAT")
        : "";
      trigger.disabled = select.disabled || !select.options.length;
      trigger.title = select.title || selected?.textContent || "";
      menu.replaceChildren();
      options = [...select.options].map((sourceOption) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "picker-option";
        option.setAttribute("role", "option");
        option.tabIndex = -1;
        option.dataset.value = sourceOption.value;
        option.disabled = sourceOption.disabled;
        option.setAttribute("aria-selected", String(sourceOption.selected));
        const name = document.createElement("span");
        name.className = "picker-option-name";
        name.textContent = kind === "model" ? sourceOption.value : sourceOption.textContent;
        if (kind === "mode") {
          const mode = sourceOption.value;
          const details = MODE_DETAILS[mode] || {
            icon: "✦",
            description: `A dedicated ${sourceOption.textContent.toLowerCase()} mode.`,
            best: "Best for tasks that match this mode.",
          };
          option.classList.add("picker-option-mode");
          if (mode === "agent") option.classList.add("picker-option-agent");
          const title = document.createElement("span");
          title.className = "picker-mode-title";
          const icon = document.createElement("span");
          icon.className = "picker-mode-icon";
          icon.textContent = details.icon;
          title.append(icon, name);
          const description = document.createElement("span");
          description.className = "picker-option-description";
          description.textContent = details.description;
          const best = document.createElement("span");
          best.className = "picker-option-best";
          best.textContent = details.best;
          option.append(title, description, best);
        } else {
          option.append(name);
        }
        if (kind === "model") {
          const capability = document.createElement("span");
          capability.className = "picker-option-meta";
          const size = sourceOption.value.match(/\b\d+(?:\.\d+)?b\b/i)?.[0]?.toUpperCase();
          const recommended = sourceOption.value === appStatus.recommended_agent_model;
          const capabilityName = sourceOption.textContent.includes("agent tools")
            ? "AGENT TOOLS"
            : sourceOption.textContent.includes("chat & code") ? "CHAT & CODE" : "CHAT ONLY";
          capability.textContent = [recommended ? "RECOMMENDED" : "", size, capabilityName]
            .filter(Boolean).join(" · ");
          if (recommended) option.classList.add("picker-option-recommended");
          option.append(capability);
        }
        option.addEventListener("click", () => selectOption(option));
        option.addEventListener("keydown", (event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            focusOption(currentIndex + 1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            focusOption(currentIndex - 1);
          } else if (event.key === "Home") {
            event.preventDefault();
            focusOption(0);
          } else if (event.key === "End") {
            event.preventDefault();
            focusOption(options.length - 1);
          } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectOption(option);
          } else if (event.key === "Escape" || event.key === "Tab") {
            close(event.key === "Escape");
          }
        });
        menu.append(option);
        return option;
      });
      menu.hidden = !options.length;
    };
    trigger.addEventListener("click", () => {
      if (trigger.disabled) return;
      if (wrapper.classList.contains("picker-open")) {
        close();
        return;
      }
      document.querySelectorAll(".picker-open").forEach((openPicker) => {
        openPicker.classList.remove("picker-open");
        openPicker.querySelector(".picker-trigger")?.setAttribute("aria-expanded", "false");
      });
      wrapper.classList.add("picker-open");
      trigger.setAttribute("aria-expanded", "true");
      currentIndex = Math.max(0, [...select.options].findIndex((option) => option.selected));
      focusOption(currentIndex);
    });
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (!wrapper.classList.contains("picker-open")) trigger.click();
        else focusOption(currentIndex + (event.key === "ArrowUp" ? -1 : 1));
      } else if (event.key === "Escape") {
        close();
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!wrapper.contains(event.target)) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && wrapper.classList.contains("picker-open")) close(true);
    });
    select.addEventListener("change", refresh);
    refresh();
    return refresh;
  }

  const refreshModePicker = createCustomPicker(elements.mode, $(".current-mode"), "mode");
  const refreshModelPicker = createCustomPicker(elements.model, $(".model-picker"), "model");

  function loadChats() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(saved)) throw new TypeError("Saved conversation data is not a list");
      return saved.filter((chat) =>
        chat && typeof chat.id === "string" && Array.isArray(chat.messages)
      ).map((chat) => ({
        ...chat,
        title: typeof chat.title === "string" ? chat.title : "New conversation",
        mode: typeof chat.mode === "string" ? chat.mode : "default",
        model: typeof chat.model === "string" ? chat.model : "",
        options: { ...preferences.options, ...(chat.options || {}) },
        permission_mode: ["manual", "auto_safe", "allow_all"].includes(chat.permission_mode)
          ? chat.permission_mode : preferences.permission_mode,
        pinned: chat.pinned === true,
        archived: chat.archived === true,
        updated: Number.isFinite(chat.updated) ? chat.updated : 0,
        messages: chat.messages.filter((message) =>
          message
          && (message.role === "user" || message.role === "assistant")
          && typeof message.content === "string"
          && (message.content.trim() || message.activities?.length || message.attachments?.length)
        ),
      })).map((chat) => {
        for (const message of chat.messages) {
          message.progress = "";
          message.activities = Array.isArray(message.activities)
            ? message.activities.filter((activity) => activity && typeof activity === "object")
            : [];
          message.attachments = Array.isArray(message.attachments)
            ? message.attachments.filter((file) => file && typeof file === "object").map((file) => ({
              ...file,
              name: typeof file.name === "string" ? file.name : "attachment",
              size: Number.isFinite(file.size) ? file.size : 0,
              content: typeof file.content === "string" ? file.content : "",
            }))
            : [];
          if (Array.isArray(message.activities)) {
            for (const activity of message.activities) {
              if (activity.status === "working") activity.status = "interrupted";
              if (activity.confirmation) {
                activity.confirmation = null;
                activity.confirmationState = "expired";
              }
            }
          }
        }
        return chat;
      });
    } catch (error) {
      console.error("Could not load saved conversations:", error);
      setTimeout(() => showToast("Saved conversation history could not be loaded."), 0);
      return [];
    }
  }

  function loadActiveChatId() {
    try {
      const savedId = localStorage.getItem(ACTIVE_CHAT_KEY);
      if (savedId === "") return "";
      if (savedId && chats.some((chat) => chat.id === savedId)) return savedId;
    } catch (error) {
      console.error("Could not restore the selected conversation:", error);
    }
    return [...chats].sort((a, b) => b.updated - a.updated)[0]?.id || "";
  }

  function persistPreferences() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(preferences));
      return true;
    } catch (error) {
      console.error("Could not save web preferences:", error);
      showToast("Browser storage could not save settings.");
      return false;
    }
  }

  function openHistoryDatabase() {
    if (!("indexedDB" in window)) return Promise.reject(new Error("IndexedDB is not available"));
    if (!historyDatabasePromise) {
      historyDatabasePromise = new Promise((resolve, reject) => {
        const request = indexedDB.open("midnight-signal-history", 1);
        request.onupgradeneeded = () => {
          if (!request.result.objectStoreNames.contains("history")) {
            request.result.createObjectStore("history", { keyPath: "id" });
          }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error("Could not open conversation storage"));
        request.onblocked = () => reject(new Error("Conversation storage upgrade is blocked by another tab"));
      });
    }
    return historyDatabasePromise;
  }

  function readHistoryFromIndexedDB() {
    return openHistoryDatabase().then((database) => new Promise((resolve, reject) => {
      const request = database.transaction("history", "readonly").objectStore("history").get("conversations");
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error || new Error("Could not read saved conversations"));
    }));
  }

  function queueHistoryBackup(savedChats, savedAt, selectedChatId = activeChatId) {
    historyWriteQueue = historyWriteQueue.catch(() => {}).then(async () => {
      const database = await openHistoryDatabase();
      await new Promise((resolve, reject) => {
        const transaction = database.transaction("history", "readwrite");
        transaction.objectStore("history").put({
          id: "conversations",
          chats: savedChats,
          activeChatId: selectedChatId,
          savedAt,
        });
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error || new Error("Could not save conversation backup"));
        transaction.onabort = () => reject(transaction.error || new Error("Conversation backup was aborted"));
      });
      if (localHistoryUnavailable && !indexedDbUnavailable) {
        showToast("Conversation history is safely stored in IndexedDB. Export it regularly.");
      }
      indexedDbUnavailable = false;
    }).catch((error) => {
      console.error("Could not save IndexedDB conversation backup:", error);
      if (!indexedDbUnavailable) {
        indexedDbUnavailable = true;
        showToast("History backup failed. Export this conversation to avoid losing it.");
      }
    });
  }

  async function restoreIndexedDBHistory() {
    try {
      const backup = await readHistoryFromIndexedDB();
      if (!backup || !Array.isArray(backup.chats)) return;
      const localSavedAt = Number(localStorage.getItem(HISTORY_SAVED_AT_KEY)) || 0;
      if (backup.savedAt > localSavedAt) {
        chats = backup.chats.filter((chat) => chat && typeof chat.id === "string" && Array.isArray(chat.messages));
        activeChatId = chats.some((chat) => chat.id === backup.activeChatId)
          ? backup.activeChatId
          : (chats[0]?.id || "");
        saveActiveChat();
        localHistoryUnavailable = true;
        renderSidebar();
        renderMessages();
        showToast("Restored your latest conversation history from IndexedDB.");
      } else if (localSavedAt > backup.savedAt) {
        queueHistoryBackup(chats.map((chat) => ({ ...chat })), localSavedAt, activeChatId);
      }
    } catch (error) {
      console.error("Could not restore IndexedDB conversation history:", error);
      if (!indexedDbUnavailable) {
        indexedDbUnavailable = true;
        showToast("IndexedDB history could not be read. Your browser-storage copy is still available.");
      }
    }
  }

  function applyPreferences() {
    const automaticTheme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.body.dataset.theme = preferences.theme === "auto" ? automaticTheme : preferences.theme;
    document.body.classList.toggle(
      "sidebar-collapsed",
      preferences.sidebar_collapsed || matchMedia("(max-width: 760px)").matches
    );
  }

  function openSettings(focusField = "") {
    const form = elements.settingsForm;
    for (const [key, value] of Object.entries(preferences.options)) {
      const input = form.elements.namedItem(key);
      if (input) input.value = String(value);
    }
    form.elements.namedItem("theme").value = preferences.theme;
    form.elements.namedItem("sound").checked = preferences.sound;
    form.elements.namedItem("volume").value = String(preferences.volume);
    form.elements.namedItem("permission_mode").value = preferences.permission_mode;
    form.elements.namedItem("sidebar_collapsed").checked = preferences.sidebar_collapsed;
    elements.soundVolume.value = `${preferences.volume}%`;
    elements.settingsBackdrop.hidden = false;
    void refreshMcpSettings();
    if (focusField) {
      elements.settingsForm.elements.namedItem(focusField)?.focus();
      if (focusField === "theme") {
        elements.settingsForm.elements.namedItem("theme").value = preferences.theme;
      }
    } else $("#close-settings").focus();
  }

  async function refreshMcpSettings() {
    elements.mcpStatus.textContent = "Checking MCP configuration…";
    try {
      const response = await fetch("/api/mcp-status", { cache: "no-store" });
      const status = await response.json();
      if (!response.ok) {
        throw new Error(status.error || `Server returned ${response.status}`);
      }
      elements.mcpConfigPath.textContent = status.config_path;
      if (status.error) {
        elements.mcpStatus.textContent = `Configuration error: ${status.error}`;
      } else if (!status.sdk_available) {
        elements.mcpStatus.textContent = "MCP requires Python 3.10 or newer and the installed MCP SDK.";
      } else if (status.configured_servers.length) {
        elements.mcpStatus.textContent = `Configured local servers: ${status.configured_servers.join(", ")}. Restart Studio after editing this file.`;
      } else {
        elements.mcpStatus.textContent = "No MCP servers configured. Existing built-in tools remain available.";
      }
    } catch (error) {
      console.error("Could not load MCP integration status:", error);
      elements.mcpStatus.textContent = `Could not load MCP configuration status: ${error.message}`;
    }
  }

  function closeSettings() {
    elements.settingsBackdrop.hidden = true;
    applyPreferences();
    elements.settingsButton.focus();
  }

  function renderPhoneAccess(links = []) {
    elements.mobileAccessLinks.replaceChildren();
    for (const value of links) {
      let url;
      try {
        url = new URL(value);
      } catch (error) {
        console.error("The server returned an invalid phone-access link:", error);
        continue;
      }
      if (url.protocol !== "http:" || !url.searchParams.has("access")) continue;
      const card = document.createElement("div");
      card.className = "mobile-access-link-card";
      const row = document.createElement("div");
      row.className = "mobile-access-link-row";
      const anchor = document.createElement("a");
      anchor.href = url.href;
      anchor.textContent = url.href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copy link";
      copy.addEventListener("click", async () => {
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(url.href);
          } else {
            const temporary = document.createElement("textarea");
            temporary.value = url.href;
            temporary.style.position = "fixed";
            temporary.style.opacity = "0";
            document.body.append(temporary);
            temporary.select();
            const copied = document.execCommand("copy");
            temporary.remove();
            if (!copied) throw new Error("Clipboard access is unavailable");
          }
          showToast("Private phone link copied");
        } catch (error) {
          console.error("Could not copy the phone-access link:", error);
          showToast("Could not copy the link. Select and copy it manually.");
        }
      });
      const qr = document.createElement("img");
      qr.className = "mobile-access-qr";
      qr.alt = `Scan to open Midnight Signal at ${url.host}`;
      qr.src = `/api/mobile-qr?url=${encodeURIComponent(url.href)}`;
      qr.addEventListener("error", () => {
        qr.hidden = true;
        showToast("Could not create a phone QR code. Use Copy link instead.");
      }, { once: true });
      row.append(anchor, copy);
      card.append(row, qr);
      elements.mobileAccessLinks.append(card);
    }
    elements.mobileAccessStart.hidden = phoneAccessEnabled;
    elements.mobileAccessStop.hidden = !phoneAccessEnabled;
  }

  async function requestPhoneAccess(action) {
    const response = await fetch("/api/mobile-access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
      cache: "no-store",
    });
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new Error(`Phone access returned an unreadable response (${response.status}).`);
    }
    if (!response.ok) throw new Error(payload.error || `Phone access failed (${response.status}).`);
    phoneAccessEnabled = payload.enabled === true;
    renderPhoneAccess(Array.isArray(payload.links) ? payload.links : []);
    return payload;
  }

  async function openPhoneAccess() {
    elements.mobileAccessBackdrop.hidden = false;
    elements.mobileAccessStart.disabled = true;
    elements.mobileAccessLinks.textContent = "Checking phone access…";
    $("#close-mobile-access").focus();
    try {
      await requestPhoneAccess("status");
    } catch (error) {
      console.error("Could not check phone access status:", error);
      elements.mobileAccessLinks.textContent = error.message;
    } finally {
      elements.mobileAccessStart.disabled = false;
    }
  }

  function closePhoneAccess() {
    elements.mobileAccessBackdrop.hidden = true;
    elements.mobileAccessButton.focus();
  }

  async function startPhoneAccess() {
    elements.mobileAccessStart.disabled = true;
    elements.mobileAccessLinks.textContent = "Starting a private Wi-Fi connection…";
    try {
      const result = await requestPhoneAccess("start");
      if (result.links?.length) {
        showToast("Phone access is ready. Open a link on your phone.");
      } else {
        elements.mobileAccessLinks.textContent = "No private network link is available.";
      }
    } catch (error) {
      console.error("Could not start phone access:", error);
      elements.mobileAccessLinks.textContent = error.message;
    } finally {
      elements.mobileAccessStart.disabled = false;
    }
  }

  async function stopPhoneAccess() {
    elements.mobileAccessStop.disabled = true;
    try {
      await requestPhoneAccess("stop");
      showToast("Phone access stopped");
    } catch (error) {
      console.error("Could not stop phone access:", error);
      showToast(error.message);
    } finally {
      elements.mobileAccessStop.disabled = false;
    }
  }

  function playUiSound(kind) {
    if (!preferences.sound || preferences.volume <= 0) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      const context = new AudioContextClass();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      const frequencies = { done: 660, tool: 520, error: 180, approval: 780 };
      oscillator.frequency.value = frequencies[kind] || 440;
      oscillator.type = "sine";
      gain.gain.value = (preferences.volume / 100) * 0.045;
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.09);
      oscillator.addEventListener("ended", () => context.close(), { once: true });
    } catch (error) {
      console.warn("Could not play interface sound:", error);
    }
  }

  function saveSettingsFromForm(event) {
    event.preventDefault();
    const form = elements.settingsForm;
    const options = {};
    const bounds = {
      temperature: [0, 2], top_p: [0, 1], top_k: [1, 1000],
      repeat_penalty: [0.5, 2], num_ctx: [512, 131072], num_predict: [-1, 32768],
    };
    for (const [key, [minimum, maximum]] of Object.entries(bounds)) {
      const input = form.elements.namedItem(key);
      const value = Number(input.value);
      if (!Number.isFinite(value) || value < minimum || value > maximum) {
        input.focus();
        showToast(`${key} must be between ${minimum} and ${maximum}.`);
        return;
      }
      options[key] = ["top_k", "num_ctx", "num_predict"].includes(key) ? Math.round(value) : value;
    }
    preferences = {
      ...preferences,
      options,
      theme: form.elements.namedItem("theme").value,
      sound: form.elements.namedItem("sound").checked,
      volume: Number(form.elements.namedItem("volume").value),
      permission_mode: form.elements.namedItem("permission_mode").value,
      sidebar_collapsed: form.elements.namedItem("sidebar_collapsed").checked,
    };
    const chat = activeChat();
    if (chat) {
      chat.options = { ...options };
      chat.permission_mode = preferences.permission_mode;
      elements.permission.value = chat.permission_mode;
      saveChats();
    }
    persistPreferences();
    applyPreferences();
    updateModeControls();
    closeSettings();
    showToast("Settings saved");
    playUiSound("approval");
  }

  function updatePermissionControl() {
    const isAgent = elements.mode.value === "agent";
    elements.permissionControl.hidden = !isAgent;
    elements.permission.disabled = streaming || preparingMessage || !isAgent;
  }

  function updateThinkingControl() {
    const isQwen3 = /^qwen3(?::|$)/i.test(elements.model.value);
    elements.thinkingControl.hidden = !isQwen3;
    elements.thinking.disabled = streaming || preparingMessage || !isQwen3;
  }

  function updateModeControls() {
    const isAgent = elements.mode.value === "agent";
    const agentModels = appStatus.agent_models || [];
    const selectedModel = elements.model.value;
    const selectedModelSupportsTools = agentModels.includes(selectedModel);
    const isQwen3 = /^qwen3(?::|$)/i.test(selectedModel);
    elements.input.placeholder = isAgent
      ? "Ask the coding agent to inspect or change this workspace…"
      : "Send a message...";
    if (isAgent) {
      elements.composerNote.textContent = selectedModelSupportsTools
        ? (isQwen3
          ? `Qwen3 agent tools are enabled. ${elements.thinking.value === "on" ? "Think mode shows high-level live progress stages; private reasoning stays hidden. It is slower." : "Fast mode responds quicker; live tool activity still appears."}`
          : "Workspace reads stay local.")
        : (agentModels.length
          ? "This model can chat and generate code, but cannot edit workspace files. Choose a tool-enabled model."
          : "No installed model supports agent tools. Chat and code generation still work.");
    } else if (isQwen3) {
      elements.composerNote.textContent = elements.thinking.value === "on"
        ? "Qwen3 Think mode is on: extra reasoning before the answer, with a slower response."
        : "Qwen3 Fast mode is on: tool calling and multi-step agent work stay available; extra reasoning is skipped.";
    } else if (selectedModel && !selectedModelSupportsTools) {
      elements.composerNote.textContent =
        "Chat and code generation are available. Switch to Coding agent with a tool-enabled model to edit workspace files.";
    } else {
      elements.composerNote.textContent = "Midnight Signal can make mistakes. Verify important information.";
    }
    if (isAgent) {
      const permissionNotes = {
        manual: "Edits, commands, and external web requests ask before running.",
        auto_safe: "Only simple read-only checks auto-run; edits, other commands, and web requests still ask.",
        allow_all: "Agent actions run without per-action approval; web requests send queries or URLs externally.",
      };
      elements.composerNote.textContent += ` ${permissionNotes[elements.permission.value] || permissionNotes.manual}`;
    }
    elements.model.title = selectedModelSupportsTools
      ? `${selectedModel} supports coding-agent tools`
      : `${selectedModel} is available for chat and code generation; it cannot use workspace tools`;
    elements.composerNote.title = isQwen3
      ? "Fast mode responds quicker and still shows live tool activity. Think mode adds slower high-level progress stages; private reasoning is not displayed."
      : "";
    updateThinkingControl();
    updatePermissionControl();
    elements.mode.disabled = streaming || preparingMessage;
    elements.model.disabled = streaming || preparingMessage;
    refreshModePicker();
    refreshModelPicker();
    elements.send.disabled = isAgent
      ? (!selectedModelSupportsTools && !streaming) || preparingMessage
      : (appStatus.models.length === 0 && !streaming) || preparingMessage;
  }

  function saveChats() {
    chats.sort((a, b) => b.updated - a.updated);
    let savedChats;
    try {
      const persistChat = (chat) => ({
        ...chat,
        messages: chat.messages.map((message) => {
          const { progress, progressNotes, ...savedMessage } = message;
          if (Array.isArray(message.activities)) {
            savedMessage.activities = message.activities.slice(-12).map((activity) => ({
              ...activity,
              args: { preview: JSON.stringify(activity.args || {}).slice(0, 1200) },
              result: (activity.result || "").slice(0, 1200),
              confirmation: null,
              confirmationState: activity.confirmation ? "expired" : activity.confirmationState,
            }));
          }
          return savedMessage;
        }),
      });
      savedChats = chats.map(persistChat);
      const serialized = JSON.stringify(savedChats);
      const savedAt = Date.now();
      if (serialized.length > LOCAL_HISTORY_LIMIT) {
        localHistoryUnavailable = true;
      } else {
        localStorage.setItem(STORAGE_KEY, serialized);
        localStorage.setItem(HISTORY_SAVED_AT_KEY, String(savedAt));
        localHistoryUnavailable = false;
      }
      queueHistoryBackup(savedChats, savedAt, activeChatId);
      saveActiveChat();
    } catch (error) {
      console.error("Could not save conversation history:", error);
      localHistoryUnavailable = true;
      if (savedChats) {
        queueHistoryBackup(savedChats, Date.now(), activeChatId);
      } else {
        showToast("Could not prepare conversation history for saving. Export this conversation now.");
      }
    }
  }

  function saveActiveChat() {
    try {
      localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId);
    } catch (error) {
      console.error("Could not save the selected conversation:", error);
      showToast("Browser storage could not remember the selected conversation.");
    }
  }

  function activeChat() {
    return chats.find((chat) => chat.id === activeChatId) || null;
  }

  function makeChat() {
    return {
      id: createLocalId(),
      title: "New conversation",
      mode: elements.mode.value || "default",
      model: elements.model.value || appStatus.model,
      options: { ...preferences.options },
      think: false,
      permission_mode: preferences.permission_mode,
      messages: [],
      updated: Date.now(),
    };
  }

  function ensureChat() {
    let chat = activeChat();
    if (!chat) {
      chat = makeChat();
      chats.unshift(chat);
      activeChatId = chat.id;
    }
    return chat;
  }

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function inlineMarkdown(value) {
    let text = escapeHtml(value);
    const code = [];
    text = text.replace(/(`+)([^\n]*?)\1/g, (_, ticks, content) => {
      const index = code.push(`<code class="inline">${content.replace(/`/g, "")}</code>`) - 1;
      return `\u0000INLINE${index}\u0000`;
    });
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    text = text.replace(/(^|\s)(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    return text.replace(/\u0000INLINE(\d+)\u0000/g, (_, index) => code[Number(index)]);
  }

  function renderMarkdown(markdown) {
    const lines = markdown.split(/\r?\n/);
    const output = [];
    let paragraph = [];

    const flushParagraph = () => {
      if (paragraph.length) {
        output.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
        paragraph = [];
      }
    };
    const renderList = (items) => {
      const root = { children: [] };
      const stack = [];
      for (const item of items) {
        while (stack.length && item.indent < stack[stack.length - 1].indent) stack.pop();
        let frame = stack[stack.length - 1];
        let parent;
        if (frame && item.indent > frame.indent) {
          parent = frame.lastItem.children;
        } else if (frame && item.indent === frame.indent && frame.type === item.type) {
          parent = null;
        } else {
          if (frame && item.indent === frame.indent) stack.pop();
          parent = stack.length ? stack[stack.length - 1].lastItem.children : root.children;
          frame = null;
        }
        let list = frame && item.indent === frame.indent && frame.type === item.type
          ? frame.list
          : null;
        if (!list) {
          list = { listType: item.type, children: [] };
          parent.push(list);
        }
        const entry = { text: item.text, children: [] };
        list.children.push(entry);
        if (!frame || item.indent > frame.indent || frame.type !== item.type) {
          stack.push({ indent: item.indent, type: item.type, list, lastItem: entry });
        } else {
          frame.lastItem = entry;
        }
      }
      const renderNode = (node) => node.listType
        ? `<${node.listType}>${node.children.map(renderNode).join("")}</${node.listType}>`
        : `<li>${inlineMarkdown(node.text)}${node.children.map(renderNode).join("")}</li>`;
      return root.children.map(renderNode).join("");
    };

    for (let i = 0; i < lines.length;) {
      const line = lines[i];
      const fence = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
      if (fence) {
        flushParagraph();
        const marker = fence[1][0];
        const closing = new RegExp(`^\\s*${marker}{${fence[1].length},}\\s*$`);
        const code = [];
        i += 1;
        while (i < lines.length && !closing.test(lines[i])) code.push(lines[i++]);
        if (i < lines.length) i += 1;
        const language = fence[2].trim().split(/\s+/)[0] || "code";
        const copyLabel = language === "code" ? "code snippet" : `${language} code`;
        output.push(`<div class="code-wrap"><div class="code-head"><span>${escapeHtml(language)}</span><button class="copy-code" type="button" aria-label="Copy ${escapeHtml(copyLabel)}">Copy</button></div><pre><code>${escapeHtml(code.join("\n"))}</code></pre></div>`);
        continue;
      }
      if (!line.trim()) {
        flushParagraph();
        i += 1;
        continue;
      }
      const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
      if (heading) {
        flushParagraph();
        const level = heading[1].length;
        output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
        i += 1;
        continue;
      }
      if (/^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line)) {
        flushParagraph();
        output.push("<hr>");
        i += 1;
        continue;
      }
      if (/^\s*\|?.+\|.+\|?\s*$/.test(line) && i + 1 < lines.length
        && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i + 1])) {
        flushParagraph();
        const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
        const headers = cells(line);
        const alignments = cells(lines[i + 1]).map((cell) =>
          cell.startsWith(":") && cell.endsWith(":") ? "center" : cell.endsWith(":") ? "right" : cell.startsWith(":") ? "left" : ""
        );
        const rows = [];
        i += 2;
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(cells(lines[i++]));
        const rowHtml = (values, tag) => `<tr>${headers.map((_, index) => `<${tag}${alignments[index] ? ` style="text-align:${alignments[index]}"` : ""}>${inlineMarkdown(values[index] || "")}</${tag}>`).join("")}</tr>`;
        output.push(`<div class="markdown-table-wrap"><table><thead>${rowHtml(headers, "th")}</thead><tbody>${rows.map((row) => rowHtml(row, "td")).join("")}</tbody></table></div>`);
        continue;
      }
      if (/^\s{0,3}>\s?/.test(line)) {
        flushParagraph();
        const quote = [];
        while (i < lines.length && /^\s{0,3}>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^\s{0,3}>\s?/, ""));
        output.push(`<blockquote>${renderMarkdown(quote.join("\n"))}</blockquote>`);
        continue;
      }
      const listMatch = line.match(/^(\s*)(\d+[.)]|[-*+])\s+(.+)$/);
      if (listMatch) {
        flushParagraph();
        const items = [];
        while (i < lines.length) {
          const match = lines[i].match(/^(\s*)(\d+[.)]|[-*+])\s+(.+)$/);
          if (!match) break;
          items.push({
            indent: match[1].replace(/\t/g, "  ").length,
            type: /^\d/.test(match[2]) ? "ol" : "ul",
            text: match[3],
          });
          i += 1;
        }
        output.push(renderList(items));
        continue;
      }
      paragraph.push(line);
      i += 1;
    }
    flushParagraph();
    return output.join("") || "<p></p>";
  }

  function historyMessageContent(message, includeActivity) {
    let content = message.content || "";
    if (includeActivity && message.role === "assistant" && message.activities?.length) {
      const activityHistory = message.activities.slice(-6).map((activity) => {
        const args = JSON.stringify(activity.args || {}).slice(0, 800);
        const result = (activity.result || "").slice(0, 1600);
        const state = activity.status || activity.confirmationState || "unknown";
        return `- ${activity.name || "tool"}(${args}) [${state}]\n  Result: ${result || "(no result recorded)"}`;
      });
      content += `\n\n[Previous workspace tool activity; results are historical context]\n${activityHistory.join("\n")}`;
    }
    return content;
  }

  function isNearBottom() {
    return elements.chatScroll.scrollHeight - elements.chatScroll.scrollTop - elements.chatScroll.clientHeight < 100;
  }

  function scrollToBottom() {
    elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
  }

  function formatAge(timestamp) {
    const date = new Date(timestamp);
    if (!Number.isFinite(date.getTime())) return "—";
    const age = Date.now() - date.getTime();
    if (age < 60_000) return "now";
    if (age < 3_600_000) return `${Math.floor(age / 60_000)}m`;
    if (age < 86_400_000) return `${Math.floor(age / 3_600_000)}h`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function conversationGroup(timestamp) {
    const date = new Date(timestamp);
    if (!Number.isFinite(date.getTime())) return "Older";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);
    if (date >= today) return "Today";
    if (date >= yesterday) return "Yesterday";
    if (date >= weekAgo) return "Previous 7 days";
    return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  function setWorkspaceDisplay(path) {
    const workspace = typeof path === "string" ? path : "";
    elements.workspaceName.textContent = workspace
      ? workspace.split(/[\\/]/).filter(Boolean).pop() || workspace
      : "Workspace";
    elements.workspace.title = workspace
      ? `${workspace}\nClick to change workspace · Shift-click or right-click to copy`
      : "Workspace path unavailable. Click to set it.";
  }

  function renderSidebar() {
    const scrollPosition = elements.conversationList.scrollTop;
    elements.conversationList.replaceChildren();
    const query = elements.historySearch.value.trim().toLowerCase();
    const filter = elements.historyFilter.value;
    const groups = new Map();
    let visibleChats = 0;
    const orderedChats = [...chats].sort((a, b) =>
      Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || b.updated - a.updated
    );
    for (const chat of orderedChats) {
      if (filter === "active" && chat.archived) continue;
      if (filter === "archived" && !chat.archived) continue;
      if (filter === "pinned" && (!chat.pinned || chat.archived)) continue;
      const matchesQuery = !query
        || (chat.title || "New conversation").toLowerCase().includes(query)
        || chat.messages.some((message) =>
          (message.content || "").toLowerCase().includes(query)
          || (message.attachments || []).some((file) =>
            (file.name || "").toLowerCase().includes(query)
          )
          || (Array.isArray(message.progressNotes) && message.progressNotes.some((note) =>
            typeof note === "string" && note.toLowerCase().includes(query)
          ))
          || (Array.isArray(message.activities) && message.activities.some((activity) => {
            if (!activity || typeof activity !== "object") return false;
            const searchable = [
              activity.name,
              activity.result,
              JSON.stringify(activity.args || {}),
            ];
            return searchable.some((value) =>
              typeof value === "string" && value.toLowerCase().includes(query)
            );
          }))
        );
      if (!matchesQuery) continue;
      visibleChats += 1;
      const groupName = chat.pinned && !chat.archived
        ? "Pinned"
        : conversationGroup(chat.updated);
      if (!groups.has(groupName)) groups.set(groupName, []);
      groups.get(groupName).push(chat);
    }

    const entries = [];
    for (const [groupName, groupChats] of groups) {
      entries.push({ type: "heading", groupName, offset: 0, height: 34 });
      for (const chat of groupChats) entries.push({ type: "chat", groupName, chat, offset: 0, height: 47 });
    }
    let totalHeight = 0;
    for (const entry of entries) {
      entry.offset = totalHeight;
      totalHeight += entry.height;
    }
    let firstEntry = 0;
    let lastEntry = entries.length;
    if (visibleChats > 100) {
      const overscan = 250;
      const viewportStart = Math.max(0, scrollPosition - overscan);
      const viewportEnd = scrollPosition
        + Math.max(elements.conversationList.clientHeight, 500) + overscan;
      firstEntry = entries.findIndex((entry) => entry.offset + entry.height >= viewportStart);
      if (firstEntry < 0) firstEntry = entries.length;
      lastEntry = entries.findIndex((entry) => entry.offset > viewportEnd);
      if (lastEntry < 0) lastEntry = entries.length;
    }
    const visibleEntries = entries.slice(firstEntry, lastEntry);
    const visibleChatIds = new Set(
      visibleEntries.filter((entry) => entry.type === "chat").map((entry) => entry.chat.id)
    );
    const visibleGroupHeadings = new Set(
      visibleEntries.filter((entry) => entry.type === "heading").map((entry) => entry.groupName)
    );
    const appendSpacer = (height) => {
      if (height <= 0) return;
      const spacer = document.createElement("div");
      spacer.className = "conversation-spacer";
      spacer.setAttribute("aria-hidden", "true");
      spacer.style.height = `${height}px`;
      elements.conversationList.append(spacer);
    };
    if (visibleChats > 100) {
      appendSpacer(visibleEntries[0]?.offset || totalHeight);
    }

    for (const [groupName, groupChats] of groups) {
      const chatsInWindow = visibleChats > 100
        ? groupChats.filter((chat) => visibleChatIds.has(chat.id))
        : groupChats;
      if (!chatsInWindow.length && !visibleGroupHeadings.has(groupName)) continue;
      const group = document.createElement("section");
      group.className = "conversation-group";
      if (visibleChats <= 100 || visibleGroupHeadings.has(groupName)) {
        const heading = document.createElement("h2");
        heading.className = "conversation-group-heading";
        heading.textContent = groupName;
        group.append(heading);
      }
      for (const chat of chatsInWindow) {
        const row = document.createElement("div");
        row.className = "conversation-row";
        const button = document.createElement("button");
        button.type = "button";
        button.className = `conversation-item${chat.id === activeChatId ? " active" : ""}`;
        button.title = chat.title;
        button.setAttribute("aria-current", chat.id === activeChatId ? "page" : "false");
        const copy = document.createElement("span");
        copy.className = "conversation-copy";
        const title = document.createElement("span");
        title.className = "conversation-title";
        title.textContent = `${chat.pinned ? "📌 " : ""}${chat.title || "New conversation"}`;
        const meta = document.createElement("span");
        meta.className = "conversation-meta";
        meta.textContent = [
          chat.mode === "agent" ? "Coding agent" : "Chat",
          chat.model || "",
        ].filter(Boolean).join(" · ");
        copy.append(title, meta);
        const age = document.createElement("span");
        age.className = "item-date";
        age.textContent = formatAge(chat.updated);
        button.append(copy, age);
        button.addEventListener("click", () => openChat(chat.id));

        const rename = document.createElement("button");
        rename.type = "button";
        rename.className = "rename-conversation";
        rename.setAttribute("aria-label", `Rename ${chat.title || "conversation"}`);
        rename.title = "Rename conversation";
        rename.textContent = "✎";
        rename.addEventListener("click", (event) => {
          event.stopPropagation();
          if (streaming || preparingMessage) return;
          const nextTitle = window.prompt("Rename conversation", chat.title || "New conversation");
          if (nextTitle === null) return;
          const cleanTitle = nextTitle.trim();
          if (!cleanTitle) return;
          if (cleanTitle.length > 80) {
            showToast("Conversation titles are limited to 80 characters.");
            return;
          }
          chat.title = cleanTitle;
          saveChats();
          renderSidebar();
        });

        const pin = document.createElement("button");
        pin.type = "button";
        pin.className = "organize-conversation";
        pin.setAttribute("aria-label", `${chat.pinned ? "Unpin" : "Pin"} ${chat.title || "conversation"}`);
        pin.setAttribute("aria-pressed", String(Boolean(chat.pinned)));
        pin.title = chat.pinned ? "Unpin conversation" : "Pin conversation";
        pin.textContent = chat.pinned ? "📌" : "⌖";
        pin.addEventListener("click", (event) => {
          event.stopPropagation();
          if (streaming || preparingMessage) return;
          chat.pinned = !chat.pinned;
          saveChats();
          renderSidebar();
        });

        const archive = document.createElement("button");
        archive.type = "button";
        archive.className = "organize-conversation";
        archive.setAttribute("aria-label", `${chat.archived ? "Restore" : "Archive"} ${chat.title || "conversation"}`);
        archive.title = chat.archived ? "Restore conversation" : "Archive conversation";
        archive.textContent = chat.archived ? "↩" : "▱";
        archive.addEventListener("click", (event) => {
          event.stopPropagation();
          if (streaming || preparingMessage) return;
          chat.archived = !chat.archived;
          if (chat.archived) chat.pinned = false;
          saveChats();
          renderSidebar();
        });

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "delete-conversation";
        remove.setAttribute("aria-label", `Delete ${chat.title || "conversation"}`);
        remove.title = "Delete conversation";
        remove.textContent = "×";
        remove.disabled = streaming || preparingMessage;
        rename.disabled = streaming || preparingMessage;
        pin.disabled = streaming || preparingMessage;
        archive.disabled = streaming || preparingMessage;
        button.disabled = streaming;
        remove.addEventListener("click", (event) => {
          event.stopPropagation();
          if (streaming || preparingMessage) return;
          if (!window.confirm("Delete this conversation from this browser?")) return;
          const deletedActiveChat = activeChatId === chat.id;
          chats = chats.filter((item) => item.id !== chat.id);
          if (deletedActiveChat) activeChatId = chats[0]?.id || "";
          saveChats();
          if (deletedActiveChat && activeChatId) {
            openChat(activeChatId);
          } else {
            updateModeControls();
            saveChats();
            renderMessages();
          }
        });

        row.append(button, pin, archive, rename, remove);
        group.append(row);
      }
      elements.conversationList.append(group);
    }
    if (visibleChats > 100) {
      const visibleEnd = visibleEntries.length
        ? visibleEntries[visibleEntries.length - 1].offset
          + visibleEntries[visibleEntries.length - 1].height
        : totalHeight;
      appendSpacer(totalHeight - visibleEnd);
    }
    elements.conversationList.scrollTop = scrollPosition;
    if (!visibleChats) {
      const empty = document.createElement("div");
      empty.className = "history-empty";
      empty.textContent = query ? "No conversations match your search." : "Your conversations will appear here.";
      elements.conversationList.append(empty);
    }
    elements.exportChat.disabled = !activeChat()?.messages.some((message) =>
      message.content || message.attachments?.length
    );
  }

  function renderAgentActivity(activity) {
    const fileTools = new Set([
      "write_file",
      "edit_file",
      "create_website_entry",
      "repair_website_entry",
      "create_website_asset",
    ]);
    const isFileWrite = fileTools.has(activity.name);
    const filePath = activity.name === "create_website_entry"
      || activity.name === "repair_website_entry"
      ? "index.html"
      : String(activity.args?.path || "");
    const title = isFileWrite && filePath
      ? `${activity.name === "edit_file" || activity.name === "repair_website_entry" ? "Updating" : "Writing"} ${filePath}`
      : activity.name || "Agent";
    const rawDetails = !isFileWrite && activity.args && Object.keys(activity.args).length
      ? JSON.stringify(activity.args, null, 2)
      : "";
    const details = rawDetails.length > 1200
      ? `${rawDetails.slice(0, 1200)}\n… preview truncated`
      : rawDetails;
    const fullResult = typeof activity.result === "string" ? activity.result : "";
    const result = fullResult.slice(0, 4000);
    const state = activity.confirmationState
      || (activity.confirmation ? "needs approval" : (activity.status || "working"));
    const stateClass = state.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const canResolve = activity.confirmation
      && activeConfirmations.has(activity.confirmation.id);
    const timeoutAt = Number(activity.expiresAt || activity.confirmation?.expiresAt) || 0;
    const remaining = timeoutAt ? Math.max(0, Math.ceil((timeoutAt - Date.now()) / 1000)) : null;
    const undo = activity.undoId && !activity.undone
      ? `<button class="undo-agent-change" data-undo-id="${escapeHtml(activity.undoId)}" type="button" aria-label="Undo agent change to ${escapeHtml(activity.changedPath || "file")}">Undo ${escapeHtml(activity.changedPath || "change")}</button>`
      : "";
    const confirmation = activity.confirmation
      ? `<div class="approval-preview"><strong>${escapeHtml(activity.confirmation.action)} · ${escapeHtml(activity.confirmation.target)}</strong><pre>${escapeHtml(activity.confirmation.preview || "No preview supplied")}</pre>${remaining !== null ? `<span class="approval-countdown${remaining === 0 ? " expired" : ""}" data-confirm-id="${escapeHtml(activity.confirmation.id)}" data-expires-at="${timeoutAt}">${remaining === 0 ? "Approval expired" : `Approval expires in ${remaining}s`}</span>` : ""}${canResolve ? `<div class="approval-actions"><button class="tool-approve" data-confirm-id="${escapeHtml(activity.confirmation.id)}">Approve</button><button class="tool-deny" data-confirm-id="${escapeHtml(activity.confirmation.id)}">Deny</button></div>` : ""}</div>`
      : "";
    const expanded = canResolve || ["working", "running", "needs approval"].includes(state.toLowerCase());
    const linksResult = ["web_search", "web_fetch"].includes(activity.name);
    const renderedResult = escapeHtml(result).replace(
      /https?:\/\/[^\s<]+/g,
      (value) => {
        const punctuation = value.match(/[.,;:!?)}\]]+$/)?.[0] || "";
        const href = value.slice(0, value.length - punctuation.length);
        return `<a href="${href}" target="_blank" rel="noopener noreferrer">${href}</a>${punctuation}`;
      },
    );
    return     `<details class="agent-activity activity-${escapeHtml(stateClass)}"${expanded ? " open" : ""}><summary class="activity-heading"><span class="activity-pulse" aria-hidden="true"></span><strong>${escapeHtml(title)}</strong><span class="activity-state">${escapeHtml(state)}</span></summary><div class="activity-content">${details ? `<pre class="activity-details">${escapeHtml(details)}</pre>` : ""}${result ? `<pre class="activity-result">${linksResult ? renderedResult : escapeHtml(result)}${activity.resultTruncated || fullResult.length > 4000 ? "\n… output truncated" : ""}</pre>` : ""}${confirmation}${undo}</div></details>`;
  }

  function appendGeneratedDownloads(container, message) {
    const downloads = (message.downloads || []).filter((item) =>
      item && typeof item.path === "string" && typeof item.name === "string"
    );
    if (!downloads.length) return;
    const list = document.createElement("div");
    list.className = "project-download-list";
    downloads.forEach((item) => {
      const link = document.createElement("a");
      link.className = "project-download";
      link.href = item.type === "document" || item.type === "website"
        ? `/api/file-download?path=${encodeURIComponent(item.path)}`
        : `/api/download?path=${encodeURIComponent(item.path)}`;
      link.download = item.name;
      const kind = item.type === "zip"
        ? "project ZIP"
        : item.type === "website" ? "HTML file" : "document";
      link.textContent = `Download ${kind} · ${item.name}`;
      list.append(link);
    });
    container.append(list);
  }

  function appendWebsitePreview(container, message) {
    const previewPath = message.websitePreview;
    if (typeof previewPath !== "string" || !/\.(?:html?)$/i.test(previewPath)) return;
    const preview = document.createElement("details");
    preview.className = "website-preview";
    const summary = document.createElement("summary");
    summary.textContent = `Preview website · ${previewPath}`;
    const frame = document.createElement("iframe");
    frame.title = `Sandboxed preview of ${previewPath}`;
    frame.loading = "lazy";
    frame.referrerPolicy = "no-referrer";
    frame.setAttribute("sandbox", "allow-scripts");
    frame.dataset.previewSrc = `/api/site-preview/${previewPath
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/")}`;
    preview.addEventListener("toggle", () => {
      if (preview.open && !streaming && !frame.hasAttribute("src")) {
        frame.src = frame.dataset.previewSrc;
      }
    });
    preview.append(summary, frame);
    preview.open = true;
    container.append(preview);
    if (!streaming) frame.src = frame.dataset.previewSrc;
  }

  function progressForTool(name) {
    if (["read_file", "list_dir", "search_files", "git_status", "git_diff"].includes(name)) {
      return "Exploring the workspace";
    }
    if (["write_file", "edit_file"].includes(name)) return "Building your changes";
    if (name === "run_command") return "Checking the result";
    if (["web_search", "web_fetch"].includes(name)) return "Researching public sources";
    return "Working through the next step";
  }

  function userFacingProgress(text) {
    const phase = String(text || "").trim();
    if (/waiting for the model(?:['’]s)? first response/i.test(phase)) {
      return "Tuning the signal and sketching your next steps…";
    }
    if (/generating a user-facing update/i.test(phase)) {
      return "Bringing the useful details into focus…";
    }
    if (/^analyzing your request$/i.test(phase)) {
      return "Getting oriented to your request…";
    }
    if (/^planning the implementation$/i.test(phase)) {
      return "Mapping out a helpful approach…";
    }
    if (/^preparing the next action$/i.test(phase)) {
      return "Lining up the next step…";
    }
    return phase;
  }

  function progressStagesForPrompt(prompt) {
    const request = String(prompt || "").toLowerCase();
    if (/\b(?:website|web site|html|css|landing page|frontend|front-end|design|ui|ux)\b/.test(request)) {
      return [
        "Mapping the pages and moving parts…",
        "Bringing the layout and details together…",
        "Checking the small touches that make it feel finished…",
      ];
    }
    if (/\b(?:pdf|docx|document|report|summari[sz]e|write|draft)\b/.test(request)) {
      return [
        "Gathering the details that matter…",
        "Shaping them into a clear structure…",
        "Giving the final pass a careful look…",
      ];
    }
    if (/\b(?:code|workspace|project|bug|debug|file|function|test|build)\b/.test(request)) {
      return [
        "Tracing the pieces involved…",
        "Connecting the changes to the right places…",
        "Checking the result for rough edges…",
      ];
    }
    return [
      "Finding a clear path through your question…",
      "Bringing the useful details into focus…",
      "Shaping a considered response…",
    ];
  }

  function isWebsiteBuildRequest(prompt) {
    const request = String(prompt || "").trim();
    if (/^(?:how\b|explain\b|what is\b|why\b|when\b|where\b|tell me about\b|tell me how\b|guide me through\b)/i.test(request)) {
      return false;
    }
    return /\b(?:build|create|make|generate|develop|design|write|code)\b[\s\S]{0,120}\b(?:website|web\s+site|webpage|web\s+page|landing\s+page|site)\b/i.test(request);
  }

  function progressMotionFor(text) {
    const motions = ["orbit", "ripple", "signal"];
    let hash = 0;
    for (const character of String(text || "")) {
      hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
    }
    return motions[hash % motions.length];
  }

  function createProgressIndicator(text) {
    const progress = document.createElement("div");
    progress.className = "agent-progress";
    progress.setAttribute("role", "status");
    progress.setAttribute("aria-live", "polite");
    progress.innerHTML = '<span class="progress-orbit" aria-hidden="true"><span></span><span></span><span></span></span><span></span>';
    progress.dataset.motion = progressMotionFor(text);
    progress.lastElementChild.textContent = userFacingProgress(text);
    return progress;
  }

  function renderMessages(forceBottom = false) {
    const keepAtBottom = isNearBottom();
    const chat = activeChat();
    const messages = chat ? chat.messages : [];
    elements.emptyState.hidden = messages.length > 0;
    elements.messages.replaceChildren();

    messages.forEach((message, index) => {
      const row = document.createElement("article");
      row.className = `message ${message.role}`;
      row.setAttribute(
        "aria-label",
        message.role === "user" ? "Your message" : "Assistant response",
      );
      if (streaming && message.role === "assistant" && index === messages.length - 1) {
        row.setAttribute("aria-busy", "true");
      }
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = message.role === "user" ? "Y" : "✳";
      const content = document.createElement("div");
      content.className = "message-content";
      if (message.role === "assistant") {
        const body = document.createElement("div");
        body.className = "message-body";
        body.innerHTML = renderMarkdown(message.content);
        content.append(body);
        appendWebsitePreview(content, message);
        appendGeneratedDownloads(content, message);
        if (Array.isArray(message.versions) && message.versions.length > 1) {
          const versionControl = document.createElement("div");
          versionControl.className = "response-version-controls";
          const previous = document.createElement("button");
          previous.type = "button";
          previous.className = "message-action response-version";
          previous.dataset.direction = "-1";
          previous.dataset.messageIndex = String(index);
          previous.setAttribute("aria-label", "Show previous response version");
          previous.textContent = "‹";
          const current = document.createElement("span");
          current.textContent = `${Math.max(0, Number(message.activeVersion) || 0) + 1} / ${message.versions.length}`;
          current.setAttribute("aria-live", "polite");
          const next = document.createElement("button");
          next.type = "button";
          next.className = "message-action response-version";
          next.dataset.direction = "1";
          next.dataset.messageIndex = String(index);
          next.setAttribute("aria-label", "Show next response version");
          next.textContent = "›";
          versionControl.append(previous, current, next);
          content.append(versionControl);
        }
      } else {
        const visibleContent = typeof message.displayContent === "string"
          ? message.displayContent
          : message.content;
        content.innerHTML = `<p>${escapeHtml(visibleContent).replace(/\n/g, "<br>")}</p>`;
        for (const file of message.attachments || []) {
          const details = document.createElement("details");
          details.className = "message-attachment";
          const summary = document.createElement("summary");
          summary.textContent = `${file.name} · ${Math.ceil((file.size || 0) / 1024)} KB`;
          summary.title = file.name;
          const preview = document.createElement("pre");
          if (file.encoding === "base64" || file.name?.toLowerCase().endsWith(".pdf")) {
            preview.textContent = "PDF content is sent to Midnight Signal for local text extraction; the raw PDF is not shown in this preview.";
          } else {
            const text = file.content || "";
            preview.textContent = text.slice(0, 4000)
              + (text.length > 4000 ? "\n… preview limited to 4,000 characters" : "");
          }
          details.append(summary, preview);
          content.append(details);
        }
        const actions = document.createElement("div");
        actions.className = "message-actions";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "message-action";
        copy.dataset.messageAction = "copy";
        copy.dataset.messageIndex = String(index);
        copy.textContent = "Copy prompt";
        copy.setAttribute("aria-label", "Copy this prompt");
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "message-action";
        edit.dataset.messageAction = "edit";
        edit.dataset.messageIndex = String(index);
        edit.textContent = "Edit & resend";
        edit.setAttribute("aria-label", "Edit and resend this prompt");
        edit.disabled = streaming || preparingMessage;
        const branch = document.createElement("button");
        branch.type = "button";
        branch.className = "message-action";
        branch.dataset.messageAction = "branch";
        branch.dataset.messageIndex = String(index);
        branch.textContent = "Branch from here";
        branch.setAttribute("aria-label", "Start a new conversation from this prompt");
        branch.disabled = streaming || preparingMessage;
        actions.append(copy, edit, branch);
        content.append(actions);
      }
      row.classList.toggle("message-error", Boolean(message.error));
      if (message.role === "assistant" && message.stepLimit) {
        const note = document.createElement("div");
        note.className = "step-limit-note";
        note.setAttribute("role", "status");
        note.textContent = "The agent reached its tool-step limit. Its completed work is preserved; send a follow-up to continue.";
        content.append(note);
      }
      if (message.role === "assistant" && message.activities?.length) {
        const activities = document.createElement("div");
        activities.className = "agent-activities";
        activities.innerHTML = message.activities.map(renderAgentActivity).join("");
        content.append(activities);
      }
      if (message.role === "assistant" && message.progressNotes?.length) {
        const log = document.createElement("div");
        log.className = "agent-progress-log";
        log.setAttribute("aria-label", "Live user-facing progress updates");
        for (const note of message.progressNotes.slice(-8)) {
          const entry = document.createElement("p");
          entry.className = "agent-progress-note";
          entry.textContent = note;
          log.append(entry);
        }
        content.append(log);
      }
      if (message.role === "assistant" && message.progress) {
        content.append(createProgressIndicator(message.progress));
      }
      if (streaming && message.role === "assistant" && index === messages.length - 1) {
        content.insertAdjacentHTML(
          "beforeend",
          '<span class="typing-indicator" aria-label="Generating"><i></i><i></i><i></i></span>'
        );
      }
      row.append(avatar, content);

      if (message.role === "assistant" && index === messages.length - 1 && !streaming) {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "message-action";
        copy.textContent = "Copy response";
        copy.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(message.content);
            showToast("Copied to clipboard");
          } catch {
            showToast("Clipboard access is unavailable in this browser");
          }
        });
        actions.append(copy);
        const previous = messages[index - 1];
        if (previous?.role === "user") {
          const regenerate = document.createElement("button");
          regenerate.type = "button";
          regenerate.className = "message-action regenerate-response";
          regenerate.textContent = message.error ? "Retry" : "Regenerate";
          regenerate.setAttribute(
            "aria-label",
            message.error ? "Retry this response" : "Regenerate this response"
          );
          actions.append(regenerate);
        }
        if (message.stepLimit && activeChat()?.mode === "agent") {
          const continueButton = document.createElement("button");
          continueButton.type = "button";
          continueButton.className = "message-action continue-agent";
          continueButton.textContent = "Continue task";
          continueButton.setAttribute("aria-label", "Continue the unfinished agent task");
          actions.append(continueButton);
        }
        content.append(actions);
      }
      elements.messages.append(row);
    });

    renderSidebar();
    if (forceBottom || keepAtBottom) scrollToBottom();
  }

  function updateStreamingMessage(message, chatId, changedActivityIndexes = []) {
    if (activeChatId !== chatId) return;
    const keepAtBottom = isNearBottom();
    const rows = elements.messages.querySelectorAll(".message.assistant");
    const row = rows[rows.length - 1];
    const content = row?.querySelector(".message-content");
    const body = content?.querySelector(".message-body");
    if (!content || !body) return;

    row.setAttribute("aria-busy", "true");
    body.classList.add("is-streaming");
    body.textContent = message.content;
    content.querySelector(".project-download-list")?.remove();
    appendGeneratedDownloads(content, message);

    let stepLimitNote = content.querySelector(".step-limit-note");
    if (message.stepLimit && !stepLimitNote) {
      stepLimitNote = document.createElement("div");
      stepLimitNote.className = "step-limit-note";
      stepLimitNote.setAttribute("role", "status");
      stepLimitNote.textContent = "The agent reached its tool-step limit. Its completed work is preserved; send a follow-up to continue.";
      content.append(stepLimitNote);
    }

    let progress = content.querySelector(".agent-progress");
    if (message.progress) {
      if (!progress) {
        progress = createProgressIndicator(message.progress);
        content.append(progress);
      }
      progress.dataset.motion = progressMotionFor(message.progress);
      progress.lastElementChild.textContent = userFacingProgress(message.progress);
    } else {
      progress?.remove();
    }

    let progressLog = content.querySelector(".agent-progress-log");
    if (message.progressNotes?.length) {
      if (!progressLog) {
        progressLog = document.createElement("div");
        progressLog.className = "agent-progress-log";
        progressLog.setAttribute("aria-label", "Agent progress updates");
        content.append(progressLog);
      }
      progressLog.replaceChildren(...message.progressNotes.slice(-8).map((note) => {
        const entry = document.createElement("p");
        entry.className = "agent-progress-note";
        entry.textContent = note;
        return entry;
      }));
    }

    let activities = content.querySelector(".agent-activities");
    if (changedActivityIndexes.length && message.activities?.length) {
      if (!activities) {
        activities = document.createElement("div");
        activities.className = "agent-activities";
        content.append(activities);
      }
      for (const index of [...new Set(changedActivityIndexes)].sort((a, b) => a - b)) {
        if (index < 0 || index >= message.activities.length) continue;
        const wrapper = document.createElement("div");
        wrapper.innerHTML = renderAgentActivity(message.activities[index]);
        const updatedCard = wrapper.firstElementChild;
        const currentCard = activities.children[index];
        if (currentCard) {
          currentCard.replaceWith(updatedCard);
        } else {
          activities.append(updatedCard);
        }
      }
    }
    const typing = content.querySelector(".typing-indicator");
    if (typing) content.append(typing);
    if (keepAtBottom) scrollToBottom();
  }

  function scheduleStreamingRender(message, chatId, activityIndex = null) {
    if (Number.isInteger(activityIndex)) streamActivityIndexes.add(activityIndex);
    if (streamRenderTimer !== null) return;
    streamRenderTimer = setTimeout(() => {
      streamRenderTimer = null;
      const changedActivityIndexes = [...streamActivityIndexes];
      streamActivityIndexes.clear();
      if (streaming) updateStreamingMessage(message, chatId, changedActivityIndexes);
    }, 70);
  }

  function openChat(chatId) {
    if (streaming || preparingMessage) return;
    if (editingMessage) cancelMessageEdit();
    activeChatId = chatId;
    if (matchMedia("(max-width: 760px)").matches) {
      document.body.classList.add("sidebar-collapsed");
    }
    const chat = activeChat();
    if (chat) {
      elements.mode.value = chat.mode;
      if (appStatus.models.includes(chat.model)) {
        elements.model.value = chat.model;
        modelSelectionMade = true;
      }
      elements.thinking.value = chat.think ? "on" : "off";
      elements.permission.value = chat.permission_mode || "manual";
    }
    saveActiveChat();
    updateModeControls();
    updateThinkingControl();
    updatePermissionControl();
    renderMessages(true);
  }

  function newChat() {
    if (streaming || preparingMessage) return;
    if (editingMessage) cancelMessageEdit();
    activeChatId = "";
    saveActiveChat();
    saveChats();
    if (matchMedia("(max-width: 760px)").matches) {
      document.body.classList.add("sidebar-collapsed");
    }
    elements.permission.value = preferences.permission_mode;
    elements.thinking.value = "off";
    updateModeControls();
    renderMessages(true);
    elements.input.focus();
  }

  function exportChat() {
    const chat = activeChat();
    if (!chat || !chat.messages.length) {
      showToast("There is no conversation to export.");
      return;
    }
    const transcript = chat.messages.map((message) => {
      const speaker = message.role === "assistant" ? "Midnight Signal" : "You";
      if (speaker === "You" && message.attachments?.length) {
        const body = message.displayContent || message.content || "";
        const files = message.attachments.map((file) =>
          `- Attached file: ${String(file.name || "attachment").replace(/[\r\n]/g, " ")} (${Math.ceil((file.size || 0) / 1024)} KB)`
        ).join("\n\n");
        return `## ${speaker}\n\n${body}${body ? "\n\n" : ""}${files}`;
      }
      return `## ${speaker}\n\n${message.content || ""}`;
    }).join("\n\n");
    const markdown = [
      `# ${chat.title || "Midnight Signal conversation"}`,
      "",
      `- Mode: ${chat.mode || "default"}`,
      `- Model: ${chat.model || "unknown"}`,
      `- Exported: ${new Date().toLocaleString()}`,
      "",
      transcript,
      "",
    ].join("\n");
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(chat.title || "midnight-signal-chat")
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
      .trim()
      .slice(0, 80) || "midnight-signal-chat"}.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast("Conversation exported as Markdown");
  }

  function updateMessageEditBanner() {
    const status = elements.editMessageBanner.querySelector("span");
    if (!editingMessage) {
      elements.editMessageBanner.hidden = true;
      return;
    }
    const count = editingMessage.attachments.length;
    status.textContent = `Editing an earlier prompt${count ? ` · ${count} attachment${count === 1 ? "" : "s"} will be resent` : ""} · later messages will be replaced on send`;
    elements.editMessageBanner.hidden = false;
  }

  function cancelMessageEdit() {
    if (!editingMessage) return;
    elements.input.value = editingMessage.draftText;
    attachedFiles = [...editingMessage.draftFiles, ...attachedFiles];
    editingMessage = null;
    updateMessageEditBanner();
    renderAttachments();
    resizeInput();
    renderMessages();
  }

  function editUserMessage(index) {
    const chat = activeChat();
    const message = chat?.messages[index];
    if (!chat || message?.role !== "user" || streaming || preparingMessage) return;
    editingMessage = {
      chatId: chat.id,
      messageIndex: index,
      attachments: message.attachments || [],
      originalMessages: chat.messages.slice(index),
      originalTitle: chat.title,
      originalUpdated: chat.updated,
      draftText: elements.input.value,
      draftFiles: attachedFiles.slice(),
    };
    attachedFiles = [];
    elements.input.value = message.content || "";
    updateMessageEditBanner();
    renderAttachments();
    resizeInput();
    elements.input.focus();
  }

  function branchFromMessage(index) {
    const source = activeChat();
    if (!source || streaming || preparingMessage || index < 0 || index >= source.messages.length) return;
    const branch = {
      ...source,
      id: createLocalId(),
      title: `Branch: ${(source.title || "New conversation").slice(0, 70)}`,
      messages: JSON.parse(JSON.stringify(source.messages.slice(0, index + 1))),
      pinned: false,
      archived: false,
      branchFrom: { chatId: source.id, messageIndex: index },
      updated: Date.now(),
    };
    chats.unshift(branch);
    activeChatId = branch.id;
    saveActiveChat();
    saveChats();
    renderMessages(true);
    showToast("Started a new conversation from this prompt");
  }

  async function regenerateLastResponse() {
    const chat = activeChat();
    if (!chat || streaming || chat.messages.length < 2) return;
    const assistant = chat.messages[chat.messages.length - 1];
    const user = chat.messages[chat.messages.length - 2];
    if (assistant.role !== "assistant" || user.role !== "user") return;
    const versions = Array.isArray(assistant.versions)
      ? assistant.versions.filter((version) => version && typeof version.content === "string")
      : [];
    if (!versions.some((version) => version.content === assistant.content)) {
      versions.push({
        content: assistant.content,
        downloads: Array.isArray(assistant.downloads) ? assistant.downloads : [],
      });
    }
    const retainedVersions = versions.slice(-4);
    chat.messages.splice(-2);
    chat.updated = Date.now();
    saveChats();
    renderMessages();
    const sent = await sendMessage(user.content, user.attachments || []);
    const replacement = chat.messages[chat.messages.length - 1];
    if (!sent || replacement?.role !== "assistant") {
      showToast("Could not regenerate this response. The previous version remains in history.");
      return;
    }
    if (replacement.content && !retainedVersions.some((version) => version.content === replacement.content)) {
      retainedVersions.push({
        content: replacement.content,
        downloads: Array.isArray(replacement.downloads) ? replacement.downloads : [],
      });
    }
    replacement.versions = retainedVersions.slice(-5);
    replacement.activeVersion = Math.max(0, replacement.versions.length - 1);
    saveChats();
    renderMessages();
  }

  async function continueAgentTask() {
    const chat = activeChat();
    const lastMessage = chat?.messages[chat.messages.length - 1];
    if (!chat || chat.mode !== "agent" || !lastMessage?.stepLimit || streaming) return;
    await sendMessage(
      "Continue the unfinished task from where you left off. Review the existing workspace, preserve completed work, and continue from the last completed step."
    );
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => elements.toast.classList.remove("visible"), 2400);
  }

  function explainRequestFailure(error) {
    const details = String(error?.message || "Could not reach Midnight Signal");
    if (/failed to fetch|networkerror|load failed|connection (?:reset|refused|closed)|incomplete chunked/i.test(details)) {
      return "The connection to Midnight Signal or Ollama was interrupted. Check that both are running; any partial reply is preserved, and you can retry.";
    }
    if (/does not support.*tool calling|tool calling.*not supported/i.test(details)) {
      return `${details} Select a model with tool-calling support to use Coding agent mode.`;
    }
    if (/model .* not found|model .* does not exist/i.test(details)) {
      return `${details} Confirm the model is installed with Ollama, then select it again.`;
    }
    return details;
  }

  function parseStreamEvent(line) {
    let event;
    try {
      event = JSON.parse(line);
    } catch (error) {
      throw new Error(`Midnight Signal sent an invalid stream event: ${error.message}`);
    }
    if (!event || typeof event !== "object" || Array.isArray(event) || typeof event.type !== "string") {
      throw new Error("Midnight Signal sent a stream event without a valid type.");
    }
    return event;
  }

  function showHelp() {
    showToast("Commands: /help · /new · /clear · /export · /settings · /theme · /mode <name> · /workspace · /stats · Ctrl/⌘ K palette · ? shortcuts");
  }

  function showModelStatus() {
    const model = appStatus.model || elements.model.value || "No model selected";
    const installed = appStatus.models?.length || 0;
    showToast(`${model} · ${installed} installed model${installed === 1 ? "" : "s"} · local Ollama`);
  }

  function toggleSidebar() {
    const collapsed = !document.body.classList.contains("sidebar-collapsed");
    document.body.classList.toggle("sidebar-collapsed", collapsed);
    preferences.sidebar_collapsed = collapsed;
    persistPreferences();
  }

  function runSlashCommand(value) {
    const [command, ...args] = value.trim().split(/\s+/);
    const argument = args.join(" ");
    switch (command.toLowerCase()) {
      case "/help": showHelp(); return true;
      case "/new":
      case "/clear": newChat(); return true;
      case "/export": exportChat(); return true;
      case "/settings": openSettings(); return true;
      case "/theme":
        openSettings("theme");
        if (argument) {
          const themeSelect = elements.settingsForm.elements.namedItem("theme");
          const allowed = [...themeSelect.options].some((option) => option.value === argument);
          if (!allowed) showToast(`Unknown theme: ${argument}`);
          else {
            themeSelect.value = argument;
            preferences.theme = argument;
            persistPreferences();
            applyPreferences();
          }
        }
        return true;
      case "/mode": {
        const mode = (appStatus.modes || []).find((item) => item.toLowerCase() === argument.toLowerCase());
        if (!mode) showToast(argument ? `Unknown mode: ${argument}` : `Modes: ${(appStatus.modes || []).join(", ")}`);
        else {
          elements.mode.value = mode;
          elements.mode.dispatchEvent(new Event("change", { bubbles: true }));
        }
        return true;
      }
      case "/workspace": openWorkspaceBrowser(); return true;
      case "/stats": showModelStatus(); return true;
      case "/search":
        elements.historySearch.value = argument;
        renderSidebar();
        elements.historySearch.focus();
        return true;
      default: return false;
    }
  }

  function setStreaming(value) {
    streaming = value;
    if (!value && streamRenderTimer !== null) {
      clearTimeout(streamRenderTimer);
      streamRenderTimer = null;
      streamActivityIndexes.clear();
    }
    elements.send.classList.toggle("is-streaming", value);
    elements.send.setAttribute("aria-label", value ? "Stop response" : "Send message");
    elements.send.title = value ? "Stop response" : "Send message";
    elements.input.disabled = value;
    $("#new-chat").disabled = value;
    elements.fileInput.disabled = value;
    $("#attach-files").disabled = value;
    updateThinkingControl();
    updatePermissionControl();
    updateModeControls();
    renderMessages();
  }

  function appendMessage(chat, role, content, metadata = {}) {
    chat.messages.push({ role, content, ...metadata });
    chat.updated = Date.now();
    saveChats();
    renderMessages();
  }

  async function generateConversationTitle(chatId, prompt, model) {
    if (!prompt.trim()) return;
    try {
      const response = await fetch("/api/title", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, prompt: prompt.slice(0, 6000) }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `Title generation failed (${response.status})`);
      const chat = chats.find((item) => item.id === chatId);
      const title = typeof payload.title === "string" ? payload.title.trim() : "";
      if (!chat || chat.title !== "New conversation" || !title || title.length > 80) return;
      chat.title = title;
      chat.updated = Date.now();
      saveChats();
      renderSidebar();
    } catch (error) {
      console.warn("Could not generate a conversation title; keeping the default title.", error);
    }
  }

  async function sendMessage(text, replayAttachments = null) {
    let value = text.trim();
    const editContext = editingMessage?.chatId === activeChatId ? editingMessage : null;
    const newlyAttachedFiles = attachedFiles.slice();
    if (replayAttachments === null && value.startsWith("/") && runSlashCommand(value)) {
      elements.input.value = "";
      resizeInput();
      return true;
    }
    if (streaming || preparingMessage
      || (!value && !attachedFiles.length && !replayAttachments?.length
        && !editContext?.attachments.length)) return false;
    if (!value && (attachedFiles.length || editContext?.attachments.length)
      && replayAttachments === null) {
      renderAttachments();
      elements.input.focus();
      showToast("What would you like me to do with the attached file? Add a request before sending.");
      return false;
    }
    preparingMessage = true;
    updateModeControls();
    $("#new-chat").disabled = true;
    $("#attach-files").disabled = true;
    elements.fileInput.disabled = true;
    elements.conversationList.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    const restoreFocus = document.activeElement === elements.send || document.activeElement === elements.input;
    const filesToSend = replayAttachments !== null
      ? replayAttachments
      : [...(editContext?.attachments || []), ...attachedFiles];
    elements.cancelEditMessage.disabled = Boolean(editContext);
    let attachmentMetadata = [];
    if (filesToSend.length) {
      try {
        const totalAttachmentBytes = filesToSend.reduce((sum, file) => sum + file.size, 0);
        if (filesToSend.length > 5 || totalAttachmentBytes > MAX_ATTACHMENT_BYTES) {
          throw new Error("Attachments are limited to 5 files and 100 MiB total.");
        }
        attachmentMetadata = await Promise.all(filesToSend.map(async (file) => {
          if (typeof file.content === "string"
            && (file.encoding === "text" || file.encoding === "base64")) {
            return { name: file.name, size: file.size, content: file.content, encoding: file.encoding };
          }
          return readAttachment(file);
        }));
      } catch (error) {
        preparingMessage = false;
        updateModeControls();
        $("#new-chat").disabled = false;
        $("#attach-files").disabled = false;
        elements.fileInput.disabled = false;
        elements.cancelEditMessage.disabled = false;
        renderSidebar();
        if (restoreFocus) elements.input.focus();
        showToast(error.message || "Could not read the attached file");
        return false;
      }
    }
    if (new TextEncoder().encode(value).length > 500_000) {
      preparingMessage = false;
      updateModeControls();
      $("#new-chat").disabled = false;
      $("#attach-files").disabled = false;
      elements.fileInput.disabled = false;
      elements.cancelEditMessage.disabled = false;
      renderSidebar();
      if (restoreFocus) elements.input.focus();
      showToast("Message exceeds the 500 KB limit");
      return false;
    }
    const displayContent = text.trim();
    if ((replayAttachments === null || editContext)
      && elements.input.value.trim() === displayContent) {
      elements.input.value = "";
      resizeInput();
    }
    attachedFiles = attachedFiles.filter((file) => !filesToSend.includes(file));
    renderAttachments();
    preparingMessage = false;
    $("#new-chat").disabled = false;
    $("#attach-files").disabled = false;
    elements.fileInput.disabled = false;
    elements.cancelEditMessage.disabled = false;
    const chat = ensureChat();
    if (editContext && editContext.chatId === chat.id) {
      chat.messages.splice(editContext.messageIndex);
      editingMessage = null;
      updateMessageEditBanner();
      renderAttachments();
    }
    const websiteBuild = isWebsiteBuildRequest(displayContent);
    chat.mode = elements.mode.value || "default";
    chat.model = elements.model.value || appStatus.model;
    if (
      chat.mode !== "agent"
      && websiteBuild
      && appStatus.modes.includes("agent")
    ) {
      chat.mode = "agent";
      elements.mode.value = "agent";
      if (
        !(appStatus.agent_models || []).includes(chat.model)
        && appStatus.recommended_agent_model
      ) {
        chat.model = appStatus.recommended_agent_model;
        elements.model.value = chat.model;
        modelSelectionMade = false;
        showToast(`Using ${chat.model} so the website can be written to your workspace`);
      } else {
        showToast("Switching to Coding agent to create the website in your workspace");
      }
      updateModeControls();
    }
    chat.think = /^qwen3(?::|$)/i.test(chat.model) && elements.thinking.value === "on";
    chat.permission_mode = elements.permission.value || "manual";
    const agentMode = chat.mode === "agent";
    chat.options = { ...preferences.options, ...(chat.options || {}) };
    appendMessage(chat, "user", displayContent, { attachments: attachmentMetadata });
    const assistant = { role: "assistant", content: "" };
    assistant.websiteBuild = websiteBuild && agentMode;
    chat.messages.push(assistant);
    requestController = new AbortController();
    setStreaming(true);
    assistant.progress = chat.mode === "agent"
      ? "Starting the coding agent"
      : progressStagesForPrompt(displayContent)[0];
    let waitingProgressStage = 0;
    const waitingProgressStages = progressStagesForPrompt(displayContent);
    let waitingProgressTimer = null;
    const stopWaitingProgress = () => {
      if (waitingProgressTimer !== null) {
        clearInterval(waitingProgressTimer);
        waitingProgressTimer = null;
      }
    };
    if (!agentMode) {
      waitingProgressTimer = setInterval(() => {
        waitingProgressStage = (waitingProgressStage + 1) % waitingProgressStages.length;
        assistant.progress = waitingProgressStages[waitingProgressStage];
        scheduleStreamingRender(assistant, chat.id);
      }, 5000);
    }

    try {
      const history = chat.messages.slice(0, -1).filter((message) =>
        message.role === "user" || message.role === "assistant"
      ).slice(-30);
      const latestUserMessage = [...history].reverse().find((message) => message.role === "user");
      const requestMessages = history.map((message) => {
        const requestMessage = {
          role: message.role,
          content: historyMessageContent(message, agentMode),
        };
        if (message === latestUserMessage && message.attachments?.length) {
          requestMessage.attachments = message.attachments.map(({ name, size, content, encoding }) => ({
            name, size, content, encoding,
          }));
        }
        return requestMessage;
      });
      const requestBody = {
        chat_id: chat.id,
        mode: chat.mode,
        model: chat.model,
        messages: requestMessages,
        options: chat.options,
        think: chat.think,
        permission_mode: chat.permission_mode,
      };
      const maxRequestBytes = MAX_ATTACHMENT_BYTES * 2 + 16_000_000;
      while (requestMessages.length > 1 && new TextEncoder().encode(JSON.stringify(requestBody)).length > maxRequestBytes) {
        requestMessages.shift();
      }
      if (new TextEncoder().encode(JSON.stringify(requestBody)).length > maxRequestBytes) {
        throw new Error("This conversation is too large to send. Start a new chat or remove large attachments.");
      }
      const response = await fetch(chat.mode === "agent" ? "/api/agent" : "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: requestController.signal,
        body: JSON.stringify(requestBody),
      });
      if (!response.ok) {
        let problem = {};
        try { problem = await response.json(); } catch { /* use HTTP status below */ }
        throw new Error(problem.error || `Request failed (${response.status})`);
      }
      if (!response.body) throw new Error("This browser cannot stream responses.");
      if (editContext) editContext.committed = true;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      let gotDone = false;
      while (true) {
        const { value: bytes, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(bytes, { stream: true });
        const lines = pending.split("\n");
        pending = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = parseStreamEvent(line);
          stopWaitingProgress();
          if (event.type === "token") {
            if (!assistant.websiteBuild) {
              assistant.progress = "";
              assistant.content += event.text;
              scheduleStreamingRender(assistant, chat.id);
            }
          } else if (event.type === "replace") {
            assistant.progress = "";
            assistant.content = event.text;
            scheduleStreamingRender(assistant, chat.id);
          } else if (event.type === "error") {
            playUiSound("error");
            throw new Error(event.error);
          } else if (event.type === "step_limit" || event.type === "max_steps") {
            assistant.stepLimit = true;
            assistant.content = event.text || event.error
              || "The agent reached its tool-step limit. Send a follow-up to continue.";
            scheduleStreamingRender(assistant, chat.id);
          } else if (event.type === "warning") {
            if (/tool[- ]step limit|step limit|max(?:imum)? steps/i.test(event.text || "")) {
              assistant.stepLimit = true;
              scheduleStreamingRender(assistant, chat.id);
            }
            showToast(event.text);
          } else if (event.type === "status") {
            assistant.progress = event.text;
            scheduleStreamingRender(assistant, chat.id);
          } else if (event.type === "progress_note") {
            assistant.progress = event.text;
            assistant.progressNotes ||= [];
            assistant.progressNotes.push(event.text);
            assistant.progressNotes = assistant.progressNotes.slice(-8);
            scheduleStreamingRender(assistant, chat.id);
          } else if (event.type === "permission_auto_approved") {
            assistant.progress = `Auto-approved ${event.action}: ${event.target}`;
            scheduleStreamingRender(assistant, chat.id);
          } else if (event.type === "tool_call") {
            playUiSound("tool");
            assistant.activities ||= [];
            const args = Object.fromEntries(Object.entries(event.args || {}).map(([key, item]) => [
              key,
              typeof item === "string" && item.length > 1200
                ? `${item.slice(0, 1200)}\n… argument truncated`
                : item,
            ]));
            assistant.activities.push({
              name: event.name,
              args,
              status: "working",
              result: "",
            });
            assistant.progress = progressForTool(event.name);
            scheduleStreamingRender(assistant, chat.id, assistant.activities.length - 1);
          } else if (event.type === "tool_result") {
            const activity = [...(assistant.activities || [])].reverse().find((item) =>
              item.name === event.name && item.status === "working"
            );
            const activityIndex = activity ? assistant.activities.indexOf(activity) : -1;
            if (activity) {
              const result = event.result || "";
              activity.result = result.slice(0, 4000);
              activity.resultTruncated = result.length > 4000;
              if (typeof event.undo_id === "string" && /^[a-f0-9]{32}$/.test(event.undo_id)) {
                activity.undoId = event.undo_id;
                activity.changedPath = typeof event.changed_path === "string" ? event.changed_path : "";
              }
              activity.status = activity.result.startsWith("CANCELLED_BY_USER")
                ? "declined"
                : (activity.result.startsWith("error:") ? "failed" : "complete");
              activity.confirmationState = "";
              activity.confirmation = null;
              assistant.progress = activity.status === "failed"
                ? "Reviewing a tool error"
                : "Reviewing the results";
            }
            scheduleStreamingRender(assistant, chat.id, activityIndex);
          } else if (event.type === "download_ready") {
            if (typeof event.archive_path === "string"
              && typeof event.archive_name === "string"
              && event.archive_path.toLowerCase().endsWith(".zip")) {
              assistant.downloads ||= [];
              assistant.downloads.push({
                name: event.archive_name,
                path: event.archive_path,
                type: "zip",
              });
              scheduleStreamingRender(assistant, chat.id);
            }
          } else if (event.type === "document_ready") {
            if (typeof event.document_path === "string"
              && typeof event.document_name === "string"
              && /\.(?:pdf|docx)$/i.test(event.document_path)) {
              assistant.downloads ||= [];
              assistant.downloads.push({
                name: event.document_name,
                path: event.document_path,
                type: "document",
              });
              scheduleStreamingRender(assistant, chat.id);
            }
          } else if (event.type === "preview_ready") {
            if (typeof event.path === "string" && /\.(?:html?)$/i.test(event.path)) {
              assistant.websitePreview = event.path;
              scheduleStreamingRender(assistant, chat.id);
            }
          } else if (event.type === "website_file_ready") {
            if (typeof event.file_path === "string"
              && /\.(?:html?)$/i.test(event.file_path)
              && typeof event.file_name === "string") {
              assistant.downloads ||= [];
              if (!assistant.downloads.some((item) => item.path === event.file_path)) {
                assistant.downloads.push({
                  name: event.file_name,
                  path: event.file_path,
                  type: "website",
                });
              }
              scheduleStreamingRender(assistant, chat.id);
            }
          } else if (event.type === "confirmation") {
            activeConfirmations.add(event.id);
            assistant.progress = "Waiting for your approval";
            const activityIndex = (assistant.activities || []).length - 1;
            const activity = assistant.activities?.[activityIndex];
            if (activity) {
              const timeoutSeconds = Number(event.timeout_seconds);
              const timeoutAt = Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
                ? Date.now() + timeoutSeconds * 1000
                : 0;
              activity.confirmation = { ...event, expiresAt: timeoutAt || undefined };
              activity.expiresAt = timeoutAt || undefined;
              activity.confirmationState = "needs approval";
            }
            saveChats();
            scheduleStreamingRender(assistant, chat.id, activity ? activityIndex : null);
          } else if (event.type === "confirmation_expired") {
            activeConfirmations.delete(event.id);
            assistant.progress = "Approval timed out";
            const activity = [...(assistant.activities || [])].reverse().find((item) =>
              item.confirmation?.id === event.id
            );
            const activityIndex = activity ? assistant.activities.indexOf(activity) : -1;
            if (activity) {
              activity.confirmationState = "expired";
              activity.confirmation = null;
            }
            saveChats();
            scheduleStreamingRender(assistant, chat.id, activityIndex);
          } else if (event.type === "done") {
            playUiSound("done");
            assistant.progress = "";
            if (assistant.websiteBuild && !assistant.content.trim()) {
              const websiteReady = assistant.downloads?.some((item) => item.type === "website");
              assistant.content = websiteReady
                ? "Your website is ready. Preview it here or open index.html in your workspace."
                : "No verified website file was created. Review the tool results and try again.";
              assistant.error = !websiteReady;
            }
            gotDone = true;
          }
        }
      }
      pending += decoder.decode();
      if (pending.trim()) {
        const event = parseStreamEvent(pending);
        stopWaitingProgress();
        if (event.type === "error") throw new Error(event.error);
        if (event.type === "step_limit" || event.type === "max_steps") {
          assistant.stepLimit = true;
          assistant.content = event.text || event.error
            || "The agent reached its tool-step limit. Send a follow-up to continue.";
          scheduleStreamingRender(assistant, chat.id);
        }
        if (event.type === "token") {
          if (!assistant.websiteBuild) {
            assistant.progress = "";
            assistant.content += event.text;
            scheduleStreamingRender(assistant, chat.id);
          }
        }
        if (event.type === "replace") {
          assistant.progress = "";
          assistant.content = event.text;
          scheduleStreamingRender(assistant, chat.id);
        }
        if (event.type === "done") {
          assistant.progress = "";
          gotDone = true;
        }
      }
      if (!gotDone && !requestController.signal.aborted) {
        throw new Error("The connection ended before the response was complete.");
      }
      if (!assistant.content.trim() && gotDone) {
        assistant.content = "The model completed without returning a text response.";
        assistant.error = true;
      }
    } catch (error) {
      const editRolledBack = Boolean(editContext && !editContext.committed);
      if (editRolledBack) {
        chat.messages.splice(editContext.messageIndex);
        chat.messages.push(...editContext.originalMessages);
        chat.title = editContext.originalTitle;
        chat.updated = editContext.originalUpdated;
        editingMessage = editContext;
        attachedFiles = newlyAttachedFiles;
        elements.input.value = displayContent;
        updateMessageEditBanner();
        renderAttachments();
        resizeInput();
      }
      if (error.name === "AbortError") {
        for (const id of activeConfirmations) resolveConfirmation(id, false);
        activeConfirmations.clear();
        if (!editRolledBack && !assistant.content) chat.messages.pop();
      } else {
        const details = explainRequestFailure(error);
        const stepLimit = /(?:step limit|max(?:imum)? steps|too many steps)/i.test(details);
        assistant.stepLimit = stepLimit;
        const failureNotice = stepLimit
          ? "The coding agent reached its step limit before finishing. Review the progress above, then send a follow-up to continue."
          : `Request failed: ${details}`;
        assistant.content = assistant.content.trim()
          ? `${assistant.content}\n\n${failureNotice}`
          : failureNotice;
        assistant.error = true;
        showToast(stepLimit ? "The coding agent reached its step limit" : details);
      }
    } finally {
      stopWaitingProgress();
      const finalAssistant = elements.messages.querySelector(".message.assistant:last-of-type");
      finalAssistant?.removeAttribute("aria-busy");
      assistant.progress = "";
      requestController = null;
      setStreaming(false);
      saveChats();
      renderMessages();
      if (!assistant.error && assistant.content.trim() && chat.title === "New conversation") {
        void generateConversationTitle(chat.id, displayContent, chat.model);
      }
      if (restoreFocus) elements.input.focus();
    }
    return true;
  }

  async function loadStatus(silent = false) {
    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      const status = await response.json();
      if (!response.ok) throw new Error(status.error || "Ollama is unavailable");
      if (streaming || preparingMessage) return;
      const signature = JSON.stringify([
        status.modes, status.models, status.model, status.agent_models,
        status.recommended_agent_model,
      ]);
      const previousMode = elements.mode.value;
      const previousModel = elements.model.value;
      appStatus = status;
      setWorkspaceDisplay(status.workspace);
      const connectedModel = status.model || status.models?.[0] || "Ollama";
      elements.status.textContent = `Connected · ${connectedModel}`;
      elements.status.title = `${status.models?.length || 0} local model(s) available`;
      $(".local-pill").title = `Connected to local Ollama · ${connectedModel}`;
      elements.status.previousElementSibling?.classList.remove("offline");
      if (signature === statusSignature) {
        updateModeControls();
        return;
      }
      statusSignature = signature;
      elements.mode.replaceChildren(...status.modes.map((mode) => {
        const option = document.createElement("option");
        option.value = mode;
        option.textContent = ({
          agent: "Coding agent",
          coder: "Code",
          default: "General",
        })[mode] || mode[0].toUpperCase() + mode.slice(1);
        return option;
      }));
      elements.model.replaceChildren(...status.models.map((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = status.agent_models?.includes(name)
          ? `${name} · agent tools` : `${name} · chat only`;
        return option;
      }));
      const modeChoice = status.modes.includes(previousMode)
        ? previousMode
        : (status.modes.includes("agent") ? "agent" : (status.modes.includes("default") ? "default" : status.modes[0]));
      elements.mode.value = modeChoice;
      if (!status.models.length) {
        elements.status.textContent = "No Ollama models installed";
        $(".local-pill").title = "Ollama is running, but no models are installed.";
        elements.model.append(new Option("No models installed", ""));
        elements.send.disabled = true;
        if (!silent) showToast("Ollama is ready, but no models are installed. Pull a model with `ollama pull <model>`.");
      } else {
        const preferredModel = modeChoice === "agent"
          ? (status.recommended_agent_model || status.model)
          : status.model;
        elements.model.value = status.models.includes(previousModel) && modelSelectionMade
          ? previousModel
          : preferredModel;
      }
      const chat = activeChat();
      if (chat) {
        if (status.modes.includes(chat.mode)) elements.mode.value = chat.mode;
        if (status.models.includes(chat.model)) elements.model.value = chat.model;
        elements.thinking.value = chat.think ? "on" : "off";
        elements.permission.value = chat.permission_mode || "manual";
      }
      updateModeControls();
    } catch (error) {
      if (streaming || preparingMessage) return;
      elements.status.textContent = "Ollama is unavailable";
      elements.status.title = error.message || "Could not connect to Ollama";
      $(".local-pill").title = "Ollama is unavailable. Check that the local Ollama service is running.";
      elements.status.previousElementSibling?.classList.add("offline");
      elements.send.disabled = true;
      if (!silent) showToast(error.message || "Could not connect to Ollama");
    }
  }

  function resizeInput() {
    elements.input.style.height = "auto";
    elements.input.style.height = `${Math.min(elements.input.scrollHeight, 190)}px`;
  }

  function renderAttachments() {
    elements.attachments.replaceChildren();
    elements.attachments.hidden = attachedFiles.length === 0;
    const hasAttachments = attachedFiles.length > 0 || (editingMessage?.attachments.length || 0) > 0;
    const needsPrompt = hasAttachments && !elements.input.value.trim();
    elements.attachmentPrompt.hidden = !needsPrompt;
    elements.attachmentPrompt.textContent = needsPrompt
      ? "What would you like me to do with these files? Add a request, such as summarize, extract key points, or answer a question."
      : "";
    attachedFiles.forEach((file, index) => {
      const chip = document.createElement("span");
      chip.className = "attachment-chip";
      const size = file.size >= 1024 * 1024
        ? `${(file.size / (1024 * 1024)).toFixed(1)} MiB`
        : `${Math.ceil(file.size / 1024)} KB`;
      const name = document.createElement("span");
      name.className = "attachment-name";
      name.textContent = file.name;
      const fileSize = document.createElement("span");
      fileSize.textContent = size;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "attachment-remove";
      remove.setAttribute("aria-label", `Remove ${file.name}`);
      remove.title = `Remove ${file.name}`;
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        attachedFiles.splice(index, 1);
        renderAttachments();
      });
      chip.append(name, fileSize, remove);
      chip.title = file.name;
      elements.attachments.append(chip);
      const previewDetails = document.createElement("details");
      previewDetails.className = "attachment-preview";
      const previewSummary = document.createElement("summary");
      previewSummary.textContent = "Preview";
      const preview = document.createElement("pre");
      preview.textContent = "Open to preview the beginning of this file.";
      previewDetails.append(previewSummary, preview);
      previewDetails.addEventListener("toggle", async () => {
        if (!previewDetails.open || previewDetails.dataset.loaded) return;
        previewDetails.dataset.loaded = "true";
        if (file.encoding === "base64" || file.name.toLowerCase().endsWith(".pdf")) {
          preview.textContent = "PDF text is extracted locally when you send your request. Raw PDF data is not displayed.";
          return;
        }
        try {
          const text = typeof file.content === "string"
            ? file.content
            : await file.slice(0, 4096).text();
          preview.textContent = text.slice(0, 2000)
            + (text.length > 2000 || file.size > 4096 ? "\n… preview limited to the first 2,000 characters" : "");
          if (!text.trim()) preview.textContent = "This file is empty.";
        } catch (error) {
          console.error(`Could not preview attachment ${file.name}:`, error);
          preview.textContent = "Could not preview this file. It will still be attached if the request is sent.";
        }
      });
      elements.attachments.append(previewDetails);
    });
  }

  function addAttachments(files) {
    const incoming = [...files];
    const unsupported = incoming.find((file) => {
      const extension = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || "";
      return extension !== ".pdf" && !file.type.startsWith("text/")
        && !TEXT_ATTACHMENT_EXTENSIONS.has(extension);
    });
    if (unsupported) {
      showToast(`Unsupported file type: ${unsupported.name}. Attach a PDF or text/code file.`);
      return false;
    }
    const totalFiles = attachedFiles.length + incoming.length;
    const totalBytes = [...attachedFiles, ...incoming].reduce((sum, file) => sum + file.size, 0);
    if (totalFiles > 5 || totalBytes > MAX_ATTACHMENT_BYTES) {
      const sizeMiB = (Math.ceil(totalBytes / (1024 * 1024) * 100) / 100).toFixed(2);
      const exactSize = new Intl.NumberFormat().format(totalBytes);
      showToast(`Limit: 5 files and 100 MiB total. Selection: ${totalFiles} ${totalFiles === 1 ? "file" : "files"}, ${exactSize} bytes (${sizeMiB} MiB).`);
      return false;
    }
    attachedFiles = [...attachedFiles, ...incoming];
    renderAttachments();
    return true;
  }

  function updateApprovalCountdowns() {
    let expiredAny = false;
    for (const chat of chats) {
      for (const message of chat.messages) {
        for (const activity of message.activities || []) {
          const confirmation = activity.confirmation;
          const expiresAt = Number(activity.expiresAt || confirmation?.expiresAt) || 0;
          if (!confirmation || !expiresAt) continue;
          const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
          document.querySelectorAll(".approval-countdown").forEach((countdown) => {
            if (countdown.dataset.confirmId !== confirmation.id) return;
            countdown.textContent = remaining
              ? `Approval expires in ${remaining}s`
              : "Approval expired";
            countdown.classList.toggle("expired", remaining === 0);
          });
          if (remaining === 0) {
            activeConfirmations.delete(confirmation.id);
            activity.confirmation = null;
            activity.expiresAt = 0;
            activity.confirmationState = "expired";
            message.progress = "Approval timed out";
            expiredAny = true;
          }
        }
      }
    }
    if (expiredAny) {
      saveChats();
      renderMessages();
    }
  }

  async function resolveConfirmation(id, approved) {
    if (!activeConfirmations.has(id)) return;
    try {
      const response = await fetch("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, approved }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not send approval");
      activeConfirmations.delete(id);
      let owner = null;
      let ownerMessage = null;
      const activity = chats.flatMap((chat) => chat.messages.map((message) => ({ chat, message })))
        .find(({ message }) => (message.activities || []).some((item) => item.confirmation?.id === id));
      if (activity) {
        owner = activity.chat;
        ownerMessage = activity.message;
      }
      const confirmationActivity = ownerMessage?.activities?.find((item) => item.confirmation?.id === id);
      if (confirmationActivity) {
        confirmationActivity.confirmationState = approved ? "approved" : "declined";
        confirmationActivity.confirmation = null;
        confirmationActivity.expiresAt = 0;
        saveChats();
      }
      if (streaming && owner?.id === activeChatId) {
        scheduleStreamingRender(ownerMessage, owner.id);
      } else {
        renderMessages();
      }
      if (!approved) showToast("Action declined; no change was made");
    } catch (error) {
      showToast(error.message || "Could not send approval");
    }
  }

  elements.send.addEventListener("click", () => {
    if (streaming) {
      requestController?.abort();
      return;
    }
    const value = elements.input.value;
    if (!value.trim() && !attachedFiles.length) {
      elements.input.focus();
      return;
    }
    sendMessage(value);
  });
  elements.input.addEventListener("input", () => {
    resizeInput();
    if (attachedFiles.length) renderAttachments();
  });
  elements.input.addEventListener("keydown", (event) => {
    if (event.key === "/" && !elements.input.value && !streaming) {
      event.preventDefault();
      openPalette("/");
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.send.click();
    }
  });
  $("#new-chat").addEventListener("click", newChat);
  elements.exportChat.addEventListener("click", exportChat);
  elements.settingsButton.addEventListener("click", openSettings);
  elements.mobileAccessButton.addEventListener("click", openPhoneAccess);
  $("#close-mobile-access").addEventListener("click", closePhoneAccess);
  elements.mobileAccessBackdrop.addEventListener("click", (event) => {
    if (event.target === elements.mobileAccessBackdrop) closePhoneAccess();
  });
  elements.mobileAccessStart.addEventListener("click", startPhoneAccess);
  elements.mobileAccessStop.addEventListener("click", stopPhoneAccess);
  $("#close-settings").addEventListener("click", closeSettings);
  elements.settingsBackdrop.addEventListener("click", (event) => {
    if (event.target === elements.settingsBackdrop) closeSettings();
  });
  elements.settingsForm.addEventListener("submit", saveSettingsFromForm);
  elements.copyMcpConfigPath.addEventListener("click", async () => {
    const path = elements.mcpConfigPath.textContent.trim();
    if (!path || path === "Loading configuration path…") return;
    try {
      await navigator.clipboard.writeText(path);
      showToast("MCP configuration path copied");
    } catch (error) {
      console.error("Could not copy the MCP configuration path:", error);
      showToast("Could not copy the path. Select and copy it manually.");
    }
  });
  elements.settingsForm.elements.namedItem("theme").addEventListener("input", (event) => {
    document.body.dataset.theme = event.target.value === "auto"
      ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : event.target.value;
  });
  elements.settingsForm.elements.namedItem("volume").addEventListener("input", (event) => {
    elements.soundVolume.value = `${event.target.value}%`;
  });
  $("#reset-settings").addEventListener("click", () => {
    preferences = { ...DEFAULT_PREFERENCES, options: { ...DEFAULT_OPTIONS } };
    if (activeChat()) {
      activeChat().options = { ...DEFAULT_OPTIONS };
      activeChat().permission_mode = "manual";
      elements.permission.value = "manual";
      saveChats();
    }
    persistPreferences();
    applyPreferences();
    openSettings();
    updateModeControls();
  });
  $("#export-history").addEventListener("click", () => {
    if (!chats.length) {
      showToast("There are no conversations to export.");
      return;
    }
    const transcript = chats.map((chat) => [
      `# ${chat.title || "Midnight Signal conversation"}`,
      "",
      `- Mode: ${chat.mode || "default"}`,
      `- Model: ${chat.model || "unknown"}`,
      "",
      ...chat.messages.map((message) => {
        const attachments = (message.attachments || []).map((file) =>
          `- Attached file: ${String(file.name || "attachment").replace(/[\r\n]/g, " ")} (${Math.ceil((file.size || 0) / 1024)} KB)`
        );
        return [
          `## ${message.role === "assistant" ? "Midnight Signal" : "You"}`,
          "",
          message.displayContent || message.content || "",
          ...attachments,
        ].join("\n");
      }),
    ].join("\n")).join("\n\n---\n\n");
    const url = URL.createObjectURL(new Blob([transcript], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "midnight-signal-conversations.md";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast(`Exported ${chats.length} conversations`);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.workspaceBrowserBackdrop.hidden) {
      closeWorkspaceBrowser();
      return;
    }
    if (event.key === "Escape" && !elements.mobileAccessBackdrop.hidden) {
      closePhoneAccess();
      return;
    }
    if (event.key === "Escape" && !elements.settingsBackdrop.hidden) {
      closeSettings();
      return;
    }
    if (event.key === "Tab") {
      const dialog = [...document.querySelectorAll('[role="dialog"][aria-modal="true"]')]
        .find((element) => element.getClientRects().length > 0);
      if (dialog) {
        const focusable = [...dialog.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])'
        )].filter((element) => !element.hidden && element.getClientRects().length > 0);
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (first && last) {
          if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
            event.preventDefault();
            first.focus();
          }
        }
      }
    }
    if (event.key === "?" && !/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) {
      showToast("Shortcuts: Ctrl/⌘ K command palette · Enter send · Shift+Enter newline · Esc close/stop · ? help");
    }
  });
  elements.historySearch.addEventListener("input", () => {
    elements.conversationList.scrollTop = 0;
    renderSidebar();
  });
  elements.historyFilter.addEventListener("change", () => {
    elements.conversationList.scrollTop = 0;
    renderSidebar();
  });
  elements.conversationList.addEventListener("scroll", () => {
    if (chats.length <= 100 || sidebarRenderScheduled) return;
    sidebarRenderScheduled = true;
    requestAnimationFrame(() => {
      sidebarRenderScheduled = false;
      renderSidebar();
    });
  });
  $("#collapse-sidebar").addEventListener("click", () => {
    toggleSidebar();
  });
  $("#show-sidebar").addEventListener("click", () => {
    document.body.classList.remove("sidebar-collapsed");
    if (!matchMedia("(max-width: 760px)").matches) {
      preferences.sidebar_collapsed = false;
      persistPreferences();
    }
  });
  elements.mainPanel.addEventListener("click", (event) => {
    if (event.target.closest("#show-sidebar")) return;
    if (matchMedia("(max-width: 760px)").matches) {
      document.body.classList.add("sidebar-collapsed");
    }
  });
  elements.sidebar.querySelector(".sidebar-collapse").addEventListener("click", () => {
    if (matchMedia("(max-width: 760px)").matches) document.body.classList.add("sidebar-collapsed");
    else {
      preferences.sidebar_collapsed = true;
      persistPreferences();
    }
  });
  elements.emptyState.addEventListener("click", (event) => {
    const button = event.target.closest("[data-studio-prompt]");
    if (!button) return;
    elements.input.value = button.dataset.studioPrompt;
    resizeInput();
    elements.input.focus();
  });
  elements.messages.addEventListener("click", async (event) => {
    const messageAction = event.target.closest("[data-message-action]");
    if (messageAction) {
      const index = Number(messageAction.dataset.messageIndex);
      const chat = activeChat();
      const message = chat?.messages[index];
      if (messageAction.dataset.messageAction === "edit") {
        editUserMessage(index);
      } else if (messageAction.dataset.messageAction === "branch") {
        branchFromMessage(index);
      } else if (messageAction.dataset.messageAction === "copy" && message?.role === "user") {
        const text = message.content || (message.attachments || [])
          .map((file) => `Attached file: ${file.name}`).join("\n");
        try {
          await navigator.clipboard.writeText(text);
          showToast("Prompt copied to clipboard");
        } catch {
          showToast("Clipboard access is unavailable in this browser");
        }
      }
      return;
    }
    if (event.target.closest(".regenerate-response")) {
      await regenerateLastResponse();
      return;
    }
    const versionButton = event.target.closest(".response-version");
    if (versionButton) {
      const chat = activeChat();
      const message = chat?.messages[Number(versionButton.dataset.messageIndex)];
      if (!message) return;
      const current = Number(message.activeVersion) || 0;
      const next = (current + Number(versionButton.dataset.direction) + message.versions.length)
        % message.versions.length;
      const version = message.versions[next];
      if (!version || typeof version.content !== "string") {
        showToast("That response version is unavailable.");
        return;
      }
      message.activeVersion = next;
      message.content = version.content;
      message.downloads = Array.isArray(version.downloads) ? version.downloads : [];
      saveChats();
      renderMessages();
      return;
    }
    if (event.target.closest(".continue-agent")) {
      await continueAgentTask();
      return;
    }
    const undoButton = event.target.closest(".undo-agent-change");
    if (undoButton) {
      undoButton.disabled = true;
      try {
        const response = await fetch("/api/undo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          cache: "no-store",
          body: JSON.stringify({ id: undoButton.dataset.undoId }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Undo failed (${response.status})`);
        const activity = activeChat()?.messages
          .flatMap((message) => message.activities || [])
          .find((item) => item.undoId === undoButton.dataset.undoId);
        if (activity) {
          activity.undone = true;
          activity.status = "undone";
        }
        saveChats();
        renderMessages();
        showToast(`Undid change to ${result.undone}`);
      } catch (error) {
        console.error("Could not undo agent change:", error);
        showToast(error.message || "Could not undo this change");
        undoButton.disabled = false;
      }
      return;
    }
    const approvalButton = event.target.closest(".tool-approve, .tool-deny");
    if (approvalButton) {
      await resolveConfirmation(
        approvalButton.dataset.confirmId,
        approvalButton.classList.contains("tool-approve")
      );
      return;
    }
    const button = event.target.closest(".copy-code");
    if (!button) return;
    const code = button.closest(".code-wrap")?.querySelector("code")?.textContent || "";
    const copyLabel = button.getAttribute("aria-label") || "Copy code";
    try {
      await navigator.clipboard.writeText(code);
      button.textContent = "Copied";
      button.setAttribute("aria-label", "Copied to clipboard");
      setTimeout(() => {
        button.textContent = "Copy";
        button.setAttribute("aria-label", copyLabel);
      }, 1300);
    } catch {
      showToast("Clipboard access is unavailable in this browser");
    }
  });
  elements.cancelEditMessage.addEventListener("click", cancelMessageEdit);
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (elements.paletteBackdrop.hidden) openPalette();
      else closePalette();
      return;
    }
    if (event.key === "Escape" && !elements.paletteBackdrop.hidden) {
      closePalette();
      return;
    }
    if (event.key === "Escape" && streaming) {
      requestController?.abort();
    } else if (event.key === "Escape" && matchMedia("(max-width: 760px)").matches) {
      document.body.classList.add("sidebar-collapsed");
    }
  });
  elements.mode.addEventListener("change", () => {
    if (streaming || preparingMessage) return;
    const agentModels = appStatus.agent_models || [];
    if (elements.mode.value === "agent"
      && !agentModels.includes(elements.model.value)
      && appStatus.recommended_agent_model) {
      elements.model.value = appStatus.recommended_agent_model;
      modelSelectionMade = false;
      showToast(`Using ${appStatus.recommended_agent_model} for agent tools`);
    }
    updateModeControls();
    const chat = activeChat();
    if (chat) {
      chat.mode = elements.mode.value;
      chat.model = elements.model.value;
      chat.permission_mode = elements.permission.value || "manual";
      saveChats();
    }
  });
  elements.model.addEventListener("change", () => {
    if (streaming || preparingMessage) return;
    modelSelectionMade = true;
    updateModeControls();
    const chat = activeChat();
    if (chat) {
      chat.model = elements.model.value;
      saveChats();
    }
  });
  elements.thinking.addEventListener("change", () => {
    if (streaming || preparingMessage) return;
    const chat = activeChat();
    if (chat) {
      chat.think = elements.thinking.value === "on";
      saveChats();
    }
    updateModeControls();
  });
  elements.permission.addEventListener("change", () => {
    if (streaming || preparingMessage) return;
    if (elements.permission.value === "allow_all"
      && !window.confirm(
        "Allow all agent file edits and shell commands in this chat without asking each time? " +
        "This can make unwanted changes. Workspace path restrictions and blocked dangerous command patterns still apply."
      )) {
      elements.permission.value = "manual";
    }
    const chat = activeChat();
    if (chat) {
      chat.permission_mode = elements.permission.value;
      saveChats();
    }
    updateModeControls();
  });
  $("#attach-files").addEventListener("click", () => elements.fileInput.click());
  elements.templateToggle.addEventListener("click", () => {
    const opening = elements.promptTemplates.hidden;
    elements.promptTemplates.hidden = !opening;
    elements.templateToggle.setAttribute("aria-expanded", String(opening));
  });
  elements.promptTemplates.addEventListener("click", (event) => {
    const template = event.target.closest("[data-template]");
    if (!template) return;
    elements.input.value = template.dataset.template.replace(/\\n/g, "\n");
    resizeInput();
    elements.promptTemplates.hidden = true;
    elements.templateToggle.setAttribute("aria-expanded", "false");
    elements.input.focus();
    showToast("Template added to your draft");
  });
  elements.fileInput.addEventListener("change", () => {
    addAttachments(elements.fileInput.files);
    elements.fileInput.value = "";
  });
  const composer = $(".composer");
  composer.addEventListener("dragenter", (event) => {
    if (!event.dataTransfer?.types.includes("Files")) return;
    event.preventDefault();
    composer.classList.add("drag-over");
  });
  composer.addEventListener("dragover", (event) => {
    if (event.dataTransfer?.types.includes("Files")) event.preventDefault();
  });
  composer.addEventListener("dragleave", (event) => {
    if (!composer.contains(event.relatedTarget)) composer.classList.remove("drag-over");
  });
  composer.addEventListener("drop", (event) => {
    if (!event.dataTransfer?.files.length) return;
    event.preventDefault();
    composer.classList.remove("drag-over");
    addAttachments(event.dataTransfer.files);
  });
  elements.paletteSearch.addEventListener("input", () => {
    paletteIndex = 0;
    renderPalette();
  });
  elements.paletteSearch.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      movePaletteSelection(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      movePaletteSelection(-1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      elements.paletteList.querySelector(".palette-item.active")?.click();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closePalette();
    }
  });
  elements.paletteBackdrop.addEventListener("click", (event) => {
    if (event.target === elements.paletteBackdrop) closePalette();
  });
  async function copyWorkspacePath() {
    try {
      if (!appStatus.workspace) {
        showToast("Workspace path unavailable");
        return;
      }
      await navigator.clipboard.writeText(appStatus.workspace);
      showToast("Workspace path copied");
    } catch {
      showToast(appStatus.workspace || "Workspace path unavailable");
    }
  }

  async function loadWorkspaceDirectory(path = "") {
    workspaceRelativePath = path;
    elements.workspaceBrowserPath.replaceChildren();
    elements.workspaceFileList.textContent = "Loading workspace…";
    elements.workspaceFilePreview.hidden = true;
    const parts = path.split("/").filter(Boolean);
    const root = document.createElement("button");
    root.type = "button";
    root.textContent = elements.workspaceName.textContent || "Workspace";
    root.addEventListener("click", () => loadWorkspaceDirectory(""));
    elements.workspaceBrowserPath.append(root);
    let current = "";
    parts.forEach((part, index) => {
      const separator = document.createElement("span");
      separator.textContent = "/";
      separator.setAttribute("aria-hidden", "true");
      elements.workspaceBrowserPath.append(separator);
      current = current ? `${current}/${part}` : part;
      const crumb = document.createElement("button");
      crumb.type = "button";
      crumb.textContent = part;
      const target = current;
      crumb.setAttribute("aria-current", String(index === parts.length - 1));
      crumb.addEventListener("click", () => loadWorkspaceDirectory(target));
      elements.workspaceBrowserPath.append(crumb);
    });
    try {
      const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `Could not list files (${response.status})`);
      elements.workspaceFileList.replaceChildren();
      if (!payload.entries?.length) {
        const empty = document.createElement("div");
        empty.className = "workspace-file-empty";
        empty.textContent = "This folder is empty.";
        elements.workspaceFileList.append(empty);
      }
      for (const entry of payload.entries || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "workspace-file-row";
        button.setAttribute("aria-label", `${entry.type === "directory" ? "Open folder" : "Preview file"} ${entry.name}`);
        const icon = document.createElement("span");
        icon.className = "file-kind";
        icon.textContent = entry.type === "directory" ? "▰" : (entry.name.toLowerCase().endsWith(".zip") ? "⇩" : "·");
        const name = document.createElement("span");
        name.className = "file-label";
        name.textContent = entry.name;
        button.append(icon, name);
        if (entry.type === "file" && Number.isFinite(entry.size)) {
          const size = document.createElement("span");
          size.className = "file-size";
          size.textContent = entry.size >= 1024 * 1024
            ? `${(entry.size / (1024 * 1024)).toFixed(1)} MiB`
            : `${Math.ceil(entry.size / 1024)} KB`;
          button.append(size);
        }
        button.addEventListener("click", () => {
          if (entry.type === "directory") loadWorkspaceDirectory(entry.path);
          else previewWorkspaceFile(entry);
        });
        elements.workspaceFileList.append(button);
      }
      if (payload.truncated) {
        const note = document.createElement("div");
        note.className = "workspace-file-empty";
        note.textContent = "Showing the first 300 items in this folder.";
        elements.workspaceFileList.append(note);
      }
    } catch (error) {
      console.error("Could not browse workspace files:", error);
      elements.workspaceFileList.textContent = error.message || "Could not load this folder.";
    }
  }

  async function previewWorkspaceFile(entry) {
    elements.workspaceFilePreview.hidden = false;
    elements.workspaceFilePreview.textContent = "Loading preview…";
    const title = document.createElement("div");
    title.className = "workspace-preview-title";
    const label = document.createElement("span");
    label.textContent = entry.path;
    const download = document.createElement("a");
    download.href = `/api/file-download?path=${encodeURIComponent(entry.path)}`;
    download.download = entry.name;
    download.textContent = "Download";
    title.append(label, download);
    try {
      const response = await fetch(`/api/file-preview?path=${encodeURIComponent(entry.path)}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      const payload = await response.json();
      const preview = document.createElement("pre");
      preview.textContent = response.ok
        ? (payload.content || "(empty file)")
        : (payload.error || `Preview unavailable (${response.status})`);
      elements.workspaceFilePreview.replaceChildren(title, preview);
    } catch (error) {
      console.error("Could not preview workspace file:", error);
      const preview = document.createElement("pre");
      preview.textContent = error.message || "Preview unavailable.";
      elements.workspaceFilePreview.replaceChildren(title, preview);
    }
  }

  async function reviewWorkspaceChanges() {
    elements.workspaceFilePreview.hidden = false;
    elements.workspaceFilePreview.textContent = "Reviewing Git changes…";
    try {
      const response = await fetch("/api/git-review", {
        cache: "no-store",
        credentials: "same-origin",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Git review failed (${response.status})`);
      const title = document.createElement("div");
      title.className = "workspace-preview-title";
      title.textContent = "Working tree review · read-only";
      const preview = document.createElement("pre");
      preview.textContent = [
        "GIT STATUS",
        result.status || "(no status output)",
        "",
        "TRACKED-FILE DIFF",
        result.diff || "(no tracked-file diff; untracked files are listed in status and can be inspected from the file list)",
      ].join("\n");
      elements.workspaceFilePreview.replaceChildren(title, preview);
    } catch (error) {
      console.error("Could not review workspace changes:", error);
      elements.workspaceFilePreview.textContent = error.message || "Could not review workspace changes.";
    }
  }

  function openWorkspaceBrowser() {
    elements.workspaceBrowserBackdrop.hidden = false;
    loadWorkspaceDirectory("");
    $("#close-workspace-browser").focus();
  }

  function closeWorkspaceBrowser() {
    elements.workspaceBrowserBackdrop.hidden = true;
    elements.workspaceBrowserButton.focus();
  }

  async function chooseWorkspace() {
    if (streaming || preparingMessage) {
      showToast("Wait for the current message to finish before changing workspaces.");
      return;
    }
    let selected;
    try {
      selected = window.prompt(
        "Enter an absolute path to a local workspace folder:",
        appStatus.workspace || ""
      );
    } catch {
      showToast("This browser cannot open a folder-path prompt.");
      return;
    }
    if (selected === null) return;
    const path = selected.trim();
    const isAbsoluteLocalPath = /^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+|\/)/.test(path);
    if (!path || !isAbsoluteLocalPath || path.length > 4096 || /[\u0000-\u001f]/.test(path)) {
      showToast("Enter a valid absolute local folder path.");
      return;
    }
    elements.workspace.disabled = true;
    try {
      const response = await fetch("/api/workspace", {
        method: "POST",
        mode: "same-origin",
        credentials: "same-origin",
        redirect: "error",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      let result = {};
      try { result = await response.json(); } catch { /* the status endpoint is authoritative */ }
      if (!response.ok) throw new Error(result.error || `Workspace update failed (${response.status})`);
      if (typeof result.workspace === "string") setWorkspaceDisplay(result.workspace);
      await loadStatus(true);
      showToast(`Workspace set to ${appStatus.workspace || path}`);
    } catch (error) {
      showToast(error.message || "Could not change the workspace");
    } finally {
      elements.workspace.disabled = false;
    }
  }

  elements.workspace.addEventListener("click", (event) => {
    if (event.shiftKey) {
      copyWorkspacePath();
      return;
    }
    chooseWorkspace();
  });
  elements.workspace.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    copyWorkspacePath();
  });
  elements.workspaceBrowserButton.addEventListener("click", openWorkspaceBrowser);
  $("#close-workspace-browser").addEventListener("click", closeWorkspaceBrowser);
  elements.workspaceBrowserBackdrop.addEventListener("click", (event) => {
    if (event.target === elements.workspaceBrowserBackdrop) closeWorkspaceBrowser();
  });
  $("#change-workspace").addEventListener("click", async () => {
    closeWorkspaceBrowser();
    await chooseWorkspace();
  });
  $("#review-workspace-changes").addEventListener("click", reviewWorkspaceChanges);

  applyPreferences();
  renderMessages();
  restoreIndexedDBHistory();
  loadStatus();
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    if (preferences.theme === "auto") applyPreferences();
  });
  setInterval(updateApprovalCountdowns, 1000);
  setInterval(() => {
    if (!streaming) loadStatus(true);
  }, 30_000);
})();
