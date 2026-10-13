"use strict";
/* Frontend-only category and brand management. Session-scoped changes only. */
window.LUMIERE_ADMIN_TAXONOMY = function ({mount, kind, products, esc}) {
  const isCategory = kind === 'categories';
  const label = isCategory ? 'danh mục' : 'thương hiệu';
  const title = isCategory ? 'Danh mục sản phẩm' : 'Thương hiệu trang sức';
  const KEY = `lumiere_admin_${kind}_preview_v1`;
  const names = isCategory
    ? [...new Set(products.map(p => p.category).filter(Boolean))]
    : [...new Set([...products.map(p => p.brand).filter(Boolean), 'LUMIÈRE'])];
  const baseline = names.map((name, i) => ({ id: i + 1, name, code: `${isCategory ? 'CAT' : 'BR'}-${String(i + 1).padStart(3, '0')}`, description: '', status: 'active' }));
  let rows;
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY));
    rows = Array.isArray(stored) ? stored : structuredClone(baseline);
  } catch { rows = structuredClone(baseline); }
  let state = { q:'', status:'', page:1, size:5 };
  const $ = selector => mount.querySelector(selector);
  const counts = name => products.filter(p => (isCategory ? p.category : p.brand) === name).length;
  const save = () => sessionStorage.setItem(KEY, JSON.stringify(rows));
  const alertText = (text, bad=false) => { const el=$('#tax-notice'); el.textContent=text; el.className='tax-notice '+(bad?'error':'success'); el.hidden=false; };
  const text = value => String(value ?? '').trim();
  const unique = (name, code, id) => rows.some(x => x.id !== id && (x.name.toLocaleLowerCase('vi') === name.toLocaleLowerCase('vi') || x.code.toLocaleLowerCase('vi') === code.toLocaleLowerCase('vi')));
  mount.innerHTML = `
    <div class="demo-note"><strong>CHẾ ĐỘ DEMO FRONTEND.</strong> Các thay đổi ${label} chỉ lưu trong phiên trình duyệt, không ghi vào PostgreSQL. API quản trị phải xác minh quyền admin.</div>
    <div class="tax-head"><div><h2>${title}</h2><p class="mini-note">Quản lý dữ liệu nền tảng cho sản phẩm LUMIÈRE.</p></div><button type="button" class="button button-dark" id="tax-add">+ Thêm ${label}</button></div>
    <div class="tax-stats"><div class="tax-stat"><span>Tổng ${label}</span><strong id="tax-total"></strong></div><div class="tax-stat"><span>Đang sử dụng</span><strong id="tax-active"></strong></div><div class="tax-stat"><span>Ngừng sử dụng</span><strong id="tax-inactive"></strong></div></div>
    <section class="panel tax-panel"><div class="tax-filters"><label class="tax-search"><span class="sr-only">Tìm kiếm</span><input id="tax-query" type="search" placeholder="Tìm tên hoặc mã ${label}..." /></label><label><span class="sr-only">Trạng thái</span><select id="tax-filter"><option value="">Mọi trạng thái</option><option value="active">Đang sử dụng</option><option value="inactive">Ngừng sử dụng</option></select></label><label><span class="sr-only">Số hàng</span><select id="tax-page-size"><option value="5">5 / trang</option><option value="10">10 / trang</option><option value="20">20 / trang</option></select></label></div>
      <div class="tax-notice" id="tax-notice" role="status" aria-live="polite" hidden></div>
      <div class="table-wrap"><table class="data-table tax-table"><thead><tr><th>Mã</th><th>Tên ${label}</th><th>Mô tả</th><th>Số sản phẩm (demo)</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="tax-body"></tbody></table></div>
      <div class="tax-pagination"><span id="tax-count"></span><div id="tax-pages" class="tax-page-buttons"></div></div>
    </section>
    <div class="tax-modal-backdrop" id="tax-backdrop" hidden><section class="tax-modal" role="dialog" aria-modal="true" aria-labelledby="tax-modal-title"><div class="tax-modal-head"><h2 id="tax-modal-title">Thêm ${label}</h2><button type="button" id="tax-close" aria-label="Đóng">×</button></div><form id="tax-form"><input type="hidden" id="tax-id"><div class="field"><label for="tax-name">Tên ${label} *</label><input id="tax-name" maxlength="100" required></div><div class="field"><label for="tax-code">Mã ${label} *</label><input id="tax-code" maxlength="30" pattern="[A-Za-z0-9_-]+" required><small>Chữ cái, chữ số, _ hoặc -; không trùng.</small></div><div class="field"><label for="tax-description">Mô tả</label><textarea id="tax-description" maxlength="500"></textarea></div><div class="field"><label for="tax-status">Trạng thái</label><select id="tax-status"><option value="active">Đang sử dụng</option><option value="inactive">Ngừng sử dụng</option></select></div><div class="tax-modal-actions"><button type="button" id="tax-cancel" class="button button-outline">HỦY</button><button class="button button-dark" type="submit">LƯU ${label.toUpperCase()}</button></div></form></section></div>`;

  function draw() {
    $('#tax-total').textContent=rows.length;
    $('#tax-active').textContent=rows.filter(x=>x.status==='active').length;
    $('#tax-inactive').textContent=rows.filter(x=>x.status==='inactive').length;
    const q=state.q.toLocaleLowerCase('vi');
    const filtered=rows.filter(x=>(x.name+' '+x.code).toLocaleLowerCase('vi').includes(q)&&(!state.status||x.status===state.status));
    const totalPages=Math.max(1,Math.ceil(filtered.length/state.size));
    state.page=Math.min(Math.max(1,state.page),totalPages);
    const pageRows=filtered.slice((state.page-1)*state.size,state.page*state.size);
    $('#tax-body').innerHTML=pageRows.length?pageRows.map(row=>`<tr><td><code>${esc(row.code)}</code></td><td><strong>${esc(row.name)}</strong></td><td>${esc(row.description)||'—'}</td><td>${counts(row.name)}</td><td><span class="tax-status ${row.status==='active'?'active':'inactive'}">${row.status==='active'?'Đang sử dụng':'Ngừng sử dụng'}</span></td><td><div class="row-actions"><button type="button" class="button-sm" data-tax-edit="${row.id}">Sửa</button><button type="button" class="button-sm" data-tax-toggle="${row.id}">${row.status==='active'?'Ngừng dùng':'Mở lại'}</button></div></td></tr>`).join(''):`<tr><td colspan="6" class="tax-empty">Không tìm thấy ${label} phù hợp.</td></tr>`;
    $('#tax-count').textContent=`${filtered.length} kết quả · Trang ${state.page}/${totalPages}`;
    const controls=$('#tax-pages'); controls.replaceChildren();
    for(let p=1;p<=totalPages;p++){const btn=document.createElement('button');btn.type='button';btn.textContent=p;btn.className='tax-page'+(p===state.page?' active':'');btn.setAttribute('aria-label',`Trang ${p}`);btn.setAttribute('aria-current',p===state.page?'page':'false');btn.onclick=()=>{state.page=p;draw();};controls.appendChild(btn);}
  }
  function openModal(row=null) {
    $('#tax-form').reset();
    $('#tax-id').value=row?.id ?? '';
    $('#tax-name').value=row?.name ?? '';
    $('#tax-code').value=row?.code ?? '';
    $('#tax-description').value=row?.description ?? '';
    $('#tax-status').value=row?.status ?? 'active';
    $('#tax-modal-title').textContent=(row?'Sửa ':'Thêm ')+label;
    $('#tax-backdrop').hidden=false;
    $('#tax-name').focus();
  }
  function closeModal(){$('#tax-backdrop').hidden=true;}
  $('#tax-add').onclick=()=>openModal();
  $('#tax-close').onclick=closeModal;
  $('#tax-cancel').onclick=closeModal;
  $('#tax-backdrop').addEventListener('click',e=>{if(e.target===$('#tax-backdrop'))closeModal();});
  mount.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#tax-backdrop').hidden)closeModal();});
  $('#tax-query').addEventListener('input',e=>{state.q=e.target.value.trim();state.page=1;draw();});
  $('#tax-filter').addEventListener('change',e=>{state.status=e.target.value;state.page=1;draw();});
  $('#tax-page-size').addEventListener('change',e=>{state.size=Number(e.target.value);state.page=1;draw();});
  $('#tax-body').addEventListener('click',e=>{
    const edit=e.target.closest('[data-tax-edit]');
    const toggle=e.target.closest('[data-tax-toggle]');
    if(edit){openModal(rows.find(r=>r.id===Number(edit.dataset.taxEdit)));}
    if(toggle){const row=rows.find(r=>r.id===Number(toggle.dataset.taxToggle));if(!row)return;row.status=row.status==='active'?'inactive':'active';save();draw();alertText(`Đã cập nhật trạng thái ${label} trong bản demo. ${counts(row.name)?'Lưu ý: sản phẩm demo liên quan không bị thay đổi.':''}`);}
  });
  $('#tax-form').addEventListener('submit',e=>{
    e.preventDefault();
    const id=Number($('#tax-id').value)||null;
    const name=text($('#tax-name').value),code=text($('#tax-code').value).toUpperCase(),description=text($('#tax-description').value),status=$('#tax-status').value;
    if(name.length<2||name.length>100){alertText('Tên cần từ 2 đến 100 ký tự.',true);return;}
    if(!/^[A-Z0-9_-]{2,30}$/.test(code)){alertText('Mã phải từ 2–30 ký tự và chỉ gồm chữ, số, _ hoặc -.',true);return;}
    if(unique(name,code,id)){alertText('Tên hoặc mã đã tồn tại. Vui lòng chọn giá trị khác.',true);return;}
    if(id){const row=rows.find(x=>x.id===id);if(!row)return;Object.assign(row,{name,code,description,status});}
    else rows.unshift({id:Math.max(0,...rows.map(x=>x.id))+1,name,code,description,status});
    save();state.page=1;closeModal();draw();alertText(`Đã ${id?'cập nhật':'thêm'} ${label} trong bản demo. Chưa ghi cơ sở dữ liệu.`);
  });
  draw();
};
