"use strict";
(() => {
  const KEY = "lumiere_admin_customers_demo_v1";
  const seed = [
    { id: "KH-DEMO-001", name: "Nguyễn Minh Anh", email: "minhanh@example.com", phone: "0900000001", joined: "2026-09-11", active: true, city: "TP. Hồ Chí Minh", orders: 3, spending: 18450000 },
    { id: "KH-DEMO-002", name: "Trần Gia Hân", email: "giahan@example.com", phone: "0900000002", joined: "2026-09-15", active: true, city: "Hà Nội", orders: 2, spending: 9700000 },
    { id: "KH-DEMO-003", name: "Lê Quốc Bảo", email: "quocbao@example.com", phone: "0900000003", joined: "2026-09-20", active: true, city: "Đà Nẵng", orders: 1, spending: 12500000 },
    { id: "KH-DEMO-004", name: "Phạm Thanh Trúc", email: "thanhtruc@example.com", phone: "0900000004", joined: "2026-09-22", active: false, city: "Cần Thơ", orders: 0, spending: 0 },
    { id: "KH-DEMO-005", name: "Đỗ Hoàng Nam", email: "hoangnam@example.com", phone: "0900000005", joined: "2026-09-26", active: true, city: "TP. Hồ Chí Minh", orders: 4, spending: 41200000 },
    { id: "KH-DEMO-006", name: "Võ Ngọc Hà", email: "ngocha@example.com", phone: "0900000006", joined: "2026-10-01", active: true, city: "Hải Phòng", orders: 1, spending: 4850000 },
    { id: "KH-DEMO-007", name: "Bùi Thảo Vy", email: "thaovy@example.com", phone: "0900000007", joined: "2026-10-05", active: false, city: "Đồng Nai", orders: 1, spending: 2300000 },
    { id: "KH-DEMO-008", name: "Ngô Khánh Linh", email: "khanhlinh@example.com", phone: "0900000008", joined: "2026-10-10", active: true, city: "TP. Hồ Chí Minh", orders: 0, spending: 0 }
  ];
  const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const money = n => Number(n).toLocaleString("vi-VN") + " ₫";
  const validCustomer = x => x && typeof x.id === "string" && typeof x.name === "string" && typeof x.active === "boolean";
  function load() {
    try {
      const raw = sessionStorage.getItem(KEY);
      const data = raw ? JSON.parse(raw) : null;
      return Array.isArray(data) && data.every(validCustomer) ? data : structuredClone(seed);
    } catch { return structuredClone(seed); }
  }
  const persist = data => sessionStorage.setItem(KEY, JSON.stringify(data));
  window.LUMIERE_ADMIN_CUSTOMERS = function init({ mount }) {
    if (!mount) return;
    let customers = load(), page = 1;
    mount.innerHTML = `
      <div class="demo-note"><strong>CHẾ ĐỘ DEMO FRONTEND.</strong> Dữ liệu khách hàng, đơn hàng và tổng chi tiêu dưới đây đều giả lập. Khóa/mở khóa chỉ lưu trong phiên tab, không cập nhật PostgreSQL. Backend phải kiểm tra quyền admin.</div>
      <div class="cust-titlebar"><div><h2>Danh sách khách hàng</h2><p class="mini-note">Quản lý tài khoản và tình trạng hoạt động</p></div><button class="button button-outline" id="cust-reset" type="button">Khôi phục DEMO</button></div>
      <div class="cust-stats" aria-label="Thống kê khách hàng demo">
        <div class="cust-stat"><span>Tổng khách hàng</span><strong id="cust-total"></strong></div>
        <div class="cust-stat"><span>Đang hoạt động</span><strong id="cust-active"></strong></div>
        <div class="cust-stat"><span>Đã khóa</span><strong id="cust-locked"></strong></div>
      </div>
      <section class="panel cust-panel" aria-label="Quản lý khách hàng demo">
        <div class="cust-filters">
          <div class="field"><label for="cust-search">Tìm mã, họ tên, email, số điện thoại</label><input id="cust-search" type="search" placeholder="VD: KH-DEMO-001, Minh Anh..."></div>
          <div class="field"><label for="cust-status">Trạng thái</label><select id="cust-status"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="locked">Đã khóa</option></select></div>
          <div class="field"><label for="cust-size">Hiển thị</label><select id="cust-size"><option value="5">5 / trang</option><option value="10">10 / trang</option><option value="20">20 / trang</option></select></div>
        </div>
        <div class="table-wrap"><table class="data-table cust-table"><thead><tr><th>Mã KH</th><th>Khách hàng</th><th>Điện thoại</th><th>Ngày đăng ký</th><th>Đơn (demo)</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="cust-tbody"></tbody></table></div>
        <div class="cust-pagination"><span id="cust-count" aria-live="polite"></span><div><button type="button" id="cust-prev">← Trước</button><span id="cust-page" aria-live="polite"></span><button type="button" id="cust-next">Sau →</button></div></div>
      </section>
      <dialog id="cust-dialog" class="cust-dialog" aria-labelledby="cust-dialog-title"><div class="cust-dialog-head"><h2 id="cust-dialog-title">Chi tiết khách hàng</h2><button type="button" id="cust-close" aria-label="Đóng cửa sổ">×</button></div><div id="cust-detail"></div><div class="cust-dialog-bottom"><button type="button" class="button button-outline" id="cust-close-bottom">Đóng</button></div></dialog>
    `;
    const $ = s => mount.querySelector(s);
    const search = $('#cust-search'), status = $('#cust-status'), size = $('#cust-size');
    const normalized = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();
    const matching = () => {
      const q = normalized(search.value.trim());
      return customers.filter(c => (!q || normalized([c.id,c.name,c.email,c.phone].join(' ')).includes(q)) && (status.value === 'all' || (status.value === 'active' ? c.active : !c.active)));
    };
    function draw() {
      $('#cust-total').textContent = customers.length;
      $('#cust-active').textContent = customers.filter(c => c.active).length;
      $('#cust-locked').textContent = customers.filter(c => !c.active).length;
      const filtered = matching(), per = Number(size.value), pages = Math.max(1, Math.ceil(filtered.length / per));
      page = Math.min(Math.max(1,page),pages);
      const slice = filtered.slice((page - 1) * per, page * per);
      $('#cust-tbody').innerHTML = slice.length ? slice.map(c => `<tr>
        <td><strong>${escapeHTML(c.id)}</strong></td><td><strong>${escapeHTML(c.name)}</strong><small class="cust-email">${escapeHTML(c.email)}</small></td>
        <td>${escapeHTML(c.phone)}</td><td>${escapeHTML(c.joined)}</td><td>${Number(c.orders) || 0}</td>
        <td><span class="cust-badge ${c.active ? 'is-active' : 'is-locked'}">${c.active ? 'Hoạt động':'Đã khóa'}</span></td>
        <td><div class="row-actions"><button type="button" class="button-sm" data-detail="${escapeHTML(c.id)}">Chi tiết</button><button type="button" class="button-sm" data-toggle="${escapeHTML(c.id)}">${c.active?'Khóa':'Mở khóa'}</button></div></td>
      </tr>`).join('') : '<tr><td class="cust-empty" colspan="7">Không tìm thấy khách hàng phù hợp.</td></tr>';
      $('#cust-count').textContent = `Hiển thị ${slice.length} / ${filtered.length} khách hàng (DEMO)`;
      $('#cust-page').textContent = `Trang ${page} / ${pages}`;
      $('#cust-prev').disabled = page <= 1;
      $('#cust-next').disabled = page >= pages;
    }
    function detail(id) {
      const c = customers.find(x => x.id === id); if (!c) return;
      $('#cust-dialog-title').textContent = `Khách hàng ${c.id}`;
      const dl = [
        ['Họ tên',c.name], ['Email',c.email], ['Điện thoại',c.phone],
        ['Ngày đăng ký',c.joined], ['Khu vực (demo)',c.city],
        ['Trạng thái',c.active?'Hoạt động':'Đã khóa'],
        ['Số đơn (demo)',String(c.orders)], ['Tổng chi tiêu (demo)',money(c.spending)]
      ];
      $('#cust-detail').innerHTML = `<p class="demo-note">Đây là hồ sơ minh họa, không phải dữ liệu khách hàng PostgreSQL. Không hiển thị mật khẩu hoặc mã băm.</p><dl class="cust-info">${dl.map(([label,value]) => `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd></div>`).join('')}</dl><p class="mini-note">Lịch sử đơn hàng thực, địa chỉ nhận hàng và tổng chi tiêu chính xác sẽ được lấy từ API có phân quyền.</p>`;
      $('#cust-dialog').showModal();
    }
    mount.addEventListener('click', e => {
      const btn = e.target.closest('button'); if (!btn || !mount.contains(btn)) return;
      if (btn.dataset.detail) detail(btn.dataset.detail);
      if (btn.dataset.toggle) {
        const c = customers.find(x => x.id === btn.dataset.toggle); if (!c) return;
        if (!confirm(`Xác nhận ${c.active?'khóa':'mở khóa'} tài khoản DEMO ${c.name}?`)) return;
        c.active = !c.active; persist(customers); draw();
      }
    });
    [search,status,size].forEach(el => el.addEventListener('input', () => { page=1; draw(); }));
    $('#cust-prev').onclick = () => {page--;draw();};
    $('#cust-next').onclick = () => {page++;draw();};
    $('#cust-reset').onclick = () => { if (!confirm('Khôi phục tất cả tài khoản DEMO về trạng thái ban đầu?')) return; customers=structuredClone(seed);persist(customers);page=1;search.value='';status.value='all';size.value='5';draw(); };
    $('#cust-close').onclick = $('#cust-close-bottom').onclick = () => $('#cust-dialog').close();
    draw();
  };
})();
