"use strict";
/* LUMIÈRE Admin Analytics: verified payment revenue only; no synthetic behavior metrics. */
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const amount = v => Number(v || 0);
  const money = v => amount(v).toLocaleString('vi-VN', {maximumFractionDigits:0}) + ' ₫';
  const number = v => Number(v || 0).toLocaleString('vi-VN');
  const viDate = iso => /^\d{4}-\d{2}-\d{2}$/.test(iso || '') ? `${iso.slice(8,10)}/${iso.slice(5,7)}/${iso.slice(0,4)}` : String(iso || '');
  const localToday = () => {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const obj = Object.fromEntries(parts.map(p => [p.type,p.value]));
    return `${obj.year}-${obj.month}-${obj.day}`;
  };
  const minusDays = (iso, days) => {
    const d = new Date(`${iso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() - days);
    return d.toISOString().slice(0,10);
  };
  window.LUMIERE_ADMIN_ANALYTICS = ({mount}) => {
    if (!mount) return;
    let days=30, groupBy='day', metric='amount', report=null, dashboard=null, loading=false;
    let salesRows=null, salesLoading=false;
    mount.innerHTML = `<section class="ana-root">
      <div class="ana-top"><div><h2>Phân tích kinh doanh</h2><p class="mini-note">Số liệu thanh toán thực tế từ Business API · PostgreSQL</p></div>
      <label class="ana-range">Khoảng thời gian <select id="ana-days"><option value="7">7 ngày gần nhất</option><option value="30" selected>30 ngày gần nhất</option><option value="90">90 ngày gần nhất</option></select></label></div>
      <p class="mini-note">Doanh thu được nhóm theo <strong>ngày xác nhận thanh toán</strong> (payment_transaction.verified_at), múi giờ Asia/Ho_Chi_Minh; không phải ngày đặt hàng.</p>
      <div id="ana-message" class="demo-note" role="status" aria-live="polite">Đang tải báo cáo từ PostgreSQL...</div>
      <div class="ana-kpis" id="ana-kpis"></div>
      <div class="ana-chart-grid"><article class="panel ana-panel"><div class="ana-panel-header"><div><h3>Xu hướng thanh toán</h3><p class="mini-note" id="ana-period"></p></div>
      <label class="ana-range">Chỉ số <select id="ana-metric"><option value="amount">Tiền đã thu (VNĐ)</option><option value="count">Số đơn đã thanh toán</option></select></label></div>
      <div id="ana-trend" role="img" aria-label="Biểu đồ thanh toán thực tế theo thời gian"></div></article>
      <article class="panel ana-panel"><h3>Trạng thái dữ liệu</h3><p class="mini-note">Các loại thống kê có thể xác minh từ Backend</p>
      <div id="ana-funnel"></div></article></div>
      <div class="ana-chart-grid"><article class="panel ana-panel"><h3>Báo cáo theo kỳ</h3><p class="mini-note">Dữ liệu thanh toán đã xác nhận; không bao gồm đơn chưa thu tiền</p>
      <div class="table-wrap"><table class="data-table ana-table"><thead><tr><th>Kỳ</th><th>Số đơn đã thanh toán</th><th>Số tiền xác nhận</th></tr></thead><tbody id="ana-products"></tbody></table></div></article>
      <article class="panel ana-panel"><h3>Phân tích hành vi khách hàng</h3><p class="mini-note">Backend chưa cung cấp API ghi nhận sự kiện hành vi</p>
      <div id="ana-keywords"><p>Chưa có dữ liệu theo dõi lượt xem sản phẩm, tìm kiếm, thêm giỏ, yêu thích hoặc nhấp gợi ý AI.</p><p>Không suy diễn lượt tương tác từ đơn hàng và không hiển thị số liệu DEMO.</p></div></article></div>
      <section class="panel ana-panel" style="margin-top:24px" aria-labelledby="ana-sales-title">
        <div class="ana-panel-header"><div><h3 id="ana-sales-title">Sản phẩm bán chạy · Toàn thời gian</h3>
          <p class="mini-note">Tổng hợp từ đơn <code>delivered</code> và <code>paid</code>; <strong>không áp dụng bộ lọc 7/30/90 ngày</strong> vì API đơn hàng chưa cung cấp thời điểm xác nhận thanh toán theo từng dòng sản phẩm.</p></div>
          <button id="ana-sales-reload" type="button" class="button button-outline">Làm mới sản phẩm</button></div>
        <p id="ana-sales-message" class="mini-note" role="status" aria-live="polite">Đang tải dữ liệu bán hàng...</p>
        <div id="ana-sales-kpis" class="ana-kpis"></div>
        <div id="ana-sales-bars" style="margin-top:18px"></div>
        <div class="table-wrap" style="margin-top:20px"><table class="data-table ana-table"><thead><tr><th>STT</th><th>Sản phẩm</th><th>SKU</th><th>Số lượng bán</th><th>Giá trị dòng hàng</th></tr></thead><tbody id="ana-sales-rows"><tr><td colspan="5">Đang tải...</td></tr></tbody></table></div>
        <p class="mini-note" style="margin-top:10px">Giá trị dòng hàng không phải doanh thu đã thu theo kỳ. Khi có chiết khấu, phí vận chuyển hoặc hoàn tiền, các số liệu có thể khác nhau.</p>
        <button id="ana-sales-export" type="button" class="button button-outline" disabled>Xuất CSV sản phẩm</button>
      </section>
      <div class="panel ana-event-panel"><div><h3>Xuất dữ liệu thực</h3><p class="mini-note">CSV gồm kỳ báo cáo, số đơn được xác nhận thanh toán và số tiền</p></div>
      <button id="ana-export" type="button" class="button button-outline" disabled>Xuất báo cáo CSV</button>
      <button id="ana-reload" type="button" class="button button-outline">Làm mới</button></div>
    </section>`;
    const $ = id => mount.querySelector('#'+id);
    const kpi = (label,value,note) => `<article class="ana-kpi"><span>${esc(label)}</span><strong>${esc(value)}</strong>${note?`<small>${esc(note)}</small>`:''}</article>`;
    function showMessage(msg, error=false){$('ana-message').textContent=msg; $('ana-message').style.display=msg?'':'none';$('ana-message').setAttribute('data-error',String(error));}
    function draw(){
      if(!report)return;
      const items=Array.isArray(report.items)?report.items:[];
      const received=amount(report.confirmed_payment_amount_vnd);
      const count=Number(report.confirmed_payment_order_count||0);
      const totalOrders=dashboard?.total_orders;
      $('ana-kpis').innerHTML=[
        kpi('Tiền đã thu trong kỳ',money(received),'Đã xác nhận thanh toán'),
        kpi('Số đơn thu tiền trong kỳ',number(count),'Không tính đơn chưa thanh toán'),
        kpi('Tổng đơn toàn thời gian',totalOrders==null?'—':number(totalOrders),'Thống kê tổng quan Backend'),
        kpi('Bình quân/đơn đã thu',count?money(received/count):'0 ₫','Trong khoảng thời gian chọn')
      ].join('');
      $('ana-period').textContent=`${viDate(report.start_date)} – ${viDate(report.end_date)} · ${report.timezone||'Asia/Ho_Chi_Minh'}`;
      const values=items.map(i=>metric==='count'?Number(i.confirmed_payment_order_count||0):amount(i.confirmed_payment_amount_vnd));
      const max=Math.max(1,...values);
      $('ana-trend').innerHTML=items.length?`<div class="ana-trend" style="overflow-x:auto;min-height:260px">${items.map((item,i)=>{
        const v=values[i]; const label=groupBy==='month'?item.period_start.slice(0,7):item.period_start.slice(5).split('-').reverse().join('/');
        const caption=metric==='count'?number(v):v>=1000000?(v/1000000).toLocaleString('vi-VN',{maximumFractionDigits:1})+'tr':number(v);
        return `<div class="ana-trend-col" style="min-width:${items.length>35?'25px':'34px'}" title="${esc(viDate(item.period_start))}: ${esc(metric==='count'?number(v)+' đơn':money(v))}"><span>${esc(caption)}</span><div class="ana-trend-track"><div style="height:${v?Math.max(2,v/max*100):0}%"></div></div><small>${esc(label)}</small></div>`;
      }).join('')}</div>`:'<p>Không có dữ liệu trong kỳ.</p>';
      $('ana-trend').setAttribute('aria-label',`Biểu đồ ${metric==='count'?'số đơn đã thu tiền':'tiền đã thu'} theo ${groupBy==='month'?'tháng':'ngày'}`);
      $('ana-funnel').innerHTML=`<p><strong>${number(count)}</strong> đơn xác nhận thanh toán trong kỳ.</p><p><strong>${money(received)}</strong> tiền được ghi nhận theo thời điểm xác nhận.</p><p class="ana-footnote">Chưa có dữ liệu sự kiện product_view, search, add_to_cart, favorite, recommendation_click. Không thể tính phễu chuyển đổi hành vi thực tế từ báo cáo doanh thu.</p>`;
      $('ana-products').innerHTML=items.map(item=>`<tr><td>${esc(groupBy==='month'?item.period_start.slice(0,7):viDate(item.period_start))}</td><td>${number(item.confirmed_payment_order_count)}</td><td>${money(item.confirmed_payment_amount_vnd)}</td></tr>`).join('')||'<tr><td colspan="3">Không có dữ liệu</td></tr>';
      $('ana-export').disabled=false;
    }
    async function requestJSON(path){
      const response=await fetch('http://localhost:8001'+path,{credentials:'include',headers:{Accept:'application/json'}});
      const body=await response.json().catch(()=>({}));
      if(!response.ok){const detail=typeof body.detail==='string'?body.detail:`HTTP ${response.status}`;throw new Error(response.status===401?'Vui lòng đăng nhập Admin.':response.status===403?'Tài khoản không có quyền Admin.':detail);}
      return body;
    }
    // Order-item summaries are ALL-TIME and are not mixed with date-scoped payment reporting.
    // No order IDs, customer details or customer addresses are rendered or exported.
    async function loadSales(){
      if(salesLoading)return;
      salesLoading=true;
      $('ana-sales-reload').disabled=true;
      $('ana-sales-export').disabled=true;
      $('ana-sales-message').textContent='Đang tải danh sách và chi tiết đơn hàng...';
      const fail = message => {
        $('ana-sales-message').textContent='Không tải được báo cáo sản phẩm: '+message;
        $('ana-sales-kpis').innerHTML='';
        $('ana-sales-bars').innerHTML='';
        $('ana-sales-rows').innerHTML='<tr><td colspan="5">Chưa có báo cáo hợp lệ.</td></tr>';
      };
      try{
        // Same admin authentication requirement as payment analytics.
        const current=await requestJSON('/auth/me');
        if(current.role!=='admin')throw new Error('Chỉ Admin được xem báo cáo.');
        const pageSize=20;
        const first=await requestJSON('/staff/orders?'+new URLSearchParams({page:'1',page_size:String(pageSize)}));
        if(!Array.isArray(first.items)||!Number.isSafeInteger(Number(first.total))||Number(first.total)<0){
          throw new Error('Phản hồi danh sách đơn hàng không hợp lệ.');
        }
        const total=Number(first.total);
        const pages=Math.ceil(total/pageSize);
        // Client-side aggregation is intended for small/test datasets. Larger data needs server reports.
        if(pages>50)throw new Error('Có hơn 1.000 đơn. Cần API tổng hợp phía Backend để tạo báo cáo chính xác.');
        const orders=[...first.items];
        for(let page=2;page<=pages;page++){
          const data=await requestJSON('/staff/orders?'+new URLSearchParams({page:String(page),page_size:String(pageSize)}));
          if(!Array.isArray(data.items))throw new Error('Dữ liệu phân trang không hợp lệ.');
          orders.push(...data.items);
        }
        if(orders.length!==total)throw new Error('Số đơn thay đổi khi tải các trang; vui lòng làm mới.');
        const eligible=orders.filter(o=>o.status==='delivered'&&o.payment_status==='paid');
        const detailList=[];
        for(let i=0;i<eligible.length;i+=5){
          const batch=eligible.slice(i,i+5);
          detailList.push(...await Promise.all(batch.map(o=>requestJSON('/staff/orders/'+encodeURIComponent(o.id)))));
        }
        const byProduct=new Map();
        let units=0;
        for(const order of detailList){
          if(order.status!=='delivered'||order.payment_status!=='paid'||!Array.isArray(order.items)){
            throw new Error('Dữ liệu chi tiết đơn hàng không nhất quán.');
          }
          for(const item of order.items){
            const qty=Number(item.quantity),value=Number(item.line_total_vnd);
            if(!Number.isInteger(qty)||qty<=0||!Number.isFinite(value)||value<0||item.product_id==null){
              throw new Error('Dữ liệu dòng sản phẩm không hợp lệ.');
            }
            const key=String(item.product_id);
            const row=byProduct.get(key)||{product_id:key,sku:String(item.sku??''),product_name:String(item.product_name??''),quantity:0,line_value_vnd:0};
            row.quantity+=qty;
            row.line_value_vnd+=value;
            units+=qty;
            byProduct.set(key,row);
          }
        }
        salesRows=[...byProduct.values()].sort((a,b)=>b.quantity-a.quantity||b.line_value_vnd-a.line_value_vnd);
        const totalLineValue=salesRows.reduce((sum,r)=>sum+r.line_value_vnd,0);
        $('ana-sales-kpis').innerHTML=[
          kpi('Đơn hoàn tất và đã thanh toán',number(detailList.length),'Toàn thời gian'),
          kpi('Sản phẩm khác nhau',number(salesRows.length),'Đã bán'),
          kpi('Tổng số lượng bán',number(units),'Tất cả dòng hàng hợp lệ'),
          kpi('Giá trị dòng hàng',money(totalLineValue),'Không phải doanh thu theo kỳ')
        ].join('');
        const top=salesRows.slice(0,10),maxQty=Math.max(1,...top.map(r=>r.quantity));
        $('ana-sales-bars').innerHTML=top.length?'<h4 style="margin:0 0 12px">Top 10 theo số lượng</h4>'+top.map(r=>
          `<div style="display:grid;grid-template-columns:minmax(120px,200px) 1fr 40px;align-items:center;gap:12px;margin:10px 0"><span title="${esc(r.product_name)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.product_name)}</span><div style="height:15px;background:#f0ebe4;overflow:hidden"><div style="height:100%;background:#9d8060;width:${(r.quantity/maxQty*100).toFixed(2)}%"></div></div><strong>${number(r.quantity)}</strong></div>`
        ).join(''):'<p>Không có sản phẩm trong đơn đã giao và đã thanh toán.</p>';
        $('ana-sales-rows').innerHTML=salesRows.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.product_name)}</td><td>${esc(r.sku)}</td><td>${number(r.quantity)}</td><td>${money(r.line_value_vnd)}</td></tr>`).join('')||'<tr><td colspan="5">Chưa có dữ liệu.</td></tr>';
        $('ana-sales-message').textContent=`Đã tổng hợp ${number(detailList.length)} / ${number(total)} đơn (toàn thời gian). Nguồn: Business API /staff/orders.`;
        $('ana-sales-export').disabled=false;
      }catch(err){salesRows=null;fail(err.message);}
      finally{salesLoading=false;$('ana-sales-reload').disabled=false;}
    }
    function downloadCSV(rows,filename){
      const csv='\ufeff'+rows.map(row=>row.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');
      const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
    }
    async function load(){
      if(loading)return;loading=true;$('ana-reload').disabled=true;$('ana-export').disabled=true;
      showMessage('Đang tải số liệu từ PostgreSQL...');
      try{
        const user=await requestJSON('/auth/me');
        if(user.role!=='admin')throw new Error('Chỉ tài khoản Admin được xem báo cáo này.');
        const end=localToday(),start=minusDays(end,days-1);
        groupBy=days===90?'month':'day';
        const path='/admin/reports/revenue?'+new URLSearchParams({start_date:start,end_date:end,group_by:groupBy}).toString();
        const [rev,dash]=await Promise.all([requestJSON(path),requestJSON('/admin/dashboard')]);
        report=rev;dashboard=dash;showMessage('');draw();
      }catch(err){report=null;showMessage('Không tải được báo cáo: '+err.message,true);$('ana-kpis').innerHTML='';$('ana-trend').innerHTML='';$('ana-products').innerHTML='';$('ana-funnel').innerHTML='';}
      finally{loading=false;$('ana-reload').disabled=false;}
    }
    $('ana-days').onchange=e=>{days=Number(e.target.value);load();};
    $('ana-metric').onchange=e=>{metric=e.target.value;draw();};
    $('ana-reload').onclick=load;
    $('ana-sales-reload').onclick=loadSales;
    $('ana-sales-export').onclick=()=>{
      if(!salesRows)return;
      downloadCSV([['product_id','sku','product_name','quantity','line_value_vnd'],...salesRows.map(r=>[r.product_id,r.sku,r.product_name,r.quantity,r.line_value_vnd.toFixed(2)])], 'lumiere_products_all_time.csv');
    };
    $('ana-export').onclick=()=>{
      if(!report)return;
      const lines=[['period_start','confirmed_payment_order_count','confirmed_payment_amount_vnd'],...(report.items||[]).map(i=>[i.period_start,i.confirmed_payment_order_count,i.confirmed_payment_amount_vnd])];
      const csv='\ufeff'+lines.map(row=>row.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');
      const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=`lumiere_revenue_${report.start_date}_${report.end_date}.csv`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
    };
    load();
    loadSales();
  };
})();
