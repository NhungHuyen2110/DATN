
(function () {
  "use strict";

  if (document.body.dataset.page !== "forgot-password") {
    return;
  }

  function initializeForgotPassword() {
    const button = document.querySelector("#forgot-demo");
    const emailInput = document.querySelector("#email");

    if (!button || !emailInput) {
      return;
    }

    // Không gắn sự kiện nhiều lần.
    if (button.dataset.resetReady === "true") {
      return;
    }

    button.dataset.resetReady = "true";

    // Thay sự kiện demo cũ trong site.js.
    button.onclick = null;

    button.textContent = "GỬI YÊU CẦU KHÔI PHỤC";
    button.disabled = false;

    // Cập nhật thông báo cũ.
    const note = document.querySelector(
      ".auth-form .demo-note"
    );

    if (note) {
      note.textContent =
        "Dịch vụ gửi email khôi phục hiện chưa được kích hoạt. " +
        "Vui lòng liên hệ bộ phận hỗ trợ nếu bạn cần đặt lại mật khẩu.";
    }

    const feedback = document.createElement("p");
    feedback.id = "forgot-password-result";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    button.insertAdjacentElement("afterend", feedback);

    button.addEventListener("click", async function () {
      const email = emailInput.value.trim();

      if (!emailInput.checkValidity()) {
        emailInput.reportValidity();
        return;
      }

      button.disabled = true;
      button.textContent = "ĐANG XỬ LÝ...";
      feedback.textContent = "";

      try {
        const response = await fetch(
          window.LUMIERE_API.base + "/auth/forgot-password",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            credentials: "same-origin",
            body: JSON.stringify({ email })
          }
        );

        if (!response.ok) {
          throw new Error(
            "Không thể xử lý yêu cầu lúc này."
          );
        }

        feedback.textContent =
          "Yêu cầu khôi phục đã được tiếp nhận. " +
          "Vui lòng liên hệ bộ phận hỗ trợ để được hướng dẫn tiếp theo.";

        feedback.style.color = "#437447";

      } catch (error) {
        feedback.textContent = error.message;
        feedback.style.color = "#b42318";

      } finally {
        button.disabled = false;
        button.textContent =
          "GỬI YÊU CẦU KHÔI PHỤC";
      }
    });

    console.log(
      "[LUMIERE] Forgot password initialized"
    );
  }

  // Theo dõi vì site.js render nội dung bất đồng bộ.
  function watchPage() {
    const mount = document.querySelector("#page-content");

    if (!mount) {
      return;
    }

    initializeForgotPassword();

    const observer = new MutationObserver(function () {
      initializeForgotPassword();
    });

    observer.observe(mount, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      watchPage
    );
  } else {
    watchPage();
  }
})();
