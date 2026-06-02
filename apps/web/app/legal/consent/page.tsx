import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_POLICY_VERSION, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Đồng thuận sử dụng y tế | The Clara Care",
  description: "Điều khoản đồng thuận bắt buộc khi dùng các tính năng có rủi ro lâm sàng trong The Clara Care.",
};

const CONSENT_SECTIONS = [
  { id: "nature", label: "Bản chất hệ thống" },
  { id: "scope", label: "Phạm vi bắt buộc" },
  { id: "user-commitment", label: "Cam kết người dùng" },
  { id: "clinical-verification", label: "Xác nhận chuyên môn" },
  { id: "emergency", label: "Xử lý tình huống khẩn" },
  { id: "consent-data", label: "Dữ liệu đồng thuận" },
  { id: "withdrawal", label: "Rút lại đồng thuận" },
  { id: "versioning", label: "Version và hiệu lực" },
  { id: "support", label: "Liên hệ hỗ trợ" },
] as const;

export default function MedicalConsentPage() {
  return (
    <LegalPageShell
      policyKey="consent"
      title="Đồng thuận sử dụng y tế"
      summary="Đây là điều khoản bắt buộc trước khi truy cập các tính năng có ảnh hưởng lâm sàng trong The Clara Care, nhằm đảm bảo người dùng hiểu đúng giới hạn của hệ thống và trách nhiệm xác thực chuyên môn."
      updatedAt={LEGAL_UPDATED_AT}
      sections={CONSENT_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Bắt buộc trước khi dùng luồng Self-Med, CareGuard và các tính năng safety-critical.",
        "AI chỉ mang tính hỗ trợ thông tin, không thay thế chỉ định y khoa.",
        "Mọi quyết định điều trị phải do nhân sự có thẩm quyền xác nhận.",
        `Phiên bản đồng thuận hiện hành: ${LEGAL_POLICY_VERSION}.`,
      ]}
    >
      <LegalSection id="nature" title="1. Bản chất của hệ thống">
        <p>
          The Clara Care là nền tảng hỗ trợ thu thập, tổng hợp và gợi ý thông tin y khoa dựa trên dữ liệu truy xuất. Hệ thống không
          phải là bác sĩ, không tự đưa ra chẩn đoán cuối cùng và không thay thế quy trình khám chữa bệnh trực tiếp.
        </p>
      </LegalSection>

      <LegalSection id="scope" title="2. Phạm vi bắt buộc đồng thuận">
        <p>
          Đồng thuận này bắt buộc đối với các tính năng có nguy cơ ảnh hưởng quyết định lâm sàng như phân tích tương tác thuốc,
          cảnh báo safety, gợi ý xử trí và các luồng hỗ trợ hội chẩn có yếu tố can thiệp điều trị.
        </p>
      </LegalSection>

      <LegalSection id="user-commitment" title="3. Cam kết của người dùng khi đồng thuận">
        <ul className="list-disc space-y-2 pl-5">
          <li>Không dùng kết quả AI để tự chẩn đoán hoặc tự điều trị khi không có chuyên môn phù hợp.</li>
          <li>Luôn đối chiếu thông tin với guideline chính thống và tình trạng người bệnh thực tế.</li>
          <li>Không nhập dữ liệu sai lệch có chủ ý nhằm tạo khuyến nghị không phù hợp.</li>
        </ul>
      </LegalSection>

      <LegalSection id="clinical-verification" title="4. Yêu cầu xác nhận chuyên môn">
        <p>
          Mọi quyết định liên quan đơn thuốc, liều dùng, thay đổi phác đồ hoặc xử trí tình trạng nguy cơ cao phải được xác nhận bởi
          bác sĩ/dược sĩ hoặc chuyên gia có thẩm quyền theo quy định chuyên môn hiện hành.
        </p>
      </LegalSection>

      <LegalSection id="emergency" title="5. Xử lý tình huống khẩn cấp">
        <p>
          Khi xuất hiện dấu hiệu cấp cứu như khó thở nặng, đau ngực dữ dội, rối loạn ý thức, co giật, sốc phản vệ hoặc xuất huyết
          nghiêm trọng, người dùng phải liên hệ cơ sở cấp cứu ngay. Không chờ hệ thống AI đưa thêm phân tích.
        </p>
      </LegalSection>

      <LegalSection id="consent-data" title="6. Dữ liệu liên quan đến đồng thuận">
        <p>
          Hệ thống lưu trữ thông tin đồng thuận (phiên bản, thời điểm, ngữ cảnh user) để phục vụ kiểm soát truy cập, audit tuân thủ
          và điều tra sự cố khi cần thiết. Dữ liệu này được xử lý theo Chính sách quyền riêng tư của The Clara Care.
        </p>
      </LegalSection>

      <LegalSection id="withdrawal" title="7. Rút lại hoặc cập nhật đồng thuận">
        <p>
          Người dùng có thể yêu cầu cập nhật trạng thái đồng thuận qua quản trị viên hệ thống. Khi đồng thuận không còn hiệu lực,
          các tính năng nhạy cảm có thể bị khóa cho đến khi hoàn tất quy trình xác nhận lại.
        </p>
      </LegalSection>

      <LegalSection id="versioning" title="8. Version và hiệu lực áp dụng">
        <p>
          Đồng thuận y tế được version hóa để bảo đảm khả năng truy vết. Phiên bản hiện hành: <span className="font-bold">{LEGAL_POLICY_VERSION}</span>.
          Phiên bản mới sẽ có hiệu lực kể từ thời điểm công bố tại mục Thỏa thuận người dùng.
        </p>
      </LegalSection>

      <LegalSection id="support" title="9. Liên hệ hỗ trợ">
        <p>
          Nếu cần tư vấn thêm về phạm vi đồng thuận, vui lòng liên hệ{" "}
          <a className="font-bold text-[var(--text-brand)] hover:underline" href={"mailto:" + LEGAL_CONTACT_EMAIL}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
