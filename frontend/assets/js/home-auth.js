
"use strict";

(async () => {
  const link = document.querySelector('#account-link');
  const menu = document.querySelector('#home-account-menu');

  if (!link || !menu || !window.LUMIERE_API) return;

  try {
    const user = await LUMIERE_API.me();

    if (user.role === "admin" || user.role === "staff") {
      const roleHome =
        user.role === "admin"
          ? "./pages/admin/dashboard.html"
          : "./pages/staff/orders.html";

      link.href = roleHome;
      link.title = "Quay lại khu vực quản lý";
      link.setAttribute("aria-label", "Quay lại khu vực quản lý");
      link.hidden = false;
      menu.hidden = true;

      return;
    }

    if (user.role !== "customer") return;

    link.hidden = true;
    menu.hidden = false;

    document.querySelector('#home-account-name').textContent =
      user.full_name || 'Tài khoản';

    const logout = document.querySelector('#home-logout');

    logout.addEventListener('click', async () => {
      logout.disabled = true;

      try {
        await LUMIERE_API.logout();
        location.href = './pages/login.html';
      } catch (error) {
        document.querySelector('#home-logout-error').textContent =
          error.message || 'Không thể đăng xuất.';

        logout.disabled = false;
      }
    });

    document.addEventListener('click', event => {
      if (!menu.contains(event.target)) {
        menu.open = false;
      }
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        menu.open = false;
      }
    });

  } catch {
    link.href = './pages/login.html';
  }
})();
