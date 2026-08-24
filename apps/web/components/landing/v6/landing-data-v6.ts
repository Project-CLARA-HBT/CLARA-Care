export type V6DemoSource = {
  id: string;
  name: string;
  type: string;
  authority: string;
  authorityLevel: "National" | "International" | "Regulatory" | "Peer-Reviewed";
  relevanceVi: string;
  relevanceEn: string;
  applicabilityVi: string;
  applicabilityEn: string;
  limitationsVi: string;
  limitationsEn: string;
  updated: string;
};

export type V6DemoMedicine = {
  id: string;
  name: string;
  dosage: string;
  schedule: string;
  category: string;
  state: "current" | "needs-confirmation" | "cabinet";
  fidesStatus: "verified" | "pending" | "storage-only";
  noteVi: string;
  noteEn: string;
};

export type V6DemoPhrField = {
  id: string;
  labelVi: string;
  labelEn: string;
  valueVi: string;
  valueEn: string;
  status: "allowed" | "blocked";
  reasonVi: string;
  reasonEn: string;
};

export const V6_DEMO_SOURCES: V6DemoSource[] = [
  {
    id: "dav-national",
    name: "Dược thư Quốc gia Việt Nam (DAV)",
    type: "Dược điển & Hướng dẫn Quốc gia",
    authority: "Bộ Y tế Việt Nam / Cục Quản lý Dược",
    authorityLevel: "National",
    relevanceVi: "Quy chuẩn liều lượng, chỉ định và chống chỉ định chính thức cho lưu hành dược phẩm tại Việt Nam.",
    relevanceEn: "Official standard for drug dosage, indications, and contraindications in Vietnam.",
    applicabilityVi: "Áp dụng cho mọi cơ sở y tế và đơn thuốc được kê trong lãnh thổ Việt Nam.",
    applicabilityEn: "Mandatory standard for all prescriptions within Vietnamese clinical practice.",
    limitationsVi: "Chu kỳ cập nhật theo ấn bản định kỳ (2-3 năm/lần); cần đối chiếu cảnh báo nhanh khi có thuốc mới.",
    limitationsEn: "Periodic revision cycles; require supplementary fast alerts for newly introduced molecules.",
    updated: "2024 (Ấn bản III)",
  },
  {
    id: "drugbank-51",
    name: "DrugBank 5.1 Comprehensive",
    type: "Cơ sở Dữ liệu Dược lý Chuyên sâu",
    authority: "OMx Technologies / University of Alberta",
    authorityLevel: "International",
    relevanceVi: "Cơ chế tác dụng phân tử, enzym chuyển hóa CYP450 và ma trận tương tác thuốc - thuốc (DDI).",
    relevanceEn: "Molecular mechanisms of action, CYP450 metabolism pathways, and comprehensive DDI matrices.",
    applicabilityVi: "Kiểm tra tự động tương tác dược động học và dược lực học đa thuốc.",
    applicabilityEn: "Automated multi-drug pharmacokinetic and pharmacodynamic cross-checking.",
    limitationsVi: "Dữ liệu quốc tế cần bản địa hóa theo biệt dược và hàm lượng lưu hành tại Việt Nam.",
    limitationsEn: "Global dataset requires localization against locally registered brands and strengths.",
    updated: "08/2026",
  },
  {
    id: "who-guidelines",
    name: "WHO Guidelines for Essential Medicines",
    type: "Hướng dẫn Điều trị Quốc tế",
    authority: "Tổ chức Y tế Thế giới",
    authorityLevel: "International",
    relevanceVi: "Phác đồ điều trị chuẩn cho các bệnh mạn tính: Tăng huyết áp, Đái tháo đường, Tim mạch.",
    relevanceEn: "Standard treatment protocols for major non-communicable chronic diseases.",
    applicabilityVi: "Định hướng phân tầng nguy cơ và phác đồ bậc thang cho cộng đồng.",
    applicabilityEn: "Population-level risk stratification and stepped-care protocols.",
    limitationsVi: "Thiết kế cho y tế toàn cầu, cần điều chỉnh theo nguồn lực và dịch tễ học từng quốc gia.",
    limitationsEn: "Global scope; must be tailored to national resources and epidemiology.",
    updated: "2025",
  },
  {
    id: "fda-alerts",
    name: "FDA Drug Safety Communications",
    type: "Cảnh báo Dược phẩm Khẩn cấp",
    authority: "US Food and Drug Administration",
    authorityLevel: "Regulatory",
    relevanceVi: "Cảnh báo thu hồi, độc tính mới phát hiện trên tim mạch/thận và thay đổi nhãn thuốc.",
    relevanceEn: "Real-time safety alerts, newly discovered organ toxicities, and black-box revisions.",
    applicabilityVi: "Cảnh báo khẩn khi phát hiện rủi ro nghiêm trọng trên các nhóm bệnh nhân đặc thù.",
    applicabilityEn: "Immediate escalation for critical drug safety signals in vulnerable cohorts.",
    limitationsVi: "Áp dụng theo quy định của Hoa Kỳ; một số thuốc có thể có tên thương mại khác tại Việt Nam.",
    limitationsEn: "US regulatory framework; brand nomenclature may differ from regional naming.",
    updated: "Tuần này",
  },
  {
    id: "pubmed-rct",
    name: "PubMed / MEDLINE Clinical Queries",
    type: "Y văn & Thử nghiệm Lâm sàng (RCT)",
    authority: "National Library of Medicine (NLM)",
    authorityLevel: "Peer-Reviewed",
    relevanceVi: "Bằng chứng nghiên cứu ngẫu nhiên có đối chứng và phân tích gộp (Meta-analysis) mới nhất.",
    relevanceEn: "Latest randomized controlled trials and peer-reviewed meta-analyses.",
    applicabilityVi: "Hỗ trợ bác sĩ trong các ca bệnh phức tạp chưa có đồng thuận rõ ràng.",
    applicabilityEn: "Clinical decision support for nuanced cases without single established consensus.",
    limitationsVi: "Kết quả nghiên cứu cần được bác sĩ đánh giá phù hợp với thể trạng cụ thể của bệnh nhân.",
    limitationsEn: "Trial findings require physician interpretation regarding patient-specific comorbidities.",
    updated: "Hàng ngày",
  },
];

export const V6_DEMO_MEDICINES: V6DemoMedicine[] = [
  {
    id: "med-1",
    name: "Metformin HCl",
    dosage: "500 mg",
    schedule: "1 viên × 2 lần/ngày (Sau bữa ăn chính)",
    category: "Đái tháo đường Type 2",
    state: "current",
    fidesStatus: "verified",
    noteVi: "Theo dõi chức năng thận định kỳ. Tránh uống khi bụng rỗng để giảm kích ứng tiêu hóa.",
    noteEn: "Periodic renal monitoring indicated. Take with meals to minimize GI side effects.",
  },
  {
    id: "med-2",
    name: "Amlodipine Besylate",
    dosage: "5 mg",
    schedule: "1 viên × 1 lần/ngày (08:00 sáng)",
    category: "Hạ huyết áp (Chẹn kênh Canxi)",
    state: "current",
    fidesStatus: "verified",
    noteVi: "Duy trì uống đúng giờ mỗi ngày. Đã kiểm tra: Không đối kháng nguy hiểm với Metformin.",
    noteEn: "Maintain regular daily timing. Verified: No severe antagonism with Metformin.",
  },
  {
    id: "med-3",
    name: "Gliclazide MR",
    dosage: "30 mg",
    schedule: "Đang chờ bác sĩ xác nhận liều mới",
    category: "Hạ đường huyết (Sulfonylurea)",
    state: "needs-confirmation",
    fidesStatus: "pending",
    noteVi: "Cần xác nhận liều chính thức từ đơn khám ngày 20/08 trước khi đưa vào lịch uống hàng ngày.",
    noteEn: "Awaiting formal dosage confirmation from Aug 20 visit before active scheduling.",
  },
  {
    id: "med-4",
    name: "Paracetamol",
    dosage: "500 mg",
    schedule: "Chỉ dùng khi sốt hoặc đau đầu",
    category: "Giảm đau / Hạ sốt",
    state: "cabinet",
    fidesStatus: "storage-only",
    noteVi: "Thuốc dự phòng tủ gia đình. Không dùng quá 3000mg/ngày. Tránh lặp liều gần nhau.",
    noteEn: "Cabinet reserve. Do not exceed 3000mg/day. Space doses by at least 4-6 hours.",
  },
  {
    id: "med-5",
    name: "Berberin",
    dosage: "100 mg",
    schedule: "Thuốc hỗ trợ tiêu hóa (Tủ gia đình)",
    category: "Tiêu hóa dự phòng",
    state: "cabinet",
    fidesStatus: "storage-only",
    noteVi: "Thuốc tủ gia đình. Lưu trữ ở nơi khô ráo, tránh ánh sáng trực tiếp.",
    noteEn: "Home medicine cabinet inventory. Keep in cool, dry storage.",
  },
];

export const V6_DEMO_PHR_FIELDS: V6DemoPhrField[] = [
  {
    id: "phr-allergies",
    labelVi: "Tiền sử Dị ứng",
    labelEn: "Allergy History",
    valueVi: "Dị ứng Penicillin (Phát ban nhẹ, 2018)",
    valueEn: "Penicillin Allergy (Mild urticaria, 2018)",
    status: "allowed",
    reasonVi: "Bắt buộc chia sẻ để bác sĩ lựa chọn kháng sinh an toàn.",
    reasonEn: "Mandatory share item to ensure safe antibiotic prescription.",
  },
  {
    id: "phr-active-meds",
    labelVi: "Danh mục Thuốc đang dùng",
    labelEn: "Active Medication List",
    valueVi: "Metformin 500mg, Amlodipine 5mg",
    valueEn: "Metformin 500mg, Amlodipine 5mg",
    status: "allowed",
    reasonVi: "Cần thiết để kiểm tra tương tác thuốc trong phiên khám.",
    reasonEn: "Essential for in-consultation drug-drug interaction checks.",
  },
  {
    id: "phr-vitals",
    labelVi: "Chỉ số Huyết áp & Đường huyết",
    labelEn: "Vitals & Glucose Logs",
    valueVi: "Nhật ký đo HA 60 ngày gần nhất (Trung bình 126/82 mmHg)",
    valueEn: "60-day home BP log (Average 126/82 mmHg)",
    status: "allowed",
    reasonVi: "Được cấp phép cho Bác sĩ Tim mạch theo dõi đáp ứng thuốc.",
    reasonEn: "Granted to consulting Cardiologist to assess therapeutic response.",
  },
  {
    id: "phr-sensitive-notes",
    labelVi: "Ghi chú & Nhật ký Riêng tư",
    labelEn: "Private Personal Notes",
    valueVi: "Nhật ký tâm lý & sinh hoạt cá nhân",
    valueEn: "Personal mood and lifestyle logs",
    status: "blocked",
    reasonVi: "Bị chặn tại cổng: Không liên quan đến phạm vi chuyên khoa Tim mạch.",
    reasonEn: "Halted at boundary: Outside the clinical scope of Cardiology review.",
  },
  {
    id: "phr-financial",
    labelVi: "Thông tin Bảo hiểm & Viện phí",
    labelEn: "Billing & Insurance Data",
    valueVi: "Chi tiết thẻ BHYT & Lịch sử thanh toán",
    valueEn: "Health insurance policy and payment records",
    status: "blocked",
    reasonVi: "Bị chặn tại cổng: Không được đính kèm vào gói chia sẻ lâm sàng.",
    reasonEn: "Halted at boundary: Excluded from clinical consultation packet.",
  },
];
