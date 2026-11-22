'use strict';
// Không dùng framework. Frontend demo; checkout và tài khoản thật cần backend.
const $ = (sel, scope=document) => scope.querySelector(sel);
const $$ = (sel, scope=document) => [...scope.querySelectorAll(sel)];
const products = window.LUMIERE_PRODUCTS;
const money = n => Number(n).toLocaleString('vi-VN') + ' ₫';
const read = (key, fallback) => { try { const v=JSON.parse(localStorage.getItem(key));return v ?? fallback; } catch { return fallback; } };
const state = { filter:'Tất cả', sort:'featured', search:'', expanded:false, cart:read('lumiere_cart',{}), favorites:read('lumiere_favorites',[]) };
const save = () => { localStorage.setItem('lumiere_cart', JSON.stringify(state.cart)); localStorage.setItem('lumiere_favorites', JSON.stringify(state.favorites)); updateCounters(); };
const getProduct = id => products.find(p => p.id === Number(id));
let toastTimer;
function toast(text){ const el=$('#toast'); el.textContent=text;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),3200); }
function updateCounters(){const count=Object.values(state.cart).reduce((a,b)=>a+b,0);const c=$('#cart-count');c.textContent=count;c.hidden=!count;const w=$('#wishlist-count');w.textContent=state.favorites.length;w.hidden=!state.favorites.length;}
function filtered(){let items=products.filter(p=>(state.filter==='Tất cả'||p.category===state.filter)&&`${p.name} ${p.category} ${p.material} ${p.gem}`.toLocaleLowerCase('vi').includes(state.search.toLocaleLowerCase('vi')));if(state.sort==='price-asc')items.sort((a,b)=>a.price-b.price);if(state.sort==='price-desc')items.sort((a,b)=>b.price-a.price);if(state.sort==='name')items.sort((a,b)=>a.name.localeCompare(b.name,'vi'));return items;}
function card(p){const fav=state.favorites.includes(p.id),name=escapeHtml(p.name),category=escapeHtml(p.category),material=escapeHtml(p.material),image=escapeHtml(p.image);return `<article class="product-card"><div class="product-picture"><button class="wish-btn ${fav?'is-active':''}" data-action="favorite" data-id="${p.id}" aria-label="${fav?'Bỏ yêu thích':'Yêu thích'} ${name}">${fav?'♥':'♡'}</button>${p.tag?`<span class="product-tag">${escapeHtml(p.tag)}</span>`:''}<button class="picture-button" data-action="detail" data-id="${p.id}" aria-label="Xem ${name}"><img src="${image}" loading="lazy" alt="${name}" onerror="this.style.opacity='.2'"></button><button class="quick-add" data-action="add" data-id="${p.id}" ${p.stock<=0?'disabled':''}>+ Thêm vào giỏ</button></div><div class="product-info"><span>${category} · ${material}</span><button class="product-name" data-action="detail" data-id="${p.id}">${name}</button><strong>${money(p.price)}</strong></div></article>`;}
function renderProducts(){const all=filtered();const shown=state.expanded?all:all.slice(0,8);$('#product-grid').innerHTML=shown.length?shown.map(card).join(''):'<div class="empty-state">Không tìm thấy sản phẩm phù hợp. Hãy thử từ khóa khác.</div>';$('#product-count').textContent=`Hiển thị ${shown.length} / ${all.length} sản phẩm`;$('#show-more').hidden=all.length<=8;$('#show-more').textContent=state.expanded?'THU GỌN ↑':'XEM THÊM SẢN PHẨM ↗';}
function setFilter(category){state.filter=category;state.expanded=false;$$('.filter-chip').forEach(el=>el.classList.toggle('active',el.dataset.filter===category));renderProducts();}
function addToCart(id, qty=1){const p=getProduct(id);if(!p)return;const current=state.cart[id]||0;if(current+qty>p.stock){toast(`Tồn kho chỉ còn ${p.stock} sản phẩm`);return;}state.cart[id]=current+qty;save();toast(`Đã thêm ${p.name} vào giỏ hàng`);if(!$('#drawer').hidden && $('#drawer-title').textContent==='Giỏ hàng')showCart();}
function toggleFav(id){id=Number(id);state.favorites=state.favorites.includes(id)?state.favorites.filter(x=>x!==id):[...state.favorites,id];save();renderProducts();toast(state.favorites.includes(id)?'Đã thêm vào yêu thích':'Đã bỏ khỏi yêu thích');if(!$('#drawer').hidden && $('#drawer-title').textContent==='Yêu thích')showWishlist();}
function showDrawer(title, html){$('#drawer-title').textContent=title;$('#drawer-body').innerHTML=html;$('#drawer').hidden=false;$('#overlay').hidden=false;document.body.classList.add('no-scroll');}
function closeDrawer(){$('#drawer').hidden=true;$('#overlay').hidden=true;document.body.classList.remove('no-scroll');}
function showCart(){const entries=Object.entries(state.cart).map(([id,qty])=>({p:getProduct(id),qty})).filter(x=>x.p);const subtotal=entries.reduce((sum,{p,qty})=>sum+p.price*qty,0);const shipping=subtotal>=2000000||subtotal===0?0:30000;const rows=entries.length?entries.map(({p,qty})=>`<div class="mini-item"><img src="${p.image}" alt=""><div><h3>${p.name}</h3><p>${money(p.price)}</p><div class="qty"><button data-action="decrease" data-id="${p.id}" aria-label="Giảm">−</button><span>${qty}</span><button data-action="increase" data-id="${p.id}" aria-label="Tăng">+</button></div><button class="small-link" data-action="remove" data-id="${p.id}">Xóa</button></div></div>`).join(''):'<p class="empty-drawer">Giỏ hàng đang trống. Hãy khám phá sản phẩm bạn yêu thích.</p>';showDrawer('Giỏ hàng',`${rows}<div class="drawer-summary"><div><span>Tạm tính</span><strong>${money(subtotal)}</strong></div><div><span>Vận chuyển (minh họa)</span><strong>${money(shipping)}</strong></div><div class="total"><span>Tổng dự kiến</span><strong>${money(subtotal+shipping)}</strong></div><button class="button button-dark button-full" id="checkout-demo" ${!entries.length?'disabled':''}>TIẾP TỤC ĐẶT HÀNG ↗</button><p>Giỏ hàng lưu trên thiết bị. Chưa kết nối đặt hàng/thanh toán thật.</p></div>`);}
function showWishlist(){const items=state.favorites.map(getProduct).filter(Boolean);showDrawer('Yêu thích',items.length?items.map(p=>`<div class="mini-item"><img src="${p.image}" alt=""><div><h3>${p.name}</h3><p>${money(p.price)}</p><button class="small-link" data-action="add" data-id="${p.id}">Thêm vào giỏ</button> · <button class="small-link" data-action="favorite" data-id="${p.id}">Bỏ yêu thích</button></div></div>`).join(''):'<p class="empty-drawer">Chưa có sản phẩm yêu thích.</p>');}
function showSearch(){showDrawer('Tìm kiếm',`<form id="search-form" class="search-form"><label for="search-term">Tìm theo tên, chất liệu, đá quý</label><input id="search-term" name="term" placeholder="Ví dụ: Nhẫn kim cương..." value="${escapeHtml(state.search)}" required maxlength="100"><button class="button button-dark button-full">TÌM SẢN PHẨM ↗</button></form><p class="hint">Tìm kiếm trong dữ liệu minh họa đang hiển thị.</p>`);setTimeout(()=>$('#search-term')?.focus(),50);}
function showAccount(){showDrawer('Tài khoản',`<div class="account-demo"><div class="account-icon">♙</div><h3>Chào mừng đến LUMIÈRE</h3><p>Đăng ký, đăng nhập, quên mật khẩu và phân quyền cần được xây dựng với Backend + PostgreSQL để sử dụng thật.</p><p class="hint">Đây là giao diện demo, không lưu hay xử lý mật khẩu trong trình duyệt.</p></div>`);}
function escapeHtml(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');}
function showDetail(id){const p=getProduct(id);if(!p)return;const name=escapeHtml(p.name),category=escapeHtml(p.category),material=escapeHtml(p.material),gem=escapeHtml(p.gem),image=escapeHtml(p.image);$('#modal-content').innerHTML=`<div class="detail-grid"><img src="${image}" alt="${name}"><div class="detail-copy"><div class="eyebrow">LUMIÈRE / ${category}</div><h2>${name}</h2><div class="detail-price">${money(p.price)}</div><p class="detail-description">Thông tin sản phẩm, giá và tồn kho được tải từ Business API.</p><dl><div><dt>Chất liệu</dt><dd>${material}</dd></div><div><dt>Đá quý</dt><dd>${gem}</dd></div><div><dt>Tồn kho</dt><dd>${p.stock} sản phẩm</dd></div></dl><button class="button button-dark button-full" data-action="add" data-id="${p.id}" ${p.stock<=0?'disabled':''}>THÊM VÀO GIỎ HÀNG ↗</button><button class="button button-outline button-full" data-action="favorite" data-id="${p.id}">♡ ${state.favorites.includes(p.id)?'BỎ YÊU THÍCH':'LƯU YÊU THÍCH'}</button></div></div>`;$('#product-modal').hidden=false;$('#overlay').hidden=false;document.body.classList.add('no-scroll');}
function closeModal(){$('#product-modal').hidden=true;$('#overlay').hidden=true;document.body.classList.remove('no-scroll');}
function showChat(){$('#chat-window').hidden=false;$('#chat-query').focus();}function closeChat(){$('#chat-window').hidden=true;}
function chatMessage(text,kind='bot'){const div=document.createElement('div');div.className=`message ${kind}`;div.textContent=text;$('#chat-messages').append(div);$('#chat-messages').scrollTop=$('#chat-messages').scrollHeight;return div;}
let homeAIPending=false;
async function askAI(query){
  if(homeAIPending)return;
  homeAIPending=true;
  const sendBtn=$('#chat-form button'),input=$('#chat-query');
  sendBtn.disabled=true;input.disabled=true;
  const pending=chatMessage('Đang tìm các sản phẩm phù hợp…','bot');
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),50000);
  try{
    if(!window.LUMIERE_AI_BASE)throw new Error('AI chưa được cấu hình.');
    const response=await fetch(window.LUMIERE_AI_BASE.replace(/\/$/,'')+'/chat',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query,top_k:3}),signal:controller.signal
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok||result.success===false)throw new Error('AI tạm thời chưa sẵn sàng.');
    pending.textContent=result.answer||'Chưa có sản phẩm phù hợp. Bạn có thể thử loại trang sức và ngân sách khác.';
    if(Array.isArray(result.products)&&result.products.length){
      const list=document.createElement('div');list.className='chat-products';
      for(const item of result.products.slice(0,10)){
        const id=Number(item.ProductID);
        if(!Number.isSafeInteger(id)||id<=0)continue;
        const el=document.createElement('div'),link=document.createElement('a');
        el.className='chat-product-linked';
        link.href='./pages/product-detail.html?id='+id;
        link.textContent='#'+id+' · '+String(item.ProductName||'Sản phẩm');
        const facts=document.createElement('small');
        facts.textContent=' · '+money(item.Price??item.SalePrice);
        if(Number.isInteger(item.Stock))facts.textContent+=' · Còn '+item.Stock+' sản phẩm';
        el.append(link,facts);
        if(item.reason){const reason=document.createElement('p');reason.textContent=String(item.reason);el.append(reason)}
        list.append(el);
      }
      $('#chat-messages').append(list);
    }
  }catch(error){
    pending.textContent=error.name==='AbortError'
      ?'Phản hồi đang lâu hơn dự kiến. Bạn hãy thử lại sau; các chức năng mua sắm vẫn hoạt động.'
      :'Trợ lý tạm thời chưa kết nối được. Bạn vẫn có thể xem sản phẩm và đặt hàng; hãy thử lại sau.';
  }finally{
    clearTimeout(timer);homeAIPending=false;sendBtn.disabled=false;input.disabled=false;
    $('#chat-messages').scrollTop=$('#chat-messages').scrollHeight;
  }
}
let homeUser=null,homeCart={items:[],total_quantity:0,subtotal_vnd:'0.00'},homeWishlist=new Set();
function updateCounters(){const cart=$('#cart-count');cart.textContent=homeCart.total_quantity||0;cart.hidden=!homeCart.total_quantity;const wishlist=$('#wishlist-count');wishlist.textContent=homeWishlist.size;wishlist.hidden=!homeWishlist.size}
async function addToCart(id,qty=1){if(!homeUser||homeUser.role!=='customer'){location.href='./pages/login.html';return}try{homeCart=await LUMIERE_API.addCartItem(Number(id),qty);updateCounters();toast('Đã cập nhật giỏ hàng');if(!$('#drawer').hidden&&$('#drawer-title').textContent==='Giỏ hàng')showCart()}catch(error){toast(error.message)}}
async function toggleFav(id){if(!homeUser||homeUser.role!=='customer'){location.href='./pages/login.html';return}try{const rows=await LUMIERE_API.wishlist(1,100);const saved=rows.items.some(item=>item.product.id===Number(id));if(saved){await LUMIERE_API.removeWishlist(id);homeWishlist.delete(Number(id))}else{await LUMIERE_API.addWishlist(Number(id));homeWishlist.add(Number(id))}renderProducts();updateCounters();if(!$('#drawer').hidden&&$('#drawer-title').textContent==='Yêu thích')showWishlist()}catch(error){toast(error.message)}}
async function showCart(){if(!homeUser){location.href='./pages/login.html';return}try{homeCart=await LUMIERE_API.getCart();updateCounters();const rows=homeCart.items.map(item=>{const p=products.find(row=>row.id===item.product.id);return p?`<div class="mini-item"><img src="${p.image}" alt=""><div><h3>${escapeHtml(p.name)}</h3><p>${money(item.unit_price_vnd)}</p><div class="qty"><button data-action="decrease" data-id="${p.id}">−</button><span>${item.quantity}</span><button data-action="increase" data-id="${p.id}">+</button></div><button class="small-link" data-action="remove" data-id="${p.id}">Xóa</button></div></div>`:''}).join('');showDrawer('Giỏ hàng',`${rows||'<p class="empty-drawer">Giỏ hàng đang trống.</p>'}<div class="drawer-summary"><div><span>Tạm tính</span><strong>${money(homeCart.subtotal_vnd)}</strong></div><button class="button button-dark button-full" id="checkout-demo" ${homeCart.items.length?'':'disabled'}>TIẾP TỤC THANH TOÁN ↗</button></div>`)}catch(error){toast(error.message)}}
async function showWishlist(){if(!homeUser||homeUser.role!=='customer'){location.href='./pages/login.html';return}try{const data=await LUMIERE_API.wishlist(1,100);homeWishlist=new Set(data.items.map(item=>item.product.id));const rows=data.items.map(item=>{const p=products.find(row=>row.id===item.product.id);return p?`<div class="mini-item"><img src="${p.image}" alt=""><div><h3>${escapeHtml(p.name)}</h3><p>${money(p.price)}</p><button class="small-link" data-action="add" data-id="${p.id}">Thêm vào giỏ</button> · <button class="small-link" data-action="favorite" data-id="${p.id}">Bỏ yêu thích</button></div></div>`:''}).join('');showDrawer('Yêu thích',rows||'<p class="empty-drawer">Chưa có sản phẩm yêu thích.</p>');updateCounters()}catch(error){toast(error.message)}}
async function changeHomeCart(id,action){if(!homeUser)return;const item=homeCart.items.find(row=>row.product.id===Number(id));if(!item)return;try{if(action==='remove'||(action==='decrease'&&item.quantity===1))homeCart=await LUMIERE_API.removeCartItem(item.id);else homeCart=await LUMIERE_API.updateCartItem(item.id,item.quantity+(action==='increase'?1:-1));updateCounters();showCart()}catch(error){toast(error.message)}}
// Sự kiện ủy quyền: các thẻ sinh động trong grid và drawer.
document.addEventListener('click',e=>{const target=e.target.closest('[data-action]');if(!target)return;const id=Number(target.dataset.id);const action=target.dataset.action;if(action==='add')addToCart(id);if(action==='favorite')toggleFav(id);if(action==='detail')showDetail(id);if(['remove','increase','decrease'].includes(action))changeHomeCart(id,action)});
$$('.filter-chip').forEach(btn=>btn.addEventListener('click',()=>setFilter(btn.dataset.filter)));
$$('[data-category]').forEach(el=>el.addEventListener('click',()=>setFilter(el.dataset.category)));
$('#sort-products').addEventListener('change',e=>{state.sort=e.target.value;renderProducts();});
$('#show-more').addEventListener('click',()=>{state.expanded=!state.expanded;renderProducts();});
$('#open-cart').addEventListener('click',showCart);$('#open-wishlist').addEventListener('click',showWishlist);$('#open-search').addEventListener('click',showSearch);
$('#drawer-close').addEventListener('click',closeDrawer);$('#modal-close').addEventListener('click',closeModal);$('#overlay').addEventListener('click',()=>{closeDrawer();closeModal();});
$('#drawer-body').addEventListener('submit',e=>{if(e.target.id!=='search-form')return;e.preventDefault();state.search=$('#search-term').value.trim();setFilter('Tất cả');closeDrawer();location.hash='shop';toast(`Tìm kiếm: ${state.search}`);});
$('#drawer-body').addEventListener('click',e=>{if(e.target.id==='checkout-demo'){window.location.href='./pages/checkout.html';}});
$('#chat-fab').addEventListener('click',showChat);$('#open-chat-section').addEventListener('click',showChat);$('#footer-chat').addEventListener('click',showChat);$('#chat-close').addEventListener('click',closeChat);
$('#chat-form').addEventListener('submit',async e=>{e.preventDefault();const input=$('#chat-query');const query=input.value.trim();if(!query)return;chatMessage(query,'user');input.value='';await askAI(query);});
$('#menu-toggle').addEventListener('click',()=>{const nav=$('#main-nav');nav.classList.toggle('open');$('#menu-toggle').setAttribute('aria-expanded',nav.classList.contains('open'));});
$$('.main-nav a').forEach(el=>el.addEventListener('click',()=>{$('#main-nav').classList.remove('open');$('#menu-toggle').setAttribute('aria-expanded','false');}));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeDrawer();closeModal();closeChat();}});
(async()=>{
  try{
    await window.LUMIERE_LOAD_PRODUCTS();
  }catch(error){
    $('#product-grid').innerHTML=`<div class="empty-state">Không tải được dữ liệu sản phẩm từ Business API: ${escapeHtml(error.message)}</div>`;
    $('#product-count').textContent='Danh mục tạm thời không khả dụng.';
    $('#show-more').hidden=true;
    console.error('LUMIERE catalog failed:',error);
    return;
  }
  try{homeUser=await LUMIERE_API.me()}catch{homeUser=null}
  if(homeUser?.role==='admin'){location.replace('./pages/admin/dashboard.html');return}
  if(homeUser?.role==='staff'){location.replace('./pages/staff/orders.html');return}
  if(homeUser?.role==='customer'){
    try{homeCart=await LUMIERE_API.getCart()}catch(error){toast(error.message)}
    try{const saved=await LUMIERE_API.wishlist(1,100);homeWishlist=new Set(saved.items.map(item=>item.product.id))}catch(error){toast(error.message)}
  }
  state.favorites=[...homeWishlist];
  updateCounters();
  renderProducts();
  $('#product-count').textContent=`Hiển thị 8 / ${products.length} sản phẩm · Giá và tồn kho từ Business API`;
})();
