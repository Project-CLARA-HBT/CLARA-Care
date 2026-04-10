import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư | The Clara Care",
  description: "Mô tả cách The Clara Care thu thập, sử dụng, lưu trữ và bảo vệ dữ liệu người dùng.",
};

const PRIVACY_SECTIONS = [
  { id: "scope", label: "Phạm vi áp dụng" },
  { id: "data-categories", label: "Danh mục dữ liệu" },
  { id: "processing-purpose", label: "Mục đích xử lý" },
  { id: "legal-basis", label: "Căn cứ xử lý" },
  { id: "retention", label: "Lưu trữ dữ liệu" },
  { id: "sharing", label: "Chia sẻ với bên thứ ba" },
  { id: "security", label: "An toàn thông tin" },
  { id: "user-rights", label: "Quyền của người dùng" },
  { id: "cross-border", label: "Chuyển dữ liệu xuyên biên giới" },
  { id: "contact", label: "Liên hệ & cập nhật" },
] as const;

export default function PrivacyPolicyPage() {
  return (
    <LegalPageShell
      policyKey="privacy"
      title="Chính sách quyền riêng tư"
      summary="Chính sách này mô tả cách The Clara Care quản trị dữ liệu cá nhân và dữ liệu liên quan vận hành lâm sàng để đảm bảo tính minh bạch, khả kiểm và an toàn khi sử dụng hệ thống."
      updatedAt={LEGAL_UPDATED_AT}
      sections={PRIVACY_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Thu thập tối thiểu theo mục tiêu nghiệp vụ rõ ràng.",
        "Ưu tiên khử định danh ở các luồng phân tích không cần nhận diện cá nhân.",
        "Mọi truy cập nhạy cảm đều ghi nhận audit trail.",
        "Người dùng có quyền yêu cầu xem/chỉnh sửa/xóa dữ liệu theo quy định.",
      ]}
    >
      <LegalSection id="scope" title="1. Phạm vi áp dụng">
        <p>
          Chính sách áp dụng cho toàn bộ dịch vụ The Clara Care, gồm giao diện web, API và các module như Research, Council,
          Self-Med, CareGuard, Scribe, Control Tower và các thành phần tích hợp liên quan.
        </p>
        <p>
          Chính sách này được áp dụng cho cả tài khoản cá nhân, tài khoản tổ chức và tài khoản quản trị khi truy cập các tài
          nguyên thuộc hệ thống.
        </p>
      </LegalSection>

      <LegalSection id="data-categories" title="2. Danh mục dữ liệu được thu thập">
        <ul className="list-disc space-y-2 pl-5">
          <li>Dữ liệu tài khoản: họ tên, email, vai trò, trạng thái xác thực, thông tin phiên đăng nhập.</li>
          <li>Dữ liệu vận hành: log request/response, tín hiệu lỗi, timestamp, chỉ số chất lượng và hiệu năng.</li>
          <li>Dữ liệu người dùng cung cấp: truy vấn, tài liệu tải lên, thông tin thuốc, nội dung ghi chú, bản tóm tắt lâm sàng.</li>
          <li>Dữ liệu đồng thuận: phiên bản consent, thời điểm chấp thuận, user context dùng cho kiểm chứng pháp lý.</li>
        </ul>
      </LegalSection>

      <LegalSection id="processing-purpose" title="3. Mục đích xử lý dữ liệu">
        <ul className="list-disc space-y-2 pl-5">
          <li>Cung cấp chức năng cốt lõi của sản phẩm và duy trì trải nghiệm sử dụng ổn định.</li>
          <li>Nâng cao chất lượng suy luận, truy xuất bằng chứng và khả năng kiểm chứng câu trả lời.</li>
          <li>Phát hiện, điều tra, ngăn chặn hành vi bất thường hoặc truy cập trái phép.</li>
          <li>Đáp ứng nghĩa vụ tuân thủ pháp luật, yêu cầu kiểm toán và quy trình quản trị nội bộ.</li>
        </ul>
      </LegalSection>

      <LegalSection id="legal-basis" title="4. Căn cứ xử lý dữ liệu">
        <p>
          The Clara Care xử lý dữ liệu dựa trên: (i) sự đồng ý của người dùng đối với các tính năng nhạy cảm; (ii) nhu cầu thực
          hiện hợp đồng/dịch vụ; (iii) nghĩa vụ pháp lý hợp lệ; và (iv) lợi ích chính đáng về an toàn vận hành hệ thống.
        </p>
      </LegalSection>

      <LegalSection id="retention" title="5. Chính sách lưu trữ và xóa dữ liệu">
        <p>
          Dữ liệu được lưu trong thời gian cần thiết để phục vụ mục đích nêu trên, hoặc theo yêu cầu pháp lý hiện hành. Sau khi
          hết thời gian lưu trữ, dữ liệu sẽ được xóa hoặc ẩn danh hóa theo quy trình kỹ thuật.
        </p>
        <p>
          Với log vận hành và audit trail, hệ thống có thể lưu dài hơn để phục vụ điều tra sự cố, truy vết và đối chiếu tuân thủ.
        </p>
      </LegalSection>

      <LegalSection id="sharing" title="6. Chia sẻ dữ liệu với bên thứ ba">
        <p>
          Hệ thống chỉ chia sẻ dữ liệu trong phạm vi cần thiết cho vận hành, ví dụ đối tác hạ tầng, dịch vụ xử lý hỗ trợ hoặc khi
          có yêu cầu pháp lý hợp lệ từ cơ quan có thẩm quyền.
        </p>
        <p>The Clara Care không bán dữ liệu cá nhân cho bên thứ ba.</p>
      </LegalSection>

      <LegalSection id="security" title="7. Biện pháp an toàn thông tin">
        <ul className="list-disc space-y-2 pl-5">
          <li>Kiểm soát truy cập theo vai trò, nguyên tắc tối thiểu quyền hạn và phân tách môi trường vận hành.</li>
          <li>Giám sát bảo mật liên tục, cảnh báo bất thường và quy trình phản ứng sự cố theo mức độ ưu tiên.</li>
          <li>Ghi nhận nhật ký truy cập nhạy cảm để phục vụ truy vết, kiểm tra và hậu kiểm.</li>
        </ul>
      </LegalSection>

      <LegalSection id="user-rights" title="8. Quyền của chủ thể dữ liệu">
        <p>
          Người dùng có thể yêu cầu truy cập, chỉnh sửa hoặc xóa dữ liệu cá nhân trong phạm vi pháp luật cho phép. The Clara Care
          có thể cần xác minh danh tính trước khi xử lý các yêu cầu này nhằm đảm bảo an toàn thông tin.
        </p>
      </LegalSection>

      <LegalSection id="cross-border" title="9. Chuyển dữ liệu xuyên biên giới">
        <p>
          Trong trường hợp có xử lý hạ tầng đa vùng, The Clara Care áp dụng biện pháp kỹ thuật và điều khoản ràng buộc phù hợp để
          duy trì mức độ bảo vệ dữ liệu tương đương với tiêu chuẩn nội bộ.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="10. Liên hệ và cập nhật chính sách">
        <p>
          Mọi yêu cầu liên quan quyền riêng tư hoặc dữ liệu cá nhân vui lòng gửi về{" "}
          <a className="font-bold text-[var(--text-brand)] hover:underline" href={`mailto:${LEGAL_CONTACT_EMAIL}`}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
        <p>
          Chính sách có thể được cập nhật theo thay đổi pháp lý hoặc thay đổi kiến trúc hệ thống. Phiên bản mới nhất luôn được
          công bố tại Policy Center của The Clara Care.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
