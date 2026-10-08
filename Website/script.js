// ============================================================
// CẤU HÌNH
// ============================================================

const API_URL =
    "http://127.0.0.1:8000";


// Sản phẩm đang xem
let currentProductId = 1;


// ============================================================
// FORMAT GIÁ
// ============================================================

function formatPrice(price) {

    if (price === null || price === undefined) {

        return "Liên hệ";

    }


    return Number(price).toLocaleString(
        "vi-VN"
    ) + " VNĐ";
}


// ============================================================
// LOAD PRODUCT
// ============================================================

async function loadProduct() {

    try {

        const response =
            await fetch(
                `${API_URL}/products/${currentProductId}`
            );


        const result =
            await response.json();


        if (!result.success) {

            console.error(
                "Không tìm thấy sản phẩm"
            );

            return;

        }


        const product =
            result.data;


        // Tên
        document.getElementById(
            "productName"
        ).textContent =
            product.ProductName;


        // Category
        document.getElementById(
            "productCategory"
        ).textContent =
            product.CategoryName;


        // Giá
        document.getElementById(
            "productPrice"
        ).textContent =
            formatPrice(
                product.SalePrice
            );


        // Brand
        document.getElementById(
            "productBrand"
        ).textContent =
            product.BrandName;


        // Material
        document.getElementById(
            "productMaterial"
        ).textContent =
            product.MaterialName;


        // Gemstone
        document.getElementById(
            "productGemstone"
        ).textContent =
            product.GemstoneName;


        // Collection
        document.getElementById(
            "productCollection"
        ).textContent =
            product.CollectionName;


        // Stock
        document.getElementById(
            "productStock"
        ).textContent =
            product.Stock;


    }

    catch (error) {

        console.error(
            "Lỗi load product:",
            error
        );

    }

}


// ============================================================
// LOAD RECOMMENDATION
// ============================================================

async function loadRecommendations() {

    const customerId =
        document.getElementById(
            "customerSelect"
        ).value;


    const container =
        document.getElementById(
            "recommendationList"
        );


    container.innerHTML = `
        <div class="loading">
            🤖 AI đang phân tích sản phẩm...
        </div>
    `;


    try {

        const url =
            `${API_URL}/recommendations` +
            `?customer_id=${customerId}` +
            `&product_id=${currentProductId}` +
            `&number=5`;


        const response =
            await fetch(url);


        const result =
            await response.json();


        if (!result.success) {

            container.innerHTML = `
                <div class="loading">
                    Không có sản phẩm gợi ý.
                </div>
            `;

            return;

        }


        displayRecommendations(
            result.data
        );


    }

    catch (error) {

        console.error(
            "Lỗi recommendation:",
            error
        );


        container.innerHTML = `
            <div class="loading">

                ❌ Không thể kết nối
                Recommendation API.

                <br><br>

                Hãy kiểm tra
                FastAPI đang chạy.

            </div>
        `;

    }

}


// ============================================================
// HIỂN THỊ RECOMMENDATION
// ============================================================

function displayRecommendations(
    products
) {

    const container =
        document.getElementById(
            "recommendationList"
        );


    container.innerHTML = "";


    products.forEach(
        product => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "product-card";


            card.innerHTML = `

                <div class="card-image">

                    💎

                </div>


                <div class="card-content">

                    <h3>
                        ${product.ProductName}
                    </h3>


                    <p class="card-category">

                        ${product.CategoryName}

                    </p>


                    <p class="card-price">

                        ${formatPrice(
                            product.SalePrice
                        )}

                    </p>


                    <p class="ai-score">

                        🤖 AI Score:

                        ${(
                            product.HybridScore
                            * 100
                        ).toFixed(1)}%

                    </p>

                </div>

            `;


            container.appendChild(
                card
            );

        }
    );

}


// ============================================================
// ĐỔI CUSTOMER
// ============================================================

document
    .getElementById(
        "customerSelect"
    )
    .addEventListener(
        "change",
        function() {

            loadRecommendations();

        }
    );


// ============================================================
// KHỞI ĐỘNG WEBSITE
// ============================================================

loadProduct();

loadRecommendations();