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
      dashboard: "Tổng quan", products: "Sản phẩm", orders: "Đơn hàng",
      customers: "Khách hàng", staff: "Nhân viên", coupons: "Mã giảm giá",
      inventory: "Tồn kho", analytics: "Phân tích doanh thu",
      categories: "Danh mục", brands: "Thương hiệu"
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

  function showError(target, error) {
    target.innerHTML = `<div class="form-alert" role="alert">${esc(error.message || error)}</div>`;
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
      select.addEventListener("change", async () => {
        select.disabled = true;
        try {
          await api.updateOrderStatus(select.dataset.status, select.value, role);
          await renderOrders(target, role, page);
        } catch (error) {
          await renderOrders(target, role, page);
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

  async function renderCustomers(target) {
    let page = 1;
    let search = "";
    let active = "";
    async function draw() {
      const filters = { search, ...(active === "" ? {} : { is_active: active === "active" }) };
      const result = await api.adminCustomers(page, 20, filters);
      target.innerHTML = `<div class="panel">
        <div class="toolbar"><input id="customer-search" type="search" value="${esc(search)}" placeholder="Tên, email, điện thoại">
          <select id="customer-active"><option value="">Mọi trạng thái</option><option value="active" ${active === "active" ? "selected" : ""}>Hoạt động</option><option value="locked" ${active === "locked" ? "selected" : ""}>Đã khóa</option></select>
        </div><div class="table-wrap"><table class="data-table"><thead><tr><th>Khách hàng</th><th>Liên hệ</th><th>Ngày tạo</th><th>Số đơn</th><th>Chi tiêu</th><th>Trạng thái</th><th></th></tr></thead><tbody>
        ${result.items.map(customer => `<tr><td>${esc(customer.full_name)}</td><td>${esc(customer.email)}<br>${esc(customer.phone || "—")}</td>
        <td>${new Date(customer.created_at).toLocaleDateString("vi-VN")}</td><td>${customer.order_count}</td>
        <td>${money(customer.total_spent_vnd)}</td><td>${customer.is_active ? "Hoạt động" : "Đã khóa"}</td>
        <td><button class="button-sm" type="button" data-detail="${customer.id}">Chi tiết</button>
        <button class="button-sm" type="button" data-toggle="${customer.id}" data-active="${customer.is_active}">${customer.is_active ? "Khóa" : "Mở khóa"}</button></td></tr>`).join("") || '<tr><td colspan="7">Không tìm thấy khách hàng.</td></tr>'}
        </tbody></table></div><p>${result.total} khách hàng · Trang ${result.page}</p>
        <button id="customer-prev" ${page <= 1 ? "disabled" : ""}>← Trước</button>
        <button id="customer-next" ${page * result.page_size >= result.total ? "disabled" : ""}>Sau →</button><div id="customer-detail"></div></div>`;
      target.querySelector("#customer-search").addEventListener("change", event => { search = event.target.value; page = 1; draw().catch(error => showError(target, error)); });
      target.querySelector("#customer-active").addEventListener("change", event => { active = event.target.value; page = 1; draw().catch(error => showError(target, error)); });
      target.querySelector("#customer-prev").addEventListener("click", () => { page -= 1; draw().catch(error => showError(target, error)); });
      target.querySelector("#customer-next").addEventListener("click", () => { page += 1; draw().catch(error => showError(target, error)); });
      target.querySelectorAll("[data-toggle]").forEach(button => button.addEventListener("click", async () => {
        button.disabled = true;
        try { await api.setCustomerStatus(button.dataset.toggle, button.dataset.active !== "true"); await draw(); }
        catch (error) { showError(target, error); }
      }));
      target.querySelectorAll("[data-detail]").forEach(button => button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const customer = await api.customer(button.dataset.detail);
          target.querySelector("#customer-detail").innerHTML = `<section class="panel"><h3>${esc(customer.full_name)}</h3>
            <p>${esc(customer.email)} · ${esc(customer.phone || "Chưa có số điện thoại")}</p>
            <p>Trạng thái: ${customer.is_active ? "Hoạt động" : "Đã khóa"}</p>
            <p>${customer.order_count} đơn · Tổng chi tiêu ${money(customer.total_spent_vnd)}</p></section>`;
        } catch (error) { target.insertAdjacentHTML("afterbegin", `<p class="form-alert" role="alert">${esc(error.message)}</p>`); }
        finally { button.disabled = false; }
      }));
    }
    await draw();
  }

  async function renderStaff(target) {
    let page = 1;
    async function draw() {
      const result = await api.adminStaff(page, 20);
      target.innerHTML = `<div class="panel"><button class="button button-dark" id="staff-create">+ Tạo tài khoản Staff</button>
        <p>Tạo tài khoản Staff yêu cầu mật khẩu khởi tạo. Backend không gửi email đặt lại mật khẩu.</p>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Họ tên</th><th>Email</th><th>Điện thoại</th><th>Trạng thái</th><th></th></tr></thead><tbody>
        ${result.items.map(staff => `<tr><td>${esc(staff.full_name)}</td><td>${esc(staff.email)}</td><td>${esc(staff.phone || "—")}</td>
        <td>${staff.is_active ? "Hoạt động" : "Đã khóa"}</td><td><button class="button-sm" data-edit="${staff.id}" data-name="${esc(staff.full_name)}" data-phone="${esc(staff.phone || "")}">Sửa</button>
        <button class="button-sm" data-toggle="${staff.id}" data-active="${staff.is_active}">${staff.is_active ? "Khóa" : "Mở khóa"}</button></td></tr>`).join("") || '<tr><td colspan="5">Chưa có tài khoản Staff.</td></tr>'}
        </tbody></table></div><p>${result.total} nhân viên · Trang ${result.page}</p>
        <button id="staff-prev" ${page <= 1 ? "disabled" : ""}>← Trước</button>
        <button id="staff-next" ${page * result.page_size >= result.total ? "disabled" : ""}>Sau →</button></div>`;
      target.querySelector("#staff-create").addEventListener("click", async () => {
        const full_name = window.prompt("Họ tên nhân viên:");
        if (full_name === null) return;
        const email = window.prompt("Email:");
        if (email === null) return;
        const password = window.prompt("Mật khẩu khởi tạo (tối thiểu 8 ký tự):");
        if (password === null) return;
        const phone = window.prompt("Số điện thoại (không bắt buộc):") || null;
        try { await api.createStaff({ full_name, email, password, phone }); await draw(); }
        catch (error) { showError(target, error); }
      });
      target.querySelector("#staff-prev").addEventListener("click", () => { page -= 1; draw().catch(error => showError(target, error)); });
      target.querySelector("#staff-next").addEventListener("click", () => { page += 1; draw().catch(error => showError(target, error)); });
      target.querySelectorAll("[data-toggle]").forEach(button => button.addEventListener("click", async () => {
        button.disabled = true;
        try { await api.setStaffStatus(button.dataset.toggle, button.dataset.active !== "true"); await draw(); }
        catch (error) { showError(target, error); }
      }));
      target.querySelectorAll("[data-edit]").forEach(button => button.addEventListener("click", async () => {
        const full_name = window.prompt("Họ tên:", button.dataset.name);
        if (full_name === null) return;
        const phone = window.prompt("Số điện thoại (để trống để xóa):", button.dataset.phone);
        if (phone === null) return;
        try { await api.updateStaff(button.dataset.edit, { full_name, phone: phone || null }); await draw(); }
        catch (error) { showError(target, error); }
      }));
    }
    await draw();
  }

  async function renderProducts(target, section, role) {
    const rows = await loadAllProducts(role === "admin");
    target.innerHTML = `<div class="panel"><p>Giá và tồn kho là dữ liệu Business API. Backend hiện không hỗ trợ tạo/xóa sản phẩm; chỉ sửa trường được API cho phép.</p>
      <div class="toolbar" style="display:flex;gap:12px;flex-wrap:wrap;margin:16px 0">
  <input
    id="product-search"
    type="search"
    placeholder="Tìm tên sản phẩm, SKU hoặc ID..."
    aria-label="Tìm sản phẩm"
    style="flex:1;min-width:240px;padding:10px"
  >
  <select id="product-category" aria-label="Lọc danh mục">
    <option value="">Tất cả danh mục</option>
    ${[...new Set(rows.map(item => item.category?.name || ""))]
      .filter(Boolean)
      .sort((a,b) => a.localeCompare(b,"vi"))
      .map(name => `<option value="${esc(name)}">${esc(name)}</option>`)
      .join("")}
  </select>
</div>
<p id="product-search-count"></p>
<div class="table-wrap"><table class="data-table"><thead><tr><th>ID / SKU</th><th>Sản phẩm</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th>${section === "inventory" ? "<th>Điều chỉnh</th>" : "<th>Thông tin</th>"}</tr></thead><tbody>
      ${rows.map(item => `<tr><td>${item.id} / ${esc(item.sku)}</td><td>${esc(item.name)}</td><td>${esc(item.category.name)}</td>
      <td>${money(item.price_vnd)}</td><td>${item.stock}</td><td>${section === "inventory"
        ? `<button class="button-sm" data-stock="${item.id}" data-value="${item.stock}">Cập nhật tồn</button>`
        : `<button class="button-sm" data-edit="${item.id}" data-name="${esc(item.name)}" data-price="${item.price_vnd}">Sửa tên / giá</button>`}</td></tr>`).join("")}
      </tbody></table></div></div>`;
    const productSearch = target.querySelector("#product-search");
    const categoryFilter = target.querySelector("#product-category");
    const productCount = target.querySelector("#product-search-count");
    const productTable = target.querySelector(".table-wrap tbody");
    function normalizeProductText(value) {
      return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLocaleLowerCase("vi")
        .trim();
    }
    function filterProducts() {
      const keyword = normalizeProductText(productSearch.value);
      const category = categoryFilter.value;
      let count = 0;
      productTable.querySelectorAll("tr").forEach(row => {
        const identity = row.cells[0]?.textContent || "";
        const name = row.cells[1]?.textContent || "";
        const categoryName = row.cells[2]?.textContent?.trim() || "";
        const searchable = normalizeProductText(
          identity + " " + name
        );
        const match =
          searchable.includes(keyword) &&
          (!category || categoryName === category);
        row.style.display = match ? "" : "none";
        if (match) count++;
      });
      productCount.textContent =
        `Hiển thị ${count} / ${rows.length} sản phẩm`;
      if (count === 0) {
        productCount.textContent += " — Không tìm thấy sản phẩm phù hợp.";
      }
    }
    productSearch.addEventListener("input", filterProducts);
    categoryFilter.addEventListener("change", filterProducts);
    filterProducts();
    if (section === "products" && role === "admin") {
      const addButton = document.createElement("button");
      addButton.type = "button";
      addButton.className = "button button-dark";
      addButton.textContent = "+ Thêm sản phẩm";
      addButton.style.margin = "16px 0";
      target.querySelector(".panel > p")
        .insertAdjacentElement("afterend", addButton);
      const dialog = document.createElement("dialog");
      dialog.style.width = "min(680px, 94vw)";
      dialog.style.maxHeight = "85vh";
      dialog.style.overflowY = "auto";
      dialog.style.padding = "24px";
      const lookupOptions = key => {
        const unique = new Map();
        rows.forEach(item => {
          const value = item[key];
          if (value && !unique.has(value.id)) {
            unique.set(value.id, value.name);
          }
        });
        return [...unique.entries()]
          .sort((a, b) => a[1].localeCompare(b[1], "vi"))
          .map(([id, name]) =>
            `<option value="${id}">${esc(name)}</option>`
          ).join("");
      };
      const nextId = Math.max(0, ...rows.map(p => p.id)) + 1;
      dialog.innerHTML = `
        <h2>Thêm sản phẩm mới</h2>
        <p>Thông tin sẽ được lưu vào PostgreSQL.</p>
        <form id="product-create-form">
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
            <label>ID sản phẩm
              <input name="id" type="number" min="1"
                value="${nextId}" required>
            </label>
            <label>SKU
              <input name="sku" maxlength="50" required>
            </label>
            <label>Barcode
              <input name="barcode" maxlength="50" required>
            </label>
            <label>Tên sản phẩm
              <input name="name" maxlength="255" required>
            </label>
            <label>Danh mục
              <select name="category_id" required>
                ${lookupOptions("category")}
              </select>
            </label>
            <label>Thương hiệu
              <select name="brand_id" required>
                ${lookupOptions("brand")}
              </select>
            </label>
            <label>Chất liệu
              <select name="material_id" required>
                ${lookupOptions("material")}
              </select>
            </label>
            <label>Đá
              <select name="gemstone_id" required>
                ${lookupOptions("gemstone")}
              </select>
            </label>
            <label>Bộ sưu tập
              <select name="collection_id" required>
                ${lookupOptions("collection")}
              </select>
            </label>
            <label>Trọng lượng
              <input name="weight" type="number"
                min="0.01" step="0.01" required>
            </label>
            <label>Giá bán (VNĐ)
              <input name="sale_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Giá sỉ (VNĐ)
              <input name="wholesale_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Giá vốn (VNĐ)
              <input name="cost_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Số lượng tồn
              <input name="stock" type="number"
                min="0" step="1" required>
            </label>
          </div>
          <p id="create-product-error"
            role="alert"
            style="color:#b42318;margin-top:12px"></p>
          <div style="display:flex;gap:12px;margin-top:20px">
            <button type="submit" class="button button-dark">
              Lưu sản phẩm
            </button>
            <button type="button" id="cancel-create-product"
              class="button button-outline">
              Hủy
            </button>
          </div>
        </form>
      `;
      target.appendChild(dialog);
      addButton.addEventListener("click", () => {
        dialog.showModal();
      });
      dialog.querySelector("#cancel-create-product")
        .addEventListener("click", () => dialog.close());
      const form = dialog.querySelector("#product-create-form");
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const data = new FormData(form);
        const numericIds = [
          "id", "category_id", "brand_id",
          "material_id", "gemstone_id", "collection_id", "stock"
        ];
        const prices = [
          "weight", "sale_price", "wholesale_price", "cost_price"
        ];
        const payload = {};
        for (const [key, value] of data.entries()) {
          payload[key] = numericIds.includes(key)
            ? Number(value)
            : prices.includes(key)
              ? String(value)
              : String(value).trim();
        }
        const errorBox = dialog.querySelector("#create-product-error");
        const submit = form.querySelector('[type="submit"]');
        errorBox.textContent = "";
        submit.disabled = true;
        try {
          await api.createProduct(payload);
          dialog.close();
          await renderProducts(target, section, role);
          window.alert("Đã thêm sản phẩm thành công!");
        } catch (error) {
          errorBox.textContent =
            error.message || "Không thể thêm sản phẩm.";
        } finally {
          submit.disabled = false;
        }
      });
    }    target.querySelectorAll("[data-edit]").forEach(button => button.addEventListener("click", async () => {
      const name = window.prompt("Tên sản phẩm:", button.dataset.name);
      if (name === null) return;
      const price = window.prompt("Giá mới (VNĐ):", button.dataset.price);
      if (price === null) return;
      try {
        await api.updateProduct(button.dataset.edit, {
          name: name.trim(),
          sale_price: price,
          expected_sale_price: button.dataset.price
        });
        await renderProducts(target, section, role);
      } catch (error) { showError(target, error); }
    }));
    target.querySelectorAll("[data-stock]").forEach(button => button.addEventListener("click", async () => {
      const stock = window.prompt("Tồn kho mới:", button.dataset.value);
      if (stock === null) return;
      if (!/^\d+$/.test(stock)) { showError(target, new Error("Tồn kho phải là số nguyên không âm.")); return; }
      try {
        await api.updateStock(button.dataset.stock, Number(button.dataset.value), Number(stock));
        await renderProducts(target, section, role);
      } catch (error) { showError(target, error); }
    }));
  }

  async function renderCoupons(target) {
    const result = await api.adminCoupons(1, 100);
    target.innerHTML = `<div class="panel"><p>Mã giảm giá được đọc từ Backend. Không có xóa; có thể bật/tắt hoặc tạo mới.</p>
      <button class="button button-dark" id="coupon-create">+ Tạo mã</button>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Mã</th><th>Loại</th><th>Giá trị</th><th>Đơn tối thiểu</th><th>Đã dùng</th><th>Trạng thái</th><th></th></tr></thead><tbody>
      ${result.items.map(coupon => `<tr><td>${esc(coupon.code)}</td><td>${coupon.discount_type === "percent" ? "Phần trăm" : "Số tiền"}</td>
      <td>${coupon.discount_type === "percent" ? `${coupon.discount_value}%` : money(coupon.discount_value)}</td>
      <td>${money(coupon.min_order_vnd)}</td><td>${coupon.used_count}${coupon.usage_limit ? ` / ${coupon.usage_limit}` : ""}</td>
      <td>${coupon.is_active ? "Đang bật" : "Đã tắt"}</td><td><button class="button-sm" data-edit="${coupon.id}" data-code="${esc(coupon.code)}" data-type="${coupon.discount_type}" data-value="${coupon.discount_value}" data-min="${coupon.min_order_vnd}">Sửa</button>
      <button class="button-sm" data-toggle="${coupon.id}" data-active="${coupon.is_active}">${coupon.is_active ? "Tắt" : "Bật"}</button></td></tr>`).join("")}
      </tbody></table></div></div>`;
    target.querySelector("#coupon-create").addEventListener("click", async () => {
      const code = window.prompt("Mã (3–24 ký tự A-Z, số, _ hoặc -):");
      if (code === null) return;
      const discount_type = window.prompt("Loại giảm: fixed hoặc percent", "percent");
      if (discount_type === null) return;
      const discount_value = window.prompt("Giá trị giảm:");
      if (discount_value === null) return;
      const min_order_vnd = window.prompt("Đơn tối thiểu (VNĐ):", "0");
      if (min_order_vnd === null) return;
      const starts_at = window.prompt("Thời điểm bắt đầu (ISO kèm timezone):", new Date().toISOString());
      if (starts_at === null) return;
      const ends_at = window.prompt("Thời điểm kết thúc (ISO kèm timezone):");
      if (ends_at === null) return;
      let max_discount_vnd = null;
      if (discount_type === "percent") {
        max_discount_vnd = window.prompt("Giảm tối đa (VNĐ):");
        if (max_discount_vnd === null) return;
      }
      try {
        await api.createCoupon({
          code, discount_type, discount_value, min_order_vnd,
          max_discount_vnd, starts_at, ends_at, is_active: true
        });
        await renderCoupons(target);
      } catch (error) { showError(target, error); }
    });
    target.querySelectorAll("[data-edit]").forEach(button => button.addEventListener("click", async () => {
      const code = window.prompt("Mã giảm giá:", button.dataset.code);
      if (code === null) return;
      const discount_value = window.prompt("Giá trị giảm:", button.dataset.value);
      if (discount_value === null) return;
      const min_order_vnd = window.prompt("Đơn tối thiểu (VNĐ):", button.dataset.min);
      if (min_order_vnd === null) return;
      try {
        await api.updateCoupon(button.dataset.edit, { code, discount_value, min_order_vnd });
        await renderCoupons(target);
      } catch (error) { showError(target, error); }
    }));
    target.querySelectorAll("[data-toggle]").forEach(button => button.addEventListener("click", async () => {
      try {
        await api.setCouponStatus(button.dataset.toggle, button.dataset.active !== "true");
        await renderCoupons(target);
      } catch (error) { showError(target, error); }
    }));
  }

  async function renderDashboard(target, analytics) {
    if (analytics) {
      const now = new Date();
      const dateValue = value => [
        value.getFullYear(),
        String(value.getMonth() + 1).padStart(2, "0"),
        String(value.getDate()).padStart(2, "0")
      ].join("-");
      const start = dateValue(new Date(now.getFullYear(), now.getMonth(), 1));
      const end = dateValue(now);
      const result = await api.revenue(start, end);
      target.innerHTML = `<div class="panel"><p>Tiền thanh toán được xác nhận từ Backend; không phải lợi nhuận hoặc doanh thu thuần sau hoàn tiền.</p>
        <strong>${money(result.confirmed_payment_amount_vnd)} · ${result.confirmed_payment_order_count} giao dịch xác nhận</strong>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Ngày</th><th>Số đơn thanh toán</th><th>Số tiền xác nhận</th></tr></thead><tbody>
        ${result.items.map(row => `<tr><td>${esc(row.period_start)}</td><td>${row.confirmed_payment_order_count}</td><td>${money(row.confirmed_payment_amount_vnd)}</td></tr>`).join("")}</tbody></table></div></div>`;
      return;
    }
    const result = await api.dashboard();
    target.innerHTML = `<div class="dashboard-grid">
      <div class="stat"><span>Tổng đơn hàng</span><strong>${result.total_orders}</strong></div>
      <div class="stat"><span>Sản phẩm</span><strong>${result.total_products}</strong></div>
      <div class="stat"><span>Đã hết hàng</span><strong>${result.out_of_stock_products}</strong></div>
      <div class="stat"><span>Tiền xác nhận</span><strong>${money(result.confirmed_payment_amount_vnd)}</strong></div></div>
      <div class="panel"><h3>Đơn theo trạng thái</h3>${Object.entries(result.orders_by_status).map(([key, count]) => `<p>${esc(statusNames[key] || key)}: ${count}</p>`).join("")}
      <h3>Cần đối soát</h3><p>${result.reconciliation_order_count} đơn · tổng giá trị đơn ${money(result.reconciliation_order_value_vnd)}</p>
      <ul>${result.reconciliation_reasons.map(row => `<li>${esc(row.reason)}: ${row.order_count}</li>`).join("")}</ul>
      <p>Tiền xác nhận là khoản thanh toán được hệ thống xác nhận, không phải lợi nhuận/doanh thu thuần.</p></div>`;
  }


  async function renderLookup(target, kind) {
    const title = kind === "brands" ? "thương hiệu" : "danh mục";
    const path = "/admin/" + kind;
    const result = await api.request(path);
    const items = result.items || [];
    const used = items.filter(x => x.product_count > 0).length;
    target.innerHTML = `<div class="tax-head"><div><h2>Quản lý ${title}</h2><p class="mini-note">Dữ liệu thật từ PostgreSQL · Chỉ Admin có quyền thay đổi.</p></div><button id="lookup-add" class="button button-dark" type="button">+ Thêm ${title}</button></div>
    <div class="tax-stats"><div class="tax-stat"><span>Tổng ${title}</span><strong>${items.length}</strong></div><div class="tax-stat"><span>Đang có sản phẩm</span><strong>${used}</strong></div><div class="tax-stat"><span>Chưa sử dụng</span><strong>${items.length-used}</strong></div></div>
    <div class="panel"><div class="toolbar"><input type="search" id="lookup-search" placeholder="Tìm tên hoặc mã ${title}..." aria-label="Tìm kiếm" style="width:min(100%,420px);padding:12px;border:1px solid #d9c9b4"><span id="lookup-count">${items.length} kết quả</span></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Mã</th><th>Tên ${title}</th><th>Số sản phẩm</th><th>Tình trạng</th><th>Thao tác</th></tr></thead>
    <tbody id="lookup-rows">${items.map(x=>`<tr data-lookup-row data-search="${esc(x.id+' '+x.name).toLowerCase()}"><td><strong>#${x.id}</strong></td><td>${esc(x.name)}</td><td>${x.product_count}</td><td><span class="tax-status ${x.product_count?'active':'inactive'}">${x.product_count?'Đang sử dụng':'Chưa sử dụng'}</span></td><td class="row-actions"><button class="button-sm" data-lookup-edit="${x.id}" type="button">Sửa tên</button><button class="button-sm" data-lookup-delete="${x.id}" type="button" ${x.product_count?'disabled title="Đang được sản phẩm sử dụng"':''}>Xóa</button></td></tr>`).join('')||'<tr><td colspan="5">Chưa có dữ liệu</td></tr>'}</tbody></table></div>
    <p class="mini-note">Lưu ý: thay đổi tên ${title} có thể khiến dữ liệu mô tả của AI cần đồng bộ lại. Không xóa được ${title} đang gắn với sản phẩm.</p></div>
    <dialog class="ap-modal" id="lookup-modal"><div class="ap-modal-head"><h2 id="lookup-dialog-title">Thêm ${title}</h2><button class="ap-close" id="lookup-close" type="button" aria-label="Đóng">×</button></div>
    <form class="ap-form" id="lookup-form"><div class="field"><label for="lookup-name">Tên ${title}</label><input id="lookup-name" maxlength="150" required></div><p id="lookup-error" class="form-alert error" hidden></p><div class="ap-actions"><button class="button button-outline" type="button" id="lookup-cancel">Hủy</button><button class="button button-dark" type="submit">Lưu thay đổi</button></div></form></dialog>`;
    const find = selector => target.querySelector(selector);
    const modal = find("#lookup-modal");
    let editing = null;
    function open(item=null) {
      editing = item;
      find("#lookup-dialog-title").textContent=(item?"Sửa ":"Thêm ")+title;
      find("#lookup-name").value=item?.name||"";
      find("#lookup-error").hidden=true;
      modal.showModal();
      find("#lookup-name").focus();
    }
    find("#lookup-add").onclick=()=>open();
    find("#lookup-close").onclick=()=>modal.close();
    find("#lookup-cancel").onclick=()=>modal.close();
    find("#lookup-search").oninput=event=>{
      const query=event.target.value.trim().toLocaleLowerCase("vi");
      let visible=0;
      find("#lookup-rows").querySelectorAll("[data-lookup-row]").forEach(row=>{
        row.hidden=!row.dataset.search.toLocaleLowerCase("vi").includes(query);
        if(!row.hidden)visible++;
      });
      find("#lookup-count").textContent=visible+" kết quả";
    };
    find("#lookup-form").onsubmit=async event=>{
      event.preventDefault();
      const submit=find('#lookup-form button[type="submit"]');
      const name=find("#lookup-name").value.trim();
      if(!name)return;
      submit.disabled=true;
      try{
        await api.request(editing?path+"/"+editing.id:path,{method:editing?"PATCH":"POST",body:JSON.stringify({name})});
        modal.close();
        await renderLookup(target,kind);
      }catch(error){find("#lookup-error").hidden=false;find("#lookup-error").textContent=error.message}
      finally{submit.disabled=false}
    };
    find("#lookup-rows").querySelectorAll("[data-lookup-edit]").forEach(button=>button.onclick=()=>{
      open(items.find(x=>x.id===Number(button.dataset.lookupEdit)));
    });
    find("#lookup-rows").querySelectorAll("[data-lookup-delete]").forEach(button=>button.onclick=async()=>{
      const item=items.find(x=>x.id===Number(button.dataset.lookupDelete));
      if(!item||item.product_count>0)return;
      if(!confirm("Xóa "+title+" “"+item.name+"”? Không thể hoàn tác."))return;
      try{await api.request(path+"/"+item.id,{method:"DELETE"});await renderLookup(target,kind)}
      catch(error){showError(target,error)}
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
      else if (section === "staff-inventory") await renderProducts(target, "inventory", role);
      else throw new Error("Trang này chưa có contract Backend.");
    } catch (error) {
      showError(target, error);
    }
  };
})();
