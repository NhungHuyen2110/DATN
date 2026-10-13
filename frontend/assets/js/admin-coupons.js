"use strict";
/* Coupon management is an isolated frontend DEMO; never redeems real coupons. */
(() => {
  const KEY="lumiere_admin_coupons_demo_v1";
  const SEED=[
    {id:1,code:"LUMIERE10",type:"percent",value:10,maxDiscount:1500000,minOrder:2000000,limit:100,used:22,start:"2026-10-01",end:"2026-12-31",active:true,description:"Ưu đãi thành viên"},
    {id:2,code:"WELCOME200",type:"fixed",value:200000,maxDiscount:0,minOrder:3000000,limit:50,used:14,start:"2026-09-01",end:"2026-12-31",active:true,description:"Khách hàng mới"},
    {id:3,code:"VIP15",type:"percent",value:15,maxDiscount:2500000,minOrder:10000000,limit:30,used:8,start:"2026-10-10",end:"2026-11-30",active:true,description:"Giá trị đơn cao"},
    {id:4,code:"FLASH500",type:"fixed",value:500000,maxDiscount:0,minOrder:8000000,limit:20,used:20,start:"2026-09-01",end:"2026-10-10",active:true,description:"Ưu đãi đã kết thúc"},
    {id:5,code:"GOLD8",type:"percent",value:8,maxDiscount:1000000,minOrder:5000000,limit:80,used:11,start:"2026-11-01",end:"2026-12-31",active:true,description:"Sắp triển khai"},
    {id:6,code:"THANKYOU",type:"fixed",value:150000,maxDiscount:0,minOrder:2000000,limit:100,used:25,start:"2026-10-01",end:"2027-01-01",active:false,description:"Tạm dừng"}
  ];
  const clone=x=>JSON.parse(JSON.stringify(x));
  const safe=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const currency=x=>Number(x||0).toLocaleString("vi-VN")+" ₫";
  const normalize=s=>String(s??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const today=()=>new Date().toLocaleDateString("en-CA");
  const load=()=>{try{const x=JSON.parse(sessionStorage.getItem(KEY));return Array.isArray(x)?x:clone(SEED)}catch{return clone(SEED)}};
  const store=x=>sessionStorage.setItem(KEY,JSON.stringify(x));
  const status=c=>!c.active?"paused":c.used>=c.limit?"exhausted":today()<c.start?"upcoming":today()>c.end?"expired":"active";
  const labels={active:"Đang hiệu lực",paused:"Tạm dừng",exhausted:"Hết lượt",upcoming:"Sắp diễn ra",expired:"Hết hạn"};
  const discount=c=>c.type==="percent"?`${c.value}% (tối đa ${currency(c.maxDiscount)})`:currency(c.value);
  window.LUMIERE_ADMIN_COUPONS=({mount})=>{
    let items=load(),page=1,perPage=5,search="",filter="all";
    mount.innerHTML=`<section class="cp-root"><p class="demo-note"><strong>CHẾ ĐỘ DEMO FRONTEND.</strong> Dữ liệu mã giảm giá chỉ lưu trong sessionStorage của tab, không ghi PostgreSQL và không áp dụng vào giỏ hàng thật. Backend cần kiểm tra quyền admin trước mọi thao tác.</p>
      <div class="cp-heading"><div><h2>Danh sách mã giảm giá</h2><p class="mini-note">Quản lý điều kiện ưu đãi, thời hạn và số lượt sử dụng</p></div><div class="cp-heading-actions"><button id="cp-reset" class="button button-outline" type="button">Khôi phục DEMO</button><button id="cp-create" class="button button-dark" type="button">+ Thêm mã giảm giá</button></div></div>
      <div id="cp-stats" class="cp-stats"></div>
      <div class="panel cp-panel"><div class="cp-filters"><label class="field">Tìm mã / mô tả<input id="cp-search" type="search" placeholder="Ví dụ: LUMIERE10..." autocomplete="off"></label><label class="field">Trạng thái<select id="cp-filter"><option value="all">Tất cả</option><option value="active">Đang hiệu lực</option><option value="upcoming">Sắp diễn ra</option><option value="expired">Hết hạn</option><option value="exhausted">Hết lượt</option><option value="paused">Tạm dừng</option></select></label><label class="field">Hiển thị<select id="cp-size"><option value="5">5 / trang</option><option value="10">10 / trang</option><option value="20">20 / trang</option></select></label></div>
      <div class="table-wrap"><table class="data-table cp-table"><thead><tr><th>Mã giảm giá</th><th>Giá trị</th><th>Đơn tối thiểu</th><th>Hiệu lực</th><th>Đã dùng</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="cp-rows"></tbody></table></div><div class="cp-pager"><span id="cp-summary"></span><div><button id="cp-prev" type="button">← Trước</button><span id="cp-page-label"></span><button id="cp-next" type="button">Sau →</button></div></div></div>
      <dialog class="cp-dialog" id="cp-dialog"><div class="cp-dialog-header"><h2 id="cp-dialog-title"></h2><button type="button" id="cp-close" aria-label="Đóng">×</button></div><div class="cp-notice">Dữ liệu giả lập. Không tạo hoặc thay đổi mã giảm giá thực tế.</div><form id="cp-form"><input type="hidden" id="cp-id"><div class="cp-form-grid">
      <label class="field">Mã giảm giá *<input id="cp-code" name="code" maxlength="24" required placeholder="VD: SALE10" pattern="[A-Za-z0-9_-]{3,24}"></label>
      <label class="field">Loại giảm *<select id="cp-type"><option value="percent">Giảm theo %</option><option value="fixed">Giảm số tiền</option></select></label>
      <label class="field">Giá trị giảm *<input id="cp-value" type="number" min="1" step="1" required></label>
      <label class="field">Giảm tối đa (cho %)<input id="cp-cap" type="number" min="0" step="1000" value="0"></label>
      <label class="field">Giá trị đơn tối thiểu *<input id="cp-min" type="number" min="0" step="1000" required></label>
      <label class="field">Giới hạn lượt dùng *<input id="cp-limit" type="number" min="1" step="1" required></label>
      <label class="field">Từ ngày *<input id="cp-start" type="date" required></label>
      <label class="field">Đến ngày *<input id="cp-end" type="date" required></label>
      <label class="field wide">Mô tả<input id="cp-description" maxlength="160" placeholder="Mô tả ngắn"></label>
      <label class="cp-check wide"><input id="cp-active" type="checkbox" checked> Cho phép sử dụng</label></div>
      <div class="cp-error" id="cp-error" role="alert" hidden></div><div class="cp-dialog-footer"><button class="button button-outline" type="button" id="cp-cancel">Hủy</button><button class="button button-dark" type="submit">Lưu DEMO</button></div></form></dialog></section>`;
    const $=id=>mount.querySelector("#"+id), dialog=$("cp-dialog");
    const field=id=>$(id).value;
    const notify=(msg)=>{const e=$("cp-error");e.textContent=msg;e.hidden=!msg;};
    const count=(value)=>items.filter(c=>status(c)===value).length;
    function draw(){
      $("cp-stats").innerHTML=`<div class="cp-stat"><span>Tổng mã DEMO</span><strong>${items.length}</strong></div><div class="cp-stat"><span>Đang hiệu lực</span><strong>${count("active")}</strong></div><div class="cp-stat"><span>Sắp diễn ra</span><strong>${count("upcoming")}</strong></div><div class="cp-stat"><span>Ngừng / hết hạn / hết lượt</span><strong>${items.length-count("active")-count("upcoming")}</strong></div>`;
      const matches=items.filter(c=>(filter==="all"||status(c)===filter)&&normalize(c.code+" "+c.description).includes(normalize(search))).sort((a,b)=>b.id-a.id);
      const total=Math.max(1,Math.ceil(matches.length/perPage));page=Math.min(page,total);
      const start=(page-1)*perPage,shown=matches.slice(start,start+perPage);
      $("cp-rows").innerHTML=shown.length?shown.map(c=>`<tr><td><strong>${safe(c.code)}</strong><small class="cp-sub">${safe(c.description)}</small></td><td>${safe(discount(c))}</td><td>${currency(c.minOrder)}</td><td><span class="cp-date">${safe(c.start)} → ${safe(c.end)}</span></td><td>${c.used} / ${c.limit}</td><td><span class="cp-badge cp-${status(c)}">${labels[status(c)]}</span></td><td><div class="row-actions"><button class="button-sm" type="button" data-edit="${c.id}">Sửa</button><button class="button-sm" type="button" data-toggle="${c.id}">${c.active?"Tạm dừng":"Mở lại"}</button></div></td></tr>`).join(""):'<tr><td colspan="7" class="cp-empty">Không có mã phù hợp.</td></tr>';
      $("cp-summary").textContent=`Hiển thị ${shown.length} / ${matches.length} mã`;$("cp-page-label").textContent=`Trang ${page}/${total}`;$("cp-prev").disabled=page===1;$("cp-next").disabled=page===total;
    }
    function open(c){$("cp-form").reset();notify("");$("cp-id").value=c?.id??"";$("cp-dialog-title").textContent=c?"Chỉnh sửa mã "+c.code:"Thêm mã giảm giá";
      $("cp-code").value=c?.code||"";$("cp-type").value=c?.type||"percent";$("cp-value").value=c?.value||10;$("cp-cap").value=c?.maxDiscount||0;$("cp-min").value=c?.minOrder??0;$("cp-limit").value=c?.limit||100;$("cp-start").value=c?.start||today();$("cp-end").value=c?.end||today();$("cp-description").value=c?.description||"";$("cp-active").checked=c?.active??true;adjustCap();dialog.showModal();}
    function adjustCap(){const enabled=field("cp-type")==="percent";$("cp-cap").disabled=!enabled;$("cp-cap").required=enabled;}
    $("cp-create").onclick=()=>open(null);$("cp-close").onclick=()=>dialog.close();$("cp-cancel").onclick=()=>dialog.close();$("cp-type").onchange=adjustCap;
    $("cp-reset").onclick=()=>{if(!confirm("Khôi phục toàn bộ mã giảm giá DEMO về ban đầu?"))return;items=clone(SEED);sessionStorage.removeItem(KEY);page=1;draw()};
    $("cp-search").oninput=e=>{search=e.target.value;page=1;draw()};$("cp-filter").onchange=e=>{filter=e.target.value;page=1;draw()};$("cp-size").onchange=e=>{perPage=Number(e.target.value);page=1;draw()};$("cp-prev").onclick=()=>{page--;draw()};$("cp-next").onclick=()=>{page++;draw()};
    $("cp-rows").onclick=e=>{const b=e.target.closest("button");if(!b)return; if(b.dataset.edit){open(items.find(c=>c.id===Number(b.dataset.edit)));return;}if(b.dataset.toggle){const c=items.find(x=>x.id===Number(b.dataset.toggle));if(!c)return;c.active=!c.active;store(items);draw();}};
    $("cp-form").onsubmit=e=>{e.preventDefault();notify("");const id=Number(field("cp-id"));const old=items.find(c=>c.id===id);const code=field("cp-code").trim().toUpperCase();const type=field("cp-type"),value=Number(field("cp-value")),maxDiscount=Number(field("cp-cap")),minOrder=Number(field("cp-min")),limit=Number(field("cp-limit"));const start=field("cp-start"),end=field("cp-end");
      if(!/^[A-Z0-9_-]{3,24}$/.test(code))return notify("Mã gồm 3–24 ký tự A-Z, số, _ hoặc -.");
      if(items.some(c=>c.code===code&&c.id!==id))return notify("Mã giảm giá đã tồn tại.");
      if(!Number.isSafeInteger(value)||value<=0||(type==="percent"&&value>100))return notify("Giá trị giảm không hợp lệ (phần trăm từ 1 đến 100).");
      if(!Number.isSafeInteger(minOrder)||minOrder<0||!Number.isSafeInteger(maxDiscount)||maxDiscount<0)return notify("Số tiền phải là số nguyên không âm.");
      if(type==="percent"&&maxDiscount<=0)return notify("Mã giảm phần trăm phải có mức giảm tối đa lớn hơn 0.");
      if(!Number.isSafeInteger(limit)||limit<1||limit<(old?.used||0))return notify("Giới hạn lượt dùng không hợp lệ hoặc thấp hơn số đã sử dụng.");
      if(!start||!end||end<start)return notify("Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.");
      const valueObj={id:old?.id??Math.max(0,...items.map(c=>c.id))+1,code,type,value,maxDiscount:type==="percent"?maxDiscount:0,minOrder,limit,used:old?.used||0,start,end,active:$("cp-active").checked,description:field("cp-description").trim()};
      if(old)Object.assign(old,valueObj);else items.push(valueObj);store(items);dialog.close();page=1;draw();
    };
    draw();
  };
})();
