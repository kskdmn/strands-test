const STORAGE_KEY = "strands-test-conversation-id";

const messageList = document.getElementById("message-list");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.getElementById("new-chat-button");
const messageTemplate = document.getElementById("message-template");
const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

function getConversationId() {
  return localStorage.getItem(STORAGE_KEY);
}

function setConversationId(conversationId) {
  localStorage.setItem(STORAGE_KEY, conversationId);
}

function clearConversationId() {
  localStorage.removeItem(STORAGE_KEY);
}

function renderEmptyState() {
  messageList.innerHTML = `
    <div class="empty-state">
      <p>Start a conversation by sending a message below.</p>
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

async function ensureConversation() {
  const existingId = getConversationId();
  if (existingId) {
    return existingId;
  }

  const payload = await apiRequest("/api/conversations/", { method: "POST" });
  setConversationId(payload.conversation_id);
  return payload.conversation_id;
}

async function loadConversation() {
  const conversationId = getConversationId();
  if (!conversationId) {
    renderEmptyState();
    return;
  }

  try {
    const payload = await apiRequest(`/api/conversations/${conversationId}/messages/`);
    if (!payload.messages.length) {
      renderEmptyState();
      return;
    }

    messageList.innerHTML = "";
    payload.messages.forEach((message) => {
      renderMessage(message.role, message.content);
    });
  } catch (error) {
    clearConversationId();
    renderEmptyState();
  }
}

async function sendMessage(content) {
  const conversationId = await ensureConversation();
  renderMessage("user", content);
  const pendingNode = renderMessage("assistant", "Thinking...", { pending: true });

  sendButton.disabled = true;
  newChatButton.disabled = true;

  try {
    const payload = await apiRequest(
      `/api/conversations/${conversationId}/messages/send/`,
      {
        method: "POST",
        body: JSON.stringify({ content }),
      },
    );

    pendingNode.remove();
    const assistantMessage = payload.messages.find((message) => message.role === "assistant");
    renderMessage("assistant", assistantMessage.content);
  } catch (error) {
    pendingNode.classList.remove("pending");
    pendingNode.classList.add("error");
    pendingNode.querySelector(".message-content").textContent = error.message;
  } finally {
    sendButton.disabled = false;
    newChatButton.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = messageInput.value.trim();
  if (!content) {
    return;
  }

  messageInput.value = "";
  messageInput.style.height = "auto";
  await sendMessage(content);
});

newChatButton.addEventListener("click", async () => {
  clearConversationId();
  renderEmptyState();
  await ensureConversation();
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

loadConversation();
