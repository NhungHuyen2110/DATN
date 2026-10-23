"use strict";
/* LUMIÈRE Admin Dashboard — reads Business API/PostgreSQL; no demo transactions. */
(() => {
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = v => Number(v || 0).toLocaleString('vi-VN') + ' ₫';
  const num = v => Number(v || 0).toLocaleString('vi-VN');
  const labels = {pending:'Chờ xác nhận',confirmed:'Đã xác nhận',packing:'Đóng gói',shipping:'Đang giao',delivered:'Đã giao',cancelled:'Đã hủy'};
  const card = (label,value,note) => `<div class="dash-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`;
  const vnDate = value => value ? new Date(value).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}) : '—';
  const dayKey = value => {
    if (!value) return '';
    const d = new Date(value);
    if (!Number.isFinite(d.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
    const take = x => parts.find(p=>p.type===x)?.value || '';
    return `${take('year')}-${take('month')}-${take('day')}`;
  };
  async function allOrders(api){
    const list=[];
    for(let page=1;page<=200;page++){
      const response=await api.getStaffOrders(page,20);
      if(!response || !Array.isArray(response.items)) throw Error('Phản hồi danh sách đơn hàng không hợp lệ.');
      list.push(...response.items);
      const total=Number(response.total);
      if((Number.isFinite(total)&&list.length>=total)||response.items.length<20)return list;
    }
    throw Error('Danh sách đơn hàng quá lớn; cần API thống kê chuyên dụng để tránh số liệu thiếu.');
  }
  async function allProducts(api){
    const list=[];
    for(let page=1;page<=200;page++){
      const response=await api.products(page,100);
      if(!response || !Array.isArray(response.items)) throw Error('Phản hồi sản phẩm không hợp lệ.');
      list.push(...response.items);
      const total=Number(response.total);
      if((Number.isFinite(total)&&list.length>=total)||response.items.length<100)return list;
    }
    throw Error('Danh mục quá lớn; cần tải phân trang hoặc API thống kê chuyên dụng.');
  }
  window.LUMIERE_ADMIN_DASHBOARD=({mount})=>{
    if(!mount)return;
    let chartMode='orders';
    const error = message => {mount.innerHTML=`<section class="panel" style="padding:24px"><h2>Không tải được Dashboard Admin</h2><p role="alert">${esc(message)}</p><button id="dash-retry" type="button" class="button button-outline">Thử lại</button></section>`;mount.querySelector('#dash-retry').onclick=load;};
    async function load(){
      mount.innerHTML='<section class="panel" style="padding:24px"><h2>Tổng quan cửa hàng</h2><p>Đang tải số liệu từ Business API · PostgreSQL...</p></section>';
      try{
        const api=window.LUMIERE_API;
        if(!api || typeof api.getStaffOrders!=='function'||typeof api.products!=='function'||typeof api.me!=='function')throw Error('Thiếu Business API (api.js).');
        const user=await api.me();
        if(user.role!=='admin')throw Error('Chỉ tài khoản Admin được xem Dashboard quản trị.');
        const [orders,products]=await Promise.all([allOrders(api),allProducts(api)]);
        const pending=orders.filter(o=>o.status==='pending').length;
        const processing=orders.filter(o=>['confirmed','packing','shipping'].includes(o.status)).length;
        const delivered=orders.filter(o=>o.status==='delivered').length;
        const cancelled=orders.filter(o=>o.status==='cancelled').length;
        const paid=orders.filter(o=>o.payment_status==='paid');
        // Paid total, regardless of delivery state; NOT gross order value or COD receivables.
        const revenue=paid.reduce((sum,o)=>sum+Number(o.total_vnd||0),0);
        const low=products.filter(p=>Number(p.stock)>0&&Number(p.stock)<=5);
        const out=products.filter(p=>Number(p.stock)===0);
        const categories=new Set(products.map(p=>p.category_id??p.category?.id??p.category).filter(v=>v!==null&&v!==undefined&&v!=='')).size;
        const chartDays=[];
        const now=new Date();
        const todayKey=dayKey(now.toISOString());
        // Build local calendar days by operating on the ISO date part; independent of browser timezone.
        for(let ago=6;ago>=0;ago--){
          const d=new Date(`${todayKey}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-ago);
          chartDays.push({key:d.toISOString().slice(0,10),orders:0,revenue:0});
        }
        const map=new Map(chartDays.map(d=>[d.key,d]));
        for(const order of orders){
          const b=map.get(dayKey(order.created_at));
          if(b){b.orders++;if(order.payment_status==='paid')b.revenue+=Number(order.total_vnd||0);}
        }
        const rows=[...orders].sort((a,b)=>new Date(b.created_at)-new Date(a.created_at)).slice(0,5);
        const denom=Math.max(orders.length,1);
        const statusRows=[['Chờ xác nhận',pending],['Đang xử lý / giao',processing],['Đã giao',delivered],['Đã hủy',cancelled]];
        mount.innerHTML=`<section class="dash-section" aria-label="Tổng quan quản trị">
          <div class="dash-head"><div><h2>Tổng quan cửa hàng</h2><p>Số liệu lấy từ Business API · PostgreSQL</p></div><button type="button" class="button button-outline" id="dash-refresh">Làm mới</button></div>
          <div class="dash-kpis">
            ${card('Sản phẩm',num(products.length),'Danh mục: '+num(categories))}
            ${card('Đơn hàng',num(orders.length),pending+' đơn chờ xác nhận')}
            ${card('Giá trị đơn đã thanh toán',fmt(revenue),paid.length+' đơn đã thanh toán (mọi thời điểm)')}
            ${card('Cảnh báo tồn kho',num(low.length+out.length),low.length+' sắp hết · '+out.length+' hết hàng')}
          </div>
          <div class="dash-sections-grid">
            <section class="dash-card"><div class="dash-card-head"><div><h3>Hoạt động 7 ngày gần nhất</h3><p>Doanh thu: đơn đã thanh toán, nhóm theo ngày đặt (giờ Việt Nam)</p></div><label class="dash-chart-control">Chỉ số <select id="dash-chart-type"><option value="orders">Số đơn hàng</option><option value="revenue">Giá trị đơn đã thanh toán</option></select></label></div><div id="dash-chart" class="dash-chart" role="img"></div></section>
            <section class="dash-card"><div class="dash-card-head"><div><h3>Trạng thái đơn hàng</h3><p>${num(orders.length)} đơn hàng thực tế</p></div></div>
              <div class="dash-progress-list">${statusRows.map(([name,n])=>`<div class="dash-progress-row"><span>${esc(name)}</span><div class="dash-progress"><i style="width:${100*n/denom}%"></i></div><b>${n}</b></div>`).join('')}</div><a class="dash-inline-link" href="orders.html">Xem quản lý đơn hàng →</a></section>
          </div>
          <div class="dash-sections-grid dash-bottom-grid">
            <section class="dash-card"><div class="dash-card-head"><div><h3>Đơn hàng gần đây</h3><p>Lấy từ PostgreSQL</p></div><a href="orders.html">Tất cả đơn →</a></div><div class="table-wrap"><table class="data-table dash-table"><thead><tr><th>Mã đơn</th><th>Người nhận</th><th>Tổng tiền</th><th>Trạng thái</th></tr></thead><tbody>${rows.map(o=>`<tr><td><b>${esc(o.code)}</b><small>${esc(vnDate(o.created_at))}</small></td><td>${esc(o.recipient_name||'—')}</td><td>${fmt(o.total_vnd)}</td><td><span class="order-status order-status--${esc(o.status)}">${esc(labels[o.status]||o.status)}</span></td></tr>`).join('')||'<tr><td colspan="4">Chưa có đơn hàng.</td></tr>'}</tbody></table></div></section>
            <section class="dash-card"><div class="dash-card-head"><div><h3>Tồn kho cần chú ý</h3><p>Thông tin tồn kho từ PostgreSQL</p></div><a href="inventory.html">Xem tồn kho →</a></div><div id="dash-stock-list"></div><div class="dash-shortcuts"><a href="products.html">Quản lý sản phẩm ↗</a><a href="analytics.html">Phân tích hành vi ↗</a><a href="coupons.html">Mã giảm giá ↗</a></div></section>
          </div><p class="dash-footer-note">* Số liệu tại thời điểm tải trang. Giá trị đơn đã thanh toán không đồng nghĩa với dòng tiền thực nhận theo ngày; biểu đồ nhóm theo ngày đặt, không phải ngày thu tiền. Các chỉ số được tính từ toàn bộ đơn/sản phẩm đã tải qua API.</p>
        </section>`;
        mount.querySelector('#dash-refresh').onclick=load;
        const drawChart=()=>{
          chartMode=mount.querySelector('#dash-chart-type').value;
          const max=Math.max(1,...chartDays.map(d=>d[chartMode]));
          const chart=mount.querySelector('#dash-chart');
          chart.setAttribute('aria-label',`Biểu đồ ${chartMode==='orders'?'số đơn':'giá trị đơn đã thanh toán'} trong 7 ngày gần nhất`);
          chart.innerHTML=chartDays.map(d=>`<div class="dash-bar-column"><span class="dash-bar-value">${chartMode==='orders'?num(d.orders):(d.revenue/1000000).toLocaleString('vi-VN',{maximumFractionDigits:1})+'tr'}</span><div class="dash-bar-track"><div class="dash-bar-fill" style="height:${d[chartMode]===0?0:Math.max(4,100*d[chartMode]/max)}%"></div></div><span class="dash-bar-label">${esc(d.key.slice(8,10)+'/'+d.key.slice(5,7))}</span></div>`).join('');
        };
        mount.querySelector('#dash-chart-type').addEventListener('change',drawChart);
        drawChart();
        const stock=mount.querySelector('#dash-stock-list');
        const listed=[...out,...low].sort((a,b)=>Number(a.stock)-Number(b.stock)).slice(0,6);
        stock.innerHTML=listed.length?`<div class="dash-stock-list">${listed.map(p=>`<div class="dash-stock-item"><span>${esc(p.name)}<small>ID ${esc(p.id)} · ${esc(p.sku||'')}</small></span><strong>${Number(p.stock)===0?'Hết hàng':num(p.stock)+' còn lại'}</strong></div>`).join('')}</div>`:'<div class="dash-stock-empty">✓ Hiện không có sản phẩm tồn kho thấp hoặc hết hàng.</div>';
      }catch(e){error(e instanceof Error?e.message:String(e));}
    }
    load();
  };
})();
