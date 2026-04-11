import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư | The Clara Care",
  description: "Mô tả cách The Clara Care thu thập, xử lý, lưu trữ và bảo vệ dữ liệu trong toàn bộ hệ thống CLARA.",
};

const PRIVACY_SECTIONS = [
  { id: "scope", label: "Phạm vi áp dụng" },
  { id: "data-categories", label: "Loại dữ liệu thu thập" },
  { id: "module-flows", label: "Dữ liệu theo module" },
  { id: "processing-purpose", label: "Mục đích xử lý" },
  { id: "legal-basis", label: "Căn cứ xử lý dữ liệu" },
  { id: "retention", label: "Lưu trữ và xóa dữ liệu" },
  { id: "sharing", label: "Chia sẻ với bên thứ ba" },
  { id: "security", label: "Biện pháp bảo mật" },
  { id: "user-rights", label: "Quyền của người dùng" },
  { id: "contact", label: "Liên hệ và cập nhật" },
] as const;

export default function PrivacyPolicyPage() {
  return (
    <LegalPageShell
      policyKey="privacy"
      title="Chính sách quyền riêng tư"
      summary="Chính sách này mô tả cách The Clara Care quản trị dữ liệu cá nhân và dữ liệu lâm sàng tham khảo trong các module Research, Council, Self-Med, CareGuard, Scribe và Control Tower."
      updatedAt={LEGAL_UPDATED_AT}
      sections={PRIVACY_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Thu thập theo nguyên tắc tối thiểu và đúng mục đích nghiệp vụ.",
        "Consent y tế được version hóa để kiểm soát truy cập và truy vết.",
        "Cookie phiên, CSRF và audit log được dùng cho bảo mật vận hành.",
        "Không bán dữ liệu cá nhân cho bên thứ ba.",
      ]}
    >
      <LegalSection id="scope" title="1. Phạm vi áp dụng">
        <p>
          Chính sách áp dụng cho toàn bộ dịch vụ thuộc The Clara Care trên web, API và các thành phần hạ tầng hỗ trợ vận hành.
        </p>
        <p>
          Tài khoản cá nhân, tài khoản tổ chức và tài khoản quản trị đều thuộc phạm vi chính sách khi truy cập hoặc sử dụng hệ
          thống.
        </p>
      </LegalSection>

      <LegalSection id="data-categories" title="2. Loại dữ liệu được thu thập">
        <ul className="list-disc space-y-2 pl-5">
          <li>Dữ liệu tài khoản: email, họ tên, vai trò, trạng thái xác thực, trạng thái hoạt động.</li>
          <li>Dữ liệu xác thực phiên: thông tin đăng nhập, refresh session, cookie xác thực và CSRF.</li>
          <li>Dữ liệu vận hành: nhật ký truy cập, lỗi hệ thống, tín hiệu bảo mật, thông số kỹ thuật phục vụ giám sát.</li>
          <li>Dữ liệu đồng thuận: loại consent, phiên bản consent, thời điểm chấp thuận và user context liên quan.</li>
        </ul>
      </LegalSection>

      <LegalSection id="module-flows" title="3. Dữ liệu theo từng module sản phẩm">
        <ul className="list-disc space-y-2 pl-5">
          <li>Research: truy vấn, tài liệu tải lên, metadata nguồn và trích dẫn phục vụ kiểm chứng.</li>
          <li>Council: dữ liệu intake, bản phân tích hội chẩn, timeline suy luận và kết quả tổng hợp.</li>
          <li>Self-Med/CareGuard: dữ liệu tủ thuốc, OCR kê đơn, đánh giá tương tác thuốc và cảnh báo rủi ro.</li>
          <li>Scribe: transcript, bản ghi SOAP và dữ liệu chuẩn hóa ghi chú lâm sàng tham khảo.</li>
          <li>Control Tower: cấu hình hệ thống, policy guard và dữ liệu audit thao tác quản trị.</li>
        </ul>
      </LegalSection>

      <LegalSection id="processing-purpose" title="4. Mục đích xử lý dữ liệu">
        <ul className="list-disc space-y-2 pl-5">
          <li>Cung cấp chức năng cốt lõi của hệ thống theo từng module.</li>
          <li>Duy trì an toàn vận hành, chống truy cập trái phép và phản ứng sự cố.</li>
          <li>Cải thiện chất lượng truy xuất bằng chứng, cảnh báo rủi ro và trải nghiệm sử dụng.</li>
          <li>Đáp ứng yêu cầu kiểm toán nội bộ, tuân thủ pháp lý và nghĩa vụ báo cáo khi cần thiết.</li>
        </ul>
      </LegalSection>

      <LegalSection id="legal-basis" title="5. Căn cứ xử lý dữ liệu">
        <p>
          The Clara Care xử lý dữ liệu dựa trên đồng ý của người dùng, nhu cầu thực hiện dịch vụ, nghĩa vụ pháp lý hợp lệ và lợi
          ích chính đáng về bảo mật hệ thống.
        </p>
        <p>
          Với luồng y tế nhạy cảm, hệ thống có thể yêu cầu người dùng hoàn tất đồng thuận bắt buộc trước khi cho phép truy cập.
        </p>
      </LegalSection>

      <LegalSection id="retention" title="6. Chính sách lưu trữ và xóa dữ liệu">
        <p>
          Dữ liệu được lưu trong thời gian cần thiết cho mục đích vận hành và tuân thủ. Khi hết vòng đời sử dụng, dữ liệu sẽ được
          xóa, ẩn danh hoặc giới hạn truy cập theo chính sách nội bộ.
        </p>
        <p>
          Một số log bảo mật, log phiên và audit trail có thể được lưu lâu hơn dữ liệu nghiệp vụ để phục vụ điều tra sự cố và đối
          chiếu tuân thủ.
        </p>
      </LegalSection>

      <LegalSection id="sharing" title="7. Chia sẻ dữ liệu với bên thứ ba">
        <p>
          Dữ liệu chỉ được chia sẻ trong phạm vi cần thiết cho hạ tầng vận hành, xử lý kỹ thuật và tích hợp nguồn tham chiếu theo
          cấu hình hệ thống.
        </p>
        <p>
          The Clara Care không bán dữ liệu cá nhân. Trường hợp phải cung cấp dữ liệu theo yêu cầu pháp lý hợp lệ sẽ được xử lý
          theo quy trình kiểm soát nội bộ.
        </p>
      </LegalSection>

      <LegalSection id="security" title="8. Biện pháp bảo mật dữ liệu">
        <ul className="list-disc space-y-2 pl-5">
          <li>Kiểm soát truy cập theo vai trò, nguyên tắc tối thiểu quyền hạn.</li>
          <li>Áp dụng cơ chế phiên an toàn, rate-limit và các lớp bảo vệ xác thực.</li>
          <li>Ghi nhận audit log cho thao tác nhạy cảm để phục vụ truy vết và hậu kiểm.</li>
        </ul>
      </LegalSection>

      <LegalSection id="user-rights" title="9. Quyền của chủ thể dữ liệu">
        <p>
          Người dùng có thể gửi yêu cầu truy cập, điều chỉnh hoặc xóa dữ liệu cá nhân trong phạm vi pháp luật cho phép. Hệ thống có
          thể yêu cầu xác minh danh tính trước khi xử lý để đảm bảo an toàn thông tin.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="10. Liên hệ và cập nhật chính sách">
        <p>
          Mọi yêu cầu liên quan quyền riêng tư vui lòng gửi về{" "}
          <a className="font-bold text-[var(--text-brand)] hover:underline" href={`mailto:${LEGAL_CONTACT_EMAIL}`}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
        <p>
          Chính sách có thể được cập nhật khi kiến trúc hệ thống hoặc yêu cầu pháp lý thay đổi. Phiên bản mới nhất luôn được công
          bố tại Policy Hub của The Clara Care.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
