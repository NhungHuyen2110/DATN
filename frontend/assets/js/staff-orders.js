"use strict";
/* LUMIÈRE staff order processing — DEMO, no real API. Shared tab data with Admin Orders. */
(() => {
  const KEY='lumiere_admin_orders_demo_v1';
  const statuses={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',preparing:'Đang chuẩn bị',shipping:'Đang giao',completed:'Hoàn thành',cancelled:'Đã hủy'};
  const transitions={pending:['confirmed','cancelled'],confirmed:['preparing','cancelled'],preparing:['shipping'],shipping:['completed'],completed:[],cancelled:[]};
  const payments={cod:'COD – Chưa thu',paid:'Đã thanh toán (DEMO)',refunded:'Đã hoàn tiền (DEMO)'};
  const seed=[
    {id:'ORD-DEMO-1001',customer:'Nguyễn Minh Anh',phone:'0900000001',address:'Quận 1, TP.HCM (giả lập)',date:'2026-10-09',status:'pending',payment:'cod',items:[{id:1,name:'Nhẫn Diamond Queen',qty:1,unit_price:14686287}],shipping_fee:0,note:'Giao giờ hành chính'},
    {id:'ORD-DEMO-1002',customer:'Trần Hoàng Nam',phone:'0900000002',address:'Bình Thạnh, TP.HCM (giả lập)',date:'2026-10-10',status:'confirmed',payment:'cod',items:[{id:2,name:'Dây chuyền Golden Grace',qty:1,unit_price:8950000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1003',customer:'Lê Thảo Vy',phone:'0900000003',address:'Thủ Đức, TP.HCM (giả lập)',date:'2026-10-11',status:'preparing',payment:'paid',items:[{id:3,name:'Bông tai Celina',qty:2,unit_price:12500000}],shipping_fee:0,note:'Đóng gói quà'},
    {id:'ORD-DEMO-1004',customer:'Phạm Gia Bảo',phone:'0900000004',address:'Quận 7, TP.HCM (giả lập)',date:'2026-10-11',status:'shipping',payment:'cod',items:[{id:4,name:'Vòng tay Ocean',qty:1,unit_price:4850000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1005',customer:'Đỗ Ngọc Hà',phone:'0900000005',address:'Đà Nẵng (giả lập)',date:'2026-10-07',status:'completed',payment:'paid',items:[{id:1,name:'Nhẫn Diamond Queen',qty:1,unit_price:14686287},{id:4,name:'Vòng tay Ocean',qty:1,unit_price:4850000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1006',customer:'Vũ Thanh Tùng',phone:'0900000006',address:'Hà Nội (giả lập)',date:'2026-10-08',status:'cancelled',payment:'cod',items:[{id:2,name:'Dây chuyền Golden Grace',qty:1,unit_price:8950000}],shipping_fee:0,note:'Khách yêu cầu hủy'},
    {id:'ORD-DEMO-1007',customer:'Bùi Mai Linh',phone:'0900000007',address:'Cần Thơ (giả lập)',date:'2026-10-12',status:'pending',payment:'cod',items:[{id:3,name:'Bông tai Celina',qty:1,unit_price:12500000}],shipping_fee:0,note:''},
    {id:'ORD-DEMO-1008',customer:'Ngô Quốc Huy',phone:'0900000008',address:'Hải Phòng (giả lập)',date:'2026-10-12',status:'confirmed',payment:'cod',items:[{id:4,name:'Vòng tay Ocean',qty:2,unit_price:4850000}],shipping_fee:0,note:''}
  ];
  const escapeHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=n=>Number(n||0).toLocaleString('vi-VN')+' ₫';
  const total=o=>o.items.reduce((s,x)=>s+Number(x.qty)*Number(x.unit_price),0)+Number(o.shipping_fee||0);
  function read(){try{const raw=sessionStorage.getItem(KEY);const arr=raw?JSON.parse(raw):null;return Array.isArray(arr)?arr:structuredClone(seed);}catch{return structuredClone(seed);}}
  const save=arr=>sessionStorage.setItem(KEY,JSON.stringify(arr));
  const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
  const badge=s=>`<span class="order-status order-status--${escapeHtml(s)}">${escapeHtml(statuses[s]||s)}</span>`;
  window.LUMIERE_STAFF_ORDERS=({mount})=>{
    let data=read(),query='',filter='',size=5,page=1;
    const opt=(entries,current)=>entries.map(([v,t])=>`<option value="${escapeHtml(v)}" ${String(v)===String(current)?'selected':''}>${escapeHtml(t)}</option>`).join('');
    function render(){
      const results=data.filter(o=>norm([o.id,o.customer,o.phone].join(' ')).includes(norm(query))&&(!filter||o.status===filter)).sort((a,b)=>b.date.localeCompare(a.date)||b.id.localeCompare(a.id));
      const pages=Math.max(1,Math.ceil(results.length/size));page=Math.min(page,pages);
      const shown=results.slice((page-1)*size,page*size);
      mount.innerHTML=`<div class="demo-note"><strong>CHẾ ĐỘ DEMO NHÂN VIÊN.</strong> Đơn hàng giả lập dùng chung dữ liệu trong một tab với trang Admin. Không ghi PostgreSQL, không giao hàng hay thanh toán thật. Backend phải kiểm tra role staff/admin cho từng API.</div>
        <div class="so-title"><div><h2>Xử lý đơn hàng</h2><p class="mini-note">Tiếp nhận, kiểm tra đơn và cập nhật trạng thái</p></div><button type="button" class="button button-outline" id="so-reset">Khôi phục DEMO</button></div>
        <div class="so-stats">
          <div class="stat"><span>Tổng đơn mẫu</span><strong>${data.length}</strong></div>
          <div class="stat"><span>Chờ xác nhận</span><strong>${data.filter(x=>x.status==='pending').length}</strong></div>
          <div class="stat"><span>Đang xử lý / giao</span><strong>${data.filter(x=>['confirmed','preparing','shipping'].includes(x.status)).length}</strong></div>
          <div class="stat"><span>Đã hoàn thành</span><strong>${data.filter(x=>x.status==='completed').length}</strong></div>
        </div><section class="panel so-panel"><div class="so-filters">
          <label class="field"><span>Tìm mã đơn, khách hàng, SĐT</span><input id="so-query" type="search" placeholder="ORD-DEMO-1001..." value="${escapeHtml(query)}"></label>
          <label class="field"><span>Trạng thái</span><select id="so-status">${opt([['','Tất cả'],...Object.entries(statuses)],filter)}</select></label>
          <label class="field"><span>Hiển thị</span><select id="so-size">${opt([['5','5 / trang'],['10','10 / trang'],['20','20 / trang']],size)}</select></label></div>
          <div class="table-wrap"><table class="data-table so-table"><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th>Khách hàng</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng (DEMO)</th><th>Thao tác</th></tr></thead><tbody>${shown.map(o=>`<tr><td><strong>${escapeHtml(o.id)}</strong></td><td>${escapeHtml(o.date)}</td><td>${escapeHtml(o.customer)}<small class="so-sub">${escapeHtml(o.phone)}</small></td><td>${badge(o.status)}</td><td>${escapeHtml(payments[o.payment]||o.payment)}</td><td>${money(total(o))}</td><td><button class="button-sm" type="button" data-so-id="${escapeHtml(o.id)}">Chi tiết</button></td></tr>`).join('')||'<tr><td colspan="7" class="so-empty">Không có đơn phù hợp.</td></tr>'}</tbody></table></div>
          <div class="so-pages"><span>${results.length} đơn · Trang ${page}/${pages}</span><div><button id="so-prev" ${page===1?'disabled':''}>← Trước</button><button id="so-next" ${page===pages?'disabled':''}>Sau →</button></div></div></section>
          <dialog id="so-dialog" class="so-dialog" aria-labelledby="so-detail-title"><div id="so-detail-body"></div><div class="so-dialog-bottom"><button id="so-close" type="button" class="button button-outline">ĐÓNG</button></div></dialog>`;
      const bind=(s,event,fn)=>mount.querySelector(s).addEventListener(event,fn);
      bind('#so-query','input',e=>{const cursor=e.target.selectionStart;query=e.target.value;page=1;render();const field=mount.querySelector('#so-query');field.focus();field.setSelectionRange(cursor,cursor)});
      bind('#so-status','change',e=>{filter=e.target.value;page=1;render()});bind('#so-size','change',e=>{size=Number(e.target.value);page=1;render()});
      bind('#so-prev','click',()=>{page--;render()});bind('#so-next','click',()=>{page++;render()});
      bind('#so-reset','click',()=>{if(confirm('Khôi phục đơn hàng DEMO? Thay đổi demo của Admin trong tab này cũng sẽ mất.')){sessionStorage.removeItem(KEY);data=structuredClone(seed);page=1;render()}});
      mount.querySelectorAll('[data-so-id]').forEach(button=>button.addEventListener('click',()=>open(button.dataset.soId)));
    }
    function open(id){const o=data.find(x=>x.id===id);if(!o)return;const dialog=mount.querySelector('#so-dialog');
      const next=transitions[o.status]||[];
      mount.querySelector('#so-detail-body').innerHTML=`<div class="so-detail-heading"><div><p class="eyebrow">ORDER PROCESSING — DEMO</p><h2 id="so-detail-title">${escapeHtml(o.id)}</h2></div>${badge(o.status)}</div>
        <div class="so-columns"><div><h3>Thông tin người nhận</h3><p><strong>${escapeHtml(o.customer)}</strong></p><p>${escapeHtml(o.phone)}</p><p>${escapeHtml(o.address)}</p></div><div><h3>Thông tin đơn</h3><p>Ngày đặt: ${escapeHtml(o.date)}</p><p>Thanh toán: ${escapeHtml(payments[o.payment]||o.payment)}</p><p>Ghi chú: ${escapeHtml(o.note||'Không có')}</p></div></div>
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>${o.items.map(i=>`<tr><td>${escapeHtml(i.name)}</td><td>${Number(i.qty)}</td><td>${money(i.unit_price)}</td><td>${money(i.qty*i.unit_price)}</td></tr>`).join('')}</tbody></table></div>
        <p class="so-total"><span>Vận chuyển: ${money(o.shipping_fee)}</span><strong>Tổng: ${money(total(o))}</strong></p>
        <div class="so-transition"><label for="so-next-status">Chuyển trạng thái hợp lệ</label><div><select id="so-next-status" ${next.length?'':'disabled'}>${next.length?next.map(s=>`<option value="${escapeHtml(s)}">${escapeHtml(statuses[s])}</option>`).join(''):'<option>Đơn đã kết thúc</option>'}</select><button class="button button-dark" type="button" id="so-apply" ${next.length?'':'disabled'}>XÁC NHẬN (DEMO)</button></div><small>Không tự đánh dấu đã thanh toán. Không chuyển ngược từ Hoàn thành / Đã hủy.</small></div>`;
      dialog.showModal();mount.querySelector('#so-close').onclick=()=>dialog.close();
      mount.querySelector('#so-apply').onclick=()=>{const desired=mount.querySelector('#so-next-status').value;if(!transitions[o.status].includes(desired))return;if(!confirm(`Đổi trạng thái ${o.id} thành ${statuses[desired]} (DEMO)?`))return;o.status=desired;save(data);dialog.close();render()};
    }
    render();
  };
})();
