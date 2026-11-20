
/**
 * LUMIÈRE - Shared Site Shell
 * Header chung cho Customer, Admin và Staff.
 * Sidebar quản trị được xử lý riêng trong Management Console.
 */

export function mountSiteShell(root) {
  const $ = (selector) => document.querySelector(selector);

  const nav = (text, url) =>
    `<a href="${root + url}">${text}</a>`;

  const shell = $("#site-shell");
  if (!shell) return;

  shell.innerHTML = `
    <div class="site-bar">
      LUMIÈRE — TINH HOA TRANG SỨC
    </div>

    <header class="site-nav">
      <div class="container site-nav-inner">

        <a class="logo" href="${root}index.html">
          LUMIÈRE
          <span>FINE JEWELRY</span>
        </a>

        <nav class="site-nav-links" aria-label="Điều hướng chính">
          ${nav("Trang chủ", "index.html")}
          ${nav("Sản phẩm", "pages/products.html")}
          ${nav("Bộ sưu tập", "pages/collections.html")}
          ${nav("Giới thiệu", "pages/about.html")}
          ${nav("Liên hệ", "pages/contact.html")}
        </nav>

        <div class="account-links">
          ${nav("♡ Yêu thích", "pages/wishlist.html")}
          ${nav("Giỏ hàng", "pages/cart.html")}

          <a
            id="account-nav"
            href="${root}pages/login.html"
            aria-label="Tài khoản"
          >
            <svg
              viewBox="0 0 24 24"
              width="19"
              height="19"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
              style="vertical-align:middle"
            >
              <circle cx="12" cy="8" r="4"/>
              <path d="M4 21a8 8 0 0 1 16 0"/>
            </svg>
            Đăng nhập
          </a>

          <button id="nav-logout" type="button" hidden>
            Đăng xuất
          </button>
        </div>

      </div>
    </header>
  `;

  const footer = $("#site-footer");

  if (footer) {
    footer.innerHTML = `
      <footer class="footer">
        <div class="container footer-grid">

          <div>
            <div class="logo footer-logo">
              LUMIÈRE<span>FINE JEWELRY</span>
            </div>
            <p>
              Vẻ đẹp vượt thời gian.<br>
              Chạm vào dấu ấn riêng của bạn.
            </p>
          </div>

          <div>
            <h3>KHÁM PHÁ</h3>

            <a href="${root}pages/products.html">
              Tất cả sản phẩm
            </a>

            <a href="${root}pages/collections.html">
              Bộ sưu tập
            </a>

            <a href="${root}pages/about.html">
              Câu chuyện thương hiệu
            </a>
          </div>

          <div>
            <h3>HỖ TRỢ</h3>

            <a href="${root}index.html#shop">
              Hướng dẫn mua hàng
            </a>

            <button type="button" id="footer-chat">
              Tư vấn trực tuyến
            </button>

            <a href="${root}pages/contact.html">
              Liên hệ
            </a>
          </div>

          <div>
            <h3>ĐỒ ÁN TỐT NGHIỆP</h3>
            <p>
              Mẫu frontend HTML, CSS, JavaScript thuần.<br>
              Dữ liệu hiển thị là dữ liệu demo.
            </p>
          </div>

        </div>

        <div class="container footer-bottom">
          <span>
            © 2026 LUMIÈRE — Academic Prototype
          </span>

          <span>DESIGNED WITH CARE ✧</span>
        </div>
      </footer>
    `;

    // Ở các trang con, chatbot trang chủ không được tải.
    // Dẫn về trang chủ thay vì để nút không phản hồi.
    const chatButton = footer.querySelector("#footer-chat");

    if (chatButton) {
      chatButton.addEventListener("click", () => {
        window.location.assign(root + "index.html");
      });
    }
  }
}

/**
 * Điều hướng theo vai trò.
 *
 * Customer:
 *   Giữ nguyên menu cửa hàng.
 *
 * Admin / Staff:
 *   Giữ menu cửa hàng trên header.
 *   Quản lý nghiệp vụ qua sidebar riêng.
 *   Ẩn Wishlist / Cart không thuộc quyền quản trị.
 */

export function applyRoleNavigation(root, page, user) {
  const role = user?.role || "guest";

  const menu = document.querySelector(".site-nav-links");
  const account = document.querySelector("#account-nav");
  const accountLinks = document.querySelector(".account-links");

  if (!menu || !account || !accountLinks) {
    return false;
  }

  const link = (label, path) =>
    `<a href="${root + path}">${label}</a>`;

  // Giữ menu cửa hàng giống nhau trên tất cả vai trò.
  // Sidebar Admin / Staff không bị tác động.
  const storeMenu = [
    link("Trang chủ", "index.html"),
    link("Sản phẩm", "pages/products.html"),
    link("Bộ sưu tập", "pages/collections.html"),
    link("Giới thiệu", "pages/about.html"),
    link("Liên hệ", "pages/contact.html")
  ].join("");

  menu.innerHTML = storeMenu;

  if (role === "admin" || role === "staff") {
    const isAdmin = role === "admin";

    const roleHome = isAdmin
      ? "pages/admin/dashboard.html"
      : "pages/staff/orders.html";

    // Hiển thị thông tin tài khoản theo vai trò.
    account.href = root + roleHome;
    account.textContent =
      `${user.full_name || (isAdmin ? "Admin" : "Staff")} ` +
      (isAdmin ? "(Admin)" : "(Staff)");

    // Ẩn các công cụ mua sắm dành riêng cho Customer.
    accountLinks.querySelectorAll("a").forEach((anchor) => {
      if (anchor.id === "account-nav") return;

      const url = anchor.getAttribute("href") || "";

      if (
        url.endsWith("pages/wishlist.html") ||
        url.endsWith("pages/cart.html")
      ) {
        anchor.hidden = true;
        anchor.style.display = "none";
      }
    });

    // Không ép Admin / Staff về Dashboard tại đây.
    // Backend vẫn kiểm tra quyền trên từng API.
    return false;
  }

  // Guest / Customer giữ hành vi điều hướng mặc định.
  return false;
}
