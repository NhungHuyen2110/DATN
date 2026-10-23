/* Business Catalog API (PostgreSQL :8001); ProductID remains identical to the AI dataset. */
window.LUMIERE_PRODUCTS = [];
window.LUMIERE_PRODUCTS_ERROR = null;
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
    if (!window.LUMIERE_API || typeof window.LUMIERE_API.request !== 'function') {
      throw new Error('Thiếu api.js hoặc LUMIERE_API.request');
    }

    // Business API paginates up to 100 products per request. The existing site.js
    // needs the full catalog for client-side filters/cart/admin/AI recommendations.
    const pageSize = 100;
    const first = await window.LUMIERE_API.request('/products?page=1&page_size=' + pageSize);
    if (!first || !Array.isArray(first.items) || !Number.isSafeInteger(first.total) || first.total < 0) {
      throw new Error('Business API trả dữ liệu danh mục không hợp lệ');
    }
    const pages = Math.ceil(first.total / pageSize);
    if (pages > 100) throw new Error('Danh mục quá lớn cho chế độ tải toàn bộ; cần phân trang phía server');

    const remaining = await Promise.all(Array.from({length: Math.max(0, pages - 1)}, (_, i) =>
      window.LUMIERE_API.request('/products?page=' + (i + 2) + '&page_size=' + pageSize)
    ));
    const rows = [...first.items];
    for (const part of remaining) {
      if (!part || !Array.isArray(part.items) || part.total !== first.total) {
        throw new Error('Dữ liệu phân trang bị thay đổi khi đang tải');
      }
      rows.push(...part.items);
    }
    if (rows.length !== first.total) throw new Error('Thiếu sản phẩm khi tải các trang Backend');

    const mapped = rows.map(row => {
      const category = String(row.category?.name || 'Khác');
      return {
        id: Number(row.id),
        name: String(row.name || ''),
        category,
        categoryId: Number(row.category?.id || 0),
        brand: String(row.brand?.name || ''),
        brandId: Number(row.brand?.id || 0),
        material: String(row.material?.name || ''),
        gem: String(row.gemstone?.name || ''),
        collection: String(row.collection?.name || ''),
        price: Number(row.price_vnd),
        stock: Number(row.stock),
        sku: String(row.sku || ''),
        image: LUMIERE_CATEGORY_IMAGES[category] || LUMIERE_CATEGORY_IMAGES.Charm,
        imageDemo: true,
        tag: ''
      };
    });
    if (mapped.some(p => !Number.isSafeInteger(p.id) || p.id <= 0 || !p.name ||
      !Number.isFinite(p.price) || p.price < 0 || !Number.isSafeInteger(p.stock) || p.stock < 0)) {
      throw new Error('Một số sản phẩm Backend có ID, giá hoặc tồn kho không hợp lệ');
    }
    if (new Set(mapped.map(p => p.id)).size !== mapped.length) throw new Error('ProductID trùng trong Backend');

    // Mutate in place because site.js and admin/staff modules hold this array reference.
    window.LUMIERE_PRODUCTS.splice(0, window.LUMIERE_PRODUCTS.length, ...mapped);
    window.LUMIERE_PRODUCTS_ERROR = null;
    return mapped;
  } catch (error) {
    window.LUMIERE_PRODUCTS_ERROR = error.message || 'Không thể kết nối Backend API';
    throw error;
  }
};
