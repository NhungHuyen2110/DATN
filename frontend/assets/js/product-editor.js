const escapeText=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export async function openProductEditor({api,rows,product=null,onSaved}){
  const categories=await api.request('/categories');
  const brands=await api.request('/brands');
  const options=(key,provided)=>{
    const items=provided||[...new Map(rows.map(row=>[row[key]?.id,row[key]])).values()].filter(Boolean);
    return items.map(item=>`<option value="${item.id}">${escapeText(item.name)}</option>`).join('');
  };
  const input=(name,label,type='text',extra='')=>`<label class="pe-field">${label}<input name="${name}" type="${type}" ${extra} required></label>`;
  const select=(name,label,key,provided)=>`<label class="pe-field">${label}<select name="${name}" required>${options(key,provided)}</select></label>`;
  const dialog=document.createElement('dialog');
  dialog.className='product-editor';dialog.setAttribute('aria-labelledby','pe-title');
  const nextId=Math.max(0,...rows.map(row=>row.id))+1;
  dialog.innerHTML=`<form id="product-create-form" class="pe-form">
    <header class="pe-header"><div><span class="pe-eyebrow">LUMIÈRE · QUẢN LÝ DANH MỤC</span><h2 id="pe-title">${product?'Cập nhật ảnh sản phẩm':'Thêm sản phẩm mới'}</h2><p>${product?escapeText(product.name):'Thông tin và ảnh sẽ được lưu vào hệ thống bán hàng.'}</p></div><button class="pe-close" type="button" aria-label="Đóng">×</button></header>
    <div class="pe-body ${product?'pe-image-only':''}">
      ${product?'':`<div class="pe-details" data-product-details>
        <section><h3>01 <span>Thông tin sản phẩm</span></h3><div class="pe-grid">
        ${input('name','Tên sản phẩm','text','maxlength="255" class="pe-name"')}
        ${input('id','ID sản phẩm','number',`min="1" max="2147483647" value="${nextId}"`)}
        ${input('sku','SKU','text','maxlength="50"')}${input('barcode','Mã vạch','text','maxlength="50"')}
        ${select('category_id','Danh mục','category',categories)}${select('brand_id','Thương hiệu','brand',brands)}
        ${select('material_id','Chất liệu','material')}${select('gemstone_id','Đá quý','gemstone')}
        ${select('collection_id','Bộ sưu tập','collection')}${input('weight','Trọng lượng (g)','number','min="0.01" max="99999999.99" step="0.01"')}
        </div></section><section><h3>02 <span>Giá bán & tồn kho</span></h3><div class="pe-grid">
        ${input('sale_price','Giá bán (VNĐ)','number','min="0" step="0.01"')}${input('stock','Số lượng tồn','number','min="0" max="2147483647" step="1"')}
        ${input('wholesale_price','Giá sỉ (VNĐ)','number','min="0" step="0.01"')}${input('cost_price','Giá vốn (VNĐ)','number','min="0" step="0.01"')}
        </div></section></div>`}
      <aside class="pe-media"><h3>${product?'Ảnh đại diện':'03 Ảnh sản phẩm'}</h3>
        <div class="pe-upload"><img id="pe-preview" alt="Xem trước ảnh sản phẩm" hidden><div id="pe-placeholder"><span class="pe-plus">＋</span><strong>Chọn ảnh từ máy</strong><span>Nhấn để chọn hoặc kéo ảnh vào đây</span></div><input id="pe-file" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Chọn ảnh sản phẩm" ${product?'required':''}></div>
        <p id="pe-filename" class="pe-help">JPEG, PNG hoặc WebP · Tối đa 5 MB</p><p class="pe-help">Ảnh được lưu riêng, không ghi đè kho ảnh SKU cũ. ${product?'Bạn có thể chọn ảnh mới để thay ảnh đại diện.':'Có thể thêm ảnh sau nếu chưa có sẵn.'}</p>
        <button id="pe-clear-image" class="button button-outline" type="button" hidden>Bỏ ảnh đã chọn</button>
      </aside>
    </div><div id="create-product-error" class="pe-error" role="alert" hidden></div>
    <footer class="pe-footer"><span>* Kiểm tra mã sản phẩm và giá trước khi lưu</span><div><button class="button button-outline" id="cancel-create-product" type="button">Hủy</button><button class="button button-dark" type="submit">${product?'Lưu ảnh':'Lưu sản phẩm'}</button></div></footer>
  </form>`;
  document.body.append(dialog);
  const form=dialog.querySelector('form'),fileInput=dialog.querySelector('#pe-file'),preview=dialog.querySelector('#pe-preview');
  const error=dialog.querySelector('#create-product-error'),submit=form.querySelector('[type="submit"]');
  let previewUrl=null,createdId=product?.id||null,createdThisForm=false,finished=false,busy=false;
  const originalImage=product&&(product.image_url?api.base+product.image_url:window.LUMIERE_PRODUCTS?.find(p=>p.id===product.id)?.image);
  function updatePreview(){
    if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;
    const file=fileInput.files[0];
    if(file)previewUrl=URL.createObjectURL(file);
    const image=previewUrl||originalImage;
    preview.hidden=!image;preview.src=image||'';
    dialog.querySelector('#pe-placeholder').hidden=!!image;
    dialog.querySelector('#pe-clear-image').hidden=!file;
    dialog.querySelector('#pe-filename').textContent=file?`${file.name} · ${(file.size/1024/1024).toFixed(2)} MB`:'JPEG, PNG hoặc WebP · Tối đa 5 MB';
  }
  fileInput.addEventListener('change',updatePreview);
  dialog.querySelector('#pe-clear-image').onclick=()=>{fileInput.value='';updatePreview()};
  for(const button of dialog.querySelectorAll('.pe-close,#cancel-create-product'))button.onclick=()=>{if(!busy)dialog.close()};
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault()});
  dialog.addEventListener('close',()=>{
    if(previewUrl)URL.revokeObjectURL(previewUrl);
    dialog.remove();
    if(createdThisForm&&!finished)onSaved().catch(()=>{});
  },{once:true});
  form.onsubmit=async event=>{
    event.preventDefault();if(busy)return;
    error.hidden=true;
    const file=fileInput.files[0];
    if(file&&(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>5*1024*1024||file.size===0)){
      error.hidden=false;error.textContent='Chọn ảnh JPEG, PNG hoặc WebP có dung lượng tối đa 5 MB.';return;
    }
    busy=true;submit.disabled=true;submit.textContent='Đang lưu…';
    try{
      if(!createdId){
        const values=new FormData(form),payload={};
        for(const key of ['id','category_id','brand_id','material_id','gemstone_id','collection_id','stock'])payload[key]=Number(values.get(key));
        for(const key of ['sku','barcode','name','weight','sale_price','wholesale_price','cost_price'])payload[key]=String(values.get(key)).trim();
        const saved=await api.createProduct(payload);createdId=saved.id;createdThisForm=true;
        dialog.querySelectorAll('[data-product-details] input,[data-product-details] select').forEach(field=>field.disabled=true);
      }
      if(file)await api.uploadProductImage(createdId,file);
      finished=true;dialog.close();await onSaved();
    }catch(problem){
      error.hidden=false;error.textContent=(createdThisForm?`Sản phẩm #${createdId} đã được tạo. Ảnh chưa lưu được; chọn lại ảnh và bấm lưu để thử lại, không tạo thêm sản phẩm. `:'')+problem.message;
    }finally{busy=false;submit.disabled=false;submit.textContent=createdThisForm?'Thử lưu ảnh lại':product?'Lưu ảnh':'Lưu sản phẩm'}
  };
  updatePreview();dialog.showModal();(product?fileInput:form.elements.namedItem('name')).focus();
}
