"use strict";
/* LUMIÈRE Taxonomy — read-only Business API; no fake database mutations. */
window.LUMIERE_ADMIN_TAXONOMY = function ({mount, kind, products = []}) {
  if (!mount) return;
  const isCategory = kind === 'categories';
  const singular = isCategory ? 'danh mục' : 'thương hiệu';
  const title = isCategory ? 'Danh mục sản phẩm' : 'Thương hiệu trang sức';
  const api = window.LUMIERE_API;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
  const listOf = value => Array.isArray(value) ? value : Array.isArray(value?.items) ? value.items : Array.isArray(value?.data) ? value.data : Array.isArray(value?.results) ? value.results : null;
  const state = {q:'', usage:'', page:1, size:5};
  let rows=[], loading=true, error='', countsReady=false, productCount=0;
  const $ = id => mount.querySelector('#'+id);
  mount.innerHTML = `
    <div class="demo-note">DỮ LIỆU THẬT TỪ BUSINESS API / POSTGRESQL. Hiện Backend chỉ cung cấp GET /categories và GET /brands; chưa hỗ trợ thêm, sửa, ngừng dùng hoặc xóa ${singular}. Trang này chỉ xem, không ghi cơ sở dữ liệu.</div>
    <div class="tax-head"><div><h2>${title}</h2><p class="mini-note">Danh sách ${singular} từ Business API.</p></div><button class="button button-outline" id="tax-refresh" type="button">Làm mới</button></div>
    <div class="tax-stats"><div class="tax-stat"><span>Tổng ${singular}</span><strong id="tax-total">—</strong></div><div class="tax-stat"><span>Có sản phẩm</span><strong id="tax-active">—</strong></div><div class="tax-stat"><span>Chưa gán sản phẩm</span><strong id="tax-inactive">—</strong></div></div>
    <section class="panel tax-panel"><div class="tax-filters"><label class="tax-search"><span class="sr-only">Tìm kiếm</span><input id="tax-query" type="search" placeholder="Tìm tên hoặc ID ${singular}..."></label><label><span class="sr-only">Lọc</span><select id="tax-filter"><option value="">Mọi ${singular}</option><option value="used">Có sản phẩm</option><option value="unused">Chưa gán sản phẩm</option></select></label><label><span class="sr-only">Số hàng</span><select id="tax-page-size"><option value="5">5 / trang</option><option value="10">10 / trang</option><option value="20">20 / trang</option></select></label></div>
    <div class="tax-notice" id="tax-notice" role="status" aria-live="polite" hidden></div>
    <div class="table-wrap"><table class="data-table tax-table"><thead><tr><th>ID</th><th>Tên ${singular}</th><th>Số sản phẩm</th><th>Tình trạng sử dụng</th><th>Thao tác</th></tr></thead><tbody id="tax-body"></tbody></table></div>
    <div class="tax-pagination"><span id="tax-count"></span><div id="tax-pages" class="tax-page-buttons"></div></div></section>`;
  function notice(message, bad=false) {
    const el=$('tax-notice'); el.textContent=message; el.hidden=!message;
    el.className='tax-notice '+(bad?'error':'success');
  }
  function draw() {
    $('tax-total').textContent=loading?'…':rows.length;
    $('tax-active').textContent=!countsReady?'—':rows.filter(x=>x.count>0).length;
    $('tax-inactive').textContent=!countsReady?'—':rows.filter(x=>x.count===0).length;
    const filtered=rows.filter(x=>norm(x.name+' '+x.id).includes(norm(state.q)) &&
      (!countsReady || !state.usage || (state.usage==='used'?x.count>0:x.count===0)));
    const pages=Math.max(1,Math.ceil(filtered.length/state.size));
    state.page=Math.min(Math.max(1,state.page),pages);
    const shown=filtered.slice((state.page-1)*state.size,state.page*state.size);
    $('tax-body').innerHTML=loading?'<tr><td colspan="5">Đang tải dữ liệu Business API…</td></tr>':error?`<tr><td colspan="5">${esc(error)}</td></tr>`:
      shown.length?shown.map(row=>`<tr><td><code>${esc(row.id)}</code></td><td><strong>${esc(row.name)}</strong></td><td>${countsReady?row.count:'—'}</td><td>${countsReady?`<span class="tax-status ${row.count?'active':'inactive'}">${row.count?'Có sản phẩm':'Chưa gán'}</span>`:'Chưa có thống kê'}</td><td><span class="mini-note">Chỉ xem</span></td></tr>`).join(''):
      `<tr><td colspan="5" class="tax-empty">Không tìm thấy ${singular} phù hợp.</td></tr>`;
    $('tax-count').textContent=loading?'Đang tải…':`${filtered.length} kết quả · Trang ${state.page}/${pages}`;
    const pager=$('tax-pages');pager.replaceChildren();
    const start=Math.max(1,state.page-2),end=Math.min(pages,start+4);
    for(let i=start;i<=end;i++) {const b=document.createElement('button');b.type='button';b.textContent=i;b.className='tax-page'+(i===state.page?' active':'');b.setAttribute('aria-current',i===state.page?'page':'false');b.onclick=()=>{state.page=i;draw();};pager.append(b);}
  }
  async function fetchAllProducts() {
    if(!api?.products) throw Error('Thiếu Products API');
    const first=await api.products(1,100);
    const list=listOf(first);
    if(!list) throw Error('Products API không có danh sách items hợp lệ.');
    let found=[...list];
    const total=Number(first?.total);
    if(Number.isFinite(total) && total>=0 && total<=100000) {
      const pageSize=Number(first?.page_size)||100;
      const n=Math.ceil(total/pageSize);
      for(let page=2;page<=n;page++){
        const response=await api.products(page,pageSize);
        const next=listOf(response);
        if(!next) throw Error('Không đọc được trang sản phẩm '+page);
        found.push(...next);
      }
    } else if(list.length===100) {
      for(let page=2;page<=100;page++){
        const response=await api.products(page,100);
        const next=listOf(response);
        if(!next) throw Error('Không đọc được trang sản phẩm '+page);
        found.push(...next);
        if(next.length<100) break;
      }
    }
    return found;
  }
  async function load() {
    loading=true;error='';countsReady=false;rows=[];draw();notice('');
    try {
      if(!api?.[kind]) throw Error('Chưa có LUMIERE_API.'+kind+'()');
      const raw=await api[kind]();
      const arr=listOf(raw);
      if(!arr) throw Error('API /'+kind+' trả dữ liệu không đúng dạng danh sách.');
      rows=arr.map(x=>({id:x.id,name:String(x.name??''),count:0})).filter(x=>x.id!=null && x.name);
      error='';loading=false;draw();
      try {
        const all=await fetchAllProducts();
        productCount=all.length;
        const counter=new Map();
        for(const p of all){
          const field=p[isCategory?'category':'brand'];
          const id=field && typeof field==='object' ? field.id : p[isCategory?'category_id':'brand_id'];
          const name=field && typeof field==='object' ? field.name : field;
          if(id!=null) counter.set('id:'+id,(counter.get('id:'+id)||0)+1);
          else if(name) counter.set('name:'+norm(name),(counter.get('name:'+norm(name))||0)+1);
        }
        for(const row of rows)row.count=counter.get('id:'+row.id)??counter.get('name:'+norm(row.name))??0;
        countsReady=true;
        notice(`Đã tải ${rows.length} ${singular} và đối chiếu ${productCount} sản phẩm từ API.`);
      } catch(e) {
        notice('Đã tải danh sách thật. Chưa tính được số sản phẩm: '+e.message,true);
      }
      draw();
    } catch(e){loading=false;error=e.message||String(e);notice('Không tải được '+singular+': '+error,true);draw();}
  }
  $('tax-query').addEventListener('input',e=>{state.q=e.target.value;state.page=1;draw();});
  $('tax-filter').addEventListener('change',e=>{state.usage=e.target.value;state.page=1;draw();});
  $('tax-page-size').addEventListener('change',e=>{state.size=Number(e.target.value);state.page=1;draw();});
  $('tax-refresh').onclick=load;
  load();
};
