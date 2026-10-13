"use strict";
/* LUMIÈRE Admin Orders – frontend-only demo. No order/payment API calls. */
(() => {
  const KEY = 'lumiere_admin_orders_demo_v1';
  const statuses = {
    pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', preparing: 'Đang chuẩn bị',
    shipping: 'Đang giao', completed: 'Hoàn thành', cancelled: 'Đã hủy'
  };
  const allowed = {
    pending: ['confirmed','cancelled'], confirmed: ['preparing','cancelled'],
    preparing: ['shipping'], shipping: ['completed'], completed: [], cancelled: []
  };
  const paymentLabels = {cod:'COD - Chưa thu', paid:'Đã thanh toán (demo)', refunded:'Đã hoàn tiền (demo)'};
  const seed = [
    {id:'ORD-DEMO-1001',customer:'Nguyễn Minh Anh',phone:'0900000001',address:'Quận 1, TP.HCM (giả lập)',date:'2026-10-09',status:'pending',payment:'cod',items:[{id:1,name:'Nhẫn Diamond Queen',qty:1,unit_price:14686287}],shipping_fee:0,note:'Giao giờ hành chính'},
    {id:'ORD-DEMO-1002',customer:'Trần Hoàng Nam',phone:'0900000002',address:'Bình Thạnh, TP.HCM (giả lập)',date:'2026-10-10',status:'confirmed',payment:'cod',items:[{id:2,name:'Dây chuyền Golden Grace',qty:1,unit_price:8950000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1003',customer:'Lê Thảo Vy',phone:'0900000003',address:'Thủ Đức, TP.HCM (giả lập)',date:'2026-10-11',status:'preparing',payment:'paid',items:[{id:3,name:'Bông tai Celina',qty:2,unit_price:12500000}],shipping_fee:0,note:'Đóng gói quà'},
    {id:'ORD-DEMO-1004',customer:'Phạm Gia Bảo',phone:'0900000004',address:'Quận 7, TP.HCM (giả lập)',date:'2026-10-11',status:'shipping',payment:'cod',items:[{id:4,name:'Vòng tay Ocean',qty:1,unit_price:4850000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1005',customer:'Đỗ Ngọc Hà',phone:'0900000005',address:'Đà Nẵng (giả lập)',date:'2026-10-07',status:'completed',payment:'paid',items:[{id:1,name:'Nhẫn Diamond Queen',qty:1,unit_price:14686287},{id:4,name:'Vòng tay Ocean',qty:1,unit_price:4850000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1006',customer:'Vũ Thanh Tùng',phone:'0900000006',address:'Hà Nội (giả lập)',date:'2026-10-08',status:'cancelled',payment:'cod',items:[{id:2,name:'Dây chuyền Golden Grace',qty:1,unit_price:8950000}],shipping_fee:0,note:'Khách yêu cầu hủy'},
    {id:'ORD-DEMO-1007',customer:'Bùi Mai Linh',phone:'0900000007',address:'Cần Thơ (giả lập)',date:'2026-10-12',status:'pending',payment:'cod',items:[{id:3,name:'Bông tai Celina',qty:1,unit_price:12500000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1008',customer:'Ngô Quốc Huy',phone:'0900000008',address:'Hải Phòng (giả lập)',date:'2026-10-12',status:'confirmed',payment:'cod',items:[{id:4,name:'Vòng tay Ocean',qty:2,unit_price:4850000}],shipping_fee:0,note:''}
  ];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = v => Number(v || 0).toLocaleString('vi-VN') + ' ₫';
  const total = o => o.items.reduce((n,i)=>n + i.qty*i.unit_price,0) + o.shipping_fee;
  const read = () => {try {const raw=sessionStorage.getItem(KEY);const v=raw?JSON.parse(raw):null;return Array.isArray(v)?v:structuredClone(seed);}catch{return structuredClone(seed)}};
  const store = data => sessionStorage.setItem(KEY, JSON.stringify(data));
  window.LUMIERE_ADMIN_ORDERS = ({ mount }) => {
    let orders=read(), q='',status='',payment='',from='',to='',page=1,size=5, selected=null;
    const orderSort = (a,b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id);
    const matches = o => {
      const term=(o.id+' '+o.customer+' '+o.phone).toLocaleLowerCase('vi');
      return term.includes(q.toLocaleLowerCase('vi')) && (!status || o.status===status) &&
        (!payment || o.payment===payment) && (!from || o.date>=from) && (!to || o.date<=to);
    };
    const options = (values, current) => values.map(([v,label])=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(label)}</option>`).join('');
    const notice = 'CHẾ ĐỘ DEMO FRONTEND. Các đơn dưới đây hoàn toàn giả lập; mọi cập nhật chỉ lưu trong sessionStorage của tab trình duyệt. Không ghi PostgreSQL, không thanh toán hay vận chuyển thật.';
    const badge = st=>`<span class="order-status order-status--${esc(st)}">${esc(statuses[st]||st)}</span>`;
    const stats = () => {
      const open=orders.filter(o=>!['completed','cancelled'].includes(o.status)).length;
      return `<div class="order-stats"><div class="stat"><span>Tổng đơn DEMO</span><strong>${orders.length}</strong></div><div class="stat"><span>Chờ xác nhận</span><strong>${orders.filter(o=>o.status==='pending').length}</strong></div><div class="stat"><span>Đang xử lý / giao</span><strong>${open}</strong></div><div class="stat"><span>Hoàn thành DEMO</span><strong>${orders.filter(o=>o.status==='completed').length}</strong></div></div>`;
    };
    function render(){
      const filtered=orders.filter(matches).sort(orderSort);
      const pages=Math.max(1,Math.ceil(filtered.length/size));page=Math.min(page,pages);
      const rows=filtered.slice((page-1)*size,page*size);
      mount.innerHTML=`<div class="demo-note"><strong>${notice}</strong></div>
        <div class="order-titlebar"><div><h2>Danh sách đơn hàng</h2><p class="mini-note">Mô phỏng quy trình tiếp nhận, xử lý và giao hàng</p></div><button type="button" id="orders-reset" class="button button-outline">Khôi phục dữ liệu demo</button></div>
        ${stats()}
        <div class="panel order-panel"><div class="order-filters">
          <label class="field"><span>Tìm mã đơn / khách hàng / SĐT</span><input id="orders-search" type="search" placeholder="ORD-DEMO-1001, tên khách..." value="${esc(q)}"></label>
          <label class="field"><span>Trạng thái</span><select id="orders-status">${options([['','Tất cả'],...Object.entries(statuses)],status)}</select></label>
          <label class="field"><span>Thanh toán</span><select id="orders-payment">${options([['','Tất cả'],...Object.entries(paymentLabels)],payment)}</select></label>
          <label class="field"><span>Từ ngày</span><input id="orders-from" type="date" value="${esc(from)}"></label>
          <label class="field"><span>Đến ngày</span><input id="orders-to" type="date" value="${esc(to)}"></label>
          <label class="field"><span>Hiển thị</span><select id="orders-size">${options([['5','5 / trang'],['10','10 / trang'],['20','20 / trang']],String(size))}</select></label>
        </div><div class="order-table-wrap table-wrap"><table class="data-table"><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th>Khách hàng</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng (demo)</th><th>Thao tác</th></tr></thead><tbody>
        ${rows.length?rows.map(o=>`<tr><td><strong>${esc(o.id)}</strong></td><td>${esc(o.date)}</td><td>${esc(o.customer)}<small class="order-subtext">${esc(o.phone)}</small></td><td>${badge(o.status)}</td><td>${esc(paymentLabels[o.payment])}</td><td>${money(total(o))}</td><td><button class="button-sm" type="button" data-order-view="${esc(o.id)}">Chi tiết</button></td></tr>`).join(''):'<tr><td colspan="7" class="order-empty">Không tìm thấy đơn hàng phù hợp.</td></tr>'}</tbody></table></div>
        <div class="order-pagination"><span>${filtered.length} đơn phù hợp · Trang ${page}/${pages}</span><div><button type="button" id="orders-prev" ${page===1?'disabled':''}>← Trước</button><button type="button" id="orders-next" ${page===pages?'disabled':''}>Sau →</button></div></div></div>
        <dialog class="order-dialog" id="orders-dialog" aria-labelledby="orders-dialog-title"><div id="orders-dialog-body"></div><div class="order-dialog-actions"><button class="button button-outline" id="orders-close" type="button">ĐÓNG</button></div></dialog>`;
      const set=(id,fn,event='change')=>mount.querySelector(id).addEventListener(event,fn);
      set('#orders-search',e=>{q=e.target.value;page=1;const caret=e.target.selectionStart;render();const input=mount.querySelector('#orders-search');input.focus();input.setSelectionRange(caret,caret)},'input');
      set('#orders-status',e=>{status=e.target.value;page=1;render()});
      set('#orders-payment',e=>{payment=e.target.value;page=1;render()});
      set('#orders-from',e=>{from=e.target.value;page=1;render()});
      set('#orders-to',e=>{to=e.target.value;page=1;render()});
      set('#orders-size',e=>{size=Number(e.target.value);page=1;render()});
      set('#orders-prev',()=>{page--;render()},'click');set('#orders-next',()=>{page++;render()},'click');
      set('#orders-reset',()=>{if(confirm('Khôi phục toàn bộ đơn hàng DEMO ban đầu?')){orders=structuredClone(seed);sessionStorage.removeItem(KEY);page=1;render()}},'click');
      mount.querySelectorAll('[data-order-view]').forEach(btn=>btn.addEventListener('click',()=>openDetail(btn.dataset.orderView)));
    }
    function openDetail(id){
      selected=orders.find(o=>o.id===id);if(!selected)return;
      const o=selected;
      const dlg=mount.querySelector('#orders-dialog');
      const next=allowed[o.status]||[];
      mount.querySelector('#orders-dialog-body').innerHTML=`<div class="order-detail-header"><div><p class="eyebrow">ORDER DETAIL — DEMO</p><h2 id="orders-dialog-title">${esc(o.id)}</h2></div>${badge(o.status)}</div>
        <div class="order-detail-grid"><div><h3>Người nhận</h3><p><strong>${esc(o.customer)}</strong></p><p>${esc(o.phone)}</p><p>${esc(o.address)}</p></div><div><h3>Thông tin đơn</h3><p>Ngày đặt: ${esc(o.date)}</p><p>Thanh toán: ${esc(paymentLabels[o.payment])}</p><p>Ghi chú: ${esc(o.note||'Không có')}</p></div></div>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>${o.items.map(i=>`<tr><td>${esc(i.name)} <small>#${Number(i.id)}</small></td><td>${Number(i.qty)}</td><td>${money(i.unit_price)}</td><td>${money(i.qty*i.unit_price)}</td></tr>`).join('')}</tbody></table></div>
        <div class="order-totals"><span>Phí vận chuyển: ${money(o.shipping_fee)}</span><strong>Tổng cộng (demo): ${money(total(o))}</strong></div>
        <div class="order-transition"><label for="orders-next-status"><strong>Cập nhật trạng thái demo</strong></label><div class="order-transition-controls"><select id="orders-next-status" ${next.length?'':'disabled'}>${next.length?next.map(s=>`<option value="${s}">${esc(statuses[s])}</option>`).join(''):'<option>Không có bước tiếp theo</option>'}</select><button type="button" id="orders-apply" class="button button-dark" ${next.length?'':'disabled'}>XÁC NHẬN CHUYỂN</button></div><p class="mini-note">Không tự thay đổi thanh toán khi cập nhật trạng thái. Không thể chuyển ngược hoặc hủy sau khi đã giao.</p></div>`;
      dlg.showModal();
      const closeBtn=mount.querySelector('#orders-close');
      closeBtn.onclick=()=>dlg.close();
      dlg.querySelector('#orders-apply').onclick=()=>{
        const desired=dlg.querySelector('#orders-next-status').value;
        if(!(allowed[o.status]||[]).includes(desired))return;
        if(!confirm(`Đổi ${o.id} từ “${statuses[o.status]}” sang “${statuses[desired]}” (chỉ DEMO)?`))return;
        o.status=desired;store(orders);dlg.close();render();
      };
    }
    render();
  };
})();
