from crewai import Task

from agents import jewelry_agent


# ============================================================
# TẠO TASK TƯ VẤN
# ============================================================

def create_recommendation_task(query, context):

    task = Task(
        description=f"""
Khách hàng đặt câu hỏi:

{query}


Dữ liệu sản phẩm được truy xuất từ hệ thống:

{context}


Hãy tư vấn cho khách hàng dựa hoàn toàn vào dữ liệu trên.


QUY TẮC BẮT BUỘC:

1. Trả lời bằng tiếng Việt.

2. Chỉ sử dụng sản phẩm xuất hiện trong CONTEXT.

3. Không tự tạo ProductID.

4. Không tự tạo tên sản phẩm.

5. Không tự tạo giá.

6. Không thay đổi giá.

7. Không nhân hoặc chia giá.

8. Không đưa ra sản phẩm không có trong CONTEXT.

9. Số lượng sản phẩm được giới thiệu phải nhỏ hơn
   hoặc bằng số sản phẩm thực tế trong CONTEXT.

10. Không được nói "ba sản phẩm" nếu CONTEXT
    chỉ có hai sản phẩm.

11. Giá phải giữ nguyên chính xác như CONTEXT.

12. Khi giới thiệu giá, phải giữ đúng định dạng:
    Ví dụ: 10.898.911 VNĐ

13. Không được suy diễn thêm thông tin không có
    trong CONTEXT.

14. Nếu có nhiều sản phẩm phù hợp, ưu tiên sản phẩm
    có điểm tương đồng Qdrant cao hơn.

15. Giới thiệu tối đa 3 sản phẩm.

16. Nếu không có sản phẩm phù hợp, hãy nói rõ
    rằng hệ thống không tìm thấy sản phẩm phù hợp.

17. Không được tự suy đoán số lượng sản phẩm.

18. Không được thêm thông tin về sản phẩm
    nếu thông tin đó không xuất hiện trong CONTEXT.


CÁCH TRẢ LỜI:

- Giới thiệu ngắn gọn.
- Liệt kê sản phẩm phù hợp.
- Với mỗi sản phẩm, ưu tiên hiển thị:
  + ProductID
  + Tên
  + Chất liệu
  + Đá quý
  + Giá
- Không cần giải thích dài dòng.
""",

        expected_output="""
Câu trả lời tư vấn trang sức bằng tiếng Việt.

Câu trả lời chỉ sử dụng dữ liệu trong CONTEXT.

Không được tạo dữ liệu mới.

Số lượng sản phẩm trong câu trả lời không vượt quá
số lượng sản phẩm có trong CONTEXT.
""",

        agent=jewelry_agent
    )

    return task