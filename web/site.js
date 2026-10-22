"use strict";

const feedbackForm = document.querySelector("#feedback-form");
let feedbackObjectUrl = "";

window.addEventListener("pagehide", () => {
  if (feedbackObjectUrl) URL.revokeObjectURL(feedbackObjectUrl);
});

feedbackForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!feedbackForm.reportValidity()) return;
  const fields = new FormData(feedbackForm);
  const note = [
    "# Midnight Signal feedback",
    "",
    `Category: ${fields.get("category")}`,
    `Subject: ${String(fields.get("subject")).trim()}`,
    "",
    String(fields.get("details")).trim(),
    "",
  ].join("\n");
  const status = document.querySelector("#feedback-note");
  if (feedbackObjectUrl) URL.revokeObjectURL(feedbackObjectUrl);
  try {
    const blob = new Blob([note], { type: "text/plain;charset=utf-8" });
    feedbackObjectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = feedbackObjectUrl;
    link.download = "midnight-signal-feedback.txt";
    link.className = "feedback-download-link";
    link.textContent = "Download feedback note";
    status.textContent = "Your note is ready. Review it before sharing; no message was sent. ";
    status.append(link);
  } catch (error) {
    console.error("Could not prepare the local feedback note:", error);
    status.textContent =
      "Could not prepare the feedback note. Copy your message before leaving this page.";
  }
});
