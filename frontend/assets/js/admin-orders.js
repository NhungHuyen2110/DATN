"use strict";
/* Admin Orders — Business API/PostgreSQL. No demo orders, no sessionStorage. */
(() => {
  const names={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',packing:'Đang đóng gói',shipping:'Đang giao',delivered:'Đã giao',cancelled:'Đã hủy'};
  const transitions={pending:['confirmed','cancelled'],confirmed:['packing','cancelled'],packing:['shipping'],shipping:['delivered'],delivered:[],cancelled:[]};
  const payments={unpaid:'Chưa thanh toán',paid:'Đã thanh toán',refunded:'Đã hoàn tiền'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=n=>Number(n||0).toLocaleString('vi-VN')+' ₫';
  const date=v=>v?new Date(v).toLocaleString('vi-VN'):'—';
  const day=v=>v?String(v).slice(0,10):'';
  const norm=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
  const badge=v=>`<span class="order-status order-status--${esc(v)}">${esc(names[v]||v)}</span>`;
  const options=(obj,current)=>Object.entries(obj).map(([v,s])=>`<option value="${esc(v)}" ${current===v?'selected':''}>${esc(s)}</option>`).join('');
  const api=()=>window.LUMIERE_API;
  window.LUMIERE_ADMIN_ORDERS=({mount})=>{
    let orders=[],page=1,size=20,total=0,q='',status='',payment='',from='',to='',busy=false;
    function fault(message){mount.innerHTML=`<section class="panel order-panel"><h2>Không tải được đơn hàng Admin</h2><p role="alert">${esc(message)}</p><p>Hãy đăng nhập đúng tài khoản Admin và kiểm tra Business API tại localhost:8001.</p><button id="orders-retry" type="button" class="button button-outline">Thử lại</button></section>`;mount.querySelector('#orders-retry').onclick=load;}
    async function load(){
      mount.innerHTML='<section class="panel order-panel">Đang tải đơn hàng từ PostgreSQL…</section>';
      try{
        if(!api()||typeof api().getStaffOrders!=='function')throw Error('api.js chưa có getStaffOrders. Cần giữ bản api.js đã tích hợp Staff Orders.');
        const user=await api().me();
        if(user.role!=='admin')throw Error('Chỉ tài khoản Admin được truy cập mục Quản lý đơn hàng này.');
        // The Staff order API is shared with Admin in the current Backend contract.
        const result=await api().getStaffOrders(page,size);
        if(!Array.isArray(result.items))throw Error('Danh sách đơn từ Backend không hợp lệ.');
        orders=result.items;total=Number(result.total||0);render();
      }catch(e){fault(e.message||String(e));}
    }
    function matches(o){
      const d=day(o.created_at);
      return norm([o.code,o.id,o.recipient_name,o.phone].join(' ')).includes(norm(q)) &&
        (!status||o.status===status) && (!payment||o.payment_status===payment) &&
        (!from||d>=from) && (!to||d<=to);
    }
    function render(){
      const filtered=orders.filter(matches);
      const pages=Math.max(1,Math.ceil(total/size));
      mount.innerHTML=`<div class="order-titlebar"><div><h2>Danh sách đơn hàng</h2><p class="mini-note">Dữ liệu PostgreSQL qua Business API · Tìm kiếm và lọc trong trang hiện tại</p></div><button type="button" id="orders-refresh" class="button button-outline">Làm mới</button></div>
      <div class="order-stats"><div class="stat"><span>Tổng đơn (toàn hệ thống)</span><strong>${total}</strong></div><div class="stat"><span>Chờ xác nhận (trang này)</span><strong>${orders.filter(o=>o.status==='pending').length}</strong></div><div class="stat"><span>Đang xử lý / giao (trang này)</span><strong>${orders.filter(o=>['confirmed','packing','shipping'].includes(o.status)).length}</strong></div><div class="stat"><span>Đã giao (trang này)</span><strong>${orders.filter(o=>o.status==='delivered').length}</strong></div></div>
      <div class="panel order-panel"><div class="order-filters"><label class="field"><span>Tìm mã đơn / ID / khách hàng (trang này)</span><input id="orders-search" type="search" placeholder="Mã đơn LUMIÈRE…" value="${esc(q)}"></label><label class="field"><span>Trạng thái</span><select id="orders-status"><option value="">Tất cả</option>${options(names,status)}</select></label><label class="field"><span>Thanh toán</span><select id="orders-payment"><option value="">Tất cả</option>${options(payments,payment)}</select></label><label class="field"><span>Từ ngày</span><input id="orders-from" type="date" value="${esc(from)}"></label><label class="field"><span>Đến ngày</span><input id="orders-to" type="date" value="${esc(to)}"></label><label class="field"><span>Số đơn / trang</span><select id="orders-size">${[5,10,20,50,100].map(n=>`<option value="${n}" ${size===n?'selected':''}>${n} / trang</option>`).join('')}</select></label></div>
      <div class="order-table-wrap table-wrap"><table class="data-table"><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th>Trạng thái</th><th>Thanh toán</th><th>Tổng tiền</th><th>Thao tác</th></tr></thead><tbody>${filtered.map(o=>`<tr><td><strong>${esc(o.code)}</strong></td><td>${esc(date(o.created_at))}</td><td>${badge(o.status)}</td><td>${esc(payments[o.payment_status]||o.payment_status)}</td><td>${fmt(o.total_vnd)}</td><td><button class="button-sm" type="button" data-order-view="${Number(o.id)}">Chi tiết</button></td></tr>`).join('')||'<tr><td colspan="6" class="order-empty">Không có đơn phù hợp trong trang này.</td></tr>'}</tbody></table></div>
      <div class="order-pagination"><span>Trang ${page}/${pages} · Tổng ${total} đơn · Hiển thị ${filtered.length} đơn phù hợp</span><div><button id="orders-prev" type="button" ${page<=1?'disabled':''}>← Trước</button><button id="orders-next" type="button" ${page>=pages?'disabled':''}>Sau →</button></div></div></div>
      <dialog class="order-dialog" id="orders-dialog" aria-labelledby="orders-dialog-title"><div id="orders-dialog-body"></div><div class="order-dialog-actions"><button id="orders-close" type="button" class="button button-outline">ĐÓNG</button></div></dialog>`;
      const bind=(sel,type,fn)=>mount.querySelector(sel).addEventListener(type,fn);
      bind('#orders-refresh','click',load);
      bind('#orders-search','input',e=>{q=e.target.value;const pos=e.target.selectionStart;render();const input=mount.querySelector('#orders-search');input.focus();input.setSelectionRange(pos,pos)});
      for(const [sel,set] of [['#orders-status',v=>status=v],['#orders-payment',v=>payment=v],['#orders-from',v=>from=v],['#orders-to',v=>to=v]])bind(sel,'change',e=>{set(e.target.value);render()});
      bind('#orders-size','change',e=>{size=Number(e.target.value);page=1;load()});
      bind('#orders-prev','click',()=>{if(page>1){page--;load()}});
      bind('#orders-next','click',()=>{if(page<pages){page++;load()}});
      mount.querySelectorAll('[data-order-view]').forEach(b=>b.onclick=()=>openDetail(Number(b.dataset.orderView)));
    }
    async function openDetail(id){
      const dlg=mount.querySelector('#orders-dialog'),body=mount.querySelector('#orders-dialog-body');
      dlg.showModal();body.textContent='Đang tải chi tiết từ PostgreSQL…';
      mount.querySelector('#orders-close').onclick=()=>dlg.close();
      try{const o=await api().getStaffOrder(id);if(!dlg.open)return;drawDetail(dlg,body,o);}
      catch(e){body.textContent='Không tải được chi tiết: '+(e.message||String(e));}
    }
    function drawDetail(dlg,body,o){
      const next=transitions[o.status]||[];
      const cod=o.status==='delivered'&&o.payment_status==='unpaid';
      body.innerHTML=`<div class="order-detail-header"><div><p class="eyebrow">ĐƠN HÀNG POSTGRESQL</p><h2 id="orders-dialog-title">${esc(o.code)}</h2></div>${badge(o.status)}</div>
      <div class="order-detail-grid"><div><h3>Người nhận</h3><p><strong>${esc(o.recipient_name)}</strong></p><p>${esc(o.phone)}</p><p>${esc(o.address)}</p></div><div><h3>Thông tin đơn</h3><p>Ngày đặt: ${esc(date(o.created_at))}</p><p>Thanh toán: ${esc(payments[o.payment_status]||o.payment_status)}</p><p>ID: ${Number(o.id)}</p></div></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead><tbody>${(o.items||[]).map(i=>`<tr><td>${esc(i.product_name)}</td><td>${Number(i.quantity)}</td><td>${fmt(i.unit_price_vnd)}</td><td>${fmt(i.line_total_vnd)}</td></tr>`).join('')}</tbody></table></div>
      <div class="order-totals"><span>Tạm tính: ${fmt(o.subtotal_vnd)} · Vận chuyển: ${fmt(o.shipping_vnd)} · Giảm giá: ${fmt(o.discount_vnd)}</span><strong>Tổng cộng: ${fmt(o.total_vnd)}</strong></div>
      <div class="order-transition"><label for="orders-next-status"><strong>Chuyển trạng thái hợp lệ</strong></label><div class="order-transition-controls"><select id="orders-next-status" ${next.length?'':'disabled'}>${next.length?next.map(x=>`<option value="${x}">${esc(names[x])}</option>`).join(''):'<option>Không có bước tiếp theo</option>'}</select><button type="button" id="orders-apply" class="button button-dark" ${next.length?'':'disabled'}>XÁC NHẬN CHUYỂN</button></div><p class="mini-note">Giao hàng không tự đánh dấu đã thu tiền. Mọi cập nhật được lưu vào PostgreSQL.</p></div>
      ${cod?'<p><button type="button" class="button button-dark" id="orders-cod">XÁC NHẬN ĐÃ THU TIỀN COD</button></p>':''}
      <p id="orders-error" role="alert" class="form-alert" hidden></p>`;
      const showError=s=>{const el=body.querySelector('#orders-error');el.hidden=false;el.textContent=s};
      body.querySelector('#orders-apply').onclick=async()=>{
        const desired=body.querySelector('#orders-next-status').value;
        if(busy||!next.includes(desired))return;
        if(!confirm(`Cập nhật đơn ${o.code} sang ${names[desired]}? Thao tác ghi PostgreSQL.`))return;
        busy=true;
        try{await api().updateStaffOrderStatus(o.id,desired);dlg.close();await load();}
        catch(e){showError(e.message||String(e))}finally{busy=false}
      };
      const codBtn=body.querySelector('#orders-cod');
      if(codBtn)codBtn.onclick=async()=>{
        if(busy)return;
        const input=prompt(`Nhập mã tham chiếu thu tiền COD cho đơn ${o.code} (3–100 ký tự):`);
        if(input===null)return;
        const reference=input.trim();
        if(reference.length<3||reference.length>100){showError('Mã tham chiếu COD phải có 3–100 ký tự.');return}
        if(!confirm(`Xác nhận đã thu ${fmt(o.total_vnd)} COD cho đơn ${o.code}?\nMã tham chiếu: ${reference}\nGhi dữ liệu thật vào PostgreSQL.`))return;
        busy=true;codBtn.disabled=true;
        try{await api().confirmStaffCOD(o.id,reference);dlg.close();await load();}
        catch(e){showError((e.message||String(e))+' — Nếu không chắc kết quả, làm mới chi tiết trước khi thử lại.');}
        finally{busy=false;codBtn.disabled=false}
      };
    }
    load();
  };
})();
