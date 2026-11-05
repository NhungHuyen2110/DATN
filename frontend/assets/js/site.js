"use strict";
(() => {
const root=document.body.dataset.root||'../',page=document.body.dataset.page,area=document.body.dataset.area;
const P=window.LUMIERE_PRODUCTS||[];const $=(s)=>document.querySelector(s), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>Number(n||0).toLocaleString('vi-VN')+' ₫';
const read=(key,fallback)=>{try{const v=JSON.parse(localStorage.getItem(key));return v??fallback}catch{return fallback}};
const FAV='lumiere_favorites';
let user=null;
let cartData={items:[],total_quantity:0,subtotal_vnd:"0.00"};
let cartBusy=false;
const favorites=()=>read(FAV,[]);
const save=(key,value)=>localStorage.setItem(key,JSON.stringify(value));
const product=id=>P.find(p=>p.id===Number(id));
const notify=(text,error=false)=>{const el=$('#site-toast');el.textContent=text;el.style.background=error?'#9d4232':'#292824';clearTimeout(notify.timer);notify.timer=setTimeout(()=>el.textContent='',4200)};
const demo=msg=>notify(msg||'Đây là giao diện DEMO. Backend chưa cung cấp API cho chức năng này.');
const nav=(text,url)=>`<a href="${root+url}">${text}</a>`;
const shell=$('#site-shell');shell.innerHTML=`<div class="site-bar">LUMIÈRE — TINH HOA TRANG SỨC · FRONTEND KHÔNG DÙNG FRAMEWORK</div><header class="site-nav"><div class="container site-nav-inner"><a class="logo" href="${root}index.html">LUMIÈRE<span>FINE JEWELRY</span></a><nav class="site-nav-links">${nav('Trang chủ','index.html')}${nav('Sản phẩm','pages/products.html')}${nav('Bộ sưu tập','pages/collections.html')}${nav('Giới thiệu','pages/about.html')}${nav('Liên hệ','pages/contact.html')}</nav><div class="account-links">${nav('♡ Yêu thích','pages/wishlist.html')}${nav('Giỏ hàng','pages/cart.html')}<a id="account-nav" href="${root}pages/login.html" aria-label="Tài khoản"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg> Đăng nhập</a><button id="nav-logout" type="button" hidden>Đăng xuất</button></div></div></header>`;
$('#site-footer').innerHTML=`<footer class="site-bottom"><strong>LUMIÈRE</strong><p>Vẻ đẹp vượt thời gian · Đồ án tốt nghiệp · Frontend HTML/CSS/JS thuần</p><p>${nav('Sản phẩm','pages/products.html')} · ${nav('Đơn hàng','pages/orders.html')} · ${nav('Chính sách liên hệ','pages/contact.html')}</p></footer>`;
const content=$('#page-content');

function applyRoleNavigation() {
  const role = user?.role || "guest";
  const menu = document.querySelector(".site-nav-links");
  const account = document.querySelector("#account-nav");
  const accountLinks = document.querySelector(".account-links");
  const footerLinks = document.querySelector("#site-footer .site-bottom p:last-child");
  if (!menu || !account || !accountLinks) return;
  const link = (label, path) =>
    `<a href="${root + path}">${label}</a>`;
  if (role === "admin") {
    menu.innerHTML = [
      link("Dashboard", "pages/admin/dashboard.html"),
      link("S&#7843;n ph&#7849;m", "pages/admin/products.html"),
      link("&#272;&#417;n h&#224;ng", "pages/admin/orders.html"),
      link("Kh&#225;ch h&#224;ng", "pages/admin/customers.html"),
      link("Nh&#226;n vi&#234;n", "pages/admin/staff.html"),
      link("M&#227; gi&#7843;m gi&#225;", "pages/admin/coupons.html")
    ].join("");
    account.href = root + "pages/admin/dashboard.html";
    account.textContent = user.full_name + " (Admin)";
    if (footerLinks) {
      footerLinks.innerHTML =
        link("B&#7843;ng &#273;i&#7873;u khi&#7875;n", "pages/admin/dashboard.html");
    }
  } else if (role === "staff") {
    menu.innerHTML = [
      link("X&#7917; l&#253; &#273;&#417;n h&#224;ng", "pages/staff/orders.html"),
      link("Qu&#7843;n l&#253; t&#7891;n kho", "pages/staff/inventory.html")
    ].join("");
    account.href = root + "pages/staff/orders.html";
    account.textContent = user.full_name + " (Staff)";
    if (footerLinks) {
      footerLinks.innerHTML =
        link("X&#7917; l&#253; &#273;&#417;n h&#224;ng", "pages/staff/orders.html");
    }
  } else {
    return;
  }
  accountLinks.querySelectorAll("a").forEach(a => {
    if (a.id === "account-nav") return;
    const url = a.getAttribute("href") || "";
    if (
      url.endsWith("pages/wishlist.html") ||
      url.endsWith("pages/cart.html")
    ) {
      a.hidden = true;
      a.style.display = "none";
    }
  });
  const roleHome = role === "admin"
    ? "pages/admin/dashboard.html"
    : "pages/staff/orders.html";
  const allowed = role === "admin"
    ? page.startsWith("admin-")
    : page.startsWith("staff-");
  if (!allowed) {
    location.replace(root + roleHome);
    return true;
  }
  return false;
}

const card=p=>`<article class="catalog-card"><a href="${root}pages/product-detail.html?id=${encodeURIComponent(p.id)}"><img loading="lazy" src="${esc(p.image)}" alt="${esc(p.name)}"></a><div class="meta"><small>${esc(p.category)} · ${esc(p.material)}</small><h3><a href="${root}pages/product-detail.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a></h3><strong>${money(p.price)}</strong><div class="small-actions"><button class="button-sm" data-add="${p.id}" ${p.stock<=0?'disabled':''}>+ Giỏ hàng</button><button class="button-sm" data-favorite="${p.id}">♡ Yêu thích</button></div></div></article>`;
const formField=(id,label,type='text',extra='')=>`<div class="field"><label for="${id}">${label}</label><input id="${id}" name="${id}" type="${type}" ${extra}></div>`;
const errorBox='<div id="form-alert" class="form-alert" role="status" aria-live="polite" hidden></div>';
const alert=(message,kind='error')=>{const el=$('#form-alert');if(!el)return;el.hidden=false;el.className='form-alert '+kind;el.textContent=message};
const get=(id)=>document.getElementById(id)?.value?.trim()||'';
async function add(id, amount=1) {
  if (!user) {
    notify("Vui l?ng ??ng nh?p ?? th?m v?o gi? h?ng", true);
    return;
  }
  if (cartBusy) return;
  const productId=Number(id);
  if (!Number.isInteger(productId) || !Number.isInteger(amount) || amount<1) {
    notify("S? l??ng s?n ph?m kh?ng h?p l?", true);
    return;
  }
  cartBusy=true;
  try {
    cartData=await LUMIERE_API.addCartItem(productId,amount);
    notify("\u0110\u00e3 th\u00eam s\u1ea3n ph\u1ea9m v\u00e0o gi\u1ecf h\u00e0ng");
    if(page==="cart" || page==="checkout") render();
  } catch(error) {
    notify(error.message,true);
  } finally {
    cartBusy=false;
  }
}
async function changeCartItem(productId, delta, remove=false) {
  if(cartBusy || !user) return;
  const item=cartData.items.find(
    row=>row.product.id===Number(productId)
  );
  if(!item) return;
  cartBusy=true;
  try {
    const next=item.quantity+delta;
    if(remove || next<=0) {
      cartData=await LUMIERE_API.removeCartItem(item.id);
    } else {
      cartData=await LUMIERE_API.updateCartItem(item.id,next);
    }
    render();
    notify("\u0110\u00e3 c\u1eadp nh\u1eadt gi\u1ecf h\u00e0ng");
  } catch(error) {
    notify(error.message,true);
  } finally {
    cartBusy=false;
  }
}
function favorite(id){id=Number(id);const f=favorites();const next=f.includes(id)?f.filter(n=>n!==id):[...f,id];save(FAV,next);notify(f.includes(id)?'Đã bỏ yêu thích':'Đã thêm vào yêu thích');if(page==='wishlist')render()}
const cartLines=()=>cartData.items.map(item=>({
  p:product(item.product.id),
  qty:Number(item.quantity),
  itemId:item.id,
  unitPrice:Number(item.unit_price_vnd),
  lineTotal:Number(item.line_total_vnd)
})).filter(x=>x.p && Number.isInteger(x.qty) && x.qty>0);
const subtotal=()=>Number(cartData.subtotal_vnd||0);
const shipping=()=>subtotal()>0&&subtotal()<2000000?30000:0;
const itemsHtml=()=>cartLines().map(({p,qty,unitPrice,lineTotal})=>`
<div class="list-row">
  <a href="${root}pages/product-detail.html?id=${p.id}">
    <img src="${esc(p.image)}" alt="${esc(p.name)}">
  </a>
  <div>
    <h3>${esc(p.name)}</h3>
    <p>${esc(p.material)} &middot; ${money(unitPrice)}</p>
    <button data-remove="${p.id}">X&oacute;a s&#7843;n ph&#7849;m</button>
  </div>
  <div>
    <div class="qty-line">
      <button data-dec="${p.id}" aria-label="Gi&#7843;m">&minus;</button>
      <strong>${qty}</strong>
      <button data-inc="${p.id}" aria-label="T?ng">+</button>
    </div>
    <strong class="price">${money(lineTotal)}</strong>
  </div>
</div>`).join('');
function requireAuthMessage(){return '<p class="demo-note">Bạn cần đăng nhập để tiếp tục. Thông tin đơn hàng chưa được ghi vào PostgreSQL trong bản frontend-first.</p>'}
function catalog(){
  if(window.LUMIERE_PRODUCTS_ERROR){content.innerHTML=`<div class="empty-panel">Không tải được dữ liệu sản phẩm từ Business API: ${esc(window.LUMIERE_PRODUCTS_ERROR)}</div>`;return}
  content.innerHTML=`<div class="content-grid"><aside class="filter-panel"><h2>Bộ lọc sản phẩm</h2>${formField('keyword','Tìm tên / chất liệu / đá quý','search','placeholder="Tìm trang sức..."')}<div class="field"><label for="category">Danh mục</label><select id="category"><option value="">Tất cả</option>${[...new Set(P.map(x=>x.category))].sort().map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('')}</select></div><div class="field"><label for="max-price">Giá tối đa</label><select id="max-price"><option value="">Không giới hạn</option><option value="5000000">Dưới 5 triệu</option><option value="10000000">Dưới 10 triệu</option><option value="20000000">Dưới 20 triệu</option><option value="30000000">Dưới 30 triệu</option></select></div><button id="reset-filter" class="button button-outline" type="button">XÓA BỘ LỌC</button><p class="mini-note">Danh mục sản phẩm được tải từ Business API và PostgreSQL. Hình ảnh minh họa theo nhóm sản phẩm.</p></aside><section><div class="toolbar"><span id="result-count"></span><label>Sắp xếp <select id="sort"><option value="default">Theo ID</option><option value="asc">Giá tăng dần</option><option value="desc">Giá giảm dần</option><option value="name">Tên A–Z</option></select></label></div><div id="catalog-results" class="catalog-grid"></div><div class="ap-pager"><span id="catalog-page-info"></span><div class="ap-page-actions"><button id="catalog-prev" type="button">← Trước</button><button id="catalog-next" type="button">Sau →</button></div></div></section></div>`;
  const params=new URLSearchParams(location.search);
  $('#keyword').value=params.get('q')||'';$('#category').value=params.get('category')||'';
  let currentPage=1;const pageSize=12;
  function draw(){let matches=P.filter(p=>`${p.name} ${p.category} ${p.material} ${p.gem} ${p.brand}`.toLocaleLowerCase('vi').includes(get('keyword').toLocaleLowerCase('vi'))&&(!get('category')||p.category===get('category'))&&(!get('max-price')||p.price<=Number(get('max-price'))));
    if(get('sort')==='asc')matches.sort((a,b)=>a.price-b.price);
    if(get('sort')==='desc')matches.sort((a,b)=>b.price-a.price);
    if(get('sort')==='name')matches.sort((a,b)=>a.name.localeCompare(b.name,'vi'));
    const totalPages=Math.max(1,Math.ceil(matches.length/pageSize));currentPage=Math.min(currentPage,totalPages);
    const slice=matches.slice((currentPage-1)*pageSize,currentPage*pageSize);
    $('#result-count').textContent=`Tìm thấy ${matches.length} / ${P.length} sản phẩm`;
    $('#catalog-results').innerHTML=slice.length?slice.map(card).join(''):'<div class="empty-panel">Không có sản phẩm phù hợp.</div>';
    $('#catalog-page-info').textContent=`Trang ${currentPage} / ${totalPages}`;
    $('#catalog-prev').disabled=currentPage===1;$('#catalog-next').disabled=currentPage>=totalPages;
  }
  ['keyword','category','max-price','sort'].forEach(id=>$('#'+id).addEventListener('input',()=>{currentPage=1;draw()}));
  $('#catalog-prev').onclick=()=>{currentPage--;draw();window.scrollTo({top:0,behavior:'smooth'})};
  $('#catalog-next').onclick=()=>{currentPage++;draw();window.scrollTo({top:0,behavior:'smooth'})};
  $('#reset-filter').onclick=()=>{['keyword','category','max-price'].forEach(id=>$('#'+id).value='');$('#sort').value='default';currentPage=1;draw()};draw();
}
async function detail(){
  const p=product(new URLSearchParams(location.search).get('id'));
  if(!p){content.innerHTML='<div class="empty-panel">Không tìm thấy ProductID trong danh mục AI. <a class="inline-link" href="products.html">Quay lại danh sách</a></div>';return}
  document.title=p.name+' | LUMIÈRE';
  content.innerHTML=`<div class="two-col"><div><img class="detail-photo" src="${esc(p.image)}" alt="Ảnh minh họa ${esc(p.category)}"><p class="mini-note">Ảnh minh họa theo danh mục, chưa phải ảnh sản phẩm thực.</p></div><section><div class="eyebrow">${esc(p.category)}</div><h2 class="product-title">${esc(p.name)}</h2><div class="price" style="font-size:28px">${money(p.price)}</div><p class="page-subtitle">Thông tin sản phẩm được tải từ Business API. Giá bán và tồn kho được kiểm tra khi đặt hàng.</p><dl class="specs"><div><dt>ProductID (AI)</dt><dd>${p.id}</dd></div><div><dt>Thương hiệu</dt><dd>${esc(p.brand)}</dd></div><div><dt>Chất liệu</dt><dd>${esc(p.material)}</dd></div><div><dt>Đá quý</dt><dd>${esc(p.gem)}</dd></div><div><dt>Bộ sưu tập</dt><dd>${esc(p.collection)}</dd></div><div><dt>Tồn kho theo AI dataset</dt><dd>${p.stock}</dd></div></dl><label for="qty">Số lượng</label><div class="qty-line"><button id="qty-minus">−</button><input id="qty" type="number" min="1" max="${p.stock}" value="1"><button id="qty-plus">+</button></div><button id="detail-add" class="button button-dark button-wide" ${p.stock===0?'disabled':''}>THÊM VÀO GIỎ HÀNG ↗</button><button id="detail-fav" class="button button-outline button-wide">♡ YÊU THÍCH</button><div class="demo-note">Giỏ hàng được đồng bộ với PostgreSQL. Đơn hàng được tạo khi xác nhận thanh toán.</div></section></div><hr class="section-divider"><h2 class="reco-title">Gợi ý dành cho bạn · Hybrid V2</h2><p class="mini-note">Kết quả dựa trên TF-IDF, Qdrant, Collaborative Filtering và Neo4j. Với khách chưa có customer_id trong AI dataset, thành phần cá nhân hóa có thể thiếu.</p><div id="ai-reco-status" class="mini-note">Đang tải đề xuất AI…</div><div id="ai-reco-grid" class="catalog-grid"></div>`;
  $('#qty-minus').onclick=()=>$('#qty').value=Math.max(1,Number($('#qty').value||1)-1);
  $('#qty-plus').onclick=()=>$('#qty').value=Math.min(p.stock,Number($('#qty').value||1)+1);
  $('#detail-add').onclick=()=>{const q=Number($('#qty').value);if(!Number.isInteger(q)||q<1||q>p.stock)return notify('Số lượng không hợp lệ',true);add(p.id,q)};
  $('#detail-fav').onclick=()=>favorite(p.id);
  const status=$('#ai-reco-status');const grid=$('#ai-reco-grid');
  const customerId=user?.customer_id || 'GUEST';
  if(!window.LUMIERE_AI_BASE){status.textContent='AI Service chưa được cấu hình; bạn vẫn có thể mua sắm.';return}
  const url=new URL(window.LUMIERE_AI_BASE.replace(/\/$/,'')+'/recommendations/v2');url.searchParams.set('customer_id',customerId);url.searchParams.set('product_id',String(p.id));url.searchParams.set('number','4');
  try{
    const response=await fetch(url,{signal:AbortSignal.timeout(45000)});
    if(!response.ok)throw Error('HTTP '+response.status);
    const payload=await response.json();if(!payload.success||!Array.isArray(payload.data))throw Error('Phản hồi không hợp lệ');
    const recommended=payload.data.map(x=>product(x.ProductID)).filter(x=>x&&x.id!==p.id);
    status.textContent=recommended.length?`Đã tìm thấy ${recommended.length} sản phẩm phù hợp từ Hybrid V2.`:'AI chưa trả về sản phẩm có trong danh mục.';
    grid.innerHTML=recommended.map(card).join('');
  }catch(error){status.textContent='Chưa tải được đề xuất Hybrid V2 ('+error.message+'). Bạn vẫn có thể xem và mua sắm danh mục.';}
}
function cartPage(){const count=cartLines().length;content.innerHTML=`<div class="content-grid cart-layout"><div>${count?itemsHtml():'<div class="empty-panel">Giỏ hàng của bạn đang trống.</div>'}<p><a class="inline-link" href="products.html">← Tiếp tục mua sắm</a></p></div><aside class="summary-card"><h2>Tóm tắt đơn hàng</h2><div class="summary-line"><span>Tạm tính</span><strong>${money(subtotal())}</strong></div><div class="summary-line"><span>Phí vận chuyển dự kiến</span><strong>${money(shipping())}</strong></div><div class="summary-line total"><span>Tổng cộng</span><strong class="price">${money(subtotal()+shipping())}</strong></div><p class="mini-note">Tạm tính theo dữ liệu giỏ hàng từ Backend. Tổng tiền được xác nhận khi tạo đơn.</p><a class="button button-dark button-wide" href="checkout.html">TIẾN HÀNH ĐẶT HÀNG ↗</a></aside></div>`}
function checkout(){if(!cartLines().length){content.innerHTML='<div class="empty-panel">Giỏ hàng trống. <a class="inline-link" href="products.html">Mua sắm ngay</a></div>';return}content.innerHTML=`<div class="two-col"><div class="panel"><h2>Thông tin người nhận</h2>${errorBox}<form id="checkout-form">${formField('recipient','Họ và tên','text','required autocomplete="name"')}${formField('phone','Số điện thoại','tel','required pattern="0[0-9]{9}"')}${formField('address','Địa chỉ nhận hàng','text','required')}${formField('province','Tỉnh / thành phố','text','required')}<div class="field"><label for="payment">Phương thức thanh toán</label><select id="payment"><option value="cod">Thanh toán khi nhận hàng (COD)</option><option value="bank">Chuyển khoản (mô phỏng, chưa xử lý)</option></select></div><div class="field"><label for="note">Ghi chú</label><textarea id="note" maxlength="500"></textarea></div>${requireAuthMessage()}<button class="button button-dark button-wide">KIỂM TRA ĐƠN HÀNG</button></form></div><aside class="summary-card"><h2>Đơn hàng tạm tính</h2>${cartLines().map(({p,qty})=>`<div class="summary-line"><span>${esc(p.name)} × ${qty}</span><strong>${money(p.price*qty)}</strong></div>`).join('')}<div class="summary-line"><span>Vận chuyển</span><span>${money(shipping())}</span></div><div class="summary-line total"><span>Tổng</span><strong>${money(subtotal()+shipping())}</strong></div><p class="mini-note">Bản frontend-first không tạo đơn giả. Khi có API POST /orders, backend phải đọc giá/tồn kho từ PostgreSQL và tạo đơn trong transaction.</p></aside></div>`
  const bankOption = document.querySelector('#payment option[value="bank"]');
  if (bankOption) bankOption.remove();
  const noteField = document.querySelector('#note');
  if (noteField) noteField.closest('.field')?.remove();
  content.querySelectorAll('.demo-note,.mini-note').forEach(el => {
    if (el.textContent.includes('frontend-first')) {
      el.textContent = user
        ? 'Don hang se duoc ghi nhan vao PostgreSQL khi xac nhan.'
        : 'Vui long dang nhap truoc khi dat hang.';
    }
  });
  $('#checkout-form').onsubmit = async e => {
    e.preventDefault();
    if (!user) {
      alert("Vui l\u00f2ng \u0111\u0103ng nh\u1eadp \u0111\u1ec3 \u0111\u1eb7t h\u00e0ng");
      return;
    }
    if (get('payment') !== 'cod') {
      alert("Ph\u01b0\u01a1ng th\u1ee9c thanh to\u00e1n ch\u01b0a \u0111\u01b0\u1ee3c h\u1ed7 tr\u1ee3");
      return;
    }
    const button = $('#checkout-form button[type="submit"], #checkout-form button');
    if (button.disabled) return;
    button.disabled = true;
    try {
      const order = await LUMIERE_API.createOrder({
        recipient_name: get('recipient'),
        phone: get('phone'),
        address: get('address') + ', ' + get('province'),
        payment_method: 'cod'
      });
      cartData = {
        items: [],
        total_quantity: 0,
        subtotal_vnd: "0.00"
      };
      content.innerHTML = `
        <section class="panel">
          <h2>&#272;&#7863;t h&#224;ng th&#224;nh c&#244;ng!</h2>
          <p>M&#227; &#273;&#417;n h&#224;ng:
            <strong>${esc(order.code)}</strong>
          </p>
          <p>T&#7893;ng ti&#7873;n:
            <strong>${money(order.total_vnd)}</strong>
          </p>
          <p>Tr&#7841;ng th&#225;i &#273;&#417;n:
            <strong>${esc(order.status)}</strong>
          </p>
          <p>Thanh to&#225;n:
            <strong>${esc(order.payment_status)}</strong>
          </p>
          <p>Ph&#432;&#417;ng th&#7913;c: COD</p>
          <a class="button button-dark"
             href="orders.html">
            Xem &#273;&#417;n h&#224;ng
          </a>
        </section>
      `;
    } catch (error) {
      alert(error.message);
      button.disabled = false;
      notify(
        "Neu ket noi bi gian doan, hay kiem tra don hang truoc khi thu lai.",
        true
      );
    }
  };
}

function auth(which){const reg=which==='register',forgot=which==='forgot-password';content.innerHTML=`<section class="auth-page"><div class="auth-photo"><div><div class="eyebrow">THE ART OF FINE JEWELRY</div><h2>Vẻ đẹp mang<br>dấu ấn riêng</h2><p>Chào mừng đến với LUMIÈRE</p></div></div><div class="auth-form"><div class="eyebrow">MY LUMIÈRE</div><h2>${forgot?'Quên mật khẩu':reg?'Tạo tài khoản':'Đăng nhập'}</h2><p class="page-subtitle">${forgot?'Tính năng khôi phục cần dịch vụ gửi email an toàn.':reg?'Đăng ký để khám phá trang sức dành riêng cho bạn.':'Đăng nhập để quản lý tài khoản và đơn hàng của bạn.'}</p>${errorBox}${forgot?'<p class="demo-note">Chưa có API quên mật khẩu. Backend cần triển khai token một lần có thời hạn, gửi qua email. Không hiển thị thông tin tài khoản có tồn tại hay không.</p>'+formField('email','Email','email','required')+'<button class="button button-dark button-wide" id="forgot-demo">GỬI YÊU CẦU (CHƯA KÍCH HOẠT)</button>':`<form id="auth-form">${reg?formField('full_name','Họ tên','text','minlength="2" maxlength="150" required autocomplete="name"')+formField('phone','Số điện thoại','tel','pattern="0[0-9]{9}" autocomplete="tel"'):''}${formField('email','Email','email','required autocomplete="email"')}${formField('password','Mật khẩu','password',`${reg?'minlength="8" maxlength="128" autocomplete="new-password"':'autocomplete="current-password"'} required`)}${reg?formField('confirm','Nhập lại mật khẩu','password','minlength="8" required autocomplete="new-password"'):''}<label class="mini-note"><input id="show-password" type="checkbox"> Hiện mật khẩu</label><button id="auth-submit" class="button button-dark button-wide">${reg?'ĐĂNG KÝ':'ĐĂNG NHẬP'}</button></form>`}<p class="mini-note">${reg?'Đã có tài khoản? <a class="inline-link" href="login.html">Đăng nhập</a>':'Chưa có tài khoản? <a class="inline-link" href="register.html">Đăng ký</a>'}</p>${!reg&&!forgot?'<p><a class="inline-link" href="forgot-password.html">Quên mật khẩu?</a></p>':''}</div></section>`;if(forgot){$('#forgot-demo').onclick=()=>demo('Yêu cầu khôi phục chưa có backend.');return}$('#show-password').onchange=e=>['password','confirm'].forEach(id=>{const el=$('#'+id);if(el)el.type=e.target.checked?'text':'password'});$('#auth-form').onsubmit=async e=>{e.preventDefault();const btn=$('#auth-submit');btn.disabled=true;try{if(reg){if($('#password').value!==$('#confirm').value)throw Error('Mật khẩu xác nhận không khớp');await LUMIERE_API.register({full_name:get('full_name'),phone:get('phone')||null,email:get('email'),password:$('#password').value});alert('Đăng ký thành công! Đang chuyển sang đăng nhập.','success');setTimeout(()=>location.href='login.html',850)}else{await LUMIERE_API.login(get('email'),$('#password').value);alert('Đăng nhập thành công','success');const signedIn=await LUMIERE_API.me();location.href=signedIn.role==='admin'?'admin/dashboard.html':signedIn.role==='staff'?'staff/orders.html':'account.html'}}catch(err){alert(err.message)}finally{btn.disabled=false}}}
function account(){if(!user){content.innerHTML='<div class="empty-panel">Bạn chưa đăng nhập. <a class="inline-link" href="login.html">Đăng nhập</a></div>';return}content.innerHTML=`<div class="two-col"><div class="panel"><h2>Thông tin tài khoản</h2><dl class="specs"><div><dt>Họ tên</dt><dd>${esc(user.full_name)}</dd></div><div><dt>Email</dt><dd>${esc(user.email)}</dd></div><div><dt>Vai trò</dt><dd>${esc(user.role)}</dd></div></dl><p class="demo-note">Chỉnh sửa hồ sơ, địa chỉ và đổi mật khẩu sẽ được kết nối API sau.</p></div><div class="panel"><h2>Truy cập nhanh</h2><p>${nav('Đơn hàng của tôi','pages/orders.html')}</p><p>${nav('Danh sách yêu thích','pages/wishlist.html')}</p><p>${nav('Đánh giá của tôi','pages/reviews.html')}</p><button class="button button-outline" id="logout-main">ĐĂNG XUẤT</button></div></div>`;$('#logout-main').onclick=logout}


async function orders() {
  if (!user) {
    content.innerHTML = `
      <div class="empty-panel">
        Vui l&#242;ng &#273;&#259;ng nh&#7853;p
        &#273;&#7875; xem &#273;&#417;n h&#224;ng.
        <a href="login.html">&#272;&#259;ng nh&#7853;p</a>
      </div>`;
    return;
  }
  content.innerHTML =
    '<div class="empty-panel">&#272;ang t&#7843;i &#273;&#417;n h&#224;ng...</div>';
  try {
    if (page === "order-detail") {
      const id = Number(
        new URLSearchParams(location.search).get("id")
      );
      if (!Number.isInteger(id) || id <= 0) {
        throw new Error("Invalid order ID");
      }
      const order = await LUMIERE_API.request("/orders/" + id);
      const rows = (order.items || []).map(item => `
        <tr>
          <td>${esc(item.product_name)}</td>
          <td>${esc(item.sku)}</td>
          <td>${Number(item.quantity)}</td>
          <td>${money(item.unit_price_vnd)}</td>
          <td>${money(item.line_total_vnd)}</td>
        </tr>
      `).join("");
      content.innerHTML = `
        <div class="panel">
          <h2>Chi ti&#7871;t &#273;&#417;n h&#224;ng</h2>
          <p><strong>M&#227; &#273;&#417;n:</strong> ${esc(order.code)}</p>
          <p><strong>Ng&#224;y &#273;&#7863;t:</strong>
            ${new Date(order.created_at).toLocaleString("vi-VN")}
          </p>
          <p><strong>Tr&#7841;ng th&#225;i:</strong> ${esc(order.status)}</p>
          <p><strong>Thanh to&#225;n:</strong> ${esc(order.payment_status)}</p>
          <p><strong>Ph&#432;&#417;ng th&#7913;c:</strong>
            ${esc(order.payment_method).toUpperCase()}
          </p>
          <p><strong>Ng&#432;&#7901;i nh&#7853;n:</strong>
            ${esc(order.recipient_name)}
          </p>
          <p><strong>S&#7889; &#273;i&#7879;n tho&#7841;i:</strong>
            ${esc(order.phone)}
          </p>
          <p><strong>&#272;&#7883;a ch&#7881;:</strong>
            ${esc(order.address)}
          </p>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>S&#7843;n ph&#7849;m</th>
                  <th>SKU</th>
                  <th>S&#7889; l&#432;&#7907;ng</th>
                  <th>&#272;&#417;n gi&#225;</th>
                  <th>Th&#224;nh ti&#7873;n</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
          <p>T&#7841;m t&#237;nh: ${money(order.subtotal_vnd)}</p>
          <p>Ph&#237; v&#7853;n chuy&#7875;n: ${money(order.shipping_vnd)}</p>
          <p>Gi&#7843;m gi&#225;: ${money(order.discount_vnd)}</p>
          <h3>T&#7893;ng c&#7897;ng: ${money(order.total_vnd)}</h3>
          <p>
            <a class="inline-link" href="orders.html">
              &larr; Tr&#7903; v&#7873; danh s&#225;ch &#273;&#417;n h&#224;ng
            </a>
          </p>
        </div>
      `;
      return;
    }
    const params = new URLSearchParams(location.search);
    const requestedPage = Number(params.get("page") || 1);
    const currentPage = Number.isInteger(requestedPage)
      && requestedPage > 0 ? requestedPage : 1;
    const result = await LUMIERE_API.request(
      "/orders/my?page=" + currentPage + "&page_size=20"
    );
    if (!Array.isArray(result.items)) {
      throw new Error("Invalid orders response");
    }

    const statusLabel = value => ({
      pending: "Ch\u1edd x\u00e1c nh\u1eadn",
      confirmed: "\u0110\u00e3 x\u00e1c nh\u1eadn",
      packing: "\u0110ang \u0111\u00f3ng g\u00f3i",
      shipping: "\u0110ang giao",
      delivered: "\u0110\u00e3 giao",
      cancelled: "\u0110\u00e3 h\u1ee7y"
    }[value] || value);
    const paymentLabel = value => ({
      unpaid: "Ch\u01b0a thanh to\u00e1n",
      paid: "\u0110\u00e3 thanh to\u00e1n",
      refunded: "\u0110\u00e3 ho\u00e0n ti\u1ec1n"
    }[value] || value);
const rows = result.items.map(order => `
      <tr>
        <td><span class="customer-order-code" title="${esc(order.code)}">${esc(order.code.slice(0, 12))}&hellip;</span></td>
        <td>${new Date(order.created_at).toLocaleDateString("vi-VN")}</td>
        <td><span class="customer-order-status">${esc(statusLabel(order.status))}</span></td>
        <td>${esc(paymentLabel(order.payment_status))}</td>
        <td>${esc(order.payment_method).toUpperCase()}</td>
        <td>${money(order.total_vnd)}</td>
        <td>
          <a class="inline-link"
             href="order-detail.html?id=${Number(order.id)}">
            Xem chi ti&#7871;t
          </a>
        </td>
      </tr>
    `).join("");
    const totalPages = Math.max(
      1, Math.ceil(Number(result.total || 0) / 20)
    );
    content.innerHTML = `
      <div class="panel">
        <h2>&#272;&#417;n h&#224;ng c&#7911;a t&#244;i</h2>
        <p>T&#7893;ng s&#7889; &#273;&#417;n h&#224;ng:
          ${Number(result.total || 0)}
        </p>
        ${result.items.length ? `
          <div class="table-wrap">
            <table class="data-table customer-orders-table">
              <thead>
                <tr>
                  <th>M&#227; &#273;&#417;n</th>
                  <th>Ng&#224;y &#273;&#7863;t</th>
                  <th>Tr&#7841;ng th&#225;i</th>
                  <th>Thanh to&#225;n</th>
                  <th>Ph&#432;&#417;ng th&#7913;c</th>
                  <th>T&#7893;ng ti&#7873;n</th>
                  <th>Chi ti&#7871;t</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        ` : `
          <div class="empty-panel">Ch&#432;a c&#243; &#273;&#417;n h&#224;ng.</div>
        `}
        <p>Trang ${currentPage} / ${totalPages}</p>
        ${currentPage > 1
          ? `<a href="orders.html?page=${currentPage-1}">&larr; Tr&#432;&#7899;c</a>`
          : ""}
        ${currentPage < totalPages
          ? `<a href="orders.html?page=${currentPage+1}">Ti&#7871;p &rarr;</a>`
          : ""}
      </div>
    `;
  } catch (error) {
    content.innerHTML = `
      <div class="empty-panel">
        Kh&#244;ng t&#7843;i &#273;&#432;&#7907;c &#273;&#417;n h&#224;ng:
        ${esc(error.message)}
      </div>`;
    console.error("Orders API:", error);
  }
}

function wishlist(){const list=favorites().map(product).filter(Boolean);content.innerHTML=`<p class="mini-note">Yêu thích đang lưu trên trình duyệt, chưa đồng bộ theo tài khoản.</p><div class="catalog-grid">${list.length?list.map(card).join(''):'<div class="empty-panel">Chưa có sản phẩm yêu thích.</div>'}</div>`}
function staticPage(){const copy={about:'LUMIÈRE kết hợp thương mại điện tử trang sức với hệ thống gợi ý và tư vấn sử dụng trí tuệ nhân tạo. Giao diện là nguyên mẫu phục vụ khóa luận tốt nghiệp.',contact:'Liên hệ với đội ngũ LUMIÈRE để trao đổi thông tin mua sắm và hỗ trợ. Kênh liên lạc thực tế sẽ cấu hình khi triển khai.',collections:'Khám phá các thiết kế nhẫn, dây chuyền, bông tai và vòng tay theo phong cách riêng.',reviews:'Đánh giá chỉ được tạo sau khi đơn hàng hoàn tất. Backend phải xác nhận sản phẩm đã mua và chống đánh giá lặp.'};content.innerHTML=`<div class="panel"><h2>${page==='contact'?'Liên hệ':'LUMIÈRE Jewelry'}</h2><p class="page-subtitle">${copy[page]||''}</p>${page==='collections'?'<div class="catalog-grid">'+P.filter((p,i)=>i<4).map(card).join('')+'</div>':page==='contact'?errorBox+'<form id="contact-form">'+formField('name','Họ tên','text','required')+formField('email','Email','email','required')+'<div class="field"><label>Lời nhắn</label><textarea id="message" required maxlength="1500"></textarea></div><button class="button button-dark">GỬI LIÊN HỆ (DEMO)</button></form>':page==='reviews'?'<p class="demo-note">Chưa có API đánh giá. Yêu cầu backend: POST /products/{id}/reviews, GET /reviews/me.</p>':''}</div>`;if(page==='contact')$('#contact-form').onsubmit=e=>{e.preventDefault();alert('Chưa kết nối API liên hệ. Không có thông tin nào được gửi.','success')}}
function adminPage(){const section=page.slice(6),names={'dashboard':'Dashboard','products':'Sản phẩm','categories':'Danh mục','brands':'Thương hiệu','orders':'Đơn hàng','customers':'Khách hàng','coupons':'Mã giảm giá','staff':'Nhân viên','analytics':'Phân tích hành vi','inventory':'Tồn kho'};const sidebar=`<nav class="admin-side">${Object.entries(names).map(([key,label])=>`<a class="${key===section?'active':''}" href="${key}.html">${label}</a>`).join('')}<a href="../../index.html">← Trở về cửa hàng</a></nav>`;if(section==='dashboard' && typeof window.LUMIERE_ADMIN_DASHBOARD==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="dashboard-mount"></div></div>`;window.LUMIERE_ADMIN_DASHBOARD({mount:$('#dashboard-mount'),products:P,money,esc});return}if((section==='categories'||section==='brands') && typeof window.LUMIERE_ADMIN_TAXONOMY==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="taxonomy-mount"></div></div>`;window.LUMIERE_ADMIN_TAXONOMY({mount:$('#taxonomy-mount'),kind:section,products:P,esc});return}if(section==='analytics' && typeof window.LUMIERE_ADMIN_ANALYTICS==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="analytics-mount"></div></div>`;window.LUMIERE_ADMIN_ANALYTICS({mount:$('#analytics-mount'),products:P});return}if(section==='inventory' && typeof window.LUMIERE_ADMIN_INVENTORY==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="inventory-mount"></div></div>`;window.LUMIERE_ADMIN_INVENTORY({mount:$('#inventory-mount'),products:P});return}if(section==='coupons' && typeof window.LUMIERE_ADMIN_COUPONS==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="coupons-mount"></div></div>`;window.LUMIERE_ADMIN_COUPONS({mount:$('#coupons-mount')});return}if(section==='staff' && typeof window.LUMIERE_ADMIN_STAFF==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="staff-admin-mount"></div></div>`;window.LUMIERE_ADMIN_STAFF({mount:$('#staff-admin-mount')});return}if(section==='customers' && typeof window.LUMIERE_ADMIN_CUSTOMERS==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="customers-mount"></div></div>`;window.LUMIERE_ADMIN_CUSTOMERS({mount:$('#customers-mount')});return}if(section==='orders' && typeof window.LUMIERE_ADMIN_ORDERS==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="orders-mount"></div></div>`;window.LUMIERE_ADMIN_ORDERS({mount:$('#orders-mount')});return}if(section==='products' && typeof window.LUMIERE_ADMIN_PRODUCTS==='function'){content.innerHTML=`<div class="admin-layout">${sidebar}<div id="ap-mount"></div></div>`;window.LUMIERE_ADMIN_PRODUCTS({mount:$('#ap-mount'), products:P, money, esc, authorized:!!(user&&user.role==='admin')});return}let body='';if(section==='dashboard'||section==='analytics'){body=`<div class="dashboard-grid"><div class="stat"><span>Sản phẩm demo</span><strong>${P.length}</strong></div><div class="stat"><span>Danh mục</span><strong>${new Set(P.map(p=>p.category)).size}</strong></div><div class="stat"><span>Đơn hàng (chưa API)</span><strong>—</strong></div><div class="stat"><span>Doanh thu (chưa API)</span><strong>—</strong></div></div><div class="panel"><h2>${section==='analytics'?'Phân tích hành vi khách hàng':'Tổng quan'}</h2><p class="page-subtitle">Các biểu đồ và số liệu doanh thu phải lấy từ backend, không được tự tạo số liệu giao dịch giả. Backend cần hỗ trợ event: product_view, search, add_to_cart, favorite, purchase và bảng tổng hợp theo ngày.</p></div>`}else if(section==='products'||section==='inventory'){body=`<div class="panel"><div class="toolbar"><h2>${names[section]}</h2><button class="button button-outline" data-demo="create-product">+ Thêm mới (demo)</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Hình</th><th>ID</th><th>Tên</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Thao tác</th></tr></thead><tbody>${P.map(p=>`<tr><td><img src="${esc(p.image)}" alt=""></td><td>${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td><td>${money(p.price)}</td><td>${p.stock}</td><td><button class="button-sm" data-demo="edit">Sửa</button></td></tr>`).join('')}</tbody></table></div></div>`}else{const data=section==='categories'?[...new Set(P.map(p=>p.category))]:section==='brands'?['SJC','PNJ','LUMIÈRE (đề xuất)']:[];body=`<div class="panel"><div class="toolbar"><h2>${names[section]}</h2><button class="button button-outline" data-demo="new">+ Thêm mới (demo)</button></div>${data.length?'<div class="table-wrap"><table class="data-table"><thead><tr><th>STT</th><th>Tên</th><th>Thao tác</th></tr></thead><tbody>'+data.map((name,i)=>`<tr><td>${i+1}</td><td>${esc(name)}</td><td><button class="button-sm" data-demo="edit">Sửa</button></td></tr>`).join('')+'</tbody></table></div>':'<div class="empty-panel">Chưa có dữ liệu nghiệp vụ từ PostgreSQL.</div>'}<p class="demo-note">Trang quản trị đã có giao diện, nhưng thêm/sửa/xóa và thống kê cần API có xác thực role admin.</p></div>`}const gate=user&&user.role==='admin'?'':'<div class="demo-note">CHẾ ĐỘ XEM TRƯỚC GIAO DIỆN ADMIN. Chưa được cấp quyền quản trị; mọi thao tác quản trị bị vô hiệu. Backend phải chặn API bằng role admin.</div>';content.innerHTML=`<div class="admin-layout">${sidebar}<div>${gate}${body}</div></div>`}
function staffPage(){const kind=page.slice(6);if(kind==='inventory' && typeof window.LUMIERE_STAFF_INVENTORY==='function'){content.innerHTML=`<div class="admin-layout"><nav class="admin-side"><a href="orders.html">Xử lý đơn</a><a class="active" href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div id="staff-inventory-mount"></div></div>`;window.LUMIERE_STAFF_INVENTORY({mount:document.querySelector('#staff-inventory-mount'),products:P});return;}if(kind==='orders' && typeof window.LUMIERE_STAFF_ORDERS==='function'){content.innerHTML=`<div class="admin-layout"><nav class="admin-side"><a class="active" href="orders.html">Xử lý đơn</a><a href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div id="staff-orders-mount"></div></div>`;window.LUMIERE_STAFF_ORDERS({mount:document.querySelector('#staff-orders-mount')});return;}content.innerHTML=`<div class="admin-layout"><nav class="admin-side"><a href="orders.html">Xử lý đơn</a><a href="inventory.html">Tồn kho</a><a href="../../index.html">Về cửa hàng</a></nav><div class="panel"><h2>${kind==='orders'?'Đơn hàng cần xử lý':'Kiểm tra tồn kho'}</h2><p class="demo-note">GIAO DIỆN DEMO. Backend phải yêu cầu role staff hoặc admin trước khi truy xuất dữ liệu nghiệp vụ.</p>${kind==='inventory'?'<div class="table-wrap"><table class="data-table"><thead><tr><th>Sản phẩm</th><th>Tồn kho demo</th></tr></thead><tbody>'+P.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.stock}</td></tr>`).join('')+'</tbody></table></div>':'<div class="empty-panel">Chưa có đơn hàng thực để xử lý.</div>'}</div></div>`}
function adminPage(){window.LUMIERE_BACKEND_CONSOLE({mount:content,section:page.slice(6),role:'admin'})}
function staffPage(){window.LUMIERE_BACKEND_CONSOLE({mount:content,section:page.slice(6),role:'staff'})}
function favorite(id){
  if(!user||user.role!=='customer'){notify('Đăng nhập bằng tài khoản khách hàng để dùng danh sách yêu thích.',true);return}
  const productId=Number(id);
  LUMIERE_API.wishlist().then(async result=>{
    const saved=result.items.some(item=>item.product.id===productId);
    if(saved){await LUMIERE_API.removeWishlist(productId);wishlistIds.delete(productId)}
    else{await LUMIERE_API.addWishlist(productId);wishlistIds.add(productId)}
    notify(saved?'Đã bỏ yêu thích':'Đã thêm vào yêu thích');if(page==='wishlist')wishlist();
  }).catch(error=>notify(error.message,true));
}
let wishlistIds=new Set();
function account(){
  if(!user){content.innerHTML='<div class="empty-panel">Bạn chưa đăng nhập. <a class="inline-link" href="login.html">Đăng nhập</a></div>';return}
  content.innerHTML=`<div class="two-col"><section class="panel"><h2>Thông tin tài khoản</h2>${errorBox}
    <form id="profile-form">${formField('profile-name','Họ tên','text',`value="${esc(user.full_name)}" minlength="2" maxlength="150" required`)}
    ${formField('profile-phone','Số điện thoại','tel',`value="${esc(user.phone||'')}" maxlength="20"`)}
    ${formField('profile-email','Email','email',`value="${esc(user.email)}" disabled`)}
    <p>Vai trò: ${esc(user.role)}</p><button class="button button-dark">Cập nhật hồ sơ</button></form></section>
    <section class="panel"><h2>Tài khoản</h2><p><a href="orders.html">Đơn hàng của tôi</a></p><p><a href="wishlist.html">Danh sách yêu thích</a></p><p><a href="reviews.html">Đánh giá của tôi</a></p><button class="button button-outline" id="logout-main">Đăng xuất</button></section></div>`;
  $('#profile-form').onsubmit=async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;try{user=await LUMIERE_API.updateProfile({full_name:get('profile-name'),phone:get('profile-phone')||null});notify('Đã cập nhật hồ sơ');account()}catch(error){alert(error.message)}finally{button.disabled=false}};
  $('#logout-main').onclick=logout;
}
async function wishlist(){
  if(!user||user.role!=='customer'){content.innerHTML='<div class="empty-panel">Đăng nhập bằng tài khoản khách hàng để xem yêu thích. <a href="login.html">Đăng nhập</a></div>';return}
  content.innerHTML='<div class="empty-panel">Đang tải danh sách yêu thích…</div>';
  try{
    const result=await LUMIERE_API.wishlist();wishlistIds=new Set(result.items.map(item=>item.product.id));
    const rows=result.items.map(item=>{const p=item.product;return {...p,category:p.category?.name||'',material:p.material?.name||'',brand:p.brand?.name||'',gem:p.gemstone?.name||'',collection:p.collection?.name||'',price:Number(p.price_vnd),image:LUMIERE_CATEGORY_IMAGES[p.category?.name]||LUMIERE_CATEGORY_IMAGES.Charm}}).map(p=>`<article class="catalog-card"><a href="${root}pages/product-detail.html?id=${p.id}"><img src="${esc(p.image)}" alt="${esc(p.name)}"></a><div class="meta"><h3>${esc(p.name)}</h3><strong>${money(p.price)}</strong><button class="button-sm" data-favorite="${p.id}">Bỏ yêu thích</button></div></article>`).join('');
    content.innerHTML=`<div class="catalog-grid">${rows||'<div class="empty-panel">Chưa có sản phẩm yêu thích.</div>'}</div>`;
  }catch(error){content.innerHTML=`<div class="empty-panel">${esc(error.message)}</div>`}
}
function checkout(){
  if(!cartLines().length){content.innerHTML='<div class="empty-panel">Giỏ hàng trống. <a href="products.html">Mua sắm ngay</a></div>';return}
  const statusLabels={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',packing:'Đang đóng gói',shipping:'Đang giao',delivered:'Đã giao',cancelled:'Đã hủy'};
  content.innerHTML=`<div class="two-col"><section class="panel"><h2>Thông tin người nhận</h2>${errorBox}<form id="checkout-form">
    ${formField('recipient','Họ và tên','text','required autocomplete="name"')}
    ${formField('phone','Số điện thoại','tel','required pattern="0[0-9]{9}"')}
    ${formField('address','Địa chỉ nhận hàng','text','required minlength="5"')}
    ${formField('province','Tỉnh / thành phố','text','required')}
    ${formField('coupon-code','Mã giảm giá','text','maxlength="24" autocomplete="off"')}
    <button id="coupon-validate" class="button button-outline" type="button">Kiểm tra mã giảm giá</button><p id="coupon-result" role="status"></p>
    <p class="mini-note">Thanh toán khi nhận hàng (COD). VNPay chưa được kích hoạt.</p>
    <button class="button button-dark button-wide" type="submit">ĐẶT HÀNG COD</button></form></section>
    <aside class="summary-card"><h2>Đơn hàng</h2>${cartLines().map(({p,qty,lineTotal})=>`<div class="summary-line"><span>${esc(p.name)} × ${qty}</span><strong>${money(lineTotal)}</strong></div>`).join('')}
    <div class="summary-line"><span>Tạm tính theo Business API</span><strong>${money(subtotal())}</strong></div><p>Phí vận chuyển và giảm giá được Backend tính khi tạo đơn.</p></aside></div>`;
  let couponCode=null;
  $('#coupon-validate').onclick=async()=>{const output=$('#coupon-result');output.textContent='Đang kiểm tra…';try{const result=await LUMIERE_API.validateCoupon(get('coupon-code'));if(!result.valid)throw new Error(result.reason||'Mã giảm giá không hợp lệ');couponCode=result.coupon_code;output.textContent=`Giảm ${money(result.discount_vnd)} · Tổng sau giảm ${money(result.total_vnd)}`}catch(error){couponCode=null;output.textContent=error.message}};
  $('#checkout-form').onsubmit=async event=>{event.preventDefault();if(!user||user.role!=='customer'){alert('Đăng nhập bằng tài khoản khách hàng để đặt hàng.');return}if(couponCode&&get('coupon-code').toUpperCase()!==couponCode){alert('Mã giảm giá đã thay đổi. Hãy kiểm tra lại mã.');return}
    const button=event.currentTarget.querySelector('button[type="submit"]');button.disabled=true;
    try{const order=await LUMIERE_API.createOrder({recipient_name:get('recipient'),phone:get('phone'),address:get('address')+', '+get('province'),payment_method:'cod',...(couponCode?{coupon_code:couponCode}:{})});
      cartData={items:[],total_quantity:0,subtotal_vnd:'0.00'};
      content.innerHTML=`<section class="panel"><h2>Đặt hàng thành công</h2><p>Mã đơn: <strong>${esc(order.code)}</strong></p><p>Tổng tiền: <strong>${money(order.total_vnd)}</strong></p><p>Trạng thái: ${esc(statusLabels[order.status]||order.status)}</p><p>Thanh toán: COD · ${esc(order.payment_status)}</p><a class="button button-dark" href="orders.html">Xem đơn hàng</a></section>`;
    }catch(error){alert(error.message);button.disabled=false}
  };
}
async function showProductReviews(){
  const id=Number(new URLSearchParams(location.search).get('id'));if(!Number.isInteger(id)||id<1)return;
  const section=document.createElement('section');section.className='panel';section.innerHTML='<h2>Đánh giá sản phẩm</h2><p>Đang tải đánh giá…</p>';content.append(section);
  try{const result=await LUMIERE_API.reviews(id);section.innerHTML=`<h2>Đánh giá sản phẩm</h2>${result.items.map(review=>`<article><strong>${esc(review.author_display_name)}</strong> · ${review.rating}/5<p>${esc(review.comment)}</p></article>`).join('')||'<p>Chưa có đánh giá.</p>'}
    ${user?.role==='customer'?`<form id="review-form"><label>Điểm đánh giá <select name="rating"><option value="5">5</option><option value="4">4</option><option value="3">3</option><option value="2">2</option><option value="1">1</option></select></label><label for="review-comment">Nhận xét</label><textarea id="review-comment" required maxlength="2000"></textarea><button class="button button-dark">Gửi đánh giá</button><p id="review-error" role="alert"></p></form>`:'<p>Đăng nhập bằng tài khoản khách hàng để đánh giá sản phẩm đã mua.</p>'}`;
    section.querySelector('#review-form')?.addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;try{await LUMIERE_API.createReview(id,{rating:Number(event.currentTarget.elements.rating.value),comment:section.querySelector('#review-comment').value});await showProductReviews()}catch(error){section.querySelector('#review-error').textContent=error.message;button.disabled=false}});
  }catch(error){section.innerHTML=`<h2>Đánh giá sản phẩm</h2><p>${esc(error.message)}</p>`}
}
async function showMyReviews(){
  if(!user||user.role!=='customer'){content.innerHTML='<div class="empty-panel">Đăng nhập bằng tài khoản khách hàng để xem đánh giá của bạn. <a href="login.html">Đăng nhập</a></div>';return}
  try{const result=await LUMIERE_API.reviews();content.innerHTML=`<section class="panel"><h2>Đánh giá của tôi</h2>${result.items.map(review=>`<article><h3>${esc(review.author_display_name)} · ${review.rating}/5</h3><p>${esc(review.comment)}</p><a href="product-detail.html?id=${review.product_id}">Xem sản phẩm</a> <button class="button-sm" data-review-edit="${review.id}" data-rating="${review.rating}">Sửa</button> <button class="button-sm" data-review-delete="${review.id}">Xóa</button></article>`).join('')||'<p>Bạn chưa có đánh giá.</p>'}</section>`;
    content.querySelectorAll('[data-review-edit]').forEach(button=>button.onclick=async()=>{const rating=Number(window.prompt('Điểm từ 1 đến 5:',button.dataset.rating));if(!Number.isInteger(rating)||rating<1||rating>5)return;const comment=window.prompt('Nội dung đánh giá:');if(comment===null)return;try{await LUMIERE_API.updateReview(button.dataset.reviewEdit,{rating,comment});await showMyReviews()}catch(error){notify(error.message,true)}});
    content.querySelectorAll('[data-review-delete]').forEach(button=>button.onclick=async()=>{if(!window.confirm('Xóa đánh giá này?'))return;try{await LUMIERE_API.deleteReview(button.dataset.reviewDelete);await showMyReviews()}catch(error){notify(error.message,true)}});
  }catch(error){content.innerHTML=`<div class="empty-panel">${esc(error.message)}</div>`}
}
function staticPage(){
  if(page==='reviews'){showMyReviews();return}
  if(page==='contact'){content.innerHTML='<div class="panel"><h2>Liên hệ</h2><p>Backend hiện chưa cung cấp API tiếp nhận liên hệ; biểu mẫu chưa gửi dữ liệu.</p></div>';return}
  const descriptions={about:'LUMIÈRE kết hợp thương mại điện tử trang sức với hệ thống gợi ý và tư vấn AI.',collections:'Khám phá các thiết kế trang sức theo phong cách riêng.'};
  content.innerHTML=`<div class="panel"><h2>${page==='about'?'LUMIÈRE Jewelry':'Bộ sưu tập'}</h2><p>${descriptions[page]||''}</p>${page==='collections'?`<div class="catalog-grid">${P.slice(0,4).map(card).join('')}</div>`:''}</div>`;
}
async function logout(){try{await LUMIERE_API.logout();user=null;location.href=root+'pages/login.html'}catch(e){notify(e.message,true)}}
function render(){if(page==='products'||page==='search')catalog();else if(page==='product-detail')detail();else if(page==='cart')cartPage();else if(page==='checkout')checkout();else if(['login','register','forgot-password'].includes(page))auth(page);else if(page==='account')account();else if(['orders','order-detail'].includes(page))orders();else if(page==='wishlist')wishlist();else if(page.startsWith('admin-'))adminPage();else if(page.startsWith('staff-'))staffPage();else staticPage()}
document.addEventListener('click', e=>{
  const button=e.target.closest('button');
  if(!button) return;
  if(button.dataset.add) {
    add(button.dataset.add);
  } else if(button.dataset.favorite) {
    favorite(button.dataset.favorite);
  } else if(button.dataset.remove) {
    changeCartItem(button.dataset.remove,0,true);
  } else if(button.dataset.inc) {
    changeCartItem(button.dataset.inc,1);
  } else if(button.dataset.dec) {
    changeCartItem(button.dataset.dec,-1);
  } else if(button.dataset.demo) {
    demo();
  }
});
$('#nav-logout').onclick=logout;
(async()=>{
  content.innerHTML='<div class="empty-panel">Đang tải danh mục từ Business API…</div>';
  const [productsResult,authResult]=await Promise.allSettled([
    window.LUMIERE_LOAD_PRODUCTS ? window.LUMIERE_LOAD_PRODUCTS() : Promise.reject(Error('Thiếu products.js')),
    window.LUMIERE_API ? LUMIERE_API.me() : Promise.reject(Error('Thiếu api.js'))
  ]);
  if(authResult.status==='fulfilled'){
    user=authResult.value;
    $('#account-nav').textContent=user.full_name;
    $('#account-nav').href=root+'pages/account.html';
    $('#nav-logout').hidden=false;
  }
  if(productsResult.status==='rejected'){
    window.LUMIERE_PRODUCTS_ERROR=productsResult.reason?.message||'Không tải được dữ liệu sản phẩm.';
    console.error('LUMIERE products load failed:',productsResult.reason);
  }
  if(user && (page==="cart" || page==="checkout")) {
    try {
      cartData=await LUMIERE_API.getCart();
    } catch(error) {
      console.error("Không tải được giỏ hàng:",error);
      content.innerHTML=`<div class="empty-panel">${esc(error.message)}</div>`;
      return;
    }
  }

  if (user && ["admin", "staff"].includes(user.role)) {
    if (applyRoleNavigation()) return;
  }
  if (page.startsWith("admin-") && user?.role !== "admin") {
    location.replace(
      root + (user?.role === "staff"
        ? "pages/staff/orders.html"
        : user ? "pages/products.html" : "pages/login.html")
    );
    return;
  }
  if (page.startsWith("staff-") && user?.role !== "staff") {
    location.replace(
      root + (user?.role === "admin"
        ? "pages/admin/dashboard.html"
        : user ? "pages/products.html" : "pages/login.html")
    );
    return;
  }

  if(page.startsWith("admin-")||page.startsWith("staff-")){
    try{await import(new URL(root+"assets/js/backend-console.js",document.baseURI).href)}catch(error){content.innerHTML=`<div class="empty-panel">Không tải được giao diện nghiệp vụ: ${esc(error.message)}</div>`;console.error(error);return}
  }
  render();
  if(page==="product-detail")showProductReviews();
})();
})();
