from crewai import Task
from agents import jewelry_agent


def create_recommendation_task(query, context):

    task = Task(
        description=f"""
Bạn là trợ lý tư vấn trang sức.

CÂU HỎI CỦA KHÁCH HÀNG:
{query}


DỮ LIỆU SẢN PHẨM TỪ HỆ THỐNG:
{context}


NHIỆM VỤ:

Hãy trả lời câu hỏi của khách hàng dựa TRỰC TIẾP
vào dữ liệu sản phẩm ở trên.


QUY TẮC QUAN TRỌNG:

1. Chỉ sử dụng thông tin xuất hiện trong dữ liệu sản phẩm.

2. Không được tự tạo ProductID.

3. Không được tự tạo tên sản phẩm.

4. Không được tự tạo giá.

5. Không được thay đổi giá.

6. Không được thêm sản phẩm ngoài dữ liệu.

7. Nếu dữ liệu có sản phẩm thì PHẢI giới thiệu sản phẩm đó.

8. Không được nói "không tìm thấy sản phẩm"
   nếu dữ liệu sản phẩm bên trên có sản phẩm.

9. Nếu có 2 sản phẩm trong dữ liệu thì có thể
   giới thiệu cả 2 sản phẩm.

10. Nếu có 1 sản phẩm thì chỉ giới thiệu 1 sản phẩm.

11. Nếu có 3 sản phẩm thì giới thiệu tối đa 3 sản phẩm.

12. Giá phải giữ nguyên chính xác như dữ liệu.

13. ProductID phải giữ nguyên chính xác.

14. Tên sản phẩm phải giữ nguyên chính xác.

15. Chất liệu phải giữ nguyên chính xác.

16. Đá quý phải giữ nguyên chính xác.

17. Không được suy diễn thêm thông tin.

18. Trả lời bằng tiếng Việt.


CÁCH TRẢ LỜI:

Nếu có sản phẩm phù hợp:

"Đây là các sản phẩm phù hợp với yêu cầu của bạn:"

Sau đó liệt kê từng sản phẩm theo mẫu:

- ProductID: ...
- Tên: ...
- Chất liệu: ...
- Đá quý: ...
- Giá: ...


Nếu có nhiều sản phẩm, liệt kê từng sản phẩm riêng biệt.

Không cần giải thích dài.


ĐẶC BIỆT:

Dữ liệu sản phẩm ở trên là kết quả đã được
hệ thống Hybrid Retrieval lọc.

Vì vậy:

NẾU CONTEXT CÓ SẢN PHẨM,
BẠN PHẢI GIỚI THIỆU CÁC SẢN PHẨM ĐÓ.

KHÔNG ĐƯỢC tự kết luận rằng không có sản phẩm
khi CONTEXT đã chứa sản phẩm.


Nếu CONTEXT thực sự không có sản phẩm,
chỉ khi đó mới trả lời:

"Hệ thống không tìm thấy sản phẩm phù hợp."
""",

        expected_output="""
Câu trả lời tư vấn sản phẩm bằng tiếng Việt.

Chỉ sử dụng sản phẩm trong CONTEXT.

Nếu CONTEXT có sản phẩm thì phải giới thiệu
sản phẩm đó.

Không được nói không tìm thấy sản phẩm
khi CONTEXT có sản phẩm.

Không được tạo dữ liệu mới.
""",

        agent=jewelry_agent
    )

    return task