/* 500 products from AI API — source of identity is ProductID, never demo IDs. */
window.LUMIERE_PRODUCTS = [];
window.LUMIERE_PRODUCTS_ERROR = null;
const LUMIERE_AI_BASE = 'http://127.0.0.1:8000';
const LUMIERE_CATEGORY_IMAGES = {
  'Nhẫn': 'https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=700&q=80',
  'Dây chuyền': 'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=700&q=80',
  'Bông tai': 'https://images.unsplash.com/photo-1630019852942-f89202989a59?w=700&q=80',
  'Vòng tay': 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=700&q=80',
  'Lắc tay': 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=700&q=80',
  'Charm': 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=700&q=80'
};
window.LUMIERE_LOAD_PRODUCTS = async function () {
  try {
    const response = await fetch(LUMIERE_AI_BASE + '/products', {signal: AbortSignal.timeout(25000)});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const payload = await response.json();
    if (!payload.success || !Array.isArray(payload.data)) throw new Error('Dữ liệu API không hợp lệ');
    const mapped = payload.data.map(row => ({
      id: Number(row.ProductID),
      name: String(row.ProductName || ''),
      category: String(row.CategoryName || 'Khác'),
      brand: String(row.BrandName || ''),
      material: String(row.MaterialName || ''),
      gem: String(row.GemstoneName || ''),
      collection: String(row.CollectionName || ''),
      price: Number(row.SalePrice),
      stock: Number(row.Stock),
      image: LUMIERE_CATEGORY_IMAGES[row.CategoryName] || LUMIERE_CATEGORY_IMAGES.Charm,
      imageDemo: true,
      tag: ''
    })).filter(p => Number.isInteger(p.id) && p.id > 0 && p.name && Number.isFinite(p.price) && p.price >= 0 && Number.isInteger(p.stock) && p.stock >= 0);
    if (new Set(mapped.map(p=>p.id)).size !== mapped.length) throw new Error('ProductID trùng');
    window.LUMIERE_PRODUCTS.splice(0, window.LUMIERE_PRODUCTS.length, ...mapped);
    window.LUMIERE_PRODUCTS_ERROR = null;
    return mapped;
  } catch(error) {
    window.LUMIERE_PRODUCTS_ERROR = error.message || 'Không thể kết nối AI API';
    throw error;
  }
};
