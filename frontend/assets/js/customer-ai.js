/* LUMIÈRE AI assistant — vanilla JavaScript, standalone widget */
(() => {
  'use strict';
  if (document.getElementById('lumiere-ai-widget')) return;
  const API = window.LUMIERE_AI_BASE ? window.LUMIERE_AI_BASE.replace(/\/$/, '') + '/chat' : '';
  const REQUEST_TIMEOUT_MS = 50000;
  const root = document.createElement('div');
  root.id = 'lumiere-ai-widget';
  root.innerHTML = `
    <button type="button" class="lai-launch" aria-label="Mở trợ lý tư vấn trang sức" aria-expanded="false" aria-controls="lai-dialog"><span aria-hidden="true">✧</span> Tư vấn AI</button>
    <section id="lai-dialog" class="lai-dialog" role="dialog" aria-modal="false" aria-label="Trợ lý tư vấn LUMIÈRE" hidden>
      <header class="lai-head"><div><strong>✧ LUMIÈRE AI</strong><small>Gợi ý trang sức theo nhu cầu</small></div><button class="lai-close" type="button" aria-label="Đóng trò chuyện">×</button></header>
      <div class="lai-messages" role="log" aria-live="polite" aria-relevant="additions text"><div class="lai-msg lai-bot">Xin chào! Bạn cần tìm nhẫn, dây chuyền, bông tai hay trang sức theo ngân sách nào?</div></div>
      <form class="lai-form"><label class="lai-sr" for="lai-query">Nhập câu hỏi</label><input id="lai-query" type="text" maxlength="500" required autocomplete="off" placeholder="Ví dụ: Tìm nhẫn kim cương dưới 20 triệu"/><button type="submit" aria-label="Gửi câu hỏi">➤</button></form>
      <p class="lai-foot">Thông tin do AI hỗ trợ, vui lòng kiểm tra giá và tồn kho trước khi mua.</p>
    </section>`;
  document.body.append(root);
  const launch = root.querySelector('.lai-launch');
  const dialog = root.querySelector('.lai-dialog');
  const close = root.querySelector('.lai-close');
  const form = root.querySelector('.lai-form');
  const input = root.querySelector('#lai-query');
  const messages = root.querySelector('.lai-messages');
  const submit = form.querySelector('button[type=submit]');
  let pending = false;
  let conversationId = null;
  function toggle(open) {
    dialog.hidden = !open;
    launch.setAttribute('aria-expanded', String(open));
    if (open) input.focus(); else launch.focus();
  }
  launch.addEventListener('click', () => toggle(dialog.hidden));
  close.addEventListener('click', () => toggle(false));
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !dialog.hidden) toggle(false); });
  function message(text, css) {
    const el = document.createElement('div');
    el.className = `lai-msg ${css}`;
    el.textContent = String(text);
    messages.append(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }
  function productList(products) {
    if (!Array.isArray(products) || !products.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'lai-products';
    for (const p of products.slice(0, 10)) {
      if (!p || typeof p !== 'object') continue;
      const item = document.createElement('article');
      item.className = 'lai-product';
      const name = document.createElement('a');
      name.textContent = String(p.ProductName ?? p.name ?? 'Sản phẩm');
      const productId = Number(p.ProductID ?? p.id);
      if (Number.isSafeInteger(productId) && productId > 0) {
        name.href = '/pages/product-detail.html?id=' + productId;
      }
      const imagePath = window.LUMIERE_PRODUCT_IMAGE?.(p.SKU ?? p.sku, null);
      if (imagePath) {
        const photo = document.createElement('img');
        photo.src = imagePath;
        photo.alt = name.textContent;
        photo.loading = 'lazy';
        item.append(photo);
      }
      const meta = document.createElement('small');
      const priceValue = p.Price ?? p.SalePrice;
      const price = priceValue == null ? NaN : Number(priceValue);
      const fields = [p.Material ?? p.MaterialName, p.Gemstone ?? p.GemstoneName].filter(Boolean).map(String);
      if (Number.isFinite(price) && price >= 0) fields.push(price.toLocaleString('vi-VN') + ' ₫');
      if (Number.isInteger(p.Stock) && p.Stock >= 0) fields.push('Còn ' + p.Stock + ' sản phẩm');
      meta.textContent = fields.join(' · ');
      const id = document.createElement('small');
      id.textContent = p.ProductID != null ? `Mã sản phẩm: ${p.ProductID}` : '';
      item.append(name, meta, id);
      if (p.reason) {
        const reason = document.createElement('small');
        reason.textContent = String(p.reason);
        item.append(reason);
      }
      wrap.append(item);
    }
    if (wrap.children.length) {
      messages.append(wrap);
      messages.scrollTop = messages.scrollHeight;
    }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (pending) return;
    const query = input.value.trim();
    if (!query) return;
    input.value = '';
    message(query, 'lai-user');
    pending = true;
    submit.disabled = true;
    input.disabled = true;
    const loading = message('AI đang phân tích yêu cầu và tìm sản phẩm. Vui lòng đợi…', 'lai-bot lai-loading');
    try {
      if (!API) throw new Error('AI Service chưa được cấu hình trên môi trường này.');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      let response;
      try {
        response = await fetch(API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, top_k: 3, conversation_id: conversationId }),
          signal: controller.signal,
        });
      } finally { clearTimeout(timer); }
      const data = await response.json().catch(() => ({}));
      if (typeof data.conversation_id === 'string') conversationId = data.conversation_id;
      if (!response.ok || data.success === false) {
        const detail = typeof data.detail === 'string' ? data.detail :
          (typeof data.message === 'string' ? data.message : `AI Service trả lỗi HTTP ${response.status}.`);
        throw new Error(detail);
      }
      loading.remove();
      const answer = data.answer;
      message(typeof answer === 'string' && answer.trim() ? answer : 'AI đã phản hồi nhưng chưa có nội dung tư vấn.', 'lai-bot');
      productList(data.products);
    } catch (error) {
      loading.remove();
      const errorMessage = error?.name === 'AbortError'
        ? 'Phản hồi đang lâu hơn dự kiến. Bạn hãy thử lại sau; các chức năng mua sắm vẫn hoạt động.'
        : error instanceof TypeError
          ? 'Trợ lý tạm thời chưa kết nối được. Bạn vẫn có thể xem sản phẩm và đặt hàng; hãy thử lại sau.'
          : (error?.message || 'AI Service gặp lỗi không xác định.');
      message(errorMessage, 'lai-bot lai-error');
      console.warn('LUMIERE AI chatbot request failed:', error);
    } finally {
      pending = false; submit.disabled = false; input.disabled = false; input.focus();
    }
  });
})();
