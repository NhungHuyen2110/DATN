import { esc } from "./ui.mjs";

export function consoleShell(mount, section, role, root) {
    const labels = {
      dashboard: "Tổng quan", products: "Sản phẩm", orders: "Đơn hàng",
      customers: "Khách hàng", staff: "Nhân viên", coupons: "Mã giảm giá",
      inventory: "Tồn kho", analytics: "Phân tích doanh thu",
      categories: "Danh mục", brands: "Thương hiệu", contacts: "Liên hệ"
    };
    const links = role === "staff"
      ? [["orders", "Đơn hàng"], ["inventory", "Tồn kho"]]
      : Object.entries(labels).map(([key, label]) => [key, label]);
    mount.innerHTML = `<div class="admin-layout">
      <nav class="admin-side">${links.map(([key, label]) =>
        `<a class="${key === section ? "active" : ""}" href="${key}.html">${label}</a>`
      ).join("")}<a href="${root}index.html">← Về cửa hàng</a></nav>
      <section class="backend-console"><h2>${esc(labels[section] || "Quản trị")}</h2><div id="console-body"></div></section>
    </div>`;
    return mount.querySelector("#console-body");
  }
