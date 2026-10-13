"use strict";
/* LUMIÈRE Admin Dashboard – deterministic demo, no real transactions */
(() => {
  const DEMO_ORDERS = [
    {id:'ORD-DEMO-1008',customer:'Ngô Quốc Huy',date:'2026-10-12',status:'Đã xác nhận',total:9700000},
    {id:'ORD-DEMO-1007',customer:'Bùi Mai Linh',date:'2026-10-12',status:'Chờ xác nhận',total:12500000},
    {id:'ORD-DEMO-1006',customer:'Trần Gia Hân',date:'2026-10-11',status:'Đang chuẩn bị',total:14686287},
    {id:'ORD-DEMO-1005',customer:'Nguyễn Minh Anh',date:'2026-10-11',status:'Hoàn thành',total:8950000},
    {id:'ORD-DEMO-1004',customer:'Phạm Gia Bảo',date:'2026-10-11',status:'Đang giao',total:4850000},
    {id:'ORD-DEMO-1003',customer:'Lê Quốc Bảo',date:'2026-10-10',status:'Chờ xác nhận',total:7200000},
    {id:'ORD-DEMO-1002',customer:'Đỗ Thanh Trúc',date:'2026-10-10',status:'Đã hủy',total:3800000},
    {id:'ORD-DEMO-1001',customer:'Võ Ngọc Mai',date:'2026-10-09',status:'Đang chuẩn bị',total:11200000}
  ];
  const DAILY=[
    {day:'07/10',orders:2,revenue:7500000},
    {day:'08/10',orders:3,revenue:11900000},
    {day:'09/10',orders:4,revenue:17000000},
    {day:'10/10',orders:3,revenue:9800000},
    {day:'11/10',orders:6,revenue:24500000},
    {day:'12/10',orders:5,revenue:18700000},
    {day:'13/10',orders:4,revenue:14300000}
  ];
  const fmt=n=>Number(n||0).toLocaleString('vi-VN')+' ₫';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stateClass=s=>({'Chờ xác nhận':'pending','Hoàn thành':'completed','Đã hủy':'cancelled','Đang giao':'shipping'}[s]||'');
  const card=(label,value,note)=>`<div class="dash-stat"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`;
  window.LUMIERE_ADMIN_DASHBOARD=({mount,products=[]})=>{
    if(!mount)return;
    const currentProducts=Array.isArray(products)?products:[];
    const counts={pending:DEMO_ORDERS.filter(x=>x.status==='Chờ xác nhận').length,processing:DEMO_ORDERS.filter(x=>['Đã xác nhận','Đang chuẩn bị','Đang giao'].includes(x.status)).length,completed:DEMO_ORDERS.filter(x=>x.status==='Hoàn thành').length};
    const low=currentProducts.filter(p=>Number(p.stock)>0&&Number(p.stock)<=5);
    const out=currentProducts.filter(p=>Number(p.stock)===0);
    const categories=new Set(currentProducts.map(p=>p.category)).size;
    const mockCompletedValue=DEMO_ORDERS.filter(x=>x.status==='Hoàn thành').reduce((s,x)=>s+x.total,0);
    mount.innerHTML=`
      <section class="dash-section" aria-label="Tổng quan quản trị">
        <div class="dash-head"><div><h2>Tổng quan cửa hàng</h2><p>Theo dõi hoạt động kinh doanh và tình trạng vận hành</p></div><span class="dash-demo-pill">DỮ LIỆU DEMO</span></div>
        <div class="demo-note"><b>CHẾ ĐỘ XEM TRƯỚC.</b> Đơn hàng, doanh thu và biểu đồ bên dưới là số liệu giả lập, không lấy từ PostgreSQL. Các liên kết quản trị chỉ để xem giao diện. Backend phải xác thực vai trò admin.</div>
        <div class="dash-kpis">
          ${card('Sản phẩm mẫu',currentProducts.length,'Danh mục: '+categories)}
          ${card('Đơn hàng mẫu',DEMO_ORDERS.length,counts.pending+' đơn chờ xác nhận')}
          ${card('Doanh thu hoàn thành DEMO',fmt(mockCompletedValue),'Chỉ tổng đơn hoàn thành giả lập')}
          ${card('Cảnh báo tồn kho',low.length+out.length,low.length+' sắp hết · '+out.length+' hết hàng')}
        </div>
        <div class="dash-sections-grid">
          <section class="dash-card"><div class="dash-card-head"><div><h3>Xu hướng hoạt động DEMO</h3><p>Số liệu minh họa theo ngày</p></div><label class="dash-chart-control">Chỉ số <select id="dash-chart-type"><option value="orders">Số đơn hàng</option><option value="revenue">Doanh thu</option></select></label></div><div id="dash-chart" class="dash-chart" role="img" aria-label="Biểu đồ cột số đơn hàng mẫu theo ngày"></div></section>
          <section class="dash-card"><div class="dash-card-head"><div><h3>Trạng thái đơn DEMO</h3><p>8 đơn mẫu, không phải đơn thật</p></div></div>
          <div class="dash-progress-list">
            ${[['Chờ xác nhận',counts.pending],['Đang xử lý / giao',counts.processing],['Hoàn thành',counts.completed],['Đã hủy',DEMO_ORDERS.filter(x=>x.status==='Đã hủy').length]].map(([label,count])=>`<div class="dash-progress-row"><span>${label}</span><div class="dash-progress"><i style="width:${100*count/DEMO_ORDERS.length}%"></i></div><b>${count}</b></div>`).join('')}
          </div><a class="dash-inline-link" href="orders.html">Xem quản lý đơn hàng →</a></section>
        </div>
        <div class="dash-sections-grid dash-bottom-grid">
          <section class="dash-card"><div class="dash-card-head"><div><h3>Đơn hàng gần đây</h3><p>Danh sách ví dụ để kiểm thử</p></div><a href="orders.html">Tất cả đơn →</a></div><div class="table-wrap"><table class="data-table dash-table"><thead><tr><th>Mã đơn</th><th>Khách hàng</th><th>Tổng tiền</th><th>Trạng thái</th></tr></thead><tbody>${DEMO_ORDERS.slice(0,5).map(o=>`<tr><td><b>${esc(o.id)}</b><small>${esc(o.date)}</small></td><td>${esc(o.customer)}</td><td>${fmt(o.total)}</td><td><span class="order-status order-status--${stateClass(o.status)}">${esc(o.status)}</span></td></tr>`).join('')}</tbody></table></div></section>
          <section class="dash-card"><div class="dash-card-head"><div><h3>Tồn kho cần chú ý</h3><p>Dữ liệu sản phẩm DEMO gốc</p></div><a href="inventory.html">Xem tồn kho →</a></div><div id="dash-stock-list"></div><div class="dash-shortcuts"><a href="products.html">Quản lý sản phẩm ↗</a><a href="analytics.html">Phân tích hành vi ↗</a><a href="coupons.html">Mã giảm giá ↗</a></div></section>
        </div>
        <p class="dash-footer-note">* Dashboard chưa đồng bộ với các chỉnh sửa DEMO ở trang khác. Khi triển khai backend, thống kê phải lấy từ cùng nguồn dữ liệu thật và có bộ lọc thời gian.</p>
      </section>`;
    function drawChart(){
      const which=mount.querySelector('#dash-chart-type').value;
      const maximum=Math.max(...DAILY.map(d=>d[which]));
      const chart=mount.querySelector('#dash-chart');
      chart.setAttribute('aria-label',`Biểu đồ ${which==='orders'?'số đơn hàng':'doanh thu'} demo theo ngày`);
      chart.innerHTML=DAILY.map(d=>`<div class="dash-bar-column"><span class="dash-bar-value">${which==='orders'?d.orders:(d.revenue/1000000).toLocaleString('vi-VN')+'tr'}</span><div class="dash-bar-track"><div class="dash-bar-fill" style="height:${Math.max(4,100*d[which]/maximum)}%"></div></div><span class="dash-bar-label">${d.day}</span></div>`).join('');
    }
    mount.querySelector('#dash-chart-type').addEventListener('change',drawChart);
    drawChart();
    const stock=mount.querySelector('#dash-stock-list');
    if(!low.length&&!out.length){
      stock.innerHTML=`<div class="dash-stock-empty">✓ Chưa có sản phẩm tồn kho thấp hoặc hết hàng trong dữ liệu sản phẩm mẫu.</div>`;
    }else{
      stock.innerHTML=`<div class="dash-stock-list">${[...out,...low].slice(0,6).map(p=>`<div class="dash-stock-item"><span>${esc(p.name)}<small>ID ${esc(p.id)} · ${esc(p.category)}</small></span><strong>${p.stock===0?'Hết hàng':p.stock+' còn lại'}</strong></div>`).join('')}</div>`;
    }
  };
})();
