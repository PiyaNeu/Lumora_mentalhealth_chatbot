// Lumora chat page. All message text is inserted with textContent (never innerHTML).
(function () {
  const shell = document.getElementById("chat-shell");
  const chatEl = document.getElementById("main-chat");
  const form = document.getElementById("message-form");
  const input = document.getElementById("textInput");
  const warning = document.getElementById("input-warning");
  const authed = shell.dataset.authed === "true";
  let sessionId = shell.dataset.sessionId || null;
  let sending = false;

  function timeNow() {
    const d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  function scrollDown() {
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function appendMessage(side, text, opts) {
    opts = opts || {};
    const row = el("div", "chat " + side + "-msg" + (opts.sos ? " sos-msg" : ""));
    const img = el("img", "chat-image");
    img.src = side === "left" ? shell.dataset.botImg : shell.dataset.userImg;
    img.alt = "";
    const bubble = el("div", "chat-bubble");
    const info = el("div", "chat-info");
    info.appendChild(el("span", "chat-info-name", side === "left" ? "LUMORA" : "You"));
    info.appendChild(el("span", "chat-info-time", timeNow()));
    bubble.appendChild(info);
    bubble.appendChild(el("div", "chat-text", text));
    if (opts.sos) {
      const a = el("a", "btn btn-danger btn-sm mt-2", "Open SOS helplines");
      a.href = shell.dataset.sosUrl;
      bubble.appendChild(a);
    }
    if (side === "left" && opts.messageId) {
      bubble.appendChild(saveButton(opts.messageId));
    }
    row.appendChild(img);
    row.appendChild(bubble);
    chatEl.appendChild(row);
    scrollDown();
    return row;
  }

  function saveButton(messageId) {
    const b = el("button", "btn btn-link btn-sm p-0 mt-1 save-insight");
    b.type = "button";
    b.dataset.messageId = messageId;
    b.appendChild(el("i", "bi bi-bookmark"));
    b.appendChild(document.createTextNode(" Save"));
    return b;
  }

  function showWarning(text) {
    warning.textContent = text;
    warning.classList.remove("d-none");
  }

  // --- Send messages (queued so nothing typed while waiting is dropped) ---
  const queue = [];

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) {
      showWarning("Please type a message before sending.");
      return;
    }
    warning.classList.add("d-none");
    appendMessage("right", text);
    input.value = "";
    input.focus();
    queue.push(text);
    if (!sending) drainQueue();
  });

  async function drainQueue() {
    sending = true;
    while (queue.length) {
      await sendOne(queue.shift());
    }
    sending = false;
  }

  async function sendOne(text) {
    const typing = appendMessage("left", "…");
    try {
      const resp = await fetch("/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await resp.json();
      typing.remove();
      if (!resp.ok) {
        showWarning(data.error || "Something went wrong. Please try again.");
        return;
      }
      appendMessage("left", data.reply, { sos: data.sos, messageId: data.message_id });
      if (authed && data.session_id && String(data.session_id) !== String(sessionId)) {
        sessionId = data.session_id;
        // Keep the URL on this session so a refresh reloads it
        history.replaceState(null, "", "/chat?s=" + sessionId);
        addSessionToList(data.session_id, data.session_title);
      }
    } catch (err) {
      typing.remove();
      showWarning("Could not reach Lumora. Check your connection and try again.");
    }
  }

  function addSessionToList(id, title) {
    document.querySelectorAll(".chat-list").forEach(function (list) {
      const empty = list.querySelector("li:not(.chat-list-item)");
      if (empty) empty.remove();
      const li = el("li", "chat-list-item active");
      li.dataset.title = (title || "").toLowerCase();
      const a = el("a", "text-decoration-none text-dark flex-grow-1");
      a.href = "/chat?s=" + id;
      a.appendChild(el("div", "small fw-semibold text-truncate", title));
      a.appendChild(el("div", "text-secondary", "just now"));
      li.appendChild(a);
      const del = el("button", "btn btn-sm btn-link text-danger delete-session");
      del.type = "button";
      del.dataset.sessionId = id;
      del.title = "Delete chat";
      del.appendChild(el("i", "bi bi-trash"));
      li.appendChild(del);
      list.querySelectorAll(".chat-list-item.active").forEach(function (x) { x.classList.remove("active"); });
      list.prepend(li);
    });
  }

  // --- Delegated clicks: save insight, delete chat, topics ---
  document.addEventListener("click", async function (e) {
    const save = e.target.closest(".save-insight");
    if (save) {
      if (!authed) {
        showWarning("Log in to save insights.");
        return;
      }
      const resp = await fetch("/chat/insights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: save.dataset.messageId }),
      });
      if (resp.ok) {
        save.replaceChildren(el("i", "bi bi-bookmark-check-fill"), document.createTextNode(" Saved"));
        save.disabled = true;
      }
      return;
    }

    const del = e.target.closest(".delete-session");
    if (del) {
      if (!confirm("Delete this chat and all its messages?")) return;
      const id = del.dataset.sessionId;
      const resp = await fetch("/chat/sessions/" + id + "/delete", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (resp.ok) {
        if (String(id) === String(sessionId)) {
          window.location.href = "/chat";
        } else {
          document.querySelectorAll('.delete-session[data-session-id="' + id + '"]').forEach(function (b) {
            b.closest("li").remove();
          });
        }
      }
      return;
    }

    const topic = e.target.closest(".topic-item");
    if (topic) {
      const title = topic.dataset.title;
      const body = new URLSearchParams({ title: title });
      const resp = await fetch("/topic", { method: "POST", body: body });
      const data = await resp.json();
      appendMessage("right", title);
      (data.contents || []).forEach(function (part, i) {
        setTimeout(function () { appendMessage("left", part); }, i * 1200);
      });
    }
  });

  // --- Search Your Chats ---
  document.querySelectorAll(".chat-search").forEach(function (box) {
    box.addEventListener("input", function () {
      const q = box.value.trim().toLowerCase();
      box.parentElement.querySelectorAll(".chat-list-item").forEach(function (li) {
        li.style.display = li.dataset.title.includes(q) ? "" : "none";
      });
    });
  });

  // --- Response style ---
  document.getElementById("mode-select").addEventListener("change", function (e) {
    fetch("/chat/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: e.target.value }),
    });
  });

  // Bootstrap popovers
  document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (p) {
    new bootstrap.Popover(p);
  });

  scrollDown();
  input.focus();
})();
