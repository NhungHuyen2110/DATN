"use strict";
/* Staff Orders: PostgreSQL is the only source. No demo data or sessionStorage. */
(() => {
  const statusNames = {pending:'Chờ xác nhận',confirmed:'Đã xác nhận',packing:'Đang đóng gói',shipping:'Đang giao',delivered:'Đã giao',cancelled:'Đã hủy'};
  const transitions = {pending:['confirmed','cancelled'],confirmed:['packing','cancelled'],packing:['shipping'],shipping:['delivered'],delivered:[],cancelled:[]};
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const money = value => Number(value || 0).toLocaleString('vi-VN') + ' ₫';
  const date = value => value ? new Date(value).toLocaleString('vi-VN') : '—';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
  const badge = value => `<span class="order-status order-status--${escapeHtml(value)}">${escapeHtml(statusNames[value] || value)}</span>`;
  const api = () => window.LUMIERE_API;

  window.LUMIERE_STAFF_ORDERS = ({mount}) => {
    let orders = [], page = 1, pageSize = 20, total = 0, query = '', filter = '', busy = false, selected = null;
    const showError = error => { const el = mount.querySelector('#so-error'); if (el) {el.hidden = false; el.textContent = error.message || String(error);} };
    async function load() {
      mount.innerHTML = '<div class="panel">Đang tải đơn hàng từ PostgreSQL…</div>';
      try {
        if (!api()) throw Error('Không tìm thấy api.js.');
        // Backend rejects unauthenticated/unauthorized users with 401/403.
        const response = await api().getStaffOrders(page,pageSize);
        if (!Array.isArray(response.items)) throw Error('Dữ liệu danh sách đơn không hợp lệ.');
        orders = response.items; total = Number(response.total || 0); render();
      } catch (error) {
        mount.innerHTML = `<div class="panel"><h2>Không tải được đơn hàng Staff</h2><p>${escapeHtml(error.message)}</p><p>Đăng nhập bằng tài khoản Staff/Admin. Tài khoản Customer không có quyền xem đơn của người khác.</p><button type="button" class="button button-outline" id="so-retry">Thử lại</button></div>`;
        mount.querySelector('#so-retry').onclick = load;
      }
    }
    function render() {
      const shown = orders.filter(o => (!filter || o.status === filter) && norm([o.code,o.id,o.status,o.payment_status].join(' ')).includes(norm(query)));
      const pages = Math.max(1,Math.ceil(total/pageSize));
      mount.innerHTML = `<div class="so-title"><div><h2>Xử lý đơn hàng</h2><p class="mini-note">Dữ liệu thật từ Business API · PostgreSQL. Bộ lọc áp dụng cho trang hiện tại.</p></div><button type="button" class="button button-outline" id="so-refresh">Làm mới</button></div>
      <p id="so-error" class="form-alert" role="alert" hidden></p>
      <div class="so-stats"><div class="stat"><span>Tổng đơn (toàn hệ thống)</span><strong>${total}</strong></div><div class="stat"><span>Chờ xác nhận (trang này)</span><strong>${orders.filter(o=>o.status==='pending').length}</strong></div><div class="stat"><span>Đang xử lý / giao (trang này)</span><strong>${orders.filter(o=>['confirmed','packing','shipping'].includes(o.status)).length}</strong></div><div class="stat"><span>Đã giao (trang này)</span><strong>${orders.filter(o=>o.status==='delivered').length}</strong></div></div>
      <section class="panel so-panel"><div class="so-filters"><label class="field"><span>Tìm mã đơn / ID (trang này)</span><input id="so-query" type="search" placeholder="Mã đơn LUMIÈRE…" value="${escapeHtml(query)}"></label><label class="field"><span>Trạng thái</span><select id="so-status"><option value="">Tất cả</option>${Object.entries(statusNames).map(([k,v])=>`<option value="${k}" ${filter===k?'selected':''}>${v}</option>`).join('')}</select></label><label class="field"><span>Số đơn / trang</span><select id="so-size">${[5,10,20,50,100].map(n=>`<option value="${n}" ${pageSize===n?'selected':''}>${n} / trang</option>`).join('')}</select></label></div>
      <div class="table-wrap"><table class="data-table so-table"><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng tiền</th><th>Thao tác</th></tr></thead><tbody>${shown.map(o=>`<tr><td><strong>${escapeHtml(o.code)}</strong></td><td>${escapeHtml(date(o.created_at))}</td><td>${badge(o.status)}</td><td>${escapeHtml(o.payment_status)}</td><td>${money(o.total_vnd)}</td><td><button type="button" class="button-sm" data-so-id="${Number(o.id)}">Chi tiết</button></td></tr>`).join('')||'<tr><td colspan="6">Không có đơn phù hợp trong trang này.</td></tr>'}</tbody></table></div>
      <div class="so-pages"><span>Trang ${page}/${pages} · Tổng ${total} đơn</span><div><button id="so-prev" ${page<=1?'disabled':''}>← Trước</button><button id="so-next" ${page>=pages?'disabled':''}>Sau →</button></div></div></section><dialog id="so-dialog" class="so-dialog" aria-labelledby="so-detail-title"><div id="so-detail-body"></div><div class="so-dialog-bottom"><button id="so-close" type="button" class="button button-outline">ĐÓNG</button></div></dialog>`;
      mount.querySelector('#so-refresh').onclick=load;
      mount.querySelector('#so-query').oninput=e=>{const cursor=e.target.selectionStart;query=e.target.value;render();const field=mount.querySelector('#so-query');field.focus();field.setSelectionRange(cursor,cursor)};
      mount.querySelector('#so-status').onchange=e=>{filter=e.target.value;render()};
      mount.querySelector('#so-size').onchange=e=>{pageSize=Number(e.target.value);page=1;load()};
      mount.querySelector('#so-prev').onclick=()=>{if(page>1){page--;load()}};
      mount.querySelector('#so-next').onclick=()=>{if(page<pages){page++;load()}};
      mount.querySelectorAll('[data-so-id]').forEach(button=>button.onclick=()=>open(Number(button.dataset.soId)));
    }
    async function open(id) {
      const dialog=mount.querySelector('#so-dialog'), body=mount.querySelector('#so-detail-body');
      dialog.showModal();body.textContent='Đang tải chi tiết đơn hàng…';
      mount.querySelector('#so-close').onclick=()=>dialog.close();
      try { selected=await api().getStaffOrder(id); showDetail(dialog,body); }
      catch(error){body.textContent='Không tải được chi tiết: '+error.message;}
    }
    function showDetail(dialog,body) {
      const o=selected, allowed=transitions[o.status]||[];
      const codEligible = o.status==='delivered' && o.payment_status==='unpaid';
      body.innerHTML=`<div class="so-detail-heading"><div><p class="eyebrow">ĐƠN HÀNG POSTGRESQL</p><h2 id="so-detail-title">${escapeHtml(o.code)}</h2></div>${badge(o.status)}</div>
      <div class="so-columns"><div><h3>Thông tin người nhận</h3><p><strong>${escapeHtml(o.recipient_name)}</strong></p><p>${escapeHtml(o.phone)}</p><p>${escapeHtml(o.address)}</p></div><div><h3>Thông tin đơn</h3><p>Ngày đặt: ${escapeHtml(date(o.created_at))}</p><p>Thanh toán: <strong>${escapeHtml(o.payment_status)}</strong></p><p>Mã định danh: ${Number(o.id)}</p></div></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>${(o.items||[]).map(i=>`<tr><td>${escapeHtml(i.product_name)}</td><td>${Number(i.quantity)}</td><td>${money(i.unit_price_vnd)}</td><td>${money(i.line_total_vnd)}</td></tr>`).join('')}</tbody></table></div>
      <p class="so-total"><span>Vận chuyển: ${money(o.shipping_vnd)} · Giảm giá: ${money(o.discount_vnd)}</span><strong>Tổng: ${money(o.total_vnd)}</strong></p>
      <div class="so-transition"><label for="so-next-status">Chuyển trạng thái hợp lệ</label><div><select id="so-next-status" ${allowed.length?'':'disabled'}>${allowed.length?allowed.map(s=>`<option value="${s}">${statusNames[s]}</option>`).join(''):'<option>Không có trạng thái tiếp theo</option>'}</select><button type="button" class="button button-dark" id="so-apply" ${allowed.length?'':'disabled'}>CẬP NHẬT TRẠNG THÁI</button></div><small>Chuyển sang “Đã giao” không tự xác nhận đã thu tiền.</small></div>
      ${codEligible?'<p><button class="button button-dark" type="button" id="so-confirm-cod">XÁC NHẬN ĐÃ THU TIỀN COD</button></p>':''}
      <p id="so-modal-error" class="form-alert" role="alert" hidden></p>`;
      const modalError=message=>{const el=body.querySelector('#so-modal-error');el.hidden=false;el.textContent=message};
      body.querySelector('#so-apply').onclick=async()=>{
        const desired=body.querySelector('#so-next-status').value;
        if(!allowed.includes(desired)||busy)return;
        if(!confirm(`Đổi trạng thái đơn ${o.code} sang ${statusNames[desired]}? Thao tác ghi PostgreSQL.`))return;
        busy=true;
        try {await api().updateStaffOrderStatus(o.id,desired);dialog.close();await load();}
        catch(error){modalError(error.message);}finally{busy=false;}
      };
      const codButton=body.querySelector('#so-confirm-cod');
      if(codButton) codButton.onclick=async()=>{
        if(busy)return;
        const reference=prompt(`Nhập mã tham chiếu THU TIỀN COD cho đơn ${o.code} (3–100 ký tự).\nChỉ tiếp tục nếu đã thực tế thu tiền hoặc đang mô phỏng trên database kiểm thử:`);
        if(reference===null)return;
        const normalized=reference.trim();
        if(normalized.length<3||normalized.length>100){modalError('Mã tham chiếu thu COD phải có từ 3 đến 100 ký tự.');return;}
        if(!confirm(`Xác nhận đã thu ${money(o.total_vnd)} COD cho đơn ${o.code}?\nMã tham chiếu: ${normalized}\nThao tác ghi PostgreSQL.`))return;
        busy=true;codButton.disabled=true;
        try {await api().confirmStaffCOD(o.id,normalized);dialog.close();await load();}
        catch(error){modalError(error.message+' — Nếu không rõ kết quả, tải lại chi tiết đơn trước khi thử lại.');}
        finally{busy=false;codButton.disabled=false;}
      };
    }
    load();
  };
})();
