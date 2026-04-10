import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Điều khoản sử dụng | The Clara Care",
  description: "Điều khoản sử dụng The Clara Care: quyền, trách nhiệm, giới hạn dịch vụ và điều kiện truy cập.",
};

const TERMS_SECTIONS = [
  { id: "acceptance", label: "Chấp thuận điều khoản" },
  { id: "account", label: "Tài khoản và bảo mật" },
  { id: "allowed-use", label: "Phạm vi sử dụng" },
  { id: "forbidden-use", label: "Hành vi bị cấm" },
  { id: "medical-disclaimer", label: "Miễn trừ y tế" },
  { id: "availability", label: "Khả dụng dịch vụ" },
  { id: "intellectual-property", label: "Sở hữu trí tuệ" },
  { id: "termination", label: "Tạm ngưng/chấm dứt" },
  { id: "liability", label: "Giới hạn trách nhiệm" },
  { id: "governing-law", label: "Luật áp dụng" },
] as const;

export default function TermsOfServicePage() {
  return (
    <LegalPageShell
      policyKey="terms"
      title="Điều khoản sử dụng (Terms of Service)"
      summary="Điều khoản này xác lập nguyên tắc sử dụng dịch vụ The Clara Care, phân định rõ trách nhiệm người dùng và giới hạn trách nhiệm của hệ thống trong bối cảnh hỗ trợ lâm sàng."
      updatedAt={LEGAL_UPDATED_AT}
      sections={TERMS_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "CLARA là công cụ hỗ trợ, không thay thế quyết định chuyên môn y tế.",
        "Người dùng chịu trách nhiệm kiểm chứng trước khi áp dụng lâm sàng.",
        "Tài khoản có thể bị khóa khi vi phạm bảo mật hoặc chính sách sử dụng.",
        "Điều khoản cập nhật có hiệu lực từ thời điểm công bố tại Policy Center.",
      ]}
    >
      <LegalSection id="acceptance" title="1. Chấp thuận điều khoản">
        <p>
          Khi tạo tài khoản, truy cập API hoặc tiếp tục sử dụng dịch vụ, bạn xác nhận đã đọc và đồng ý với Điều khoản sử dụng,
          Chính sách quyền riêng tư, Chính sách cookie và Đồng thuận y tế của The Clara Care.
        </p>
      </LegalSection>

      <LegalSection id="account" title="2. Tài khoản và bảo mật truy cập">
        <ul className="list-disc space-y-2 pl-5">
          <li>Người dùng phải cung cấp thông tin chính xác, cập nhật và không mạo danh.</li>
          <li>Thông tin đăng nhập phải được bảo mật; mọi hoạt động trên tài khoản thuộc trách nhiệm chủ tài khoản.</li>
          <li>Khi nghi ngờ lộ thông tin, người dùng cần đổi mật khẩu và báo quản trị trong thời gian sớm nhất.</li>
        </ul>
      </LegalSection>

      <LegalSection id="allowed-use" title="3. Phạm vi sử dụng được phép">
        <p>
          Dịch vụ được cung cấp nhằm hỗ trợ tra cứu bằng chứng, tổng hợp thông tin y khoa và quản trị quy trình làm việc. Việc sử
          dụng phải tuân thủ pháp luật hiện hành, quy tắc chuyên môn và chính sách nội bộ của đơn vị triển khai.
        </p>
      </LegalSection>

      <LegalSection id="forbidden-use" title="4. Hành vi bị cấm">
        <ul className="list-disc space-y-2 pl-5">
          <li>Cố ý khai thác lỗ hổng, phá hoại hệ thống, thu thập trái phép dữ liệu người dùng khác.</li>
          <li>Tái phân phối nội dung có bản quyền hoặc dữ liệu hạn chế khi chưa được phép.</li>
          <li>Dùng hệ thống để tạo nội dung trái pháp luật, gian lận chuyên môn hoặc gây hại cho người bệnh.</li>
        </ul>
      </LegalSection>

      <LegalSection id="medical-disclaimer" title="5. Miễn trừ trách nhiệm y tế">
        <p>
          The Clara Care không thay thế bác sĩ trong chẩn đoán, kê đơn, chỉ định điều trị hoặc xử trí cấp cứu. Mọi khuyến nghị do
          hệ thống cung cấp cần được kiểm tra độc lập bởi người có chuyên môn trước khi áp dụng.
        </p>
      </LegalSection>

      <LegalSection id="availability" title="6. Tính khả dụng và thay đổi dịch vụ">
        <p>
          The Clara Care nỗ lực duy trì dịch vụ liên tục nhưng không bảo đảm hoạt động không gián đoạn tuyệt đối. Hệ thống có thể
          tạm dừng để bảo trì, nâng cấp hoặc xử lý sự cố mà không cần thông báo trước trong tình huống khẩn cấp.
        </p>
      </LegalSection>

      <LegalSection id="intellectual-property" title="7. Quyền sở hữu trí tuệ">
        <p>
          Mã nguồn, kiến trúc, giao diện, tài liệu vận hành và nhãn hiệu thuộc quyền sở hữu của The Clara Care hoặc đối tác cấp
          phép. Mọi hành vi sao chép, sửa đổi, phân phối cho mục đích thương mại khi chưa được chấp thuận đều bị cấm.
        </p>
      </LegalSection>

      <LegalSection id="termination" title="8. Tạm ngưng hoặc chấm dứt truy cập">
        <p>
          Hệ thống có quyền tạm ngưng hoặc chấm dứt tài khoản khi phát hiện vi phạm nghiêm trọng về bảo mật, pháp lý hoặc đạo đức
          sử dụng. Sau khi chấm dứt, một số dữ liệu vẫn có thể được lưu giữ theo nghĩa vụ tuân thủ.
        </p>
      </LegalSection>

      <LegalSection id="liability" title="9. Giới hạn trách nhiệm">
        <p>
          Trong phạm vi pháp luật cho phép, The Clara Care không chịu trách nhiệm đối với thiệt hại gián tiếp phát sinh từ việc sử
          dụng thông tin tham khảo nếu bỏ qua bước xác nhận chuyên môn bắt buộc trước quyết định điều trị.
        </p>
      </LegalSection>

      <LegalSection id="governing-law" title="10. Luật áp dụng và liên hệ">
        <p>
          Điều khoản này được giải thích theo pháp luật hiện hành tại Việt Nam và quy định liên quan đến dữ liệu, an toàn thông tin
          và hoạt động y tế số.
        </p>
        <p>
          Cần làm rõ điều khoản, vui lòng liên hệ{" "}
          <a className="font-bold text-[var(--text-brand)] hover:underline" href={"mailto:" + LEGAL_CONTACT_EMAIL}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
