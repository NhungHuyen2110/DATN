import { esc, money, showError } from "../shared/ui.mjs";
import { consoleShell } from "../shared/console-shell.mjs";

export function createManagementConsole() {
  const api = window.LUMIERE_API;
  const root = document.body.dataset.root || "../../";
  const statusNames = {
    pending: "Chờ xác nhận",
    confirmed: "Đã xác nhận",
    packing: "Đang đóng gói",
    shipping: "Đang giao",
    delivered: "Đã giao",
    cancelled: "Đã hủy"
  };
  const paymentNames = { unpaid: "Chưa thanh toán", paid: "Đã thanh toán", refunded: "Đã hoàn tiền" };

  async function loadAllProducts(admin = false) {
    const rows = [];
    let page = 1;
    let total = 0;
    do {
      const payload = admin
        ? await api.adminProducts(page, 100)
        : await api.products(page, 100);
      if (!Array.isArray(payload.items) || !Number.isInteger(payload.total) ||
          (payload.items.length === 0 && rows.length < payload.total)) {
        throw new Error("Dữ liệu phân trang sản phẩm không hợp lệ");
      }
      rows.push(...payload.items);
      total = payload.total;
      page += 1;
    } while (rows.length < total);
    return rows;
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
    if(analytics){
      target.innerHTML=`<div class="lm-admin-head"><div><h2>Hành vi mua hàng</h2><p class="mini-note">Phân tích dữ liệu đơn hàng thực, không phải lượt truy cập giả lập.</p></div><label class="field">Khoảng thời gian<select id="behavior-days"><option value="7">7 ngày gần đây</option><option value="30" selected>30 ngày gần đây</option><option value="90">90 ngày gần đây</option></select></label></div>
      <div id="behavior-results"><p>Đang phân tích đơn hàng...</p></div>
      <div class="panel lm-analytics-note"><h3>Phạm vi dữ liệu</h3><p>Số liệu lấy từ bảng đơn hàng và chi tiết đơn hàng PostgreSQL: số đơn, khách mua duy nhất, khách mua lại, sản phẩm được đặt và các đơn có mã giảm giá. Hệ thống chưa lưu sự kiện xem sản phẩm, nguồn truy cập hay tìm kiếm; vì vậy không hiển thị tỷ lệ chuyển đổi từ lượt xem hoặc lượt tìm kiếm.</p></div>`;
      const select=target.querySelector("#behavior-days");
      async function refresh(){
        const days=Number(select.value);
        const start=dateText(new Date(now.getFullYear(),now.getMonth(),now.getDate()-days+1));
        const output=target.querySelector("#behavior-results");
        output.innerHTML="<p>Đang tải dữ liệu PostgreSQL...</p>";
        try{
          const [behavior,revenue]=await Promise.all([
            api.request("/admin/reports/purchase-behavior?"+new URLSearchParams({start_date:start,end_date:today})),
            api.revenue(start,today)
          ]);
          const daily=behavior.daily_orders||[];
          const max=Math.max(1,...Object.values(behavior.orders_by_status||{}));
          output.innerHTML=`<div class="lm-kpis">
            <div class="lm-kpi"><span>Tổng đơn đã tạo</span><strong>${behavior.total_orders}</strong><small>Trong khoảng ngày đã chọn</small></div>
            <div class="lm-kpi"><span>Khách đã đặt hàng</span><strong>${behavior.unique_buyers}</strong><small>Số tài khoản duy nhất</small></div>
            <div class="lm-kpi"><span>Khách mua lại</span><strong>${behavior.repeat_buyers}</strong><small>Ít nhất 2 đơn trong giai đoạn</small></div>
            <div class="lm-kpi"><span>Số sản phẩm được đặt</span><strong>${behavior.total_units}</strong><small>Trung bình ${behavior.average_units_per_order} sản phẩm/đơn</small></div>
            <div class="lm-kpi"><span>Đơn dùng mã giảm giá</span><strong>${behavior.orders_using_coupons}</strong><small>Theo mã đã áp dụng</small></div>
            <div class="lm-kpi"><span>Thanh toán được xác nhận</span><strong>${money(revenue.confirmed_payment_amount_vnd)}</strong><small>${revenue.confirmed_payment_order_count} giao dịch được xác minh</small></div>
          </div>
          <div class="lm-data-grid"><section class="panel"><h3>Số đơn theo ngày</h3><p class="mini-note">Ngày khách tạo đơn · không phải doanh thu</p>${dayChart(daily,"orders",x=>x+" đơn")}</section>
          <section class="panel"><h3>Trạng thái đơn hàng</h3>${Object.entries(behavior.orders_by_status||{}).map(([key,value])=>statsBar(statusNames[key]||key,value,max)).join("")||"<p>Chưa có đơn</p>"}<h3>Phương thức thanh toán</h3>${Object.entries(behavior.orders_by_payment_method||{}).map(([key,value])=>statsBar(key.toUpperCase(),value,behavior.total_orders)).join("")||"<p>Chưa có</p>"}</section></div>
          <div class="panel"><h3>Sản phẩm được đặt nhiều nhất</h3><p class="mini-note">Đếm số lượng trên chi tiết đơn; bao gồm các đơn đã hủy, không đại diện cho doanh thu thuần.</p>
          <div class="table-wrap"><table class="data-table"><thead><tr><th>Mã SP</th><th>Tên sản phẩm</th><th>Số lượng được đặt</th></tr></thead><tbody>${(behavior.top_products||[]).map(x=>`<tr><td>#${x.product_id}</td><td>${esc(x.name)}</td><td><strong>${x.units}</strong></td></tr>`).join("")||'<tr><td colspan="3">Chưa có dữ liệu mua hàng</td></tr>'}</tbody></table></div></div>`;
        }catch(error){output.innerHTML=`<div class="form-alert error">${esc(error.message)}</div>`}
      }
      select.onchange=refresh;
      await refresh();
      return;
    }
    const first=new Date(now.getFullYear(),now.getMonth(),now.getDate()-29);
    // Summary is the primary source; recent orders, stock and 30-day revenue are independent.
    const [summaryResult,ordersResult,productsResult,revenueResult]=await Promise.allSettled([
      api.dashboard(),api.adminOrders(1,5),loadAllProducts(true),api.revenue(dateText(first),today)
    ]);
    const result=summaryResult.status==='fulfilled'?summaryResult.value:null;
    const orderPage=ordersResult.status==='fulfilled'?ordersResult.value:null;
    const products=productsResult.status==='fulfilled'?productsResult.value:null;
    const revenue=revenueResult.status==='fulfilled'?revenueResult.value:null;
    const failure=(label,response)=>`<span class="form-alert error" role="alert">Không tải được ${label}: ${esc(response.reason?.message || response.reason)}</span>`;
    const low=products?.filter(p=>p.stock>0&&p.stock<=5).sort((a,b)=>a.stock-b.stock).slice(0,7);
    const statuses=result?.orders_by_status||{};
    const max=Math.max(1,...Object.values(statuses));
    target.innerHTML=`<div class="lm-admin-head"><div><h2>Tổng quan hoạt động cửa hàng</h2><p class="mini-note">Dữ liệu trực tiếp từ Business API · báo cáo thanh toán đã xác nhận</p></div><span class="lm-live">PostgreSQL · LIVE</span></div>
      <div class="lm-kpis">
      <div class="lm-kpi"><span>Tổng đơn hàng</span>${result?`<strong>${result.total_orders}</strong><small>${statuses.pending||0} đơn chờ xác nhận</small>`:failure('tổng quan',summaryResult)}</div>
      <div class="lm-kpi"><span>Sản phẩm</span>${result?`<strong>${result.total_products}</strong>`:failure('tổng quan',summaryResult)}<small>${products?`${products.length} sản phẩm đã tải`:failure('danh mục tồn kho',productsResult)}</small></div>
      <div class="lm-kpi"><span>Đã hết hàng</span>${result?`<strong>${result.out_of_stock_products}</strong>`:failure('tổng quan',summaryResult)}<small>${low?`${low.length} sản phẩm tồn kho thấp đang hiển thị`:failure('danh mục tồn kho',productsResult)}</small></div>
      <div class="lm-kpi"><span>Tổng tiền được xác nhận</span>${result?`<strong>${money(result.confirmed_payment_amount_vnd)}</strong><small>Không phải lợi nhuận</small>`:failure('tổng quan',summaryResult)}</div>
      <div class="lm-kpi"><span>Thanh toán 30 ngày</span>${revenue?`<strong>${money(revenue.confirmed_payment_amount_vnd)}</strong><small>${revenue.confirmed_payment_order_count} giao dịch xác minh</small>`:failure('thanh toán 30 ngày',revenueResult)}</div>
      <div class="lm-kpi"><span>Cần đối soát</span>${result?`<strong>${result.reconciliation_order_count}</strong><small>Tổng giá trị đơn: ${money(result.reconciliation_order_value_vnd)}</small>`:failure('tổng quan',summaryResult)}</div></div>
      <div class="lm-data-grid"><section class="panel"><h3>Đơn hàng theo trạng thái</h3>${result?Object.entries(statuses).map(([key,value])=>statsBar(statusNames[key]||key,value,max)).join(""):failure('tổng quan',summaryResult)}<p><a class="inline-link" href="orders.html">Quản lý đơn hàng</a></p></section>
      <section class="panel"><h3>Thanh toán được xác nhận · 30 ngày</h3><p class="mini-note">Phân bổ theo ngày xác minh giao dịch</p>${revenue?dayChart((revenue.items||[]).map(x=>({...x,date:x.period_start})),"confirmed_payment_amount_vnd",money):failure('thanh toán 30 ngày',revenueResult)}</section></div>
      <div class="lm-data-grid"><section class="panel"><h3>Đơn hàng gần nhất</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Mã</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng tiền</th></tr></thead><tbody>
      ${orderPage?((orderPage.items||[]).map(row=>`<tr><td>${esc(row.code)}</td><td>${esc(statusNames[row.status]||row.status)}</td><td>${esc(paymentNames[row.payment_status]||row.payment_status)}</td><td>${money(row.total_vnd)}</td></tr>`).join("")||'<tr><td colspan="4">Chưa có đơn</td></tr>'):`<tr><td colspan="4">${failure('đơn hàng gần nhất',ordersResult)}</td></tr>`}</tbody></table></div></section>
      <section class="panel"><h3>Sản phẩm gần hết hàng</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>ID</th><th>Sản phẩm</th><th>Tồn kho</th></tr></thead><tbody>${low?(low.map(p=>`<tr><td>#${p.id}</td><td>${esc(p.name)}</td><td><strong>${p.stock}</strong></td></tr>`).join("")||'<tr><td colspan="3">Chưa có sản phẩm tồn kho thấp</td></tr>'):`<tr><td colspan="3">${failure('danh mục tồn kho',productsResult)}</td></tr>`}</tbody></table></div><a class="inline-link" href="inventory.html">Kiểm tra tồn kho</a></section></div>
      <div class="panel"><h3>Lưu ý đối soát</h3><p class="mini-note">Dữ liệu được xác nhận theo chứng từ thanh toán; số tiền không tương đương doanh thu thuần hoặc lợi nhuận.</p>${result?((result.reconciliation_reasons||[]).map(x=>`<p>${esc(x.reason)}: ${x.order_count} đơn</p>`).join("")||'<p>Chưa phát hiện trường hợp cần đối soát.</p>'):failure('tổng quan',summaryResult)}</div>`;
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
      if(submit.disabled)return;
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


  async function renderContacts(target,page=1) {
    const result=await api.request("/admin/contact-messages?"+new URLSearchParams({page,page_size:20}));
    const labels={new:"Mới",in_progress:"Đang xử lý",closed:"Đã hoàn tất"};
    target.innerHTML=`<div class="lm-admin-head"><div><h2>Yêu cầu liên hệ</h2><p class="mini-note">Hộp thư hỗ trợ của khách hàng và khách truy cập · Dữ liệu lưu trên PostgreSQL.</p></div><span class="lm-live">${result.total} yêu cầu</span></div>
      <div class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Mã / Ngày</th><th>Người gửi</th><th>Chủ đề</th><th>Nội dung</th><th>Trạng thái</th></tr></thead><tbody>
      ${(result.items||[]).map(item=>`<tr><td><strong>#${item.id}</strong><br><small>${new Date(item.created_at).toLocaleString("vi-VN")}</small></td><td>${esc(item.full_name)}<br><small>${esc(item.email)}</small></td><td>${esc(item.topic)}</td><td style="min-width:220px;max-width:350px;white-space:pre-wrap;overflow-wrap:anywhere">${esc(item.message)}</td>
      <td><select data-contact-status="${item.id}" aria-label="Trạng thái liên hệ #${item.id}" style="padding:10px;border:1px solid #d6c9b9">${Object.entries(labels).map(([key,value])=>`<option value="${key}" ${item.status===key?"selected":""}>${value}</option>`).join('')}</select></td></tr>`).join("")||'<tr><td colspan="5">Chưa có yêu cầu liên hệ</td></tr>'}</tbody></table></div>
      <div class="ap-pager"><span>Trang ${result.page} · ${result.total} yêu cầu</span><div class="ap-page-actions"><button id="contact-prev" ${page<=1?"disabled":""}>← Trước</button><button id="contact-next" ${page*result.page_size>=result.total?"disabled":""}>Tiếp →</button></div></div></div>`;
    target.querySelector("#contact-prev").onclick=()=>renderContacts(target,page-1).catch(error=>showError(target,error));
    target.querySelector("#contact-next").onclick=()=>renderContacts(target,page+1).catch(error=>showError(target,error));
    target.querySelectorAll("[data-contact-status]").forEach(select=>select.onchange=async()=>{
      select.disabled=true;
      try{
        await api.request("/admin/contact-messages/"+select.dataset.contactStatus,{
          method:"PATCH",body:JSON.stringify({status:select.value})
        });
        await renderContacts(target,page);
      }catch(error){showError(target,error)}
      finally{select.disabled=false}
    });
  }

  async function renderOrders(...args) {
    const { createOrdersController } = await import("./management-orders.mjs");
    return createOrdersController({ api, esc, money, showError, statusNames, paymentNames })(...args);
  }
  async function renderProducts(...args) {
    const { createProductsController } = await import("./management-products.mjs");
    return createProductsController({ api, esc, money, showError, loadAllProducts })(...args);
  }

  return async ({ mount, section, role }) => {
    const target = consoleShell(mount, section, role, root);
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
}
