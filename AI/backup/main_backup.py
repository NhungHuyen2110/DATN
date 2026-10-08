import sys
import os

# ============================================================
# THÊM THƯ MỤC AI\crewai VÀO PYTHON PATH
# ============================================================

CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


# ============================================================
# IMPORT
# ============================================================

from retrieval import (
    hybrid_search,
    build_rag_context
)

from crew import run_crew


# ============================================================
# CONFIG
# ============================================================

TOP_K = 3


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("JEWELRY RECOMMENDATION - CREWAI + RAG")
    print("=" * 70)

    # --------------------------------------------------------
    # USER QUERY
    # --------------------------------------------------------

    query = input(
        "\nNhập câu hỏi của khách hàng: "
    ).strip()


    if not query:

        print(
            "Bạn chưa nhập câu hỏi."
        )

        return


    # --------------------------------------------------------
    # HYBRID RETRIEVAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("HYBRID RETRIEVAL")
    print("=" * 70)

    products = hybrid_search(
        query,
        top_k=TOP_K
    )


    # --------------------------------------------------------
    # KHÔNG CÓ SẢN PHẨM
    # --------------------------------------------------------

    if not products:

        print()
        print(
            "Không tìm thấy sản phẩm phù hợp."
        )

        return


    # --------------------------------------------------------
    # HIỂN THỊ RETRIEVAL RESULT
    # --------------------------------------------------------

    print()
    print("Các sản phẩm phù hợp:")

    for product in products:

        print(
            f"- {product.get('ProductID')} | "
            f"{product.get('ProductName')} | "
            f"{product.get('Material')} | "
            f"{product.get('score'):.4f}"
        )


    # --------------------------------------------------------
    # BUILD RAG CONTEXT
    # --------------------------------------------------------

    context = build_rag_context(
        products
    )


    print()
    print("=" * 70)
    print("RAG CONTEXT")
    print("=" * 70)

    print(context)


    # --------------------------------------------------------
    # CREWAI
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CREWAI + QWEN 3B")
    print("=" * 70)

    answer = run_crew(
        query,
        context
    )


    # --------------------------------------------------------
    # FINAL ANSWER
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CÂU TRẢ LỜI CUỐI CÙNG")
    print("=" * 70)

    print()
    print(answer)

    print()
    print("=" * 70)
    print("HOÀN TẤT")
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()