# VN Medical PDF Source Catalog Deepdive (Phase-1 Part-1)

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-29  
Phạm vi: nguồn PDF y khoa Việt Nam phục vụ CLARA Research + Self-Med

## 1) Mục tiêu và cách đọc

Tài liệu này tổng hợp các nguồn PDF y khoa Việt Nam có thể thu thập hợp pháp, ưu tiên nguồn chính thức của Bộ Y tế và đơn vị trực thuộc.

Mỗi nguồn có các trường thực thi:
- URL truy cập trực tiếp (entry URL + ví dụ URL PDF tải trực tiếp nếu xác minh được).
- Đơn vị sở hữu nguồn.
- Nhóm nguồn (guideline, dược, cảnh giác dược, học thuật, công cộng).
- Nhịp cập nhật quan sát được.
- Ghi chú sử dụng cho ingest.
- Trust tier.
- Mức chắc chắn xác minh (`verified` / `partial` / `uncertain`).

## 2) Mức độ tin cậy (Trust Tier)

- `A1`: Cơ quan ban hành gốc cấp Bộ/Cục trên domain chính thức nhà nước.
- `A2`: Đơn vị trực thuộc chính thức hoặc cổng phụ trợ chính thức (dữ liệu vẫn thuộc BYT).
- `B1`: Tạp chí/kho dữ liệu chính thức của bệnh viện, đại học, hội nghề nghiệp.
- `C1`: Nguồn mirror/pháp lý bên thứ ba, chỉ dùng đối chiếu khi nguồn gốc tạm thiếu.

## 3) Danh mục nguồn VN PDF (catalog)

| ID | Source owner | Category | Entry URL | Direct PDF URL (example) | Update cadence (observed) | Usage notes | Trust tier | Confidence |
|---|---|---|---|---|---|---|---|---|
| VN-DT-01 | Hội đồng Dược thư QG / BYT | Dược thư Quốc gia | https://duocquocgia.com.vn/ | N/A (site trả `502` khi kiểm tra ngày 2026-03-29) | Không xác định do site gián đoạn | Nguồn gốc chính cho Dược thư; cần health-check định kỳ để tự động mở lại ingest khi site hoạt động lại | A1 | verified |
| VN-DT-02 | Bộ Y tế (quyết định ban hành) qua mirror pháp lý | Dược thư Quốc gia (văn bản quyết định) | https://luatvietnam.vn/y-te/quyet-dinh-3445-qd-byt-2022-ban-hanh-duoc-thu-quoc-gia-viet-nam-lan-xuat-ban-thu-ba-313553-d1.html | URL chứa toàn văn quyết định (không phải bản PDF gốc BYT) | Ổn định tĩnh | Chỉ dùng đối chiếu số quyết định, không dùng làm bản chuẩn nội dung chuyên luận | C1 | partial |
| VN-DT-03 | Bộ Y tế (quyết định ban hành) qua mirror pháp lý | Dược thư tuyến cơ sở | https://vbpl.ts24.com.vn/support/solutions/articles/16000042729-quy%E1%BA%BFt-%C4%91%E1%BB%8Bnh-5539-q%C4%91-byt-d%C6%B0%E1%BB%A3c-th%C6%B0-qu%E1%BB%91c-gia-vi%E1%BB%87t-nam-d%C3%B9ng-cho-tuy%E1%BA%BFn-y-t%E1%BA%BF-c%C6%A1-s%E1%BB%9F-l%E1%BA%A7n-xu%E1%BA%A5t-b%E1%BA%A3n-th%E1%BB%A9-2 | URL chứa toàn văn quyết định (không phải bản PDF gốc BYT) | Ổn định tĩnh | Chỉ dùng để bootstrap metadata khi nguồn gốc BYT chưa truy xuất được | C1 | partial |
| VN-MOH-01 | Cục Quản lý Khám chữa bệnh (BYT) | Guideline chẩn đoán/điều trị | https://kcb.vn/thu-vien-tai-lieu | Ví dụ PDF trực tiếp: https://kcb.vn/upload/2005611/20210723/H%C6%B0%E1%BB%9Bng-d%E1%BA%ABn-ch%E1%BA%A9n-%C4%91o%C3%A1n-v%C3%A0-%C4%91i%E1%BB%81u-tr%E1%BB%8B-S%E1%BA%A3n-ph%E1%BB%A5-khoa.pdf | Ad-hoc (theo quyết định ban hành) | Nguồn chính cho guideline chuyên khoa; ưu tiên crawl theo chuyên mục + file list | A1 | verified |
| VN-MOH-02 | Cục Quản lý Khám chữa bệnh (BYT) | Guideline sản phụ khoa | https://kcb.vn/thu-vien-tai-lieu/huong-dan-chan-doan-va-dieu-tri-cac-benh-san-phu-khoa.html | File list chứa: `/Hướng-dẫn-chẩn-đoán-và-điều-trị-Sản-phụ-khoa.pdf` | Ít thay đổi, dạng archive | Crawl page + resolve link tương đối thành URL tuyệt đối | A1 | verified |
| VN-MOH-03 | Cục Quản lý Khám chữa bệnh (BYT) | Guideline viêm gan B | https://kcb.vn/thu-vien-tai-lieu/huong-dan-chan-doan-dieu-tri-benh-viem-gan-vi-rut-b.html | File list chứa: `/Hướng-dẫn-chẩn-đoán-và-điều-trị-bệnh-viêm-gan-vi-rút-B.pdf` | Ít thay đổi | Lấy metadata từ số QĐ-BYT hiển thị trên trang | A1 | verified |
| VN-MOH-04 | Cục Quản lý Khám chữa bệnh (BYT) | Guideline da liễu | https://kcb.vn/phac-do/huong-dan-chan-doan-va-dieu-tri-cac-benh-da-lieu.html | File list chứa: `/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf` | Ít thay đổi | Nhóm guideline cũ nhưng còn giá trị tham chiếu và citation | A1 | verified |
| VN-MOH-05 | Cục Quản lý Khám chữa bệnh (BYT) | Nhiễm khuẩn bệnh viện | https://kcb.vn/quy-trinh/tai-lieu-huong-dan-phong-ngua-chuan-trong-cac-co-so-kham-chu.html | File list chứa: `/3.huong-dan-phong-ngua-chuan.pdf` | Ít thay đổi | Nên gắn tag `infection_control` để truy hồi đúng intent | A1 | verified |
| VN-MOH-06 | Cục Quản lý Khám chữa bệnh (BYT) | COVID guideline | https://kcb.vn/phac-do/tai-lieu-huong-dan-thiet-lap-co-so-thu-dung-dieu-tri-covid-19-theo-mo-hinh-thap-3-tang.html | File list chứa: `/Huong-dan-co-so-thu-dung-COVID-mo-hinh-thap-3-tang_trinh-ky-25.8.signed.pdf` | Theo đợt dịch/chính sách | Đánh dấu `legacy_covid` để tránh ưu tiên cao cho truy vấn hiện hành nếu guideline đã cũ | A1 | verified |
| VN-MOH-07 | Cổng BYT (hạ tầng attach) | Tài liệu chuyên môn BYT (nhiều lĩnh vực) | https://moh.gov.vn/ | Ví dụ: https://emohbackup.moh.gov.vn/publish/attach/getfile/35713 | Liên tục, ad-hoc | Endpoint `getfile/{id}` dùng tốt cho ingest theo id mapping | A1 | verified |
| VN-MOH-08 | Cổng BYT (hạ tầng attach) | Tài liệu chuyên môn BYT | https://emohbackup.moh.gov.vn/publish/attach/getfile/35703 | https://emohbackup.moh.gov.vn/publish/attach/getfile/35703 | Liên tục, ad-hoc | Cần crawler theo danh sách quyết định để tránh quét id tuần tự | A1 | partial |
| VN-YDCT-01 | Cục Quản lý Y Dược cổ truyền (BYT) | Văn bản + guideline YHCT | https://ydct.moh.gov.vn/category/van-ban | Ví dụ trực tiếp: https://ydct.moh.gov.vn/static/files/uploads/bec97baf7acd25948bb814f6c5c2990f16f46ee453f0d23dd0b83fa8b85622ba.pdf | Hàng tuần/tháng | Domain chính thức, có nhiều tài liệu PDF chuyên ngành | A2 | verified |
| VN-YDCT-02 | Cục Quản lý Y Dược cổ truyền (BYT) | Guideline YHCT tập II | https://ydct.moh.gov.vn/detail/quyet-dinh-3991-qd-byt-ngay-29-12-2025-ve-viec-ban-hanh-tai-lieu-chuyen-mon-huong-dan-chan-doan-va-dieu-tri-benh-theo-y-hoc-co-truyen-ket-hop-y-hoc-co-truyen-voi-y-hoc-hien-dai-tap-ii | https://ydct.moh.gov.vn/static/files/uploads/bec97baf7acd25948bb814f6c5c2990f16f46ee453f0d23dd0b83fa8b85622ba.pdf | Theo quyết định ban hành | Có thể trích số QĐ-BYT + ngày từ tiêu đề page | A2 | verified |
| VN-YDCT-03 | Cục Quản lý Y Dược cổ truyền (BYT) | Quy trình kỹ thuật YHCT | https://ydct.moh.gov.vn/detail/quyet-dinh-so-486-qd-byt-ngay-13-02-2026-cua-bo-truong-bo-y-te-ve-viec-ban-hanh-tai-lieu-chuyen-mon-huong-dan-quy-trinh-ky-thuat-chuyen-nganh-y-hoc-co-truyen | Link tải xuất hiện trên trang chi tiết (không cố định slug) | Hàng tháng | Cần parser lấy link `Tải xuống` động thay vì hardcode | A2 | partial |
| VN-MCH-01 | Cục Bà mẹ và Trẻ em (BYT) | Văn bản hướng dẫn chuyên môn | https://mch.moh.gov.vn/ | Trang có mục “Văn bản” và nút tải tệp đính kèm | Hàng tháng/quý | Nguồn tốt cho SRH/maternal-child guidelines | A2 | verified |
| VN-MCH-02 | Cục Bà mẹ và Trẻ em (BYT) | Sàng lọc ung thư vú | https://mch.moh.gov.vn/cong-tac-cham-soc-suc-khoe-sinh-san/huong-dan-sang-loc-phat-hien-som-ung-thu-vu.html | Tệp đính kèm theo QĐ 3898/QĐ-BYT (trên page) | Theo đợt ban hành | Cần connector đọc bảng metadata + link đính kèm | A2 | verified |
| VN-DAV-01 | Cục Quản lý Dược (BYT) | Thông báo chất lượng, công văn, thu hồi | https://dav.gov.vn/thong-tin-thuoc-qlchatluong/page-1.html | Ví dụ file trực tiếp cũ: https://dav.gov.vn/upload/attach/2592015_18055_qld_cl.pdf | Hàng ngày/tuần | Nguồn bắt buộc cho cảnh báo thuốc giả và chất lượng | A1 | verified |
| VN-DAV-02 | Cục Quản lý Dược (BYT) | Cảnh báo thuốc giả | https://dav.gov.vn/cong-van-cua-cuc-quan-ly-duoc-ve-thuoc-gia-cephalexin-500mg-ne1664.html | Ví dụ file đính kèm: https://dav.gov.vn/upload_images/files/4138_QLD_CL_signed.pdf | Hàng tuần | Ưu tiên crawl mục thuốc giả và không đạt chất lượng | A1 | verified |
| VN-DAV-03 | Cục Quản lý Dược (BYT) | Cảnh báo thuốc lưu hành trái phép | https://dav.gov.vn/cong-van-so-1001qld-cl-ve-viec-canh-bao-thuoc-gia-thuoc-luu-hanh-trai-phep-tren-thi-truong-thuoc-tiem-yeztugo-lenacapavir-injection-4635g15ml-309mgml-n5271.html | Link đính kèm xuất hiện trong trang (ví dụ `1001_QLD_CL_signed.pdf`) | Hàng tuần | Cần parser robust vì cấu trúc HTML/URL file không hoàn toàn nhất quán | A1 | partial |
| VN-DAV-04 | Cục Quản lý Dược (BYT) | Công bố GMP nước ngoài | https://dav.gov.vn/cong-van-so-684qld-cl-ve-viec-cong-bo-ket-qua-danh-gia-dap-ung-gmp-cua-co-so-san-xuat-nuoc-ngoai-dot-50-n5225.html | Nhiều file phụ lục đính kèm trên cùng page | Định kỳ theo đợt | Hữu ích cho trust filtering nhà sản xuất trong tư vấn thuốc | A1 | verified |
| VN-DAV-05 | Cục Quản lý Dược (DVC) | Công bố thuốc lưu hành | https://dichvucong.dav.gov.vn/congbothuoc/ | Export/web table | Liên tục | Dùng làm nguồn chuẩn hóa legal status thuốc | A1 | verified |
| VN-DAV-06 | Cục Quản lý Dược (DVC) | Công bố thuốc không kê đơn | https://dichvucong.dav.gov.vn/congbothuockhongkedon | Export/web table | Liên tục | Quan trọng cho luồng Self-Med OTC guardrail | A1 | verified |
| VN-DAV-07 | Cục Quản lý Dược (DVC) | Công bố thuốc vi phạm chất lượng | https://dichvucong.dav.gov.vn/congbothuocvipham/index | Export/web table | Liên tục | Tạo blocklist theo số đăng ký/lô sản xuất | A1 | verified |
| VN-DIADR-01 | Trung tâm DI & ADR Quốc gia | Cổng thông tin chính | https://canhgiacduoc.org.vn/ | Nhiều bài có tệp đính kèm/điều hướng sang magazine | Hàng tuần | Nguồn chính thống cho pharmacovigilance Việt Nam | A1 | verified |
| VN-DIADR-02 | Trung tâm DI & ADR Quốc gia | Bản tin Cảnh giác Dược | https://magazine.canhgiacduoc.org.vn/Volume/Details/71 | Tải toàn bộ số: https://magazine.canhgiacduoc.org.vn/Volume/Download/71 | Theo số (quan sát 2025 có 4 số) | Nên ingest full issue + tách bài | A1 | partial |
| VN-DIADR-03 | Trung tâm DI & ADR Quốc gia | Bản tin Cảnh giác Dược | https://magazine.canhgiacduoc.org.vn/Volume/Details/72 | Tải toàn bộ số: https://magazine.canhgiacduoc.org.vn/Volume/Download/72 | Theo số (quý) | Đã xác minh endpoint download hoạt động | A1 | verified |
| VN-DIADR-04 | Trung tâm DI & ADR Quốc gia | Chuyên mục bản tin quốc gia | https://canhgiacduoc.org.vn/CanhGiacDuoc/DiemTin/AnPham/BanTinQuocGia | PDF theo số bản tin | Theo số | Dùng crawl bổ sung khi magazine index lỗi | A1 | verified |
| VN-DIADR-05 | Trung tâm DI & ADR Quốc gia | Thông tin thuốc | https://canhgiacduoc.org.vn/CanhGiacDuoc/DiemTin/ThongTinThuoc | Bài + tài liệu tham khảo | Hàng tuần | Gắn nhãn `drug_safety_vn` cho retrieval ưu tiên | A1 | verified |
| VN-DIADR-06 | Trung tâm DI & ADR Quốc gia | Báo cáo ADR trực tuyến | http://baocaoadr.vn/ | Form/portal nghiệp vụ (không crawl nội dung cá nhân) | Liên tục | Chỉ thu metadata public; không ingest dữ liệu cá nhân báo cáo ADR | A1 | verified |
| VN-PUB-01 | Cục Y tế dự phòng (BYT) | Hướng dẫn dịch tễ + văn bản đính kèm | https://vncdc.gov.vn/ | Ví dụ PDF trực tiếp: https://vncdc.gov.vn/mediacenter/media/files/1012/09-2021/490_1631088059_21261386dbb2c9c0.pdf | Ad-hoc theo dịch tễ | Cần parser khu vực danh sách tệp đính kèm trên bài | A2 | verified |
| VN-PUB-02 | Cục Y tế dự phòng (BYT) | Bài hướng dẫn có file đính kèm | https://vncdc.gov.vn/bo-y-te-ban-hanh-huong-dan-tam-thoi-kham-sang-loc-truoc-tiem-chung-vac-xin-phong-covid-19-nd16507.html | Download link nằm trong bài | Ad-hoc | Cần chống trùng lặp do nhiều bài trỏ cùng 1 PDF | A2 | verified |
| VN-PUB-03 | Viện Sốt rét-KST-CT Quy Nhơn (BYT) | Hướng dẫn sốt rét | https://www.impe-qn.org.vn/van-ban-cua-bo-y-te/quyet-dinh-so-3377qd-byt-ngay-3082023-huong-dan-chan-doan-va-dieu-tri-benh-sot/ct/33/11734 | Ví dụ PDF trực tiếp (bản 2020): https://impe-qn.org.vn/impe-qn/vn/upload/info/file/1588918983040_huong%20dan%20chuan%20doan%20va%20dieu%20tri%20sot%20ret_file_pdf.pdf | Ad-hoc | Nguồn chuyên ngành truyền nhiễm/ký sinh trùng, dùng bổ sung cho KCB | A2 | verified |
| VN-PUB-04 | Viện Sốt rét-KST-CT Quy Nhơn (BYT) | Hướng dẫn sốt rét 2020 | https://www.impe-qn.org.vn/van-ban-cua-bo-y-te/quyet-dinh-so-2699qd-byt-ve-viec-huong-dan-chan-doan-dieu-tri-benh-sot-ret-nam/ctmb/33/11091 | Bài liệt kê 2 file đính kèm trực tiếp | Thấp (archive) | Dùng làm baseline lịch sử guideline thay thế theo version | A2 | verified |
| VN-UNI-01 | Trường ĐH Dược Hà Nội (HUP) | Tạp chí Nghiên cứu Dược & TT thuốc (JPRDI) | https://jprdi.vn/ | Bài mẫu: https://jprdi.vn/JP/article/view/171 (có nút tải PDF) | 6 số/năm (theo giới thiệu tạp chí) | Nguồn học thuật dược chính thức, nên ingest metadata + PDF fulltext | B1 | verified |
| VN-UNI-02 | Trường ĐH Dược Hà Nội (HUP) | Bài nghiên cứu dược | https://jprdi.vn/JP/article/view/315 | Tải PDF từ mục `Tải xuống` trong bài | Theo số tạp chí | Cần parser OJS (`article/view`) để lấy direct PDF URL | B1 | verified |
| VN-HOSP-01 | BV TWQĐ 108 | Journal of 108 - Clinical Medicine & Pharmacy | https://tcydls108.benhvien108.vn/index.php/YDLS | Ví dụ trang PDF-view: https://tcydls108.benhvien108.vn/index.php/YDLS/article/view/1380/1218 | Liên tục theo số tạp chí | Nguồn bệnh viện tuyến cuối, hữu ích cho evidence nội địa | B1 | verified |
| VN-HOSP-02 | BV TWQĐ 108 | OJS PDF viewer endpoint | https://tcydls108.benhvien108.vn/plugins/generic/pdfJsViewer/pdf.js/web/viewer.html?file=https%3A%2F%2Ftcydls108.benhvien108.vn%2Findex.php%2FYDLS%2Farticle%2Fdownload%2F4%2F4%2F | URL chứa file PDF thực qua tham số `file=` | Liên tục | Có thể tách URL PDF thật từ query param `file` để ingest trực tiếp | B1 | verified |
| VN-UNI-03 | Trường ĐH Y Hà Nội | Kho dữ liệu số HMU | https://dulieuso.hmu.edu.vn/ | Ví dụ item: https://dulieuso.hmu.edu.vn/handle/hmu/5726 | Liên tục | Nhiều file `Restricted Access`; chỉ ingest metadata khi chưa có quyền đọc PDF | B1 | verified |
| VN-UNI-04 | Trường ĐH Y Hà Nội | HMU DSpace metadata archive | https://dulieuso.hmu.edu.vn/handle/hmu/4583 | PDF hiện trạng: `Restricted Access` | Liên tục | Không bypass auth; lưu trạng thái quyền truy cập trong catalog | B1 | verified |
| VN-PUB-05 | Tạp chí Y học Việt Nam | Journal issue + PDF theo bài/số | https://tapchiyhocvietnam.vn/index.php/vmj/issue/view/381 | Tải full issue (ví dụ): https://tapchiyhocvietnam.vn/index.php/vmj/issue/download/343/539 | Theo số (quan sát nhiều số/năm) | Nguồn học thuật lớn, thích hợp ingestion quy mô batch | B1 | verified |
| VN-PUB-06 | BV Bạch Mai (site khoa) | Mirror guideline từ KCB | https://chanthuongvacotsong.bachmai.gov.vn/phac-do/ | Ví dụ file tương đối: `/Hướng-dẫn-phòng-ngừa-nhiễm-khuẩn-vết-mổ.pdf` | Không ổn định (mirror nội bộ) | Chỉ dùng làm nguồn dự phòng khi KCB lỗi; ưu tiên nguồn gốc KCB | B1 | partial |

## 4) Tổng quan độ phủ hiện tại

### 4.1 Theo nhóm nguồn

- Dược thư Quốc gia: 3 mục (1 nguồn gốc chính thức đang gián đoạn + 2 mirror pháp lý đối chiếu).
- Bộ Y tế guideline/PDF (KCB + emohbackup + YDCT + MCH): 13 mục.
- Cục Quản lý Dược (DAV + DVC): 7 mục.
- DI & ADR: 6 mục.
- Đại học/bệnh viện/công cộng: 12 mục.

Tổng catalog hiện tại: `41` mục.

### 4.2 Theo trust tier

- `A1`: 22
- `A2`: 9
- `B1`: 8
- `C1`: 2

### 4.3 Điểm chưa chắc chắn cần theo dõi

- Cổng `duocquocgia.com.vn` trả `502` tại thời điểm kiểm tra; chưa xác nhận được URL PDF chuyên luận chính thức còn hoạt động.
- Một số trang DAV/YDCT cung cấp link tải động theo nội dung bài, chưa phù hợp hardcode URL file.
- HMU DSpace có nhiều PDF ở trạng thái restricted; cần tuân thủ bản quyền và quyền truy cập.

## 5) Chiến lược thu thập (acquisition strategy) khả thi và an toàn

## 5.1 Ràng buộc pháp lý/an toàn crawler

- Chỉ crawl các URL công khai; không vượt qua đăng nhập/CAPTCHA/paywall.
- Tuân thủ `robots.txt` và điều khoản sử dụng từng site; nếu mâu thuẫn, dừng crawl và mở legal review.
- Tôn trọng hạ tầng cơ quan nhà nước: mặc định `<= 0.2 req/s/domain`, burst tối đa `2`, retry exponential backoff.
- Dữ liệu có yếu tố cá nhân (VD portal ADR report) chỉ thu metadata public, không thu nội dung cá nhân.
- Bắt buộc lưu nguồn gốc: `source_url`, `retrieved_at`, `publisher`, `license_note` (nếu có).

## 5.2 Chuẩn dedupe

Dedupe 3 lớp:

1. `URL canonical dedupe`
- Chuẩn hóa scheme/host/path, bỏ tracking query.
- Chuẩn hóa Unicode path và percent-encoding.

2. `Metadata dedupe`
- Khóa nghiệp vụ: `(issuer, decision_no, decision_date, title_norm)`.
- Với tạp chí: `(journal, volume, issue, article_doi_or_slug)`.

3. `Content dedupe`
- Hash bắt buộc: `sha256` trên bytes gốc.
- Hash nhanh bổ sung: `xxh3_64` để so sánh tốc độ.
- Nếu OCR scan có biến thể nhẹ: thêm `simhash` văn bản trích xuất để phát hiện near-duplicate.

## 5.3 Versioning + checksum

Đề xuất layout lưu trữ bất biến (object storage hoặc filesystem):

```text
vn-medical-pdf/
  raw/{source_key}/{yyyy}/{mm}/{dd}/{doc_id}/{sha256}.pdf
  meta/{source_key}/{yyyy}/{mm}/{dd}/{doc_id}.json
  normalized/{doc_uid}/v{n}.json
```

`doc_uid` được sinh từ metadata-key ổn định; mỗi lần file thay đổi hash -> tăng `v{n}`.

Manifest chuẩn mỗi bản ingest:

```json
{
  "doc_uid": "dav-qldcl-2026-684",
  "source_key": "dav",
  "source_url": "https://dav.gov.vn/...",
  "download_url": "https://dav.gov.vn/upload_images/files/...pdf",
  "retrieved_at": "2026-03-29T08:10:33Z",
  "http_etag": "...",
  "http_last_modified": "...",
  "size_bytes": 248920,
  "sha256": "...",
  "xxh3_64": "...",
  "content_type": "application/pdf",
  "decision_no": "684/QLD-CL",
  "decision_date": "2026-03-02",
  "title": "...",
  "publisher": "Cục Quản lý Dược - Bộ Y tế",
  "trust_tier": "A1",
  "access": "public"
}
```

## 5.4 Freshness schedule

Đề xuất lịch đồng bộ theo mức độ rủi ro nghiệp vụ:

- `Hằng ngày` (T+0/T+1): DAV, DI&ADR magazine, canhgiacduoc, DVC DAV.
- `3 lần/tuần`: KCB, YDCT, MCH, VNCDC.
- `Hằng tuần`: IMPE, Journal 108, JPRDI, Tạp chí Y học Việt Nam.
- `Hằng tháng`: HMU DSpace metadata scan, mirror sources.
- `Health-check mỗi 6 giờ`: duocquocgia.com.vn (để reopen ingest tự động khi site khôi phục).

SLA freshness gợi ý:
- Safety-critical (thuốc giả/thu hồi/cảnh giác dược): phát hiện thay đổi <= 24h.
- Guideline chuyên môn: <= 72h.
- Học thuật/journal: <= 7 ngày.

## 6) Schema đề xuất cho engineering

## 6.1 `source_registry` (cấu hình nguồn)

```json
{
  "source_key": "dav",
  "name": "Cục Quản lý Dược",
  "owner": "Bộ Y tế",
  "category": "drug-regulatory",
  "entry_urls": ["https://dav.gov.vn/thong-tin-thuoc-qlchatluong/page-1.html"],
  "allowed_domains": ["dav.gov.vn", "dichvucong.dav.gov.vn"],
  "crawl_mode": "html_list_with_attachment",
  "default_schedule": "daily",
  "trust_tier": "A1",
  "legal_notes": "public web, respect robots and rate limit",
  "enabled": true
}
```

## 6.2 `document_manifest` (mỗi tài liệu)

```json
{
  "doc_uid": "string",
  "source_key": "string",
  "title": "string",
  "publisher": "string",
  "decision_no": "string|null",
  "decision_date": "YYYY-MM-DD|null",
  "language": "vi",
  "document_type": "guideline|notice|bulletin|journal_article|legal_text",
  "source_url": "https://...",
  "download_url": "https://...",
  "sha256": "hex",
  "size_bytes": 0,
  "mime_type": "application/pdf",
  "retrieved_at": "ISO-8601",
  "trust_tier": "A1|A2|B1|C1",
  "confidence": "verified|partial|uncertain",
  "is_active": true
}
```

## 7) Acceptance criteria cho Part-1 (research+documentation)

- Có catalog nguồn với URL cụ thể, phân loại rõ trust tier và confidence.
- Có chiến lược crawl/phiên bản hóa/dedupe/checksum đủ để chuyển sang triển khai code.
- Có lịch freshness rõ theo mức độ ưu tiên safety.
- Có chỉ ra khoảng mù dữ liệu (đặc biệt Dược thư Quốc gia khi cổng chính thức lỗi).

## 8) Khuyến nghị khởi động triển khai ngay sau Part-1

- Ưu tiên `A1/A2` trước (`DAV`, `KCB`, `DI&ADR`, `YDCT`, `MCH`, `VNCDC`, `IMPE`).
- Chỉ dùng `C1` làm fallback metadata, không dùng làm nguồn nội dung chuẩn.
- Mở ticket riêng theo dõi trạng thái `duocquocgia.com.vn` để bổ sung Dược thư chính thức ngay khi cổng khôi phục.

