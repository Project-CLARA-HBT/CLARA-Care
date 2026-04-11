import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_POLICY_VERSION, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Đồng thuận sử dụng y tế | The Clara Care",
  description: "Điều khoản đồng thuận bắt buộc trước khi dùng các tính năng có nguy cơ ảnh hưởng lâm sàng.",
};

const CONSENT_SECTIONS = [
  { id: "overview", label: "Bản chất hệ thống" },
  { id: "scope", label: "Phạm vi bắt buộc đồng thuận" },
  { id: "enforcement", label: "Cơ chế thực thi kỹ thuật" },
  { id: "user-commitment", label: "Cam kết của người dùng" },
  { id: "clinical-verification", label: "Xác nhận chuyên môn bắt buộc" },
  { id: "emergency", label: "Tình huống khẩn cấp" },
  { id: "consent-data", label: "Dữ liệu đồng thuận được lưu" },
  { id: "withdrawal", label: "Rút lại đồng thuận" },
  { id: "versioning", label: "Version và hiệu lực" },
  { id: "support", label: "Liên hệ hỗ trợ" },
] as const;

export default function MedicalConsentPage() {
  return (
    <LegalPageShell
      policyKey="consent"
      title="Đồng thuận sử dụng y tế"
      summary="Đồng thuận này nhằm bảo đảm người dùng hiểu rõ giới hạn của AI và trách nhiệm chuyên môn trước khi sử dụng các tính năng CLARA có tác động đến quyết định lâm sàng."
      updatedAt={LEGAL_UPDATED_AT}
      sections={CONSENT_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Bắt buộc trước các luồng có rủi ro lâm sàng như Self-Med và CareGuard.",
        "Consent được kiểm tra theo phiên bản bắt buộc từ backend trước khi cho phép truy cập.",
        "Mọi quyết định điều trị cần xác nhận bởi nhân sự chuyên môn có thẩm quyền.",
        `Policy Hub version: ${LEGAL_POLICY_VERSION}.`,
      ]}
    >
      <LegalSection id="overview" title="1. Bản chất của hệ thống">
        <p>
          The Clara Care là nền tảng hỗ trợ tham khảo thông tin y khoa, cảnh báo rủi ro và tổng hợp dữ liệu. Hệ thống không thay
          thế bác sĩ trong chẩn đoán hoặc chỉ định điều trị.
        </p>
      </LegalSection>

      <LegalSection id="scope" title="2. Phạm vi bắt buộc đồng thuận">
        <p>
          Đồng thuận này áp dụng cho các tính năng có khả năng ảnh hưởng trực tiếp đến đánh giá an toàn dùng thuốc, cảnh báo tương
          tác hoặc gợi ý xử trí lâm sàng.
        </p>
      </LegalSection>

      <LegalSection id="enforcement" title="3. Cơ chế thực thi kỹ thuật">
        <p>
          Hệ thống sử dụng cơ chế kiểm tra trạng thái đồng thuận theo người dùng và phiên bản bắt buộc trước khi mở các endpoint
          nhạy cảm. Nếu chưa đạt điều kiện, truy cập sẽ bị chặn cho đến khi hoàn tất xác nhận.
        </p>
      </LegalSection>

      <LegalSection id="user-commitment" title="4. Cam kết của người dùng khi đồng thuận">
        <ul className="list-disc space-y-2 pl-5">
          <li>Không dùng kết quả AI để tự chẩn đoán hoặc tự điều trị khi không có chuyên môn phù hợp.</li>
          <li>Đối chiếu kết quả với tài liệu chuyên môn chính thống và dữ liệu lâm sàng thực tế.</li>
          <li>Không cố ý nhập dữ liệu sai lệch hoặc bỏ qua cảnh báo an toàn đã được hệ thống nêu rõ.</li>
        </ul>
      </LegalSection>

      <LegalSection id="clinical-verification" title="5. Yêu cầu xác nhận chuyên môn bắt buộc">
        <p>
          Mọi quyết định liên quan đơn thuốc, liều dùng, thay đổi phác đồ hoặc xử trí nguy cơ cao phải được xác nhận bởi bác sĩ,
          dược sĩ hoặc chuyên gia có thẩm quyền theo quy định hiện hành.
        </p>
      </LegalSection>

      <LegalSection id="emergency" title="6. Xử lý tình huống khẩn cấp">
        <p>
          Khi có dấu hiệu cấp cứu (khó thở nặng, đau ngực dữ dội, rối loạn ý thức, co giật, sốc phản vệ, xuất huyết nặng), người
          dùng phải liên hệ cơ sở cấp cứu ngay. Không trì hoãn xử trí để chờ thêm phản hồi AI.
        </p>
      </LegalSection>

      <LegalSection id="consent-data" title="7. Dữ liệu đồng thuận được lưu trữ">
        <p>
          Hệ thống ghi nhận loại consent, phiên bản đã chấp thuận, thời điểm chấp thuận và user context để phục vụ kiểm soát truy
          cập, audit tuân thủ và điều tra sự cố khi cần.
        </p>
      </LegalSection>

      <LegalSection id="withdrawal" title="8. Rút lại hoặc cập nhật đồng thuận">
        <p>
          Người dùng có thể đề nghị cập nhật trạng thái đồng thuận qua kênh hỗ trợ. Khi trạng thái đồng thuận không còn hợp lệ, hệ
          thống có thể khóa các luồng nhạy cảm cho đến khi hoàn tất xác nhận lại theo phiên bản hiện hành.
        </p>
      </LegalSection>

      <LegalSection id="versioning" title="9. Version và hiệu lực áp dụng">
        <p>
          Đồng thuận y tế được version hóa để bảo đảm truy vết. Phiên bản bắt buộc được xác định bởi cấu hình runtime của hệ thống;
          phiên bản policy center hiện tại là <span className="font-bold">{LEGAL_POLICY_VERSION}</span>.
        </p>
      </LegalSection>

      <LegalSection id="support" title="10. Liên hệ hỗ trợ">
        <p>
          Nếu cần làm rõ phạm vi đồng thuận, vui lòng liên hệ{" "}
          <a className="font-bold text-[var(--text-brand)] hover:underline" href={"mailto:" + LEGAL_CONTACT_EMAIL}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
