"use strict";
/* FRONTEND-ONLY admin prototype. Never sends writes to backend. */
window.LUMIERE_ADMIN_PRODUCTS = function ({mount, products, money, esc, authorized}) {
  const STORAGE = 'lumiere_admin_products_preview_v1';
  const base = products.map(p => ({
    id: Number(p.id), name: String(p.name || ''), sku: String(p.sku || `DEMO-${String(p.id).padStart(4,'0')}`),
    category: String(p.category || 'Khác'), brand: String(p.brand || 'LUMIÈRE'),
    material: String(p.material || ''), gem: String(p.gem || ''),
    price: Number(p.price) || 0, stock: Number(p.stock) || 0,
    image: String(p.image || ''), status: 'active', description: String(p.description || '')
  }));
  let rows;
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE));
    rows = Array.isArray(saved) ? saved : structuredClone(base);
  } catch { rows = structuredClone(base); }
  const state = {page:1, size:5, q:'', category:'', brand:'', status:''};
  const categories = [...new Set([...base.map(x=>x.category),'Nhẫn','Dây chuyền','Bông tai','Vòng tay'])];
  const brands = [...new Set([...base.map(x=>x.brand),'LUMIÈRE'])];
  const sel = (id) => mount.querySelector('#'+id);
  const optionList = vals => vals.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  const cleanImage = url => {try{const u=new URL(url,location.href);return ['http:','https:'].includes(u.protocol)?u.href:''}catch{return ''}};
  const persist = () => sessionStorage.setItem(STORAGE,JSON.stringify(rows));
  const statusName = p => p.status!=='active' ? 'Ngừng bán' : Number(p.stock)<=5 ? 'Sắp hết hàng' : 'Đang bán';
  const statusClass = p => p.status!=='active'?'off':p.stock<=5?'low':'';
  mount.innerHTML = `
    <div class="ap-preview-note"><strong>CHẾ ĐỘ DEMO FRONTEND.</strong> Các nút Thêm / Sửa / Ngừng bán chỉ cập nhật dữ liệu giả lập trong phiên trình duyệt này. Không ghi PostgreSQL và không cập nhật cửa hàng. ${authorized?'Quyền admin đã xác thực, nhưng kết nối lưu sản phẩm chưa triển khai.':'Bạn chưa đăng nhập tài khoản admin; đây chỉ là giao diện thử nghiệm, không cấp quyền quản trị.'}</div>
    <div class="ap-head"><div><h2>Danh sách sản phẩm</h2><p class="mini-note">Tra cứu, lọc và quản lý bản nháp giao diện</p></div><button class="button button-dark" id="ap-add" type="button">+ Thêm sản phẩm (demo)</button></div>
    <div class="ap-stats"><div class="ap-stat"><span>Tổng sản phẩm</span><strong id="ap-stat-total">0</strong></div><div class="ap-stat"><span>Đang bán</span><strong id="ap-stat-active">0</strong></div><div class="ap-stat"><span>Tồn kho thấp (≤ 5)</span><strong id="ap-stat-low">0</strong></div></div>
    <div class="panel"><div class="ap-filters">
      <input id="ap-search" type="search" placeholder="Tìm tên, ID hoặc SKU..." aria-label="Tìm sản phẩm">
      <select id="ap-category" aria-label="Danh mục"><option value="">Mọi danh mục</option>${optionList(categories)}</select>
      <select id="ap-brand" aria-label="Thương hiệu"><option value="">Mọi thương hiệu</option>${optionList(brands)}</select>
      <select id="ap-status" aria-label="Trạng thái"><option value="">Mọi trạng thái</option><option value="active">Đang bán</option><option value="inactive">Ngừng bán</option><option value="low">Tồn kho thấp</option></select>
    </div>
    <div class="table-wrap"><table class="data-table ap-table"><thead><tr><th>Hình</th><th>Sản phẩm / SKU</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="ap-tbody"></tbody></table></div>
    <div class="ap-pager"><span id="ap-summary"></span><div class="ap-page-actions"><label for="ap-size">Hiện</label><select id="ap-size" class="ap-page-size"><option>5</option><option>10</option><option>20</option></select><button type="button" id="ap-prev">←</button><span id="ap-page-label"></span><button type="button" id="ap-next">→</button></div></div>
    <button id="ap-reset" type="button" class="button-sm">Khôi phục dữ liệu demo gốc</button>
    </div>
    <dialog id="ap-dialog" class="ap-modal" aria-labelledby="ap-dialog-title"><div class="ap-modal-head"><h2 id="ap-dialog-title">Thông tin sản phẩm</h2><button type="button" class="ap-close" id="ap-close" aria-label="Đóng">×</button></div>
      <form id="ap-form" class="ap-form"><div class="ap-form-grid">
        <div class="field wide"><label for="ap-name">Tên sản phẩm *</label><input id="ap-name" name="name" required maxlength="150"></div>
        <div class="field"><label for="ap-sku">SKU *</label><input id="ap-sku" name="sku" required maxlength="50"></div>
        <div class="field"><label for="ap-price">Giá bán (VNĐ) *</label><input id="ap-price" name="price" type="number" min="0" max="100000000000" step="1" required></div>
        <div class="field"><label for="ap-form-category">Danh mục *</label><input id="ap-form-category" name="category" list="ap-category-list" required maxlength="80"><datalist id="ap-category-list">${categories.map(c=>`<option value="${esc(c)}"></option>`).join('')}</datalist></div>
        <div class="field"><label for="ap-form-brand">Thương hiệu *</label><input id="ap-form-brand" name="brand" required maxlength="80"></div>
        <div class="field"><label for="ap-material">Chất liệu</label><input id="ap-material" name="material" maxlength="80"></div>
        <div class="field"><label for="ap-gem">Đá quý</label><input id="ap-gem" name="gem" maxlength="80"></div>
        <div class="field"><label for="ap-stock">Tồn kho *</label><input id="ap-stock" name="stock" type="number" min="0" max="1000000" step="1" required></div>
        <div class="field"><label for="ap-form-status">Trạng thái</label><select id="ap-form-status" name="status"><option value="active">Đang bán</option><option value="inactive">Ngừng bán</option></select></div>
        <div class="field wide"><label for="ap-image">URL ảnh (http/https)</label><input id="ap-image" name="image" type="url" maxlength="2000" placeholder="https://..."></div>
        <div class="field wide"><label for="ap-description">Mô tả</label><textarea id="ap-description" name="description" maxlength="1000"></textarea></div>
      </div><p class="ap-error" id="ap-error" hidden role="alert"></p><div class="ap-actions"><button type="button" class="button button-outline" id="ap-cancel">Hủy</button><button class="button button-dark" type="submit">Lưu bản demo</button></div></form>
    </dialog>`;
  const dlg=sel('ap-dialog'), form=sel('ap-form'); let editing=null;
  const notify = message => {const e=document.querySelector('#site-toast');if(e){e.textContent=message;setTimeout(()=>{if(e.textContent===message)e.textContent=''},3500)}};
  function filtered() {
    const q=state.q.toLocaleLowerCase('vi');
    return rows.filter(p => {
      const text=`${p.id} ${p.name} ${p.sku}`.toLocaleLowerCase('vi');
      return text.includes(q) && (!state.category||p.category===state.category) && (!state.brand||p.brand===state.brand) &&
        (!state.status || (state.status==='low'?p.status==='active'&&p.stock<=5:p.status===state.status));
    }).sort((a,b)=>b.id-a.id);
  }
  function draw(){
    sel('ap-stat-total').textContent=rows.length;
    sel('ap-stat-active').textContent=rows.filter(p=>p.status==='active').length;
    sel('ap-stat-low').textContent=rows.filter(p=>p.status==='active'&&p.stock<=5).length;
    const list=filtered(),pages=Math.max(1,Math.ceil(list.length/state.size));state.page=Math.min(state.page,pages);
    const begin=(state.page-1)*state.size;
    sel('ap-tbody').innerHTML=list.slice(begin,begin+state.size).map(p=>`<tr>
      <td>${cleanImage(p.image)?`<img loading="lazy" src="${esc(cleanImage(p.image))}" alt="${esc(p.name)}">`:'—'}</td>
      <td class="ap-name"><strong>${esc(p.name)}</strong><span class="ap-sku">ID ${p.id} · ${esc(p.sku)}</span></td>
      <td>${esc(p.category)}<span class="ap-sku">${esc(p.material)}</span></td><td>${money(p.price)}</td><td>${p.stock}</td>
      <td><span class="ap-status ${statusClass(p)}">${statusName(p)}</span></td>
      <td><div class="row-actions"><button type="button" class="button-sm" data-ap-edit="${p.id}">Sửa</button><button type="button" class="button-sm" data-ap-toggle="${p.id}">${p.status==='active'?'Ngừng bán':'Mở bán'}</button></div></td></tr>`).join('') || '<tr><td colspan="7" style="text-align:center;padding:45px">Không tìm thấy sản phẩm phù hợp.</td></tr>';
    sel('ap-summary').textContent=`${list.length?begin+1:0}–${Math.min(begin+state.size,list.length)} / ${list.length} sản phẩm`;
    sel('ap-page-label').textContent=`Trang ${state.page}/${pages}`;sel('ap-prev').disabled=state.page===1;sel('ap-next').disabled=state.page===pages;
  }
  function openForm(id=null){
    editing=id;
    const p=id===null?null:rows.find(x=>x.id===id);
    form.reset();sel('ap-error').hidden=true;
    for(const key of ['name','sku','category','brand','material','gem','price','stock','image','description','status']) {
      const field=form.elements.namedItem(key);if(field && p)field.value=p[key]??'';
    }
    if(!p){form.elements.namedItem('status').value='active';form.elements.namedItem('brand').value='LUMIÈRE';}
    sel('ap-dialog-title').textContent=p?`Sửa sản phẩm #${p.id} (demo)`:'Thêm sản phẩm (demo)';dlg.showModal();form.elements.namedItem('name').focus();
  }
  sel('ap-add').onclick=()=>openForm();sel('ap-close').onclick=()=>dlg.close();sel('ap-cancel').onclick=()=>dlg.close();
  for(const [id,key] of [['ap-search','q'],['ap-category','category'],['ap-brand','brand'],['ap-status','status']])sel(id).addEventListener('input',e=>{state[key]=e.target.value;state.page=1;draw()});
  sel('ap-size').onchange=e=>{state.size=Number(e.target.value);state.page=1;draw()};
  sel('ap-prev').onclick=()=>{state.page--;draw()};sel('ap-next').onclick=()=>{state.page++;draw()};
  sel('ap-reset').onclick=()=>{if(confirm('Khôi phục toàn bộ dữ liệu xem trước? Các sửa đổi trong phiên này sẽ mất.')){rows=structuredClone(base);sessionStorage.removeItem(STORAGE);state.page=1;draw();notify('Đã khôi phục dữ liệu demo.')}};
  sel('ap-tbody').addEventListener('click',e=>{
    const edit=e.target.closest('[data-ap-edit]');const toggle=e.target.closest('[data-ap-toggle]');
    if(edit)openForm(Number(edit.dataset.apEdit));
    if(toggle){const p=rows.find(x=>x.id===Number(toggle.dataset.apToggle));if(!p)return;p.status=p.status==='active'?'inactive':'active';persist();draw();notify('Đã cập nhật trạng thái bản demo.');}
  });
  form.addEventListener('submit',e=>{
    e.preventDefault();const d=new FormData(form);const val=k=>String(d.get(k)||'').trim();
    const obj={name:val('name'),sku:val('sku'),category:val('category'),brand:val('brand'),material:val('material'),gem:val('gem'),price:Number(val('price')),stock:Number(val('stock')),image:val('image'),description:val('description'),status:val('status')};
    const errors=[];
    if(!obj.name||!obj.sku||!obj.category||!obj.brand)errors.push('Vui lòng điền các trường bắt buộc.');
    if(rows.some(p=>p.sku.toLocaleLowerCase()===obj.sku.toLocaleLowerCase()&&p.id!==editing))errors.push('SKU đã tồn tại trong bản demo.');
    if(!Number.isSafeInteger(obj.price)||obj.price<0)errors.push('Giá phải là số nguyên không âm.');
    if(!Number.isSafeInteger(obj.stock)||obj.stock<0)errors.push('Tồn kho phải là số nguyên không âm.');
    if(obj.image&&!cleanImage(obj.image))errors.push('Ảnh phải là URL http hoặc https hợp lệ.');
    if(!['active','inactive'].includes(obj.status))errors.push('Trạng thái không hợp lệ.');
    if(errors.length){sel('ap-error').textContent=errors.join(' ');sel('ap-error').hidden=false;return;}
    if(editing===null){obj.id=Math.max(0,...rows.map(p=>p.id))+1;rows.unshift(obj)}else{const index=rows.findIndex(p=>p.id===editing);if(index<0)return;rows[index]={...rows[index],...obj}}
    try{persist()}catch{notify('Bộ nhớ trình duyệt đã đầy; thay đổi chỉ tồn tại đến khi tải lại trang.')}
    dlg.close();draw();notify('Đã lưu bản demo (không ghi cơ sở dữ liệu).');
  });
  draw();
};
