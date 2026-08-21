#!/usr/bin/env python3
"""Create a review-safe revision of the CLARA-Care manuscript.

This deliberately does not add clinical, human, expert, or external results.
It preserves all non-document XML parts of the source DOCX and changes only
the narrative/table cells identified by their stable section headings.
"""

from __future__ import annotations

import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W}
ET.register_namespace("w", W)
ET.register_namespace("r", R)


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.findall(".//w:t", NS)).strip()


def body_paragraphs(body: ET.Element) -> list[ET.Element]:
    return [child for child in list(body) if child.tag == qn("p")]


def body_tables(body: ET.Element) -> list[ET.Element]:
    return [child for child in list(body) if child.tag == qn("tbl")]


def find_last_paragraph(body: ET.Element, expected: str) -> ET.Element:
    matches = [paragraph for paragraph in body_paragraphs(body) if text_of(paragraph) == expected]
    if not matches:
        raise RuntimeError(f"missing target paragraph: {expected}")
    return matches[-1]


def set_paragraph_text(paragraph: ET.Element, value: str) -> None:
    props = paragraph.find("w:pPr", NS)
    for child in list(paragraph):
        if child is not props:
            paragraph.remove(child)
    run = ET.SubElement(paragraph, qn("r"))
    text = ET.SubElement(run, qn("t"))
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = value


def new_paragraph(template: ET.Element, value: str) -> ET.Element:
    paragraph = ET.Element(qn("p"))
    props = template.find("w:pPr", NS)
    if props is not None:
        paragraph.append(copy.deepcopy(props))
    set_paragraph_text(paragraph, value)
    return paragraph


def insert_after(body: ET.Element, anchor: ET.Element, elements: list[ET.Element]) -> None:
    index = list(body).index(anchor) + 1
    for element in elements:
        body.insert(index, element)
        index += 1


def table_rows(table: ET.Element) -> list[list[ET.Element]]:
    return [row.findall("w:tc", NS) for row in table.findall("w:tr", NS)]


def set_cell_text(cell: ET.Element, value: str) -> None:
    paragraph = cell.find("w:p", NS)
    if paragraph is None:
        paragraph = ET.SubElement(cell, qn("p"))
    set_paragraph_text(paragraph, value)
    for extra in list(cell.findall("w:p", NS))[1:]:
        cell.remove(extra)


def table_header(table: ET.Element) -> str:
    rows = table_rows(table)
    if not rows:
        return ""
    return " | ".join(text_of(cell) for cell in rows[0])


def find_table(body: ET.Element, header_prefix: str) -> ET.Element:
    matches = [table for table in body_tables(body) if table_header(table).startswith(header_prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one table headed {header_prefix!r}, found {len(matches)}")
    return matches[0]


def replace_table(table: ET.Element, content: list[list[str]]) -> None:
    rows = table_rows(table)
    if len(rows) != len(content):
        raise RuntimeError(f"table has {len(rows)} rows, revision requires {len(content)}")
    for row, new_cells in zip(rows, content, strict=True):
        if len(row) != len(new_cells):
            raise RuntimeError("table column count mismatch")
        for cell, value in zip(row, new_cells, strict=True):
            set_cell_text(cell, value)


def main(source: Path, output: Path) -> None:
    with ZipFile(source) as archive:
        entries = {item.filename: archive.read(item.filename) for item in archive.infolist()}

    root = ET.fromstring(entries["word/document.xml"])
    body = root.find(".//w:body", NS)
    if body is None:
        raise RuntimeError("document body was not found")

    # Executive summary: a prototype/implementation claim, never a clinical result.
    summary_heading = find_last_paragraph(body, "TÓM TẮT ĐỀ TÀI")
    summary = body_paragraphs(body)
    summary_index = summary.index(summary_heading)
    set_paragraph_text(summary[summary_index + 1], (
        "CLARA-Care là một nguyên mẫu phần mềm tích hợp để tổ chức thông tin sức khỏe, "
        "nguồn tham khảo và các bước rà soát của con người. Báo cáo này mô tả hiện vật "
        "mã nguồn, cơ chế kiểm soát và giao thức đánh giá; đây không phải nghiên cứu lâm sàng "
        "hay nghiên cứu có người tham gia."
    ))
    set_paragraph_text(summary[summary_index + 2], (
        "Các phân hệ Research, CareGuard, Council, Scribe, PHR và LifeMap được triển khai "
        "để hỗ trợ ghi nhận, truy xuất, chuẩn bị thông tin và rà soát trong các giới hạn đã "
        "định nghĩa. Mọi nhận định về hiệu quả chăm sóc, an toàn lâm sàng, tiết kiệm thời gian "
        "hoặc phối hợp giữa các bên đều cần được kiểm chứng bằng nghiên cứu độc lập trong tương lai."
    ))
    set_paragraph_text(summary[summary_index + 3], (
        "Về kỹ thuật, repository có Web, API và dịch vụ ML cùng các kiểm thử hợp đồng và "
        "fixture tổng hợp. Lần kiểm tra được báo cáo trong bản sửa này xác nhận toàn vẹn manifest "
        "của chín fixture tổng hợp; nó không đo chất lượng câu trả lời, hiệu năng mô hình, an toàn "
        "thuốc, hiệu quả lâm sàng, chi phí hay trải nghiệm người dùng."
    ))

    # The source uses a static table of contents. Keep its revised Section 35–45
    # labels and page references aligned with the rendered revision, rather than
    # leaving a misleading pre-revision navigation map.
    toc_updates = {
        "35. CÂU HỎI NGHIÊN CỨU VÀ GIẢ THUYẾT104": "35. CÂU HỎI NGHIÊN CỨU TIỀN ĐĂNG KÝ (CHƯA CÓ KẾT QUẢ HIỆU NĂNG)\t101",
        "36. BỘ DỮ LIỆU VÀ KỊCH BẢN KIỂM THỬ105": "36. DỮ LIỆU HIỆN CÓ, KHOẢNG TRỐNG THAM CHIẾU VÀ KỊCH BẢN DỰ KIẾN\t102",
        "37. HỆ CHỈ SỐ ĐÁNH GIÁ106": "37. HỆ CHỈ SỐ ĐƯỢC ĐỊNH NGHĨA (KHÔNG PHẢI KẾT QUẢ)\t103",
        "38. GIAO THỨC THỬ NGHIỆM108": "38. GIAO THỨC ĐÁNH GIÁ DỰ KIẾN (CHƯA THỰC HIỆN)\t104",
        "39. TÓM TẮT KẾT QUẢ NỘI BỘ VÀ CÁCH DIỄN GIẢI109": "39. KẾT QUẢ CÓ THỂ BÁO CÁO VÀ CÁC KHOẢNG TRỐNG\t105",
        "40. THẢO LUẬN, GIỚI HẠN VÀ ĐE DỌA TỚI TÍNH HỢP LỆ110": "40. THẢO LUẬN, GIỚI HẠN VÀ RANH GIỚI SUY LUẬN\t106",
        "41. QUẢN TRỊ RỦI RO111": "41. QUẢN TRỊ RỦI RO\t108",
        "42. KỊCH BẢN TRIỂN KHAI114": "42. KỊCH BẢN TRIỂN KHAI DỰ KIẾN\t112",
        "43. MÔ HÌNH KINH DOANH VÀ NGUYÊN TẮC XUNG ĐỘT LỢI ÍCH119": "43. MÔ HÌNH KINH DOANH VÀ NGUYÊN TẮC XUNG ĐỘT LỢI ÍCH\t117",
        "44. QUẢN TRỊ VÀ LỘ TRÌNH PHÁT TRIỂN127": "44. QUẢN TRỊ VÀ LỘ TRÌNH PHÁT TRIỂN\t125",
        "45. NĂNG LỰC VẬN HÀNH VÀ CHIẾN LƯỢC MỞ RỘNG131": "45. NĂNG LỰC VẬN HÀNH VÀ CHIẾN LƯỢC MỞ RỘNG\t129",
        "KẾT LUẬN134": "KẾT LUẬN\t132",
        "KIẾN NGHỊ135": "KIẾN NGHỊ\t133",
        "TÀI LIỆU THAM KHẢO136": "TÀI LIỆU THAM KHẢO\t134",
        "PHỤ LỤC A. BẢN ĐỒ THÀNH PHẦN KIẾN TRÚC VÀ TRÁCH NHIỆM141": "PHỤ LỤC A. BẢN ĐỒ THÀNH PHẦN KIẾN TRÚC VÀ TRÁCH NHIỆM\t138",
        "PHỤ LỤC B. BỘ CÂU HỎI VÀ KỊCH BẢN KIỂM THỬ147": "PHỤ LỤC B. BỘ CÂU HỎI VÀ KỊCH BẢN KIỂM THỬ\t144",
        "PHỤ LỤC C. BẢN GHI HỘI THOẠI MẪU VÀ KHUNG SOAP MONG ĐỢI154": "PHỤ LỤC C. BẢN GHI HỘI THOẠI MẪU VÀ KHUNG SOAP MONG ĐỢI\t150",
        "PHỤ LỤC D. BẢNG THUẬT NGỮ VÀ DANH MỤC TỪ VIẾT TẮT155": "PHỤ LỤC D. BẢNG THUẬT NGỮ VÀ DANH MỤC TỪ VIẾT TẮT\t151",
        "PHỤ LỤC E. MA TRẬN TRUY VẾT YÊU CẦU164": "PHỤ LỤC E. MA TRẬN TRUY VẾT YÊU CẦU\t160",
        "PHỤ LỤC F. DANH SÁCH KIỂM TRA TRƯỚC KHI TRÌNH DIỄN166": "PHỤ LỤC F. DANH SÁCH KIỂM TRA TRƯỚC KHI TRÌNH DIỄN\t162",
        "PHỤ LỤC G. MA TRẬN HỢP ĐỒNG API167": "PHỤ LỤC G. MA TRẬN HỢP ĐỒNG API\t163",
        "PHỤ LỤC H. SỔ ĐĂNG KÝ RỦI RO169": "PHỤ LỤC H. SỔ ĐĂNG KÝ RỦI RO\t165",
        "PHỤ LỤC I. KẾ HOẠCH KIỂM THỬ CHẤP NHẬN172": "PHỤ LỤC I. KẾ HOẠCH KIỂM THỬ CHẤP NHẬN\t168",
        "PHỤ LỤC J. HƯỚNG DẪN TRIỂN KHAI VÀ TRÌNH DIỄN175": "PHỤ LỤC J. HƯỚNG DẪN TRIỂN KHAI VÀ TRÌNH DIỄN\t171",
        "LIÊN KẾT SẢN PHẨM VÀ MÃ NGUỒN177": "LIÊN KẾT SẢN PHẨM VÀ MÃ NGUỒN\t173",
    }
    for paragraph in body_paragraphs(body):
        value = text_of(paragraph)
        if value in toc_updates:
            set_paragraph_text(paragraph, toc_updates[value])

    # Scope: distinguish the product's broad capability map from this report's narrow evidence scope.
    objective = find_last_paragraph(body, "3.1. Mục tiêu tổng quát")
    scope_template = find_last_paragraph(body, "3.2. Nhóm người dùng")
    scope_heading = new_paragraph(scope_template, "3.1.1. Phạm vi thực nghiệm của báo cáo này")
    scope_paragraph = new_paragraph(scope_template, (
        "Đơn vị phân tích của báo cáo là nguyên mẫu phần mềm và các hiện vật kiểm tra trong "
        "repository, không phải người bệnh, bác sĩ, người chăm sóc hay cơ sở y tế. Vì vậy, báo cáo "
        "không tuyên bố một hiệu quả đối với bất kỳ nhóm người dùng nào. Nghiên cứu tiếp theo nên "
        "khóa một mục tiêu chính hẹp: truy xuất bằng chứng tiếng Việt có bác sĩ rà soát cho mục đích "
        "đào tạo/tra cứu; các năng lực khác chỉ là đối tượng đánh giá riêng sau khi có giao thức phù hợp."
    ))
    insert_after(body, objective, [scope_heading, scope_paragraph])

    # Product/market chapters are design positioning, not an efficacy or SOTA comparison.
    novelty_heading = find_last_paragraph(body, "4. TÍNH MỚI VÀ TÍNH SÁNG TẠO")
    set_paragraph_text(novelty_heading, "4. ĐÓNG GÓP THIẾT KẾ VÀ GIẢ THUYẾT TÍNH MỚI (CHƯA SO SÁNH THỰC NGHIỆM)")
    novelty_note = new_paragraph(scope_template, (
        "Chương này mô tả điểm khác biệt ở cấp độ thiết kế và phạm vi tích hợp của nguyên mẫu. Không có "
        "benchmark tái lập đối đầu với một hệ thống cụ thể, nên các so sánh với chatbot, công cụ tìm kiếm, PHR "
        "hay sản phẩm thương mại chỉ nhằm đặt bối cảnh; chúng không chứng minh tính mới tuyệt đối hoặc ưu thế "
        "về hiệu năng, an toàn hay giá trị người dùng."
    ))
    insert_after(body, novelty_heading, [novelty_note])
    market_heading = find_last_paragraph(body, "5. THỊ TRƯỜNG, KHẢ NĂNG ÁP DỤNG VÀ GIÁ TRỊ TẠO RA")
    set_paragraph_text(market_heading, "5. BỐI CẢNH THỊ TRƯỜNG VÀ GIẢ THUYẾT ỨNG DỤNG (CHƯA XÁC NHẬN HIỆU QUẢ)")
    market_note = new_paragraph(scope_template, (
        "Các tình huống và giá trị trong chương này là giả thuyết sản phẩm/triển khai dựa trên nhu cầu được nêu "
        "trong tài liệu nền, không phải outcome được đo trong CLARA-Care. Cụm từ “giảm”, “tiết kiệm”, “cải thiện”, "
        "“lợi thế” hoặc “có thể” trong chương phải được đọc như mục tiêu cần kiểm tra trong các nghiên cứu hẹp, "
        "không phải kết quả đã quan sát."
    ))
    insert_after(body, market_heading, [market_note])

    # Replace Sections 35–40 language with evidence-status language.
    set_paragraph_text(find_last_paragraph(body, "35. CÂU HỎI NGHIÊN CỨU VÀ GIẢ THUYẾT"), "35. CÂU HỎI NGHIÊN CỨU TIỀN ĐĂNG KÝ (CHƯA CÓ KẾT QUẢ HIỆU NĂNG)")
    rq_texts = [
        "RQ1 (chưa đo): Truy xuất kết hợp và sắp xếp lại có cải thiện Precision@k, Recall@k, MRR hoặc nDCG so với baseline đã khóa trên cùng một tập relevance-label hay không?",
        "RQ2 (chưa đo): Kiểm chứng bằng chứng có thay đổi tỷ lệ nhận định không được nguồn hỗ trợ và độ chính xác trích dẫn trên gold claim đã được chấm độc lập hay không?",
        "RQ3 (chưa đo): CareGuard có đạt độ nhạy, độ đặc hiệu, precision và tỷ lệ cảnh báo sai chấp nhận được cho DDI nghiêm trọng trên chuẩn tham chiếu được cấp phép hay không?",
        "RQ4 (chưa đo): Council có phát hiện dữ kiện thiếu và tạo cấu trúc đồng thuận ổn định khi so với phán quyết độc lập của chuyên gia hay không?",
        "RQ5 (chưa đo): Scribe có tạo SOAP bám transcript và thay đổi thời gian/khối lượng chỉnh sửa trong một nghiên cứu có người tham gia, đối chứng và đo thời gian hay không?",
        "RQ6 (chưa đo): Một workflow liên thông có làm thay đổi nhập trùng hoặc độ đầy đủ truy vết trong quan sát sử dụng thực tế có kiểm soát hay không?",
    ]
    start = find_last_paragraph(body, "RQ1: Việc kết hợp tìm kiếm từ khóa, tìm kiếm ngữ nghĩa và bước sắp xếp lại có đưa những tài liệu liên quan lên nhóm kết quả đầu tốt hơn so với chỉ tìm theo từ khóa hay không?")
    paragraphs = body_paragraphs(body)
    start_index = paragraphs.index(start)
    for offset, value in enumerate(rq_texts):
        set_paragraph_text(paragraphs[start_index + offset], value)
    set_paragraph_text(paragraphs[start_index + 6], (
        "Sáu câu hỏi trên là giao thức tiền đăng ký cho các đánh giá sau này. Trong revision này, "
        "không câu hỏi nào được chấp nhận hoặc bác bỏ: repository không chứa bộ tham chiếu, dữ liệu "
        "được phê duyệt, phân xử độc lập, người tham gia hoặc execution trace cần để suy luận kết quả."
    ))
    set_paragraph_text(find_last_paragraph(body, "35.1. Cách chuyển câu hỏi nghiên cứu thành phép đo"), "35.1. Điều kiện để một câu hỏi có thể được kiểm tra")
    section_35_text = find_last_paragraph(body, "Mỗi câu hỏi nghiên cứu được gắn với phương án chuẩn, thay đổi cần kiểm tra, chỉ số, tập dữ liệu và ngưỡng thất bại. Ví dụ, câu hỏi thứ nhất so sánh truy xuất bằng từ khóa với truy xuất kết hợp và bộ sắp xếp lại trên cùng tập truy vấn; câu hỏi thứ hai so sánh kết quả trước và sau bước kiểm chứng cùng quy tắc an toàn; câu hỏi thứ ba chạy CareGuard khi nguồn bên ngoài hoạt động và khi nguồn này bị ngắt. Thiết kế so sánh trên cùng một tập giúp giảm nhiễu do bộ câu hỏi khác nhau.")
    set_paragraph_text(section_35_text, (
        "Mỗi nghiên cứu tương lai phải khóa baseline, đơn vị phân tích, tập phát triển và tập kiểm "
        "thử, tiêu chí thất bại, mô hình/tham số, corpus/index, ngày truy xuất, quy trình chấm và "
        "kế hoạch thống kê trước khi chạy. Các so sánh RQ1–RQ3 phải theo cặp trên cùng đơn vị; kết quả "
        "báo effect size và khoảng tin cậy bằng resampling theo cặp, kèm kế hoạch kiểm soát đa kiểm định."
    ))
    next_35_text = find_last_paragraph(body, "Một giả thuyết chỉ được chấp nhận khi sự cải thiện không đánh đổi một tiêu chí quan trọng khác. Chẳng hạn, kết quả tìm kiếm không được xem là tốt hơn nếu độ liên quan chỉ tăng nhẹ nhưng thời gian chờ và số yêu cầu quá hạn tăng mạnh. Tương tự, lớp an toàn không được xem là tốt hơn nếu chặn được nhiều nội dung nguy hại hơn nhưng đồng thời từ chối quá nhiều câu hỏi hợp lệ. Vì vậy, CLARA đánh giá mỗi thay đổi bằng một nhóm chỉ số thay vì chọn một con số duy nhất.")
    set_paragraph_text(next_35_text, (
        "Các nghiên cứu có con người cho RQ4–RQ6 cần xác định tiêu chí tuyển chọn/loại trừ, cỡ mẫu "
        "và power analysis, comparator workflow, thứ tự thao tác, đào tạo, thời điểm đo, xử lý thiếu "
        "dữ liệu, giám sát hại và phê duyệt đạo đức/đồng thuận khi áp dụng. Ba lần chạy stochastic chỉ "
        "đo biến thiên kỹ thuật; chúng không thay thế chuẩn tham chiếu hoặc đánh giá chuyên gia."
    ))

    set_paragraph_text(find_last_paragraph(body, "36. BỘ DỮ LIỆU VÀ KỊCH BẢN KIỂM THỬ"), "36. DỮ LIỆU HIỆN CÓ, KHOẢNG TRỐNG THAM CHIẾU VÀ KỊCH BẢN DỰ KIẾN")
    dataset_intro = find_last_paragraph(body, "Bộ kiểm thử được chia theo từng năng lực. Mỗi mẫu đều có hành vi mong đợi, nguồn tham chiếu, mức rủi ro và điều kiện đạt hoặc không đạt. Research sử dụng câu hỏi về định nghĩa, triệu chứng, điều trị chung, mã hóa và quan hệ. Medication Safety kiểm tra danh sách thuốc sạch, cách gọi thuốc bằng tiếng Việt, dữ liệu OCR nhiễu, các cặp tương tác nghiêm trọng hoặc không nghiêm trọng và tình huống nguồn bên ngoài gặp lỗi. Council sử dụng cả ca bệnh đầy đủ lẫn ca thiếu dữ kiện. Scribe dùng bản ghi hội thoại có phân vai cùng mẫu SOAP tham chiếu. Nhóm an toàn kiểm tra các yêu cầu chẩn đoán, kê đơn, định liều và những tình huống cố tình vượt qua giới hạn của hệ thống.")
    set_paragraph_text(dataset_intro, (
        "Dataset manifest hiện có khai báo chín fixture smoke tổng hợp, tổng cộng 12 bản ghi. Các fixture "
        "không chứa PHI hay bí mật và chỉ kiểm tra hình dạng hợp đồng, checksum và metadata; chúng không "
        "đại diện cho bệnh nhân, vùng miền, chuyên khoa, mức độ hiểu biết sức khỏe, đơn thuốc, chất lượng "
        "OCR, âm thanh hay dữ liệu thực tế. Không có gold relevance labels, claim adjudication, full DrugBank "
        "được cấp phép, transcript/audio có đồng thuận, tập Council do chuyên gia chấm hoặc telemetry live."
    ))
    set_paragraph_text(find_last_paragraph(body, "36.1. Quy tắc tách tập"), "36.1. Điều chưa được chỉ định và phải có trước khi đo")
    split_text = find_last_paragraph(body, "Bộ dữ liệu dùng để phát triển, bộ kiểm thử hồi quy và bộ dùng cho trình diễn phải được tách riêng. Những ca đã dùng để chỉnh luật không được trở thành bằng chứng duy nhất khi công bố chất lượng. Mỗi lần đánh giá ghi rõ phiên bản mã nguồn, mô hình hoặc nhà cung cấp, cấu hình, các nguồn được bật, môi trường chạy và thời điểm thực hiện. Kết quả không thể lặp lại do nguồn bên ngoài thay đổi phải được đánh dấu rõ.")
    set_paragraph_text(split_text, (
        "Vì bộ kết quả chưa tồn tại, manuscript không thể báo inclusion/exclusion, sampling, phân bố nguy cơ, "
        "ngôn ngữ, OCR hay hard negative cho một benchmark hiệu năng. Một bộ đánh giá hợp lệ cần công bố "
        "nguồn/phiên bản/giấy phép, tách development-test-demo, quy tắc chống leakage, số người gán nhãn, "
        "chuyên môn, tính độc lập, phân xử bất đồng và inter-rater reliability."
    ))
    set_paragraph_text(find_last_paragraph(body, "36.2. Cấu trúc một mẫu đánh giá"), "36.2. Schema bắt buộc cho nghiên cứu tiếp theo")
    schema_text = find_last_paragraph(body, "Mỗi mẫu kiểm thử có mã định danh, năng lực cần đánh giá, mức rủi ro, dữ liệu đầu vào, ngữ cảnh, hành vi mong đợi, nguồn tham chiếu, thang điểm, hành vi bị cấm và ghi chú. Với Research, nguồn tham chiếu có thể là danh sách tài liệu và các nhận định chính. Với DDI, mẫu ghi cặp hoạt chất, mức độ tương tác và nguồn. Với Scribe, mẫu chứa bản ghi hội thoại và những thông tin được phép xuất hiện trong SOAP. Với nhóm an toàn, việc xác định hành vi bị cấm quan trọng không kém câu trả lời mong đợi.")
    set_paragraph_text(schema_text, (
        "Mỗi mẫu đánh giá mới phải có mã định danh, provenance/quyền sử dụng, thời điểm và môi trường thu "
        "thập, dữ liệu/đầu vào đã khử định danh, nhãn tham chiếu, hướng dẫn chấm, người chấm độc lập, "
        "kết quả phân xử và đường liên kết đến snapshot bất biến. Các bản ghi thô không được đưa vào repository "
        "công khai; báo cáo chỉ dùng số liệu tổng hợp đã được phê duyệt."
    ))
    hard_negative = find_last_paragraph(body, "Các mẫu gây nhiễu khó được xây dựng từ những trường hợp dễ nhầm: tên thuốc gần giống, tài liệu chứa từ khóa nhưng không trả lời câu hỏi, trích dẫn cùng chủ đề nhưng không hỗ trợ nhận định, chỉ dẫn ẩn trong tệp và ca bệnh thiếu dữ kiện. Những mẫu này giúp đo khả năng phân biệt của hệ thống, thay vì chỉ kiểm tra bằng các câu hỏi thuận lợi.")
    set_paragraph_text(hard_negative, (
        "Hard-negative, adversarial prompt/file-injection, cross-profile access, privacy leakage, calibration "
        "và regional-language robustness đều là các hạng mục chưa đo. Chúng được giữ là yêu cầu của kế hoạch "
        "đánh giá tiếp theo, không được trình bày như coverage hay bảo chứng hiện hữu."
    ))

    set_paragraph_text(find_last_paragraph(body, "37. HỆ CHỈ SỐ ĐÁNH GIÁ"), "37. HỆ CHỈ SỐ ĐƯỢC ĐỊNH NGHĨA (KHÔNG PHẢI KẾT QUẢ)")
    metrics_table = find_table(body, "Năng lực | Chỉ số chính | Ý nghĩa")
    replace_table(metrics_table, [
        ["Năng lực", "Chỉ số cho nghiên cứu tương lai", "Trạng thái trong bản thảo"],
        ["Retrieval", "Precision@k, Recall@k, MRR, nDCG; paired effect size/CI", "Chưa đo: không có relevance gold set hoặc baseline run."],
        ["Grounding", "Citation precision, support rate, unsupported-claim rate", "Chưa đo: không có claim labels/adjudication hoặc retrieval snapshot."],
        ["Medication", "Sensitivity, specificity, precision, false-alert rate theo severity", "Chưa đo: không có chuẩn DDI được cấp phép/đóng băng."],
        ["Council", "Completeness detection, agreement, stability, critical-error rate", "Chưa đo: không có corpus và phán quyết chuyên gia độc lập."],
        ["Scribe", "SOAP accuracy/grounding, hallucinated-fact rate, edit burden/time", "Chưa đo: không có audio/transcript có đồng thuận hay nghiên cứu người dùng."],
        ["Longitudinal", "Duplicate-entry reduction, traceability completeness, correction rate", "Chưa đo: không có workflow study hoặc dữ liệu sử dụng thực tế."],
        ["Security/robustness", "Injection, privacy, cross-profile, calibration and penetration outcomes", "Chưa đo: chưa có đánh giá độc lập/ở quy mô công bố."],
        ["Fixture governance", "Manifest checksum/count integrity", "Đã đo hẹp: 9/9 fixture synthetic hợp lệ; không phải chất lượng sản phẩm."]
    ])
    set_paragraph_text(find_last_paragraph(body, "37.1. Định nghĩa và nguyên tắc diễn giải chỉ số"), "37.1. Nguyên tắc diễn giải")
    principle_a = find_last_paragraph(body, "Precision@k cho biết trong k tài liệu đứng đầu có bao nhiêu tài liệu thực sự liên quan. Recall@k cho biết hệ thống tìm được bao nhiêu trong tổng số tài liệu liên quan đã biết. MRR chú ý đến vị trí của tài liệu liên quan đầu tiên, còn nDCG xem xét cả mức độ liên quan và thứ hạng. Các chỉ số này chỉ đánh giá chất lượng tìm nguồn; chúng không tự chứng minh rằng câu trả lời cuối cùng là đúng.")
    set_paragraph_text(principle_a, (
        "Các chỉ số ở Bảng 37 là định nghĩa tiền đăng ký. Chúng chỉ trở thành kết quả khi có dataset phù hợp, "
        "nhãn tham chiếu, execution trace, denominator, baseline và phương pháp tính được đóng băng. Không có "
        "giá trị trống nào được hiểu là 0, 100%, không lỗi hoặc đạt ngưỡng."
    ))
    principle_b = find_last_paragraph(body, "Độ chính xác của trích dẫn đo tỷ lệ trích dẫn thực sự hỗ trợ cho nhận định đi kèm. Độ bao phủ trích dẫn cho biết có bao nhiêu nhận định cần nguồn đã được gắn ít nhất một nguồn phù hợp. Tỷ lệ nhận định được hỗ trợ đánh giá mức độ bằng chứng nâng đỡ đầy đủ hoặc một phần cho câu trả lời. Những nhận định không có căn cứ phải được báo cáo riêng, đặc biệt khi liên quan đến số liệu, chỉ định hoặc quan hệ nhân quả.")
    set_paragraph_text(principle_b, (
        "Các outcome quan trọng phải báo cáo hiệu số tuyệt đối/tương đối, khoảng tin cậy 95%, số ca, các thất bại "
        "và missing/timeout theo từng track. Với nhiều RQ/metric, kế hoạch multiplicity phải được định trước. "
        "Một kết quả kỹ thuật hoặc fixture integrity không phải surrogate cho đáp án y khoa đúng hoặc an toàn lâm sàng."
    ))
    principle_c = find_last_paragraph(body, "Medication Safety ưu tiên khả năng phát hiện các tương tác thuốc nghiêm trọng, độ chính xác khi chuẩn hóa tên thuốc và tỷ lệ cảnh báo sai. Scribe được đánh giá bằng độ chính xác và độ bao phủ của thông tin, tỷ lệ chi tiết không có căn cứ, mức độ đầy đủ của các trường và khối lượng chỉnh sửa của người rà soát. Nhóm an toàn theo dõi tỷ lệ nội dung nguy hiểm bị lọt, tỷ lệ từ chối đúng và tỷ lệ từ chối nhầm. Thời gian đáp ứng được báo cáo bằng trung vị, phân vị 95, số lần quá thời gian và tỷ lệ chuyển sang chế độ dự phòng.")
    set_paragraph_text(principle_c, (
        "Các số liệu lịch sử như số rule, alias hay ca smoke là inventory/cổng kỹ thuật, không phải sensitivity, "
        "specificity, coverage, accuracy hoặc usability. Chúng chỉ được giữ để truy vết nguồn lực nội bộ và luôn "
        "đi cùng giới hạn của tập/cấu hình tương ứng."
    ))

    set_paragraph_text(find_last_paragraph(body, "38. GIAO THỨC THỬ NGHIỆM"), "38. GIAO THỨC ĐÁNH GIÁ DỰ KIẾN (CHƯA THỰC HIỆN)")
    protocol_items = [
        "Đóng băng commit, model/provider/version, prompt, tham số, corpus/index/retrieval snapshot, k, phần cứng/runtime và ledger chi phí trước khi chạy.",
        "Khóa dataset được cấp phép/khử định danh, tiêu chí chọn/loại trừ, nhãn tham chiếu, split và cách chống leakage.",
        "Chấm độc lập, mù khi phù hợp; báo số người chấm, chuyên môn, agreement và cách phân xử bất đồng.",
        "Chạy baseline và phiên bản đầy đủ trên cùng đơn vị; dùng paired bootstrap hoặc phép kiểm định đã định trước, effect size và CI 95%.",
        "Báo đủ denominator, failures, timeout, dữ liệu thiếu, critical errors và độ biến thiên; không chọn lần chạy thuận lợi.",
        "Đăng ký cỡ mẫu/power cho nghiên cứu có người tham gia và có kế hoạch kiểm soát đa kiểm định.",
        "Tách software validation, expert review, usability/workflow study và clinical validation; không suy luận chéo giữa các mức này.",
    ]
    first_protocol = find_last_paragraph(body, "Đóng băng commit, cấu hình và threshold trước khi chạy.")
    paragraphs = body_paragraphs(body)
    protocol_index = paragraphs.index(first_protocol)
    for offset, value in enumerate(protocol_items):
        set_paragraph_text(paragraphs[protocol_index + offset], value)
    set_paragraph_text(find_last_paragraph(body, "38.1. Kế hoạch đánh giá từng thành phần"), "38.1. Phân cấp bằng chứng và điều kiện chuyển pha")
    plan_a = find_last_paragraph(body, "Thử nghiệm loại bỏ từng thành phần được dùng để đo đóng góp thực sự của kiến trúc. Nhóm lần lượt so sánh tìm kiếm từ khóa với tìm kiếm kết hợp, kết quả trước và sau bước sắp xếp lại, câu trả lời có và không có kiểm chứng, CareGuard chỉ dùng nguồn ngoài với phương án kết hợp nguồn ngoài và luật cục bộ, cũng như Council có và không có bước kiểm tra dữ kiện thiếu. Mọi phương án được chạy trên cùng dữ liệu và cùng cấu hình để bảo đảm so sánh công bằng.")
    set_paragraph_text(plan_a, (
        "Giai đoạn 1 chỉ xác nhận hợp đồng phần mềm và toàn vẹn artifact. Giai đoạn 2 dùng benchmark nội bộ "
        "được khóa và chấm độc lập để đo RQ1–RQ3. Giai đoạn 3 cần nghiên cứu có người tham gia/expert review "
        "cho RQ4–RQ6. Giai đoạn 4 mới kiểm tra external validity, đa cơ sở, subgroup, bảo mật và triển khai "
        "tiền cứu. Không giai đoạn nào được bỏ qua bằng cách suy diễn từ unit test."
    ))
    plan_b = find_last_paragraph(body, "Kết quả được đọc trong mối quan hệ giữa chất lượng, thời gian và chi phí. Nếu bước sắp xếp lại làm nguồn liên quan hơn nhưng tăng độ trễ quá nhiều, nó có thể chỉ được bật ở chế độ phân tích sâu. Nếu kiểm chứng giảm số nhận định không có căn cứ nhưng tạo quá nhiều cảnh báo sai, ngưỡng sẽ được điều chỉnh trên bộ dữ liệu phát triển, không sửa trực tiếp theo bộ kiểm thử hồi quy. Cách làm này giúp mỗi thành phần có lý do tồn tại rõ ràng, thay vì làm kiến trúc phức tạp chỉ để gây ấn tượng.")
    set_paragraph_text(plan_b, (
        "Để bảo đảm tái lập, mỗi run phải tạo artifact bất biến liên kết commit, manifest, output summary, cấu hình "
        "và dấu vết runtime. Một release dựa trên outcome y tế chỉ có thể được cân nhắc sau khi các kết quả phù hợp "
        "được tái lập độc lập; hiện không có artifact như vậy trong repository."
    ))

    set_paragraph_text(find_last_paragraph(body, "39. TÓM TẮT KẾT QUẢ NỘI BỘ VÀ CÁCH DIỄN GIẢI"), "39. KẾT QUẢ CÓ THỂ BÁO CÁO VÀ CÁC KHOẢNG TRỐNG")
    result_intro = find_last_paragraph(body, "Các bằng chứng kỹ thuật hiện có cho CareGuard và lớp an toàn gồm bộ luật tương tác thuốc cục bộ, tình huống kiểm thử, từ điển tên gọi thay thế, kiểm tra từ chối và bước xác nhận ánh xạ. Mọi con số được báo cáo phải đi kèm phiên bản mã nguồn, ngày chạy, cấu hình, kích thước tập và phạm vi bao phủ. Đây là kết quả xác thực phần mềm trên tập nội bộ, không phải bằng chứng về độ an toàn lâm sàng. Khi mã nguồn hoặc dữ liệu đánh giá thay đổi, bảng kết quả phải được tạo lại từ phiên bản chính thức tương ứng.")
    set_paragraph_text(result_intro, (
        "Kết quả mới duy nhất được tạo lại trong audit này là kiểm tra toàn vẹn manifest fixture. Lệnh `python3 -m "
        "evaluation.clara_eval.run --config evaluation/configs/smoke.yaml --output artifacts/clara-eval-vn/smoke` chạy tại "
        "revision 524907ccc59ff1677e22e48990620fd014810d13 tạo artifact lúc 2026-08-06T19:25:39Z: 9/9 fixture "
        "tổng hợp có checksum/count hợp lệ (Wilson 95% CI 0.701–1.000). Đây là bằng chứng quản trị artifact, không "
        "phải benchmark chất lượng hay kết quả lâm sàng."
    ))
    result_table = find_table(body, "Chỉ số nội bộ | Snapshot đang được dự án sử dụng | Cách diễn giải đúng")
    replace_table(result_table, [
        ["Loại bằng chứng", "Quan sát/repository basis", "Kết luận được phép"],
        ["Kiểm tra mới, tái lập", "9/9 fixture smoke qua checksum/count manifest; 12 bản ghi synthetic; commit + timestamp nêu trên", "Chỉ manifest integrity được xác nhận; không có product-quality metric được đo."],
        ["Chất lượng sản phẩm", "28 metric trong smoke report là not_measured", "Không có Precision/Recall/nDCG, grounding, DDI, Council, Scribe, longitudinal, latency hay cost outcome."],
        ["Asset/pre-check lịch sử", "~62 local DDI rules; ~50 internal cases; 217 aliases; 10/10 refusal prompt gate", "Inventory/cổng hẹp có giới hạn; không phải sensitivity, specificity, accuracy, coverage hoặc resilience."],
        ["Bản ghi Deep Beta lịch sử", "Một Markdown nêu số liệu nhưng JSON report tham chiếu không có trong checkout", "Loại khỏi kết quả: không tái lập, không dùng cho claim hoặc so sánh."],
        ["Clinical/external evidence", "Không có participant, clinician review, external set, prospective/multisite, security assessment độc lập", "Không thể kết luận clinical safety, utility, readiness, generalizability hoặc superiority."]
    ])
    # Replace the existing report-principle single-cell table with an unambiguous evidence boundary.
    report_principle = find_table(body, "Nguyên tắc báo cáo:")
    replace_table(report_principle, [[
        "Ranh giới báo cáo: 9/9 chỉ nghĩa là chín fixture tổng hợp có manifest hợp lệ. “10/10” chỉ là cổng prompt hẹp. "
        "Không con số nào trong hai số đó là độ chính xác, độ an toàn hay hiệu quả trong thực tế. Mọi RQ1–RQ6 hiện là "
        "not_measured cho đến khi có dataset/reference standard/execution/adjudication được phê duyệt và lưu trace."
    ]])

    set_paragraph_text(find_last_paragraph(body, "40. THẢO LUẬN, GIỚI HẠN VÀ ĐE DỌA TỚI TÍNH HỢP LỆ"), "40. THẢO LUẬN, GIỚI HẠN VÀ RANH GIỚI SUY LUẬN")
    limitation_a = find_last_paragraph(body, "Giới hạn đầu tiên nằm ở chất lượng và độ cập nhật của nguồn: RAG không thể bù đắp cho tài liệu yếu hoặc thiếu bằng chứng. Giới hạn thứ hai liên quan đến mô hình, nhà cung cấp và thời gian đáp ứng; chế độ Deep Beta có thể xử lý chậm hơn khi đường truyền hoặc nguồn bên ngoài không ổn định. Giới hạn thứ ba là mức độ bản địa hóa: tên thuốc, cách diễn đạt và bản ghi hội thoại tiếng Việt vẫn cần một bộ kiểm thử ngày càng rộng. Giới hạn cuối cùng là việc đánh giá lâm sàng phải tiếp tục được thực hiện trong từng môi trường sử dụng; các phép đo kỹ thuật không thể tự thay thế cho bằng chứng về hiệu quả chăm sóc.")
    set_paragraph_text(limitation_a, (
        "Giới hạn chủ đạo là thiếu bằng chứng outcome. Không có so sánh retrieval/grounding, chuẩn DDI đầy đủ, "
        "expert reference, nghiên cứu Scribe/workflow, dataset ngoài, đánh giá prospective/multisite hay subgroup "
        "Việt Nam. Mô hình, provider, corpus/index snapshot, retrieval configuration, prompt/runtime trace và per-query "
        "cost cũng chưa được thực thi/đóng băng cho một benchmark. Vì vậy, kiến trúc và unit/contract test không tương "
        "đương với demonstrated safety, clinical benefit, scalability hoặc readiness."
    ))
    limitation_b = find_last_paragraph(body, "Những yếu tố có thể làm giảm độ tin cậy của kết quả gồm thiên lệch khi chọn tập kiểm thử, thiên lệch do tự đánh giá, sự thay đổi của nguồn kết nối, trùng lặp giữa tình huống kiểm thử và bộ luật, kích thước mẫu nhỏ và việc dùng chỉ số thay thế cho kết quả lâm sàng. Các giới hạn này cần được công bố cùng kết quả để tránh diễn giải quá mức.")
    set_paragraph_text(limitation_b, (
        "Ngay cả sau khi có benchmark nội bộ, nguy cơ selection bias, rule-test leakage, self-evaluation bias, label "
        "error, spectrum bias, stochastic variance và source drift vẫn phải được định lượng. Ngoài ra, chưa có systematic "
        "prompt/file-injection testing, privacy leakage testing, cross-profile testing at scale, penetration testing hay "
        "calibration analysis độc lập. Các khoảng trống này giới hạn cả tính nội tại lẫn ngoại suy của mọi claim tương lai."
    ))
    section_401 = find_last_paragraph(body, "40.1. Phân tích lỗi theo nhóm nguyên nhân")
    heading_template = section_401
    extra = [
        new_paragraph(heading_template, "40.2. Tính mới và so sánh"),
        new_paragraph(limitation_a, "Đóng góp có thể bảo vệ ở revision này là đóng gói nhiều cơ chế đã triển khai thành một nguyên mẫu có ranh giới an toàn và truy vết phiên bản. Đây là claim hệ thống/thiết kế, không phải claim superiority. Các bảng so sánh với “chatbot”, “search tool” hay “PHR” chỉ có giá trị bối cảnh; không phải baseline tái lập, đối đầu trực tiếp hoặc bằng chứng tính mới thực nghiệm."),
        new_paragraph(heading_template, "40.3. Bằng chứng cần có trước khi mở rộng claim"),
        new_paragraph(limitation_a, "Trước khi công bố hiệu năng, cần dữ liệu đã phê duyệt và có reference standard; model/retrieval/runtime snapshot bất biến; phép đo paired có effect size/CI; và phân xử độc lập. Trước khi công bố lợi ích workflow hoặc người dùng, cần một nghiên cứu có participant, đối chứng, thời gian/chi phí và hại được ghi nhận. Trước khi nói về lâm sàng hoặc mở rộng cơ sở, cần đánh giá độc lập, external, privacy/security và prospective phù hợp với intended use hẹp đã khóa."),
    ]
    # Insert after the last paragraph of 40.1, just before Chapter 41.
    last_401 = find_last_paragraph(body, "Đối với mô hình hoặc nhà cung cấp có tính ngẫu nhiên, nhóm phân biệt lỗi xuất hiện không ổn định với lỗi có thể lặp lại theo quy tắc. Những trường hợp không ổn định được chạy nhiều lần để đo độ biến thiên và có thể chuyển sang đầu ra có cấu trúc, giảm độ ngẫu nhiên hoặc dùng phương án xử lý theo quy tắc. Kết quả không thể tái lập phải được ghi rõ, thay vì chỉ chọn một lần chạy thuận lợi.")
    insert_after(body, last_401, extra)

    # Future deployment text must not be read as a completed pilot or evidence of benefit.
    implementation_heading = find_last_paragraph(body, "42. KỊCH BẢN TRIỂN KHAI")
    set_paragraph_text(implementation_heading, "42. KỊCH BẢN TRIỂN KHAI DỰ KIẾN (CHƯA PHẢI PILOT HAY BẰNG CHỨNG VẬN HÀNH)")
    implementation_paragraphs = body_paragraphs(body)
    implementation_index = implementation_paragraphs.index(implementation_heading)
    set_paragraph_text(implementation_paragraphs[implementation_index + 1], (
        "Chương này chỉ đề xuất các kịch bản nghiên cứu/triển khai có quản trị; không mô tả một pilot đã diễn ra, "
        "người dùng đã tuyển, cơ sở đã tham gia hay outcome đã quan sát. Mỗi bối cảnh chỉ có thể được mở sau khi "
        "khóa intended use, dữ liệu, người chịu trách nhiệm, phê duyệt phù hợp và thước đo hại/lợi ích."
    ))
    set_paragraph_text(implementation_paragraphs[implementation_index + 2], (
        "Mọi nhận định về tiết kiệm thời gian, giảm bỏ sót, phối hợp tốt hơn hoặc chấp nhận của người dùng trong "
        "chương này là endpoint dự kiến. Chúng không được coi là kết quả cho đến khi một nghiên cứu có comparator, "
        "denominator, đo thời gian, giám sát hại và phân tích được công bố theo giao thức."
    ))

    # End with a bounded conclusion.
    conclusion_heading = find_last_paragraph(body, "KẾT LUẬN")
    conclusion_index = body_paragraphs(body).index(conclusion_heading)
    conclusion = body_paragraphs(body)
    set_paragraph_text(conclusion[conclusion_index + 1], (
        "Audit này cho thấy CLARA-Care là một nguyên mẫu tích hợp có mã nguồn, cơ chế kiểm soát và fixture "
        "tổng hợp để kiểm tra một số hợp đồng kỹ thuật. Nó chưa chứng minh lợi ích lâm sàng, độ chính xác y khoa, "
        "an toàn trong thực tế, hiệu quả workflow, giảm chi phí hay khả năng mở rộng tổ chức."
    ))
    set_paragraph_text(conclusion[conclusion_index + 2], (
        "Kết quả tái lập duy nhất trong revision là toàn vẹn 9/9 manifest fixture tổng hợp tại commit đã nêu. "
        "Cả 28 metric chất lượng sản phẩm trong smoke suite đều được hệ thống ghi nhận trung thực là not_measured. "
        "Các asset nội bộ và test hợp đồng cho thấy cơ chế có thể được kiểm tra, không thay thế benchmark hay xác nhận độc lập."
    ))
    set_paragraph_text(conclusion[conclusion_index + 3], (
        "Bước tiếp theo không phải mở rộng claim mà là thực hiện một nghiên cứu hẹp, có dữ liệu và chuẩn tham chiếu "
        "được phê duyệt, với phương pháp và ranh giới sử dụng được khóa trước. Cho đến khi các bằng chứng đó tồn tại, "
        "CLARA-Care chỉ nên được mô tả là một nền tảng nguyên mẫu phục vụ nghiên cứu và xác thực kỹ thuật tiếp theo."
    ))

    entries["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


if __name__ == "__main__":
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("THT FINAL _ CLARA Care.docx")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("THT FINAL _ CLARA Care - scientific-revision.docx")
    main(source_path, output_path)
    print(output_path)
