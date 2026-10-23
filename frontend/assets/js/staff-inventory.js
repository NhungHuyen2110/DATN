"use strict";
/* LUMIÈRE Staff inventory — source of truth is PostgreSQL via Business API. */
(() => {
  const esc = x => String(x ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = x => String(x??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').toLowerCase();
  const fmt = x => Number(x||0).toLocaleString('vi-VN');
  const status = n => n===0?'Hết hàng':n<=5?'Sắp hết':'Còn hàng';
  const statusClass = n => n===0?'out':n<=5?'low':'ok';
  const api = () => window.LUMIERE_API;
  const msg = e => String(e?.message || e || 'Lỗi không xác định');
  window.LUMIERE_STAFF_INVENTORY = ({mount}) => {
    let products=[],query='',filter='all',limit=10,page=1,busy=false;
    const $ = id => mount.querySelector('#'+id);
    const inform=(message,failed=true)=>{const el=$('inv-feedback');if(el){el.textContent=message;el.hidden=false;el.style.color=failed?'#9f302b':'#23623b';}};
    async function load(){
      mount.innerHTML='<div class="panel">Đang tải tồn kho thật từ Business API / PostgreSQL…</div>';
      try {
        if(!api()) throw Error('Không tìm thấy api.js.');
        const user=await api().me();
        if(!['staff','admin'].includes(user.role)) throw Error('Tài khoản này không có quyền Staff/Admin.');
        const records=[];
        // All pages, not static demo catalogue. API products is paged.
        for(let p=1;p<=100;p++){
          const response=await api().products(p,100);
          const batch=Array.isArray(response)?response:response.items;
          if(!Array.isArray(batch))throw Error('API /products không trả về danh sách items hợp lệ.');
          records.push(...batch);
          const total=Number(response.total);
          if((Number.isFinite(total)&&records.length>=total)||batch.length<100)break;
          if(p===100)throw Error('Vượt giới hạn phân trang khi tải tồn kho.');
        }
        products=records.map(p=>({...p,id:Number(p.id),stock:Number(p.stock)}))
          .filter(p=>Number.isSafeInteger(p.id)&&Number.isSafeInteger(p.stock)&&p.stock>=0);
        page=1;render();
      } catch(e){
        mount.innerHTML=`<section class="panel"><h2>Không tải được tồn kho</h2><p>${esc(msg(e))}</p><p>Hãy kiểm tra Backend cổng 8001 và đăng nhập bằng tài khoản Staff/Admin.</p><button id="inv-retry" class="button button-outline" type="button">Thử lại</button></section>`;
        $('inv-retry').onclick=load;
      }
    }
    function filtered(){return products.filter(p=>norm([p.id,p.name,p.sku,p.category,p.material].join(' ')).includes(norm(query))&&(filter==='all'||statusClass(p.stock)===filter));}
    function render(){
      const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/limit));page=Math.min(page,pages);
      const shown=rows.slice((page-1)*limit,page*limit),numbers=products.map(p=>p.stock);
      mount.innerHTML=`<section class="inv-root">
       <div class="inv-heading"><div><h2>Kiểm tra tồn kho</h2><p class="mini-note">Tồn kho thực từ Business API · PostgreSQL. Điều chỉnh dùng kiểm tra tồn kỳ vọng để tránh ghi đè cập nhật khác.</p></div><button id="inv-reload" type="button" class="button button-outline">Làm mới</button></div>
       <p id="inv-feedback" class="inv-error" role="status" hidden></p>
       <div class="inv-stats">${[['Mã sản phẩm',products.length],['Tổng đơn vị tồn',fmt(numbers.reduce((a,b)=>a+b,0))],['Sắp hết (1–5)',numbers.filter(n=>n>0&&n<=5).length],['Hết hàng',numbers.filter(n=>n===0).length]].map(([k,v])=>`<div class="inv-stat"><span>${k}</span><strong>${v}</strong></div>`).join('')}</div>
       <div class="panel inv-panel"><div class="inv-filters"><label class="field">Tìm sản phẩm<input id="inv-search" type="search" placeholder="Tên, mã sản phẩm / ID…" value="${esc(query)}" autocomplete="off"></label><label class="field">Tình trạng<select id="inv-filter">${[['all','Tất cả'],['ok','Còn hàng (> 5)'],['low','Sắp hết (1–5)'],['out','Hết hàng (0)']].map(([v,t])=>`<option value="${v}" ${v===filter?'selected':''}>${t}</option>`).join('')}</select></label><label class="field">Hiển thị<select id="inv-limit">${[5,10,20,50].map(v=>`<option value="${v}" ${limit===v?'selected':''}>${v} / trang</option>`).join('')}</select></label></div>
       <div class="table-wrap"><table class="data-table inv-table"><thead><tr><th>Hình</th><th>Mã / Sản phẩm</th><th>Danh mục</th><th>Tồn kho</th><th>Tình trạng</th><th>Thao tác</th></tr></thead><tbody>${shown.map(p=>`<tr><td>${p.image_url||p.image?`<img src="${esc(p.image_url||p.image)}" alt="" loading="lazy">`:'—'}</td><td><strong>${esc(p.name)}</strong><small class="inv-muted">ID ${p.id} · ${esc(p.sku||p.material||'')}</small></td><td>${esc(typeof p.category==='string'?p.category:(p.category?.name||p.category_name||'—'))}</td><td><strong>${fmt(p.stock)}</strong></td><td><span class="inv-status ${statusClass(p.stock)}">${status(p.stock)}</span></td><td><button class="button-sm" type="button" data-inv-id="${p.id}">Điều chỉnh</button></td></tr>`).join('')||'<tr><td colspan="6">Không có sản phẩm phù hợp.</td></tr>'}</tbody></table></div>
       <div class="inv-pager"><span>${rows.length} sản phẩm phù hợp · Trang ${page}/${pages}</span><div><button id="inv-prev" type="button" ${page<=1?'disabled':''}>← Trước</button><button id="inv-next" type="button" ${page>=pages?'disabled':''}>Sau →</button></div></div></div>
       <div class="panel"><h3>Lịch sử biến động tồn kho</h3><p>Backend hiện chưa cung cấp API nhật ký kho. Giao diện không hiển thị phiếu DEMO như giao dịch thật. Các lần điều chỉnh tồn nên được ghi nhật ký phía Backend trước khi dùng trong môi trường thực tế.</p></div>
       <dialog id="inv-dialog" class="inv-dialog"><div class="inv-dialog-head"><h2 id="inv-dialog-title">Điều chỉnh tồn kho</h2><button id="inv-close" type="button" aria-label="Đóng">×</button></div>
       <p class="mini-note">Ghi tồn kho mới qua API. Backend sẽ so khớp <code>expected_stock</code> với số tồn thực trước khi cập nhật.</p>
       <form id="inv-form"><input id="inv-id" type="hidden"><div class="inv-current" id="inv-current"></div>
       <label class="field">Loại điều chỉnh<select id="inv-type"><option value="in">Nhập thêm (+)</option><option value="out">Xuất bớt (−)</option><option value="set">Đặt tồn thực tế (kiểm kê)</option></select></label>
       <label class="field">${'Số lượng nhập / xuất hoặc tồn mới'}<input id="inv-amount" type="number" min="1" step="1" required></label>
       <p class="mini-note">Không có API ghi lý do/phiếu nhập xuất; chỉ sử dụng khi đã đối chiếu chứng từ bên ngoài.</p>
       <p id="inv-modal-error" class="inv-error" role="alert" hidden></p>
       <div class="inv-actions"><button id="inv-cancel" class="button button-outline" type="button">Hủy</button><button id="inv-save" class="button button-dark" type="submit">LƯU TỒN KHO THẬT</button></div></form></dialog></section>`;
      $('inv-reload').onclick=load;
      $('inv-search').oninput=e=>{query=e.target.value;page=1;render();const input=$('inv-search');input.focus();input.setSelectionRange(query.length,query.length);};
      $('inv-filter').onchange=e=>{filter=e.target.value;page=1;render();};
      $('inv-limit').onchange=e=>{limit=Number(e.target.value);page=1;render();};
      $('inv-prev').onclick=()=>{page--;render();};$('inv-next').onclick=()=>{page++;render();};
      mount.querySelectorAll('[data-inv-id]').forEach(btn=>btn.onclick=()=>open(Number(btn.dataset.invId)));
      $('inv-close').onclick=()=> $('inv-dialog').close();$('inv-cancel').onclick=()=> $('inv-dialog').close();
      $('inv-type').onchange=()=>{$('inv-amount').min=$('inv-type').value==='set'?'0':'1';};
      $('inv-form').onsubmit=save;
    }
    function open(id){
      const product=products.find(p=>p.id===id);if(!product)return;
      $('inv-form').reset();$('inv-id').value=String(id);
      $('inv-dialog-title').textContent=`Điều chỉnh kho – ${product.name}`;
      $('inv-current').textContent=`Tồn kho đã tải: ${fmt(product.stock)} · ${status(product.stock)}`;
      $('inv-modal-error').hidden=true;
      $('inv-dialog').showModal();
    }
    async function save(e){
      e.preventDefault();if(busy)return;
      const id=Number($('inv-id').value),p=products.find(x=>x.id===id);
      const type=$('inv-type').value,quantity=Number($('inv-amount').value);
      const after=type==='in'?p?.stock+quantity:type==='out'?p?.stock-quantity:quantity;
      const error=$('inv-modal-error'),button=$('inv-save');
      if(!p||!['in','out','set'].includes(type)||!Number.isSafeInteger(quantity)||quantity<(type==='set'?0:1)||!Number.isSafeInteger(after)||after<0||after>2147483647){error.textContent='Số lượng không hợp lệ hoặc vượt số lượng tồn.';error.hidden=false;return;}
      if(after===p.stock){error.textContent='Tồn kho không thay đổi.';error.hidden=false;return;}
      if(!confirm(`Sản phẩm: ${p.name}\nTồn trước: ${p.stock}\nTồn mới: ${after}\nBạn xác nhận ghi PostgreSQL?`))return;
      busy=true;button.disabled=true;error.hidden=true;
      try{
        await api().updateStaffStock(id,p.stock,after);
        $('inv-dialog').close();
        await load();
        inform(`Đã gửi cập nhật tồn kho sản phẩm ID ${id}. Dữ liệu vừa được tải lại từ Backend.`,false);
      }catch(err){
        error.textContent=msg(err)+' — Nếu tồn kho đã thay đổi, đóng hộp thoại và nhấn Làm mới trước khi thử lại.';
        error.hidden=false;
      }finally{busy=false;if(button.isConnected)button.disabled=false;}
    }
    load();
  };
})();
