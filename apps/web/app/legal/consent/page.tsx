import LegalPageShell, {
  LegalSection,
  type LegalSectionMeta,
} from "@/components/legal/legal-page-shell";
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
  { id: "user-undertakings", title: "3. Cam kết & trách nhiệm người dùng" },
  { id: "clinical-verification", title: "4. Yêu cầu xác nhận chuyên môn y tế" },
  { id: "emergency-fast-path", title: "5. Luồng xử lý tình huống khẩn cấp (115)" },
  { id: "consent-privacy-zero-cot", title: "6. Dữ liệu đồng thuận, Zero-PII & Zero-CoT" },
  { id: "withdrawal-dsar", title: "7. Quyền rút đồng thuận & Quản trị DSAR" },
  { id: "versioning-validity", title: "8. Phiên bản hóa & Hiệu lực áp dụng" },
  { id: "support-dpo", title: "9. Kênh hỗ trợ, DPO & Tiếp nhận phản ánh" },
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
          href: "/legal/privacy",
          label: "Chính sách quyền riêng tư",
          description: "Quản trị dữ liệu y tế nhạy cảm & DSAR",
        },
        {
          href: "/legal/terms",
          label: "Điều khoản sử dụng",
          description: "Ranh giới trách nhiệm & thỏa thuận dịch vụ",
        },
        {
          href: "/legal",
          label: "Trung tâm pháp lý",
          description: "Mục lục chính sách chính thức của hệ thống",
        },
      ]}
    >
      {/* 1. Bản chất hệ thống */}
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
      </LegalSection>

      {/* 2. Phạm vi bắt buộc */}
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

      {/* 3. Cam kết người dùng */}
      <LegalSection
        id="user-undertakings"
        title="3. Cam kết & Trách nhiệm của người dùng khi đồng thuận"
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
        </ul>
      </LegalSection>

      {/* 4. Xác nhận chuyên môn */}
      <LegalSection
        id="clinical-verification"
        title="4. Yêu cầu bắt buộc xác nhận chuyên môn y tế"
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
      </LegalSection>

      {/* 5. Tình huống khẩn cấp */}
      <LegalSection
        id="emergency-fast-path"
        title="5. Luồng xử lý tình huống khẩn cấp (Emergency Fast-Path)"
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

      {/* 6. Dữ liệu đồng thuận & Zero-CoT */}
      <LegalSection
        id="consent-privacy-zero-cot"
        title="6. Dữ liệu đồng thuận, Bảo đảm Zero-PII & Chuẩn Zero-CoT"
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

      {/* 7. Rút lại đồng thuận */}
      <LegalSection
        id="withdrawal-dsar"
        title="7. Quyền rút lại đồng thuận & Quản trị quyền dữ liệu (DSAR)"
        badge="Nghị định 13/2023"
      >
        <p>
          Theo Điều 12 Nghị định 13/2023/NĐ-CP, bạn có quyền <strong>rút lại sự đồng ý</strong> bất kỳ lúc
          nào:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Bạn có thể tắt đồng thuận y tế trực tiếp tại trang Quản lý tài khoản hoặc gửi yêu cầu tới Cán bộ
            bảo vệ dữ liệu.
          </li>
          <li>
            Khi rút lại đồng thuận, các tính năng chuyên môn nhạy cảm (CareGuard, Council, DDI) sẽ tự động
            khóa lại để bảo đảm an toàn, trong khi dữ liệu hồ sơ cá nhân hiện có vẫn được bảo lưu an toàn cho
            đến khi bạn có yêu cầu xóa.
          </li>
          <li>
            Việc rút lại đồng thuận không ảnh hưởng đến tính hợp pháp của các hoạt động xử lý dữ liệu đã thực
            hiện trước thời điểm rút.
          </li>
        </ul>
      </LegalSection>

      {/* 8. Phiên bản hóa & Hiệu lực */}
      <LegalSection
        id="versioning-validity"
        title="8. Phiên bản hóa, Lưu vết kiểm toán & Hiệu lực áp dụng"
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
            <span className="font-semibold text-[var(--status-ok-text)]">Toàn bộ nền tảng The Clara Care</span>
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)] pt-2">
          Khi có thay đổi lớn về thuật toán hoặc ranh giới an toàn, người dùng sẽ được yêu cầu xem lại và xác
          nhận phiên bản mới trước khi tiếp tục thao tác trên các tính năng chuyên môn.
        </p>
      </LegalSection>

      {/* 9. Kênh hỗ trợ */}
      <LegalSection
        id="support-dpo"
        title="9. Kênh hỗ trợ, DPO & Tiếp nhận phản ánh lâm sàng"
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

