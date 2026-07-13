const messageList = document.getElementById("message-list");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const clearButton = document.getElementById("clear-button");
const messageTemplate = document.getElementById("message-template");
const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

function renderEmptyState() {
  messageList.innerHTML = `
    <div class="empty-state">
      <p>Send a single question below. Each request starts fresh on the server.</p>
    </div>
  `;
}

function renderMessage(role, content, options = {}) {
  if (messageList.querySelector(".empty-state")) {
    messageList.innerHTML = "";
  }

  const node = messageTemplate.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  if (options.pending) {
    node.classList.add("pending");
  }
  if (options.error) {
    node.classList.add("error");
  }

  node.querySelector(".message-meta").textContent = role;

  const thinkingNode = node.querySelector(".message-thinking");
  const thinkingContent = options.thinking?.trim();
  if (thinkingContent) {
    thinkingNode.querySelector(".message-thinking-content").textContent = thinkingContent;
  } else {
    thinkingNode.remove();
  }

  node.querySelector(".message-content").textContent = content;
  messageList.appendChild(node);
  messageList.scrollTop = messageList.scrollHeight;
  return node;
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

async function sendMessage(message) {
  renderMessage("user", message);
  const pendingNode = renderMessage("assistant", "Thinking...", { pending: true });

  sendButton.disabled = true;
  clearButton.disabled = true;

  try {
    const payload = await apiRequest("/api/single-round/chat/", {
      method: "POST",
      body: JSON.stringify({ message }),
    });

    pendingNode.remove();
    renderMessage("assistant", payload.reply, { thinking: payload.thinking });
  } catch (error) {
    pendingNode.classList.remove("pending");
    pendingNode.classList.add("error");
    pendingNode.querySelector(".message-content").textContent = error.message;
  } finally {
    sendButton.disabled = false;
    clearButton.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  messageInput.value = "";
  messageInput.style.height = "auto";
  await sendMessage(message);
});

clearButton.addEventListener("click", () => {
  renderEmptyState();
  messageInput.focus();
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

renderEmptyState();
