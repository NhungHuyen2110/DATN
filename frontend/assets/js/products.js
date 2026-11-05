/* Business API owns product identity, price and stock; AI is used only for recommendations and chat. */
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
    if (!window.LUMIERE_API) {
      throw new Error("Business API chưa sẵn sàng");
    }
    const rows = [];
    const pageSize = 100;
    let page = 1;
    let total = null;
    do {
      const payload = await window.LUMIERE_API.products(page, pageSize);
      if (!Array.isArray(payload.items) ||
          !Number.isInteger(payload.total)) {
        throw new Error("Dữ liệu Business API không hợp lệ");
      }
      if (total === null) total = payload.total;
      rows.push(...payload.items);
      if (payload.items.length === 0 && rows.length < total) {
        throw new Error("Thiếu dữ liệu phân trang");
      }
      page++;
    } while (rows.length < total);
    const mapped = rows.map(row => {
      const category = row.category?.name || "Khác";
      return {
        id: Number(row.id),
        name: String(row.name || ""),
        category,
        brand: String(row.brand?.name || ""),
        material: String(row.material?.name || ""),
        gem: String(row.gemstone?.name || ""),
        collection: String(row.collection?.name || ""),
        price: Number(row.price_vnd),
        stock: Number(row.stock),
        image: LUMIERE_CATEGORY_IMAGES[category] ||
               LUMIERE_CATEGORY_IMAGES.Charm,
        imageDemo: true,
        tag: ""
      };
    });
    if (mapped.some(p =>
      !Number.isInteger(p.id) ||
      p.id <= 0 ||
      !p.name ||
      !Number.isFinite(p.price) ||
      p.price < 0 ||
      !Number.isInteger(p.stock) ||
      p.stock < 0
    )) {
      throw new Error("Sản phẩm có dữ liệu không hợp lệ");
    }
    if (new Set(mapped.map(p => p.id)).size !== mapped.length) {
      throw new Error("Product ID bị trùng");
    }
    window.LUMIERE_PRODUCTS.splice(
      0,
      window.LUMIERE_PRODUCTS.length,
      ...mapped
    );
    window.LUMIERE_PRODUCTS_ERROR = null;
    return mapped;
  } catch (error) {
    window.LUMIERE_PRODUCTS_ERROR = error.message;
    throw error;
  }
};
