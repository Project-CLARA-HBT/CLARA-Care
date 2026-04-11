import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
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
  title: "Điều khoản sử dụng | The Clara Care",
  description: "Điều khoản sử dụng áp dụng cho toàn bộ hệ thống The Clara Care và các module CLARA.",
};

const SECTIONS = [
  { id: "acceptance", label: "Chấp thuận điều khoản" },
  { id: "accounts", label: "Tài khoản và điều kiện truy cập" },
  { id: "scope", label: "Phạm vi sử dụng dịch vụ" },
  { id: "prohibited", label: "Hành vi bị cấm" },
  { id: "ai-limits", label: "Giới hạn của AI" },
  { id: "data-obligations", label: "Trách nhiệm dữ liệu người dùng" },
  { id: "service-operation", label: "Vận hành và tính sẵn sàng" },
  { id: "enforcement", label: "Tạm ngưng và chấm dứt" },
  { id: "liability", label: "Giới hạn trách nhiệm" },
  { id: "changes", label: "Cập nhật điều khoản và luật áp dụng" },
  { id: "entity-info", label: "Thông tin chủ thể vận hành" },
] as const;

export default function TermsOfServicePage() {
  return (
    <LegalPageShell
      policyKey="terms"
      title="Điều khoản sử dụng The Clara Care"
      summary="Điều khoản này điều chỉnh việc truy cập và sử dụng toàn bộ nền tảng CLARA, bao gồm Research, Council, Self-Med, CareGuard, Scribe và Control Tower."
      updatedAt={LEGAL_UPDATED_AT}
      sections={SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        `Domain chính thức: ${LEGAL_PRIMARY_DOMAIN}`,
        `Chủ thể vận hành: ${LEGAL_OPERATOR_NAME}`,
        `Phiên bản điều khoản: ${LEGAL_POLICY_VERSION}`,
        "Tài khoản production cần xác nhận đầy đủ Terms, Privacy và Medical Consent khi đăng ký.",
      ]}
    >
      <LegalSection id="acceptance" title="1. Chấp thuận điều khoản">
        <p>
          Khi truy cập hoặc tiếp tục sử dụng dịch vụ The Clara Care, bạn xác nhận đã đọc, hiểu và đồng ý tuân thủ Điều khoản sử
          dụng cùng các chính sách liên quan tại Policy Hub.
        </p>
      </LegalSection>

      <LegalSection id="accounts" title="2. Tài khoản và điều kiện truy cập">
        <ul className="list-disc space-y-2 pl-5">
          <li>Bạn chịu trách nhiệm về tính chính xác của thông tin đăng ký và bảo mật thông tin đăng nhập.</li>
          <li>Không được chia sẻ tài khoản hoặc cho phép truy cập trái phép dưới danh nghĩa của bạn.</li>
          <li>
            Ở môi trường production, đăng ký tài khoản yêu cầu xác nhận đầy đủ Điều khoản sử dụng, Chính sách quyền riêng tư và
            Đồng thuận y tế theo cấu hình hệ thống.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="scope" title="3. Phạm vi sử dụng dịch vụ">
        <p>
          The Clara Care cung cấp nền tảng AI hỗ trợ thông tin y khoa tham khảo, quản trị tri thức và hỗ trợ quy trình lâm sàng.
          Dịch vụ bao gồm giao diện web, API và các module công bố chính thức trên domain của hệ thống.
        </p>
      </LegalSection>

      <LegalSection id="prohibited" title="4. Hành vi bị cấm">
        <ul className="list-disc space-y-2 pl-5">
          <li>Sử dụng hệ thống cho hoạt động vi phạm pháp luật hoặc vượt ranh giới đạo đức nghề nghiệp.</li>
          <li>Cố ý nhập dữ liệu sai lệch nhằm tạo khuyến nghị nguy hiểm hoặc gây hiểu nhầm lâm sàng.</li>
          <li>Can thiệp trái phép vào hạ tầng, token phiên, cơ chế xác thực, hoặc luồng kiểm soát bảo mật.</li>
          <li>Tải lên mã độc, dữ liệu bất hợp pháp hoặc nội dung xâm phạm quyền hợp pháp của bên thứ ba.</li>
        </ul>
      </LegalSection>

      <LegalSection id="ai-limits" title="5. Giới hạn của AI và trách nhiệm chuyên môn">
        <p>
          Kết quả do CLARA sinh ra chỉ mang tính hỗ trợ tham khảo. Hệ thống không thay thế bác sĩ, dược sĩ hoặc chuyên gia có thẩm
          quyền trong chẩn đoán, kê đơn và quyết định điều trị.
        </p>
        <p>
          Mọi hành động có ảnh hưởng lâm sàng phải được xác nhận độc lập bởi nhân sự chuyên môn phù hợp trước khi áp dụng.
        </p>
      </LegalSection>

      <LegalSection id="data-obligations" title="6. Trách nhiệm dữ liệu của người dùng">
        <ul className="list-disc space-y-2 pl-5">
          <li>Bạn chịu trách nhiệm đối với dữ liệu nhập vào, dữ liệu tải lên và các quyết định dựa trên dữ liệu đó.</li>
          <li>Bạn cần đảm bảo có quyền hợp pháp khi đưa dữ liệu của bên thứ ba vào hệ thống.</li>
          <li>Dữ liệu nhạy cảm cần được quản trị theo quy trình nội bộ của tổ chức sử dụng dịch vụ.</li>
        </ul>
      </LegalSection>

      <LegalSection id="service-operation" title="7. Vận hành dịch vụ và tính sẵn sàng">
        <p>
          The Clara Care vận hành theo nguyên tắc an toàn và có thể thay đổi cấu hình kỹ thuật, bảo trì hoặc giới hạn truy cập tạm
          thời để bảo vệ hệ thống.
        </p>
        <p>
          Chúng tôi không cam kết dịch vụ không gián đoạn tuyệt đối trong mọi thời điểm hoặc mọi điều kiện mạng.
        </p>
      </LegalSection>

      <LegalSection id="enforcement" title="8. Tạm ngưng, chấm dứt và thực thi chính sách">
        <p>
          The Clara Care có quyền tạm ngưng hoặc chấm dứt quyền truy cập khi phát hiện vi phạm điều khoản, nguy cơ bảo mật, hoặc
          theo yêu cầu từ cơ quan có thẩm quyền.
        </p>
      </LegalSection>

      <LegalSection id="liability" title="9. Giới hạn trách nhiệm">
        <p>
          Trong phạm vi pháp luật cho phép, The Clara Care không chịu trách nhiệm cho thiệt hại gián tiếp, tổn thất phát sinh từ
          việc sử dụng sai mục đích, cấu hình sai, hoặc không tuân thủ yêu cầu xác nhận chuyên môn.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="10. Cập nhật điều khoản và luật áp dụng">
        <p>
          Điều khoản có thể được cập nhật để phù hợp với thay đổi sản phẩm, kiến trúc hệ thống hoặc yêu cầu pháp lý. Phiên bản mới
          có hiệu lực từ thời điểm công bố tại Policy Hub.
        </p>
        <p>
          Tranh chấp phát sinh sẽ ưu tiên giải quyết bằng thương lượng; nếu không đạt kết quả, tranh chấp được xử lý theo pháp luật
          Việt Nam.
        </p>
      </LegalSection>

      <LegalSection id="entity-info" title="11. Thông tin chủ thể vận hành">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-bold">Tên chủ thể:</span> {LEGAL_OPERATOR_NAME}
          </li>
          <li>
            <span className="font-bold">Domain chính thức:</span> https://{LEGAL_PRIMARY_DOMAIN}
          </li>
          <li>
            <span className="font-bold">Số điện thoại liên lạc:</span> {LEGAL_CONTACT_PHONE}
          </li>
          <li>
            <span className="font-bold">Email hỗ trợ:</span>{" "}
            <a className="font-bold text-[var(--text-brand)] hover:underline" href={"mailto:" + LEGAL_CONTACT_EMAIL}>
              {LEGAL_CONTACT_EMAIL}
            </a>
          </li>
          <li>
            <span className="font-bold">Phiên bản chính sách:</span> {LEGAL_POLICY_VERSION}
          </li>
        </ul>
      </LegalSection>
    </LegalPageShell>
  );
}
