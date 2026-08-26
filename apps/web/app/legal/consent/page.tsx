import Link from "next/link";
import LegalPageShell, {
  LegalSection,
  type LegalSectionMeta,
} from "@/components/legal/legal-page-shell";
import { ConsentStatusPreviewWidget } from "@/components/legal/consent-status-preview-widget";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Đồng thuận sử dụng y tế & Ranh giới lâm sàng | The Clara Care",
  description:
    "Điều khoản đồng thuận bắt buộc trước khi sử dụng các tính năng có tác động lâm sàng trong The Clara Care theo Luật Khám bệnh 2023, Nghị định 13/2023/NĐ-CP và Luật AI 134/2025.",
};

const CONSENT_SECTIONS: LegalSectionMeta[] = [
  { id: "nature", title: "1. Bản chất hệ thống AI hỗ trợ lâm sàng" },
  { id: "scope", title: "2. Phạm vi tính năng bắt buộc đồng thuận" },
  { id: "purpose-pillars", title: "3. 5 Trụ cột đồng thuận theo mục đích (Purpose-Gated Pillars)" },
  { id: "clinical-verification", title: "4. Yêu cầu xác nhận chuyên môn y tế" },
  { id: "emergency-fast-path", title: "5. Luồng xử lý tình huống khẩn cấp (115)" },
  { id: "user-undertakings", title: "6. Cam kết & trách nhiệm người dùng" },
  { id: "withdrawal-dsar", title: "7. Quyền rút lại đồng thuận & Quản trị quyền dữ liệu (DSAR)" },
  { id: "cross-border-tia", title: "8. Chuyển giao dữ liệu suy luận xuyên biên giới & TIA" },
  { id: "consent-privacy-zero-cot", title: "9. Dữ liệu đồng thuận, Zero-PII & Zero-CoT" },
  { id: "status-preview", title: "10. Bảng điều khiển trạng thái đồng thuận trực quan" },
  { id: "versioning-validity", title: "11. Phiên bản hóa & Hiệu lực áp dụng" },
  { id: "support-dpo", title: "12. Kênh hỗ trợ, DPO & Tiếp nhận phản ánh" },
];

export default function MedicalConsentPage() {
  return (
    <LegalPageShell
      policyKey="consent"
      title="Đồng thuận sử dụng y tế & Ranh giới lâm sàng"
      summary="Đây là văn bản đồng thuận bắt buộc trước khi truy cập hoặc sử dụng các tính năng có tác động lâm sàng trong The Clara Care, nhằm bảo đảm bạn hiểu rõ bản chất hỗ trợ thông tin của AI, xác lập yêu cầu xác nhận chuyên môn của bác sĩ theo Luật Khám bệnh 2023, bảo vệ dữ liệu nhạy cảm theo Nghị định 13/2023/NĐ-CP và minh bạch hệ thống AI theo Luật 134/2025/QH15."
      updatedAt={LEGAL_UPDATED_AT}
      version={LEGAL_POLICY_VERSION}
      sections={CONSENT_SECTIONS}
      highlights={[
        "Bắt buộc chấp thuận trước khi kích hoạt Self-Medication, CareGuard, Council và Scribe.",
        "AI chỉ hỗ trợ thông tin và đối chiếu y văn, tuyệt đối không thay thế bác sĩ khám chữa bệnh.",
        "Mọi quyết định điều trị, kê đơn và đổi liều thuốc phải được nhân viên y tế xác nhận.",
        "Bảo đảm Zero-CoT và Zero-PII trong toàn bộ quá trình xử lý dữ liệu đồng thuận.",
      ]}
      relatedControls={[
        {
          href: "/account/consent",
          label: "Sổ cái đồng thuận cá nhân",
          description: "Quản lý và cấp/rút quyền các tính năng chuyên môn trực tiếp",
        },
        {
          href: "/safety",
          label: "Tuyên ngôn an toàn lâm sàng",
          description: "Chi tiết xác thực FIDES & 5 tầng an toàn",
        },
        {
          href: "/sources",
          label: "Danh mục nguồn y văn",
          description: "Dược thư Quốc gia, DrugBank & Hướng dẫn Bộ Y Tế",
        },
        {
          href: "/legal/privacy",
          label: "Chính sách quyền riêng tư",
          description: "Quản trị dữ liệu y tế nhạy cảm & DSAR",
        },
        {
          href: "/legal/terms",
          label: "Điều khoản sử dụng",
          description: "Ranh giới trách nhiệm & thỏa thuận dịch vụ",
        },
      ]}
    >
      {/* Visual Breadcrumbs & Statutory Header Badges */}
      <nav aria-label="Đường dẫn điều hướng" className="mb-2 flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)]">
        <Link href="/" className="hover:text-[var(--text-primary)] transition">Trang chủ</Link>
        <span className="text-[var(--text-muted)]">/</span>
        <Link href="/legal" className="hover:text-[var(--text-primary)] transition">Trung tâm pháp lý</Link>
        <span className="text-[var(--text-muted)]">/</span>
        <span className="font-bold text-[var(--text-brand)]">Đồng thuận y tế & Ranh giới lâm sàng</span>
      </nav>

      {/* Statutory Header Badges Card */}
      <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 sm:p-5 space-y-3">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="clinical-notes" size="1.1rem" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Căn cứ pháp lý y tế & Ranh giới bảo vệ người bệnh
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" icon="clinical-notes">
            Luật Khám bệnh số 15/2023/QH15
          </Badge>
          <Badge tone="ok" icon="check">
            Nghị định 13/2023/NĐ-CP (PDPD)
          </Badge>
          <Badge tone="neutral" icon="settings">
            Luật AI số 134/2025/QH15
          </Badge>
          <Badge tone="neutral" icon="folder">
            Tên miền: {LEGAL_PRIMARY_DOMAIN}
          </Badge>
          <Badge tone="neutral" icon="calendar">
            Phiên bản: {LEGAL_POLICY_VERSION}
          </Badge>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          Thỏa thuận này xác lập ranh giới vận hành, nguyên tắc đồng thuận theo mục đích (Purpose-Gated Consent),
          cam kết an toàn Zero-CoT/Zero-PII và các quyền tự quyết của người bệnh khi tương tác với hệ thống AI y tế CLARA.
        </p>
      </div>

      {/* 1. Bản chất hệ thống AI hỗ trợ lâm sàng */}
      <LegalSection
        id="nature"
        title="1. Bản chất của hệ thống AI hỗ trợ lâm sàng"
        badge="Bản chất dịch vụ"
      >
        <p>
          <strong>The Clara Care</strong> là hệ thống ứng dụng trí tuệ nhân tạo (AI) được phát triển nhằm
          hỗ trợ tra cứu tri thức y khoa, tổng hợp hồ sơ sức khỏe cá nhân (PHR), kiểm tra tương tác thuốc
          và gợi ý đối chiếu phác đồ điều trị dựa trên y văn chính thống (Living Evidence, Dược thư quốc
          gia Việt Nam, PubMed).
        </p>
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)]/70 bg-[var(--status-warn-bg)]/20 p-4 space-y-2 text-xs sm:text-sm">
          <p className="font-bold text-[var(--text-primary)]">
            Ranh giới lâm sàng theo Luật Khám bệnh, chữa bệnh số 15/2023/QH15:
          </p>
          <p className="text-[var(--text-secondary)]">
            The Clara Care <strong>KHÔNG PHẢI là bác sĩ</strong>, không có chức năng cấp chứng chỉ hành
            nghề, không thay thế cơ sở y tế và không đưa ra chẩn đoán y khoa chính thức. Hệ thống không tự
            ý ra y lệnh điều trị hoặc kê đơn thuốc độc lập.
          </p>
        </div>
        <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
          Mục tiêu tối thượng của The Clara Care là nâng cao năng lực tiếp cận y văn và chuẩn bị thông tin
          cho người bệnh trước khi thăm khám, đồng thời hỗ trợ nhân viên y tế tra cứu phác đồ và bằng chứng
          lâm sàng nhanh chóng và an toàn.
        </p>
      </LegalSection>

      {/* 2. Phạm vi tính năng bắt buộc đồng thuận */}
      <LegalSection
        id="scope"
        title="2. Phạm vi tính năng bắt buộc đồng thuận y tế"
        badge="Phạm vi bắt buộc"
      >
        <p>
          Sự đồng thuận này là <strong>điều kiện tiên quyết (gated consent)</strong> để kích hoạt các tính
          năng chuyên sâu và module an toàn cốt lõi trong hệ thống:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Tủ thuốc cá nhân & Tự dùng thuốc (Self-Medication):</strong> Tính năng tra cứu liều
            dùng, tác dụng phụ, đường dùng thuốc và nhắc lịch uống thuốc.
          </li>
          <li>
            <strong>Hàng rào an toàn lâm sàng (CareGuard):</strong> Phân tích tương tác thuốc bất lợi (DDI),
            phát hiện trùng lặp hoạt chất, cảnh báo chống chỉ định đối với tiền sử bệnh nền và dị ứng.
          </li>
          <li>
            <strong>Hội chẩn đa tác tử (Clinical Council):</strong> Mô phỏng phân tích y khoa đa chuyên
            khoa để cung cấp góc nhìn tham khảo cho nhân viên y tế và bệnh nhân.
          </li>
          <li>
            <strong>Trợ lý ghi chép y khoa (Scribe):</strong> Chuyển đổi giọng nói hội thoại y tế hoặc bóc
            tách tài liệu hình ảnh (OCR) thành bản tóm tắt lâm sàng có cấu trúc.
          </li>
          <li>
            <strong>Quản lý hồ sơ sức khỏe cá nhân (PHR & Lifemap):</strong> Lưu trữ và liên kết dữ liệu sinh
            hiệu, bệnh sử theo thời gian thực.
          </li>
        </ul>
      </LegalSection>

      {/* 3. 5 Trụ cột đồng thuận theo mục đích (Purpose-Gated Pillars) */}
      <LegalSection
        id="purpose-pillars"
        title="3. 5 Trụ cột đồng thuận theo mục đích (Purpose-Gated Consent Pillars)"
        badge="Kiến trúc đồng thuận"
      >
        <p>
          Tuân thủ nguyên tắc xử lý có mục đích và giảm thiểu dữ liệu theo Điều 9 và Điều 13 Nghị định 13/2023/NĐ-CP,
          The Clara Care phân tách sự đồng thuận của bạn thành <strong>5 Trụ cột độc lập</strong>, cho phép quản lý
          từng quyền xử lý riêng biệt mà không bị gộp chung hay ép buộc:
        </p>

        <div className="space-y-4 pt-2">
          {/* Purpose 1 */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-500)] text-xs font-bold text-white">
                  1
                </span>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Mục đích 1: Trợ lý thông tin y tế & Kiểm tra an toàn tương tác thuốc (Mandatory)
                </h3>
              </div>
              <Badge tone="ok">Bắt buộc · Căn cứ cốt lõi</Badge>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              <strong>Phạm vi xử lý:</strong> Hỗ trợ hỏi đáp triệu chứng, đối chiếu Living Evidence, Dược thư Quốc gia,
              kiểm tra tương tác thuốc DDI, cảnh báo dị ứng và chống chỉ định qua module CareGuard và FIDES Verification.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              <strong>Căn cứ pháp lý:</strong> Điều 15 Luật Khám bệnh, chữa bệnh 2023 và Điều 9 Nghị định 13/2023/NĐ-CP.
              Toàn bộ chuỗi suy luận logic (Zero-CoT) được tiêu hủy ngay sau phiên thực thi.
            </p>
          </div>

          {/* Purpose 2 */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-500)] text-xs font-bold text-white">
                  2
                </span>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Mục đích 2: Dòng thời gian sinh hiệu & Tổng hợp bối cảnh LifeMap (Optional)
                </h3>
              </div>
              <Badge tone="brand">Tùy chọn · Gated</Badge>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              <strong>Phạm vi xử lý:</strong> Phân tích chuỗi dữ liệu sinh hiệu liên tục (huyết áp, đường huyết, nhịp tim),
              tiền sử bệnh mạn tính và biểu đồ LifeMap nhằm phát hiện diễn tiến bất thường và chuẩn bị tóm tắt trước khám.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              <strong>Căn cứ pháp lý:</strong> Điều 9 & Điều 13 Nghị định 13/2023/NĐ-CP (Xử lý dữ liệu sức khỏe nhạy cảm).
              Bạn có thể bật hoặc tắt tính năng này bất kỳ lúc nào mà không ảnh hưởng tới các chức năng tra cứu cơ bản.
            </p>
          </div>

          {/* Purpose 3 */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-500)] text-xs font-bold text-white">
                  3
                </span>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Mục đích 3: Nghiên cứu y sinh học & Đối chiếu y văn sống (Anonymized)
                </h3>
              </div>
              <Badge tone="neutral">Khử định danh 100%</Badge>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              <strong>Phạm vi xử lý:</strong> Thu thập các cặp truy vấn hỏi - đáp lâm sàng đã loại bỏ 100% thông tin định danh
              (tên, số điện thoại, ngày sinh, địa chỉ) theo chuẩn Zero-PII nhằm đánh giá chuẩn xác mô hình AI y tế và hoàn thiện
              cơ sở dữ liệu Living Evidence tại Việt Nam.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              <strong>Căn cứ pháp lý:</strong> Điều 21 Nghị định 13/2023/NĐ-CP (Xử lý dữ liệu phục vụ nghiên cứu khoa học sau khi khử định danh).
            </p>
          </div>

          {/* Purpose 4 */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-500)] text-xs font-bold text-white">
                  4
                </span>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Mục đích 4: Suy luận mô hình xuyên biên giới không lưu vết (YEScale DeepSeek with TIA)
                </h3>
              </div>
              <Badge tone="brand">Đánh giá TIA · Zero Retention</Badge>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              <strong>Phạm vi xử lý:</strong> Chuyển tải các đoạn truy vấn đã tối thiểu hóa tới điểm cuối mô hình ngôn ngữ lớn DeepSeek
              (qua nhà cung cấp YEScale) nhằm thực hiện suy luận y khoa chuyên sâu.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              <strong>Bảo đảm an toàn:</strong> Tuân thủ thủ tục Đánh giá tác động chuyển giao dữ liệu (TIA) theo Điều 25 Nghị định 13/2023/NĐ-CP.
              Cam kết Zero Data Retention (không lưu nội dung tại máy chủ mô hình), mã hóa TLS 1.3 và không dùng dữ liệu để huấn luyện LLM công cộng.
            </p>
          </div>

          {/* Purpose 5 */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 sm:p-5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand-500)] text-xs font-bold text-white">
                  5
                </span>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Mục đích 5: Chia sẻ hồ sơ PHR có ranh giới cho người thân & Bác sĩ (Bounded PHR Sharing)
                </h3>
              </div>
              <Badge tone="neutral">Ủy quyền có thời hạn</Badge>
            </div>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
              <strong>Phạm vi xử lý:</strong> Cấp quyền truy cập chỉ đọc đối với hồ sơ sức khỏe cá nhân, nhật ký dùng thuốc và cảnh báo
              sinh hiệu cho người giám hộ, người chăm sóc chỉ định hoặc bác sĩ điều trị thông qua liên kết mã hóa và mã PIN xác thực.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              <strong>Căn cứ pháp lý:</strong> Điều 17 Nghị định 13/2023/NĐ-CP (Chuyển giao và phân quyền tiếp cận dữ liệu cá nhân).
              Bạn có quyền thu hồi mọi liên kết chia sẻ tức thì bằng 1 thao tác.
            </p>
          </div>
        </div>
      </LegalSection>

      {/* 4. Yêu cầu xác nhận chuyên môn y tế */}
      <LegalSection
        id="clinical-verification"
        title="4. Yêu cầu xác nhận chuyên môn y tế"
        badge="Luật Khám bệnh 2023"
      >
        <p>
          Căn cứ các quy định về an toàn người bệnh tại <strong>Luật Khám bệnh, chữa bệnh 2023</strong>:
        </p>
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2 text-xs sm:text-sm">
          <p className="font-bold text-[var(--text-primary)]">Quy tắc vàng trong quyết định lâm sàng:</p>
          <p className="text-[var(--text-secondary)]">
            Mọi kế hoạch điều trị, chỉ định xét nghiệm, thay đổi phác đồ dùng thuốc hoặc can thiệp y khoa
            <strong> bắt buộc phải được bác sĩ hoặc dược sĩ có chứng chỉ hành nghề trực tiếp đánh giá, xác
            nhận và chịu trách nhiệm pháp lý</strong> trước khi áp dụng trên người bệnh.
          </p>
        </div>
        <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
          The Clara Care đóng vai trò là công cụ tham vấn tri thức và tăng cường hiệu quả giao tiếp giữa bác sĩ
          và người bệnh, không tạo ra mối quan hệ pháp lý bác sĩ - bệnh nhân giữa hệ thống AI và người sử dụng.
        </p>
      </LegalSection>

      {/* 5. Luồng xử lý tình huống khẩn cấp */}
      <LegalSection
        id="emergency-fast-path"
        title="5. Luồng xử lý tình huống khẩn cấp (115)"
        badge="Cấp cứu khẩn cấp"
      >
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)]/70 bg-[var(--status-danger-bg)]/20 p-4 space-y-2">
          <div className="flex items-center gap-2 text-[var(--status-danger-text)] font-bold text-sm">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--status-danger-text)] animate-ping" />
            <span>KHI GẶP TÌNH HUỐNG Y TẾ NGUY CẤP:</span>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-primary)]">
            Nếu bạn hoặc người thân xuất hiện các triệu chứng cấp cứu đe dọa tính mạng (đau thắt ngực dữ dội,
            khó thở nặng, yếu liệt nửa người, co giật, hôn mê, sốc phản vệ, xuất huyết tiêu hóa ồ ạt hoặc chấn
            thương nặng):
          </p>
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <a
              href="tel:115"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-4 py-2 text-xs font-bold text-[var(--status-danger-text)] shadow-sm hover:brightness-110"
            >
              <span>GỌI NGAY CẤP CỨU 115</span>
            </a>
            <span className="text-xs text-[var(--text-muted)] font-medium">
              Hoặc đến ngay khoa Cấp cứu của bệnh viện gần nhất
            </span>
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)] pt-2">
          Trong trường hợp này, The Clara Care sẽ tự động kích hoạt luồng chuyển hướng cấp cứu và chặn hoàn
          toàn các bước suy luận chẩn đoán AI để không làm chậm trễ thời gian cấp cứu vàng của bệnh nhân.
        </p>
      </LegalSection>

      {/* 6. Cam kết & trách nhiệm người dùng */}
      <LegalSection
        id="user-undertakings"
        title="6. Cam kết & Trách nhiệm của người dùng khi đồng thuận"
        badge="Cam kết người dùng"
      >
        <p>Bằng việc nhấn xác nhận đồng thuận hoặc tiếp tục sử dụng các tính năng lâm sàng, bạn cam kết:</p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Cung cấp thông tin đầy đủ, chính xác và trung thực về các loại thuốc đang dùng, tiền sử dị ứng,
            bệnh nền và chỉ số sinh hiệu thực tế.
          </li>
          <li>
            Không tự ý ngưng thuốc, đổi thuốc, tăng hoặc giảm liều lượng được bác sĩ kê đơn chỉ dựa trên gợi
            ý từ hệ thống AI mà không tham vấn ý kiến chuyên môn.
          </li>
          <li>
            Hiểu rõ rằng gợi ý của AI là kết quả xử lý xác suất thống kê dựa trên dữ liệu tham chiếu và có
            thể có độ trễ so với các hướng dẫn lâm sàng cập nhật mới nhất.
          </li>
          <li>
            Bảo mật tài khoản cá nhân, mã PIN và không chia sẻ token truy cập hồ sơ sức khỏe cho các bên thứ ba
            không có thẩm quyền.
          </li>
        </ul>
      </LegalSection>

      {/* 7. Quyền rút lại đồng thuận & DSAR */}
      <LegalSection
        id="withdrawal-dsar"
        title="7. Quyền rút lại đồng thuận & Quản trị quyền dữ liệu (DSAR)"
        badge="Quyền của người bệnh"
      >
        <p>
          Căn cứ Điều 12 và Điều 9 Nghị định 13/2023/NĐ-CP, bạn là chủ thể dữ liệu và có toàn quyền tự quyết
          đối với dữ liệu sức khỏe của mình:
        </p>

        <div className="grid gap-3 pt-2 sm:grid-cols-3 text-xs">
          {/* Right 1: 1-Click Withdrawal */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-[var(--text-brand)]">
              <Icon name="trash" size="0.95rem" />
              <span>Rút đồng thuận 1-chạm</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              Bạn có thể tắt đồng thuận cho từng mục đích tùy chọn bất kỳ lúc nào tại Sổ cái đồng thuận cá nhân
              với hiệu lực tức thì.
            </p>
          </div>

          {/* Right 2: Data Portability */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-[var(--status-ok-text)]">
              <Icon name="download" size="0.95rem" />
              <span>Quyền chuyển giao dữ liệu</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              Yêu cầu xuất toàn bộ hồ sơ sức khỏe cá nhân (PHR) dưới định dạng mở máy đọc được (JSON, CSV, PDF chuẩn HL7).
            </p>
          </div>

          {/* Right 3: Erasure */}
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-amber-500">
              <Icon name="close" size="0.95rem" />
              <span>Quyền xóa dữ liệu (Erasure)</span>
            </div>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              Yêu cầu xóa vĩnh viễn hoặc khử định danh hoàn toàn toàn bộ hồ sơ dữ liệu cá nhân trong thời hạn tối đa 72h làm việc.
            </p>
          </div>
        </div>

        <div className="pt-2 flex flex-wrap items-center gap-3">
          <Link
            href="/account/consent"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand-600)] px-4 py-2 text-xs font-bold text-[var(--text-on-brand)] shadow-sm hover:bg-[var(--brand-500)] transition"
          >
            <Icon name="clinical-notes" size="0.95rem" />
            <span>Mở Sổ cái đồng thuận cá nhân</span>
          </Link>
          <Link
            href="/legal/privacy"
            className="inline-flex items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] transition"
          >
            <span>Quy trình gửi yêu cầu DSAR</span>
          </Link>
        </div>

        <p className="text-xs text-[var(--text-muted)] pt-1">
          Việc rút lại đồng thuận không ảnh hưởng đến tính hợp pháp của các hoạt động xử lý dữ liệu đã thực
          hiện hợp lệ trước thời điểm rút.
        </p>
      </LegalSection>

      {/* 8. Chuyển giao dữ liệu xuyên biên giới & TIA */}
      <LegalSection
        id="cross-border-tia"
        title="8. Chuyển giao dữ liệu suy luận xuyên biên giới & Đánh giá TIA"
        badge="Nghị định 13/2023 §25"
      >
        <p>
          Để cung cấp khả năng phân tích y văn chính xác cao, The Clara Care sử dụng các điểm cuối suy luận mô hình
          ngôn ngữ lớn DeepSeek đặt tại hạ tầng đối tác chuyên biệt (YEScale) ngoài lãnh thổ Việt Nam. Hoạt động này
          tuân thủ chặt chẽ các điều kiện tại <strong>Điều 25 Nghị định 13/2023/NĐ-CP</strong>:
        </p>

        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Hồ sơ Đánh giá Tác động Chuyển giao (TIA):</strong> Đơn vị vận hành đã lập và lưu trữ hồ sơ đánh
            giá mức độ an toàn dữ liệu, sẵn sàng phục vụ công tác thanh tra của Cục An ninh mạng và Phòng, chống tội phạm
            sử dụng công nghệ cao (Bộ Công an).
          </li>
          <li>
            <strong>Chuẩn Zero Data Retention (ZDR):</strong> Điểm cuối YEScale DeepSeek chỉ nhận dữ liệu để tạo phản hồi
            ngay trong phiên (in-flight inference) và không lưu trữ bản ghi truy vấn hoặc phản hồi vào ổ cứng.
          </li>
          <li>
            <strong>Không dùng dữ liệu để tái huấn luyện:</strong> Toàn bộ dữ liệu hội thoại y tế của bạn được bảo đảm
            tuyệt đối không bị trích xuất để huấn luyện hay tinh chỉnh (fine-tune) bất kỳ mô hình AI thương mại nào.
          </li>
          <li>
            <strong>Mã hóa đầu cuối TLS 1.3:</strong> Đường truyền dữ liệu xuyên biên giới được bảo vệ bằng giao thức mã
            hóa tiên tiến nhất, chống lại mọi hình thức giải mã hoặc chặn bắt trung gian.
          </li>
        </ul>
      </LegalSection>

      {/* 9. Dữ liệu đồng thuận, Zero-PII & Zero-CoT */}
      <LegalSection
        id="consent-privacy-zero-cot"
        title="9. Dữ liệu đồng thuận, Bảo đảm Zero-PII & Chuẩn Zero-CoT"
        badge="Bảo vệ dữ liệu"
      >
        <p>
          Theo quy định tại <strong>Nghị định 13/2023/NĐ-CP</strong> về bảo vệ dữ liệu cá nhân nhạy cảm:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Bản ghi đồng thuận phi định danh:</strong> Hệ thống lưu trữ lịch sử đồng thuận dưới dạng
            mã băm bảo mật (mã phiên bản đồng thuận, dấu thời gian UTC, ID người dùng ẩn danh), không lưu
            thêm bất kỳ thông tin định danh nhạy cảm nào vào bản ghi kiểm toán.
          </li>
          <li>
            <strong>Chuẩn Zero-CoT bất biến:</strong> Toàn bộ chuỗi suy luận logic lâm sàng (Chain-of-Thought)
            của các tác tử AI được hủy ngay sau khi trả lời; không lưu trữ vĩnh viễn và không bao giờ được
            chia sẻ ra bên ngoài.
          </li>
          <li>
            <strong>Không chia sẻ thương mại:</strong> Dữ liệu sức khỏe và thông tin đồng thuận không bao
            giờ bị bán hoặc thương mại hóa cho các công ty bảo hiểm hay quảng cáo.
          </li>
        </ul>
      </LegalSection>

      {/* 10. Bảng điều khiển trạng thái đồng thuận trực quan */}
      <LegalSection
        id="status-preview"
        title="10. Bảng điều khiển trạng thái đồng thuận tương tác"
        badge="Widget tương tác"
      >
        <p>
          Dưới đây là widget tương tác minh họa trực tiếp cơ chế Purpose-Gated Consent của hệ thống. Bạn có thể
          thử nghiệm bật/tắt từng trụ cột để xem cách thức hệ thống phản ứng và điều chỉnh năng lực lâm sàng:
        </p>

        <div className="pt-2">
          <ConsentStatusPreviewWidget />
        </div>
      </LegalSection>

      {/* 11. Phiên bản hóa & Hiệu lực */}
      <LegalSection
        id="versioning-validity"
        title="11. Phiên bản hóa, Lưu vết kiểm toán & Hiệu lực áp dụng"
        badge="Lưu vết chính sách"
      >
        <p>
          Văn bản đồng thuận này được phiên bản hóa chính thức nhằm phục vụ công tác đối chiếu và kiểm tra
          tuân thủ:
        </p>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-2 text-xs sm:text-sm">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
            <span className="text-[var(--text-muted)]">Phiên bản đồng thuận hiện hành:</span>
            <span className="font-mono font-bold text-[var(--text-brand)]">{LEGAL_POLICY_VERSION}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-2">
            <span className="text-[var(--text-muted)]">Ngày công bố áp dụng:</span>
            <span className="font-semibold text-[var(--text-primary)]">{LEGAL_UPDATED_AT}</span>
          </div>
          <div className="flex items-center justify-between pt-0.5">
            <span className="text-[var(--text-muted)]">Phạm vi áp dụng:</span>
            <span className="font-semibold text-[var(--status-ok-text)]">Toàn bộ nền tảng The Clara Care ({LEGAL_PRIMARY_DOMAIN})</span>
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)] pt-2">
          Khi có thay đổi lớn về thuật toán hoặc ranh giới an toàn, người dùng sẽ được yêu cầu xem lại và xác
          nhận phiên bản mới trước khi tiếp tục thao tác trên các tính năng chuyên môn.
        </p>
      </LegalSection>

      {/* 12. Kênh hỗ trợ */}
      <LegalSection
        id="support-dpo"
        title="12. Kênh hỗ trợ, DPO & Tiếp nhận phản ánh lâm sàng"
        badge="Liên hệ tuân thủ"
      >
        <p>
          Mọi ý kiến đóng góp, phản ánh sự cố y khoa hoặc thắc mắc về phạm vi đồng thuận y tế vui lòng liên
          hệ:
        </p>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 text-xs sm:text-sm">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Đơn vị vận hành:</span>
            <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Email hỗ trợ y tế & DPO:</span>
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
              {LEGAL_CONTACT_EMAIL}
            </a>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Hotline tư vấn kỹ thuật:</span>
            <a href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`} className="font-bold text-[var(--text-primary)] hover:underline">
              {LEGAL_CONTACT_PHONE}
            </a>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-[var(--text-muted)]">Thời hạn phản hồi:</span>
            <span className="font-semibold text-[var(--status-ok-text)]">Trong 72 giờ làm việc</span>
          </div>
        </div>
      </LegalSection>
    </LegalPageShell>
  );
}
