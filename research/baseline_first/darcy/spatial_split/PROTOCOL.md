# Ghép hai bộ nội suy ở ranh giới hình học

Phân tích hậu nghiệm sau khi đã thấy boosting thường có lỗi thấp hơn ở mép còn stencil bốn đỉnh có lỗi thấp hơn ở phần trong. Thử một quy tắc duy nhất trên tất cả bốn cohort đã mở. Chọn stencil bốn đỉnh ở mọi vị trí thiếu trừ hàng và cột cuối, dùng boosting cùng đầu vào ở hàng/cột cuối. Đối chứng là hai thành phần đơn và ghép ngược. Không chỉnh trọng số, ngưỡng hay vùng theo từng nguồn. Hai mô hình đều phải được fit. Không có claim giảm chi phí. Không đếm đây thành bài riêng.

Hai vùng không giao nhau nên có thể dựng chính xác relative L2 toàn trường từ sai số chuẩn hóa từng vùng và norm của nhãn từng vùng. Kiểm tra cách dựng bằng việc khôi phục toàn bộ điểm đã ghi của từng arm trong sai số số học. Lưu mọi trường và tỉ lệ thắng từng nguồn. Cách ghép không nhìn nhãn fine khi dự báo; lý do chọn vùng xuất phát từ kết quả đã xem. Cần tập xác nhận mới và đối chứng gate được học trên calibration để kết luận lợi thế mới.
