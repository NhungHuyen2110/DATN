"use strict";
/* Behavioral analytics preview: deliberately synthetic aggregates, not browser tracking. */
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => Number(n||0).toLocaleString('vi-VN');
  const pct = (a,b) => b ? ((a/b)*100).toFixed(1).replace('.',',')+'%' : '0%';
  const EVENT_LABELS = {product_view:'Xem sản phẩm', search:'Tìm kiếm', add_to_cart:'Thêm giỏ hàng', favorite:'Yêu thích', purchase:'Mua hàng'};
  const DATA = [
    {d:'2026-10-01',product_view:105,search:45,add_to_cart:21,favorite:13,purchase:6},
    {d:'2026-10-02',product_view:117,search:51,add_to_cart:24,favorite:14,purchase:7},
    {d:'2026-10-03',product_view:131,search:58,add_to_cart:30,favorite:19,purchase:8},
    {d:'2026-10-04',product_view:122,search:46,add_to_cart:25,favorite:15,purchase:6},
    {d:'2026-10-05',product_view:144,search:63,add_to_cart:35,favorite:20,purchase:10},
    {d:'2026-10-06',product_view:152,search:66,add_to_cart:38,favorite:21,purchase:11},
    {d:'2026-10-07',product_view:163,search:69,add_to_cart:40,favorite:25,purchase:12},
    {d:'2026-10-08',product_view:171,search:74,add_to_cart:44,favorite:28,purchase:13},
    {d:'2026-10-09',product_view:166,search:70,add_to_cart:41,favorite:25,purchase:11},
    {d:'2026-10-10',product_view:187,search:80,add_to_cart:47,favorite:32,purchase:15},
    {d:'2026-10-11',product_view:193,search:83,add_to_cart:52,favorite:34,purchase:16},
    {d:'2026-10-12',product_view:205,search:87,add_to_cart:56,favorite:35,purchase:17},
    {d:'2026-10-13',product_view:213,search:95,add_to_cart:59,favorite:38,purchase:19}
  ];
  const SEARCHES=[['nhẫn kim cương',84],['dây chuyền vàng',62],['bông tai',48],['vòng tay',39],['quà kỷ niệm',28],['nhẫn dưới 10 triệu',22]];
  const SOURCE=[['Tìm kiếm tự nhiên',43],['Trực tiếp',29],['Mạng xã hội',18],['Giới thiệu',10]];
  window.LUMIERE_ADMIN_ANALYTICS = ({mount,products=[]}) => {
    let days=7,metric='product_view';
    const productRows=products.slice(0,6).map((p,i)=>({id:p.id,name:p.name,views:[184,161,148,130,112,98][i]||80,adds:[46,37,34,26,20,16][i]||12}));
    mount.innerHTML=`<section class="ana-root"><p class="demo-note"><strong>CHẾ ĐỘ DEMO – SỐ LIỆU GIẢ LẬP.</strong> Toàn bộ số liệu hành vi và chuyển đổi dưới đây được tạo để thử giao diện; không phải log khách hàng, không kết nối PostgreSQL hay AI và không phản ánh doanh thu thật. Các con số <strong>là số lượt sự kiện</strong>, không phải người dùng duy nhất.</p>
      <div class="ana-top"><div><h2>Hành vi khách hàng</h2><p class="mini-note">Theo dõi tương tác và khám phá hành trình mua sắm</p></div><label class="ana-range">Khoảng thời gian<select id="ana-days"><option value="7">7 ngày gần nhất trong dữ liệu DEMO</option><option value="13">Toàn bộ 13 ngày DEMO</option></select></label></div>
      <div class="ana-kpis" id="ana-kpis"></div>
      <div class="ana-chart-grid"><article class="panel ana-panel"><div class="ana-panel-header"><div><h3>Xu hướng tương tác</h3><p class="mini-note">Số lượt sự kiện mỗi ngày</p></div><select id="ana-metric" aria-label="Chọn loại sự kiện"><option value="product_view">Xem sản phẩm</option><option value="search">Tìm kiếm</option><option value="add_to_cart">Thêm giỏ hàng</option><option value="favorite">Yêu thích</option><option value="purchase">Mua hàng</option></select></div><div id="ana-trend" role="img" aria-label="Biểu đồ cột xu hướng theo ngày"></div></article>
      <article class="panel ana-panel"><h3>Phễu tương tác DEMO</h3><p class="mini-note">Tỷ lệ lượt sự kiện so với lượt xem sản phẩm; không phải tỷ lệ chuyển đổi theo người dùng</p><div id="ana-funnel"></div><p class="ana-footnote">* Các bước này không liên kết theo phiên hoặc theo người mua. Để tính phễu chuyển đổi thực, backend cần event/session ID và truy vấn cohort.</p></article></div>
      <div class="ana-chart-grid"><article class="panel ana-panel"><h3>Sản phẩm quan tâm (DEMO)</h3><p class="mini-note">Lượt xem và thêm giỏ mô phỏng theo sản phẩm</p><div class="table-wrap"><table class="data-table ana-table"><thead><tr><th>Sản phẩm</th><th>Lượt xem</th><th>Thêm giỏ</th></tr></thead><tbody id="ana-products"></tbody></table></div></article>
      <article class="panel ana-panel"><h3>Từ khóa tìm kiếm phổ biến</h3><p class="mini-note">Dữ liệu ví dụ, không phải truy vấn cá nhân thực tế</p><div id="ana-keywords"></div><h3 class="ana-subhead">Nguồn truy cập giả lập</h3><div id="ana-source"></div></article></div>
      <div class="panel ana-event-panel"><div><h3>Dữ liệu backend cần cung cấp</h3><p class="mini-note">product_view · search · add_to_cart · favorite · purchase · recommendation_click</p></div><button id="ana-export" type="button" class="button button-outline">Xuất báo cáo DEMO (CSV)</button><p class="ana-footnote">Tải CSV chỉ chứa số tổng hợp giả lập hiển thị ở biểu đồ; không xuất dữ liệu khách hàng thực.</p></div>
    </section>`;
    const $=id=>mount.querySelector('#'+id);
    function bars(rows,max,showValue=true){return rows.map(([label,value])=>`<div class="ana-bar-row"><span class="ana-bar-label">${esc(label)}</span><div class="ana-bar-track"><div class="ana-bar-fill" style="width:${max?Math.max(0,value/max*100):0}%"></div></div>${showValue?`<strong>${fmt(value)}</strong>`:''}</div>`).join('')}
    function totals(rows){return Object.keys(EVENT_LABELS).reduce((a,k)=>(a[k]=rows.reduce((n,r)=>n+r[k],0),a),{})}
    function draw(){const selected=DATA.slice(-days),t=totals(selected);const kpis=[['Lượt xem sản phẩm',t.product_view],['Lượt tìm kiếm',t.search],['Lượt thêm giỏ',t.add_to_cart],['Lượt mua DEMO',t.purchase]];$('ana-kpis').innerHTML=kpis.map(([name,count])=>`<article class="ana-kpi"><span>${name}</span><strong>${fmt(count)}</strong></article>`).join('');const max=Math.max(...selected.map(r=>r[metric]),1);$('ana-trend').innerHTML=`<div class="ana-trend">${selected.map(r=>`<div class="ana-trend-col" title="${esc(r.d)}: ${fmt(r[metric])}"><span>${fmt(r[metric])}</span><div class="ana-trend-track"><div style="height:${r[metric]/max*100}%"></div></div><small>${r.d.slice(8)}/${r.d.slice(5,7)}</small></div>`).join('')}</div>`;$('ana-funnel').innerHTML=bars([['Xem sản phẩm',t.product_view],['Thêm giỏ',t.add_to_cart],['Mua hàng (demo)',t.purchase]],t.product_view)+`<p class="ana-ratio">Lượt thêm giỏ / lượt xem: <strong>${pct(t.add_to_cart,t.product_view)}</strong> · Lượt mua / lượt xem: <strong>${pct(t.purchase,t.product_view)}</strong></p>`;
      $('ana-products').innerHTML=productRows.map(p=>`<tr><td><strong>${esc(p.name)}</strong><small class="ana-muted">ID: ${esc(p.id)}</small></td><td>${fmt(p.views)}</td><td>${fmt(p.adds)}</td></tr>`).join('')||'<tr><td colspan="3">Không có sản phẩm DEMO.</td></tr>';
      $('ana-keywords').innerHTML=bars(SEARCHES,SEARCHES[0][1]);$('ana-source').innerHTML=SOURCE.map(([label,val])=>`<div class="ana-source-row"><span>${esc(label)}</span><div class="ana-bar-track"><div class="ana-bar-fill" style="width:${val}%"></div></div><strong>${val}%</strong></div>`).join('')
    }
    $('ana-days').onchange=e=>{days=Number(e.target.value);draw()};$('ana-metric').onchange=e=>{metric=e.target.value;draw()};
    $('ana-export').onclick=()=>{const selected=DATA.slice(-days),fields=['date',...Object.keys(EVENT_LABELS)];const csv=['DEMO - SYNTHETIC DATA; NOT REAL CUSTOMER EVENTS',fields.join(','),...selected.map(r=>[r.d,...fields.slice(1).map(k=>r[k])].join(','))].join('\r\n');const blob=new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='lumiere_analytics_DEMO.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
    draw();
  };
})();
