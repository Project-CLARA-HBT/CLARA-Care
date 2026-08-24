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
  title: "Điều khoản sử dụng & Thỏa thuận người dùng | The Clara Care",
  description:
    "Thỏa thuận người dùng quy định quyền, nghĩa vụ, ranh giới y tế theo Luật Khám bệnh 2023, bảo vệ dữ liệu theo Nghị định 13/2023/NĐ-CP và minh bạch AI theo Luật 134/2025.",
};

const TERMS_SECTIONS: LegalSectionMeta[] = [
  { id: "preamble", title: "Lời mở đầu & Thỏa thuận ràng buộc" },
  { id: "legal-basis", title: "Căn cứ pháp lý áp dụng" },
  { id: "definitions", title: "Điều 1: Giải thích từ ngữ" },
  { id: "prohibited", title: "Điều 2: Các hành vi bị nghiêm cấm" },
  { id: "customer-rights", title: "Điều 3: Quyền & nghĩa vụ người dùng" },
  { id: "provider-rights", title: "Điều 4: Quyền & trách nhiệm nhà cung cấp" },
  { id: "medical-boundary", title: "Điều 5: Ranh giới y tế & Giới hạn lâm sàng" },
  { id: "privacy-zero-cot", title: "Điều 6: Bảo mật, Zero-PII & Chuẩn Zero-CoT" },
  { id: "ai-transparency", title: "Điều 7: Minh bạch AI & Giám sát con người" },
  { id: "payment-terms", title: "Điều 8: Quy định thanh toán & Dịch vụ" },
  { id: "renewal-suspension", title: "Điều 9: Gia hạn & Tạm ngưng dịch vụ" },
  { id: "user-data-dsar", title: "Điều 10: Quản lý dữ liệu & Quyền DSAR" },
  { id: "support-channel", title: "Điều 11: Hỗ trợ khách hàng & Kênh DPO" },
  { id: "liability-disclaimer", title: "Điều 12: Giới hạn trách nhiệm & Bất khả kháng" },
  { id: "refund-reservation", title: "Điều 13: Chính sách hoàn tiền & Bảo lưu" },
  { id: "final-provisions", title: "Điều 14: Điều khoản thi hành & Tranh chấp" },
  { id: "entity-info", title: "Thông tin chủ thể vận hành hợp pháp" },
];

export default function TermsOfServicePage() {
  return (
    <LegalPageShell
      policyKey="terms"
      title="Điều khoản sử dụng & Thỏa thuận người dùng"
      summary="Văn bản này quy định quyền, nghĩa vụ và phạm vi sử dụng dịch vụ The Clara Care cho người dùng cá nhân, tổ chức và chuyên gia y tế, xác lập ranh giới trách nhiệm lâm sàng theo Luật Khám bệnh 2023, bảo vệ dữ liệu theo Nghị định 13/2023/NĐ-CP và minh bạch hệ thống AI theo Luật 134/2025/QH15."
      updatedAt={LEGAL_UPDATED_AT}
      version={LEGAL_POLICY_VERSION}
      sections={TERMS_SECTIONS}
      highlights={[
        "Xác lập rõ ranh giới hỗ trợ thông tin y tế, không thay thế bác sĩ theo Luật Khám bệnh 2023.",
        "Bảo vệ dữ liệu cá nhân nhạy cảm và bảo đảm quyền DSAR theo Nghị định 13/2023/NĐ-CP.",
        "Cam kết chuẩn Zero-CoT và Zero-PII Telemetry trong toàn bộ hệ thống.",
        "Minh bạch phân loại AI rủi ro cao và duy trì sự giám sát của con người theo Luật 134/2025.",
      ]}
      relatedControls={[
        {
          href: "/legal/privacy",
          label: "Chính sách quyền riêng tư",
          description: "Bảo vệ dữ liệu cá nhân, PHR & DSAR",
        },
        {
          href: "/legal/consent",
          label: "Đồng thuận y tế",
          description: "Điều khoản bắt buộc trước can thiệp lâm sàng",
        },
        {
          href: "/legal",
          label: "Trung tâm pháp lý",
          description: "Danh mục văn bản chính thức của hệ thống",
        },
      ]}
    >
      {/* Lời mở đầu */}
      <LegalSection id="preamble" title="Lời mở đầu & Thỏa thuận ràng buộc" badge="Hiệu lực">
        <p>
          Chào mừng bạn đến với <strong>The Clara Care</strong>. Thỏa thuận người dùng này (gọi tắt là
          “Điều khoản”) là văn bản pháp lý ràng buộc giữa bạn (người dùng cá nhân, đại diện hộ gia đình,
          chuyên gia y tế hoặc tổ chức) và đơn vị vận hành hợp pháp của The Clara Care.
        </p>
        <p>
          Việc bạn tạo tài khoản, đăng nhập, truy cập hoặc sử dụng bất kỳ tính năng, công cụ, API hay
          dịch vụ nào thuộc hệ sinh thái The Clara Care đồng nghĩa với việc bạn đã đọc kỹ, hiểu rõ và
          cam kết tuân thủ toàn bộ nội dung trong Điều khoản này cùng Chính sách quyền riêng tư và Điều
          khoản đồng thuận y tế có liên quan.
        </p>
      </LegalSection>

      {/* Căn cứ pháp lý */}
      <LegalSection id="legal-basis" title="Căn cứ pháp lý áp dụng" badge="Luật áp dụng">
        <p>
          Thỏa thuận này được thiết lập và điều chỉnh bởi hệ thống văn bản quy phạm pháp luật của nước
          Cộng hòa Xã hội Chủ nghĩa Việt Nam, bao gồm:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Luật Khám bệnh, chữa bệnh số 15/2023/QH15:</strong> Quy định về hành nghề y tế, điều
            kiện chuyên môn và trách nhiệm pháp lý trong hoạt động chăm sóc sức khỏe.
          </li>
          <li>
            <strong>Nghị định số 13/2023/NĐ-CP:</strong> Về bảo vệ dữ liệu cá nhân, xử lý dữ liệu cá nhân
            nhạy cảm và thực thi các quyền của chủ thể dữ liệu (PDPD).
          </li>
          <li>
            <strong>Luật Trí tuệ nhân tạo số 134/2025/QH15:</strong> Quy định về tiêu chuẩn an toàn, phân
            loại hệ thống AI rủi ro cao trong y tế và trách nhiệm minh bạch thuật toán.
          </li>
          <li>
            <strong>Luật Giao dịch điện tử 2023, Luật An toàn thông tin mạng 2015</strong> và
            <strong> Luật An ninh mạng 2018:</strong> Về giao kết hợp đồng điện tử và an ninh dữ liệu.
          </li>
          <li>
            <strong>Bộ luật Dân sự năm 2015:</strong> Về quyền và nghĩa vụ dân sự của các bên tham gia giao dịch.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 1: Giải thích từ ngữ */}
      <LegalSection id="definitions" title="Điều 1: Giải thích từ ngữ">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>The Clara Care / Chúng tôi:</strong> Nền tảng trợ lý AI y tế thông minh và quản trị
            hồ sơ sức khỏe cá nhân do chủ thể vận hành hợp pháp quản lý.
          </li>
          <li>
            <strong>Người dùng / Khách hàng / Bạn:</strong> Bất kỳ cá nhân hoặc tổ chức nào truy cập, sử
            dụng giao diện web, ứng dụng hoặc API của The Clara Care.
          </li>
          <li>
            <strong>Hồ sơ sức khỏe cá nhân (PHR):</strong> Tập hợp các dữ liệu y tế do người dùng cung cấp
            hoặc hệ thống số hóa (sinh hiệu, đơn thuốc, lịch sử dị ứng, tiền sử bệnh).
          </li>
          <li>
            <strong>Dịch vụ AI / Tác tử y khoa:</strong> Các chức năng tra cứu y văn, đối chiếu tương tác
            thuốc (DDI), phát hiện rủi ro (CareGuard), hội chẩn đa góc nhìn (Council) và bóc tách ghi chú
            lâm sàng (Scribe).
          </li>
          <li>
            <strong>Chuẩn Zero-CoT:</strong> Nguyên tắc kỹ thuật tuyệt đối không lưu trữ chuỗi suy luận logic
            trung gian (Chain-of-Thought) vào cơ sở dữ liệu dài hạn.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 2: Hành vi bị cấm */}
      <LegalSection id="prohibited" title="Điều 2: Các hành vi bị nghiêm cấm">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Sử dụng kết quả AI của hệ thống để mạo danh bác sĩ, tự ý cấp đơn thuốc hoặc thực hiện hành vi
            hành nghề y tế trái quy định của Luật Khám bệnh, chữa bệnh 2023.
          </li>
          <li>
            Cố ý nhập dữ liệu bệnh sử, đơn thuốc hoặc thông tin sức khỏe giả mạo nhằm mục đích phá hoại,
            lừa đảo hoặc trục lợi bảo hiểm y tế.
          </li>
          <li>
            Tấn công mạng, phát tán mã độc, đảo ngược mã nguồn (reverse engineering), can thiệp trái phép
            vào kiến trúc API hoặc bypass các hàng rào an toàn (guardrails).
          </li>
          <li>
            Khai thác tài nguyên vượt định mức cho phép hoặc cố tình gây suy giảm dịch vụ của người dùng khác.
          </li>
          <li>
            Lạm dụng hệ thống để phát tán thông tin y tế sai lệch, nội dung vi phạm pháp luật hoặc vi phạm
            quyền riêng tư của bên thứ ba.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 3: Quyền và nghĩa vụ người dùng */}
      <LegalSection id="customer-rights" title="Điều 3: Quyền và nghĩa vụ của người sử dụng">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Quyền tự quyết dữ liệu:</strong> Bạn toàn quyền sở hữu, trích xuất (Data Portability),
            chỉnh sửa hoặc yêu cầu xóa dữ liệu hồ sơ sức khỏe cá nhân (PHR) bất kỳ lúc nào.
          </li>
          <li>
            <strong>Trách nhiệm bảo mật tài khoản:</strong> Bạn có trách nhiệm bảo vệ mật khẩu, mã xác thực
            và chịu trách nhiệm pháp lý đối với mọi thao tác được thực hiện từ tài khoản của mình.
          </li>
          <li>
            <strong>Tính chính xác của thông tin:</strong> Bạn cam kết cung cấp thông tin trung thực về tiền
            sử bệnh, thuốc đang sử dụng và triệu chứng để hệ thống đưa ra các cảnh báo an toàn tối ưu.
          </li>
          <li>
            <strong>Chủ động đối chiếu y khoa:</strong> Luôn tham vấn ý kiến của bác sĩ hoặc dược sĩ chuyên
            khoa trước khi đưa ra bất kỳ quyết định điều trị hoặc thay đổi liều lượng thuốc nào.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 4: Quyền và trách nhiệm nhà cung cấp */}
      <LegalSection id="provider-rights" title="Điều 4: Quyền và trách nhiệm của nhà cung cấp">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Đảm bảo tính sẵn sàng, bảo mật và độ ổn định của hệ thống theo đúng cam kết chất lượng.
          </li>
          <li>
            Cập nhật thường xuyên cơ sở tri thức y văn (Living Evidence, Dược thư quốc gia) từ các nguồn chính thống.
          </li>
          <li>
            Có quyền tạm ngưng hoặc khóa quyền truy cập của các tài khoản có hành vi vi phạm nghiêm trọng
            Điều khoản sử dụng hoặc có dấu hiệu tấn công an ninh mạng.
          </li>
          <li>
            Tiếp nhận và giải quyết khiếu nại của khách hàng theo đúng quy trình và thời hạn luật định.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 5: Ranh giới y tế & Giới hạn lâm sàng */}
      <LegalSection
        id="medical-boundary"
        title="Điều 5: Ranh giới y tế & Giới hạn trách nhiệm lâm sàng"
        badge="Luật Khám bệnh 2023"
      >
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)]/70 bg-[var(--status-warn-bg)]/25 p-5 space-y-3">
          <div className="flex items-center gap-2 text-[var(--status-warn-text)]">
            <span className="font-bold text-sm">TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM LÂM SÀNG QUAN TRỌNG:</span>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-primary)]">
            The Clara Care là nền tảng công nghệ thông tin hỗ trợ tổng hợp thông tin y khoa và tham vấn.
            <strong> The Clara Care KHÔNG PHẢI là cơ sở khám bệnh, chữa bệnh</strong> và <strong>KHÔNG thay
            thế bác sĩ</strong> theo quy định của Luật Khám bệnh, chữa bệnh số 15/2023/QH15.
          </p>
        </div>

        <ul className="list-disc space-y-2 pl-5 pt-2 text-xs sm:text-sm">
          <li>
            <strong>Không chẩn đoán xác định:</strong> Mọi thông tin phân tích triệu chứng chỉ mang tính chất
            định hướng tham khảo, không cấu thành chẩn đoán bệnh chính thức.
          </li>
          <li>
            <strong>Không kê đơn thuốc tự động:</strong> Hệ thống không kê đơn thuốc mới; các cảnh báo tương
            tác thuốc và liều dùng chỉ nhằm hỗ trợ người dùng nhận diện rủi ro để trao đổi lại với bác sĩ.
          </li>
          <li>
            <strong>Bắt buộc xác nhận chuyên môn:</strong> Mọi quyết định can thiệp điều trị, dùng thuốc hay
            thay đổi lối sống trị liệu bắt buộc phải do nhân sự y tế có chứng chỉ hành nghề hợp pháp xác nhận.
          </li>
          <li>
            <strong>Tình huống khẩn cấp:</strong> Khi xuất hiện các dấu hiệu đe dọa tính mạng (đau ngực dữ
            dội, khó thở cấp, đột quỵ, sốc phản vệ), người dùng phải kích hoạt cấp cứu 115 hoặc đến ngay bệnh
            viện gần nhất; tuyệt đối không chờ đợi phản hồi từ hệ thống AI.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 6: Cam kết bảo mật, Zero-PII & Zero-CoT */}
      <LegalSection
        id="privacy-zero-cot"
        title="Điều 6: Bảo mật thông tin, Zero-PII & Chuẩn Zero-CoT"
        badge="Nghị định 13/2023"
      >
        <p>
          The Clara Care thiết lập hàng rào bảo vệ dữ liệu bất biến theo Nghị định 13/2023/NĐ-CP:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Bảo đảm Zero-CoT:</strong> Chuỗi suy luận logic nội bộ của các tác tử AI được hủy ngay
            sau khi tạo câu trả lời tổng hợp an toàn; không lưu trữ vĩnh viễn và không xuất ra API.
          </li>
          <li>
            <strong>Zero-PII Telemetry:</strong> Toàn bộ log lỗi và số liệu giám sát vận hành được loại bỏ
            100% dữ liệu định danh cá nhân (không chứa tên, email, toa thuốc hay triệu chứng gốc).
          </li>
          <li>
            <strong>Không thương mại hóa dữ liệu:</strong> Tuyệt đối không kinh doanh, mua bán hoặc chia sẻ
            dữ liệu y tế của người dùng cho bên thứ ba vì mục đích thương mại.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 7: Minh bạch AI & Giám sát con người */}
      <LegalSection
        id="ai-transparency"
        title="Điều 7: Minh bạch hệ thống AI & Giám sát con người"
        badge="Luật AI 134/2025"
      >
        <p>
          Căn cứ Luật Trí tuệ nhân tạo số 134/2025/QH15, The Clara Care thực thi các nguyên tắc minh bạch:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Hệ thống được xếp hạng là <strong>AI rủi ro cao trong y tế</strong> và luôn duy trì quyền kiểm
            soát, giám sát và can thiệp của con người (Human Oversight).
          </li>
          <li>
            Mỗi kết quả tham vấn đều công khai họ mô hình suy luận và hiển thị đầy đủ tài liệu nguồn tham
            chiếu.
          </li>
          <li>
            Khi hệ thống hoạt động ở chế độ dự phòng nội bộ (Degraded mode), trạng thái suy giảm sẽ được gắn
            nhãn trực quan và rõ ràng trên giao diện người dùng.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 8: Thanh toán & Dịch vụ */}
      <LegalSection id="payment-terms" title="Điều 8: Quy định về dịch vụ, thanh toán & Gói tính năng">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Biểu phí dịch vụ (nếu có) được niêm yết công khai trên website theo từng gói tính năng và chu kỳ.
          </li>
          <li>
            Hóa đơn điện tử hợp pháp được xuất theo quy định của pháp luật thuế Việt Nam khi giao dịch hoàn tất.
          </li>
          <li>
            Các tính năng an toàn cơ bản và tra cứu thông tin y tế thiết yếu luôn được duy trì phục vụ cộng đồng.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 9: Gia hạn & Tạm ngưng dịch vụ */}
      <LegalSection id="renewal-suspension" title="Điều 9: Gia hạn, tạm ngưng và chấm dứt dịch vụ">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Dịch vụ có thể tạm ngưng trong các khung giờ bảo trì định kỳ có thông báo trước hoặc khi có sự
            cố mạng diện rộng.
          </li>
          <li>
            Người dùng có quyền chấm dứt tài khoản bất kỳ lúc nào; dữ liệu sẽ được xử lý theo quy định xóa
            an toàn tại Chính sách quyền riêng tư.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 10: Quản lý dữ liệu & Quyền DSAR */}
      <LegalSection id="user-data-dsar" title="Điều 10: Điều chỉnh thông tin & Quyền DSAR">
        <p>
          Bạn có quyền gửi yêu cầu tra cứu, chỉnh sửa, trích xuất dữ liệu hoặc xóa tài khoản theo Nghị định
          13/2023/NĐ-CP qua trang quản lý tài khoản hoặc liên hệ trực tiếp với Cán bộ bảo vệ dữ liệu (DPO).
          Mọi yêu cầu hợp lệ được xử lý trong thời hạn 72 giờ làm việc.
        </p>
      </LegalSection>

      {/* Điều 11: Hỗ trợ khách hàng */}
      <LegalSection id="support-channel" title="Điều 11: Hỗ trợ khách hàng & Kênh tiếp nhận DPO">
        <p>
          Kênh hỗ trợ chính thức: Email{" "}
          <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
            {LEGAL_CONTACT_EMAIL}
          </a>{" "}
          và Hotline{" "}
          <a href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`} className="font-bold text-[var(--text-primary)] hover:underline">
            {LEGAL_CONTACT_PHONE}
          </a>
          . Chúng tôi tiếp nhận phản ánh kỹ thuật 24/7 và giải quyết khiếu nại trong giờ hành chính.
        </p>
      </LegalSection>

      {/* Điều 12: Giới hạn trách nhiệm & Bất khả kháng */}
      <LegalSection id="liability-disclaimer" title="Điều 12: Giới hạn trách nhiệm & Sự kiện bất khả kháng">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            The Clara Care không chịu trách nhiệm đối với các thiệt hại phát sinh do người dùng tự ý sử dụng
            thông tin AI để tự điều trị trái với chỉ định của bác sĩ.
          </li>
          <li>
            Miễn trừ trách nhiệm trong các trường hợp bất khả kháng theo Bộ luật Dân sự (thiên tai, dịch bệnh,
            đứt cáp quang biển quốc tế, quyết định khẩn cấp của cơ quan có thẩm quyền).
          </li>
        </ul>
      </LegalSection>

      {/* Điều 13: Hoàn tiền & Bảo lưu */}
      <LegalSection id="refund-reservation" title="Điều 13: Chính sách hoàn tiền & Bảo lưu thời gian dịch vụ">
        <p>
          Chính sách hoàn tiền và bảo lưu thời hạn dịch vụ được áp dụng theo từng gói hợp đồng cụ thể. Các yêu
          cầu hoàn phí hợp lệ do lỗi kỹ thuật kéo dài từ phía nhà cung cấp sẽ được xử lý trong vòng 7 ngày làm việc.
        </p>
      </LegalSection>

      {/* Điều 14: Điều khoản thi hành & Tranh chấp */}
      <LegalSection id="final-provisions" title="Điều 14: Điều khoản thi hành & Giải quyết tranh chấp">
        <p>
          Thỏa thuận này có hiệu lực kể từ thời điểm công bố trên website. Mọi tranh chấp phát sinh trong quá
          trình thực hiện thỏa thuận sẽ được ưu tiên giải quyết thông qua thương lượng hòa giải. Trường hợp
          không đạt được thỏa thuận, vụ việc sẽ được đưa ra Tòa án nhân dân có thẩm quyền tại Việt Nam để giải quyết.
        </p>
      </LegalSection>

      {/* Thông tin chủ thể vận hành */}
      <LegalSection id="entity-info" title="Thông tin chủ thể vận hành hợp pháp" badge="Đại diện pháp lý">
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 text-xs sm:text-sm">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Tên chủ thể vận hành:</span>
            <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Domain chính thức:</span>
            <span className="font-mono font-bold text-[var(--text-primary)]">https://{LEGAL_PRIMARY_DOMAIN}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Hotline liên hệ:</span>
            <a href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`} className="font-bold text-[var(--text-primary)] hover:underline">
              {LEGAL_CONTACT_PHONE}
            </a>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Email tiếp nhận pháp lý:</span>
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
              {LEGAL_CONTACT_EMAIL}
            </a>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-[var(--text-muted)]">Phiên bản điều khoản:</span>
            <span className="font-mono font-bold text-[var(--text-brand)]">{LEGAL_POLICY_VERSION} ({LEGAL_UPDATED_AT})</span>
          </div>
        </div>
      </LegalSection>
    </LegalPageShell>
  );
}

