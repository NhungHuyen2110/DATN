const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localTime=value=>{const date=new Date(value);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16)};

export function openCouponEditor({api,coupon=null,onSaved}){
  const dialog=document.createElement('dialog');dialog.className='product-editor';dialog.setAttribute('aria-labelledby','coupon-editor-title');
  const row=coupon||{code:'',discount_type:'percent',discount_value:'10',min_order_vnd:'0',max_discount_vnd:null,usage_limit:null,is_active:true,description:'',starts_at:new Date(Date.now()-60000),ends_at:new Date(Date.now()+30*86400000)};
  const field=(name,label,type='text',extra='')=>`<label class="pe-field">${label}<input name="${name}" type="${type}" value="${esc(row[name]??'')}" ${extra}></label>`;
  dialog.innerHTML = `<form class="pe-form"><header class="pe-header"><div><span class="pe-eyebrow">LUMIÈRE · ƯU ĐÃI</span><h2 id="coupon-editor-title">${coupon ? "Chỉnh sửa mã giảm giá" : "Tạo mã giảm giá"}</h2><p>Thiết lập chương trình ưu đãi dành cho khách hàng.</p></div><button class="pe-close" type="button" aria-label="Đóng">×</button></header>
    <div class="pe-body pe-coupon-body"><div class="pe-grid">
      ${field("code", "Mã giảm giá", "text", 'required minlength="3" maxlength="24" pattern="[A-Za-z0-9_-]{3,24}"')}
      <label class="pe-field">Loại giảm<select name="discount_type"><option value="percent">Phần trăm (%)</option><option value="fixed">Số tiền (VNĐ)</option></select></label>
      ${field("discount_value", "Giá trị giảm", "number", 'required min="0.01" step="0.01"')}${field("min_order_vnd", "Đơn hàng tối thiểu (VNĐ)", "number", 'required min="0" step="0.01"')}
      ${field("max_discount_vnd", "Giảm tối đa (tùy chọn, VNĐ)", "number", 'min="0.01" step="0.01"')}${field("usage_limit", "Giới hạn lượt dùng (trống = không giới hạn)", "number", 'min="1" max="2147483647" step="1"')}
      <label class="pe-field">Bắt đầu<input name="starts_at" type="datetime-local" value="${localTime(row.starts_at)}" required></label>
      <label class="pe-field">Kết thúc<input name="ends_at" type="datetime-local" value="${localTime(row.ends_at)}" required></label>
      <label class="pe-field">Ghi chú<input name="description" maxlength="500" value="${esc(row.description)}"></label>
      <label class="pe-field pe-checkbox"><span>Trạng thái</span><span><input name="is_active" type="checkbox" ${row.is_active ? "checked" : ""}> Bật mã giảm giá</span></label>
    </div><p class="pe-help">Mã giảm giá chỉ áp dụng trong thời gian hiệu lực và khi đơn hàng đáp ứng đầy đủ điều kiện ưu đãi.</p></div>
    <p class="pe-error" id="coupon-editor-error" role="alert" hidden></p><footer class="pe-footer"><span>Mỗi khách chỉ dùng một lượt đang hiệu lực cho một mã</span><div><button class="button button-outline" id="coupon-editor-cancel" type="button">Hủy</button><button class="button button-dark" type="submit">Lưu mã</button></div></footer></form>`;
  document.body.append(dialog);const form=dialog.querySelector('form'),submit=form.querySelector('[type="submit"]'),error=dialog.querySelector('#coupon-editor-error');
  let busy=false;
  form.elements.discount_type.value=row.discount_type;
  const syncType=()=>{const percent=form.elements.discount_type.value==='percent';form.elements.max_discount_vnd.disabled=!percent;form.elements.discount_value.max=percent?'100':''};
  syncType();form.elements.discount_type.onchange=syncType;
  for(const button of dialog.querySelectorAll('.pe-close,#coupon-editor-cancel'))button.onclick=()=>{if(!busy)dialog.close()};
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault()});dialog.addEventListener('close',()=>dialog.remove(),{once:true});
  form.onsubmit=async event=>{
    event.preventDefault();if(busy)return;error.hidden=true;
    const value=name=>form.elements.namedItem(name).value.trim();
    if(new Date(value('starts_at'))>=new Date(value('ends_at'))){error.hidden=false;error.textContent='Thời điểm kết thúc phải sau thời điểm bắt đầu.';return}
    busy=true;submit.disabled=true;
    try{
      const data={code:value('code').toUpperCase(),discount_type:value('discount_type'),discount_value:value('discount_value'),min_order_vnd:value('min_order_vnd'),max_discount_vnd:value('discount_type')==='percent'&&value('max_discount_vnd')?value('max_discount_vnd'):null,usage_limit:value('usage_limit')?Number(value('usage_limit')):null,starts_at:new Date(value('starts_at')).toISOString(),ends_at:new Date(value('ends_at')).toISOString(),description:value('description')||null,is_active:form.elements.is_active.checked};
      if(coupon)await api.updateCoupon(coupon.id,data);else await api.createCoupon(data);
      dialog.close();await onSaved();
    }catch(problem){error.hidden=false;error.textContent=problem.message}
    finally{busy=false;submit.disabled=false}
  };
  dialog.showModal();form.elements.code.focus();
}
