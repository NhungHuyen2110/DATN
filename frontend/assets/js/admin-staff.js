"use strict";
/* Frontend-only prototype. Never treats demo role/status changes as real authorization. */
(() => {
  const KEY = "lumiere_staff_demo_v1";
  const SEED = [
    {id:"NV-DEMO-001",name:"Nguyễn Thảo Vy",email:"thaovy@example.com",phone:"0900000101",role:"staff",department:"Bán hàng",joined:"2026-03-10",active:true},
    {id:"NV-DEMO-002",name:"Trần Minh Quân",email:"minhquan@example.com",phone:"0900000102",role:"staff",department:"Kho",joined:"2026-04-12",active:true},
    {id:"NV-DEMO-003",name:"Phạm Hải Anh",email:"haianh@example.com",phone:"0900000103",role:"staff",department:"Chăm sóc khách hàng",joined:"2026-05-05",active:true},
    {id:"NV-DEMO-004",name:"Lê Hoàng Phúc",email:"hoangphuc@example.com",phone:"0900000104",role:"staff",department:"Bán hàng",joined:"2026-06-16",active:false},
    {id:"NV-DEMO-005",name:"Võ Ngọc Mai",email:"ngocmai@example.com",phone:"0900000105",role:"staff",department:"Kho",joined:"2026-07-02",active:true},
    {id:"NV-DEMO-006",name:"Đặng Quốc Huy",email:"quochuy@example.com",phone:"0900000106",role:"staff",department:"Chăm sóc khách hàng",joined:"2026-08-18",active:false},
    {id:"NV-DEMO-007",name:"Bùi Thanh Hà",email:"thanhha@example.com",phone:"0900000107",role:"staff",department:"Bán hàng",joined:"2026-09-01",active:true}
  ];
  const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normalized = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/đ/g,"d").replace(/Đ/g,"D").toLowerCase().trim();
  const fresh = () => SEED.map(x => ({...x}));
  const load = () => { try {const a=JSON.parse(sessionStorage.getItem(KEY));return Array.isArray(a)?a:fresh();} catch {return fresh();} };
  const save = () => sessionStorage.setItem(KEY,JSON.stringify(state.rows));
  let state;
  window.LUMIERE_ADMIN_STAFF = function ({mount}) {
    if (!mount) return;
    state={rows:load(),page:1,size:5,q:"",status:"all",department:"all"};
    mount.innerHTML=`
      <p class="demo-note"><strong>CHẾ ĐỘ DEMO FRONTEND.</strong> Thêm, sửa, khóa và mở tài khoản chỉ thay đổi dữ liệu giả trong tab này; không tạo tài khoản, gửi email, cập nhật vai trò hay khóa bất kỳ người dùng nào trong PostgreSQL. API thật phải kiểm tra quyền admin.</p>
      <div class="em-head"><div><h2>Danh sách nhân viên</h2><p class="mini-note">Thông tin nhân sự mẫu cho quy trình quản trị LUMIÈRE.</p></div><div class="em-head-actions"><button class="button button-outline" id="em-reset">Khôi phục DEMO</button><button class="button button-dark" id="em-new">+ Thêm nhân viên</button></div></div>
      <div class="em-stats" id="em-stats"></div>
      <section class="panel em-panel"><div class="em-filters">
        <label class="field"><span>Tìm tên, mã, email, điện thoại</span><input id="em-search" type="search" placeholder="VD: NV-DEMO-001, Thảo Vy..."></label>
        <label class="field"><span>Bộ phận</span><select id="em-department"><option value="all">Tất cả</option><option>Bán hàng</option><option>Kho</option><option>Chăm sóc khách hàng</option></select></label>
        <label class="field"><span>Trạng thái</span><select id="em-status"><option value="all">Tất cả</option><option value="active">Đang hoạt động</option><option value="locked">Đã khóa</option></select></label>
        <label class="field"><span>Hiển thị</span><select id="em-size"><option value="5">5 / trang</option><option value="10">10 / trang</option><option value="20">20 / trang</option></select></label>
      </div>
      <div class="table-wrap"><table class="data-table em-table"><thead><tr><th>Mã NV</th><th>Họ tên / Email</th><th>Điện thoại</th><th>Bộ phận</th><th>Ngày vào</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="em-body"></tbody></table></div>
      <div class="em-pager"><span id="em-range"></span><div><button type="button" id="em-prev">← Trước</button><span id="em-page"></span><button type="button" id="em-next">Sau →</button></div></div></section>
      <dialog class="em-dialog" id="em-dialog" aria-labelledby="em-dialog-title"><form id="em-form" novalidate><div class="em-dialog-head"><h2 id="em-dialog-title">Thêm nhân viên demo</h2><button type="button" id="em-close" aria-label="Đóng">×</button></div><p class="mini-note">Không nhập mật khẩu ở đây. Tài khoản thật phải được admin tạo qua backend và nhân viên thiết lập mật khẩu bằng liên kết bảo mật.</p><div id="em-form-error" class="em-error" role="alert" hidden></div><div class="em-form-grid">
        <label class="field"><span>Mã nhân viên</span><input id="em-id" maxlength="30" required></label>
        <label class="field"><span>Họ và tên</span><input id="em-name" maxlength="150" required></label>
        <label class="field"><span>Email</span><input id="em-email" type="email" maxlength="255" required></label>
        <label class="field"><span>Số điện thoại</span><input id="em-phone" inputmode="numeric" pattern="0[0-9]{9}" maxlength="10" required></label>
        <label class="field"><span>Bộ phận</span><select id="em-form-department"><option>Bán hàng</option><option>Kho</option><option>Chăm sóc khách hàng</option></select></label>
        <label class="field"><span>Ngày vào làm</span><input id="em-joined" type="date" required></label>
      </div><div class="em-form-actions"><button type="button" class="button button-outline" id="em-cancel">Hủy</button><button type="submit" class="button button-dark">Lưu DEMO</button></div></form></dialog>
      <dialog class="em-detail-dialog" id="em-detail-dialog" aria-labelledby="em-detail-title">
        <div class="em-detail-head"><h2 id="em-detail-title">Chi tiết nhân viên</h2><button type="button" id="em-detail-x" aria-label="Đóng chi tiết">×</button></div>
        <p class="em-detail-note">Đây là hồ sơ minh họa, không phải dữ liệu nhân viên trong PostgreSQL. Không hiển thị mật khẩu hoặc mã băm.</p>
        <dl class="em-detail-info" id="em-detail-info"></dl>
        <p class="em-detail-footnote">Tài khoản, phân quyền và lịch sử làm việc thực tế sẽ được lấy từ API quản trị có xác thực.</p>
        <div class="em-detail-bottom"><button type="button" class="button button-outline" id="em-detail-close">Đóng</button></div>
      </dialog>`;
    const $ = selector => mount.querySelector(selector);
    const dialog = $("#em-dialog");
    const modalError = $("#em-form-error");
    const detailDialog = $("#em-detail-dialog");
    function showDetails(row) {
      $("#em-detail-title").textContent = `Nhân viên ${row.id}`;
      const fields = [
        ["Họ tên",row.name], ["Email",row.email], ["Điện thoại",row.phone],
        ["Bộ phận",row.department], ["Vai trò","Nhân viên (staff)"],
        ["Ngày vào làm",row.joined], ["Trạng thái",row.active?"Hoạt động":"Đã khóa"]
      ];
      $("#em-detail-info").innerHTML = fields.map(([label,value]) =>
        `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd></div>`
      ).join("");
      detailDialog.showModal();
    }
    $("#em-detail-x").onclick = () => detailDialog.close();
    $("#em-detail-close").onclick = () => detailDialog.close();
    let editingId = null;
    const display = () => {
      const total=state.rows.length,active=state.rows.filter(r=>r.active).length;
      $("#em-stats").innerHTML=[['Tổng nhân viên',total],['Đang hoạt động',active],['Đã khóa',total-active]].map(([a,b])=>`<div class="em-stat"><span>${a}</span><strong>${b}</strong></div>`).join('');
      const matches=state.rows.filter(r=>{
        const searchable=normalized([r.id,r.name,r.email,r.phone,r.department].join(' '));
        return searchable.includes(normalized(state.q)) && (state.status==='all'||(state.status==='active')===r.active) && (state.department==='all'||state.department===r.department);
      });
      const pages=Math.max(1,Math.ceil(matches.length/state.size));state.page=Math.min(state.page,pages);
      const start=(state.page-1)*state.size, subset=matches.slice(start,start+state.size);
      $("#em-body").innerHTML=subset.map(r=>`<tr><td><strong>${escapeHTML(r.id)}</strong></td><td><strong>${escapeHTML(r.name)}</strong><small class="em-muted">${escapeHTML(r.email)}</small></td><td>${escapeHTML(r.phone)}</td><td>${escapeHTML(r.department)}</td><td>${escapeHTML(r.joined)}</td><td><span class="em-badge ${r.active?'em-active':'em-locked'}">${r.active?'Hoạt động':'Đã khóa'}</span></td><td><div class="em-actions"><button class="button-sm" data-action="view" data-id="${escapeHTML(r.id)}">Chi tiết</button><button class="button-sm" data-action="edit" data-id="${escapeHTML(r.id)}">Sửa</button><button class="button-sm" data-action="toggle" data-id="${escapeHTML(r.id)}">${r.active?'Khóa':'Mở khóa'}</button></div></td></tr>`).join('') || '<tr><td colspan="7" class="em-empty">Không tìm thấy nhân viên phù hợp.</td></tr>';
      $("#em-range").textContent=matches.length?`Hiển thị ${start+1}–${Math.min(start+state.size,matches.length)} / ${matches.length}`:'Không có kết quả';
      $("#em-page").textContent=`Trang ${state.page} / ${pages}`;
      $("#em-prev").disabled=state.page<=1;$("#em-next").disabled=state.page>=pages;
    };
    const close=()=>dialog.close();
    const open=(row=null)=>{
      editingId=row?.id??null;modalError.hidden=true;
      $("#em-dialog-title").textContent=row?'Sửa nhân viên DEMO':'Thêm nhân viên DEMO';
      $("#em-id").value=row?.id??`NV-DEMO-${String(Math.max(0,...state.rows.map(r=>Number(r.id.replace('NV-DEMO-',''))||0))+1).padStart(3,'0')}`;
      $("#em-id").readOnly=!!row;
      $("#em-name").value=row?.name??'';
      $("#em-email").value=row?.email??'';
      $("#em-phone").value=row?.phone??'';
      $("#em-form-department").value=row?.department??'Bán hàng';
      $("#em-joined").value=row?.joined??new Date().toISOString().slice(0,10);
      dialog.showModal();
    };
    $("#em-search").oninput=e=>{state.q=e.target.value;state.page=1;display()};
    $("#em-status").onchange=e=>{state.status=e.target.value;state.page=1;display()};
    $("#em-department").onchange=e=>{state.department=e.target.value;state.page=1;display()};
    $("#em-size").onchange=e=>{state.size=Number(e.target.value);state.page=1;display()};
    $("#em-prev").onclick=()=>{state.page--;display()};
    $("#em-next").onclick=()=>{state.page++;display()};
    $("#em-new").onclick=()=>open();
    $("#em-reset").onclick=()=>{if(!confirm('Khôi phục toàn bộ dữ liệu nhân viên DEMO?'))return;state.rows=fresh();state.page=1;save();display()};
    $("#em-close").onclick=close;$("#em-cancel").onclick=close;
    $("#em-body").onclick=e=>{
      const b=e.target.closest('button[data-action]');if(!b)return;
      const row=state.rows.find(x=>x.id===b.dataset.id);if(!row)return;
      if(b.dataset.action==='edit')open(row);
      if(b.dataset.action==='view')showDetails(row);
      if(b.dataset.action==='toggle'){
        if(!confirm(`${row.active?'Khóa':'Mở khóa'} nhân viên ${row.name} trong dữ liệu DEMO?`))return;
        row.active=!row.active;save();display();
      }
    };
    $("#em-form").onsubmit=e=>{
      e.preventDefault();
      const data={id:$("#em-id").value.trim(),name:$("#em-name").value.trim().replace(/\s+/g,' '),email:$("#em-email").value.trim().toLowerCase(),phone:$("#em-phone").value.trim(),department:$("#em-form-department").value,joined:$("#em-joined").value,role:'staff',active:true};
      let error='';
      if(!/^NV-DEMO-[0-9]{3,}$/.test(data.id))error='Mã nhân viên phải có dạng NV-DEMO-001.';
      else if(data.name.length<2)error='Họ tên cần ít nhất 2 ký tự.';
      else if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))error='Email không hợp lệ.';
      else if(!/^0[0-9]{9}$/.test(data.phone))error='Số điện thoại phải có 10 chữ số và bắt đầu bằng 0.';
      else if(!/^\d{4}-\d{2}-\d{2}$/.test(data.joined)||Number.isNaN(Date.parse(data.joined)))error='Ngày vào làm không hợp lệ.';
      else if(state.rows.some(r=>r.id===data.id&&r.id!==editingId))error='Mã nhân viên đã tồn tại.';
      else if(state.rows.some(r=>r.email.toLowerCase()===data.email&&r.id!==editingId))error='Email đã được sử dụng.';
      else if(state.rows.some(r=>r.phone===data.phone&&r.id!==editingId))error='Số điện thoại đã được sử dụng.';
      if(error){modalError.hidden=false;modalError.textContent=error;return;}
      const existing=state.rows.find(r=>r.id===editingId);
      if(existing)Object.assign(existing,{...data,active:existing.active});
      else state.rows.unshift(data);
      save();close();display();
    };
    display();
  };
})();
