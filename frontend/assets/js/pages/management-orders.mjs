/** Existing controller, shared by Admin and Staff. */
export function createOrdersController({ api, esc, money, showError, statusNames, paymentNames }) {
  async function renderOrders(target, role, page = 1) {
    const payload = role === "admin" ? await api.adminOrders(page) : await api.staffOrders(page);
    const enrichedOrders = await Promise.all(payload.items.map(async order => {
      try {
        const path = role === "admin"
          ? `/orders/${order.id}`
          : `/staff/orders/${order.id}`;
        const detail = await api.request(path);
        return {
          ...order,
          recipient_name: detail.recipient_name,
          phone: detail.phone
        };
      } catch (error) {
        console.warn("Không tải được người nhận:", order.id, error);
        return order;
      }
    }));
    target.innerHTML = `<div class="panel"><p>Đơn thật lấy từ Business API. Trạng thái chỉ được cập nhật theo quy tắc Backend.</p>
      <div class="toolbar" style="display:flex;gap:12px;flex-wrap:wrap;margin:16px 0">
  <input id="orders-search" type="search"
    placeholder="Tìm mã đơn hoặc người nhận..."
    aria-label="Tìm kiếm đơn hàng"
    style="min-width:250px;flex:1;padding:10px">
  <select id="orders-filter-status" aria-label="Lọc trạng thái đơn hàng">
    <option value="">Tất cả trạng thái</option>
    ${Object.entries(statusNames).map(([value, label]) =>
      `<option value="${value}">${label}</option>`
    ).join("")}
  </select>
</div>
<div class="table-wrap"><table class="data-table"><thead><tr>
      <th>Mã đơn</th><th>Ngày đặt</th><th>Người nhận</th><th>Trạng thái</th>
      <th>Thanh toán</th><th>Tổng</th><th>Thao tác</th></tr></thead><tbody>
      ${enrichedOrders.map(order => `<tr data-phone="${esc(order.phone || "")}">
        <td>${esc(order.code)}</td><td>${new Date(order.created_at).toLocaleDateString("vi-VN")}</td>
        <td>${esc(order.recipient_name || "—")}</td>
        <td><select data-status="${order.id}" aria-label="Trạng thái ${esc(order.code)}">
          ${Object.entries(statusNames).map(([value, label]) =>
            `<option value="${value}" ${order.status === value ? "selected" : ""}>${label}</option>`
          ).join("")}
        </select></td>
        <td>${esc(paymentNames[order.payment_status] || order.payment_status)} · ${esc(order.payment_method.toUpperCase())}</td>
        <td>${money(order.total_vnd)}</td>
        <td><button class="button-sm" type="button" data-detail="${order.id}">Chi tiết</button>
        <button class="button-sm" type="button" data-cod="${order.id}"
          ${order.status !== "delivered" || order.payment_status !== "unpaid" || order.payment_method !== "cod" ? "disabled" : ""}>
          Xác nhận thu COD</button></td>
      </tr>`).join("") || '<tr><td colspan="7">Chưa có đơn hàng.</td></tr>'}
      </tbody></table></div><p>${payload.total} đơn · Trang ${payload.page}</p>
      <button id="orders-prev" ${page <= 1 ? "disabled" : ""}>← Trước</button>
      <button id="orders-next" ${page * payload.page_size >= payload.total ? "disabled" : ""}>Sau →</button>
      <div id="order-detail"></div></div>`;

    const searchInput = target.querySelector("#orders-search");
    const statusFilter = target.querySelector("#orders-filter-status");
    searchInput.value = target.dataset.orderSearch || "";
    statusFilter.value = target.dataset.orderStatus || "";
    function applyOrderFilters() {
      const keyword = searchInput.value.trim().toLocaleLowerCase("vi");
      const selectedStatus = statusFilter.value;
      target.querySelector(".table-wrap tbody")?.querySelectorAll("tr").forEach(row => {
        const code = row.cells[0]?.textContent || "";
        const recipient = row.cells[2]?.textContent || "";
        const text = (code + " " + recipient + " " + (row.dataset.phone || "")).toLocaleLowerCase("vi");
        const orderStatus = row.querySelector("[data-status]")?.value;
        row.hidden =
          !text.includes(keyword) ||
          (selectedStatus !== "" && orderStatus !== selectedStatus);
      });
    }
    searchInput.addEventListener("input", () => {
      target.dataset.orderSearch = searchInput.value;
      target.querySelector("#order-detail").innerHTML = "";
      applyOrderFilters();
    });
    statusFilter.addEventListener("change", () => {
      target.dataset.orderStatus = statusFilter.value;
      target.querySelector("#order-detail").innerHTML = "";
      applyOrderFilters();
    });
    applyOrderFilters();
    target.querySelector("#orders-prev").addEventListener("click", () => renderOrders(target, role, page - 1).catch(error => showError(target, error)));
    target.querySelector("#orders-next").addEventListener("click", () => renderOrders(target, role, page + 1).catch(error => showError(target, error)));
    target.querySelectorAll("[data-status]").forEach(select => {
      let savedStatus = payload.items.find(order => String(order.id) === select.dataset.status).status;
      select.addEventListener("change", async () => {
        if (select.disabled) return;
        select.disabled = true;
        try {
          await api.updateOrderStatus(select.dataset.status, select.value, role);
          savedStatus = select.value;
          await renderOrders(target, role, page);
        } catch (error) {
          select.value = savedStatus;
          select.disabled = false;
          target.insertAdjacentHTML("afterbegin", `<p class="form-alert" role="alert">${esc(error.message)}</p>`);
        }
      });
    });
    target.querySelectorAll("[data-detail]").forEach(button => button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const path = role === "admin" ? `/orders/${button.dataset.detail}` : `/staff/orders/${button.dataset.detail}`;
        const order = await api.request(path);
        target.querySelector("#order-detail").innerHTML = `<section class="panel"><h3>${esc(order.code)}</h3>
          <p>Người nhận: ${esc(order.recipient_name)} · ${esc(order.phone)}</p><p>Địa chỉ: ${esc(order.address)}</p>
          <div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>SKU</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>
          ${order.items.map(item => `<tr><td>${esc(item.product_name)}</td><td>${esc(item.sku)}</td><td>${item.quantity}</td><td>${money(item.unit_price_vnd)}</td><td>${money(item.line_total_vnd)}</td></tr>`).join("")}
          </tbody></table></div></section>`;
      } catch (error) { target.insertAdjacentHTML("afterbegin", `<p class="form-alert" role="alert">${esc(error.message)}</p>`); }
      finally { button.disabled = false; }
    }));
    target.querySelectorAll("[data-cod]").forEach(button => {
      button.addEventListener("click", async () => {
        const reference = window.prompt("Mã biên nhận COD (tối thiểu 3 ký tự):");
        if (reference === null) return;
        button.disabled = true;
        try {
          await api.confirmCod(button.dataset.cod, reference.trim(), role);
          await renderOrders(target, role, page);
        } catch (error) {
          showError(target, error);
          button.disabled = false;
        }
      });
    });
  }

  return renderOrders;
}
