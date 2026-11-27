"use strict";

(() => {
  const api = window.LUMIERE_API;
  const root = document.body.dataset.root || "../../";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
  const money = value => Number(value || 0).toLocaleString("vi-VN") + " ₫";
  const statusNames = {
    pending: "Chờ xác nhận",
    confirmed: "Đã xác nhận",
    packing: "Đang đóng gói",
    shipping: "Đang giao",
    delivered: "Đã giao",
    cancelled: "Đã hủy"
  };
  const paymentNames = { unpaid: "Chưa thanh toán", paid: "Đã thanh toán", refunded: "Đã hoàn tiền" };

  
function shell(mount, section, role) {
  const labels = {
    dashboard: "Tổng quan",
    products: "Sản phẩm",
    orders: "Đơn hàng",
    customers: "Khách hàng",
    staff: "Nhân viên",
    coupons: "Mã giảm giá",
    inventory: "Tồn kho",
    analytics: "Phân tích doanh thu",
    categories: "Danh mục",
    brands: "Thương hiệu",
    contacts: "Liên hệ",
  };

  const icons = {
    dashboard: `
      <rect x="3" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/>
      <rect x="14" y="14" width="7" height="7" rx="1"/>
    `,

    products: `
      <path d="M6 3h12l4 6-10 12L2 9Z"/>
      <path d="M2 9h20M6 3l6 18 6-18"/>
    `,

    orders: `
      <rect x="5" y="4" width="14" height="17" rx="2"/>
      <path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h4"/>
    `,

    customers: `
      <circle cx="9" cy="7" r="3"/>
      <path d="M3 21v-3a6 6 0 0 1 12 0v3"/>
      <path d="M16 4a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v2"/>
    `,

    staff: `
      <circle cx="12" cy="7" r="4"/>
      <path d="M4 21v-2a8 8 0 0 1 16 0v2"/>
    `,

    coupons: `
      <path d="M3 5h18v4a3 3 0 0 0 0 6v4H3v-4a3 3 0 0 0 0-6Z"/>
      <path d="m9 15 6-6"/>
      <circle cx="9" cy="9" r=".7"/>
      <circle cx="15" cy="15" r=".7"/>
    `,

    inventory: `
      <path d="m12 3 9 5v8l-9 5-9-5V8Z"/>
      <path d="m3 8 9 5 9-5M12 13v8M7.5 5.5l9 5"/>
    `,

    analytics: `
      <path d="M3 3v18h18"/>
      <path d="M7 16v-5M12 16V7M17 16V4"/>
    `,

    categories: `
      <rect x="3" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/>
      <rect x="14" y="14" width="7" height="7" rx="1"/>
    `,

    brands: `
      <path d="M3 3h9l9 9-9 9-9-9Z"/>
      <circle cx="7.5" cy="7.5" r="1"/>
    `,

    contacts: `
      <rect x="3" y="5" width="18" height="14" rx="2"/>
      <path d="m3 7 9 6 9-6"/>
    `,

    store: `
      <path d="M3 9l2-5h14l2 5v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0Z"/>
      <path d="M5 14v7h14v-7M9 21v-6h6v6"/>
    `,
  };

  const menuIcon = (key) => `
    <svg class="management-nav-icon"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true">
      ${icons[key] || ""}
    </svg>
  `;

  const links =
    role === "staff"
      ? [
          ["orders", "Đơn hàng"],
          ["inventory", "Tồn kho"],
        ]
      : Object.entries(labels);

  mount.innerHTML = `
    <div class="admin-layout">

      <nav class="admin-side"
        aria-label="Menu quản lý">

        <div class="management-nav-heading">
          ${role === "staff" ? "NHÂN VIÊN" : "QUẢN TRỊ"}

        </div>

        <div class="management-nav-links">

          ${links
            .map(
              ([key, label]) => `
            <a class="${key === section ? "active" : ""}"
              href="${key}.html"
              ${key === section ? 'aria-current="page"' : ""}>

              ${menuIcon(key)}

              <span>${esc(label)}</span>

            </a>
          `,
            )
            .join("")}

        </div>

        <a class="management-nav-back"
          href="${root}index.html">

          ${menuIcon("store")}

          <span>Về cửa hàng</span>

        </a>

      </nav>

      <section class="backend-console">

        <h2>${esc(labels[section] || "Quản trị")}</h2>

        <div id="console-body"></div>

      </section>

    </div>
  `;

  return mount.querySelector("#console-body");
}


  function showError(target, error) {
    target.innerHTML = `<div class="form-alert" role="alert">${esc(error.message || error)}</div>`;
  }
  function showManagementToast(message, type = "success") {
    document.querySelector(".management-toast")?.remove();

    const isError = type === "error";
    const duration = isError ? 7000 : 4000;

    const toast = document.createElement("div");

    toast.className = `management-toast ${isError ? "is-error" : "is-success"}`;

    toast.setAttribute("role", isError ? "alert" : "status");
    toast.setAttribute("aria-live", isError ? "assertive" : "polite");

    toast.style.setProperty("--toast-duration", `${duration}ms`);

    toast.innerHTML = `
    <div class="management-toast-icon">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        ${
          isError
            ? '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/>'
            : '<path d="m5 12 4 4L19 6"/>'
        }
      </svg>
    </div>

    <div class="management-toast-copy">
      <strong>${isError ? "Không thành công" : "Thành công"}</strong>
      <p>${esc(message)}</p>
    </div>

    <button type="button"
      aria-label="Đóng thông báo">×</button>

    <div class="management-toast-progress"></div>
  `;

    document.body.appendChild(toast);

    const timer = setTimeout(() => toast.remove(), duration);

    toast.querySelector("button").onclick = () => {
      clearTimeout(timer);
      toast.remove();
    };
  }

  function showSuccessToast(message) {
    showManagementToast(message, "success");
  }

  function showErrorToast(error) {
    showManagementToast(
      error?.message || String(error || "Vui lòng thử lại."),
      "error",
    );
  }


  async function loadAllProducts(admin = false) {
    const rows = [];
    let page = 1;
    let total = 0;
    do {
      const payload = admin
        ? await api.adminProducts(page, 100)
        : await api.products(page, 100);
      rows.push(...payload.items);
      total = payload.total;
      page += 1;
    } while (rows.length < total);
    return rows;
  }

  async function renderOrders(target, role, page = 1) {
    const isAdmin = role === "admin";
    const pageSize = 10;

    const normalize = (value) =>
      String(value ?? "")
        .toLocaleLowerCase("vi")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .trim();

    const payload = isAdmin
      ? await api.adminOrders(1, 100)
      : await api.staffOrders(page, pageSize);

    const orders = [...payload.items];

    if (isAdmin) {
      let nextPage = 2;

      while (orders.length < payload.total) {
        const result = await api.adminOrders(nextPage, 100);

        if (!result.items.length) break;

        orders.push(...result.items);
        nextPage++;
      }
    }

    const enrichedOrders = await Promise.all(
      orders.map(async (order) => {
        if (order.recipient_name && order.phone) {
          return order;
        }

        try {
          const path = isAdmin
            ? `/orders/${order.id}`
            : `/staff/orders/${order.id}`;

          const detail = await api.request(path);

          return {
            ...order,
            recipient_name: detail.recipient_name,
            phone: detail.phone,
          };
        } catch (error) {
          console.warn("Không tải được người nhận:", order.id, error);
          return order;
        }
      }),
    );

    const pending = orders.filter((o) => o.status === "pending").length;

    const processing = orders.filter((o) =>
      ["confirmed", "packing", "shipping"].includes(o.status),
    ).length;

    const delivered = orders.filter((o) => o.status === "delivered").length;

    target.innerHTML = `
    <div class="panel management-orders-panel ${isAdmin ? "" : "staff-orders-panel"}">

      <p class="orders-description">
        Theo dõi và xử lý đơn hàng của khách hàng.
      </p>

      ${
        isAdmin
          ? `
        <div class="order-kpis">

          <article class="order-kpi">
            <span>Tổng đơn hàng</span>
            <strong>${payload.total}</strong>
            <small>Toàn bộ đơn hàng</small>
          </article>

          <article class="order-kpi">
            <span>Chờ xác nhận</span>
            <strong>${pending}</strong>
            <small>Đơn hàng cần tiếp nhận</small>
          </article>

          <article class="order-kpi">
            <span>Đang xử lý</span>
            <strong>${processing}</strong>
            <small>Xác nhận, đóng gói và giao hàng</small>
          </article>

          <article class="order-kpi">
            <span>Đã giao</span>
            <strong>${delivered}</strong>
            <small>Đã giao đến khách hàng</small>
          </article>

        </div>
      `
          : ""
      }

      <div class="order-list-heading">
        <h3>Danh sách đơn hàng</h3>
      </div>

      <div class="management-orders-toolbar">

        <label>
          <span>Tìm kiếm</span>
          <input id="orders-search"
            type="search"
            placeholder="Tìm mã đơn, tên, số điện thoại...">
        </label>

        <label>
          <span>Trạng thái đơn hàng</span>
          <select id="orders-filter-status">
            <option value="">Tất cả trạng thái</option>

            ${Object.entries(statusNames)
              .map(
                ([value, label]) =>
                  `<option value="${value}">${label}</option>`,
              )
              .join("")}
          </select>
        </label>

        <label>
          <span>Thanh toán</span>
          <select id="orders-filter-payment">
            <option value="">Tất cả thanh toán</option>
            <option value="paid">Đã thanh toán</option>
            <option value="unpaid">Chưa thanh toán</option>
            <option value="refunded">Đã hoàn tiền</option>
          </select>
        </label>

      </div>

      <p id="orders-count" class="mini-note"></p>

      <div class="table-wrap">
        <table class="data-table management-orders-table">

          <thead>
            <tr>
              <th>Mã đơn / Ngày đặt</th>
              <th>Người nhận</th>
              <th>Trạng thái</th>
              <th>Thanh toán</th>
              <th>Tổng tiền</th>
              <th>Thao tác</th>
            </tr>
          </thead>

          <tbody>
            ${enrichedOrders
              .map((order) => {
                const code = String(order.code || "");

                const shortCode =
                  code.length > 17
                    ? code.slice(0, 8) + "…" + code.slice(-6)
                    : code;

                const canCollectCod =
                  order.status === "delivered" &&
                  order.payment_status === "unpaid" &&
                  order.payment_method === "cod";

                return `
                <tr
                  data-order-code="${esc(code)}"
                  data-phone="${esc(order.phone || "")}"
                  data-recipient="${esc(order.recipient_name || "")}"
                  data-payment="${esc(order.payment_status)}">

                  <td>
                    <strong class="order-code"
                      title="${esc(code)}">
                      ${esc(shortCode)}
                    </strong>

                    <small class="order-secondary">
                      ${new Date(order.created_at).toLocaleDateString("vi-VN")}
                    </small>
                  </td>

                  <td>
                    <strong class="order-recipient">
                      ${esc(order.recipient_name || "—")}
                    </strong>

                    <small class="order-secondary">
                      ${esc(order.phone || "")}
                    </small>
                  </td>

                  <td>
                    <select
                      class="order-status-select status-${esc(order.status)}"
                      data-status="${order.id}"
                      aria-label="Trạng thái ${esc(code)}">

                      ${Object.entries(statusNames)
                        .map(
                          ([value, label]) =>
                            `<option value="${value}"
                          ${order.status === value ? "selected" : ""}>
                          ${label}
                        </option>`,
                        )
                        .join("")}

                    </select>
                  </td>

                  <td>
                    <span class="order-payment payment-${esc(order.payment_status)}">
                      ${esc(paymentNames[order.payment_status] || order.payment_status)}
                    </span>

                    <small class="order-secondary">
                      ${esc(String(order.payment_method || "").toUpperCase())}
                    </small>
                  </td>

                  <td class="order-total">
                    ${money(order.total_vnd)}
                  </td>

                  <td>
                    <div class="order-row-actions">

                      <button class="button-sm"
                        type="button"
                        data-detail="${order.id}">
                        Chi tiết
                      </button>

                      ${
                        canCollectCod
                          ? `
                        <button class="button-sm order-cod-button"
                          type="button"
                          data-cod="${order.id}">
                          Xác nhận thu COD
                        </button>
                      `
                          : ""
                      }

                    </div>
                  </td>
                </tr>
              `;
              })
              .join("")}

            <tr id="orders-empty" hidden>
              <td colspan="6">
                Không tìm thấy đơn hàng phù hợp.
              </td>
            </tr>

          </tbody>
        </table>
      </div>

      <div class="ap-pager">

        <span id="orders-page-info"></span>

        <div class="ap-page-actions">
          <button type="button" id="orders-prev">
            ← Trước
          </button>

          <button type="button" id="orders-next">
            Sau →
          </button>
        </div>

      </div>

      <div id="order-detail"></div>

    </div>
  `;

    const searchInput = target.querySelector("#orders-search");
    const statusFilter = target.querySelector("#orders-filter-status");
    const paymentFilter = target.querySelector("#orders-filter-payment");

    const previous = target.querySelector("#orders-prev");
    const next = target.querySelector("#orders-next");

    const tableRows = [
      ...target.querySelectorAll(
        ".management-orders-table tbody tr[data-order-code]",
      ),
    ];

    let currentPage = page;
    let totalPages = 1;

    searchInput.value = target.dataset.orderSearch || "";
    statusFilter.value = target.dataset.orderStatus || "";
    paymentFilter.value = target.dataset.orderPayment || "";

    function applyOrderFilters(resetPage = false) {
      if (resetPage && isAdmin) currentPage = 1;

      const keyword = normalize(searchInput.value);
      const selectedStatus = statusFilter.value;
      const selectedPayment = paymentFilter.value;

      const matched = tableRows.filter((row) => {
        const searchable = normalize(
          row.dataset.orderCode +
            " " +
            row.dataset.recipient +
            " " +
            row.dataset.phone,
        );

        const status = row.querySelector("[data-status]").value;

        return (
          searchable.includes(keyword) &&
          (!selectedStatus || status === selectedStatus) &&
          (!selectedPayment || row.dataset.payment === selectedPayment)
        );
      });

      totalPages = Math.max(
        1,
        Math.ceil(
          (isAdmin ? matched.length : payload.total) /
            (isAdmin ? pageSize : payload.page_size),
        ),
      );

      currentPage = Math.min(currentPage, totalPages);

      const start = isAdmin ? (currentPage - 1) * pageSize : 0;

      const visible = new Set(
        isAdmin ? matched.slice(start, start + pageSize) : matched,
      );

      tableRows.forEach((row) => {
        row.hidden = !visible.has(row);
      });

      target.querySelector("#orders-empty").hidden = matched.length !== 0;

      target.querySelector("#orders-count").textContent = isAdmin
        ? `Hiển thị ${matched.length ? start + 1 : 0}–${Math.min(start + pageSize, matched.length)} / ${matched.length} đơn hàng`
        : `${matched.length} đơn phù hợp trên trang hiện tại`;

      target.querySelector("#orders-page-info").textContent =
        `Trang ${currentPage} / ${totalPages}`;

      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= totalPages;
    }

    searchInput.addEventListener("input", () => {
      target.dataset.orderSearch = searchInput.value;
      applyOrderFilters(true);
    });

    statusFilter.addEventListener("change", () => {
      target.dataset.orderStatus = statusFilter.value;
      applyOrderFilters(true);
    });

    paymentFilter.addEventListener("change", () => {
      target.dataset.orderPayment = paymentFilter.value;
      applyOrderFilters(true);
    });

    previous.onclick = () => {
      if (isAdmin) {
        currentPage--;
        applyOrderFilters();
      } else {
        renderOrders(target, role, currentPage - 1).catch((error) =>
          showError(target, error),
        );
      }
    };

    next.onclick = () => {
      if (isAdmin) {
        currentPage++;
        applyOrderFilters();
      } else {
        renderOrders(target, role, currentPage + 1).catch((error) =>
          showError(target, error),
        );
      }
    };

    applyOrderFilters();

    target.querySelectorAll("[data-status]").forEach((select) => {
      select.addEventListener("change", async () => {
        const order = enrichedOrders.find(
          (item) => Number(item.id) === Number(select.dataset.status),
        );

        select.disabled = true;

        try {
          await api.updateOrderStatus(
            select.dataset.status,
            select.value,
            role,
          );
        } catch (error) {
          if (order) select.value = order.status;

          select.disabled = false;
          showErrorToast(error);
          return;
        }

        showSuccessToast("Đã cập nhật trạng thái đơn hàng.");

        try {
          await renderOrders(target, role, currentPage);
        } catch (error) {
          showError(target, error);
        }
      });
    });
    target.querySelectorAll("[data-detail]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;

        try {
          const path =
            role === "admin"
              ? `/orders/${button.dataset.detail}`
              : `/staff/orders/${button.dataset.detail}`;

          const order = await api.request(path);

          const summary =
            enrichedOrders.find(
              (item) => Number(item.id) === Number(button.dataset.detail),
            ) || {};

          const status = order.status ?? summary.status;
          const paymentStatus = order.payment_status ?? summary.payment_status;
          const paymentMethod = order.payment_method ?? summary.payment_method;

          const dialog = document.createElement("dialog");
          dialog.className = "stock-dialog staff-order-dialog";
          dialog.setAttribute("aria-labelledby", "staff-order-title");

          dialog.innerHTML = `
        <div class="stock-dialog-head">
          <div>
            <small class="staff-order-eyebrow">
              CHI TIẾT ĐƠN HÀNG
            </small>

            <h2 id="staff-order-title">
              ${esc(order.code)}
            </h2>
          </div>

          <button type="button"
            data-close-order aria-label="Đóng">×</button>
        </div>

        <div class="staff-order-info">

          <div>
            <h3>Thông tin người nhận</h3>
            <strong>${esc(order.recipient_name)}</strong>
            <p>${esc(order.phone)}</p>
            <p>${esc(order.address)}</p>
          </div>

          <div>
            <h3>Thông tin đơn hàng</h3>

            <p>
              ${esc(statusNames[status] || status || "—")}
            </p>

            <p>
              ${
                paymentMethod === "cod"
                  ? "Thanh toán khi nhận hàng"
                  : esc(String(paymentMethod || "—").toUpperCase())
              }
            </p>

            <p>
              ${esc(paymentNames[paymentStatus] || paymentStatus || "—")}
            </p>
          </div>

        </div>

        <h3 class="staff-order-items-title">
          Sản phẩm trong đơn
        </h3>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Sản phẩm</th>
                <th>SL</th>
                <th>Đơn giá</th>
                <th>Thành tiền</th>
              </tr>
            </thead>

            <tbody>
              ${order.items
                .map(
                  (item) => `
                <tr>
                  <td>
                    <strong>${esc(item.product_name)}</strong>
                    <small class="staff-order-sku">
                      ${esc(item.sku)}
                    </small>
                  </td>

                  <td>${item.quantity}</td>
                  <td>${money(item.unit_price_vnd)}</td>
                  <td>${money(item.line_total_vnd)}</td>
                </tr>
              `,
                )
                .join("")}
            </tbody>
          </table>
        </div>

        <div class="staff-order-total">
          <span>Tổng thanh toán</span>
          <strong>${money(order.total_vnd ?? summary.total_vnd)}</strong>
        </div>

        <div class="stock-dialog-actions">
          <button type="button"
            class="button button-dark"
            data-close-order>
            Đóng
          </button>
        </div>
      `;

          target.appendChild(dialog);

          dialog.querySelectorAll("[data-close-order]").forEach((close) => {
            close.onclick = () => dialog.close();
          });

          dialog.addEventListener("close", () => dialog.remove());

          dialog.showModal();
        } catch (error) {
          showErrorToast(error);
        } finally {
          button.disabled = false;
        }
      });
    });
    target.querySelectorAll("[data-cod]").forEach((button) => {
      button.addEventListener("click", () => {
        const order = enrichedOrders.find(
          (item) => Number(item.id) === Number(button.dataset.cod),
        );

        if (!order) return;

        const dialog = document.createElement("dialog");

        dialog.className = "stock-dialog";
        dialog.setAttribute("aria-labelledby", "cod-dialog-title");

        dialog.innerHTML = `
      <div class="stock-dialog-head">
        <h2 id="cod-dialog-title">Xác nhận thu COD</h2>

        <button type="button" id="cod-close"
          aria-label="Đóng">×</button>
      </div>

      <form id="cod-form">

        <p class="mini-note">
          Mã đơn hàng: ${esc(order.code)}
        </p>

        <div class="stock-current">
          <span>Số tiền cần thu</span>
          <strong>${money(order.total_vnd)}</strong>
        </div>

        <label class="field">
          <span>Mã biên nhận COD</span>

          <input id="cod-reference"
            type="text"
            placeholder="Nhập mã biên nhận..."
            minlength="3"
            required>

          <small>
            Chỉ xác nhận khi đã thực nhận tiền
            thanh toán của đơn hàng.
          </small>
        </label>

        <p id="cod-error"
          class="form-alert error"
          role="alert" hidden></p>

        <div class="stock-dialog-actions">
          <button type="button"
            class="button button-outline"
            id="cod-cancel">Hủy bỏ</button>

          <button type="submit"
            class="button button-dark"
            id="cod-save">Xác nhận đã thu</button>
        </div>

      </form>
    `;

        target.appendChild(dialog);

        const save = dialog.querySelector("#cod-save");
        const cancel = dialog.querySelector("#cod-cancel");
        const close = dialog.querySelector("#cod-close");
        const errorBox = dialog.querySelector("#cod-error");

        let saving = false;

        cancel.onclick = close.onclick = () => dialog.close();

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        dialog.querySelector("#cod-form").onsubmit = async (event) => {
          event.preventDefault();

          if (saving) return;

          const reference = dialog.querySelector("#cod-reference").value.trim();

          if (reference.length < 3) {
            errorBox.textContent = "Mã biên nhận phải có ít nhất 3 ký tự.";
            errorBox.hidden = false;
            return;
          }

          saving = true;
          save.disabled = cancel.disabled = close.disabled = true;
          save.textContent = "Đang xác nhận...";
          errorBox.hidden = true;

          try {
            await api.confirmCod(button.dataset.cod, reference, role);
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;

            saving = false;
            save.disabled = cancel.disabled = close.disabled = false;
            save.textContent = "Xác nhận đã thu";
            return;
          }

          dialog.close();

          try {
            await renderOrders(target, role, currentPage);
            showSuccessToast("Đã xác nhận thu COD thành công.");
          } catch (error) {
            showError(target, error);
          }
        };

        dialog.showModal();
      });
    });
  }

  
async function renderCustomers(target) {
  let page = 1;
  let search = "";
  let active = "";
  const pageSize = 10;

  async function draw() {
    const filters = {
      search,
      ...(active === "" ? {} : { is_active: active === "active" }),
    };

    const [result, all, activeResult, lockedResult] = await Promise.all([
      api.adminCustomers(page, pageSize, filters),
      api.adminCustomers(1, 1, {}),
      api.adminCustomers(1, 1, { is_active: true }),
      api.adminCustomers(1, 1, { is_active: false }),
    ]);

    const totalPages = Math.max(1, Math.ceil(result.total / pageSize));

    if (page > totalPages) {
      page = totalPages;
      return draw();
    }

    target.innerHTML = `
      <div class="panel management-customers-panel">

        <p class="customers-description">
          Quản lý thông tin và tài khoản khách hàng của cửa hàng.
        </p>

        <div class="customer-kpis">

          <article class="order-kpi">
            <span>Tổng khách hàng</span>
            <strong>${all.total}</strong>
            <small>Toàn bộ tài khoản khách hàng</small>
          </article>

          <article class="order-kpi">
            <span>Đang hoạt động</span>
            <strong>${activeResult.total}</strong>
            <small>Tài khoản đang được sử dụng</small>
          </article>

          <article class="order-kpi">
            <span>Đã khóa</span>
            <strong>${lockedResult.total}</strong>
            <small>Tài khoản bị hạn chế truy cập</small>
          </article>

        </div>

        <div class="order-list-heading">
          <h3>Danh sách khách hàng</h3>
        </div>

        <div class="management-customers-toolbar">

          <label>
            <span>Tìm kiếm</span>

            <input id="customer-search"
              type="search"
              value="${esc(search)}"
              placeholder="Tìm tên, email, số điện thoại...">
          </label>

          <label>
            <span>Trạng thái tài khoản</span>

            <select id="customer-active">
              <option value="">Tất cả trạng thái</option>

              <option value="active"
                ${active === "active" ? "selected" : ""}>
                Đang hoạt động
              </option>

              <option value="locked"
                ${active === "locked" ? "selected" : ""}>
                Đã khóa
              </option>
            </select>
          </label>

        </div>

        <p class="mini-note customer-result-count">
          Hiển thị
          ${result.total ? (page - 1) * pageSize + 1 : 0}–${Math.min(page * pageSize, result.total)}
          / ${result.total} khách hàng
        </p>

        <div class="table-wrap">

          <table class="data-table management-customers-table">

            <thead>
              <tr>
                <th>Khách hàng</th>
                <th>Ngày tham gia</th>
                <th>Số đơn</th>
                <th>Chi tiêu</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>

            <tbody>

              ${
                result.items
                  .map(
                    (customer) => `
                <tr>

                  <td>
                    <div class="customer-identity">

                      <div class="customer-avatar">
                        <svg viewBox="0 0 24 24"
                          fill="none" aria-hidden="true">
                          <circle cx="12" cy="8" r="3.5"/>
                          <path d="M5 21c0-5 3-8 7-8s7 3 7 8"/>
                        </svg>
                      </div>

                      <div class="customer-identity-copy">

                        <strong>
                          ${esc(customer.full_name)}
                        </strong>

                        <small>
                          ${esc(customer.email)}
                        </small>

                        <small>
                          ${esc(customer.phone || "Chưa có số điện thoại")}
                        </small>

                      </div>
                    </div>
                  </td>

                  <td>
                    ${new Date(customer.created_at).toLocaleDateString("vi-VN")}
                  </td>

                  <td>${customer.order_count}</td>

                  <td class="customer-spent">
                    ${money(customer.total_spent_vnd)}
                  </td>

                  <td>
                    <span class="management-customer-status
                      ${customer.is_active ? "is-active" : "is-locked"}">

                      ${customer.is_active ? "Hoạt động" : "Đã khóa"}

                    </span>
                  </td>

                  <td>
                    <div class="customer-row-actions">

                      <button class="button-sm"
                        type="button"
                        data-detail="${customer.id}">
                        Chi tiết
                      </button>

                      <button class="button-sm customer-toggle
                        ${customer.is_active ? "lock-action" : "unlock-action"}"
                        type="button"
                        data-toggle="${customer.id}">

                        ${customer.is_active ? "Khóa tài khoản" : "Mở khóa"}

                      </button>

                    </div>
                  </td>

                </tr>
              `,
                  )
                  .join("") ||
                `
                <tr>
                  <td colspan="6" class="customer-empty">
                    Không tìm thấy khách hàng phù hợp.
                  </td>
                </tr>
              `
              }

            </tbody>

          </table>

        </div>

        <div class="ap-pager">

          <span>Trang ${page} / ${totalPages}</span>

          <div class="ap-page-actions">
            <button type="button" id="customer-prev"
              ${page <= 1 ? "disabled" : ""}>
              ← Trước
            </button>

            <button type="button" id="customer-next"
              ${page >= totalPages ? "disabled" : ""}>
              Sau →
            </button>
          </div>

        </div>

      </div>
    `;

    const searchInput = target.querySelector("#customer-search");
    const statusFilter = target.querySelector("#customer-active");

    searchInput.addEventListener("change", () => {
      search = searchInput.value.trim();
      page = 1;
      draw().catch((error) => showErrorToast(error));
    });

    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        searchInput.blur();
      }
    });

    statusFilter.addEventListener("change", () => {
      active = statusFilter.value;
      page = 1;
      draw().catch((error) => showErrorToast(error));
    });

    target.querySelector("#customer-prev").onclick = () => {
      page--;
      draw().catch((error) => showErrorToast(error));
    };

    target.querySelector("#customer-next").onclick = () => {
      page++;
      draw().catch((error) => showErrorToast(error));
    };

    // Modal xem chi tiết khách hàng

    target.querySelectorAll("[data-detail]").forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;

        try {
          const customer = await api.customer(button.dataset.detail);

          const dialog = document.createElement("dialog");
          dialog.className = "stock-dialog customer-detail-dialog";

          dialog.innerHTML = `
            <div class="stock-dialog-head">
              <h2>Chi tiết khách hàng</h2>
              <button type="button" data-close
                aria-label="Đóng">×</button>
            </div>

            <div class="customer-detail-profile">
              <div class="customer-avatar">
                <svg viewBox="0 0 24 24" fill="none"
                  aria-hidden="true">
                  <circle cx="12" cy="8" r="3.5"/>
                  <path d="M5 21c0-5 3-8 7-8s7 3 7 8"/>
                </svg>
              </div>

              <div>
                <strong>${esc(customer.full_name)}</strong>
                <small>Khách hàng LUMIÈRE</small>
              </div>
            </div>

            <dl class="customer-detail-info">

              <div>
                <dt>Email</dt>
                <dd>${esc(customer.email)}</dd>
              </div>

              <div>
                <dt>Số điện thoại</dt>
                <dd>${esc(customer.phone || "Chưa cập nhật")}</dd>
              </div>

              <div>
                <dt>Trạng thái</dt>
                <dd>
                  <span class="management-customer-status
                    ${customer.is_active ? "is-active" : "is-locked"}">
                    ${customer.is_active ? "Hoạt động" : "Đã khóa"}
                  </span>
                </dd>
              </div>

            </dl>

            <div class="customer-detail-stats">

              <article>
                <span>Tổng đơn hàng</span>
                <strong>${customer.order_count}</strong>
              </article>

              <article>
                <span>Tổng chi tiêu</span>
                <strong>${money(customer.total_spent_vnd)}</strong>
              </article>

            </div>

            <div class="stock-dialog-actions">
              <button type="button"
                class="button button-dark"
                data-close>Đóng</button>
            </div>
          `;

          target.appendChild(dialog);

          dialog.querySelectorAll("[data-close]").forEach((close) => {
            close.onclick = () => dialog.close();
          });

          dialog.addEventListener("close", () => dialog.remove());
          dialog.showModal();
        } catch (error) {
          showErrorToast(error);
        } finally {
          button.disabled = false;
        }
      };
    });

    // Modal xác nhận khóa hoặc mở khóa

    target.querySelectorAll("[data-toggle]").forEach((button) => {
      button.onclick = () => {
        const customer = result.items.find(
          (item) => Number(item.id) === Number(button.dataset.toggle),
        );

        if (!customer) return;

        const locking = customer.is_active;

        const dialog = document.createElement("dialog");
        dialog.className = "stock-dialog customer-confirm-dialog";

        dialog.innerHTML = `
          <div class="stock-dialog-head">
            <h2>${locking ? "Khóa tài khoản" : "Mở khóa tài khoản"}</h2>
            <button type="button" data-close
              aria-label="Đóng">×</button>
          </div>

          <p class="customer-confirm-message">
            Bạn có chắc chắn muốn
            ${locking ? "khóa" : "mở khóa"}
            tài khoản của
            <strong>${esc(customer.full_name)}</strong>?
          </p>

          <p class="mini-note">
            ${
              locking
                ? "Khách hàng sẽ bị hạn chế truy cập tài khoản sau khi khóa."
                : "Khách hàng có thể sử dụng lại tài khoản sau khi mở khóa."
            }
          </p>

          <p class="form-alert error"
            id="customer-toggle-error"
            role="alert" hidden></p>

          <div class="stock-dialog-actions">

            <button type="button"
              class="button button-outline"
              data-close>Hủy bỏ</button>

            <button type="button"
              class="button button-dark"
              id="customer-toggle-save">

              ${locking ? "Xác nhận khóa" : "Xác nhận mở khóa"}

            </button>

          </div>
        `;

        target.appendChild(dialog);

        const save = dialog.querySelector("#customer-toggle-save");
        const errorBox = dialog.querySelector("#customer-toggle-error");
        const closes = dialog.querySelectorAll("[data-close]");

        let saving = false;

        closes.forEach((close) => {
          close.onclick = () => dialog.close();
        });

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        save.onclick = async () => {
          if (saving) return;

          saving = true;
          save.disabled = true;
          save.textContent = "Đang xử lý...";
          errorBox.hidden = true;

          closes.forEach((close) => (close.disabled = true));

          try {
            await api.setCustomerStatus(customer.id, !locking);
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;

            saving = false;
            save.disabled = false;
            save.textContent = locking ? "Xác nhận khóa" : "Xác nhận mở khóa";

            closes.forEach((close) => (close.disabled = false));
            return;
          }

          dialog.close();

          showSuccessToast(
            locking
              ? "Đã khóa tài khoản khách hàng."
              : "Đã mở khóa tài khoản khách hàng.",
          );

          try {
            await draw();
          } catch (error) {
            showError(target, error);
          }
        };

        dialog.showModal();
      };
    });
  }

  await draw();
}


  
async function renderStaff(target) {
  let currentPage = 1;
  let search = "";
  let active = "";

  const pageSize = 10;

  const avatar = `
    <div class="customer-avatar">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5"/>
        <path d="M5 21c0-5 3-8 7-8s7 3 7 8"/>
      </svg>
    </div>
  `;

  function normalize(value) {
    return String(value ?? "")
      .toLocaleLowerCase("vi")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .trim();
  }

  async function draw() {
    const result = await api.adminStaff(1, 20);
    const rows = [...result.items];

    let nextPage = 2;

    while (rows.length < result.total) {
      const next = await api.adminStaff(nextPage, 20);

      if (!next.items.length) break;

      rows.push(...next.items);
      nextPage++;
    }

    const activeCount = rows.filter((staff) => staff.is_active).length;

    const lockedCount = rows.filter((staff) => !staff.is_active).length;

    target.innerHTML = `
      <div class="panel management-staff-panel">

        <div class="management-staff-head">
          <p class="customers-description">
            Quản lý thông tin và tài khoản nhân viên của cửa hàng.
          </p>

          <button type="button"
            class="button button-dark"
            id="staff-create">
            + Thêm nhân viên
          </button>
        </div>

        <div class="customer-kpis">

          <article class="order-kpi">
            <span>Tổng nhân viên</span>
            <strong>${rows.length}</strong>
            <small>Toàn bộ tài khoản nhân viên</small>
          </article>

          <article class="order-kpi">
            <span>Đang hoạt động</span>
            <strong>${activeCount}</strong>
            <small>Tài khoản được phép truy cập</small>
          </article>

          <article class="order-kpi">
            <span>Đã khóa</span>
            <strong>${lockedCount}</strong>
            <small>Tài khoản bị hạn chế truy cập</small>
          </article>

        </div>

        <div class="order-list-heading">
          <h3>Danh sách nhân viên</h3>
        </div>

        <div class="management-customers-toolbar">

          <label>
            <span>Tìm kiếm</span>
            <input id="staff-search"
              type="search"
              value="${esc(search)}"
              placeholder="Tìm tên, email, số điện thoại...">
          </label>

          <label>
            <span>Trạng thái tài khoản</span>

            <select id="staff-active">
              <option value="">Tất cả trạng thái</option>
              <option value="active">Đang hoạt động</option>
              <option value="locked">Đã khóa</option>
            </select>
          </label>

        </div>

        <p id="staff-count"
          class="mini-note customer-result-count"></p>

        <div class="table-wrap">

          <table class="data-table management-staff-table">

            <thead>
              <tr>
                <th>Nhân viên</th>
                <th>Số điện thoại</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>

            <tbody>

              ${rows
                .map(
                  (staff) => `
                <tr data-staff-id="${staff.id}">

                  <td>
                    <div class="customer-identity">

                      ${avatar}

                      <div class="customer-identity-copy">
                        <strong>${esc(staff.full_name)}</strong>
                        <small>${esc(staff.email)}</small>
                      </div>

                    </div>
                  </td>

                  <td>${esc(staff.phone || "Chưa cập nhật")}</td>

                  <td>
                    <span class="management-staff-role">
                      Nhân viên
                    </span>
                  </td>

                  <td>
                    <span class="management-customer-status
                      ${staff.is_active ? "is-active" : "is-locked"}">

                      ${staff.is_active ? "Hoạt động" : "Đã khóa"}

                    </span>
                  </td>

                  <td>
                    <div class="customer-row-actions">

                      <button type="button"
                        class="button-sm"
                        data-edit="${staff.id}">
                        Chỉnh sửa
                      </button>

                      <button type="button"
                        class="button-sm
                          ${staff.is_active ? "lock-action" : "unlock-action"}"
                        data-toggle="${staff.id}">

                        ${staff.is_active ? "Khóa tài khoản" : "Mở khóa"}

                      </button>

                    </div>
                  </td>

                </tr>
              `,
                )
                .join("")}

              <tr id="staff-empty" hidden>
                <td colspan="5" class="customer-empty">
                  Không tìm thấy nhân viên phù hợp.
                </td>
              </tr>

            </tbody>
          </table>

        </div>

        <div class="ap-pager">

          <span id="staff-page-info"></span>

          <div class="ap-page-actions">

            <button type="button" id="staff-prev">
              ← Trước
            </button>

            <button type="button" id="staff-next">
              Sau →
            </button>

          </div>
        </div>

      </div>
    `;

    const searchInput = target.querySelector("#staff-search");
    const statusFilter = target.querySelector("#staff-active");

    const previous = target.querySelector("#staff-prev");
    const next = target.querySelector("#staff-next");

    const tableRows = [...target.querySelectorAll("[data-staff-id]")];

    statusFilter.value = active;

    function applyFilters(resetPage = false) {
      if (resetPage) currentPage = 1;

      const keyword = normalize(search);

      const matched = rows.filter((staff) => {
        const searchable = normalize(
          `${staff.full_name} ${staff.email} ${staff.phone || ""}`,
        );

        return (
          searchable.includes(keyword) &&
          (!active ||
            (active === "active" && staff.is_active) ||
            (active === "locked" && !staff.is_active))
        );
      });

      const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));

      currentPage = Math.min(currentPage, totalPages);

      const start = (currentPage - 1) * pageSize;

      const visible = new Set(
        matched.slice(start, start + pageSize).map((staff) => String(staff.id)),
      );

      tableRows.forEach((row) => {
        row.hidden = !visible.has(row.dataset.staffId);
      });

      target.querySelector("#staff-empty").hidden = matched.length !== 0;

      target.querySelector("#staff-count").textContent =
        `Hiển thị ${matched.length ? start + 1 : 0}–${Math.min(start + pageSize, matched.length)} / ${matched.length} nhân viên`;

      target.querySelector("#staff-page-info").textContent =
        `Trang ${currentPage} / ${totalPages}`;

      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= totalPages;
    }

    searchInput.oninput = () => {
      search = searchInput.value;
      applyFilters(true);
    };

    statusFilter.onchange = () => {
      active = statusFilter.value;
      applyFilters(true);
    };

    previous.onclick = () => {
      currentPage--;
      applyFilters();
    };

    next.onclick = () => {
      currentPage++;
      applyFilters();
    };

    applyFilters();

    // Modal thêm hoặc chỉnh sửa nhân viên

    function openStaffEditor(staff = null) {
      const editing = staff !== null;

      const dialog = document.createElement("dialog");
      dialog.className = "stock-dialog staff-editor-dialog";
      dialog.setAttribute("aria-labelledby", "staff-editor-title");

      dialog.innerHTML = `
        <div class="stock-dialog-head">

          <h2 id="staff-editor-title">
            ${editing ? "Chỉnh sửa nhân viên" : "Thêm nhân viên"}
          </h2>

          <button type="button" data-close
            aria-label="Đóng">×</button>

        </div>

        <form id="staff-editor-form">

          <div class="customer-detail-profile">

            ${avatar}

            <div>
              <strong>
                ${editing ? esc(staff.full_name) : "Tài khoản nhân viên mới"}
              </strong>

              <small>Nhân viên LUMIÈRE</small>
            </div>

          </div>

          <label class="field">
            <span>Họ và tên</span>

            <input id="staff-name"
              type="text"
              value="${esc(staff?.full_name || "")}"
              placeholder="Nhập họ tên nhân viên"
              required>
          </label>

          <label class="field">
            <span>Email</span>

            <input id="staff-email"
              type="email"
              value="${esc(staff?.email || "")}"
              placeholder="Nhập địa chỉ email"
              ${editing ? "readonly" : "required"}>

            ${
              editing
                ? "<small>Email đăng nhập không thể chỉnh sửa tại đây.</small>"
                : ""
            }
          </label>

          ${
            !editing
              ? `
            <label class="field">
              <span>Mật khẩu khởi tạo</span>

              <div class="staff-password-field">

                <input id="staff-password"
                  type="password"
                  minlength="8"
                  autocomplete="new-password"
                  placeholder="Tối thiểu 8 ký tự"
                  required>

                <button type="button"
                  id="staff-password-toggle">
                  Hiện
                </button>

              </div>

              <small>Mật khẩu dùng để đăng nhập tài khoản nhân viên.</small>
            </label>
          `
              : ""
          }

          <label class="field">
            <span>Số điện thoại</span>

            <input id="staff-phone"
              type="tel"
              value="${esc(staff?.phone || "")}"
              placeholder="Không bắt buộc">
          </label>

          <div class="staff-role-note">
            <strong>Vai trò: Nhân viên</strong>

            <small>
              Có quyền xử lý đơn hàng và cập nhật tồn kho.
            </small>
          </div>

          <p id="staff-editor-error"
            class="form-alert error"
            role="alert" hidden></p>

          <div class="stock-dialog-actions">

            <button type="button"
              class="button button-outline"
              data-close>Hủy bỏ</button>

            <button type="submit"
              class="button button-dark"
              id="staff-editor-save">

              ${editing ? "Lưu thay đổi" : "Tạo tài khoản"}

            </button>

          </div>

        </form>
      `;

      target.appendChild(dialog);

      const form = dialog.querySelector("#staff-editor-form");
      const save = dialog.querySelector("#staff-editor-save");
      const errorBox = dialog.querySelector("#staff-editor-error");

      const closes = dialog.querySelectorAll("[data-close]");
      const password = dialog.querySelector("#staff-password");
      const passwordToggle = dialog.querySelector("#staff-password-toggle");

      let saving = false;

      if (passwordToggle) {
        passwordToggle.onclick = () => {
          const hidden = password.type === "password";

          password.type = hidden ? "text" : "password";

          passwordToggle.textContent = hidden ? "Ẩn" : "Hiện";
        };
      }

      closes.forEach((close) => {
        close.onclick = () => dialog.close();
      });

      dialog.addEventListener("close", () => dialog.remove());

      dialog.addEventListener("cancel", (event) => {
        if (saving) event.preventDefault();
      });

      form.onsubmit = async (event) => {
        event.preventDefault();

        if (saving) return;

        const full_name = dialog.querySelector("#staff-name").value.trim();

        const email = dialog.querySelector("#staff-email").value.trim();

        const phone = dialog.querySelector("#staff-phone").value.trim() || null;

        if (!full_name || (!editing && (!email || password.value.length < 8))) {
          errorBox.textContent = "Vui lòng nhập đầy đủ thông tin hợp lệ.";

          errorBox.hidden = false;
          return;
        }

        saving = true;
        save.disabled = true;
        save.textContent = "Đang lưu...";
        errorBox.hidden = true;

        closes.forEach((close) => (close.disabled = true));

        try {
          if (editing) {
            await api.updateStaff(staff.id, {
              full_name,
              phone,
            });
          } else {
            await api.createStaff({
              full_name,
              email,
              password: password.value,
              phone,
            });
          }
        } catch (error) {
          errorBox.textContent = error.message;
          errorBox.hidden = false;

          saving = false;
          save.disabled = false;

          save.textContent = editing ? "Lưu thay đổi" : "Tạo tài khoản";

          closes.forEach((close) => (close.disabled = false));
          return;
        }

        dialog.close();

        showSuccessToast(
          editing
            ? "Đã cập nhật thông tin nhân viên."
            : "Đã tạo tài khoản nhân viên thành công.",
        );

        if (!editing) {
          currentPage = 1;
          search = "";
          active = "";
        }

        try {
          await draw();
        } catch (error) {
          showError(target, error);
        }
      };

      dialog.showModal();
    }

    target.querySelector("#staff-create").onclick = () => openStaffEditor();

    target.querySelectorAll("[data-edit]").forEach((button) => {
      button.onclick = () => {
        const staff = rows.find(
          (item) => Number(item.id) === Number(button.dataset.edit),
        );

        if (staff) openStaffEditor(staff);
      };
    });

    // Modal xác nhận khóa hoặc mở khóa nhân viên

    target.querySelectorAll("[data-toggle]").forEach((button) => {
      button.onclick = () => {
        const staff = rows.find(
          (item) => Number(item.id) === Number(button.dataset.toggle),
        );

        if (!staff) return;

        const locking = staff.is_active;

        const dialog = document.createElement("dialog");
        dialog.className = "stock-dialog customer-confirm-dialog";
        dialog.setAttribute("aria-labelledby", "staff-confirm-title");

        dialog.innerHTML = `
          <div class="stock-dialog-head">

            <h2 id="staff-confirm-title">
              ${locking ? "Khóa tài khoản" : "Mở khóa tài khoản"}
            </h2>

            <button type="button" data-close
              aria-label="Đóng">×</button>

          </div>

          <p class="customer-confirm-message">
            Bạn có chắc chắn muốn
            ${locking ? "khóa" : "mở khóa"}
            tài khoản của
            <strong>${esc(staff.full_name)}</strong>?
          </p>

          <p class="mini-note">
            ${
              locking
                ? "Tài khoản sẽ bị hạn chế truy cập hệ thống quản lý."
                : "Nhân viên có thể sử dụng lại tài khoản sau khi mở khóa."
            }
          </p>

          <p id="staff-toggle-error"
            class="form-alert error"
            role="alert" hidden></p>

          <div class="stock-dialog-actions">

            <button type="button"
              class="button button-outline"
              data-close>Hủy bỏ</button>

            <button type="button"
              class="button button-dark"
              id="staff-toggle-save">

              ${locking ? "Xác nhận khóa" : "Xác nhận mở khóa"}

            </button>

          </div>
        `;

        target.appendChild(dialog);

        const save = dialog.querySelector("#staff-toggle-save");
        const errorBox = dialog.querySelector("#staff-toggle-error");
        const closes = dialog.querySelectorAll("[data-close]");

        let saving = false;

        closes.forEach((close) => {
          close.onclick = () => dialog.close();
        });

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        save.onclick = async () => {
          if (saving) return;

          saving = true;
          save.disabled = true;
          save.textContent = "Đang xử lý...";
          errorBox.hidden = true;

          closes.forEach((close) => (close.disabled = true));

          try {
            await api.setStaffStatus(staff.id, !locking);
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;

            saving = false;
            save.disabled = false;

            save.textContent = locking ? "Xác nhận khóa" : "Xác nhận mở khóa";

            closes.forEach((close) => (close.disabled = false));
            return;
          }

          dialog.close();

          showSuccessToast(
            locking
              ? "Đã khóa tài khoản nhân viên."
              : "Đã mở khóa tài khoản nhân viên.",
          );

          try {
            await draw();
          } catch (error) {
            showError(target, error);
          }
        };

        dialog.showModal();
      };
    });
  }

  await draw();
}


  async function renderProducts(target, section, role) {
    const rows = await loadAllProducts(role === "admin");
    const imageFor=item=>item.image_url?api.base+item.image_url:window.LUMIERE_PRODUCTS?.find(row=>row.id===item.id)?.image;
    const categories = [
      ...new Set(rows.map((item) => item.category?.name || "").filter(Boolean)),
    ].sort((a, b) => a.localeCompare(b, "vi"));

    const outOfStock = rows.filter((item) => Number(item.stock) <= 0).length;
    const lowStock = rows.filter(
      (item) => Number(item.stock) > 0 && Number(item.stock) <= 10,
    ).length;
    const inStock = rows.filter((item) => Number(item.stock) > 0).length;
    target.innerHTML = `
      <div class="panel admin-products-panel">
        <div class="admin-products-head">
          <div>
            <p class="inventory-description">
              ${
                role === "staff"
                  ? "Tra cứu sản phẩm và cập nhật số lượng tồn kho."
                  : section === "inventory"
                    ? "Kiểm tra số lượng tồn kho, tìm kiếm nhanh và cập nhật chính xác từng sản phẩm."
                    : "Quản lý danh mục sản phẩm, hình ảnh, giá bán và tình trạng tồn kho."
              }
            </p>
          </div>

          ${
            role === "admin" && section === "products"
              ? `
                <div class="admin-products-head-actions">
                  <button type="button" id="product-create" class="button button-dark">
                    + Thêm sản phẩm
                  </button>
                </div>
              `
              : ""
          }
        </div>

        ${
          role === "admin"
            ? `
              <div class="admin-products-kpis">
                <article class="admin-products-kpi">
                  <span>Tổng sản phẩm</span>
                  <strong>${rows.length}</strong>
                  <small>Toàn bộ sản phẩm hiện có</small>
                </article>

                <article class="admin-products-kpi">
  <span>${section === "inventory" ? "Còn hàng" : "Danh mục"}</span>

  <strong>
    ${section === "inventory" ? inStock : categories.length}
  </strong>

  <small>
    ${
      section === "inventory"
        ? "Sản phẩm còn tồn kho"
        : "Số nhóm sản phẩm đang dùng"
    }
  </small>
</article>

                <article class="admin-products-kpi">
                  <span>Sắp hết hàng</span>
                  <strong>${lowStock}</strong>
                  <small>Tồn kho từ 1 đến 10 sản phẩm</small>
                </article>

                <article class="admin-products-kpi">
                  <span>Hết hàng</span>
                  <strong>${outOfStock}</strong>
                  <small>Cần nhập lại hoặc ẩn sản phẩm</small>
                </article>
              </div>
            `
            : ""
        }

        <div class="admin-products-toolbar">
          <label class="admin-products-search">
            <span>Tìm kiếm</span>
            <input
              id="product-search"
              type="search"
              placeholder="Tìm tên sản phẩm, SKU hoặc ID..."
              aria-label="Tìm sản phẩm"
            >
          </label>

          <label class="admin-products-filter">
            <span>Danh mục</span>
            <select id="product-category" aria-label="Lọc danh mục">
              <option value="">Tất cả danh mục</option>
              ${categories
                .map(
                  (name) =>
                    `<option value="${esc(name)}">${esc(name)}</option>`,
                )
                .join("")}
                    </select>
      </label>

      ${
        role === "admin"
          ? `
        <label class="admin-products-filter">
          <span>Tồn kho</span>
          <select id="product-stock-filter">
            <option value="">Tất cả tồn kho</option>
            <option value="available">Còn hàng</option>
            <option value="low">Sắp hết hàng</option>
            <option value="out">Hết hàng</option>
          </select>
        </label>

        <label class="admin-products-filter">
          <span>Sắp xếp</span>
          <select id="product-sort">
            <option value="default">Mặc định</option>
            <option value="price-asc">Giá thấp đến cao</option>
            <option value="price-desc">Giá cao đến thấp</option>
            <option value="name">Tên A–Z</option>
            <option value="stock-asc">Tồn kho tăng dần</option>
          </select>
        </label>
      `
          : ""
      }

    </div>

    <p id="product-search-count"></p>

        <div class="table-wrap admin-products-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID / SKU</th>
                <th>Sản phẩm</th>
                <th>Danh mục</th>
                <th>Giá bán</th>
                <th>Tồn kho</th>
                <th>${section === "inventory" ? "Điều chỉnh" : "Thao tác"}</th>
              </tr>
            </thead>

            <tbody>
              ${rows
                .map(
                  (item) => `
                <tr data-stock-value="${Number(item.stock)}"
                  data-price-value="${Number(item.price_vnd)}"
                  data-product-name="${esc(item.name)}">

                  <td>
                    <strong>#${item.id}</strong><br>
                    <small>${esc(item.sku)}</small>
                  </td>

                  <td class="admin-product-name-cell">
                    ${
                      imageFor(item)
                        ? `<img class="product-table-image" width="56" height="56" loading="lazy" src="${esc(imageFor(item))}" alt="">`
                        : `<span class="product-table-image product-table-image--placeholder"></span>`
                    }

                    <div class="admin-product-copy">
                      <strong>${esc(item.name)}</strong>
                      <small>${esc(item.category?.name || "Chưa phân loại")}</small>
                    </div>
                  </td>

                  <td>${esc(item.category?.name || "")}</td>
                  <td>${money(item.price_vnd)}</td>
                  <td>
                    <div class="management-stock-info">

                      <strong>${item.stock}</strong>

                      ${
                        role === "admin"
                          ? `
                        <span class="management-stock-badge ${
                          Number(item.stock) <= 0
                            ? "is-out"
                            : Number(item.stock) <= 10
                              ? "is-low"
                              : "is-available"
                        }">

                          ${
                            Number(item.stock) <= 0
                              ? "Hết hàng"
                              : Number(item.stock) <= 10
                                ? "Sắp hết hàng"
                                : "Còn hàng"
                          }

                        </span>
                      `
                          : ""
                      }

                    </div>
                  </td>

                  <td>
                    <div class="admin-product-actions">
                      ${
                        section === "inventory"
                          ? `<button class="button-sm" data-stock="${item.id}" data-value="${item.stock}">Cập nhật tồn</button>`
                          : `
                            <button class="button-sm" data-edit="${item.id}" data-name="${esc(item.name)}" data-price="${item.price_vnd}">
                              Sửa tên / giá
                            </button>
                            <button class="button-sm" data-image="${item.id}">
                              Quản lý ảnh
                            </button>
                          `
                      }
                    </div>
                  </td>
                </tr>
              `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
    const productSearch = target.querySelector("#product-search");
    const categoryFilter = target.querySelector("#product-category");
    const stockFilter = target.querySelector("#product-stock-filter");
    const sortFilter = target.querySelector("#product-sort");
    const productCount = target.querySelector("#product-search-count");
    const productTable = target.querySelector(".table-wrap tbody");
    productTable.querySelectorAll("tr").forEach((row, index) => {
      row.dataset.originalIndex = index;
    });
    function normalizeProductText(value) {
      return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLocaleLowerCase("vi")
        .trim();
    }
    const staffPagination =
      (role === "staff" && section === "inventory") ||
      (role === "admin" && ["products", "inventory"].includes(section));

    const pageSize = role === "admin" ? 10 : 15;
    let currentPage = 1;

    const pager = document.createElement("div");
    pager.className = "ap-pager";

    if (staffPagination) {
      pager.innerHTML = `
    <span id="stock-page-info"></span>
    <div class="ap-page-actions">
      <button type="button" id="stock-prev">← Trước</button>
      <button type="button" id="stock-next">Sau →</button>
    </div>
  `;

      target
        .querySelector(".table-wrap")
        .insertAdjacentElement("afterend", pager);
    }

    function filterProducts(resetPage = false) {
      if (resetPage) currentPage = 1;

      const keyword = normalizeProductText(productSearch.value);
      const category = categoryFilter.value;

      const allRows = [...productTable.querySelectorAll("tr")];

      const matched = allRows.filter((row) => {
        const identity = row.cells[0]?.textContent || "";
        const name = row.cells[1]?.textContent || "";
        const categoryName = row.cells[2]?.textContent?.trim() || "";

        const searchable = normalizeProductText(identity + " " + name);

        const stock = Number(row.dataset.stockValue);
        const stockMode = stockFilter?.value || "";

        const stockMatches =
          !stockMode ||
          (stockMode === "available" && stock > 0) ||
          (stockMode === "low" && stock > 0 && stock <= 10) ||
          (stockMode === "out" && stock <= 0);

        return (
          searchable.includes(keyword) &&
          (!category || categoryName === category) &&
          stockMatches
        );
      });

      const sortMode = sortFilter?.value || "default";

      if (sortMode === "price-asc") {
        matched.sort(
          (a, b) => Number(a.dataset.priceValue) - Number(b.dataset.priceValue),
        );
      }

      if (sortMode === "price-desc") {
        matched.sort(
          (a, b) => Number(b.dataset.priceValue) - Number(a.dataset.priceValue),
        );
      }

      if (sortMode === "name") {
        matched.sort((a, b) =>
          a.dataset.productName.localeCompare(b.dataset.productName, "vi"),
        );
      }

      if (sortMode === "stock-asc") {
        matched.sort(
          (a, b) => Number(a.dataset.stockValue) - Number(b.dataset.stockValue),
        );
      }

      if (sortMode === "default") {
        matched.sort(
          (a, b) =>
            Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex),
        );
      }

      matched.forEach((row) => productTable.appendChild(row));
      const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));

      currentPage = Math.min(currentPage, totalPages);

      const start = staffPagination ? (currentPage - 1) * pageSize : 0;

      const visible = new Set(
        staffPagination ? matched.slice(start, start + pageSize) : matched,
      );

      allRows.forEach((row) => {
        row.style.display = visible.has(row) ? "" : "none";
      });

      const first = matched.length ? start + 1 : 0;

      const last = staffPagination
        ? Math.min(start + pageSize, matched.length)
        : matched.length;

      productCount.textContent = staffPagination
        ? `Hiển thị ${first}–${last} / ${matched.length} sản phẩm`
        : `Hiển thị ${matched.length} / ${rows.length} sản phẩm`;

      if (!matched.length) {
        productCount.textContent += " — Không tìm thấy sản phẩm phù hợp.";
      }

      if (staffPagination) {
        pager.querySelector("#stock-page-info").textContent =
          `Trang ${currentPage} / ${totalPages}`;

        pager.querySelector("#stock-prev").disabled = currentPage <= 1;

        pager.querySelector("#stock-next").disabled = currentPage >= totalPages;
      }
    }

    if (staffPagination) {
      pager.querySelector("#stock-prev").onclick = () => {
        currentPage--;
        filterProducts();
      };

      pager.querySelector("#stock-next").onclick = () => {
        currentPage++;
        filterProducts();
      };
    }

    productSearch.addEventListener("input", () => filterProducts(true));
    categoryFilter.addEventListener("change", () => filterProducts(true));
    stockFilter?.addEventListener("change", () => filterProducts(true));
    sortFilter?.addEventListener("change", () => filterProducts(true));

    filterProducts();
    if (section === "products" && role === "admin") {
      const addButton = target.querySelector("#product-create");

      const openEditor = async (product = null) => {
        const { openProductEditor } = await import(
          new URL(root + "assets/js/product-editor.js", document.baseURI).href
        );

        await openProductEditor({
          api,
          rows,
          product,
          onSaved: async () => {
            await renderProducts(target, section, role);
            showSuccessToast("Đã lưu sản phẩm thành công.");
          },
        });
      };

      const failure = (error) => showErrorToast(error);

      if (addButton) {
        addButton.onclick = () => openEditor().catch(failure);
      }

      target.querySelectorAll("[data-image]").forEach((button) => {
        button.onclick = () =>
          openEditor(
            rows.find((row) => row.id === Number(button.dataset.image)),
          ).catch(failure);
      });
    }
    target.querySelectorAll("[data-edit]").forEach((button) => {
      button.addEventListener("click", () => {
        const item = rows.find(
          (row) => Number(row.id) === Number(button.dataset.edit),
        );

        if (!item) return;

        const dialog = document.createElement("dialog");
        dialog.className = "stock-dialog product-edit-dialog";
        dialog.setAttribute("aria-labelledby", "product-edit-title");

        dialog.innerHTML = `
      <div class="stock-dialog-head">
        <h2 id="product-edit-title">Chỉnh sửa sản phẩm</h2>
        <button type="button" id="edit-close"
          aria-label="Đóng">×</button>
      </div>

      <form id="product-edit-form">

        <div class="stock-product">
          ${
            imageFor(item)
              ? `
            <img src="${esc(imageFor(item))}" alt="">
          `
              : ""
          }

          <div>
            <strong>${esc(item.name)}</strong>
            <small>SKU: ${esc(item.sku)}</small>
            <small>Danh mục: ${esc(item.category?.name || "—")}</small>
          </div>
        </div>

        <label class="field">
          <span>Tên sản phẩm</span>
          <input id="edit-product-name"
            type="text"
            value="${esc(item.name)}"
            required>
        </label>

        <label class="field">
          <span>Giá bán (VNĐ)</span>
          <input id="edit-product-price"
            type="number"
            min="1"
            step="1"
            value="${Number(item.price_vnd)}"
            required>

          <small id="edit-price-preview">
            Giá hiển thị: ${money(item.price_vnd)}
          </small>
        </label>

        <div class="stock-current">
          <span>Tồn kho hiện tại</span>
          <strong>${item.stock} sản phẩm</strong>
        </div>

        <p id="edit-product-error"
          class="form-alert error"
          role="alert" hidden></p>

        <div class="stock-dialog-actions">
          <button type="button"
            class="button button-outline"
            id="edit-cancel">Hủy bỏ</button>

          <button type="submit"
            class="button button-dark"
            id="edit-save">Lưu thay đổi</button>
        </div>

      </form>
    `;

        target.appendChild(dialog);

        const nameInput = dialog.querySelector("#edit-product-name");
        const priceInput = dialog.querySelector("#edit-product-price");
        const preview = dialog.querySelector("#edit-price-preview");
        const errorBox = dialog.querySelector("#edit-product-error");
        const save = dialog.querySelector("#edit-save");
        const cancel = dialog.querySelector("#edit-cancel");
        const close = dialog.querySelector("#edit-close");

        let saving = false;

        priceInput.oninput = () => {
          preview.textContent = "Giá hiển thị: " + money(priceInput.value);
        };

        cancel.onclick = close.onclick = () => dialog.close();

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        dialog.querySelector("#product-edit-form").onsubmit = async (event) => {
          event.preventDefault();

          if (saving) return;

          const name = nameInput.value.trim();
          const price = priceInput.value.trim();

          if (
            !name ||
            !/^\d+$/.test(price) ||
            !Number.isSafeInteger(Number(price)) ||
            Number(price) <= 0
          ) {
            errorBox.textContent =
              "Vui lòng nhập tên sản phẩm và giá bán hợp lệ.";
            errorBox.hidden = false;
            return;
          }

          saving = true;
          save.disabled = cancel.disabled = close.disabled = true;
          save.textContent = "Đang lưu...";
          errorBox.hidden = true;

          try {
            await api.updateProduct(button.dataset.edit, {
              name: name,
              sale_price: price,
              expected_sale_price: button.dataset.price,
            });
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;

            saving = false;
            save.disabled = cancel.disabled = close.disabled = false;
            save.textContent = "Lưu thay đổi";
            return;
          }

          dialog.close();

          try {
            await renderProducts(target, section, role);

            showSuccessToast("Đã cập nhật thông tin sản phẩm.");
          } catch (error) {
            showError(target, error);
          }
        };

        dialog.showModal();
      });
    });
    target.querySelectorAll("[data-stock]").forEach((button) => {
      button.addEventListener("click", () => {
        const item = rows.find(
          (row) => Number(row.id) === Number(button.dataset.stock),
        );

        if (!item) return;

        const dialog = document.createElement("dialog");
        dialog.className = "stock-dialog";
        dialog.setAttribute("aria-labelledby", "stock-dialog-title");

        dialog.innerHTML = `
      <div class="stock-dialog-head">
        <h2 id="stock-dialog-title">Cập nhật tồn kho</h2>
        <button type="button" id="stock-close"
                aria-label="Đóng">×</button>
      </div>

      <form id="stock-form">

        <div class="stock-product">
          ${
            imageFor(item)
              ? `
            <img src="${esc(imageFor(item))}" alt="">
          `
              : ""
          }

          <div>
            <strong>${esc(item.name)}</strong>
            <small>SKU: ${esc(item.sku)}</small>
            <span>${money(item.price_vnd)}</span>
          </div>
        </div>

        <div class="stock-current">
          <span>Tồn kho hiện tại</span>
          <strong>${item.stock}</strong>
        </div>

        <label class="field">
          <span>Số lượng tồn kho mới</span>

          <input id="stock-new"
                 type="number"
                 min="0"
                 step="1"
                 value="${item.stock}"
                 required>

          <small>Nhập tổng số lượng còn lại trong kho,
          không phải số lượng nhập thêm.</small>
        </label>

        <p id="stock-error"
           class="form-alert error"
           role="alert" hidden></p>

        <div class="stock-dialog-actions">
          <button type="button" id="stock-cancel"
                  class="button button-outline">
            Hủy bỏ
          </button>

          <button type="submit" id="stock-save"
                  class="button button-dark">
            Lưu thay đổi
          </button>
        </div>

      </form>
    `;

        target.appendChild(dialog);

        const form = dialog.querySelector("#stock-form");
        const input = dialog.querySelector("#stock-new");
        const errorBox = dialog.querySelector("#stock-error");
        const save = dialog.querySelector("#stock-save");
        const cancel = dialog.querySelector("#stock-cancel");
        const close = dialog.querySelector("#stock-close");

        let saving = false;

        close.onclick = cancel.onclick = () => dialog.close();

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        form.addEventListener("submit", async (event) => {
          event.preventDefault();

          if (saving) return;

          const stock = Number(input.value);

          if (
            input.value.trim() === "" ||
            !Number.isSafeInteger(stock) ||
            stock < 0
          ) {
            errorBox.textContent = "Tồn kho phải là số nguyên không âm.";
            errorBox.hidden = false;
            return;
          }

          if (stock === Number(item.stock)) {
            dialog.close();
            return;
          }

          saving = true;
          save.disabled = true;
          cancel.disabled = true;
          close.disabled = true;
          save.textContent = "Đang lưu...";
          errorBox.hidden = true;

          try {
            await api.updateStock(
              button.dataset.stock,
              Number(button.dataset.value),
              stock,
            );
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;
            saving = false;
            save.disabled = false;
            cancel.disabled = false;
            close.disabled = false;
            save.textContent = "Lưu thay đổi";
            return;
          }

          dialog.close();

          try {
            await renderProducts(target, section, role);
            showSuccessToast("Đã cập nhật tồn kho thành công.");
          } catch (error) {
            showError(target, error);
          }
        });

        dialog.showModal();
        input.focus();
        input.select();
      });
    });
  }

  
async function renderCoupons(target) {
  let currentPage = 1;
  let search = "";
  let selectedType = "";
  let selectedStatus = "";

  const pageSize = 10;

  function couponStatus(coupon) {
    if (!coupon.is_active) return "paused";
    if (Date.now() < new Date(coupon.starts_at).getTime()) return "upcoming";
    if (Date.now() >= new Date(coupon.ends_at).getTime()) return "expired";
    if (coupon.usage_limit != null && coupon.used_count >= coupon.usage_limit)
      return "exhausted";

    return "active";
  }

  const labels = {
    active: "Đang áp dụng",
    upcoming: "Sắp diễn ra",
    expired: "Hết hạn",
    exhausted: "Hết lượt",
    paused: "Tạm dừng",
  };

  async function draw() {
    const result = await api.adminCoupons(1, 100);
    const rows = [...result.items];

    let nextPage = 2;

    while (rows.length < result.total) {
      const next = await api.adminCoupons(nextPage, 100);
      if (!next.items.length) break;

      rows.push(...next.items);
      nextPage++;
    }

    const activeCount = rows.filter((c) => couponStatus(c) === "active").length;

    const upcomingCount = rows.filter(
      (c) => couponStatus(c) === "upcoming",
    ).length;

    const inactiveCount = rows.filter((c) =>
      ["expired", "exhausted", "paused"].includes(couponStatus(c)),
    ).length;

    target.innerHTML = `
      <div class="panel management-coupons-panel">

        <div class="management-staff-head">
          <p class="customers-description">
            Quản lý mã giảm giá và chương trình ưu đãi của cửa hàng.
          </p>

          <button type="button"
            class="button button-dark"
            id="coupon-create">
            + Tạo mã giảm giá
          </button>
        </div>

        <div class="order-kpis">

          <article class="order-kpi">
            <span>Tổng số mã</span>
            <strong>${rows.length}</strong>
            <small>Toàn bộ mã giảm giá</small>
          </article>

          <article class="order-kpi">
            <span>Đang áp dụng</span>
            <strong>${activeCount}</strong>
            <small>Ưu đãi đang có hiệu lực</small>
          </article>

          <article class="order-kpi">
            <span>Sắp diễn ra</span>
            <strong>${upcomingCount}</strong>
            <small>Chưa đến thời gian áp dụng</small>
          </article>

          <article class="order-kpi">
            <span>Ngừng áp dụng</span>
            <strong>${inactiveCount}</strong>
            <small>Hết hạn, hết lượt hoặc tạm dừng</small>
          </article>

        </div>

        <div class="order-list-heading">
          <h3>Danh sách mã giảm giá</h3>
        </div>

        <div class="management-orders-toolbar">

          <label>
            <span>Tìm kiếm</span>
            <input id="coupon-search"
              type="search"
              value="${esc(search)}"
              placeholder="Tìm mã giảm giá...">
          </label>

          <label>
            <span>Loại giảm giá</span>

            <select id="coupon-type">
              <option value="">Tất cả loại</option>
              <option value="percent">Phần trăm (%)</option>
              <option value="fixed">Số tiền (VNĐ)</option>
            </select>
          </label>

          <label>
            <span>Trạng thái</span>

            <select id="coupon-status">
              <option value="">Tất cả trạng thái</option>

              ${Object.entries(labels)
                .map(
                  ([value, label]) =>
                    `<option value="${value}">${label}</option>`,
                )
                .join("")}

            </select>
          </label>

        </div>

        <p id="coupon-count"
          class="mini-note customer-result-count"></p>

        <div class="table-wrap">

          <table class="data-table management-coupons-table">

            <thead>
              <tr>
                <th>Mã ưu đãi</th>
                <th>Giá trị giảm</th>
                <th>Đơn tối thiểu</th>
                <th>Lượt sử dụng</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>

            <tbody>

              ${rows
                .map(
                  (coupon) => `
                <tr data-coupon-id="${coupon.id}">

                  <td>
                    <strong class="coupon-code">
                      ${esc(coupon.code)}
                    </strong>

                    <small class="order-secondary">
                      ${
                        coupon.discount_type === "percent"
                          ? "Giảm theo phần trăm"
                          : "Giảm theo số tiền"
                      }
                    </small>
                  </td>

                  <td>
                    <strong class="coupon-value">
                      ${
                        coupon.discount_type === "percent"
                          ? Number(coupon.discount_value) + "%"
                          : money(coupon.discount_value)
                      }
                    </strong>

                    ${
                      coupon.discount_type === "percent" &&
                      coupon.max_discount_vnd != null
                        ? `<small class="order-secondary">
                          Tối đa ${money(coupon.max_discount_vnd)}
                        </small>`
                        : ""
                    }
                  </td>

                  <td>${money(coupon.min_order_vnd)}</td>

                  <td>
                    <strong>
                      ${coupon.used_count}
                      ${
                        coupon.usage_limit != null
                          ? "/ " + coupon.usage_limit
                          : ""
                      }
                    </strong>

                    <small class="order-secondary">
                      ${
                        coupon.usage_limit != null
                          ? "Lượt đã sử dụng"
                          : "Không giới hạn"
                      }
                    </small>
                  </td>

                  <td>

                    <span class="coupon-state state-${couponStatus(coupon)}">
                      ${labels[couponStatus(coupon)]}
                    </span>

                    <small class="order-secondary">
                      Từ ${new Date(coupon.starts_at).toLocaleDateString(
                        "vi-VN",
                      )}
                    </small>

                    <small class="order-secondary">
                      Đến ${new Date(coupon.ends_at).toLocaleDateString(
                        "vi-VN",
                      )}
                    </small>

                  </td>

                  <td>
                    <div class="customer-row-actions">

                      <button type="button"
                        class="button-sm"
                        data-edit="${coupon.id}">
                        Chỉnh sửa
                      </button>

                      <button type="button"
                        class="button-sm
                          ${coupon.is_active ? "lock-action" : "unlock-action"}"
                        data-toggle="${coupon.id}">

                        ${coupon.is_active ? "Tạm dừng" : "Bật lại"}

                      </button>

                    </div>
                  </td>

                </tr>
              `,
                )
                .join("")}

              <tr id="coupon-empty" hidden>
                <td colspan="6" class="customer-empty">
                  Không tìm thấy mã giảm giá phù hợp.
                </td>
              </tr>

            </tbody>
          </table>
        </div>

        <div class="ap-pager">

          <span id="coupon-page-info"></span>

          <div class="ap-page-actions">
            <button type="button" id="coupon-prev">
              ← Trước
            </button>

            <button type="button" id="coupon-next">
              Sau →
            </button>
          </div>

        </div>

      </div>
    `;

    const searchInput = target.querySelector("#coupon-search");
    const typeFilter = target.querySelector("#coupon-type");
    const statusFilter = target.querySelector("#coupon-status");

    const previous = target.querySelector("#coupon-prev");
    const next = target.querySelector("#coupon-next");

    const tableRows = [...target.querySelectorAll("[data-coupon-id]")];

    typeFilter.value = selectedType;
    statusFilter.value = selectedStatus;

    function applyFilters(resetPage = false) {
      if (resetPage) currentPage = 1;

      const keyword = search.trim().toLowerCase();

      const matched = rows.filter((coupon) => {
        const searchable =
          `${coupon.code} ${coupon.description || ""}`.toLowerCase();

        return (
          searchable.includes(keyword) &&
          (!selectedType || coupon.discount_type === selectedType) &&
          (!selectedStatus || couponStatus(coupon) === selectedStatus)
        );
      });

      const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));

      currentPage = Math.min(currentPage, totalPages);

      const start = (currentPage - 1) * pageSize;

      const visible = new Set(
        matched
          .slice(start, start + pageSize)
          .map((coupon) => String(coupon.id)),
      );

      tableRows.forEach((row) => {
        row.hidden = !visible.has(row.dataset.couponId);
      });

      target.querySelector("#coupon-empty").hidden = matched.length !== 0;

      target.querySelector("#coupon-count").textContent =
        `Hiển thị ${matched.length ? start + 1 : 0}–${Math.min(start + pageSize, matched.length)} / ${matched.length} mã giảm giá`;

      target.querySelector("#coupon-page-info").textContent =
        `Trang ${currentPage} / ${totalPages}`;

      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= totalPages;
    }

    searchInput.oninput = () => {
      search = searchInput.value;
      applyFilters(true);
    };

    typeFilter.onchange = () => {
      selectedType = typeFilter.value;
      applyFilters(true);
    };

    statusFilter.onchange = () => {
      selectedStatus = statusFilter.value;
      applyFilters(true);
    };

    previous.onclick = () => {
      currentPage--;
      applyFilters();
    };

    next.onclick = () => {
      currentPage++;
      applyFilters();
    };

    applyFilters();

    // Tận dụng modal tạo và chỉnh sửa mã hiện tại

    const openEditor = async (coupon = null) => {
      const { openCouponEditor } = await import(
        new URL(root + "assets/js/coupon-editor.js", document.baseURI).href
      );

      openCouponEditor({
        api,
        coupon,

        onSaved: async () => {
          showSuccessToast(
            coupon
              ? "Đã cập nhật mã giảm giá."
              : "Đã tạo mã giảm giá thành công.",
          );

          if (!coupon) {
            currentPage = 1;
            search = "";
            selectedType = "";
            selectedStatus = "";
          }

          try {
            await draw();
          } catch (error) {
            showError(target, error);
          }
        },
      });
    };

    target.querySelector("#coupon-create").onclick = () =>
      openEditor().catch(showErrorToast);

    target.querySelectorAll("[data-edit]").forEach((button) => {
      button.onclick = () => {
        const coupon = rows.find(
          (item) => Number(item.id) === Number(button.dataset.edit),
        );

        if (coupon) {
          openEditor(coupon).catch(showErrorToast);
        }
      };
    });

    // Xác nhận tạm dừng hoặc bật lại mã

    target.querySelectorAll("[data-toggle]").forEach((button) => {
      button.onclick = () => {
        const coupon = rows.find(
          (item) => Number(item.id) === Number(button.dataset.toggle),
        );

        if (!coupon) return;

        const pausing = coupon.is_active;

        const dialog = document.createElement("dialog");

        dialog.className = "stock-dialog customer-confirm-dialog";

        dialog.setAttribute("aria-labelledby", "coupon-confirm-title");

        dialog.innerHTML = `
          <div class="stock-dialog-head">

            <h2 id="coupon-confirm-title">
              ${pausing ? "Tạm dừng mã" : "Bật lại mã"}
            </h2>

            <button type="button" data-close
              aria-label="Đóng">×</button>
          </div>

          <p class="customer-confirm-message">
            Bạn có chắc chắn muốn
            ${pausing ? "tạm dừng" : "bật lại"}
            mã giảm giá
            <strong>${esc(coupon.code)}</strong>?
          </p>

          <p class="mini-note">
            ${
              pausing
                ? "Khách hàng sẽ không thể áp dụng mã này khi thanh toán."
                : "Mã sẽ được sử dụng nếu vẫn đáp ứng thời hạn, lượt dùng và điều kiện ưu đãi."
            }
          </p>

          <p id="coupon-toggle-error"
            class="form-alert error"
            role="alert" hidden></p>

          <div class="stock-dialog-actions">

            <button type="button"
              class="button button-outline"
              data-close>Hủy bỏ</button>

            <button type="button"
              class="button button-dark"
              id="coupon-toggle-save">

              ${pausing ? "Xác nhận tạm dừng" : "Xác nhận bật lại"}

            </button>
          </div>
        `;

        target.appendChild(dialog);

        const save = dialog.querySelector("#coupon-toggle-save");
        const errorBox = dialog.querySelector("#coupon-toggle-error");
        const closes = dialog.querySelectorAll("[data-close]");

        let saving = false;

        closes.forEach((close) => {
          close.onclick = () => dialog.close();
        });

        dialog.addEventListener("close", () => dialog.remove());

        dialog.addEventListener("cancel", (event) => {
          if (saving) event.preventDefault();
        });

        save.onclick = async () => {
          if (saving) return;

          saving = true;
          save.disabled = true;
          save.textContent = "Đang xử lý...";
          errorBox.hidden = true;

          closes.forEach((close) => (close.disabled = true));

          try {
            await api.setCouponStatus(coupon.id, !pausing);
          } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;

            saving = false;
            save.disabled = false;

            save.textContent = pausing
              ? "Xác nhận tạm dừng"
              : "Xác nhận bật lại";

            closes.forEach((close) => (close.disabled = false));
            return;
          }

          dialog.close();

          showSuccessToast(
            pausing ? "Đã tạm dừng mã giảm giá." : "Đã bật lại mã giảm giá.",
          );

          try {
            await draw();
          } catch (error) {
            showError(target, error);
          }
        };

        dialog.showModal();
      };
    });
  }

  await draw();
}



  function dateText(date) {
    return date.getFullYear()+"-"+String(date.getMonth()+1).padStart(2,"0")+"-"+String(date.getDate()).padStart(2,"0");
  }
  function statsBar(label, count, max) {
    return `<div class="lm-stat-bar"><span>${esc(label)}</span><div class="lm-stat-track"><i style="width:${Math.max(0,Math.min(100,100*count/(max||1)))}%"></i></div><strong>${count}</strong></div>`;
  }
  function dayChart(rows, key, formatter) {
    const max=Math.max(1,...rows.map(row=>Number(row[key]||0)));
    return `<div class="lm-chart">${rows.map(row=>`<div class="lm-chart-day" title="${esc(row.date||row.period_start)}: ${esc(formatter(row[key]))}"><div class="lm-chart-col"><i style="height:${Math.max(2,100*Number(row[key]||0)/max)}%"></i></div><span>${esc((row.date||row.period_start).slice(5))}</span></div>`).join('')}</div>`;
  }
  async function renderDashboard(target, analytics) {
    const now=new Date();
    const today=dateText(now);
    
if (analytics) {
  target.innerHTML = `
    <div class="management-analytics">

      <div class="analytics-header">

        <p class="customers-description">
          Theo dõi kết quả kinh doanh và hành vi mua hàng của khách hàng.
        </p>

        <label class="analytics-range">
          <span>Khoảng thời gian</span>

          <select id="behavior-days">
            <option value="7">7 ngày gần đây</option>
            <option value="30" selected>30 ngày gần đây</option>
            <option value="90">90 ngày gần đây</option>
          </select>
        </label>

      </div>

      <div id="behavior-results"
        aria-live="polite">
        <p class="mini-note">Đang tải số liệu...</p>
      </div>

    </div>
  `;

  const select = target.querySelector("#behavior-days");
  const output = target.querySelector("#behavior-results");

  const icons = {
    wallet:
      '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M16 10h5v4h-5Z"/>',
    receipt:
      '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    bag: '<rect x="5" y="7" width="14" height="14" rx="2"/><path d="M9 7V5a3 3 0 0 1 6 0v2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M5 21c0-5 3-8 7-8s7 3 7 8"/>',
    repeat:
      '<path d="M3 10a9 9 0 0 1 15-5l3 3M21 3v5h-5M21 14a9 9 0 0 1-15 5l-3-3M3 21v-5h5"/>',
    box: '<path d="m12 3 9 5v8l-9 5-9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  };

  const kpi = (label, value, note, icon) => `
    <article class="analytics-kpi">

      <div class="analytics-kpi-label">
        <span>${esc(label)}</span>

        <svg viewBox="0 0 24 24"
          fill="none" aria-hidden="true">
          ${icons[icon]}
        </svg>
      </div>

      <strong>${esc(value)}</strong>
      <small>${esc(note)}</small>

    </article>
  `;

  const statusColors = {
    pending: "#C6A258",
    confirmed: "#A79ABF",
    packing: "#B59A72",
    shipping: "#7799C4",
    delivered: "#87AC8A",
    cancelled: "#C9877E",
  };

  function reportBar(label, value, total, color) {
    const percent =
      total > 0 ? Math.max(0, Math.min(100, (Number(value) / total) * 100)) : 0;

    return `
      <div class="analytics-bar-row">

        <div class="analytics-bar-label">
          <span>${esc(label)}</span>
          <strong>${esc(value)} đơn</strong>
        </div>

        <div class="analytics-bar-track">
          <i style="width:${percent}%;background:${color}"></i>
        </div>

        <small>${percent.toFixed(1)}%</small>

      </div>
    `;
  }

  function reportChart(rows, key, formatter) {
    const data = rows.map((row) => ({
      date: String(row.date || row.period_start || ""),
      value: Number(row[key] || 0),
    }));

    if (!data.length || !data.some((row) => row.value > 0)) {
      return `
        <div class="analytics-empty-chart">
          Chưa có dữ liệu trong khoảng thời gian này.
        </div>
      `;
    }

    const max = Math.max(1, ...data.map((row) => row.value));

    const step = Math.max(1, Math.ceil(max / 4));

    const chartMax = step * 4;

    const labelEvery = Math.max(1, Math.ceil(data.length / 8));

    return `
      <div class="analytics-chart-layout">

        <div class="analytics-chart-axis">
          ${[4, 3, 2, 1, 0]
            .map(
              (n) => `
            <span>${esc(formatter(n * step))}</span>
          `,
            )
            .join("")}
        </div>

        <div class="analytics-chart-main">

          <div class="analytics-chart-grid"></div>

          <div class="analytics-chart-columns">

            ${data
              .map(
                (row, index) => `
              <div class="analytics-chart-column"
                title="${esc(row.date)}: ${esc(formatter(row.value))}">

                <div class="analytics-chart-track">

                  <i style="height:${Math.max(
                    0,
                    Math.min(100, (row.value / chartMax) * 100),
                  )}%"></i>

                </div>

                <small>
                  ${
                    index % labelEvery === 0
                      ? esc(row.date.slice(5).split("-").reverse().join("/"))
                      : ""
                  }
                </small>

              </div>
            `,
              )
              .join("")}

          </div>
        </div>
      </div>
    `;
  }

  const compactMoney = (value) => {
    const n = Number(value || 0);

    return n >= 1000000
      ? (n / 1000000).toLocaleString("vi-VN", {
          maximumFractionDigits: 1,
        }) + " tr"
      : n >= 1000
        ? (n / 1000).toLocaleString("vi-VN", {
            maximumFractionDigits: 1,
          }) + " nghìn"
        : n.toLocaleString("vi-VN");
  };

  let requestVersion = 0;

  async function refresh() {
    const version = ++requestVersion;
    const days = Number(select.value);

    const end = dateText(new Date());

    const current = new Date();

    const start = dateText(
      new Date(
        current.getFullYear(),
        current.getMonth(),
        current.getDate() - days + 1,
      ),
    );

    output.innerHTML = `
      <div class="panel analytics-loading">
        Đang tải số liệu kinh doanh...
      </div>
    `;

    try {
      const [behavior, revenue] = await Promise.all([
        api.request(
          "/admin/reports/purchase-behavior?" +
            new URLSearchParams({
              start_date: start,
              end_date: end,
            }),
        ),
        api.revenue(start, end),
      ]);

      if (version !== requestVersion) return;

      const totalOrders = Number(behavior.total_orders || 0);

      const orderStatuses = behavior.orders_by_status || {};

      const paymentMethods = behavior.orders_by_payment_method || {};

      const dailyOrders = behavior.daily_orders || [];

      const revenueRows = revenue.items || [];

      const topProducts = [...(behavior.top_products || [])].sort(
        (a, b) => Number(b.units) - Number(a.units),
      );

      output.innerHTML = `

        <div class="analytics-kpis">

          ${kpi(
            "Thanh toán đã xác nhận",
            money(revenue.confirmed_payment_amount_vnd),
            "Tổng số tiền thanh toán được xác minh",
            "wallet",
          )}

          ${kpi(
            "Giao dịch đã xác nhận",
            revenue.confirmed_payment_order_count,
            "Trong khoảng thời gian đã chọn",
            "receipt",
          )}

          ${kpi("Tổng đơn hàng", totalOrders, "Tổng số đơn được tạo", "bag")}

          ${kpi(
            "Khách đã đặt hàng",
            behavior.unique_buyers,
            "Số tài khoản khách hàng duy nhất",
            "user",
          )}

          ${kpi(
            "Khách mua lại",
            behavior.repeat_buyers,
            "Có ít nhất 2 đơn trong giai đoạn",
            "repeat",
          )}

          ${kpi(
            "Sản phẩm được đặt",
            behavior.total_units,
            "Tổng số lượng sản phẩm trên các đơn",
            "box",
          )}

        </div>

        <section class="panel analytics-card analytics-revenue">

          <div class="analytics-card-head">
            <div>
              <h3>Thanh toán đã xác nhận theo ngày</h3>

              <p class="mini-note">
                Phân bổ theo ngày xác minh giao dịch.
                Đơn vị: VNĐ.
              </p>
            </div>

            <div class="analytics-revenue-total">
              <span>Tổng thanh toán</span>
              <strong>
                ${money(revenue.confirmed_payment_amount_vnd)}
              </strong>
            </div>
          </div>

          ${reportChart(
            revenueRows,
            "confirmed_payment_amount_vnd",
            compactMoney,
          )}

        </section>

        <section class="panel analytics-card">

          <div class="analytics-card-head">
            <div>
              <h3>Số đơn hàng theo ngày</h3>
              <p class="mini-note">
                Thống kê theo ngày khách hàng tạo đơn.
              </p>
            </div>
          </div>

          ${reportChart(dailyOrders, "orders", (value) => String(value))}

        </section>

        <div class="analytics-grid">

          <section class="panel analytics-card">

            <div class="analytics-card-head">
              <div>
                <h3>Trạng thái đơn hàng</h3>
                <p class="mini-note">
                  Phân bố theo tiến độ xử lý đơn.
                </p>
              </div>
            </div>

            ${Object.entries(statusNames)
              .map(([key, label]) =>
                reportBar(
                  label,
                  Number(orderStatuses[key] || 0),
                  totalOrders,
                  statusColors[key],
                ),
              )
              .join("")}

          </section>

          <section class="panel analytics-card">

            <div class="analytics-card-head">
              <div>
                <h3>Phương thức thanh toán</h3>
                <p class="mini-note">
                  Lựa chọn thanh toán trên đơn hàng.
                </p>
              </div>
            </div>

            ${
              Object.entries(paymentMethods)
                .map(([key, value]) =>
                  reportBar(
                    key.toUpperCase(),
                    Number(value),
                    totalOrders,
                    key === "cod" ? "#B59A72" : "#7799C4",
                  ),
                )
                .join("") || '<p class="mini-note">Chưa có dữ liệu.</p>'
            }

            <div class="analytics-extra">

              <div>
                <span>Đơn sử dụng mã giảm giá</span>
                <strong>
                  ${behavior.orders_using_coupons || 0}
                </strong>
              </div>

              <div>
                <span>Sản phẩm trung bình mỗi đơn</span>
                <strong>
                  ${Number(
                    behavior.average_units_per_order || 0,
                  ).toLocaleString("vi-VN", {
                    maximumFractionDigits: 2,
                  })}
                </strong>
              </div>

            </div>

          </section>

        </div>

        <section class="panel analytics-card">

          <div class="analytics-card-head">
            <div>
              <h3>Sản phẩm được đặt nhiều nhất</h3>

              <p class="mini-note">
                Xếp hạng theo số lượng sản phẩm được đặt,
                bao gồm cả đơn hàng đã hủy.
              </p>
            </div>
          </div>

          <div class="table-wrap">

            <table class="data-table analytics-products-table">

              <thead>
                <tr>
                  <th>Xếp hạng</th>
                  <th>Mã sản phẩm</th>
                  <th>Tên sản phẩm</th>
                  <th>Số lượng được đặt</th>
                </tr>
              </thead>

              <tbody>

                ${
                  topProducts
                    .map(
                      (item, index) => `
                  <tr>
                    <td>
                      <span class="analytics-rank">
                        ${index + 1}
                      </span>
                    </td>

                    <td>#${esc(item.product_id)}</td>

                    <td>
                      <strong>${esc(item.name)}</strong>
                    </td>

                    <td>
                      <strong>${esc(item.units)}</strong>
                    </td>
                  </tr>
                `,
                    )
                    .join("") ||
                  '<tr><td colspan="4">Chưa có dữ liệu sản phẩm.</td></tr>'
                }

              </tbody>

            </table>

          </div>

        </section>

        <div class="analytics-note">

          <svg viewBox="0 0 24 24"
            fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9"/>
            <path d="M12 11v6M12 7v.01"/>
          </svg>

          <div>
            <strong>Thông tin thống kê</strong>

            <p>
              Số liệu được tổng hợp từ đơn hàng và các
              giao dịch thanh toán đã xác nhận.
              Tổng thanh toán không đồng nghĩa với
              doanh thu thuần hoặc lợi nhuận.
            </p>
          </div>

        </div>
      `;
    } catch (error) {
      if (version !== requestVersion) return;

      output.innerHTML = `
        <div class="form-alert error">
          ${esc(error.message)}
        </div>
      `;
    }
  }

  select.onchange = refresh;

  await refresh();

  return;
}

    const first=new Date(now.getFullYear(),now.getMonth(),now.getDate()-29);
    const [result,orderPage,products,revenue]=await Promise.all([
      api.dashboard(),api.adminOrders(1,5),loadAllProducts(true),api.revenue(dateText(first),today)
    ]);
    const low=products.filter(p=>p.stock>0&&p.stock<=10).sort((a,b)=>a.stock-b.stock).slice(0,7);
    const statuses=result.orders_by_status||{};
    const max=Math.max(1,...Object.values(statuses));
    target.innerHTML = `<div class="lm-admin-head"><div><p class="mini-note">Theo dõi hoạt động kinh doanh, đơn hàng và tình hình tồn kho của cửa hàng.</p></div></div>      <div class="lm-kpis">
      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Tổng đơn hàng</span>
          <svg viewBox="0 0 24 24">
            <rect x="5" y="7" width="14" height="14" rx="2"/>
            <path d="M9 7V5a3 3 0 0 1 6 0v2"/>
          </svg>
        </div>
        <strong>${result.total_orders}</strong>
        <small>${statuses.pending || 0} đơn chờ xác nhận</small>
      </div>

      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Sản phẩm</span>
          <svg viewBox="0 0 24 24">
            <path d="m12 3 9 5v8l-9 5-9-5V8Z"/>
            <path d="m3 8 9 5 9-5M12 13v8"/>
          </svg>
        </div>
        <strong>${result.total_products}</strong>
        <small>Tổng số sản phẩm trong danh mục</small>
      </div>

      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Đã hết hàng</span>
          <svg viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="m9 9 6 6m0-6-6 6"/>
          </svg>
        </div>
        <strong>${result.out_of_stock_products}</strong>
        <small>${products.filter((p) => p.stock > 0 && p.stock <= 10).length} sản phẩm sắp hết hàng</small>
      </div>

      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Tổng tiền đã xác nhận</span>
          <svg viewBox="0 0 24 24">
            <rect x="3" y="5" width="18" height="14" rx="2"/>
            <path d="M16 10h5v4h-5Z"/>
          </svg>
        </div>
        <strong>${money(result.confirmed_payment_amount_vnd)}</strong>
        <small>Tổng thanh toán đã được xác nhận</small>
      </div>

      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Thanh toán 30 ngày</span>
          <svg viewBox="0 0 24 24">
            <path d="M3 3v18h18M7 17v-5m5 5V8m5 9V5"/>
          </svg>
        </div>
        <strong>${money(revenue.confirmed_payment_amount_vnd)}</strong>
        <small>${revenue.confirmed_payment_order_count} giao dịch đã xác minh</small>
      </div>

      <div class="lm-kpi">
        <div class="lm-kpi-label">
          <span>Cần đối soát</span>
          <svg viewBox="0 0 24 24">
            <rect x="5" y="3" width="14" height="18" rx="2"/>
            <path d="M9 8h6M9 12h6M9 16h4"/>
          </svg>
        </div>
        <strong>${result.reconciliation_order_count}</strong>
        <small>Tổng giá trị: ${money(result.reconciliation_order_value_vnd)}</small>
      </div>
      </div>
      <div class="lm-data-grid"><section class="panel"><h3>Đơn hàng theo trạng thái</h3>${Object.entries(
        statuses,
      )
        .map(([key, value]) => statsBar(statusNames[key] || key, value, max))
        .join(
          "",
        )}<p><a class="inline-link" href="orders.html">Quản lý đơn hàng</a></p></section>
      <section class="panel"><h3>Thanh toán được xác nhận · 30 ngày</h3><p class="mini-note">Phân bổ theo ngày xác minh giao dịch</p>${dayChart(
        (revenue.items || []).map((x) => ({ ...x, date: x.period_start })),
        "confirmed_payment_amount_vnd",
        money,
      )}</section></div>
      <div class="lm-data-grid lm-dashboard-tables"><section class="panel"><div class="lm-dashboard-panel-head"><h3>Đơn hàng gần nhất</h3><a class="inline-link" href="orders.html">Xem tất cả →</a></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Mã</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng tiền</th></tr></thead><tbody>
      ${(orderPage.items || []).map((row) => `<tr><td>${esc(row.code)}</td><td>${esc(statusNames[row.status] || row.status)}</td><td>${esc(paymentNames[row.payment_status] || row.payment_status)}</td><td>${money(row.total_vnd)}</td></tr>`).join("") || '<tr><td colspan="4">Chưa có đơn</td></tr>'}</tbody></table></div></section>
      <section class="panel"><h3>Sản phẩm gần hết hàng</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>ID</th><th>Sản phẩm</th><th>Tồn kho</th></tr></thead><tbody>${low.map((p) => `<tr><td>#${p.id}</td><td>${esc(p.name)}</td><td><strong>${p.stock}</strong></td></tr>`).join("") || '<tr><td colspan="3">Chưa có sản phẩm tồn kho thấp</td></tr>'}</tbody></table></div><a class="inline-link" href="inventory.html">Kiểm tra tồn kho</a></section></div>
      <div class="panel"><h3>Lưu ý đối soát</h3><p class="mini-note">Dữ liệu được xác nhận theo chứng từ thanh toán; số tiền không tương đương doanh thu thuần hoặc lợi nhuận.</p>${(result.reconciliation_reasons || []).map((x) => `<p>${esc(x.reason)}: ${x.order_count} đơn</p>`).join("") || "<p>Chưa phát hiện trường hợp cần đối soát.</p>"}</div>`;
  }

  
async function renderLookup(target, kind) {
  const title = kind === "brands" ? "thương hiệu" : "danh mục";
  const path = "/admin/" + kind;
  const result = await api.request(path);
  const items = result.items || [];

  const used = items.filter((x) => x.product_count > 0).length;

  let currentPage = 1;
  const pageSize = 10;

  target.innerHTML = `
    <div class="panel management-lookup-panel">

      <div class="management-staff-head">

        <p class="customers-description">
          ${
            kind === "brands"
              ? "Quản lý thương hiệu của các sản phẩm trong cửa hàng."
              : "Quản lý các nhóm sản phẩm của cửa hàng."
          }
        </p>

        <button id="lookup-add"
          class="button button-dark" type="button">
          + Thêm ${title}
        </button>

      </div>

      <div class="customer-kpis">

        <article class="order-kpi">
          <span>Tổng ${title}</span>
          <strong>${items.length}</strong>
          <small>Toàn bộ ${title} hiện có</small>
        </article>

        <article class="order-kpi">
          <span>Đang sử dụng</span>
          <strong>${used}</strong>
          <small>Đã có sản phẩm liên kết</small>
        </article>

        <article class="order-kpi">
          <span>Chưa sử dụng</span>
          <strong>${items.length - used}</strong>
          <small>Chưa có sản phẩm liên kết</small>
        </article>

      </div>

      <div class="order-list-heading">
        <h3>Danh sách ${title}</h3>
      </div>

      <div class="management-customers-toolbar">

        <label>
          <span>Tìm kiếm</span>
          <input id="lookup-search" type="search"
            placeholder="Tìm tên hoặc mã ${title}...">
        </label>

        <label>
          <span>Tình trạng</span>
          <select id="lookup-filter">
            <option value="">Tất cả tình trạng</option>
            <option value="used">Đang sử dụng</option>
            <option value="unused">Chưa sử dụng</option>
          </select>
        </label>

      </div>

      <p id="lookup-count"
        class="mini-note customer-result-count"></p>

      <div class="table-wrap">

        <table class="data-table management-lookup-table">

          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên ${title}</th>
              <th>Số sản phẩm</th>
              <th>Tình trạng</th>
              <th>Thao tác</th>
            </tr>
          </thead>

          <tbody id="lookup-rows">

            ${items
              .map(
                (item) => `
              <tr data-lookup-row="${item.id}">

                <td>
                  <strong>#${item.id}</strong>
                </td>

                <td>
                  <strong>${esc(item.name)}</strong>
                </td>

                <td>
                  <strong>${item.product_count}</strong>
                </td>

                <td>
                  <span class="lookup-state
                    ${item.product_count > 0 ? "is-used" : "is-unused"}">

                    ${item.product_count > 0 ? "Đang sử dụng" : "Chưa sử dụng"}

                  </span>
                </td>

                <td>
                  <div class="customer-row-actions">

                    <button class="button-sm"
                      type="button"
                      data-lookup-edit="${item.id}">
                      Chỉnh sửa
                    </button>

                    <button class="button-sm lock-action"
                      type="button"
                      data-lookup-delete="${item.id}"
                      ${
                        item.product_count > 0
                          ? 'disabled title="Đang được sản phẩm sử dụng"'
                          : ""
                      }>
                      Xóa
                    </button>

                  </div>
                </td>

              </tr>
            `,
              )
              .join("")}

            <tr id="lookup-empty" hidden>
              <td colspan="5" class="customer-empty">
                Không tìm thấy ${title} phù hợp.
              </td>
            </tr>

          </tbody>
        </table>
      </div>

      <div class="ap-pager">

        <span id="lookup-page-info"></span>

        <div class="ap-page-actions">

          <button id="lookup-prev" type="button">
            ← Trước
          </button>

          <button id="lookup-next" type="button">
            Sau →
          </button>

        </div>
      </div>

      <p class="mini-note lookup-note">
        Chỉ có thể xóa ${title} chưa được liên kết với sản phẩm.
        Việc đổi tên cần được đồng bộ với dữ liệu tìm kiếm
        và tư vấn sản phẩm.
      </p>

    </div>
  `;

  const find = (selector) => target.querySelector(selector);

  const searchInput = find("#lookup-search");
  const statusFilter = find("#lookup-filter");

  function normalize(value) {
    return String(value ?? "")
      .toLocaleLowerCase("vi")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .trim();
  }

  function applyFilters(resetPage = false) {
    if (resetPage) currentPage = 1;

    const keyword = normalize(searchInput.value);
    const status = statusFilter.value;

    const matched = items.filter((item) => {
      const searchable = normalize(item.id + " " + item.name);

      return (
        searchable.includes(keyword) &&
        (!status ||
          (status === "used" && item.product_count > 0) ||
          (status === "unused" && item.product_count === 0))
      );
    });

    const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));

    currentPage = Math.min(currentPage, totalPages);

    const start = (currentPage - 1) * pageSize;

    const visible = new Set(
      matched.slice(start, start + pageSize).map((item) => String(item.id)),
    );

    target.querySelectorAll("[data-lookup-row]").forEach((row) => {
      row.hidden = !visible.has(row.dataset.lookupRow);
    });

    find("#lookup-empty").hidden = matched.length !== 0;

    find("#lookup-count").textContent =
      `Hiển thị ${matched.length ? start + 1 : 0}–${Math.min(start + pageSize, matched.length)} / ${matched.length} ${title}`;

    find("#lookup-page-info").textContent =
      `Trang ${currentPage} / ${totalPages}`;

    find("#lookup-prev").disabled = currentPage <= 1;
    find("#lookup-next").disabled = currentPage >= totalPages;
  }

  searchInput.oninput = () => applyFilters(true);
  statusFilter.onchange = () => applyFilters(true);

  find("#lookup-prev").onclick = () => {
    currentPage--;
    applyFilters();
  };

  find("#lookup-next").onclick = () => {
    currentPage++;
    applyFilters();
  };

  applyFilters();

  // Modal thêm hoặc chỉnh sửa

  function openEditor(item = null) {
    const editing = item !== null;

    const dialog = document.createElement("dialog");

    dialog.className = "stock-dialog lookup-editor-dialog";
    dialog.setAttribute("aria-labelledby", "lookup-editor-title");

    dialog.innerHTML = `
      <div class="stock-dialog-head">

        <h2 id="lookup-editor-title">
          ${editing ? "Chỉnh sửa" : "Thêm"} ${title}
        </h2>

        <button type="button" data-close
          aria-label="Đóng">×</button>

      </div>

      <form id="lookup-form">

        <p class="mini-note">
          ${
            editing
              ? "Cập nhật tên hiển thị trong cửa hàng."
              : "Tạo nhóm thông tin mới cho sản phẩm."
          }
        </p>

        <label class="field">

          <span>Tên ${title}</span>

          <input id="lookup-name"
            type="text"
            maxlength="150"
            value="${esc(item?.name || "")}"
            placeholder="Nhập tên ${title}..."
            required>

        </label>

        ${
          editing && item.product_count > 0
            ? `
          <div class="staff-role-note">
            <strong>
              ${item.product_count} sản phẩm đang liên kết
            </strong>
            <small>
              Đổi tên có thể yêu cầu đồng bộ lại dữ liệu
              tìm kiếm và tư vấn sản phẩm.
            </small>
          </div>
        `
            : ""
        }

        <p id="lookup-error"
          class="form-alert error"
          role="alert" hidden></p>

        <div class="stock-dialog-actions">

          <button type="button"
            class="button button-outline"
            data-close>Hủy bỏ</button>

          <button type="submit"
            class="button button-dark"
            id="lookup-save">

            ${editing ? "Lưu thay đổi" : "Tạo mới"}

          </button>

        </div>
      </form>
    `;

    target.appendChild(dialog);

    const save = dialog.querySelector("#lookup-save");
    const errorBox = dialog.querySelector("#lookup-error");
    const closes = dialog.querySelectorAll("[data-close]");

    let saving = false;

    closes.forEach((close) => {
      close.onclick = () => dialog.close();
    });

    dialog.addEventListener("close", () => dialog.remove());

    dialog.addEventListener("cancel", (event) => {
      if (saving) event.preventDefault();
    });

    dialog.querySelector("#lookup-form").onsubmit = async (event) => {
      event.preventDefault();

      if (saving) return;

      const name = dialog.querySelector("#lookup-name").value.trim();

      if (!name) {
        errorBox.textContent = `Vui lòng nhập tên ${title}.`;
        errorBox.hidden = false;
        return;
      }

      saving = true;
      save.disabled = true;
      save.textContent = "Đang lưu...";
      errorBox.hidden = true;

      closes.forEach((close) => (close.disabled = true));

      try {
        await api.request(editing ? path + "/" + item.id : path, {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({ name }),
        });
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;

        saving = false;
        save.disabled = false;
        save.textContent = editing ? "Lưu thay đổi" : "Tạo mới";

        closes.forEach((close) => (close.disabled = false));
        return;
      }

      dialog.close();

      showSuccessToast(
        editing ? `Đã cập nhật ${title}.` : `Đã thêm ${title} thành công.`,
      );

      try {
        await renderLookup(target, kind);
      } catch (error) {
        showError(target, error);
      }
    };

    dialog.showModal();

    dialog.querySelector("#lookup-name").focus();
  }

  find("#lookup-add").onclick = () => openEditor();

  target.querySelectorAll("[data-lookup-edit]").forEach((button) => {
    button.onclick = () => {
      const item = items.find(
        (x) => Number(x.id) === Number(button.dataset.lookupEdit),
      );

      if (item) openEditor(item);
    };
  });

  // Modal xác nhận xóa

  target.querySelectorAll("[data-lookup-delete]").forEach((button) => {
    button.onclick = () => {
      const item = items.find(
        (x) => Number(x.id) === Number(button.dataset.lookupDelete),
      );

      if (!item || item.product_count > 0) return;

      const dialog = document.createElement("dialog");

      dialog.className = "stock-dialog customer-confirm-dialog";
      dialog.setAttribute("aria-labelledby", "lookup-delete-title");

      dialog.innerHTML = `
          <div class="stock-dialog-head">

            <h2 id="lookup-delete-title">Xóa ${title}</h2>

            <button type="button" data-close
              aria-label="Đóng">×</button>

          </div>

          <p class="customer-confirm-message">
            Bạn có chắc chắn muốn xóa ${title}
            <strong>${esc(item.name)}</strong>?
          </p>

          <p class="mini-note">
            Thao tác này không thể hoàn tác.
          </p>

          <p id="lookup-delete-error"
            class="form-alert error"
            role="alert" hidden></p>

          <div class="stock-dialog-actions">

            <button type="button"
              class="button button-outline"
              data-close>Hủy bỏ</button>

            <button type="button"
              class="button lookup-delete-confirm"
              id="lookup-delete-save">

              Xác nhận xóa

            </button>
          </div>
        `;

      target.appendChild(dialog);

      const save = dialog.querySelector("#lookup-delete-save");
      const errorBox = dialog.querySelector("#lookup-delete-error");
      const closes = dialog.querySelectorAll("[data-close]");

      let saving = false;

      closes.forEach((close) => {
        close.onclick = () => dialog.close();
      });

      dialog.addEventListener("close", () => dialog.remove());

      dialog.addEventListener("cancel", (event) => {
        if (saving) event.preventDefault();
      });

      save.onclick = async () => {
        if (saving) return;

        saving = true;
        save.disabled = true;
        save.textContent = "Đang xóa...";
        errorBox.hidden = true;

        closes.forEach((close) => (close.disabled = true));

        try {
          await api.request(path + "/" + item.id, { method: "DELETE" });
        } catch (error) {
          errorBox.textContent = error.message;
          errorBox.hidden = false;

          saving = false;
          save.disabled = false;
          save.textContent = "Xác nhận xóa";

          closes.forEach((close) => (close.disabled = false));
          return;
        }

        dialog.close();

        showSuccessToast(`Đã xóa ${title} thành công.`);

        try {
          await renderLookup(target, kind);
        } catch (error) {
          showError(target, error);
        }
      };

      dialog.showModal();
    };
  });
}



  
async function renderContacts(target, page = 1) {
  const pageSize = 10;

  const labels = {
    new: "Chưa xử lý",
    in_progress: "Đang xử lý",
    closed: "Đã hoàn tất",
  };

  const loadPage = (pageNumber) =>
    api.request(
      "/admin/contact-messages?" +
        new URLSearchParams({
          page: pageNumber,
          page_size: 20,
        }),
    );

  const result = await loadPage(1);
  const items = [...(result.items || [])];

  let nextPage = 2;

  while (items.length < result.total) {
    const next = await loadPage(nextPage);

    if (!next.items?.length) break;

    items.push(...next.items);
    nextPage++;
  }

  const newCount = items.filter((item) => item.status === "new").length;

  const processingCount = items.filter(
    (item) => item.status === "in_progress",
  ).length;

  const closedCount = items.filter((item) => item.status === "closed").length;

  target.innerHTML = `
    <div class="panel management-contacts-panel">

      <p class="customers-description">
        Tiếp nhận và xử lý yêu cầu hỗ trợ từ khách hàng.
      </p>

      <div class="order-kpis">

        <article class="order-kpi">
          <span>Tổng yêu cầu</span>
          <strong>${items.length}</strong>
          <small>Toàn bộ yêu cầu liên hệ</small>
        </article>

        <article class="order-kpi">
          <span>Chưa xử lý</span>
          <strong>${newCount}</strong>
          <small>Đang chờ tiếp nhận</small>
        </article>

        <article class="order-kpi">
          <span>Đang xử lý</span>
          <strong>${processingCount}</strong>
          <small>Đang hỗ trợ khách hàng</small>
        </article>

        <article class="order-kpi">
          <span>Đã hoàn tất</span>
          <strong>${closedCount}</strong>
          <small>Yêu cầu đã được giải quyết</small>
        </article>

      </div>

      <div class="order-list-heading">
        <h3>Danh sách yêu cầu liên hệ</h3>
      </div>

      <div class="management-customers-toolbar">

        <label>
          <span>Tìm kiếm</span>

          <input id="contact-search"
            type="search"
            placeholder="Tìm tên, email, chủ đề, nội dung...">
        </label>

        <label>
          <span>Trạng thái</span>

          <select id="contact-filter">

            <option value="">Tất cả trạng thái</option>

            ${Object.entries(labels)
              .map(([key, value]) => `<option value="${key}">${value}</option>`)
              .join("")}

          </select>

        </label>

      </div>

      <p id="contact-count"
        class="mini-note customer-result-count"></p>

      <div class="table-wrap">

        <table class="data-table management-contacts-table">

          <thead>
            <tr>
              <th>Người gửi</th>
              <th>Chủ đề / Nội dung</th>
              <th>Ngày gửi</th>
              <th>Trạng thái</th>
              <th>Thao tác</th>
            </tr>
          </thead>

          <tbody>

            ${items
              .map(
                (item) => `

              <tr data-contact-id="${item.id}">

                <td>
                  <strong>${esc(item.full_name)}</strong>

                  <small class="order-secondary">
                    ${esc(item.email)}
                  </small>
                </td>

                <td>

                  <strong>${esc(item.topic)}</strong>

                  <p class="contact-message-preview">
                    ${esc(item.message)}
                  </p>

                </td>

                <td>

                  ${new Date(item.created_at).toLocaleDateString("vi-VN")}

                  <small class="order-secondary">
                    #${item.id}
                  </small>

                </td>

                <td>

                  <select
                    class="contact-state-select state-${esc(item.status)}"
                    data-contact-status="${item.id}"
                    aria-label="Trạng thái liên hệ #${item.id}">

                    ${Object.entries(labels)
                      .map(
                        ([key, value]) =>
                          `<option value="${key}"
                          ${item.status === key ? "selected" : ""}>
                          ${value}
                        </option>`,
                      )
                      .join("")}

                  </select>

                </td>

                <td>
                  <button class="button-sm"
                    type="button"
                    data-contact-detail="${item.id}">
                    Chi tiết
                  </button>
                </td>

              </tr>

            `,
              )
              .join("")}

            <tr id="contact-empty" hidden>
              <td colspan="5" class="customer-empty">
                Không tìm thấy yêu cầu liên hệ phù hợp.
              </td>
            </tr>

          </tbody>
        </table>
      </div>

      <div class="ap-pager">

        <span id="contact-page-info"></span>

        <div class="ap-page-actions">

          <button id="contact-prev" type="button">
            ← Trước
          </button>

          <button id="contact-next" type="button">
            Sau →
          </button>

        </div>

      </div>
    </div>
  `;

  const searchInput = target.querySelector("#contact-search");
  const statusFilter = target.querySelector("#contact-filter");

  const previous = target.querySelector("#contact-prev");
  const next = target.querySelector("#contact-next");

  let currentPage = page;

  searchInput.value = target.dataset.contactSearch || "";
  statusFilter.value = target.dataset.contactFilter || "";

  function normalize(value) {
    return String(value ?? "")
      .toLocaleLowerCase("vi")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .trim();
  }

  function applyFilters(resetPage = false) {
    if (resetPage) currentPage = 1;

    const keyword = normalize(searchInput.value);
    const status = statusFilter.value;

    const matched = items.filter((item) => {
      const searchable = normalize(
        `${item.id} ${item.full_name}
         ${item.email} ${item.topic} ${item.message}`,
      );

      return (
        searchable.includes(keyword) && (!status || item.status === status)
      );
    });

    const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));

    currentPage = Math.min(currentPage, totalPages);

    const start = (currentPage - 1) * pageSize;

    const visible = new Set(
      matched.slice(start, start + pageSize).map((item) => String(item.id)),
    );

    target.querySelectorAll("[data-contact-id]").forEach((row) => {
      row.hidden = !visible.has(row.dataset.contactId);
    });

    target.querySelector("#contact-empty").hidden = matched.length !== 0;

    target.querySelector("#contact-count").textContent =
      `Hiển thị ${matched.length ? start + 1 : 0}–${Math.min(start + pageSize, matched.length)} / ${matched.length} yêu cầu`;

    target.querySelector("#contact-page-info").textContent =
      `Trang ${currentPage} / ${totalPages}`;

    previous.disabled = currentPage <= 1;
    next.disabled = currentPage >= totalPages;
  }

  searchInput.oninput = () => {
    target.dataset.contactSearch = searchInput.value;
    applyFilters(true);
  };

  statusFilter.onchange = () => {
    target.dataset.contactFilter = statusFilter.value;
    applyFilters(true);
  };

  previous.onclick = () => {
    currentPage--;
    applyFilters();
  };

  next.onclick = () => {
    currentPage++;
    applyFilters();
  };

  applyFilters();

  // Cập nhật trạng thái

  target.querySelectorAll("[data-contact-status]").forEach((select) => {
    select.onchange = async () => {
      const item = items.find(
        (x) => Number(x.id) === Number(select.dataset.contactStatus),
      );

      if (!item) return;

      select.disabled = true;

      try {
        await api.request("/admin/contact-messages/" + item.id, {
          method: "PATCH",
          body: JSON.stringify({
            status: select.value,
          }),
        });
      } catch (error) {
        select.value = item.status;
        select.disabled = false;

        showErrorToast(error);
        return;
      }

      showSuccessToast("Đã cập nhật trạng thái yêu cầu liên hệ.");

      try {
        await renderContacts(target, currentPage);
      } catch (error) {
        showError(target, error);
      }
    };
  });

  // Modal đọc đầy đủ nội dung liên hệ

  target.querySelectorAll("[data-contact-detail]").forEach((button) => {
    button.onclick = () => {
      const item = items.find(
        (x) => Number(x.id) === Number(button.dataset.contactDetail),
      );

      if (!item) return;

      const dialog = document.createElement("dialog");

      dialog.className = "stock-dialog contact-detail-dialog";

      dialog.setAttribute("aria-labelledby", "contact-detail-title");

      dialog.innerHTML = `

          <div class="stock-dialog-head">

            <h2 id="contact-detail-title">
              Chi tiết yêu cầu liên hệ
            </h2>

            <button type="button" data-close
              aria-label="Đóng">×</button>

          </div>

          <div class="customer-detail-profile">

            <div class="customer-avatar">

              <svg viewBox="0 0 24 24"
                fill="none" aria-hidden="true">
                <circle cx="12" cy="8" r="3.5"/>
                <path d="M5 21c0-5 3-8 7-8s7 3 7 8"/>
              </svg>

            </div>

            <div>
              <strong>${esc(item.full_name)}</strong>
              <small>${esc(item.email)}</small>
            </div>

          </div>

          <dl class="customer-detail-info">

            <div>
              <dt>Mã yêu cầu</dt>
              <dd>#${item.id}</dd>
            </div>

            <div>
              <dt>Thời gian gửi</dt>

              <dd>
                ${new Date(item.created_at).toLocaleString("vi-VN")}
              </dd>
            </div>

            <div>
              <dt>Trạng thái</dt>

              <dd>
                <span class="contact-state-select state-${esc(item.status)}">
                  ${esc(labels[item.status] || item.status)}
                </span>
              </dd>
            </div>

          </dl>

          <div class="contact-full-message">

            <h3>${esc(item.topic)}</h3>

            <p>${esc(item.message)}</p>

          </div>

          <div class="stock-dialog-actions">

            <button class="button button-dark"
              type="button"
              data-close>Đóng</button>

          </div>
        `;

      target.appendChild(dialog);

      dialog.querySelectorAll("[data-close]").forEach((close) => {
        close.onclick = () => dialog.close();
      });

      dialog.addEventListener("close", () => dialog.remove());

      dialog.showModal();
    };
  });
}


  window.LUMIERE_BACKEND_CONSOLE = async ({ mount, section, role }) => {
    const target = shell(mount, section, role);
    target.textContent = "Đang tải dữ liệu Business API…";
    try {
      if (section === "dashboard") await renderDashboard(target, false);
      else if (section === "analytics") await renderDashboard(target, true);
      else if (section === "products" || section === "inventory") await renderProducts(target, section, role);
      else if (section === "orders" || section === "staff-orders") await renderOrders(target, role);
      else if (section === "customers") await renderCustomers(target);
      else if (section === "staff") await renderStaff(target);
      else if (section === "coupons") await renderCoupons(target);
      else if (section === "categories" || section === "brands") await renderLookup(target, section);
      else if (section === "contacts") await renderContacts(target);
      else if (section === "staff-inventory") await renderProducts(target, "inventory", role);
      else throw new Error("Trang này chưa có contract Backend.");
    } catch (error) {
      showError(target, error);
    }
  };
})();
