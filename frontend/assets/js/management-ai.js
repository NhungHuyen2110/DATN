
(() => {
  "use strict";

  // Chống khởi tạo chatbot hai lần.
  if (window.__lumiereManagementAI) return;

  const script = document.currentScript;
  const role = script?.dataset.aiRole;

  const ENDPOINTS = {
    admin: "/admin/ai/chat",
    staff: "/staff/ai/chat",
  };

  if (!Object.hasOwn(ENDPOINTS, role)) return;

  window.__lumiereManagementAI = true;

  const apiBase = window.LUMIERE_API?.base || window.LUMIERE_API_BASE || window.location.origin;
  const endpoint = apiBase.replace(/\/$/, "") + ENDPOINTS[role];
  const isAdmin = role === "admin";

  const examples = isAdmin
    ? [
        "Doanh thu tháng 10/2026 là bao nhiêu?",
        "Top 5 sản phẩm bán chạy tháng 10/2026",
        "Những sản phẩm nào sắp hết hàng?",
      ]
    : [
        "Có bao nhiêu đơn chờ xử lý?",
        "Hôm nay có bao nhiêu đơn hàng?",
        "Những sản phẩm nào sắp hết hàng?",
      ];

  // CSS riêng, không thay đổi stylesheet hiện tại.
  const style = document.createElement("style");
  style.textContent = `
    #lumiere-mgmt-ai {
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 10000;
      font-family: Arial, sans-serif;
      color: #252525;
    }

    #lumiere-mgmt-ai * {
      box-sizing: border-box;
    }

    #lumiere-mgmt-ai .ai-toggle {
      border: none;
      background: #242424;
      color: white;
      padding: 15px 20px;
      border-radius: 30px;
      cursor: pointer;
      box-shadow: 0 5px 20px #0003;
    }

    #lumiere-mgmt-ai .ai-panel {
      display: none;
      position: absolute;
      right: 0;
      bottom: 65px;
      width: min(380px, calc(100vw - 32px));
      height: min(520px, calc(100dvh - 110px));
      background: white;
      border: 1px solid #ddd;
      border-radius: 16px;
      box-shadow: 0 8px 35px #0003;
      overflow: hidden;
      flex-direction: column;
    }

    #lumiere-mgmt-ai .ai-panel.open {
      display: flex;
    }

    #lumiere-mgmt-ai .ai-header {
      background: #242424;
      color: white;
      padding: 16px;
      font-weight: bold;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    #lumiere-mgmt-ai .ai-close {
      border: none;
      background: transparent;
      color: white;
      cursor: pointer;
      font-size: 22px;
    }

    #lumiere-mgmt-ai .ai-messages {
      flex: 1;
      min-height: 0;
      padding: 14px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    #lumiere-mgmt-ai .ai-message {
      max-width: 90%;
      padding: 11px 13px;
      border-radius: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 14px;
      line-height: 1.5;
    }

    #lumiere-mgmt-ai .ai-message.user {
      align-self: flex-end;
      background: #242424;
      color: white;
    }

    #lumiere-mgmt-ai .ai-message.bot {
      align-self: flex-start;
      background: #f2f2f2;
    }

    #lumiere-mgmt-ai .ai-suggestions {
      display: flex;
      gap: 6px;
      padding: 8px 12px;
      overflow-x: auto;
    }

    #lumiere-mgmt-ai .ai-suggestions button {
      flex-shrink: 0;
      border: 1px solid #ddd;
      background: white;
      border-radius: 15px;
      padding: 7px 10px;
      font-size: 12px;
      cursor: pointer;
    }

    #lumiere-mgmt-ai .ai-form {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid #eee;
    }

    #lumiere-mgmt-ai .ai-input {
      flex: 1;
      min-width: 0;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 10px;
      font-size: 14px;
    }

    #lumiere-mgmt-ai .ai-send {
      border: none;
      border-radius: 8px;
      background: #242424;
      color: white;
      padding: 10px 14px;
      cursor: pointer;
    }

    #lumiere-mgmt-ai button:disabled {
      opacity: .5;
      cursor: not-allowed;
    }

    @media (max-width: 480px) {
      #lumiere-mgmt-ai {
        right: 16px;
        bottom: 16px;
      }
    }
  `;

  document.head.appendChild(style);

  const root = document.createElement("div");
  root.id = "lumiere-mgmt-ai";

  root.innerHTML = `
    <section class="ai-panel" aria-label="Trợ lý AI">
      <header class="ai-header">
        <span>✦ LUMIÈRE AI ${isAdmin ? "Admin" : "Staff"}</span>
        <button class="ai-close" type="button"
          aria-label="Đóng chatbot">×</button>
      </header>

      <div class="ai-messages" aria-live="polite"></div>
      <div class="ai-suggestions"></div>

      <form class="ai-form">
        <input class="ai-input" type="text"
          maxlength="1000"
          placeholder="Nhập câu hỏi..."
          aria-label="Câu hỏi dành cho AI"
          required>
        <button class="ai-send" type="submit">Gửi</button>
      </form>
    </section>

    <button class="ai-toggle" type="button"
      aria-expanded="false">✦ Trợ lý AI</button>
  `;

  document.body.appendChild(root);

  const panel = root.querySelector(".ai-panel");
  const toggle = root.querySelector(".ai-toggle");
  const close = root.querySelector(".ai-close");
  const messages = root.querySelector(".ai-messages");
  const suggestions = root.querySelector(".ai-suggestions");
  const form = root.querySelector(".ai-form");
  const input = root.querySelector(".ai-input");
  const send = root.querySelector(".ai-send");

  let busy = false;
  let conversationId = null;

  function addMessage(text, type = "bot") {
    const node = document.createElement("div");
    node.className = `ai-message ${type}`;

    // textContent ngăn HTML từ phản hồi AI bị thực thi.
    node.textContent = String(text);

    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;

    return node;
  }

  function setOpen(open) {
    panel.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));

    if (open) input.focus();
  }

  toggle.addEventListener("click", () => {
    setOpen(!panel.classList.contains("open"));
  });

  close.addEventListener("click", () => setOpen(false));

  addMessage(
    `Xin chào! Tôi là trợ lý AI ${isAdmin ? "Admin" : "Staff"} ` +
    "của LUMIÈRE. Bạn cần hỗ trợ gì?"
  );

  for (const question of examples) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question;

    button.addEventListener("click", () => {
      input.value = question;
      form.requestSubmit();
    });

    suggestions.appendChild(button);
  }

  async function askAI(question) {
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      65000
    );

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({ message: question, conversation_id: conversationId }),
        signal: controller.signal,
      });

      if (response.status === 401 || response.status === 403) {
        return "Phiên đăng nhập không hợp lệ hoặc tài khoản " +
          "không có quyền sử dụng trợ lý này.";
      }

      if (!response.ok) {
        return `Không thể xử lý yêu cầu (HTTP ${response.status}).`;
      }

      const data = await response.json();
      if (typeof data.conversation_id === 'string') conversationId = data.conversation_id;

      return typeof data.answer === "string"
        ? data.answer
        : "AI chưa có câu trả lời phù hợp.";

    } catch (error) {
      if (error.name === "AbortError") {
        return "Yêu cầu quá lâu. Vui lòng thử lại.";
      }

      return "Không thể kết nối đến AI. " +
        "Vui lòng kiểm tra backend.";
    } finally {
      clearTimeout(timeout);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();

    if (!question || busy) return;

    busy = true;
    send.disabled = true;
    input.disabled = true;

    addMessage(question, "user");
    input.value = "";

    const loading = addMessage("Đang xử lý...", "bot");

    try {
      const answer = await askAI(question);
      loading.textContent = answer;
    } finally {
      busy = false;
      send.disabled = false;
      input.disabled = false;
      messages.scrollTop = messages.scrollHeight;
      input.focus();
    }
  });
})();
