/* LUMIÈRE AI assistant — vanilla JavaScript, standalone widget */
(() => {
  'use strict';
  if (document.getElementById('lumiere-ai-widget')) return;
  const API = 'http://127.0.0.1:8000/chat';
  const REQUEST_TIMEOUT_MS = 240000; // Thời gian chờ thử nghiệm cho CrewAI + Ollama
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
    for (const p of products.slice(0, 5)) {
      if (!p || typeof p !== 'object') continue;
      const item = document.createElement('article');
      item.className = 'lai-product';
      const name = document.createElement('strong');
      name.textContent = String(p.ProductName ?? p.name ?? 'Sản phẩm');
      const meta = document.createElement('small');
      const priceValue = p.Price ?? p.SalePrice;
      const price = priceValue == null ? NaN : Number(priceValue);
      const fields = [p.Material ?? p.MaterialName, p.Gemstone ?? p.GemstoneName].filter(Boolean).map(String);
      if (Number.isFinite(price) && price >= 0) fields.push(price.toLocaleString('vi-VN') + ' ₫');
      meta.textContent = fields.join(' · ');
      const id = document.createElement('small');
      id.textContent = p.ProductID != null ? `Mã AI: ${p.ProductID}` : '';
      item.append(name, meta, id);
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
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      let response;
      try {
        response = await fetch(API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, top_k: 3 }),
          signal: controller.signal,
        });
      } finally { clearTimeout(timer); }
      const data = await response.json().catch(() => ({}));
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
        ? 'AI xử lý vượt thời gian chờ (4 phút). Bạn hãy kiểm tra log AI và thử lại.'
        : error instanceof TypeError
          ? 'Không thể kết nối tới AI Service. Hãy kiểm tra cổng 8000, CORS và tab Network.'
          : (error?.message || 'AI Service gặp lỗi không xác định.');
      message(errorMessage, 'lai-bot lai-error');
      console.warn('LUMIERE AI chatbot request failed:', error);
    } finally {
      pending = false; submit.disabled = false; input.disabled = false; input.focus();
    }
  });
})();
