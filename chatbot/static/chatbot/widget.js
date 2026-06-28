// chatbot/static/chatbot/widget.js
(function () {
  "use strict";

  // ---- CSRF helper (needed once @csrf_exempt is removed from the view) ----
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }

  const CHAT_MESSAGE_URL = "/chatbot/message/";
  const CHAT_GREETING_URL = "/chatbot/greeting/";

  let widgetOpen = false;
  let greetingLoaded = false;

  function createWidget() {
    const bubble = document.createElement("button");
    bubble.id = "lln-chat-bubble";
    bubble.setAttribute("aria-label", "Open chat assistant");
    bubble.innerHTML = "💬";

    const panel = document.createElement("div");
    panel.id = "lln-chat-panel";
    panel.innerHTML = `
      <div id="lln-chat-header">
        <span>LifeLink Assistant</span>
        <button id="lln-chat-close" aria-label="Close chat">&times;</button>
      </div>
      <div id="lln-chat-messages"></div>
      <div id="lln-chat-input-row">
        <input id="lln-chat-input" type="text" placeholder="Type a message..." />
        <button id="lln-chat-send" aria-label="Send message">Send</button>
      </div>
    `;

    document.body.appendChild(bubble);
    document.body.appendChild(panel);

    bubble.addEventListener("click", toggleWidget);
    panel.querySelector("#lln-chat-close").addEventListener("click", toggleWidget);
    panel.querySelector("#lln-chat-send").addEventListener("click", sendMessage);
    panel.querySelector("#lln-chat-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter") sendMessage();
    });
  }

  function toggleWidget() {
    widgetOpen = !widgetOpen;
    const panel = document.getElementById("lln-chat-panel");
    panel.classList.toggle("lln-open", widgetOpen);

    if (widgetOpen && !greetingLoaded) {
      loadGreeting();
      greetingLoaded = true;
    }
  }

  function loadGreeting() {
    fetch(CHAT_GREETING_URL)
      .then((res) => res.json())
      .then((data) => {
        appendBotMessage(data.answer);
        if (data.quick_replies && data.quick_replies.length) {
          appendQuickReplies(data.quick_replies);
        }
      })
      .catch(() => {
        appendBotMessage(
          "Hi! I'm having trouble loading right now, but feel free to type a question."
        );
      });
  }

  function appendUserMessage(text) {
    const messages = document.getElementById("lln-chat-messages");
    const el = document.createElement("div");
    el.className = "lln-msg lln-msg-user";
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  function appendBotMessage(text) {
    const messages = document.getElementById("lln-chat-messages");
    const el = document.createElement("div");
    el.className = "lln-msg lln-msg-bot";
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  function appendQuickReplies(replies) {
    const messages = document.getElementById("lln-chat-messages");
    const row = document.createElement("div");
    row.className = "lln-quick-replies";

    replies.forEach((reply) => {
      const btn = document.createElement("button");
      btn.className = "lln-quick-reply-btn";
      btn.textContent = reply.label;
      btn.addEventListener("click", function () {
        row.remove(); // remove buttons once one is used
        appendUserMessage(reply.label);
        sendToBackend(reply.value);
      });
      row.appendChild(btn);
    });

    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function handleAction(action) {
    // donorRegisterUrl / hospitalRegisterUrl are set in base.html via
    // Django's {% url %} tag (see snippet below), so these are always
    // correct even if the underlying URL pattern changes later.
    if (action === "route_donor") {
      appendBotMessage("Taking you to donor registration...");
      setTimeout(function () {
        window.location.href = window.LLN_CHATBOT_CONFIG.donorRegisterUrl;
      }, 900);
    } else if (action === "route_hospital") {
      appendBotMessage("Taking you to hospital registration...");
      setTimeout(function () {
        window.location.href = window.LLN_CHATBOT_CONFIG.hospitalRegisterUrl;
      }, 900);
    }
  }

  function sendMessage() {
    const input = document.getElementById("lln-chat-input");
    const text = input.value.trim();
    if (!text) return;

    appendUserMessage(text);
    input.value = "";
    sendToBackend(text);
  }

  function sendToBackend(text) {
    const typingEl = appendTypingIndicator();

    fetch(CHAT_MESSAGE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify({ message: text }),
    })
      .then((res) => res.json())
      .then((data) => {
        typingEl.remove();
        appendBotMessage(data.answer);
        if (data.action) {
          handleAction(data.action);
        }
      })
      .catch(() => {
        typingEl.remove();
        appendBotMessage(
          "Sorry, something went wrong. Please try again in a moment."
        );
      });
  }

  function appendTypingIndicator() {
    const messages = document.getElementById("lln-chat-messages");
    const el = document.createElement("div");
    el.className = "lln-msg lln-msg-bot lln-typing";
    el.textContent = "...";
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  document.addEventListener("DOMContentLoaded", createWidget);
})();