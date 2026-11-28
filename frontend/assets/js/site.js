"use strict";
(() => {
  const root = document.body.dataset.root || "../",
    page = document.body.dataset.page,
    area = document.body.dataset.area;
  const P = window.LUMIERE_PRODUCTS || [];
  const $ = (s) => document.querySelector(s),
    esc = (x) =>
      String(x ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
          })[c],
      );
  const money = (n) => Number(n || 0).toLocaleString("vi-VN") + " ₫";
  const read = (key, fallback) => {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      return v ?? fallback;
    } catch {
      return fallback;
    }
  };
  const FAV = "lumiere_favorites";
  let user = null;
  let cartData = { items: [], total_quantity: 0, subtotal_vnd: "0.00" };
  let cartBusy = false;
  const favorites = () => read(FAV, []);
  const save = (key, value) => localStorage.setItem(key, JSON.stringify(value));
  const product = (id) => P.find((p) => p.id === Number(id));
  const notify = (text, error = false) => {
    const el = $("#site-toast");
    el.textContent = text;
    el.style.background = error ? "#9d4232" : "#292824";
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => (el.textContent = ""), 4200);
  };
  const demo = (msg) =>
    notify(
      msg ||
        "Đây là giao diện DEMO. Backend chưa cung cấp API cho chức năng này.",
    );
  const nav = (text, url) => `<a href="${root + url}">${text}</a>`;

  const shell = $("#site-shell");

  const managementArea = area === "admin" || area === "staff";

  const footer = $("#site-footer");

  footer.innerHTML = managementArea
    ? `
    <footer class="footer shell-management-footer">
      <div class="container footer-bottom">
        <span>© 2026 LUMIÈRE</span>
      </div>
    </footer>
  `
    : `
    <footer class="footer premium-footer">

      <div class="footer-benefits">
        <div class="container footer-benefits-grid">

          <div class="footer-benefit">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M6 3h12l4 6-10 12L2 9Z"/>
              <path d="M2 9h20M6 3l6 18L18 3"/>
            </svg>

            <strong>Thiết kế tinh tế</strong>
            <span>Dấu ấn riêng của bạn</span>
          </div>

          <div class="footer-benefit">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/>
              <path d="m9 12 2 2 4-4"/>
            </svg>

            <strong>Chất lượng chọn lọc</strong>
            <span>Thông tin sản phẩm rõ ràng</span>
          </div>

          <div class="footer-benefit">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M1 4h14v13H1ZM15 9h4l4 4v4h-8"/>
              <circle cx="5.5" cy="18" r="2.5"/>
              <circle cx="18.5" cy="18" r="2.5"/>
            </svg>

            <strong>Giao hàng thuận tiện</strong>
            <span>Theo dõi đơn hàng dễ dàng</span>
          </div>

          <div class="footer-benefit">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M3 14v-3a9 9 0 0 1 18 0v3M21 16v2a4 4 0 0 1-4 4h-3"/>
              <rect x="2" y="11" width="5" height="7" rx="2"/>
              <rect x="17" y="11" width="5" height="7" rx="2"/>
            </svg>

            <strong>Tận tâm hỗ trợ</strong>
            <span>Đồng hành cùng khách hàng</span>
          </div>

        </div>
      </div>

      <div class="container footer-grid">

        <div class="footer-brand">

          <a class="logo footer-logo"
             href="${root}index.html">
            LUMIÈRE
            <span>FINE JEWELRY</span>
          </a>

          <p class="footer-description">
            Vẻ đẹp vượt thời gian.<br>
            Chạm vào dấu ấn riêng của bạn.
          </p>

          <div class="footer-contact">

            <div class="footer-contact-row">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M7 3H4a1 1 0 0 0-1 1
                c0 9.4 7.6 17 17 17
                a1 1 0 0 0 1-1v-3l-5-2-2 2
                a14 14 0 0 1-7-7l2-2Z"/>
              </svg>

              <span>09 2210 2110</span>
            </div>

            <div class="footer-contact-row">
              <svg viewBox="0 0 24 24" fill="none">
                <rect x="3" y="5" width="18"
                      height="14" rx="2"/>
                <path d="m3 7 9 6 9-6"/>
              </svg>

              <span>contact@lumiere.vn</span>
            </div>

            <div class="footer-contact-row footer-address">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M20 10c0 6-8 11-8 11S4 16 4 10
                        a8 8 0 1 1 16 0Z"/>
                <circle cx="12" cy="10" r="2.5"/>
              </svg>

              <span>
                12 Nguyễn Văn Bảo, phường Hạnh Thông,
                TP. Hồ Chí Minh
              </span>
            </div>

          </div>

        </div>

        <div>

          <h3>KHÁM PHÁ</h3>

          ${nav("Tất cả sản phẩm", "pages/products.html")}

          ${["Nhẫn", "Dây chuyền", "Bông tai", "Lắc tay", "Vòng tay"]
            .map(
              (category) => `
              <a href="${root}pages/products.html?category=${encodeURIComponent(category)}">
                ${esc(category)}
              </a>
            `,
            )
            .join("")}

          ${nav("Câu chuyện thương hiệu", "pages/about.html")}

        </div>

        <div class="footer-support">

          <h3>HỖ TRỢ KHÁCH HÀNG</h3>

          ${nav("Liên hệ hỗ trợ", "pages/contact.html")}

          <a href="${root}pages/policies.html#shopping">
            Hướng dẫn mua hàng
          </a>

          <a href="${root}pages/policies.html#payment">
            Hướng dẫn thanh toán
          </a>

          <a href="${root}pages/policies.html#warranty">
            Chính sách bảo hành
          </a>

          <a href="${root}pages/policies.html#returns">
            Chính sách đổi trả
          </a>

          <a href="${root}pages/policies.html#shipping">
            Chính sách giao hàng
          </a>

          <a href="${root}pages/policies.html#privacy">
            Chính sách bảo mật
          </a>

          <a href="${root}pages/policies.html#care">
            Hướng dẫn bảo quản
          </a>

          <button id="footer-chat" hidden>
            Tư vấn trực tuyến
          </button>

        </div>

        <div>

          <h3>MY LUMIÈRE</h3>

          ${nav("Thông tin tài khoản", "pages/account.html")}

          ${nav("Sản phẩm yêu thích", "pages/wishlist.html")}

          ${nav("Đơn hàng của tôi", "pages/orders.html")}

          ${nav("Đánh giá của tôi", "pages/reviews.html")}
          ${nav("Giỏ hàng của bạn", "pages/cart.html")}

          <div class="footer-payment">

            <h3>PHƯƠNG THỨC THANH TOÁN</h3>

            <div class="footer-payment-methods">

              <div class="payment-vnpay">
                VN<span>PAY</span>
              </div>

              <div class="payment-cod">
                <svg viewBox="0 0 24 24" fill="none">
                  <rect x="2" y="5" width="20"
                        height="14" rx="2"/>
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M6 12h.01M18 12h.01"/>
                </svg>

                COD
              </div>

            </div>

          </div>

        </div>

      </div>

      <div class="container footer-bottom footer-bottom-center">

        <div class="footer-copyright">
          © 2026 LUMIÈRE Fine Jewelry. All rights reserved.
        </div>

      </div>

    </footer>
  `;
  // Trang chủ chỉ sử dụng footer chung,
  // giữ nguyên header và logic riêng.
  if (!shell) return;
  /* ========================================
   SHARED CHATBOT LOADER
   ======================================== */

  function mountSharedChatbot() {
    if (!user) return;

    const isManagement = area === "admin" || area === "staff";

    // Chỉ hiển thị chatbot đúng vai trò đã đăng nhập.
    if (isManagement && user.role !== area) return;
    if (!isManagement && user.role !== "customer") return;

    // Không hiển thị chatbot trên các trang xác thực.
    if (
      ["login", "register", "forgot-password", "reset-password"].includes(page)
    ) {
      return;
    }

    const scriptName = isManagement ? "management-ai.js" : "customer-ai.js";

    const cssName = isManagement
      ? "management-ai-polish.css"
      : "customer-ai.css";

    const widgetId = isManagement ? "lumiere-mgmt-ai" : "lumiere-ai-widget";

    // Không tạo chatbot nếu trang đã có.

    if (document.getElementById(widgetId)) return;

    // Kiểm tra stylesheet hiện có.

    const hasCSS = Array.from(
      document.querySelectorAll('link[rel="stylesheet"]'),
    ).some((link) => {
      return link.href.endsWith("/" + cssName);
    });

    if (!hasCSS) {
      const stylesheet = document.createElement("link");

      stylesheet.rel = "stylesheet";
      stylesheet.href = root + "assets/css/" + cssName;

      document.head.appendChild(stylesheet);
    }

    // Kiểm tra script hiện có.

    const hasScript = Array.from(document.querySelectorAll("script[src]")).some(
      (script) => {
        return script.src.endsWith("/" + scriptName);
      },
    );

    if (hasScript) return;

    const chatbotScript = document.createElement("script");

    chatbotScript.src = root + "assets/js/" + scriptName;

    if (isManagement) {
      chatbotScript.dataset.aiRole = area;
    }

    chatbotScript.onerror = () => {
      console.warn("Không thể tải trợ lý LUMIÈRE.");
    };

    document.body.appendChild(chatbotScript);
  }

  const roleTitle = area === "admin" ? "Bảng điều khiển" : "Quản lý cửa hàng";

  const rolePath =
    area === "admin" ? "pages/admin/dashboard.html" : "pages/staff/orders.html";

  const accountIcon = `
<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <circle cx="12" cy="7.6" r="3.4"/>
  <path d="M4.7 21c.4-5.1 3-7.5 7.3-7.5s7 2.4 7.3 7.5"/>
</svg>`;

  const shopLinks = `
  ${nav("Trang chủ", "index.html")}

  <a href="${root}pages/products.html" data-mega-products>
    Sản phẩm
  </a>

  ${nav("Về chúng tôi", "pages/about.html")}
  ${nav("Liên hệ", "pages/contact.html")}
`;

  const shopActions = `
  <div class="header-search-mount"></div>

  <a class="icon-btn"
     href="${root}pages/wishlist.html"
     title="Yêu thích"
     aria-label="Yêu thích">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M20.7 8.4c0 5-8.7 11-8.7 11s-8.7-6-8.7-11A4.6 4.6 0 0 1 12 6.3a4.6 4.6 0 0 1 8.7 2.1Z"/>
    </svg>
  </a>

  <a class="icon-btn"
     href="${root}pages/cart.html"
     title="Giỏ hàng"
     aria-label="Giỏ hàng">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 8h16l-1.3 12H5.3L4 8Z"/>
      <path d="M8 9V6a4 4 0 0 1 8 0v3"/>
    </svg>
  </a>
`;

  shell.innerHTML = `
<header class="site-header lumiere-shell-header ${managementArea ? "management-header" : ""}" id="site-header">

  

  <div class="container header-inner">

    <button class="icon-btn mobile-only shell-menu-toggle"
            type="button"
            aria-label="Mở menu"
            aria-expanded="false"
            aria-controls="shell-main-nav"
            ${managementArea ? "hidden" : ""}>
      ☰
    </button>

    <a class="logo"
       href="${root}index.html"
       aria-label="LUMIÈRE trang chủ">
      LUMIÈRE
      <span>FINE JEWELRY</span>
    </a>


    ${
      managementArea
        ? ""
        : `
        <div class="header-contact">

            <div class="header-contact-item">
                <svg viewBox="0 0 24 24" fill="none"
                    aria-hidden="true">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2
                            19.79 19.79 0 0 1-8.63-3.07
                            19.5 19.5 0 0 1-6-6
                            19.79 19.79 0 0 1-3.07-8.67
                            A2 2 0 0 1 4.11 2h3
                            a2 2 0 0 1 2 1.72
                            c.13.96.36 1.9.69 2.81
                            a2 2 0 0 1-.45 2.11L8.09 9.91
                            a16 16 0 0 0 6 6l1.27-1.27
                            a2 2 0 0 1 2.11-.45
                            c.91.33 1.85.56 2.81.69
                            A2 2 0 0 1 22 16.92z"/>
                </svg>

                <span>09 2210 2110</span>
            </div>

            <div class="header-contact-item">
                <svg viewBox="0 0 24 24" fill="none"
                    aria-hidden="true">
                    <rect x="3" y="5" width="18"
                          height="14" rx="2"/>
                    <path d="m3 7 9 6 9-6"/>
                </svg>

                <span>contact@lumiere.vn</span>
            </div>

        </div>
    `
    }


    <nav class="main-nav"
         id="shell-main-nav"
         aria-label="Điều hướng chính">
      ${
        managementArea
          ? `
          <a class="management-store-link" href="${root}index.html">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 9l2-5h14l2 5v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0Z"/>
              <path d="M5 14v7h14v-7M9 21v-6h6v6"/>
            </svg>
            <span>Xem cửa hàng</span>
          </a>
        `
          : shopLinks
      }
    </nav>

    <div class="header-actions shell-account-links">

      ${managementArea ? "" : shopActions}

      <a class="icon-btn"
         id="account-nav"
         href="${root}pages/login.html"
         title="Tài khoản"
         aria-label="Tài khoản">
        ${accountIcon}
      </a>

      <details class="shell-account-menu" hidden>

        <summary class="icon-btn ${managementArea ? "management-account-trigger" : ""}"
         aria-label="Menu tài khoản">

  ${
    managementArea
      ? `
    <span class="management-avatar">
      ${accountIcon}
    </span>

    <span class="management-identity">
      <strong id="management-user-name">Tài khoản</strong>
      <small id="management-user-role"></small>
    </span>

    <svg class="management-chevron"
         viewBox="0 0 24 24"
         fill="none"
         aria-hidden="true">
      <path d="m6 9 6 6 6-6"/>
    </svg>

  `
      : accountIcon
  }

</summary>

        <div class="shell-account-panel">
          <span class="shell-account-name"></span>
          <div class="shell-account-options"></div>

          <button id="nav-logout" type="button">
            Đăng xuất
          </button>
        </div>

      </details>

    </div>

  </div>
</header>
`;

  // Shared header search
  if (!managementArea) {
    const searchScript = document.createElement("script");

    searchScript.src = root + "assets/js/header-search.js";

    document.head.appendChild(searchScript);
  }

  const menuToggle = $(".shell-menu-toggle");

  menuToggle.addEventListener("click", () => {
    const opened = $("#shell-main-nav").classList.toggle("open");

    menuToggle.setAttribute("aria-expanded", String(opened));
  });

  const accountMenu = $(".shell-account-menu");

  document.addEventListener("click", (event) => {
    if (!accountMenu.contains(event.target)) {
      accountMenu.open = false;
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      accountMenu.open = false;

      $("#shell-main-nav").classList.remove("open");

      menuToggle.setAttribute("aria-expanded", "false");
    }
  });

  function showSignedInMenu() {
    const account = $("#account-nav");

    account.hidden = true;
    accountMenu.hidden = false;

    accountMenu.querySelector(".shell-account-name").textContent =
      user.full_name || "Tài khoản";

    const options = accountMenu.querySelector(".shell-account-options");

    if (user.role === "admin" || user.role === "staff") {
      const isAdmin = user.role === "admin";

      if (managementArea) {
        $("#management-user-name").textContent = user.full_name || "Tài khoản";

        $("#management-user-role").textContent = isAdmin
          ? "Quản trị viên"
          : "Nhân viên";
      }

      options.innerHTML = nav(
        isAdmin ? "Bảng điều khiển" : "Xử lý đơn hàng",
        isAdmin ? "pages/admin/dashboard.html" : "pages/staff/orders.html",
      );

      accountMenu.querySelector(".shell-account-name").textContent += isAdmin
        ? " · Quản trị viên"
        : " · Nhân viên";
    } else {
      options.innerHTML =
        nav("Thông tin cá nhân", "pages/account.html") +
        nav("Đơn hàng của tôi", "pages/orders.html") +
        nav("Đánh giá của tôi", "pages/reviews.html");
    }
  }

  const content = $("#page-content");

  /* ========================================
   SHARED CUSTOMER BREADCRUMB
   ======================================== */

  function mountBreadcrumb() {
    if (area !== "shop") return;

    const main = $("#page-root");

    if (!main) return;

    // Không tạo trùng breadcrumb trang sản phẩm.
    if (main.querySelector(".catalog-breadcrumb")) return;

    const labels = {
      products: "Sản phẩm",
      "product-detail": "Chi tiết sản phẩm",
      collections: "Bộ sưu tập",
      search: "Kết quả tìm kiếm",
      wishlist: "Yêu thích",
      cart: "Giỏ hàng",
      checkout: "Thanh toán",
      account: "Tài khoản",
      orders: "Đơn hàng của tôi",
      reviews: "Đánh giá của tôi",
      about: "Về chúng tôi",
      contact: "Liên hệ",
      login: "Đăng nhập",
      register: "Đăng ký",
      "forgot-password": "Quên mật khẩu",
      "reset-password": "Đặt lại mật khẩu",
    };

    if (!labels[page]) return;

    const parents = {
      "product-detail": [["Sản phẩm", "pages/products.html"]],
      checkout: [["Giỏ hàng", "pages/cart.html"]],
      orders: [["Tài khoản", "pages/account.html"]],
      reviews: [["Tài khoản", "pages/account.html"]],
      "forgot-password": [["Đăng nhập", "pages/login.html"]],
      "reset-password": [["Đăng nhập", "pages/login.html"]],
    };

    const links = [["Trang chủ", "index.html"], ...(parents[page] || [])];

    const breadcrumb = document.createElement("nav");

    breadcrumb.className = "catalog-breadcrumb";
    breadcrumb.setAttribute("aria-label", "Đường dẫn");

    breadcrumb.innerHTML = `
    ${links
      .map(
        ([label, url]) => `
      <a href="${root + url}">${esc(label)}</a>
      <span aria-hidden="true">/</span>
    `,
      )
      .join("")}

    <span aria-current="page">
      ${esc(labels[page])}
    </span>
  `;

    main.prepend(breadcrumb);
  }

  mountBreadcrumb();

  function applyRoleNavigation() {
    const role = user?.role || "guest";

    if (role !== "admin" && role !== "staff") {
      return false;
    }

    const roleHome =
      role === "admin"
        ? "pages/admin/dashboard.html"
        : "pages/staff/orders.html";

    const publicPages = [
      "products",
      "product-detail",
      "collections",
      "search",
      "about",
      "contact",
    ];

    if (publicPages.includes(page)) {
      document.body.classList.add("management-preview");
      return false;
    }

    const allowed =
      role === "admin" ? page.startsWith("admin-") : page.startsWith("staff-");

    if (!allowed) {
      location.replace(root + roleHome);
      return true;
    }

    return false;
  }

  const card = (p) => {
    const saved = wishlistIds.has(Number(p.id));
    const url = `${root}pages/product-detail.html?id=${encodeURIComponent(p.id)}`;

    return `
    <article class="catalog-card">

      <div class="catalog-picture">
        <a href="${url}">
          <img loading="lazy"
               src="${esc(p.image)}"
               alt="${esc(p.name)}">
        </a>

        <button type="button"
                class="catalog-wish ${saved ? "is-active" : ""}"
                data-favorite="${p.id}"
                aria-pressed="${saved}"
                aria-label="${saved ? "Bỏ yêu thích" : "Thêm vào yêu thích"}"
                title="${saved ? "Bỏ yêu thích" : "Thêm vào yêu thích"}">

          <svg viewBox="0 0 24 24"
               aria-hidden="true">
            <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>
          </svg>

        </button>
      </div>

      <div class="meta">
        <small>${esc(p.category)} · ${esc(p.material)}</small>

        <h3>
          <a href="${url}">${esc(p.name)}</a>
        </h3>

        <strong>${money(p.price)}</strong>
      </div>

    </article>`;
  };
  const formField = (id, label, type = "text", extra = "") =>
    `<div class="field"><label for="${id}">${label}</label><input id="${id}" name="${id}" type="${type}" ${extra}></div>`;
  const errorBox =
    '<div id="form-alert" class="form-alert" role="status" aria-live="polite" hidden></div>';
  const alert = (message, kind = "error") => {
    const el = $("#form-alert");
    if (!el) return;
    el.hidden = false;
    el.className = "form-alert " + kind;
    el.textContent = message;
  };
  const get = (id) => document.getElementById(id)?.value?.trim() || "";
  async function add(id, amount = 1) {
    if (user && user.role !== "customer") {
      notify("Tài khoản quản lý chỉ có thể xem sản phẩm.", true);
      return;
    }
    if (!user) {
      notify("Vui lòng đăng nhập để thêm vào giỏ hàng.", true);
      return;
    }
    if (cartBusy) return;
    const productId = Number(id);
    if (
      !Number.isInteger(productId) ||
      !Number.isInteger(amount) ||
      amount < 1
    ) {
      notify("Số lượng sản phẩm không hợp lệ.", true);
      return;
    }
    cartBusy = true;
    try {
      cartData = await LUMIERE_API.addCartItem(productId, amount);
      notify(
        "\u0110\u00e3 th\u00eam s\u1ea3n ph\u1ea9m v\u00e0o gi\u1ecf h\u00e0ng",
      );
      if (page === "cart" || page === "checkout") render();
    } catch (error) {
      notify(error.message, true);
    } finally {
      cartBusy = false;
    }
  }
  async function changeCartItem(productId, delta, remove = false) {
    if (cartBusy || !user) return;
    const item = cartData.items.find(
      (row) => row.product.id === Number(productId),
    );
    if (!item) return;
    cartBusy = true;
    try {
      const next = item.quantity + delta;
      if (remove || next <= 0) {
        cartData = await LUMIERE_API.removeCartItem(item.id);
      } else {
        cartData = await LUMIERE_API.updateCartItem(item.id, next);
      }
      render();
      notify("\u0110\u00e3 c\u1eadp nh\u1eadt gi\u1ecf h\u00e0ng");
    } catch (error) {
      notify(error.message, true);
    } finally {
      cartBusy = false;
    }
  }
  function favorite(id) {
    id = Number(id);
    const f = favorites();
    const next = f.includes(id) ? f.filter((n) => n !== id) : [...f, id];
    save(FAV, next);
    notify(f.includes(id) ? "Đã bỏ yêu thích" : "Đã thêm vào yêu thích");
    if (page === "wishlist") render();
  }
  const cartLines = () =>
    cartData.items
      .map((item) => ({
        p: product(item.product.id),
        qty: Number(item.quantity),
        itemId: item.id,
        unitPrice: Number(item.unit_price_vnd),
        lineTotal: Number(item.line_total_vnd),
      }))
      .filter((x) => x.p && Number.isInteger(x.qty) && x.qty > 0);
  const subtotal = () => Number(cartData.subtotal_vnd || 0);
  const shipping = () => (subtotal() > 0 && subtotal() < 2000000 ? 30000 : 0);
  const itemsHtml = () =>
    cartLines()
      .map(
        ({ p, qty, unitPrice, lineTotal }) => `
<div class="list-row">
  <a href="${root}pages/product-detail.html?id=${p.id}">
    <img src="${esc(p.image)}" alt="${esc(p.name)}">
  </a>
  <div>
    <h3>${esc(p.name)}</h3>
    <p>${esc(p.material)} &middot; ${money(unitPrice)}</p>
    <button data-remove="${p.id}">X&oacute;a s&#7843;n ph&#7849;m</button>
  </div>
  <div>
    <div class="qty-line">
      <button data-dec="${p.id}" aria-label="Gi&#7843;m">&minus;</button>
      <strong>${qty}</strong>
      <button data-inc="${p.id}" aria-label="Tăng">+</button>
    </div>
    <strong class="price">${money(lineTotal)}</strong>
  </div>
</div>`,
      )
      .join("");
  function requireAuthMessage() {
    return '<p class="demo-note">Bạn cần đăng nhập để tiếp tục. Thông tin đơn hàng chưa được ghi vào PostgreSQL trong bản frontend-first.</p>';
  }
  function searchPage() {
    const suggestions = [
      "Nhẫn",
      "Kim cương",
      "Vàng 18K",
      "Dây chuyền",
      "Bạc 925",
    ];

    content.innerHTML = `
    <section class="search-landing">

      <form class="search-main-form"
            action="products.html"
            method="get">

        <div class="search-main-input">

          <svg viewBox="0 0 24 24"
               fill="none"
               stroke="currentColor"
               stroke-width="1.5"
               aria-hidden="true">
            <circle cx="10.7" cy="10.7" r="6.6"/>
            <path d="m16 16 5 5"/>
          </svg>

          <input type="search"
                 name="q"
                 aria-label="Tìm kiếm trang sức"
                 placeholder="Tìm tên trang sức, chất liệu, đá quý..."
                 maxlength="100"
                 required>

          <button type="submit"
                  class="button button-dark">
            TÌM KIẾM
          </button>

        </div>

      </form>

      <div class="search-suggestions">

        <p>Gợi ý tìm kiếm</p>

        <div class="search-suggestion-list">
          ${suggestions
            .map(
              (word) => `
            <a href="products.html?q=${encodeURIComponent(word)}">
              ${esc(word)}
            </a>
          `,
            )
            .join("")}
        </div>

      </div>

      <section class="search-featured">

        <h2>Có thể bạn quan tâm</h2>

        <div id="search-featured-grid"
             class="catalog-grid">

          ${
            window.LUMIERE_PRODUCTS_ERROR
              ? '<div class="empty-panel">Chưa tải được sản phẩm.</div>'
              : P.slice(0, 4).map(card).join("") ||
                '<div class="empty-panel">Chưa có sản phẩm.</div>'
          }

        </div>

        <div class="search-view-all">
          <a class="button button-outline"
             href="products.html">
            XEM TẤT CẢ SẢN PHẨM →
          </a>
        </div>

      </section>

    </section>`;

    refreshCatalogFavorites();
  }

  function catalog() {
    if (window.LUMIERE_PRODUCTS_ERROR) {
      content.innerHTML = `
      <div class="empty-panel">
        Không thể tải sản phẩm. Vui lòng thử lại sau.
      </div>`;
      return;
    }

    function filterValues(field) {
      return [...new Set(P.map((p) => p[field]).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, "vi"),
      );
    }

    function filterOptions(field) {
      return filterValues(field)
        .map(
          (value) => `
        <option value="${esc(value)}">
          ${esc(value)}
        </option>
      `,
        )
        .join("");
    }

    content.innerHTML = `
    <div class="content-grid catalog-layout">

      <aside class="filter-panel catalog-filter">

        <div class="catalog-filter-head">
          <h2>Bộ lọc</h2>

          <button id="reset-filter"
                  class="catalog-reset"
                  type="button">
            Xóa tất cả
          </button>
        </div>

        <input id="keyword" type="hidden">


        <!-- DANH MỤC -->

        <details class="catalog-filter-group" open>

          <summary>Danh mục</summary>

          <div class="catalog-filter-body">

            <select id="category" hidden
                    aria-label="Danh mục">
              <option value="">Tất cả</option>
              ${filterOptions("category")}
            </select>

            <div class="catalog-category-list">

              ${["", ...filterValues("category")]
                .map(
                  (value) => `
                  <label class="catalog-category-option">

                    <input type="radio"
                           name="catalog-category"
                           value="${esc(value)}"
                           ${value === "" ? "checked" : ""}>

                    <span>
                      ${esc(value || "Tất cả")}
                    </span>

                  </label>
                `,
                )
                .join("")}

            </div>

          </div>

        </details>

        <!-- CHẤT LIỆU -->

        <details class="catalog-filter-group">

          <summary>Chất liệu</summary>

          <div class="catalog-filter-body">

            <select id="material"
                    aria-label="Chất liệu">
              <option value="">Tất cả chất liệu</option>
              ${filterOptions("material")}
            </select>

          </div>

        </details>

        <!-- ĐÁ QUÝ -->

        <details class="catalog-filter-group">

          <summary>Đá quý</summary>

          <div class="catalog-filter-body">

            <select id="gem"
                    aria-label="Đá quý">
              <option value="">Tất cả đá quý</option>
              ${filterOptions("gem")}
            </select>

          </div>

        </details>

        <!-- BỘ SƯU TẬP -->

      <details class="catalog-filter-group">

        <summary>Bộ sưu tập</summary>

        <div class="catalog-filter-body">

          <select id="collection"
                  hidden
                  aria-label="Bộ sưu tập">

            <option value="">Tất cả</option>

            ${filterOptions("collection")}

          </select>

          <div class="catalog-category-list">

            ${["", ...filterValues("collection")]
              .map(
                (value) => `
                <label class="catalog-category-option">

                  <input type="radio"
                        name="catalog-collection"
                        value="${esc(value)}"
                        ${value === "" ? "checked" : ""}>

                  <span>
                    ${esc(value || "Tất cả")}
                  </span>

                </label>
              `,
              )
              .join("")}

          </div>

        </div>

      </details>

        <!-- KHOẢNG GIÁ -->

        <details class="catalog-filter-group">

          <summary>Khoảng giá</summary>

          <div class="catalog-filter-body">

            <div class="field">
              <label for="min-price">Từ (₫)</label>
              <input id="min-price"
                     type="number"
                     min="0"
                     step="1"
                     placeholder="Không giới hạn">
            </div>

            <div class="field">
              <label for="max-price">Đến (₫)</label>
              <input id="max-price"
                     type="number"
                     min="0"
                     step="1"
                     placeholder="Không giới hạn">
            </div>

          </div>

        </details>

        <p id="filter-error"
           class="mini-note"
           role="status"
           hidden></p>

        <p class="catalog-filter-note">
          Hình ảnh sản phẩm mang tính minh họa.
        </p>

      </aside>

      <!-- DANH SÁCH SẢN PHẨM -->

      <section class="catalog-listing">

        <div class="toolbar catalog-toolbar">

          <span id="result-count"
                aria-live="polite"></span>

          <label class="catalog-sort">
            <span>Sắp xếp:</span>

            <select id="sort">
              <option value="default">Mặc định</option>
              <option value="asc">Giá thấp đến cao</option>
              <option value="desc">Giá cao đến thấp</option>
              <option value="name">Tên A–Z</option>
            </select>

          </label>

        </div>

        <div id="catalog-active-filters"
             class="catalog-active-filters"
             hidden></div>

        <div id="catalog-results"
             class="catalog-grid"></div>

        <div class="ap-pager catalog-pagination">

          <span id="catalog-page-info"></span>

          <div class="ap-page-actions">

            <button id="catalog-prev"
                    type="button">
              ← Trước
            </button>

            <button id="catalog-next"
                    type="button">
              Sau →
            </button>

          </div>

        </div>

      </section>

    </div>`;

    const params = new URLSearchParams(location.search);

    $("#keyword").value = params.get("q") || "";
    $("#category").value = params.get("category") || "";
    $("#collection").value = params.get("collection") || "";
    $("#material").value = params.get("material") || "";

    if (get("material")) {
      $("#material").closest("details").open = true;
    }

    if (get("collection")) {
      $("#collection").closest("details").open = true;
    }

    let currentPage = 1;
    const pageSize = 12;

    const fields = [
      "keyword",
      "category",
      "material",
      "collection",
      "gem",
      "min-price",
      "max-price",
    ];

    const fieldLabels = {
      keyword: "Tìm kiếm",
      category: "Danh mục",
      material: "Chất liệu",
      collection: "Bộ sưu tập",
      gem: "Đá quý",
      "min-price": "Giá từ",
      "max-price": "Giá đến",
    };

    function normalize(value) {
      return String(value ?? "")
        .toLocaleLowerCase("vi")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .trim();
    }

    function syncCategory() {
      ["category", "collection"].forEach((field) => {
        document
          .querySelectorAll(`input[name="catalog-${field}"]`)
          .forEach((input) => {
            input.checked = input.value === get(field);
          });
      });
    }

    function drawActiveFilters() {
      const active = fields.filter((id) => get(id) !== "");
      const container = $("#catalog-active-filters");

      container.hidden = active.length === 0;

      container.innerHTML = active
        .map((id) => {
          const value = get(id);

          const label = id.endsWith("-price") ? money(Number(value)) : value;

          return `
        <button type="button"
                class="catalog-filter-chip"
                data-clear-filter="${id}"
                aria-label="Xóa bộ lọc ${esc(fieldLabels[id])}">
          <span>
            ${esc(fieldLabels[id])}: ${esc(label)}
          </span>
          <span aria-hidden="true">×</span>
        </button>
      `;
        })
        .join("");
    }

    function draw() {
      const searchTerm = get("keyword");
      const selectedCollection = get("collection");
      const selectedCategory = get("category");
      const selectedMaterial = get("material");

      const heading = document.querySelector(".catalog-heading h1");

      const subtitle = document.querySelector(
        ".catalog-heading .page-subtitle",
      );

      const breadcrumb = document.querySelector(".catalog-breadcrumb");

      const headerSearch = document.querySelector(".header-search-input");

      let pageTitle = "Khám phá trang sức";
      let pageSubtitle = "Vẻ đẹp tinh tế, dấu ấn riêng của bạn.";
      let breadcrumbTitle = "";

      if (searchTerm) {
        pageTitle = `Kết quả cho “${searchTerm}”`;
        pageSubtitle = "Khám phá những thiết kế phù hợp với bạn.";
        breadcrumbTitle = "Kết quả tìm kiếm";
      } else if (selectedCollection) {
        pageTitle = `Bộ sưu tập ${selectedCollection}`;
        pageSubtitle = "Mỗi thiết kế, một dấu ấn riêng.";
        breadcrumbTitle = selectedCollection;
      } else if (selectedCategory) {
        pageTitle = selectedCategory;
        breadcrumbTitle = selectedCategory;
      } else if (selectedMaterial) {
        pageTitle = `Trang sức ${selectedMaterial}`;
        breadcrumbTitle = selectedMaterial;
      }

      if (heading) {
        heading.textContent = pageTitle;
      }

      if (subtitle) {
        subtitle.textContent = pageSubtitle;
      }

      if (breadcrumb) {
        breadcrumb.innerHTML = `
      <a href="${root}index.html">Trang chủ</a>
      <span aria-hidden="true">/</span>

      ${
        breadcrumbTitle
          ? `
        <a href="${root}pages/products.html">Sản phẩm</a>
        <span aria-hidden="true">/</span>
        <span aria-current="page">
          ${esc(breadcrumbTitle)}
        </span>
      `
          : `
        <span aria-current="page">Sản phẩm</span>
      `
      }
    `;
      }

      if (headerSearch && document.activeElement !== headerSearch) {
        headerSearch.value = searchTerm;
      }

      // Đồng bộ URL với bộ lọc hiện tại.
      const catalogUrl = new URL(location.href);

      [
        ["q", searchTerm],
        ["category", selectedCategory],
        ["collection", selectedCollection],
        ["material", selectedMaterial],
      ].forEach(([key, value]) => {
        if (value) {
          catalogUrl.searchParams.set(key, value);
        } else {
          catalogUrl.searchParams.delete(key);
        }
      });

      if (catalogUrl.href !== location.href) {
        history.replaceState(history.state, "", catalogUrl.href);
      }

      syncCategory();
      drawActiveFilters();

      const keyword = normalize(get("keyword"));
      const min = get("min-price");
      const max = get("max-price");
      const error = $("#filter-error");

      const invalidPrice =
        !$("#min-price").validity.valid ||
        !$("#max-price").validity.valid ||
        (min !== "" && max !== "" && Number(min) > Number(max));

      error.hidden = !invalidPrice;

      if (invalidPrice) {
        error.textContent = "Khoảng giá không hợp lệ.";

        $("#result-count").textContent = "";

        $("#catalog-results").innerHTML = `
        <div class="empty-panel">
          Vui lòng kiểm tra lại khoảng giá.
        </div>`;

        $("#catalog-page-info").textContent = "";
        $("#catalog-prev").disabled = true;
        $("#catalog-next").disabled = true;

        return;
      }

      let matches = P.filter((p) => {
        const searchable = normalize(
          `${p.name} ${p.category} ${p.material} ` +
            `${p.gem} ${p.brand} ${p.collection || ""} ${p.sku || ""}`,
        );

        return (
          searchable.includes(keyword) &&
          (!get("category") || p.category === get("category")) &&
          (!get("material") || p.material === get("material")) &&
          (!get("gem") || p.gem === get("gem")) &&
          (!get("collection") || p.collection === get("collection")) &&
          (min === "" || p.price >= Number(min)) &&
          (max === "" || p.price <= Number(max))
        );
      });

      if (get("sort") === "asc") {
        matches.sort((a, b) => a.price - b.price);
      }

      if (get("sort") === "desc") {
        matches.sort((a, b) => b.price - a.price);
      }

      if (get("sort") === "name") {
        matches.sort((a, b) => a.name.localeCompare(b.name, "vi"));
      }

      const totalPages = Math.max(1, Math.ceil(matches.length / pageSize));

      currentPage = Math.min(currentPage, totalPages);

      const start = (currentPage - 1) * pageSize;
      const slice = matches.slice(start, start + pageSize);

      $("#result-count").textContent = `${matches.length} sản phẩm`;

      $("#catalog-results").innerHTML = slice.length
        ? slice.map(card).join("")
        : `
        <div class="empty-panel">
          Không tìm thấy sản phẩm phù hợp.
        </div>`;

      $("#catalog-page-info").textContent = matches.length
        ? `Hiển thị ${start + 1}–${start + slice.length} / ${matches.length} · Trang ${currentPage}/${totalPages}`
        : "0 sản phẩm";

      $("#catalog-prev").disabled = currentPage === 1;

      $("#catalog-next").disabled = currentPage >= totalPages;
    }

    [...fields, "sort"].forEach((id) => {
      $("#" + id).addEventListener("input", () => {
        currentPage = 1;
        draw();
      });
    });

    document
      .querySelectorAll('input[name="catalog-category"]')
      .forEach((input) => {
        input.addEventListener("change", () => {
          $("#category").value = input.value;
          currentPage = 1;
          draw();
        });
      });

    document
      .querySelectorAll('input[name="catalog-collection"]')
      .forEach((input) => {
        input.addEventListener("change", () => {
          $("#collection").value = input.value;
          currentPage = 1;
          draw();
        });
      });

    $("#catalog-active-filters").addEventListener("click", (event) => {
      const button = event.target.closest("[data-clear-filter]");

      if (!button) return;

      const id = button.dataset.clearFilter;

      if (!fields.includes(id)) return;

      $("#" + id).value = "";

      currentPage = 1;
      draw();
    });

    $("#catalog-prev").onclick = () => {
      currentPage--;
      draw();
      window.scrollTo({ top: 0, behavior: "smooth" });
    };

    $("#catalog-next").onclick = () => {
      currentPage++;
      draw();
      window.scrollTo({ top: 0, behavior: "smooth" });
    };

    $("#reset-filter").onclick = () => {
      fields.forEach((id) => ($("#" + id).value = ""));

      $("#sort").value = "default";

      currentPage = 1;
      draw();
    };

    draw();
    refreshCatalogFavorites();
  }

  async function detail() {
    const p = product(new URLSearchParams(location.search).get("id"));
    if (!p) {
      content.innerHTML =
        '<div class="empty-panel">Không tìm thấy sản phẩm. <a class="inline-link" href="products.html">Quay lại danh sách</a></div>';
      return;
    }
    document.title = p.name + " | LUMIÈRE";
    content.innerHTML = `<div class="two-col"><div><img class="detail-photo" src="${esc(p.image)}" alt="Ảnh minh họa ${esc(p.category)}"><p class="mini-note">Hình ảnh mang tính chất minh họa.</p></div><section><div class="eyebrow">${esc(p.category)}</div><h2 class="product-title">${esc(p.name)}</h2><div class="price" style="font-size:28px">${money(p.price)}</div><p class="page-subtitle">Khám phá vẻ đẹp tinh tế trong từng chi tiết.</p><dl class="specs"><div><dt>Mã sản phẩm</dt><dd>${p.id}</dd></div><div><dt>Thương hiệu</dt><dd>${esc(p.brand)}</dd></div><div><dt>Chất liệu</dt><dd>${esc(p.material)}</dd></div><div><dt>Đá quý</dt><dd>${esc(p.gem)}</dd></div><div><dt>Bộ sưu tập</dt><dd>${esc(p.collection)}</dd></div><div><dt>Số lượng còn lại</dt><dd>${p.stock}</dd></div></dl><label for="qty">Số lượng</label><div class="qty-line"><button id="qty-minus">−</button><input id="qty" type="number" min="1" max="${p.stock}" value="1"><button id="qty-plus">+</button></div><div class="detail-purchase-actions">

  <button id="detail-buy"
          type="button"
          class="button button-dark"
          ${p.stock <= 0 ? "disabled" : ""}>
    MUA NGAY
  </button>

  <div class="detail-secondary-actions">

    <button id="detail-add"
            type="button"
            class="button button-outline"
            ${p.stock <= 0 ? "disabled" : ""}>
      THÊM VÀO GIỎ HÀNG
    </button>

    <button id="detail-fav"
            type="button"
            class="button button-outline"
            title="Thêm vào yêu thích"
            aria-label="Thêm vào yêu thích">

      <svg viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.5"
           stroke-linecap="round"
           stroke-linejoin="round"
           aria-hidden="true">
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>
      </svg>

    </button>

  </div>
</div></section></div><hr class="section-divider"><h2 class="reco-title">Có thể bạn sẽ thích</h2><p class="mini-note">Gợi ý các sản phẩm có đặc điểm tương tự. Giá và tồn kho được kiểm tra từ dữ liệu bán hàng hiện tại.</p><div id="ai-reco-status" class="mini-note">Đang tải sản phẩm gợi ý…</div><div id="ai-reco-grid" class="catalog-grid"></div>`;
    $("#qty-minus").onclick = () =>
      ($("#qty").value = Math.max(1, Number($("#qty").value || 1) - 1));
    $("#qty-plus").onclick = () =>
      ($("#qty").value = Math.min(p.stock, Number($("#qty").value || 1) + 1));
    $("#detail-add").onclick = () => {
      const q = Number($("#qty").value);
      if (!Number.isInteger(q) || q < 1 || q > p.stock)
        return notify("Số lượng không hợp lệ", true);
      add(p.id, q);
    };
    $("#detail-fav").onclick = () => favorite(p.id);
    $("#detail-buy").onclick = async () => {
      if (!user) {
        notify("Vui lòng đăng nhập để mua hàng.", true);
        location.href = root + "pages/login.html";
        return;
      }

      if (user.role !== "customer") {
        notify("Vui lòng sử dụng tài khoản khách hàng.", true);
        return;
      }

      if (cartBusy) return;

      const quantity = Number($("#qty").value);

      if (!Number.isInteger(quantity) || quantity < 1 || quantity > p.stock) {
        notify("Số lượng không hợp lệ.", true);
        return;
      }

      const buyButton = $("#detail-buy");
      const addButton = $("#detail-add");

      cartBusy = true;
      buyButton.disabled = true;
      addButton.disabled = true;
      buyButton.textContent = "ĐANG XỬ LÝ...";

      try {
        cartData = await LUMIERE_API.addCartItem(Number(p.id), quantity);

        location.href = root + "pages/checkout.html";
      } catch (error) {
        notify(error.message || "Không thể thêm sản phẩm.", true);
      } finally {
        cartBusy = false;
        buyButton.disabled = p.stock <= 0;
        addButton.disabled = p.stock <= 0;
        buyButton.textContent = "MUA NGAY";
      }
    };
    const status = $("#ai-reco-status");
    const grid = $("#ai-reco-grid");
    const customerId = user?.customer_id || "GUEST";
    if (!window.LUMIERE_AI_BASE) {
      status.textContent =
        "AI Service chưa được cấu hình; bạn vẫn có thể mua sắm.";
      return;
    }
    const url = new URL(
      window.LUMIERE_AI_BASE.replace(/\/$/, "") + "/recommendations/v2",
    );
    url.searchParams.set("customer_id", customerId);
    url.searchParams.set("product_id", String(p.id));
    url.searchParams.set("number", "4");
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(45000) });
      if (!response.ok) throw Error("HTTP " + response.status);
      const payload = await response.json();
      if (!payload.success || !Array.isArray(payload.data))
        throw Error("Phản hồi không hợp lệ");
      const recommended = payload.data
        .map((x) => product(x.ProductID))
        .filter((x) => x && x.id !== p.id);
      status.textContent = recommended.length
        ? ""
        : "Hiện chưa có sản phẩm gợi ý phù hợp.";
      grid.innerHTML = recommended.map(card).join("");
    } catch (error) {
      status.textContent =
        "Chưa tải được sản phẩm gợi ý. Vui lòng thử lại sau. (" +
        error.message +
        "). Bạn vẫn có thể xem và mua sắm danh mục.";
    }
  }

  function cartPage() {
    const count = cartLines().length;

    content.innerHTML = `
    <div class="content-grid cart-layout">
      <section class="cart-items-panel">
        <div class="cart-heading">
          <h2>Sản phẩm trong giỏ</h2>
          <span>${count} mẫu trang sức</span>
        </div>

        ${
          count
            ? itemsHtml()
            : `
          <div class="empty-panel">
            Giỏ hàng của bạn đang trống.
          </div>
        `
        }

        <a class="button button-outline cart-continue"
           href="products.html">
          ← Tiếp tục mua sắm
        </a>
      </section>

      <aside class="summary-card">
        <h2>Tóm tắt đơn hàng</h2>

        <div class="summary-line">
          <span>Tạm tính</span>
          <strong>${money(subtotal())}</strong>
        </div>

        <div class="summary-line">
          <span>Phí vận chuyển dự kiến</span>
          <strong>${money(shipping())}</strong>
        </div>

        <div class="summary-line total">
          <span>Tổng cộng</span>
          <strong class="price">
            ${money(subtotal() + shipping())}
          </strong>
        </div>

        <p class="mini-note">
          Tổng tiền chính thức được xác nhận khi đặt hàng.
        </p>

        ${
          count
            ? `
          <a class="button button-dark button-wide"
             href="checkout.html">
            TIẾN HÀNH THANH TOÁN →
          </a>
        `
            : `
          <button class="button button-dark button-wide"
                  disabled>
            TIẾN HÀNH THANH TOÁN
          </button>
        `
        }
      </aside>
    </div>`;
  }
  function checkout() {
    if (!cartLines().length) {
      content.innerHTML =
        '<div class="empty-panel">Giỏ hàng trống. <a class="inline-link" href="products.html">Mua sắm ngay</a></div>';
      return;
    }
    content.innerHTML = `<div class="two-col"><div class="panel"><h2>Thông tin người nhận</h2>${errorBox}<form id="checkout-form">${formField("recipient", "Họ và tên", "text", 'required autocomplete="name"')}${formField("phone", "Số điện thoại", "tel", 'required pattern="0[0-9]{9}"')}${formField("address", "Địa chỉ nhận hàng", "text", "required")}${formField("province", "Tỉnh / thành phố", "text", "required")}<div class="field"><label for="payment">Phương thức thanh toán</label><select id="payment"><option value="cod">Thanh toán khi nhận hàng (COD)</option><option value="bank">Chuyển khoản (mô phỏng, chưa xử lý)</option></select></div><div class="field"><label for="note">Ghi chú</label><textarea id="note" maxlength="500"></textarea></div>${requireAuthMessage()}<button class="button button-dark button-wide">KIỂM TRA ĐƠN HÀNG</button></form></div><aside class="summary-card"><h2>Đơn hàng tạm tính</h2>${cartLines()
      .map(
        ({ p, qty }) =>
          `<div class="summary-line"><span>${esc(p.name)} × ${qty}</span><strong>${money(p.price * qty)}</strong></div>`,
      )
      .join(
        "",
      )}<div class="summary-line"><span>Vận chuyển</span><span>${money(shipping())}</span></div><div class="summary-line total"><span>Tổng</span><strong>${money(subtotal() + shipping())}</strong></div><p class="mini-note">Bản frontend-first không tạo đơn giả. Khi có API POST /orders, backend phải đọc giá/tồn kho từ PostgreSQL và tạo đơn trong transaction.</p></aside></div>`;
    const bankOption = document.querySelector('#payment option[value="bank"]');
    if (bankOption) bankOption.remove();
    const noteField = document.querySelector("#note");
    if (noteField) noteField.closest(".field")?.remove();
    content.querySelectorAll(".demo-note,.mini-note").forEach((el) => {
      if (el.textContent.includes("frontend-first")) {
        el.textContent = user
          ? "Don hang se duoc ghi nhan vao PostgreSQL khi xac nhan."
          : "Vui long dang nhap truoc khi dat hang.";
      }
    });
    $("#checkout-form").onsubmit = async (e) => {
      e.preventDefault();
      if (!user) {
        alert(
          "Vui l\u00f2ng \u0111\u0103ng nh\u1eadp \u0111\u1ec3 \u0111\u1eb7t h\u00e0ng",
        );
        return;
      }
      if (get("payment") !== "cod") {
        alert(
          "Ph\u01b0\u01a1ng th\u1ee9c thanh to\u00e1n ch\u01b0a \u0111\u01b0\u1ee3c h\u1ed7 tr\u1ee3",
        );
        return;
      }
      const button = $(
        '#checkout-form button[type="submit"], #checkout-form button',
      );
      if (button.disabled) return;
      button.disabled = true;
      try {
        const order = await LUMIERE_API.createOrder({
          recipient_name: get("recipient"),
          phone: get("phone"),
          address: get("address") + ", " + get("province"),
          payment_method: "cod",
        });
        cartData = {
          items: [],
          total_quantity: 0,
          subtotal_vnd: "0.00",
        };
        content.innerHTML = `
        <section class="panel">
          <h2>&#272;&#7863;t h&#224;ng th&#224;nh c&#244;ng!</h2>
          <p>M&#227; &#273;&#417;n h&#224;ng:
            <strong>${esc(order.code)}</strong>
          </p>
          <p>T&#7893;ng ti&#7873;n:
            <strong>${money(order.total_vnd)}</strong>
          </p>
          <p>Tr&#7841;ng th&#225;i &#273;&#417;n:
            <strong>${esc(order.status)}</strong>
          </p>
          <p>Thanh to&#225;n:
            <strong>${esc(order.payment_status)}</strong>
          </p>
          <p>Ph&#432;&#417;ng th&#7913;c: COD</p>
          <a class="button button-dark"
             href="orders.html">
            Xem &#273;&#417;n h&#224;ng
          </a>
        </section>
      `;
      } catch (error) {
        alert(error.message);
        button.disabled = false;
        notify(
          "Neu ket noi bi gian doan, hay kiem tra don hang truoc khi thu lai.",
          true,
        );
      }
    };
  }

  function auth(which) {
    const reg = which === "register",
      forgot = which === "forgot-password";
    content.innerHTML = `<section class="auth-page"><div class="auth-photo"><div><div class="eyebrow">LUMIÈRE FINE JEWELRY</div><h2>Vẻ đẹp mang<br>dấu ấn riêng</h2><p>Tinh tế trong từng khoảnh khắc</p></div></div><div class="auth-form"><div class="eyebrow">MY LUMIÈRE</div><h2>${forgot ? "Quên mật khẩu" : reg ? "Tạo tài khoản" : "Đăng nhập"}</h2><p class="page-subtitle">${forgot ? "Nhập địa chỉ email đã đăng ký để khôi phục tài khoản." : reg ? "Khám phá những đặc quyền dành riêng cho bạn" : "Chào mừng bạn trở lại."}</p>${errorBox}${forgot ? '<p class="demo-note">Chưa có API quên mật khẩu. Backend cần triển khai token một lần có thời hạn, gửi qua email. Không hiển thị thông tin tài khoản có tồn tại hay không.</p>' + formField("email", "Email", "email", "required") + '<button class="button button-dark button-wide" id="forgot-demo">GỬI YÊU CẦU (CHƯA KÍCH HOẠT)</button>' : `<form id="auth-form">${reg ? formField("full_name", "Họ tên", "text", 'minlength="2" maxlength="150" required autocomplete="name"') + formField("phone", "Số điện thoại", "tel", 'pattern="0[0-9]{9}" autocomplete="tel"') : ""}${formField("email", "Email", "email", 'required autocomplete="example@gmail.com"')}${formField("password", "Mật khẩu", "password", `${reg ? 'minlength="8" maxlength="128" autocomplete="new-password"' : 'autocomplete="current-password"'} required`)}${reg ? formField("confirm", "Nhập lại mật khẩu", "password", 'minlength="8" required autocomplete="new-password"') : ""}<label class="mini-note"><input id="show-password" type="checkbox"> Hiện mật khẩu</label><button id="auth-submit" class="button button-dark button-wide">${reg ? "ĐĂNG KÝ" : "ĐĂNG NHẬP"}</button></form>`}<p class="mini-note">${reg ? 'Đã có tài khoản? <a class="inline-link" href="login.html">Đăng nhập</a>' : 'Chưa có tài khoản? <a class="inline-link" href="register.html">Đăng ký</a>'}</p>${!reg && !forgot ? '<p><a class="inline-link" href="forgot-password.html">Quên mật khẩu?</a></p>' : ""}</div></section>`;
    if (forgot) {
      $("#forgot-demo").onclick = () =>
        demo("Yêu cầu khôi phục chưa có backend.");
      return;
    }
    $("#show-password").onchange = (e) =>
      ["password", "confirm"].forEach((id) => {
        const el = $("#" + id);
        if (el) el.type = e.target.checked ? "text" : "password";
      });
    $("#auth-form").onsubmit = async (e) => {
      e.preventDefault();
      const btn = $("#auth-submit");
      btn.disabled = true;
      try {
        if (reg) {
          if ($("#password").value !== $("#confirm").value)
            throw Error("Mật khẩu xác nhận không khớp");
          await LUMIERE_API.register({
            full_name: get("full_name"),
            phone: get("phone") || null,
            email: get("email"),
            password: $("#password").value,
          });
          alert("Đăng ký thành công! Đang chuyển sang đăng nhập.", "success");
          setTimeout(() => (location.href = "login.html"), 850);
        } else {
          await LUMIERE_API.login(get("email"), $("#password").value);
          alert("Đăng nhập thành công!", "success");

          const signedIn = await LUMIERE_API.me();

          if (signedIn.role === "customer") {
            sessionStorage.setItem("lumiere_login_success", "1");
            location.href = "../index.html";
          } else {
            location.href =
              signedIn.role === "admin"
                ? "admin/dashboard.html"
                : "staff/orders.html";
          }
        }
      } catch (err) {
        alert(err.message);
      } finally {
        btn.disabled = false;
      }
    };
  }
  function account() {
    if (!user) {
      content.innerHTML =
        '<div class="empty-panel">Bạn chưa đăng nhập. <a class="inline-link" href="login.html">Đăng nhập</a></div>';
      return;
    }
    content.innerHTML = `<div class="two-col"><div class="panel"><h2>Thông tin tài khoản</h2><dl class="specs"><div><dt>Họ tên</dt><dd>${esc(user.full_name)}</dd></div><div><dt>Email</dt><dd>${esc(user.email)}</dd></div><div><dt>Vai trò</dt><dd>${esc(user.role)}</dd></div></dl><p class="demo-note">Chỉnh sửa hồ sơ, địa chỉ và đổi mật khẩu sẽ được kết nối API sau.</p></div><div class="panel"><h2>Truy cập nhanh</h2><p>${nav("Đơn hàng của tôi", "pages/orders.html")}</p><p>${nav("Danh sách yêu thích", "pages/wishlist.html")}</p><p>${nav("Đánh giá của tôi", "pages/reviews.html")}</p><button class="button button-outline" id="logout-main">ĐĂNG XUẤT</button></div></div>`;
    $("#logout-main").onclick = logout;
  }

  async function orders() {
    const statusLabels = {
      pending: "Chờ xác nhận",
      confirmed: "Đã xác nhận",
      packing: "Đang đóng gói",
      shipping: "Đang giao",
      delivered: "Đã giao",
      cancelled: "Đã hủy",
    };

    const paymentLabels = {
      unpaid: "Chưa thanh toán",
      paid: "Đã thanh toán",
      pending: "Chờ thanh toán",
      failed: "Thanh toán thất bại",
      refunded: "Đã hoàn tiền",
    };

    const methodLabels = {
      cod: "COD",
      vnpay: "VNPAY",
    };

    const steps = [
      ["pending", "Chờ xác nhận"],
      ["confirmed", "Xác nhận"],
      ["packing", "Đóng gói"],
      ["shipping", "Đang giao"],
      ["delivered", "Đã giao"],
    ];

    const statusBadge = (status) => `
    <span class="customer-order-status"
          data-status="${esc(status)}">
      ${esc(statusLabels[status] || status)}
    </span>`;

    const paymentText = (status) => esc(paymentLabels[status] || status);

    const methodText = (method) => esc(methodLabels[method] || method);

    const dateText = (value) => new Date(value).toLocaleString("vi-VN");

    if (!user) {
      content.innerHTML = `
      <section class="customer-orders-empty">
        <h2>Đơn hàng của bạn</h2>
        <p>Đăng nhập để xem và theo dõi đơn hàng.</p>
        <a class="button button-dark" href="login.html">
          ĐĂNG NHẬP
        </a>
      </section>`;
      return;
    }

    content.innerHTML = `
    <div class="empty-panel">
      Đang tải đơn hàng…
    </div>`;

    try {
      /* CHI TIẾT ĐƠN HÀNG */

      if (page === "order-detail") {
        const id = Number(new URLSearchParams(location.search).get("id"));

        if (!Number.isInteger(id) || id <= 0) {
          throw new Error("Mã đơn hàng không hợp lệ.");
        }

        const order = await LUMIERE_API.request("/orders/" + id);

        const activeStep = steps.findIndex(([key]) => key === order.status);

        const timeline =
          order.status === "cancelled"
            ? `<div class="customer-order-cancelled">
             Đơn hàng này đã được hủy.
           </div>`
            : activeStep >= 0
              ? `<div class="customer-order-timeline">
              ${steps
                .map(
                  ([key, label], index) => `
                <div class="customer-order-step ${index <= activeStep ? "is-done" : ""} ${index === activeStep ? "is-current" : ""}">
                  <span class="customer-step-dot">
                    ${index < activeStep ? "✓" : index + 1}
                  </span>
                  <small>${label}</small>
                </div>
              `,
                )
                .join("")}
            </div>`
              : "";

        const rows = (order.items || [])
          .map(
            (item) => `
        <tr>
          <td>
            <strong>${esc(item.product_name)}</strong>
            <small class="customer-order-sku">
              ${esc(item.sku)}
            </small>
          </td>
          <td>${Number(item.quantity)}</td>
          <td>${money(item.unit_price_vnd)}</td>
          <td>${money(item.line_total_vnd)}</td>
        </tr>
      `,
          )
          .join("");

        content.innerHTML = `
        <div class="customer-order-detail">

          <a class="inline-link customer-order-back"
             href="orders.html">
            ← Quay lại đơn hàng của tôi
          </a>

          <section class="panel customer-order-overview">
            <div class="customer-order-head">
              <div>
                <h2>Đơn hàng ${esc(order.code)}</h2>
                <p>Ngày đặt: ${dateText(order.created_at)}</p>
              </div>

              ${statusBadge(order.status)}
            </div>

            ${timeline}
          </section>

          <div class="customer-order-info-grid">

            <section class="panel">
              <h2>Thông tin nhận hàng</h2>

              <div class="customer-order-field">
                <span>Người nhận</span>
                <strong>${esc(order.recipient_name)}</strong>
              </div>

              <div class="customer-order-field">
                <span>Số điện thoại</span>
                <strong>${esc(order.phone)}</strong>
              </div>

              <div class="customer-order-field">
                <span>Địa chỉ giao hàng</span>
                <strong>${esc(order.address)}</strong>
              </div>
            </section>

            <section class="panel">
              <h2>Thông tin thanh toán</h2>

              <div class="customer-order-field">
                <span>Phương thức thanh toán</span>
                <strong>${methodText(order.payment_method)}</strong>
              </div>

              <div class="customer-order-field">
                <span>Trạng thái thanh toán</span>
                <strong>${paymentText(order.payment_status)}</strong>
              </div>

              <div class="customer-order-field">
                <span>Tổng tiền</span>
                <strong class="customer-order-price">
                  ${money(order.total_vnd)}
                </strong>
              </div>
            </section>

          </div>

          <section class="panel customer-order-items">

            <h2>Sản phẩm đã đặt</h2>

            <div class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Sản phẩm</th>
                    <th>Số lượng</th>
                    <th>Đơn giá</th>
                    <th>Thành tiền</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            </div>

            <div class="customer-order-summary">

              <div class="summary-line">
                <span>Tạm tính</span>
                <strong>${money(order.subtotal_vnd)}</strong>
              </div>

              <div class="summary-line">
                <span>Phí vận chuyển</span>
                <strong>${money(order.shipping_vnd)}</strong>
              </div>

              <div class="summary-line">
                <span>Giảm giá</span>
                <strong>−${money(order.discount_vnd)}</strong>
              </div>

              <div class="summary-line customer-order-grandtotal">
                <span>Tổng thanh toán</span>
                <strong>${money(order.total_vnd)}</strong>
              </div>

            </div>
          </section>

        </div>`;

        return;
      }

      /* DANH SÁCH ĐƠN HÀNG */

      const params = new URLSearchParams(location.search);
      const requestedPage = Number(params.get("page") || 1);

      const currentPage =
        Number.isInteger(requestedPage) && requestedPage > 0
          ? requestedPage
          : 1;

      const result = await LUMIERE_API.request(
        "/orders/my?page=" + currentPage + "&page_size=20",
      );

      if (!Array.isArray(result.items)) {
        throw new Error("Không tải được danh sách đơn hàng.");
      }

      const total = Number(result.total || 0);
      const totalPages = Math.max(1, Math.ceil(total / 20));

      const cards = result.items
        .map(
          (order) => `
      <article class="panel customer-order-card">

        <div class="customer-order-head">

          <div>
            <h3>${esc(order.code)}</h3>
            <p>Ngày đặt: ${dateText(order.created_at)}</p>
          </div>

          ${statusBadge(order.status)}

        </div>

        <div class="customer-order-card-body">

          <div class="customer-order-field">
            <span>Thanh toán</span>
            <strong>${paymentText(order.payment_status)}</strong>
          </div>

          <div class="customer-order-field">
            <span>Phương thức</span>
            <strong>${methodText(order.payment_method)}</strong>
          </div>

          <div class="customer-order-field">
            <span>Tổng tiền</span>
            <strong class="customer-order-price">
              ${money(order.total_vnd)}
            </strong>
          </div>

        </div>

        <div class="customer-order-card-actions">
          <a class="button button-outline"
             href="order-detail.html?id=${Number(order.id)}">
            XEM CHI TIẾT →
          </a>
        </div>

      </article>
    `,
        )
        .join("");

      content.innerHTML = `
      <section class="customer-orders">

        <div class="customer-orders-toolbar">
          <span>${total} đơn hàng</span>

          <a class="inline-link" href="products.html">
            Tiếp tục mua sắm →
          </a>
        </div>

        ${
          result.items.length
            ? `
          <div class="customer-orders-list">
            ${cards}
          </div>
        `
            : `
          <section class="customer-orders-empty">
            <div class="customer-orders-empty-icon">♧</div>

            <h2>${total === 0 ? "Bạn chưa có đơn hàng" : "Không có đơn hàng ở trang này"}</h2>

            <p>
              ${total === 0 ? "Khám phá những thiết kế trang sức dành riêng cho phong cách của bạn." : "Bạn có thể quay lại danh sách đơn hàng."}
            </p>

            <a class="button button-dark"
               href="${total === 0 ? "products.html" : "orders.html"}">
              ${total === 0 ? "KHÁM PHÁ SẢN PHẨM" : "QUAY LẠI DANH SÁCH"}
            </a>
          </section>
        `
        }

        ${
          totalPages > 1
            ? `
          <div class="customer-orders-pagination">

            ${
              currentPage > 1
                ? `
              <a class="button button-outline"
                 href="orders.html?page=${currentPage - 1}">
                ← Trước
              </a>
            `
                : ""
            }

            <span>Trang ${currentPage} / ${totalPages}</span>

            ${
              currentPage < totalPages
                ? `
              <a class="button button-outline"
                 href="orders.html?page=${currentPage + 1}">
                Tiếp →
              </a>
            `
                : ""
            }

          </div>
        `
            : ""
        }

      </section>`;
    } catch (error) {
      content.innerHTML = `
      <section class="customer-orders-empty">
        <h2>Chưa tải được đơn hàng</h2>
        <p>${esc(error.message)}</p>
        <button id="orders-retry"
                class="button button-outline"
                type="button">
          Thử lại
        </button>
      </section>`;

      $("#orders-retry").onclick = () => orders();
      console.error("Orders API:", error);
    }
  }

  function wishlist() {
    const list = favorites().map(product).filter(Boolean);
    content.innerHTML = `<p class="mini-note">Yêu thích đang lưu trên trình duyệt, chưa đồng bộ theo tài khoản.</p><div class="catalog-grid">${list.length ? list.map(card).join("") : '<div class="empty-panel">Chưa có sản phẩm yêu thích.</div>'}</div>`;
  }
  function staticPage() {
    const copy = {
      about:
        "LUMIÈRE kết hợp thương mại điện tử trang sức với hệ thống gợi ý và tư vấn sử dụng trí tuệ nhân tạo. Giao diện là nguyên mẫu phục vụ khóa luận tốt nghiệp.",
      contact:
        "Liên hệ với đội ngũ LUMIÈRE để trao đổi thông tin mua sắm và hỗ trợ. Kênh liên lạc thực tế sẽ cấu hình khi triển khai.",
      collections:
        "Khám phá các thiết kế nhẫn, dây chuyền, bông tai và vòng tay theo phong cách riêng.",
      reviews:
        "Đánh giá chỉ được tạo sau khi đơn hàng hoàn tất. Backend phải xác nhận sản phẩm đã mua và chống đánh giá lặp.",
    };
    content.innerHTML = `<div class="panel"><h2>${page === "contact" ? "Liên hệ" : "LUMIÈRE Jewelry"}</h2><p class="page-subtitle">${copy[page] || ""}</p>${
      page === "collections"
        ? '<div class="catalog-grid">' +
          P.filter((p, i) => i < 4)
            .map(card)
            .join("") +
          "</div>"
        : page === "contact"
          ? errorBox +
            '<form id="contact-form">' +
            formField("name", "Họ tên", "text", "required") +
            formField("email", "Email", "email", "required") +
            '<div class="field"><label>Lời nhắn</label><textarea id="message" required maxlength="1500"></textarea></div><button class="button button-dark">GỬI LIÊN HỆ (DEMO)</button></form>'
          : page === "reviews"
            ? '<p class="demo-note">Chưa có API đánh giá. Yêu cầu backend: POST /products/{id}/reviews, GET /reviews/me.</p>'
            : ""
    }</div>`;
    if (page === "contact")
      $("#contact-form").onsubmit = (e) => {
        e.preventDefault();
        alert(
          "Chưa kết nối API liên hệ. Không có thông tin nào được gửi.",
          "success",
        );
      };
  }
  function adminPage() {
    const section = page.slice(6),
      names = {
        dashboard: "Dashboard",
        products: "Sản phẩm",
        categories: "Danh mục",
        brands: "Thương hiệu",
        orders: "Đơn hàng",
        customers: "Khách hàng",
        coupons: "Mã giảm giá",
        staff: "Nhân viên",
        analytics: "Phân tích hành vi",
        inventory: "Tồn kho",
      };
    const sidebar = `<nav class="admin-side">${Object.entries(names)
      .map(
        ([key, label]) =>
          `<a class="${key === section ? "active" : ""}" href="${key}.html">${label}</a>`,
      )
      .join("")}<a href="../../index.html">← Trở về cửa hàng</a></nav>`;
    if (
      section === "dashboard" &&
      typeof window.LUMIERE_ADMIN_DASHBOARD === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="dashboard-mount"></div></div>`;
      window.LUMIERE_ADMIN_DASHBOARD({
        mount: $("#dashboard-mount"),
        products: P,
        money,
        esc,
      });
      return;
    }
    if (
      (section === "categories" || section === "brands") &&
      typeof window.LUMIERE_ADMIN_TAXONOMY === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="taxonomy-mount"></div></div>`;
      window.LUMIERE_ADMIN_TAXONOMY({
        mount: $("#taxonomy-mount"),
        kind: section,
        products: P,
        esc,
      });
      return;
    }
    if (
      section === "analytics" &&
      typeof window.LUMIERE_ADMIN_ANALYTICS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="analytics-mount"></div></div>`;
      window.LUMIERE_ADMIN_ANALYTICS({
        mount: $("#analytics-mount"),
        products: P,
      });
      return;
    }
    if (
      section === "inventory" &&
      typeof window.LUMIERE_ADMIN_INVENTORY === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="inventory-mount"></div></div>`;
      window.LUMIERE_ADMIN_INVENTORY({
        mount: $("#inventory-mount"),
        products: P,
      });
      return;
    }
    if (
      section === "coupons" &&
      typeof window.LUMIERE_ADMIN_COUPONS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="coupons-mount"></div></div>`;
      window.LUMIERE_ADMIN_COUPONS({ mount: $("#coupons-mount") });
      return;
    }
    if (
      section === "staff" &&
      typeof window.LUMIERE_ADMIN_STAFF === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="staff-admin-mount"></div></div>`;
      window.LUMIERE_ADMIN_STAFF({ mount: $("#staff-admin-mount") });
      return;
    }
    if (
      section === "customers" &&
      typeof window.LUMIERE_ADMIN_CUSTOMERS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="customers-mount"></div></div>`;
      window.LUMIERE_ADMIN_CUSTOMERS({ mount: $("#customers-mount") });
      return;
    }
    if (
      section === "orders" &&
      typeof window.LUMIERE_ADMIN_ORDERS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="orders-mount"></div></div>`;
      window.LUMIERE_ADMIN_ORDERS({ mount: $("#orders-mount") });
      return;
    }
    if (
      section === "products" &&
      typeof window.LUMIERE_ADMIN_PRODUCTS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout">${sidebar}<div id="ap-mount"></div></div>`;
      window.LUMIERE_ADMIN_PRODUCTS({
        mount: $("#ap-mount"),
        products: P,
        money,
        esc,
        authorized: !!(user && user.role === "admin"),
      });
      return;
    }
    let body = "";
    if (section === "dashboard" || section === "analytics") {
      body = `<div class="dashboard-grid"><div class="stat"><span>Sản phẩm demo</span><strong>${P.length}</strong></div><div class="stat"><span>Danh mục</span><strong>${new Set(P.map((p) => p.category)).size}</strong></div><div class="stat"><span>Đơn hàng (chưa API)</span><strong>—</strong></div><div class="stat"><span>Doanh thu (chưa API)</span><strong>—</strong></div></div><div class="panel"><h2>${section === "analytics" ? "Phân tích hành vi khách hàng" : "Tổng quan"}</h2><p class="page-subtitle">Các biểu đồ và số liệu doanh thu phải lấy từ backend, không được tự tạo số liệu giao dịch giả. Backend cần hỗ trợ event: product_view, search, add_to_cart, favorite, purchase và bảng tổng hợp theo ngày.</p></div>`;
    } else if (section === "products" || section === "inventory") {
      body = `<div class="panel"><div class="toolbar"><h2>${names[section]}</h2><button class="button button-outline" data-demo="create-product">+ Thêm mới (demo)</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Hình</th><th>ID</th><th>Tên</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Thao tác</th></tr></thead><tbody>${P.map((p) => `<tr><td><img src="${esc(p.image)}" alt=""></td><td>${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td><td>${money(p.price)}</td><td>${p.stock}</td><td><button class="button-sm" data-demo="edit">Sửa</button></td></tr>`).join("")}</tbody></table></div></div>`;
    } else {
      const data =
        section === "categories"
          ? [...new Set(P.map((p) => p.category))]
          : section === "brands"
            ? ["SJC", "PNJ", "LUMIÈRE (đề xuất)"]
            : [];
      body = `<div class="panel"><div class="toolbar"><h2>${names[section]}</h2><button class="button button-outline" data-demo="new">+ Thêm mới (demo)</button></div>${data.length ? '<div class="table-wrap"><table class="data-table"><thead><tr><th>STT</th><th>Tên</th><th>Thao tác</th></tr></thead><tbody>' + data.map((name, i) => `<tr><td>${i + 1}</td><td>${esc(name)}</td><td><button class="button-sm" data-demo="edit">Sửa</button></td></tr>`).join("") + "</tbody></table></div>" : '<div class="empty-panel">Chưa có dữ liệu nghiệp vụ từ PostgreSQL.</div>'}<p class="demo-note">Trang quản trị đã có giao diện, nhưng thêm/sửa/xóa và thống kê cần API có xác thực role admin.</p></div>`;
    }
    const gate =
      user && user.role === "admin"
        ? ""
        : '<div class="demo-note">CHẾ ĐỘ XEM TRƯỚC GIAO DIỆN ADMIN. Chưa được cấp quyền quản trị; mọi thao tác quản trị bị vô hiệu. Backend phải chặn API bằng role admin.</div>';
    content.innerHTML = `<div class="admin-layout">${sidebar}<div>${gate}${body}</div></div>`;
  }
  function staffPage() {
    const kind = page.slice(6);
    if (
      kind === "inventory" &&
      typeof window.LUMIERE_STAFF_INVENTORY === "function"
    ) {
      content.innerHTML = `<div class="admin-layout"><nav class="admin-side"><a href="orders.html">Xử lý đơn</a><a class="active" href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div id="staff-inventory-mount"></div></div>`;
      window.LUMIERE_STAFF_INVENTORY({
        mount: document.querySelector("#staff-inventory-mount"),
        products: P,
      });
      return;
    }
    if (
      kind === "orders" &&
      typeof window.LUMIERE_STAFF_ORDERS === "function"
    ) {
      content.innerHTML = `<div class="admin-layout"><nav class="admin-side"><a class="active" href="orders.html">Xử lý đơn</a><a href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div id="staff-orders-mount"></div></div>`;
      window.LUMIERE_STAFF_ORDERS({
        mount: document.querySelector("#staff-orders-mount"),
      });
      return;
    }
    content.innerHTML = `<div class="admin-layout"><nav class="admin-side"><a href="orders.html">Xử lý đơn</a><a href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div class="panel"><h2>${kind === "orders" ? "Đơn hàng cần xử lý" : "Kiểm tra tồn kho"}</h2><p class="demo-note">GIAO DIỆN DEMO. Backend phải yêu cầu role staff hoặc admin trước khi truy xuất dữ liệu nghiệp vụ.</p>${kind === "inventory" ? '<div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>Tồn kho demo</th></tr></thead><tbody>' + P.map((p) => `<tr><td>${esc(p.name)}</td><td>${p.stock}</td></tr>`).join("") + "</tbody></table></div>" : '<div class="empty-panel">Chưa có đơn hàng thực để xử lý.</div>'}</div></div>`;
  }
  function adminPage() {
    window.LUMIERE_BACKEND_CONSOLE({
      mount: content,
      section: page.slice(6),
      role: "admin",
    });
  }
  function staffPage() {
    window.LUMIERE_BACKEND_CONSOLE({
      mount: content,
      section: page.slice(6),
      role: "staff",
    });
  }
  function favorite(id) {
    if (!user || user.role !== "customer") {
      notify(
        "Đăng nhập bằng tài khoản khách hàng để dùng danh sách yêu thích.",
        true,
      );
      return;
    }
    const productId = Number(id);
    LUMIERE_API.wishlist()
      .then(async (result) => {
        const saved = result.items.some(
          (item) => item.product.id === productId,
        );
        if (saved) {
          await LUMIERE_API.removeWishlist(productId);
          wishlistIds.delete(productId);
        } else {
          await LUMIERE_API.addWishlist(productId);
          wishlistIds.add(productId);
        }
        document
          .querySelectorAll(`.catalog-wish[data-favorite="${productId}"]`)
          .forEach((button) => {
            button.classList.toggle("is-active", !saved);
            button.setAttribute("aria-pressed", String(!saved));
            button.setAttribute(
              "aria-label",
              saved ? "Thêm vào yêu thích" : "Bỏ yêu thích",
            );
            button.title = saved ? "Thêm vào yêu thích" : "Bỏ yêu thích";
          });

        notify(saved ? "Đã bỏ yêu thích" : "Đã thêm vào yêu thích");

        if (page === "wishlist") wishlist();
      })
      .catch((error) => notify(error.message, true));
  }
  let wishlistIds = new Set();
  async function refreshCatalogFavorites() {
    if (!user || user.role !== "customer") return;

    try {
      const result = await LUMIERE_API.wishlist(1, 100);
      wishlistIds = new Set(
        result.items.map((item) => Number(item.product.id)),
      );

      document.querySelectorAll(".catalog-wish").forEach((button) => {
        const saved = wishlistIds.has(Number(button.dataset.favorite));

        button.classList.toggle("is-active", saved);
        button.setAttribute("aria-pressed", String(saved));
        button.setAttribute(
          "aria-label",
          saved ? "Bỏ yêu thích" : "Thêm vào yêu thích",
        );
        button.title = saved ? "Bỏ yêu thích" : "Thêm vào yêu thích";
      });
    } catch (error) {
      console.warn("Không tải được trạng thái yêu thích.", error);
    }
  }

  function account() {
    if (!user) {
      content.innerHTML = `
      <div class="empty-panel">
        Bạn chưa đăng nhập.
        <a class="inline-link" href="login.html">
          Đăng nhập
        </a>
      </div>`;
      return;
    }

    const initial = String(user.full_name || "L")
      .trim()
      .charAt(0)
      .toUpperCase();

    content.innerHTML = `
    <div class="my-account-layout">

      <aside class="panel my-account-sidebar">

        <div class="my-account-user">
          <div class="my-account-avatar">
            ${esc(initial)}
          </div>

          <h3>${esc(user.full_name)}</h3>
          <p>${esc(user.email)}</p>

          <span class="my-account-member">
            Thành viên LUMIÈRE
          </span>
        </div>

        <nav class="my-account-nav"
             aria-label="Điều hướng tài khoản">

          <a href="account.html"
             class="is-active"
             aria-current="page">
            <span>Thông tin cá nhân</span>
            <span>›</span>
          </a>

          <a href="orders.html">
            <span>Đơn hàng của tôi</span>
            <span>›</span>
          </a>

          <a href="wishlist.html">
            <span>Sản phẩm yêu thích</span>
            <span>›</span>
          </a>

          <a href="reviews.html">
            <span>Đánh giá của tôi</span>
            <span>›</span>
          </a>

        </nav>

        <button class="button button-outline"
                id="logout-main"
                type="button">
          ĐĂNG XUẤT
        </button>

      </aside>

      <section class="panel my-account-profile">

        <div class="my-account-heading">
          <div class="eyebrow">MY LUMIÈRE</div>

          <h2>Hồ sơ cá nhân</h2>

          <p>
            Quản lý thông tin cá nhân và cập nhật
            thông tin liên hệ của bạn.
          </p>
        </div>

        ${errorBox}

        <form id="profile-form">

          ${formField("profile-name", "Họ và tên", "text", `value="${esc(user.full_name)}" minlength="2" maxlength="150" required`)}

          ${formField("profile-phone", "Số điện thoại", "tel", `value="${esc(user.phone || "")}" maxlength="20"`)}

          ${formField("profile-email", "Địa chỉ email", "email", `value="${esc(user.email)}" disabled`)}

          <p class="my-account-hint">
            Email đăng nhập hiện không thể thay đổi.
          </p>

          <div class="my-account-actions">
            <button class="button button-dark"
                    type="submit">
              LƯU THAY ĐỔI
            </button>
          </div>

        </form>
      </section>

    </div>`;

    $("#profile-form").onsubmit = async (event) => {
      event.preventDefault();

      const button = event.currentTarget.querySelector('button[type="submit"]');

      button.disabled = true;
      button.textContent = "ĐANG LƯU...";

      try {
        user = await LUMIERE_API.updateProfile({
          full_name: get("profile-name"),
          phone: get("profile-phone") || null,
        });

        notify("Đã cập nhật hồ sơ");

        const headerName = document.querySelector(".shell-account-name");

        if (headerName) {
          headerName.textContent = user.full_name;
        }

        account();
      } catch (error) {
        alert(error.message);
      } finally {
        button.disabled = false;
        button.textContent = "LƯU THAY ĐỔI";
      }
    };

    $("#logout-main").onclick = logout;
  }

  async function wishlist() {
    if (!user || user.role !== "customer") {
      content.innerHTML = `
      <section class="wishlist-empty">
        <div class="wishlist-empty-icon">♡</div>

        <h2>Danh sách yêu thích của bạn</h2>

        <p>Đăng nhập để lưu giữ những món trang sức bạn yêu thích.</p>

        <a class="button button-dark" href="login.html">
          ĐĂNG NHẬP
        </a>
      </section>`;
      return;
    }

    content.innerHTML = `
    <div class="empty-panel">
      Đang tải danh sách yêu thích…
    </div>`;

    try {
      const result = await LUMIERE_API.wishlist();

      wishlistIds = new Set(
        result.items.map((item) => Number(item.product.id)),
      );

      const products = result.items.map((item) => {
        const p = item.product;

        const fallback =
          LUMIERE_CATEGORY_IMAGES[p.category?.name] ||
          LUMIERE_CATEGORY_IMAGES.Charm;

        return {
          ...p,
          category: p.category?.name || "",
          material: p.material?.name || "",
          brand: p.brand?.name || "",
          gem: p.gemstone?.name || "",
          collection: p.collection?.name || "",
          price: Number(p.price_vnd),
          image: window.LUMIERE_PRODUCT_IMAGE
            ? window.LUMIERE_PRODUCT_IMAGE(p.sku, fallback)
            : fallback,
        };
      });

      if (!products.length) {
        content.innerHTML = `
        <section class="wishlist-empty">

          <div class="wishlist-empty-icon">♡</div>

          <h2>Danh sách yêu thích đang trống</h2>

          <p>
            Khám phá bộ sưu tập và lưu lại những
            món trang sức khiến bạn rung động.
          </p>

          <a class="button button-dark" href="products.html">
            KHÁM PHÁ SẢN PHẨM →
          </a>

        </section>`;
        return;
      }

      content.innerHTML = `
      <section class="wishlist-section">

        <p class="wishlist-intro">
          Lưu giữ những thiết kế bạn yêu thích.
        </p>

        <div class="wishlist-toolbar">

          <span>
            ${Number(result.total ?? products.length)} sản phẩm đã lưu
          </span>

          <a href="products.html" class="inline-link">
            Tiếp tục khám phá →
          </a>

        </div>

        <div id="wishlist-grid" class="catalog-grid">
          ${products.map(card).join("")}
        </div>

      </section>`;
    } catch (error) {
      content.innerHTML = `
      <section class="wishlist-empty">

        <h2>Chưa tải được danh sách yêu thích</h2>

        <p>${esc(error.message)}</p>

        <button id="wishlist-retry"
                class="button button-outline"
                type="button">
          Thử lại
        </button>

      </section>`;

      $("#wishlist-retry").onclick = () => wishlist();
    }
  }

  function checkout() {
    if (!cartLines().length) {
      content.innerHTML =
        '<div class="empty-panel">Giỏ hàng của bạn đang trống. <a href="products.html">Tiếp tục mua sắm</a></div>';
      return;
    }

    const statusLabels = {
      pending: "Chờ xác nhận",
      confirmed: "Đã xác nhận",
      packing: "Đang đóng gói",
      shipping: "Đang giao",
      delivered: "Đã giao",
      cancelled: "Đã hủy",
    };

    const paymentLabels = {
      unpaid: "Chưa thanh toán",
      paid: "Đã thanh toán",
      pending: "Đang chờ thanh toán",
      failed: "Thanh toán thất bại",
      refunded: "Đã hoàn tiền",
    };

    content.innerHTML = `
    <div class="two-col">
      <section class="panel">
        <h2>01 — Thông tin người nhận</h2>
        ${errorBox}

        <form id="checkout-form">
          ${formField("recipient", "Họ và tên", "text", 'required autocomplete="name"')}
          ${formField("phone", "Số điện thoại", "tel", 'required pattern="0[0-9]{9}"')}
          ${formField("address", "Địa chỉ nhận hàng", "text", 'required minlength="5"')}
          ${formField("province", "Tỉnh / thành phố", "text", "required")}

          <h3 class="checkout-section-title">02 — Ưu đãi</h3>

          ${formField("coupon-code", "Mã giảm giá", "text", 'maxlength="24" autocomplete="off"')}

          <div class="coupon-actions">
            <button id="coupon-validate" class="button button-outline" type="button">
              Áp dụng mã
            </button>
            <button id="coupon-remove" class="button button-outline" type="button" hidden>
              Bỏ mã
            </button>
          </div>

          <p id="coupon-result" role="status" aria-live="polite"></p>

          <h3 class="checkout-section-title">03 — Thanh toán</h3>

          <div class="field">
            <label for="payment-method">Phương thức thanh toán</label>

            <select id="payment-method">
              <option value="cod">Thanh toán khi nhận hàng (COD)</option>
              <option value="vnpay" disabled>VNPAY · Chưa khả dụng</option>
            </select>

            <small id="vnpay-status" class="mini-note">
              Đang kiểm tra phương thức thanh toán...
            </small>
          </div>

          <button class="button button-dark button-wide" type="submit">
            XÁC NHẬN ĐẶT HÀNG
          </button>
        </form>
      </section>

      <aside class="summary-card">
        <h2>Tóm tắt đơn hàng</h2>

        ${cartLines()
          .map(
            ({ p, qty, lineTotal }) => `
          <div class="checkout-item">
            ${
              p.image
                ? `
              <img src="${esc(p.image)}" alt="${esc(p.name)}">
            `
                : ""
            }

            <div class="checkout-item-info">
              <strong>${esc(p.name)}</strong>
              <small>${esc(p.material || "")}</small>
              <small>Số lượng: ${qty}</small>
              <strong class="price">${money(lineTotal)}</strong>
            </div>
          </div>
        `,
          )
          .join("")}

        <div class="summary-line">
          <span>Tạm tính</span>
          <strong id="checkout-subtotal">${money(subtotal())}</strong>
        </div>

        <div class="summary-line" id="checkout-discount-row" hidden>
          <span>
            Giảm giá
            <small id="checkout-coupon-label"></small>
          </span>
          <strong id="checkout-discount"></strong>
        </div>

        <div class="summary-line">
          <span>Phí vận chuyển dự kiến</span>
          <strong id="checkout-shipping">Đang tính...</strong>
        </div>

        <div class="summary-line checkout-total">
          <span>Tổng thanh toán dự kiến</span>
          <strong id="checkout-total">${money(subtotal())}</strong>
        </div>

        <p id="checkout-shipping-note" class="mini-note">
          Phí vận chuyển chính xác được xác nhận khi đặt hàng.
        </p>
      </aside>
    </div>`;

    let couponCode = null;
    let vnpayReady = false;
    let couponAmounts = null,
      shippingCost = 0,
      couponRevision = 0,
      validating = 0;

    const couponReasons = {
      not_found: "Mã giảm giá không tồn tại.",
      inactive: "Mã này đang tạm dừng.",
      not_started: "Mã chưa đến thời gian sử dụng.",
      expired: "Mã đã hết hạn.",
      exhausted: "Mã đã hết lượt sử dụng.",
      already_used: "Bạn đã dùng mã này.",
      min_order: "Đơn hàng chưa đạt giá trị tối thiểu của mã.",
      invalid_discount: "Mức giảm không phù hợp với đơn hàng này.",
      counter_capacity: "Mã đã đạt giới hạn sử dụng.",
    };

    function syncSummary() {
      if (!$("#checkout-form")) return;

      const discount = Number(couponAmounts?.discount_vnd || 0);

      $("#checkout-subtotal").textContent = money(
        couponAmounts?.subtotal_vnd ?? subtotal(),
      );

      $("#checkout-discount-row").hidden = !couponCode;
      $("#checkout-coupon-label").textContent = couponCode || "";
      $("#checkout-discount").textContent = "−" + money(discount);

      const fee = couponAmounts
        ? Number(couponAmounts.total_vnd) -
          Number(couponAmounts.subtotal_vnd) +
          discount
        : shippingCost;

      $("#checkout-shipping").textContent = money(fee);

      $("#checkout-total").textContent = money(
        couponAmounts?.total_vnd ?? subtotal() + shippingCost,
      );

      $("#coupon-remove").hidden = !couponCode;
    }

    function resetCoupon() {
      couponCode = null;
      couponAmounts = null;
      syncSummary();
    }

    async function applyCoupon() {
      const code = get("coupon-code").toUpperCase();
      const revision = ++couponRevision;
      const output = $("#coupon-result");

      if (!code) {
        resetCoupon();
        output.textContent = "Nhập mã giảm giá để áp dụng.";
        return false;
      }

      validating++;
      $("#coupon-validate").disabled = true;
      output.textContent = "Đang kiểm tra mã…";

      try {
        const result = await LUMIERE_API.validateCoupon(code);

        if (
          revision !== couponRevision ||
          get("coupon-code").toUpperCase() !== code
        )
          return false;

        if (!result.valid)
          throw Error(
            couponReasons[result.reason] || "Mã giảm giá không hợp lệ.",
          );

        couponCode = result.coupon_code;
        couponAmounts = result;
        $("#coupon-code").value = couponCode;

        syncSummary();

        output.textContent = `Đã áp dụng ${couponCode}: giảm ${money(result.discount_vnd)}.`;

        return true;
      } catch (error) {
        if (revision === couponRevision) {
          resetCoupon();
          output.textContent = error.message;
        }

        return false;
      } finally {
        validating--;
        $("#coupon-validate").disabled = validating > 0;
      }
    }

    LUMIERE_API.paymentMethods()
      .then((methods) => {
        if (!$("#checkout-form")) return;

        const vnpay = $('#payment-method option[value="vnpay"]');

        vnpayReady = methods.vnpay?.enabled === true;
        vnpay.disabled = !vnpayReady;

        vnpay.textContent = vnpayReady
          ? "VNPAY Sandbox"
          : "VNPAY · Chưa khả dụng";

        $("#vnpay-status").textContent =
          methods.vnpay?.message || "Thanh toán VNPAY chưa khả dụng.";

        const fee = Number(methods.shipping?.flat_fee_vnd || 0);
        const freeFrom = Number(methods.shipping?.free_from_vnd || 0);

        shippingCost = subtotal() >= freeFrom ? 0 : fee;

        syncSummary();

        $("#checkout-shipping-note").textContent =
          shippingCost === 0
            ? "Miễn phí vận chuyển theo cấu hình hiện tại."
            : "Phí vận chuyển " +
              money(shippingCost) +
              " · miễn phí từ " +
              money(freeFrom) +
              ".";
      })
      .catch((error) => {
        if (!$("#checkout-form")) return;

        $("#vnpay-status").textContent =
          "Không xác định được trạng thái VNPAY: " + error.message;

        $("#checkout-shipping").textContent = "Tính khi đặt hàng";
      });

    $("#coupon-code").addEventListener("input", () => {
      couponRevision++;
      resetCoupon();

      $("#coupon-result").textContent =
        "Mã sẽ được kiểm tra khi áp dụng hoặc đặt hàng.";
    });

    $("#coupon-validate").onclick = applyCoupon;

    $("#coupon-remove").onclick = () => {
      couponRevision++;
      $("#coupon-code").value = "";
      resetCoupon();
      $("#coupon-result").textContent = "Đã bỏ mã giảm giá.";
    };

    $("#checkout-form").onsubmit = async (event) => {
      event.preventDefault();

      if (!user || user.role !== "customer") {
        alert("Đăng nhập bằng tài khoản khách hàng để đặt hàng.");
        return;
      }

      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true;

      try {
        if (get("coupon-code")) {
          if (!(await applyCoupon())) {
            alert($("#coupon-result").textContent);
            button.disabled = false;
            return;
          }
        } else {
          resetCoupon();
        }

        const method = get("payment-method");

        if (method === "vnpay" && !vnpayReady)
          throw Error("VNPay Sandbox chưa được cấu hình hợp lệ. Hãy chọn COD.");

        const order = await LUMIERE_API.createOrder({
          recipient_name: get("recipient"),
          phone: get("phone"),
          address: get("address") + ", " + get("province"),
          payment_method: method,
          ...(couponCode ? { coupon_code: couponCode } : {}),
        });

        cartData = {
          items: [],
          total_quantity: 0,
          subtotal_vnd: "0.00",
        };

        if (method === "vnpay") {
          try {
            const payment = await LUMIERE_API.startVnpayPayment(order.id);
            const gateway = new URL(payment.payment_url);

            if (
              gateway.protocol !== "https:" ||
              gateway.hostname !== "sandbox.vnpayment.vn"
            )
              throw Error("Địa chỉ cổng thanh toán không hợp lệ");

            location.assign(gateway.href);
            return;
          } catch (paymentError) {
            content.innerHTML = `
            <section class="panel">
              <h2>Đã tạo đơn hàng, chưa chuyển được sang VNPAY</h2>
              <p>Mã đơn: <strong>${esc(order.code)}</strong></p>
              <p class="form-alert error">${esc(paymentError.message)}</p>
              <p>Không tạo lại đơn hàng. Bạn có thể kiểm tra trạng thái trong lịch sử đơn.</p>
              <a class="button button-dark" href="orders.html">Xem đơn hàng</a>
            </section>`;
            return;
          }
        }

        const heading = document.querySelector(".page-heading h1");

        if (heading) {
          heading.textContent = "Xác nhận đơn hàng";
        }

        content.innerHTML = `
        <section class="panel order-success">

          <div class="order-success-icon">✓</div>

          <h2>Đặt hàng thành công!</h2>

          <p class="order-success-description">
            Cảm ơn bạn đã lựa chọn LUMIÈRE.
            Đơn hàng của bạn đã được ghi nhận.
          </p>

          <div class="order-success-info">

            <div class="summary-line">
              <span>Mã đơn hàng</span>
              <strong>${esc(order.code)}</strong>
            </div>

            <div class="summary-line">
              <span>Trạng thái</span>
              <strong>
                ${esc(statusLabels[order.status] || order.status)}
              </strong>
            </div>

            <div class="summary-line">
              <span>Phương thức thanh toán</span>
              <strong>COD</strong>
            </div>

            <div class="summary-line">
              <span>Thanh toán</span>
              <strong>
                ${esc(paymentLabels[order.payment_status] || order.payment_status)}
              </strong>
            </div>

            <div class="summary-line total">
              <span>Tổng tiền</span>
              <strong class="price">${money(order.total_vnd)}</strong>
            </div>

          </div>

          <div class="order-success-actions">
            <a class="button button-dark" href="orders.html">
              XEM ĐƠN HÀNG
            </a>

            <a class="button button-outline" href="products.html">
              TIẾP TỤC MUA SẮM
            </a>
          </div>

        </section>`;
      } catch (error) {
        alert(error.message);
        button.disabled = false;
      }
    };
  }

  async function showProductReviews() {
    const id = Number(new URLSearchParams(location.search).get("id"));
    if (!Number.isInteger(id) || id < 1) return;
    let section = content.querySelector("#product-reviews-panel");
    if (!section) {
      section = document.createElement("section");
      section.id = "product-reviews-panel";
      section.className = "panel";
      content.append(section);
    }
    section.innerHTML = "<h2>Đánh giá sản phẩm</h2><p>Đang tải đánh giá…</p>";
    try {
      const result = await LUMIERE_API.reviews(id);
      section.innerHTML = `<h2>Đánh giá sản phẩm</h2>${result.items.map((review) => `<article><strong>${esc(review.author_display_name)}</strong> · ${review.rating}/5<p>${esc(review.comment)}</p></article>`).join("") || "<p>Chưa có đánh giá.</p>"}
    ${
      user?.role === "customer"
        ? `<form id="review-form" class="review-form">
  <div class="review-field">
    <label for="review-rating">Điểm đánh giá</label>
    <select id="review-rating" name="rating">
      <option value="5">★★★★★ – 5 sao</option>
      <option value="4">★★★★☆ – 4 sao</option>
      <option value="3">★★★☆☆ – 3 sao</option>
      <option value="2">★★☆☆☆ – 2 sao</option>
      <option value="1">★☆☆☆☆ – 1 sao</option>
    </select>
  </div>

  <div class="review-field">
    <label for="review-comment">Nhận xét của bạn</label>
    <textarea
      id="review-comment"
      required
      maxlength="2000"
      placeholder="Chia sẻ trải nghiệm của bạn về sản phẩm..."
    ></textarea>
  </div>

  <div class="review-actions">
    <button type="submit" class="button button-dark">
      Gửi đánh giá
    </button>
  </div>

  <p id="review-error" role="alert"></p>
</form>`
        : "<p>Đăng nhập bằng tài khoản khách hàng để đánh giá sản phẩm đã mua.</p>"
    }`;
      section
        .querySelector("#review-form")
        ?.addEventListener("submit", async (event) => {
          event.preventDefault();
          const button = event.currentTarget.querySelector("button");
          button.disabled = true;
          try {
            await LUMIERE_API.createReview(id, {
              rating: Number(event.currentTarget.elements.rating.value),
              comment: section.querySelector("#review-comment").value,
            });
            await showProductReviews();
          } catch (error) {
            section.querySelector("#review-error").textContent = error.message;
            button.disabled = false;
          }
        });
    } catch (error) {
      section.innerHTML = `<h2>Đánh giá sản phẩm</h2><p>${esc(error.message)}</p>`;
    }
  }
  async function showMyReviews() {
    if (!user || user.role !== "customer") {
      content.innerHTML =
        '<div class="empty-panel">Đăng nhập để xem đánh giá của bạn. <a href="login.html">Đăng nhập</a></div>';
      return;
    }

    try {
      const result = await LUMIERE_API.reviews();
      const reviews = result.items;

      content.innerHTML = `
      <section class="my-reviews-section">
        <div class="my-reviews-toolbar">
          <span>${reviews.length} đánh giá</span>
          <a class="inline-link" href="orders.html">
            Đơn hàng của tôi →
          </a>
        </div>

        <div class="my-reviews-list">
          ${
            reviews
              .map((r) => {
                const p = P.find((p) => Number(p.id) === Number(r.product_id));
                const rating = Math.max(
                  0,
                  Math.min(5, Math.trunc(Number(r.rating) || 0)),
                );

                return `
              <article class="panel my-review-card">
                <div class="my-review-product">
                  ${
                    p?.image
                      ? `
                    <a href="product-detail.html?id=${Number(r.product_id)}">
                      <img src="${esc(p.image)}" alt="${esc(p.name)}">
                    </a>`
                      : ""
                  }

                  <div class="my-review-product-info">
                    <h3>${esc(p?.name || "Sản phẩm đã đánh giá")}</h3>

                    <div class="my-review-rating" aria-label="${rating} trên 5 sao">
                      <span>${"★".repeat(rating)}${"☆".repeat(5 - rating)}</span>
                      <small>${rating}/5</small>
                    </div>

                    <a class="inline-link" href="product-detail.html?id=${Number(r.product_id)}">
                      Xem sản phẩm →
                    </a>
                  </div>
                </div>

                <p class="my-review-comment">${esc(r.comment)}</p>

                <div class="my-review-actions">
                  <button type="button" class="button button-outline" data-review-edit="${esc(r.id)}">
                    Chỉnh sửa
                  </button>
                  <button type="button" class="button button-outline my-review-delete" data-review-delete="${esc(r.id)}">
                    Xóa đánh giá
                  </button>
                </div>
              </article>`;
              })
              .join("") ||
            `
            <div class="panel my-reviews-empty">
              <div class="my-reviews-empty-icon">☆</div>
              <h2>Bạn chưa có đánh giá</h2>
              <p>Chia sẻ trải nghiệm về trang sức bạn đã mua.</p>
              <a class="button button-dark" href="orders.html">XEM ĐƠN HÀNG</a>
            </div>`
          }
        </div>
      </section>

      <dialog id="my-review-dialog" class="my-review-dialog" aria-labelledby="my-review-dialog-title">
        <form id="my-review-edit-form">
          <div class="my-review-dialog-head">
            <h2 id="my-review-dialog-title">Chỉnh sửa đánh giá</h2>
            <button type="button" data-close-review aria-label="Đóng">×</button>
          </div>

          <div class="field">
            <label for="my-review-rating">Điểm đánh giá</label>
            <select id="my-review-rating" required>
              ${[5, 4, 3, 2, 1]
                .map(
                  (n) => `
                <option value="${n}">${"★".repeat(n)}${"☆".repeat(5 - n)} – ${n} sao</option>
              `,
                )
                .join("")}
            </select>
          </div>

          <div class="field">
            <label for="my-review-comment">Nội dung đánh giá</label>
            <textarea id="my-review-comment" maxlength="2000" required></textarea>
          </div>

          <p class="my-review-error" role="alert"></p>

          <div class="my-review-modal-actions">
            <button class="button button-outline" type="button" data-close-review>Hủy</button>
            <button class="button button-dark" type="submit">LƯU THAY ĐỔI</button>
          </div>
        </form>
      </dialog>

      <dialog id="my-review-delete-dialog" class="my-review-dialog" aria-labelledby="my-review-delete-title">
        <form id="my-review-delete-form">
          <div class="my-review-dialog-head">
            <h2 id="my-review-delete-title">Xóa đánh giá?</h2>
            <button type="button" data-close-review aria-label="Đóng">×</button>
          </div>

          <p class="page-subtitle">Bạn có chắc chắn muốn xóa đánh giá này?</p>
          <p class="my-review-error" role="alert"></p>

          <div class="my-review-modal-actions">
            <button type="button" class="button button-outline" data-close-review>Hủy</button>
            <button type="submit" class="button my-review-danger">XÓA ĐÁNH GIÁ</button>
          </div>
        </form>
      </dialog>`;

      const edit = $("#my-review-dialog");
      const del = $("#my-review-delete-dialog");

      let editingId = null;
      let deletingId = null;

      content.querySelectorAll("[data-review-edit]").forEach((button) => {
        button.onclick = () => {
          const r = reviews.find(
            (r) => String(r.id) === button.dataset.reviewEdit,
          );
          if (!r) return;

          editingId = button.dataset.reviewEdit;
          $("#my-review-rating").value = r.rating;
          $("#my-review-comment").value = r.comment || "";
          edit.querySelector(".my-review-error").textContent = "";
          edit.showModal();
        };
      });

      content.querySelectorAll("[data-review-delete]").forEach((button) => {
        button.onclick = () => {
          deletingId = button.dataset.reviewDelete;
          del.querySelector(".my-review-error").textContent = "";
          del.showModal();
        };
      });

      for (const dialog of [edit, del]) {
        dialog.querySelectorAll("[data-close-review]").forEach((button) => {
          button.onclick = () => dialog.close();
        });

        dialog.addEventListener("cancel", (event) => {
          if (dialog.querySelector('button[type="submit"]').disabled) {
            event.preventDefault();
          }
        });
      }

      async function submitReview(event, dialog, action, message) {
        event.preventDefault();

        const buttons = [...dialog.querySelectorAll("button")];

        if (dialog.querySelector('button[type="submit"]').disabled) return;

        buttons.forEach((button) => (button.disabled = true));

        const error = dialog.querySelector(".my-review-error");
        error.textContent = "";

        try {
          await action();
          dialog.close();
          notify(message);
          await showMyReviews();
        } catch (e) {
          error.textContent = e.message;
        } finally {
          buttons.forEach((button) => (button.disabled = false));
        }
      }

      $("#my-review-edit-form").onsubmit = (event) =>
        submitReview(
          event,
          edit,
          () =>
            LUMIERE_API.updateReview(editingId, {
              rating: Number(get("my-review-rating")),
              comment: get("my-review-comment"),
            }),
          "Đã cập nhật đánh giá",
        );

      $("#my-review-delete-form").onsubmit = (event) =>
        submitReview(
          event,
          del,
          () => LUMIERE_API.deleteReview(deletingId),
          "Đã xóa đánh giá",
        );
    } catch (error) {
      content.innerHTML = `<div class="empty-panel">Không tải được đánh giá: ${esc(error.message)}</div>`;
    }
  }

  function staticPage() {
    if (page === "reviews") {
      showMyReviews();
      return;
    }
    if (page === "about") {
      content.innerHTML = `<div class="story-hero"><span class="eyebrow">CÂU CHUYỆN THƯƠNG HIỆU</span><h2>Vẻ đẹp lưu giữ những khoảnh khắc</h2><p>LUMIÈRE mang đến những thiết kế trang sức tinh tế, tôn vinh vẻ đẹp riêng và lưu giữ những khoảnh khắc đáng nhớ trong cuộc sống.</p></div>
    <div class="story-grid"><section class="panel"><span class="eyebrow">01 · KHỞI NGUỒN</span><h2>Mỗi món trang sức là một câu chuyện</h2><p>Một chiếc nhẫn có thể đánh dấu lời hứa, một đôi bông tai gợi nhớ ngày đặc biệt, một sợi dây chuyền trở thành món quà mang theo kỷ niệm. Từ cảm hứng ấy, LUMIÈRE được xây dựng để việc tìm kiếm trang sức trở nên gần gũi và có ý nghĩa hơn.</p></section>
    <section class="panel"><span class="eyebrow">02 · TRẢI NGHIỆM</span><h2>Tinh tế trong từng lựa chọn</h2><p>Khách hàng có thể khám phá danh mục theo loại trang sức, chất liệu, đá quý và ngân sách, sau đó theo dõi giỏ hàng, đơn hàng, đánh giá và sản phẩm yêu thích trong cùng một hệ thống.</p></section>
    <section class="panel"><span class="eyebrow">03 · DẤU ẤN CÁ NHÂN</span><h2>Vẻ đẹp dành riêng cho bạn</h2><p>Trợ lý trang sức thông minh giúp bạn khám phá những thiết kế phù hợp với sở thích, phong cách và ngân sách của mình..</p></section>
    <section class="panel"><span class="eyebrow">04 · GIÁ TRỊ THƯƠNG HIỆU</span><h2>Sự tinh tế và minh bạch</h2><p>LUMIÈRE hướng đến trải nghiệm mua sắm rõ ràng và thuận tiện, với thông tin sản phẩm, chất liệu và giá cả được trình bày minh bạch. Hình ảnh sản phẩm mang tính minh họa.</p></section></div>
    <div class="story-end"><h2>Tìm món trang sức dành riêng cho bạn</h2><p>Khám phá bộ sưu tập hoặc trò chuyện với trợ lý AI để bắt đầu hành trình lựa chọn.</p><a class="button button-dark" href="products.html">KHÁM PHÁ SẢN PHẨM</a></div>`;
      return;
    }
    if (page === "contact") {
      content.innerHTML = `<div class="contact-grid"><section class="panel"><span class="eyebrow">LUMIÈRE SUPPORT</span><h2>Chúng tôi có thể giúp gì cho bạn?</h2><p class="page-subtitle">Đội ngũ LUMIÈRE luôn sẵn sàng lắng nghe và hỗ trợ bạn trong hành trình lựa chọn trang sức.</p>
<div class="contact-store-info">

  <div class="contact-info-heading">
    THÔNG TIN LIÊN HỆ
  </div>

  <div class="contact-info-item">
    <div class="contact-info-icon">
      <svg viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.5"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/>
        <circle cx="12" cy="10" r="2.5"/>
      </svg>
    </div>
    <div>
      <strong>Địa chỉ cửa hàng</strong>
      <span>12 Nguyễn Văn Bảo, phường Hạnh Thông, TP. Hồ Chí Minh</span>
    </div>
  </div>

  <div class="contact-info-item">
    <div class="contact-info-icon">
      <svg viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.5"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 16.9v3a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 3.1 5.2 2 2 0 0 1 5.1 3h3a2 2 0 0 1 2 1.7l.7 3a2 2 0 0 1-.5 2.1l-1.3 1.3a16 16 0 0 0 5.9 5.9l1.3-1.3a2 2 0 0 1 2.1-.5l3 .7a2 2 0 0 1 .7 1Z"/>
      </svg>
    </div>
    <div>
      <strong>Hotline hỗ trợ</strong>
      <a href="tel:0922102110">09 2210 2110</a>
    </div>
  </div>

  <div class="contact-info-item">
    <div class="contact-info-icon">
      <svg viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="1.5"
           stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="5" width="18" height="14" rx="2"/>
        <path d="m3 6 9 7 9-7"/>
      </svg>
    </div>
    <div>
      <strong>Email liên hệ</strong>
      <a href="mailto:contact@lumiere.vn">
        contact@lumiere.vn
      </a>
    </div>
  </div>

</div>

<div class="contact-quick-support">

  <div class="contact-info-heading">
    HỖ TRỢ NHANH
  </div>

  <a href="policies.html#shopping" class="contact-support-link">
    <div>
      <strong>Hướng dẫn mua hàng</strong>
      <span>Khám phá quy trình mua sắm tại LUMIÈRE</span>
    </div>
    <span class="contact-link-arrow">›</span>
  </a>

  <a href="policies.html#warranty" class="contact-support-link">
    <div>
      <strong>Chính sách &amp; Hướng dẫn</strong>
      <span>Tra cứu bảo hành, đổi trả và thanh toán</span>
    </div>
    <span class="contact-link-arrow">›</span>
  </a>

  <div class="contact-support-link">
    <div>
      <strong>Theo dõi đơn hàng</strong>
      <span>Đăng nhập và truy cập mục Đơn hàng của tôi</span>
    </div>
  </div>

  <div class="contact-support-link">
    <div>
      <strong>Trợ lý trang sức AI</strong>
      <span>Sử dụng nút Tư vấn AI trên trang mua sắm</span>
    </div>
  </div>

</div>
<p class="mini-note">Vui lòng sử dụng biểu mẫu liên hệ để gửi yêu cầu hỗ trợ đến LUMIÈRE.</p></section>
    <section class="panel"><h2>Gửi yêu cầu hỗ trợ</h2><p class="mini-note" id="contact-method">Hãy để lại thông tin liên hệ và nội dung bạn cần hỗ trợ.</p><form id="contact-form">${formField("contact-name", "Họ và tên", "text", 'required minlength="2" maxlength="150"')}${formField("contact-email", "Email liên hệ", "email", 'required maxlength="254"')}<div class="field"><label for="contact-topic">Chủ đề</label><select id="contact-topic"><option>Tư vấn sản phẩm</option><option>Hỗ trợ đơn hàng</option><option>Góp ý trải nghiệm</option><option>Hỗ trợ khác</option></select></div><div class="field"><label for="contact-message">Nội dung</label><textarea id="contact-message" required minlength="10" maxlength="1500" placeholder="Mô tả yêu cầu của bạn..."></textarea></div><button class="button button-dark button-wide" type="submit">GỬI YÊU CẦU LIÊN HỆ</button><p id="contact-result" class="mini-note" role="status"></p></form></section></div>`;
      $("#contact-form").onsubmit = async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const button = event.currentTarget.querySelector(
          'button[type="submit"]',
        );
        const result = $("#contact-result");
        button.disabled = true;
        result.textContent = "Đang gửi yêu cầu...";
        try {
          const response = await LUMIERE_API.request("/contact", {
            method: "POST",
            body: JSON.stringify({
              full_name: get("contact-name"),
              email: get("contact-email"),
              topic: get("contact-topic"),
              message: get("contact-message"),
            }),
          });
          result.textContent =
            "Cảm ơn bạn đã liên hệ LUMIÈRE. Yêu cầu của bạn đã được tiếp nhận. Mã yêu cầu: #" +
            response.id;
          form.reset();
        } catch (error) {
          result.textContent = "Không gửi được liên hệ: " + error.message;
        } finally {
          button.disabled = false;
        }
      };
      return;
    }
    if (window.LUMIERE_PRODUCTS_ERROR) {
      content.innerHTML =
        '<div class="empty-panel">Chưa tải được bộ sưu tập.</div>';
      return;
    }

    const groups = new Map();

    P.forEach((p) => {
      const name = String(p.collection || "");
      if (!name.trim()) return;
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(p);
    });

    content.innerHTML = `
    <section class="collection-section">
      <p class="collection-intro">
        Mỗi thiết kế, một câu chuyện.
        Mỗi bộ sưu tập, một dấu ấn riêng.
      </p>
      <div class="collection-grid">
        ${
          [...groups.entries()]
            .sort(([a], [b]) => a.localeCompare(b, "vi"))
            .map(([name, products]) => {
              const cover = products.find((p) => p.image);
              return `
              <a class="collection-card"
                 href="products.html?collection=${encodeURIComponent(name)}">
                <div class="collection-cover">
                  ${cover ? `<img src="${esc(cover.image)}" alt="${esc(name)}" loading="lazy">` : ""}
                </div>
                <div class="collection-info">
                  <h2>${esc(name)}</h2>
                  <p>${products.length} sản phẩm</p>
                  <span>Khám phá bộ sưu tập →</span>
                </div>
              </a>`;
            })
            .join("") || '<div class="empty-panel">Chưa có bộ sưu tập.</div>'
        }
      </div>
    </section>`;
  }
  async function logout() {
    try {
      await LUMIERE_API.logout();
      user = null;
      location.href = root + "pages/login.html";
    } catch (e) {
      notify(e.message, true);
    }
  }
  function render() {
    if (page === "products") catalog();
    else if (page === "search") searchPage();
    else if (page === "product-detail") detail();
    else if (page === "cart") cartPage();
    else if (page === "checkout") checkout();
    else if (["login", "register", "forgot-password"].includes(page))
      auth(page);
    else if (page === "account") account();
    else if (["orders", "order-detail"].includes(page)) orders();
    else if (page === "wishlist") wishlist();
    else if (page.startsWith("admin-")) adminPage();
    else if (page.startsWith("staff-")) staffPage();
    else staticPage();
  }
  document.addEventListener("click", (e) => {
    const button = e.target.closest("button");
    if (!button) return;
    if (button.dataset.add) {
      add(button.dataset.add);
    } else if (button.dataset.favorite) {
      favorite(button.dataset.favorite);
    } else if (button.dataset.remove) {
      changeCartItem(button.dataset.remove, 0, true);
    } else if (button.dataset.inc) {
      changeCartItem(button.dataset.inc, 1);
    } else if (button.dataset.dec) {
      changeCartItem(button.dataset.dec, -1);
    } else if (button.dataset.demo) {
      demo();
    }
  });
  $("#nav-logout").onclick = logout;
  (async () => {
    content.innerHTML =
      '<div class="empty-panel">Đang tải danh mục từ Business API…</div>';
    const [productsResult, authResult] = await Promise.allSettled([
      window.LUMIERE_LOAD_PRODUCTS
        ? window.LUMIERE_LOAD_PRODUCTS()
        : Promise.reject(Error("Thiếu products.js")),
      window.LUMIERE_API
        ? LUMIERE_API.me()
        : Promise.reject(Error("Thiếu api.js")),
    ]);

    if (authResult.status === "fulfilled") {
      user = authResult.value;
      showSignedInMenu();
    }

    if (productsResult.status === "rejected") {
      window.LUMIERE_PRODUCTS_ERROR =
        productsResult.reason?.message || "Không tải được dữ liệu sản phẩm.";
      console.error("LUMIERE products load failed:", productsResult.reason);
    }
    if (user && (page === "cart" || page === "checkout")) {
      try {
        cartData = await LUMIERE_API.getCart();
      } catch (error) {
        console.error("Không tải được giỏ hàng:", error);
        content.innerHTML = `<div class="empty-panel">${esc(error.message)}</div>`;
        return;
      }
    }

    if (user && ["admin", "staff"].includes(user.role)) {
      if (applyRoleNavigation()) return;
    }
    if (page.startsWith("admin-") && user?.role !== "admin") {
      location.replace(
        root +
          (user?.role === "staff"
            ? "pages/staff/orders.html"
            : user
              ? "pages/products.html"
              : "pages/login.html"),
      );
      return;
    }
    if (page.startsWith("staff-") && user?.role !== "staff") {
      location.replace(
        root +
          (user?.role === "admin"
            ? "pages/admin/dashboard.html"
            : user
              ? "pages/products.html"
              : "pages/login.html"),
      );
      return;
    }

    if (page.startsWith("admin-") || page.startsWith("staff-")) {
      try {
        await import(
          new URL(root + "assets/js/backend-console.js", document.baseURI).href
        );
      } catch (error) {
        content.innerHTML = `<div class="empty-panel">Không tải được giao diện nghiệp vụ: ${esc(error.message)}</div>`;
        console.error(error);
        return;
      }
    }
    render();
    mountSharedChatbot();

    if (page === "product-detail") showProductReviews();
  })();
})();
const reviewStyles = document.createElement("style");
reviewStyles.textContent = `
/* LUMIERE - Product reviews */
#review-form.review-form {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  max-width: 100%;
  margin-top: 25px;
  padding-top: 22px;
  border-top: 1px solid #e9dfd2;
}

#review-form .review-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

#review-form .review-field label {
  font-size: 13px;
  font-weight: 600;
  color: #665340;
}

#review-form select {
  width: min(100%, 260px);
  min-height: 46px;
  padding: 12px 14px;
  border: 1px solid #d9c9b4;
  background: #fff;
  color: #594733;
  font-size: 14px;
}

#review-form textarea {
  width: 100%;
  min-height: 130px;
  padding: 15px 17px;
  border: 1px solid #d9c9b4;
  background: #fff;
  line-height: 1.7;
  resize: vertical;
  box-sizing: border-box;
}

#review-form select:focus,
#review-form textarea:focus {
  outline: 2px solid #c5a371;
  outline-offset: 2px;
}

#review-form .review-actions {
  display: flex;
  justify-content: flex-end;
}

#review-form .review-actions button {
  min-width: 160px;
  height: 46px;
  padding: 12px 25px;
  background: #292824;
  color: white;
  border: none;
  cursor: pointer;
}

#review-form .review-actions button:hover {
  background: #8b6a40;
}

#review-form #review-error {
  margin: 0;
  color: #b43e35;
  font-size: 12px;
}

#review-form #review-error:empty {
  display: none;
}
`;
document.head.appendChild(reviewStyles);

(() => {
  "use strict";

  const policies = {
    shopping: {
      title: "Hướng dẫn mua hàng",
      content: `
                <p>Khám phá và lựa chọn những thiết kế trang sức
                phù hợp với phong cách riêng của bạn tại LUMIÈRE.</p>

                <h3>Quy trình đặt hàng</h3>
                <ol>
                    <li>Truy cập danh mục sản phẩm và lựa chọn
                    trang sức yêu thích.</li>
                    <li>Xem thông tin sản phẩm, lựa chọn thuộc tính
                    phù hợp nếu có và số lượng.</li>
                    <li>Thêm sản phẩm vào giỏ hàng.</li>
                    <li>Kiểm tra giỏ hàng và tiến hành đặt hàng.</li>
                    <li>Cung cấp thông tin nhận hàng và lựa chọn
                    phương thức thanh toán khả dụng.</li>
                    <li>Xác nhận đơn hàng và theo dõi trạng thái
                    tại mục Đơn hàng của tôi.</li>
                </ol>

                <div class="policy-note">
                    <p>Nếu cần tư vấn trong quá trình mua sắm,
                    bạn có thể sử dụng trợ lý trang sức AI
                    hoặc liên hệ đội ngũ LUMIÈRE.</p>
                </div>
            `,
    },

    payment: {
      title: "Hướng dẫn thanh toán",
      content: `
                <p>LUMIÈRE giới thiệu các phương thức thanh toán
                nhằm mang đến trải nghiệm mua sắm thuận tiện.</p>

                <h3>1. Thanh toán khi nhận hàng (COD)</h3>
                <p>Khách hàng lựa chọn COD khi đặt hàng và
                thanh toán số tiền cần trả khi nhận sản phẩm.</p>

                <h3>2. Thanh toán qua VNPAY</h3>
                <p>Khi tính năng VNPAY khả dụng, khách hàng
                lựa chọn phương thức này tại bước thanh toán
                và thực hiện theo hướng dẫn của cổng thanh toán.</p>

                <h3>3. Lưu ý khi thanh toán</h3>
                <ul>
                    <li>Kiểm tra tổng giá trị đơn hàng.</li>
                    <li>Không cung cấp mật khẩu hoặc mã OTP
                    cho người khác.</li>
                    <li>Kiểm tra trạng thái đơn hàng sau khi
                    hoàn tất thanh toán.</li>
                </ul>

                <div class="policy-note">
                    <p>Liên hệ LUMIÈRE nếu gặp khó khăn
                    trong quá trình thanh toán.</p>
                </div>
            `,
    },

    warranty: {
      title: "Chính sách bảo hành",
      content: `
                <p>LUMIÈRE tiếp nhận yêu cầu hỗ trợ liên quan
                đến chất lượng và tình trạng sản phẩm.</p>

                <h3>1. Điều kiện xem xét bảo hành</h3>
                <ul>
                    <li>Có thông tin đơn hàng để đối chiếu.</li>
                    <li>Sản phẩm có dấu hiệu lỗi cần kiểm tra.</li>
                    <li>Cung cấp thông tin và hình ảnh sản phẩm
                    khi được yêu cầu.</li>
                </ul>

                <h3>2. Các trường hợp cần đánh giá riêng</h3>
                <ul>
                    <li>Hư hỏng do va đập hoặc tác động bên ngoài.</li>
                    <li>Ảnh hưởng do hóa chất hoặc bảo quản
                    không phù hợp.</li>
                    <li>Sản phẩm đã được sửa chữa tại nơi khác.</li>
                </ul>

                <h3>3. Quy trình hỗ trợ</h3>
                <ol>
                    <li>Gửi yêu cầu qua trang Liên hệ.</li>
                    <li>Cung cấp thông tin đơn hàng.</li>
                    <li>Chờ kiểm tra và phản hồi phương án hỗ trợ.</li>
                </ol>

                <div class="policy-note">
                    <p>Thời hạn và phạm vi bảo hành cụ thể cần
                    được xác nhận theo từng sản phẩm.</p>
                </div>
            `,
    },

    returns: {
      title: "Chính sách đổi trả",
      content: `
                <p>LUMIÈRE tiếp nhận yêu cầu đổi trả và xem xét
                dựa trên thông tin đơn hàng, tình trạng sản phẩm
                và điều kiện áp dụng.</p>

                <h3>1. Các trường hợp tiếp nhận</h3>
                <ul>
                    <li>Sản phẩm giao không đúng đơn hàng.</li>
                    <li>Sản phẩm có dấu hiệu lỗi hoặc hư hỏng
                    khi nhận hàng.</li>
                    <li>Các trường hợp khác cần được xem xét.</li>
                </ul>

                <h3>2. Quy trình đổi trả</h3>
                <ol>
                    <li>Liên hệ đội ngũ hỗ trợ LUMIÈRE.</li>
                    <li>Cung cấp mã đơn hàng và lý do đổi trả.</li>
                    <li>Cung cấp hình ảnh sản phẩm nếu cần.</li>
                    <li>Chờ xác nhận phương án xử lý.</li>
                </ol>

                <div class="policy-note">
                    <p>Khách hàng nên giữ lại bao bì, phụ kiện
                    và thông tin mua hàng. Thời hạn và chi phí
                    đổi trả cần được xác nhận trước khi áp dụng.</p>
                </div>
            `,
    },

    shipping: {
      title: "Chính sách giao hàng",
      content: `
                <p>LUMIÈRE hướng đến trải nghiệm nhận hàng
                thuận tiện và dễ dàng theo dõi.</p>

                <h3>1. Quy trình giao hàng</h3>
                <ol>
                    <li>Tiếp nhận và xác nhận đơn hàng.</li>
                    <li>Chuẩn bị, kiểm tra và đóng gói sản phẩm.</li>
                    <li>Bàn giao sản phẩm cho đơn vị vận chuyển.</li>
                    <li>Giao hàng đến địa chỉ khách hàng cung cấp.</li>
                </ol>

                <h3>2. Thời gian và chi phí vận chuyển</h3>
                <p>Phụ thuộc vào địa chỉ nhận hàng,
                phương thức vận chuyển và tình trạng đơn hàng.
                Khách hàng cần kiểm tra thông tin trước khi
                xác nhận đặt hàng.</p>

                <h3>3. Theo dõi đơn hàng</h3>
                <p>Đăng nhập vào tài khoản và truy cập mục
                Đơn hàng của tôi để kiểm tra trạng thái.</p>

                <div class="policy-note">
                    <p>Vui lòng kiểm tra thông tin người nhận,
                    số điện thoại và địa chỉ trước khi đặt hàng.</p>
                </div>
            `,
    },

    privacy: {
      title: "Chính sách bảo mật",
      content: `
                <p>Thông tin cá nhân của khách hàng cần được
                quản lý phù hợp với mục đích sử dụng của hệ thống.</p>

                <h3>1. Thông tin phục vụ mua sắm</h3>
                <ul>
                    <li>Họ tên và thông tin liên hệ.</li>
                    <li>Địa chỉ nhận hàng.</li>
                    <li>Thông tin tài khoản và đơn hàng.</li>
                    <li>Nội dung yêu cầu hỗ trợ khách hàng.</li>
                </ul>

                <h3>2. Mục đích sử dụng</h3>
                <ul>
                    <li>Xử lý và theo dõi đơn hàng.</li>
                    <li>Hỗ trợ khách hàng trong quá trình mua sắm.</li>
                    <li>Quản lý tài khoản và hoạt động hệ thống.</li>
                </ul>

                <h3>3. Bảo vệ tài khoản</h3>
                <p>Khách hàng nên giữ bí mật mật khẩu,
                đăng xuất khi sử dụng thiết bị công cộng và
                thông báo nếu phát hiện hoạt động bất thường.</p>

                <h3>4. Yêu cầu hỗ trợ về thông tin cá nhân</h3>
                <p>Khách hàng có thể gửi yêu cầu thông qua
                <a href="contact.html">trang Liên hệ</a>.</p>
            `,
    },

    care: {
      title: "Hướng dẫn bảo quản trang sức",
      content: `
                <p>Chăm sóc đúng cách giúp duy trì vẻ đẹp
                và độ bền của trang sức theo thời gian.</p>

                <h3>1. Trang sức vàng</h3>
                <ul>
                    <li>Hạn chế tiếp xúc với hóa chất và mỹ phẩm.</li>
                    <li>Lau nhẹ bằng khăn mềm sạch.</li>
                    <li>Tránh va đập và ma sát mạnh.</li>
                </ul>

                <h3>2. Trang sức bạc</h3>
                <ul>
                    <li>Bảo quản ở nơi khô ráo.</li>
                    <li>Sử dụng khăn vệ sinh bạc phù hợp.</li>
                    <li>Hạn chế tiếp xúc với chất tẩy rửa
                    và môi trường ẩm ướt.</li>
                </ul>

                <h3>3. Trang sức đính đá quý</h3>
                <ul>
                    <li>Tránh va đập trực tiếp vào mặt đá.</li>
                    <li>Không sử dụng hóa chất mạnh.</li>
                    <li>Lựa chọn phương pháp vệ sinh phù hợp
                    với từng loại đá.</li>
                </ul>

                <h3>4. Lưu ý chung</h3>
                <ul>
                    <li>Tháo trang sức khi vận động mạnh.</li>
                    <li>Hạn chế đeo khi tắm hoặc bơi.</li>
                    <li>Bảo quản riêng từng món trong hộp đựng
                    để hạn chế trầy xước.</li>
                </ul>

                <div class="policy-note">
                    <p>LUMIÈRE — Vẻ đẹp vượt thời gian,
                    bắt đầu từ sự chăm sóc mỗi ngày.</p>
                </div>
            `,
    },
  };

  const content = document.getElementById("policy-content");
  const links = document.querySelectorAll(".policy-menu a");

  if (!content) return;

  function renderPolicy() {
    const requested = window.location.hash.slice(1);

    const key = Object.prototype.hasOwnProperty.call(policies, requested)
      ? requested
      : "shopping";

    const policy = policies[key];

    content.innerHTML = `
            <h2>${policy.title}</h2>
            ${policy.content}
        `;

    links.forEach((link) => {
      const active = link.getAttribute("href") === "#" + key;

      link.classList.toggle("active", active);

      if (active) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }
    });

    document.title = policy.title + " | LUMIÈRE";
  }

  window.addEventListener("hashchange", renderPolicy);

  renderPolicy();
})();
