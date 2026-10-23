"use strict";
/* LUMIÈRE Admin Products: read-only catalog + supported Admin PATCH (name/sale_price).
   Never simulate unsupported Create/Archive/Delete operations. */
window.LUMIERE_ADMIN_PRODUCTS = function ({mount, money, esc}) {
  if (!mount) return;
  const api = window.LUMIERE_API;
  const escape = esc || (x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
  const currency = money || (n => Number(n || 0).toLocaleString('vi-VN')+' ₫');
  const state = {rows:[], page:1, size:10, q:'', category:'', brand:'', status:'', busy:false, authorized:false};
  const $ = id => mount.querySelector('#'+id);
  const clean = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const textOf = v => typeof v === 'object' && v !== null ? String(v.name ?? v.title ?? '') : String(v ?? '');
  const asNumber = v => (v == null || v === '' ? NaN : Number(v));
  const normalize = p => ({
    id:Number(p.id), name:String(p.name ?? ''), sku:String(p.sku ?? ''),
    category:textOf(p.category_name ?? p.category), brand:textOf(p.brand_name ?? p.brand),
    price:asNumber(p.price_vnd ?? p.sale_price ?? p.price), stock:asNumber(p.stock),
    image:String(p.image_url ?? p.image ?? ''), // API hiện không trả trường ảnh: để trống, không tạo URL giả
    status:String(p.status ?? (p.is_active===false?'inactive':'active'))
  });
  const urlImage = source => {try {const u=new URL(source,location.href);return ['http:','https:'].includes(u.protocol)?u.href:'';}catch{return ''}};
  const statusLabel = p => p.status==='inactive'?'Ngừng bán':p.stock===0?'Hết hàng':p.stock<=5?'Sắp hết':'Đang bán';
  mount.innerHTML = `<div class="ap-head"><div><h2>Danh sách sản phẩm</h2><p class="mini-note">Dữ liệu từ Business API / PostgreSQL</p></div><button class="button button-outline" type="button" id="ap-refresh">Làm mới</button></div>
    <p id="ap-message" class="mini-note" role="status">Đang tải dữ liệu sản phẩm...</p>
    <p class="mini-note">Chỉ hỗ trợ sửa tên và giá bán qua API hiện có. Thêm sản phẩm và Ngừng bán/Mở bán chưa được Backend cung cấp.</p>
    <div class="ap-stats"><div class="ap-stat"><span>Tổng sản phẩm</span><strong id="ap-stat-total">0</strong></div><div class="ap-stat"><span>Còn hàng</span><strong id="ap-stat-active">0</strong></div><div class="ap-stat"><span>Tồn kho thấp (1–5)</span><strong id="ap-stat-low">0</strong></div></div>
    <div class="panel"><div class="ap-filters">
      <input id="ap-search" type="search" placeholder="Tìm tên, ID hoặc SKU..." aria-label="Tìm sản phẩm">
      <select id="ap-category" aria-label="Danh mục"><option value="">Mọi danh mục</option></select>
      <select id="ap-brand" aria-label="Thương hiệu"><option value="">Mọi thương hiệu</option></select>
      <select id="ap-status" aria-label="Tồn kho"><option value="">Mọi tình trạng</option><option value="in">Còn hàng</option><option value="low">Sắp hết (1–5)</option><option value="out">Hết hàng</option></select>
    </div><div class="table-wrap"><table class="data-table ap-table"><thead><tr><th>Hình</th><th>Sản phẩm / SKU</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="ap-tbody"></tbody></table></div>
    <div class="ap-pager"><span id="ap-summary"></span><div class="ap-page-actions"><label for="ap-size">Hiện</label><select id="ap-size"><option>5</option><option selected>10</option><option>20</option></select><button id="ap-prev" type="button">←</button><span id="ap-page-label"></span><button id="ap-next" type="button">→</button></div></div></div>
    <dialog id="ap-dialog" class="ap-modal" aria-labelledby="ap-dialog-title"><div class="ap-modal-head"><h2 id="ap-dialog-title">Sửa sản phẩm</h2><button type="button" class="ap-close" id="ap-close" aria-label="Đóng">×</button></div>
    <form id="ap-form" class="ap-form"><div class="ap-form-grid"><div class="field wide"><label for="ap-name">Tên sản phẩm *</label><input id="ap-name" required maxlength="255"></div><div class="field"><label for="ap-price">Giá bán (VNĐ) *</label><input id="ap-price" type="number" min="0" step="0.01" required></div></div><p class="mini-note">SKU, danh mục, chất liệu và tồn kho không thay đổi trong biểu mẫu này. Tồn kho cập nhật ở mục Staff Inventory.</p><p id="ap-error" class="ap-error" hidden role="alert"></p><div class="ap-actions"><button class="button button-outline" id="ap-cancel" type="button">Hủy</button><button class="button button-dark" id="ap-submit" type="submit">LƯU VÀO POSTGRESQL</button></div></form></dialog>`;
  const show = (msg, error=false) => {const e=$('ap-message'); e.textContent=msg; e.style.color=error?'#9c3028':''};
  function refreshFilters(){
    for(const [id,values] of [['ap-category',state.rows.map(p=>p.category)],['ap-brand',state.rows.map(p=>p.brand)]]){
      const select=$(id),current=select.value;
      select.innerHTML='<option value="">Mọi '+(id==='ap-category'?'danh mục':'thương hiệu')+'</option>'+[...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'vi')).map(v=>`<option value="${escape(v)}">${escape(v)}</option>`).join('');
      select.value=current;
    }
  }
  function filtered(){return state.rows.filter(p=>{
    if(state.q&&!clean(`${p.id} ${p.name} ${p.sku}`).includes(clean(state.q)))return false;
    if(state.category&&p.category!==state.category)return false;
    if(state.brand&&p.brand!==state.brand)return false;
    if(state.status==='in'&&p.stock<=5)return false;
    if(state.status==='low'&&!(p.stock>0&&p.stock<=5))return false;
    if(state.status==='out'&&p.stock!==0)return false;
    return true;
  }).sort((a,b)=>b.id-a.id)}
  function draw(){
    const all=state.rows;
    $('ap-stat-total').textContent=all.length;
    $('ap-stat-active').textContent=all.filter(p=>p.stock>0).length;
    $('ap-stat-low').textContent=all.filter(p=>p.stock>0&&p.stock<=5).length;
    const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/state.size));state.page=Math.min(state.page,pages);
    const start=(state.page-1)*state.size;
    $('ap-tbody').innerHTML=rows.slice(start,start+state.size).map(p=>`<tr>
      <td>${urlImage(p.image)?`<img loading="lazy" src="${escape(urlImage(p.image))}" alt="${escape(p.name)}">`:'—'}</td>
      <td class="ap-name"><strong>${escape(p.name)}</strong><span class="ap-sku">ID ${p.id} · ${escape(p.sku)}</span></td>
      <td>${escape(p.category)}</td><td>${Number.isFinite(p.price)?currency(p.price):'—'}</td><td>${p.stock}</td>
      <td><span class="ap-status ${p.stock===0?'off':p.stock<=5?'low':''}">${escape(statusLabel(p))}</span></td>
      <td><button type="button" class="button-sm" data-ap-edit="${p.id}" ${state.busy||!state.authorized?'disabled':''}>Sửa tên / giá</button></td></tr>`).join('') || '<tr><td colspan="7" style="text-align:center;padding:35px">Không có sản phẩm phù hợp.</td></tr>';
    $('ap-summary').textContent=`${rows.length?start+1:0}–${Math.min(start+state.size,rows.length)} / ${rows.length} sản phẩm`;
    $('ap-page-label').textContent=`Trang ${state.page}/${pages}`;$('ap-prev').disabled=state.page<=1;$('ap-next').disabled=state.page>=pages;
  }
  async function load(){
    if(state.busy)return;state.busy=true;show('Đang tải sản phẩm từ Backend...');
    try{
      if(!api)throw Error('Không tìm thấy LUMIERE_API. Kiểm tra trang đã nạp api.js.');
      const me=await api.me();
      if(me.role!=='admin')throw Error('Chỉ tài khoản Admin được quản lý sản phẩm.');
      state.authorized=true;
      let all=[],page=1,total=Infinity;
      while(all.length<total && page<=100){
        const result=await api.products(page,100);
        const batch=Array.isArray(result)?result:(result.items ?? result.products ?? []);
        if(!Array.isArray(batch))throw Error('Products API trả về dữ liệu không hợp lệ.');
        all.push(...batch);
        total=Number(result.total ?? (batch.length<100?all.length:Infinity));
        if(!batch.length||batch.length<100)break;
        page++;
      }
      state.rows=all.map(normalize).filter(x=>Number.isSafeInteger(x.id));
      state.page=1;refreshFilters();draw();show(`Đã tải ${state.rows.length} sản phẩm từ PostgreSQL.`);
    }catch(e){state.rows=[];show(`Không tải được sản phẩm: ${e.message}`,true)}finally{state.busy=false;draw()}
  }
  let editing=null, expected=null;
  async function openEdit(id){
    if(state.busy)return;state.busy=true;
    try{
      const detail=await api.request('/admin/products/'+encodeURIComponent(id));
      const p=detail.product ?? detail;
      if(!p||p.price_vnd==null||!Number.isFinite(Number(p.price_vnd)))throw Error('Không đọc được price_vnd hiện tại của sản phẩm.');
      editing=id;
      expected=String(p.price_vnd);
      $('ap-name').value=String(p.name ?? '');$('ap-price').value=expected;
      $('ap-dialog-title').textContent=`Sửa sản phẩm #${id}`;$('ap-error').hidden=true;
      $('ap-dialog').showModal();
    }catch(e){show(`Không thể mở chi tiết: ${e.message}`,true)}finally{state.busy=false}
  }
  $('ap-form').addEventListener('submit',async e=>{
    e.preventDefault();if(state.busy||editing===null)return;
    const name=$('ap-name').value.trim(),value=$('ap-price').value;
    const price=Number(value),current=Number(expected);
    if(!name||name.length>255||!Number.isFinite(price)||price<0||!Number.isFinite(current)){
      $('ap-error').textContent='Tên hoặc giá bán không hợp lệ.';$('ap-error').hidden=false;return;
    }
    if(!confirm(`Lưu thay đổi của sản phẩm ID ${editing} vào PostgreSQL?`))return;
    state.busy=true;$('ap-submit').disabled=true;
    try{
      const payload={name,sale_price:value,expected_sale_price:expected};
      await api.request('/admin/products/'+encodeURIComponent(editing),{method:'PATCH',body:JSON.stringify(payload)});
      $('ap-dialog').close();editing=null;
      // Reload authoritative data; no local fake success.
      state.busy=false;await load();show('Đã lưu sản phẩm vào PostgreSQL và tải lại danh sách.');
    }catch(error){$('ap-error').textContent=`Không thể lưu: ${error.message}. Hãy tải lại dữ liệu trước khi thử lại.`;$('ap-error').hidden=false;}
    finally{state.busy=false;$('ap-submit').disabled=false}
  });
  $('ap-tbody').addEventListener('click',e=>{const btn=e.target.closest('[data-ap-edit]');if(btn)openEdit(Number(btn.dataset.apEdit))});
  for(const [id,key] of [['ap-search','q'],['ap-category','category'],['ap-brand','brand'],['ap-status','status']])$(id).addEventListener('input',e=>{state[key]=e.target.value;state.page=1;draw()});
  $('ap-size').onchange=e=>{state.size=Number(e.target.value);state.page=1;draw()};
  $('ap-prev').onclick=()=>{if(state.page>1){state.page--;draw()}};
  $('ap-next').onclick=()=>{state.page++;draw()};
  $('ap-refresh').onclick=()=>load();
  $('ap-close').onclick=()=>{$('ap-dialog').close()};$('ap-cancel').onclick=()=>{$('ap-dialog').close()};
  draw();load();
};
