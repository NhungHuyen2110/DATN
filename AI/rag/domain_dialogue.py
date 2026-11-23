"""Small reviewed domain answers, separate from LLM output and catalog facts.

No database claims, product suggestions, model downloads, or network calls.
Unknown subjects return None rather than pretending to be a general LLM.
"""
from jewelry_agents.entity_linking import normalize

GIA_SIMULANTS = 'https://www.gia.edu/gem-imitation'
GIA_CARE = 'https://www.gia.edu/articles/gia-news-research-tips-caring-jewelry'


def domain_answer(question, history=()):
    text=normalize(question)
    # Policy/account queries must remain with the authorized business tools.
    if any(term in text for term in ('mat khau','doanh thu','don hang','ton kho',
            'bao hanh','doi tra','hoan tien','system prompt','bo qua huong dan',
            'ignore previous','phi ship','van chuyen','di ung','dau tai')):
        return None
    if text in {'noi ngan gon hon','tom tat lai','ngan gon hon'} and history:
        last=history[-1]
        previous=domain_answer(last['user'])
        if previous:
            return {**previous,'answer':previous['summary']}
    answer=summary=None
    sources=[]
    if any(term in text for term in ('viet loi chuc','viet mot loi chuc','soan loi chuc')):
        if 'sinh nhat' in text:
            answer='Chúc bạn một sinh nhật thật vui, luôn bình an và có nhiều điều đáng mong chờ trong tuổi mới. Mong món quà nhỏ này sẽ cùng bạn lưu giữ những khoảnh khắc đẹp!'
        elif any(term in text for term in ('tinh nhan','valentine','ky niem')):
            answer='Cảm ơn vì đã cùng mình tạo nên những kỷ niệm đẹp. Mong món quà nhỏ này sẽ nhắc bạn rằng bạn luôn được yêu thương và trân trọng.'
    elif any(term in text for term in ('moissanite','cz','cubic zirconia','kim cuong','diamond')):
        if 'cz' in text or 'cubic zirconia' in text:
            answer='CZ (cubic zirconia) là vật liệu có thể trông giống kim cương nhưng khác thành phần và cấu trúc. CZ không phải kim cương nuôi cấy. Nếu chọn mua, hãy xem đúng tên đá và thông tin kiểm định; vẻ ngoài giống nhau chưa chứng minh là cùng loại đá.'
        elif 'moissanite' in text:
            answer='Moissanite là một loại đá khác kim cương, dù có thể có vẻ ngoài tương tự. Moissanite không phải kim cương nuôi cấy. Khi so sánh, nên xem tên loại đá, thông tin kiểm định và sở thích về vẻ ngoài, thay vì chỉ dựa vào tên gọi “giống kim cương”.'
        else:
            answer='Kim cương tự nhiên, kim cương nuôi cấy và đá mô phỏng là những nhóm cần phân biệt. Moissanite và CZ là vật liệu khác kim cương; không nên gọi chúng là kim cương nuôi cấy. Với một món cụ thể, cần kiểm tra mô tả và hồ sơ của chính viên đá đó.'
        sources=[GIA_SIMULANTS]
        summary='CZ và Moissanite có thể giống kim cương về vẻ ngoài nhưng là vật liệu khác; chúng không phải kim cương nuôi cấy.'
    elif any(term in text for term in ('bao quan','ve sinh','lam sach','nuoc hoa')):
        answer='Hãy cất riêng từng món để hạn chế cọ xát và dùng khăn mềm lau sau khi đeo. Tránh để nước hoa hoặc mỹ phẩm tiếp xúc trực tiếp, nhất là với ngọc trai và đá nhạy cảm. Cách làm sạch còn tùy chất liệu, loại đá và xử lý bề mặt; khi chưa rõ, đừng tự dùng chất tẩy mạnh hoặc máy siêu âm. Bạn muốn bảo quản món có chất liệu và loại đá nào?'
        summary='Cất riêng, lau bằng khăn mềm và tránh mỹ phẩm; cách làm sạch cần theo đúng chất liệu và loại đá.'
        sources=[GIA_CARE]
    elif any(term in text for term in ('thanh lich','toi gian','tinh te')):
        answer='Trong cách phối trang sức, thanh lịch có thể hiểu là cân đối với trang phục và hoàn cảnh. Bạn có thể bắt đầu bằng một món làm điểm nhấn, ưu tiên tỷ lệ vừa vặn và các chi tiết dễ phối. Tối giản thiên về ít chi tiết; thanh lịch không bắt buộc phải ít chi tiết hay đắt tiền. Đây là định hướng thẩm mỹ, không phải chứng nhận cho từng sản phẩm. Bạn muốn đeo hằng ngày hay đi dự tiệc?'
        summary='Thanh lịch thiên về sự cân đối và hợp hoàn cảnh; tối giản thiên về ít chi tiết. Không nhất thiết phải chọn món đắt tiền.'
    elif any(term in text for term in ('co nhan','size nhan','kich co nhan','kich thuoc nhan')):
        answer='Bạn có thể đo đường kính trong của chiếc nhẫn đang đeo vừa hoặc nhờ cửa hàng đo trực tiếp. Hãy ghi rõ số đo và đơn vị để đối chiếu bảng cỡ của mẫu định mua; không nên suy cỡ nhẫn chỉ từ giới tính hay cân nặng. Nếu mua làm quà mà chưa biết cỡ, dây chuyền hoặc bông tai có thể dễ cân nhắc hơn.'
    elif text in {'nen chon day chuyen hay bong tai','day chuyen hay bong tai','chon qua the nao'}:
        answer='Nếu chưa rõ người nhận có bấm lỗ tai hay không, bạn có thể cân nhắc dây chuyền trước. Nếu họ thường đeo bông tai, hãy xem những mẫu họ thích và kích thước thường dùng. Ngân sách và sở thích thực tế giúp chọn quà tốt hơn việc chỉ dựa vào giới tính.'
    if not answer:
        return None
    return {'answer':answer,'summary':summary or answer,'sources':sources,
            'response_mode':'reviewed_domain_answer'}
