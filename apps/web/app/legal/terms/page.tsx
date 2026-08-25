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
  { id: "definitions", title: "Điều 1: Giải thích từ ngữ & Định nghĩa hệ thống" },
  { id: "prohibited", title: "Điều 2: Các hành vi bị nghiêm cấm & Giới hạn sử dụng" },
  { id: "customer-rights", title: "Điều 3: Quyền & nghĩa vụ của người sử dụng" },
  { id: "provider-rights", title: "Điều 4: Quyền & trách nhiệm của đơn vị cung cấp" },
  { id: "medical-boundary", title: "Điều 5: Ranh giới y tế & Giới hạn lâm sàng" },
  { id: "privacy-zero-cot", title: "Điều 6: Bảo mật, Zero-PII & Chuẩn Zero-CoT" },
  { id: "ai-transparency", title: "Điều 7: Minh bạch AI & Giám sát con người" },
  { id: "payment-terms", title: "Điều 8: Quy định về dịch vụ, thanh toán & Biểu phí" },
  { id: "renewal-suspension", title: "Điều 9: Gia hạn, tạm ngưng & Chấm dứt dịch vụ" },
  { id: "user-data-dsar", title: "Điều 10: Quản lý dữ liệu người dùng & Quyền DSAR" },
  { id: "support-channel", title: "Điều 11: Hỗ trợ khách hàng, sự cố & Kênh DPO" },
  { id: "liability-disclaimer", title: "Điều 12: Giới hạn trách nhiệm & Bất khả kháng" },
  { id: "refund-reservation", title: "Điều 13: Chính sách hoàn tiền & Bảo lưu quyền lợi" },
  { id: "final-provisions", title: "Điều 14: Điều khoản thi hành & Giải quyết tranh chấp" },
  { id: "entity-info", title: "Thông tin chủ thể vận hành hợp pháp" },
];

export default function TermsOfServicePage() {
  return (
    <LegalPageShell
      policyKey="terms"
      title="Điều khoản sử dụng & Thỏa thuận người dùng"
      summary="Văn bản này xác lập hợp đồng dịch vụ pháp lý ràng buộc 14 điều khoản giữa người dùng và đơn vị vận hành The Clara Care, quy định ranh giới trách nhiệm lâm sàng theo Luật Khám bệnh 2023, bảo vệ dữ liệu nhạy cảm theo Nghị định 13/2023/NĐ-CP, minh bạch AI theo Luật 134/2025/QH15 và cơ chế tài phán tranh chấp tại Hà Nội / TP. Hồ Chí Minh."
      updatedAt={LEGAL_UPDATED_AT}
      version={LEGAL_POLICY_VERSION}
      sections={TERMS_SECTIONS}
      highlights={[
        "Xác lập rõ ranh giới hỗ trợ thông tin y tế, không thay thế bác sĩ theo Luật Khám bệnh 2023.",
        "Bảo vệ dữ liệu cá nhân nhạy cảm và bảo đảm 11 quyền DSAR theo Nghị định 13/2023/NĐ-CP.",
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
      <LegalSection id="preamble" title="Lời mở đầu & Thỏa thuận ràng buộc" badge="Hiệu lực pháp lý">
        <p>
          Chào mừng bạn đến với <strong>The Clara Care</strong> (sau đây gọi tắt là “CLARA” hoặc “Hệ thống”).
          Thỏa thuận người dùng này (gọi chung là “Điều khoản sử dụng” hoặc “Hợp đồng dịch vụ điện tử”) cấu thành
          một hợp đồng pháp lý có giá trị ràng buộc đầy đủ giữa bạn (người dùng cá nhân, người giám hộ, chuyên gia
          y tế, nhà nghiên cứu hoặc tổ chức đại diện) và chủ thể vận hành hợp pháp của The Clara Care.
        </p>
        <p>
          Căn cứ theo quy định của <strong>Luật Giao dịch điện tử 2023</strong> và <strong>Bộ luật Dân sự 2015</strong>,
          việc bạn thực hiện bất kỳ hành động nào như: đăng ký tài khoản, đăng nhập, nhấn “Chấp thuận”, duyệt nội
          dung, gửi câu hỏi tham vấn, đồng bộ dữ liệu hồ sơ sức khỏe hoặc kết nối API đều có giá trị pháp lý tương
          đương với chữ ký trực tiếp xác nhận bạn đã đọc kỹ, hiểu rõ, đồng ý vô điều kiện và cam kết tuân thủ
          toàn bộ các điều khoản trong văn bản này cùng Chính sách quyền riêng tư và Điều khoản đồng thuận y tế liên
          quan.
        </p>
      </LegalSection>

      {/* Căn cứ pháp lý */}
      <LegalSection id="legal-basis" title="Căn cứ pháp lý áp dụng" badge="Luật áp dụng">
        <p>
          Thỏa thuận này được thiết lập, diễn giải và điều chỉnh bởi hệ thống văn bản quy phạm pháp luật hiện hành
          của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam, đồng thời hài hòa với các nguyên tắc và thông lệ quốc tế
          về an ninh y tế và bảo vệ dữ liệu số:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Luật Khám bệnh, chữa bệnh số 15/2023/QH15:</strong> Quy định về điều kiện hành nghề y tế,
            trách nhiệm chuyên môn lâm sàng và các giới hạn pháp lý đối với công cụ hỗ trợ công nghệ thông tin
            trong chăm sóc sức khỏe.
          </li>
          <li>
            <strong>Nghị định số 13/2023/NĐ-CP (PDPD):</strong> Quy định về bảo vệ dữ liệu cá nhân, xử lý dữ
            liệu cá nhân nhạy cảm (dữ liệu y tế & sức khỏe) và thực thi 11 quyền của chủ thể dữ liệu (DSAR).
          </li>
          <li>
            <strong>Luật Trí tuệ nhân tạo số 134/2025/QH15:</strong> Tiêu chuẩn an toàn thuật toán, phân loại
            hệ thống AI rủi ro cao trong y tế, yêu cầu minh bạch dữ liệu huấn luyện và nguyên tắc duy trì sự
            giám sát của con người (Human Oversight).
          </li>
          <li>
            <strong>Luật Giao dịch điện tử số 20/2023/QH15, Luật An toàn thông tin mạng 2015</strong> và
            <strong> Luật An ninh mạng 2018:</strong> Về giao kết hợp đồng trên môi trường mạng, xác thực số và
            bảo đảm an toàn hạ tầng thông tin.
          </li>
          <li>
            <strong>Bộ luật Dân sự số 91/2015/QH13:</strong> Về xác lập giao dịch dân sự, nghĩa vụ bồi thường
            thiệt hại và giải quyết tranh chấp hợp đồng.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 1: Giải thích từ ngữ */}
      <LegalSection id="definitions" title="Điều 1: Giải thích từ ngữ & Định nghĩa hệ thống">
        <p>Trong phạm vi Thỏa thuận này, các thuật ngữ dưới đây được hiểu và định nghĩa như sau:</p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>The Clara Care / Chúng tôi:</strong> Nền tảng trợ lý trí tuệ nhân tạo y tế thông minh và quản
            trị hồ sơ sức khỏe cá nhân, do chủ thể vận hành hợp pháp quản trị và cung cấp.
          </li>
          <li>
            <strong>Người dùng / Khách hàng / Bạn:</strong> Bất kỳ thể nhân hoặc pháp nhân nào truy cập, tạo tài
            khoản, sử dụng giao diện web, ứng dụng di động hoặc tích hợp API của The Clara Care.
          </li>
          <li>
            <strong>Hồ sơ sức khỏe cá nhân (PHR):</strong> Cơ sở dữ liệu y tế do người dùng tự cung cấp hoặc được
            số hóa qua hệ thống, bao gồm tiền sử bệnh, danh mục thuốc, dị ứng, chỉ số sinh hiệu và tài liệu y khoa.
          </li>
          <li>
            <strong>Tác tử y khoa (Clinical Agents):</strong> Các module thuật toán AI chuyên biệt bao gồm:
            <em>CareGuard</em> (phát hiện tương tác thuốc DDI & rủi ro lâm sàng), <em>Clinical Council</em> (hội
            chẩn đa tác tử), <em>Scribe</em> (bóc tách ghi chú y khoa và OCR đơn thuốc), <em>FIDES</em> (xác thực
            độ tin cậy y văn).
          </li>
          <li>
            <strong>Chuẩn Zero-CoT (Zero Chain-of-Thought Retention):</strong> Nguyên tắc an ninh bảo đảm chuỗi
            suy luận logic trung gian của AI chỉ tồn tại tạm thời trong RAM và bị hủy ngay lập tức sau khi tạo câu
            trả lời an toàn, không bao giờ được lưu trữ trong cơ sở dữ liệu dài hạn.
          </li>
          <li>
            <strong>Zero-PII Telemetry:</strong> Cơ chế giám sát kỹ thuật loại bỏ 100% dữ liệu định danh cá nhân
            và thông tin sức khỏe gốc ra khỏi toàn bộ hệ thống log và số liệu vận hành.
          </li>
          <li>
            <strong>Quyền DSAR (Data Subject Access Rights):</strong> 11 quyền theo luật định của người dùng đối
            với dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 2: Hành vi bị cấm */}
      <LegalSection id="prohibited" title="Điều 2: Các hành vi bị nghiêm cấm & Giới hạn sử dụng">
        <p>Người dùng tuyệt đối không được thực hiện các hành vi sau đây:</p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Sử dụng các phản hồi hoặc phân tích của hệ thống để mạo danh bác sĩ, tự ý cấp đơn thuốc, hoặc thực hiện
            hành vi hành nghề khám chữa bệnh trái pháp luật theo quy định của Luật Khám bệnh, chữa bệnh 2023.
          </li>
          <li>
            Cung cấp thông tin bệnh sử, đơn thuốc hoặc danh tính giả mạo nhằm mục đích phá hoại hệ thống, lừa đảo
            hoặc trục lợi các chế độ bảo hiểm y tế.
          </li>
          <li>
            Tấn công an ninh mạng, phát tán mã độc, đảo ngược mã nguồn (reverse engineering), can thiệp cấu trúc
            API hoặc cố tình phá vỡ các hàng rào an toàn kỹ thuật (guardrails bypass / prompt injection).
          </li>
          <li>
            Khai thác quá mức tài nguyên hệ thống, quét dữ liệu tự động (scraping) hoặc gây suy giảm chất lượng dịch
            vụ đối với những người dùng khác.
          </li>
          <li>
            Lợi dụng nền tảng để phát tán thông tin sai lệch về y tế, tài liệu độc hại hoặc xâm phạm quyền riêng tư
            của bất kỳ bên thứ ba nào.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 3: Quyền và nghĩa vụ người dùng */}
      <LegalSection id="customer-rights" title="Điều 3: Quyền & nghĩa vụ của người sử dụng">
        <div className="space-y-3">
          <p>
            <strong>1. Quyền của người sử dụng:</strong>
          </p>
          <ul className="list-disc space-y-1.5 pl-5 text-xs sm:text-sm">
            <li>
              Được quyền truy cập, tra cứu thông tin y văn chính thống và sử dụng các tính năng trong phạm vi gói
              dịch vụ đã đăng ký.
            </li>
            <li>
              Toàn quyền tự quyết đối với dữ liệu hồ sơ sức khỏe cá nhân (PHR), bao gồm quyền xem, chỉnh sửa, trích
              xuất dữ liệu (Data Portability) và yêu cầu xóa vĩnh viễn dữ liệu theo đúng Nghị định 13/2023/NĐ-CP.
            </li>
            <li>
              Được bảo đảm quyền riêng tư, an toàn thông tin theo chuẩn Zero-PII Telemetry và Zero-CoT.
            </li>
            <li>
              Được hỗ trợ kỹ thuật và khiếu nại chất lượng dịch vụ theo quy trình hỗ trợ chính thức.
            </li>
          </ul>

          <p className="pt-2">
            <strong>2. Nghĩa vụ của người sử dụng:</strong>
          </p>
          <ul className="list-disc space-y-1.5 pl-5 text-xs sm:text-sm">
            <li>
              Tự chịu trách nhiệm bảo mật thông tin đăng nhập, mã xác thực OTP và các phiên làm việc của tài khoản.
            </li>
            <li>
              Cam kết cung cấp thông tin trung thực, chính xác về tiền sử bệnh, danh mục thuốc và triệu chứng để hệ
              thống phân tích tương tác và rủi ro chính xác nhất.
            </li>
            <li>
              Luôn chủ động đối chiếu và tham vấn ý kiến của bác sĩ hoặc chuyên gia y tế có chứng chỉ hành nghề trước
              khi đưa ra bất kỳ quyết định điều trị y khoa nào.
            </li>
            <li>
              Thanh toán đầy đủ và đúng hạn các khoản phí dịch vụ theo biểu phí quy định (đối với các gói trả phí).
            </li>
          </ul>
        </div>
      </LegalSection>

      {/* Điều 4: Quyền và trách nhiệm nhà cung cấp */}
      <LegalSection id="provider-rights" title="Điều 4: Quyền & trách nhiệm của đơn vị cung cấp">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Duy trì chất lượng dịch vụ:</strong> Cam kết nỗ lực tối đa để duy trì độ sẵn sàng, tính ổn định
            và độ an toàn của hệ thống theo tiêu chuẩn kỹ thuật công bố.
          </li>
          <li>
            <strong>Cập nhật y văn chính thống:</strong> Thường xuyên cập nhật cơ sở tri thức y văn (Living Evidence,
            Dược thư quốc gia, PubMed) nhằm đảm bảo dữ liệu tham chiếu phản ánh các chứng cứ khoa học cập nhật.
          </li>
          <li>
            <strong>Quyền kiểm soát tài khoản:</strong> Đơn vị có quyền tạm khóa, đình chỉ hoặc hủy bỏ vĩnh viễn quyền
            truy cập của các tài khoản có hành vi gian lận, phá hoại an ninh mạng hoặc vi phạm Điều khoản sử dụng.
          </li>
          <li>
            <strong>Tiếp nhận và giải quyết yêu cầu:</strong> Tiếp nhận phản hồi, giải quyết khiếu nại và thực thi các
            yêu cầu quyền chủ thể dữ liệu (DSAR) trong thời hạn quy định.
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
            <strong>Không chẩn đoán xác định:</strong> Mọi thông tin phân tích triệu chứng, gợi ý bệnh học chỉ mang tính
            chất định hướng tham khảo khoa học, không cấu thành chẩn đoán y khoa chính thức.
          </li>
          <li>
            <strong>Không kê đơn thuốc tự động:</strong> Hệ thống không kê đơn thuốc mới; các cảnh báo tương tác thuốc
            (DDI) và liều dùng chỉ nhằm hỗ trợ người dùng nhận diện rủi ro để trao đổi lại với bác sĩ điều trị.
          </li>
          <li>
            <strong>Bắt buộc xác nhận chuyên môn:</strong> Mọi quyết định can thiệp điều trị, dùng thuốc hay thay đổi lối
            sống trị liệu bắt buộc phải do nhân sự y tế có chứng chỉ hành nghề hợp pháp xác nhận.
          </li>
          <li>
            <strong>Tình huống khẩn cấp (Emergency Fast-Path):</strong> Khi xuất hiện các dấu hiệu đe dọa tính mạng (đau
            ngực dữ dội, khó thở cấp, đột quỵ, sốc phản vệ, co giật, hôn mê), người dùng phải kích hoạt cấp cứu 115 hoặc
            đến ngay bệnh viện gần nhất; tuyệt đối không chờ đợi phản hồi từ hệ thống AI.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 6: Bảo mật, Zero-PII & Zero-CoT */}
      <LegalSection
        id="privacy-zero-cot"
        title="Điều 6: Bảo mật thông tin, Zero-PII & Chuẩn Zero-CoT"
        badge="Nghị định 13/2023"
      >
        <p>
          The Clara Care thiết lập hàng rào bảo vệ dữ liệu bất biến theo <strong>Nghị định 13/2023/NĐ-CP</strong>:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Phân loại dữ liệu nhạy cảm:</strong> Dữ liệu sức khỏe và bệnh sử cá nhân được bảo vệ theo cấp độ cao
            nhất của quy định pháp luật về bảo vệ dữ liệu cá nhân nhạy cảm.
          </li>
          <li>
            <strong>Bảo đảm Zero-CoT:</strong> Chuỗi suy luận logic nội bộ của các tác tử AI được hủy ngay sau khi tạo câu
            trả lời tổng hợp an toàn; không lưu trữ vĩnh viễn và không xuất ra API.
          </li>
          <li>
            <strong>Zero-PII Telemetry:</strong> Toàn bộ log lỗi và số liệu giám sát vận hành được loại bỏ 100% dữ liệu định
            danh cá nhân (không chứa tên, email, toa thuốc hay triệu chứng gốc).
          </li>
          <li>
            <strong>Không thương mại hóa dữ liệu:</strong> Tuyệt đối không kinh doanh, mua bán hoặc chia sẻ dữ liệu y tế
            của người dùng cho bên thứ ba vì mục đích thương mại hay quảng cáo.
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
          Căn cứ <strong>Luật Trí tuệ nhân tạo số 134/2025/QH15</strong>, The Clara Care thực thi các nguyên tắc minh bạch:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Hệ thống được xếp hạng là <strong>AI rủi ro cao trong y tế</strong> và luôn duy trì quyền kiểm soát, giám sát
            và can thiệp của con người (Human-in-the-Loop Oversight).
          </li>
          <li>
            Mỗi kết quả tham vấn đều công khai họ mô hình suy luận (DeepSeek foundation models) và hiển thị đầy đủ tài liệu
            nguồn tham chiếu từ Living Evidence, PubMed và Dược thư quốc gia.
          </li>
          <li>
            Khi hệ thống hoạt động ở chế độ dự phòng nội bộ (Degraded mode), trạng thái suy giảm sẽ được gắn nhãn trực quan
            và rõ ràng trên giao diện người dùng.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 8: Thanh toán & Biểu phí */}
      <LegalSection id="payment-terms" title="Điều 8: Quy định về dịch vụ, thanh toán & Biểu phí">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Biểu phí minh bạch:</strong> Biểu phí dịch vụ được niêm yết công khai trên website theo từng gói tính
            năng (Gói Cá nhân, Gói Chuyên gia, Gói Tổ chức y tế) và chu kỳ thanh toán.
          </li>
          <li>
            <strong>Phương thức thanh toán:</strong> Người dùng có thể thanh toán qua các cổng thanh toán điện tử hợp pháp,
            chuyển khoản ngân hàng hoặc thẻ thanh toán quốc tế được cấp phép tại Việt Nam.
          </li>
          <li>
            <strong>Hóa đơn điện tử hợp pháp:</strong> Hóa đơn giá trị gia tăng (VAT) điện tử được xuất theo đúng quy định
            của pháp luật thuế Việt Nam và gửi tự động qua email đăng ký của người dùng.
          </li>
          <li>
            <strong>Tính năng miễn phí cộng đồng:</strong> Các tính năng an toàn cơ bản và tra cứu thông tin y tế thiết yếu
            luôn được duy trì phục vụ cộng đồng phi thương mại.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 9: Gia hạn & Tạm ngưng dịch vụ */}
      <LegalSection id="renewal-suspension" title="Điều 9: Gia hạn, tạm ngưng & Chấm dứt dịch vụ">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Gia hạn dịch vụ:</strong> Các gói dịch vụ trả phí định kỳ sẽ tự động gia hạn trừ khi người dùng chủ động
            hủy đăng ký trước ngày kết thúc chu kỳ hiện tại.
          </li>
          <li>
            <strong>Tạm ngưng để bảo trì:</strong> Dịch vụ có thể tạm ngưng trong các khung giờ bảo trì định kỳ có thông báo
            trước tối thiểu 24 giờ trên hệ thống hoặc trong trường hợp sự cố mạng diện rộng bất khả kháng.
          </li>
          <li>
            <strong>Đình chỉ do vi phạm:</strong> Đơn vị cung cấp có quyền đình chỉ ngay lập tức tài khoản có dấu hiệu tấn
            công an ninh, cố tình bypass guardrails hoặc vi phạm nghiêm trọng Điều khoản sử dụng.
          </li>
          <li>
            <strong>Chấm dứt và xử lý dữ liệu:</strong> Người dùng có quyền chấm dứt tài khoản bất kỳ lúc nào; dữ liệu sẽ
            được xử lý theo quy định xóa an toàn hoặc ẩn danh hóa tại Chính sách quyền riêng tư.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 10: Quản lý dữ liệu & Quyền DSAR */}
      <LegalSection id="user-data-dsar" title="Điều 10: Quản lý dữ liệu người dùng & Quyền DSAR">
        <p>
          Căn cứ Nghị định 13/2023/NĐ-CP, bạn có đầy đủ 11 quyền hợp pháp đối với dữ liệu cá nhân của mình. Bạn có thể
          thực hiện quyền thông qua Cổng Dữ liệu của tôi (DSAR Portal), Trung tâm Đồng thuận trong phần cài đặt tài khoản,
          hoặc gửi yêu cầu trực tiếp tới Cán bộ bảo vệ dữ liệu (DPO).
        </p>
        <p className="pt-1">
          Chúng tôi cam kết tiếp nhận, xác thực danh tính và xử lý dứt điểm các yêu cầu hợp lệ trong thời hạn tối đa
          <strong> 72 giờ làm việc</strong> kể từ thời điểm tiếp nhận.
        </p>
      </LegalSection>

      {/* Điều 11: Hỗ trợ khách hàng & DPO */}
      <LegalSection id="support-channel" title="Điều 11: Hỗ trợ khách hàng, sự cố & Kênh DPO">
        <p>
          Kênh tiếp nhận hỗ trợ chính thức: Email{" "}
          <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
            {LEGAL_CONTACT_EMAIL}
          </a>{" "}
          và Hotline{" "}
          <a href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`} className="font-bold text-[var(--text-primary)] hover:underline">
            {LEGAL_CONTACT_PHONE}
          </a>
          . Chúng tôi tiếp nhận phản ánh kỹ thuật 24/7 và giải quyết khiếu nại, phản ánh chất lượng trong thời hạn từ 3–5 ngày
          làm việc.
        </p>
      </LegalSection>

      {/* Điều 12: Giới hạn trách nhiệm & Bất khả kháng */}
      <LegalSection id="liability-disclaimer" title="Điều 12: Giới hạn trách nhiệm & Bất khả kháng">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Giới hạn trách nhiệm:</strong> Trong mọi trường hợp, tổng mức trách nhiệm bồi thường thiệt hại tối đa
            của The Clara Care đối với bất kỳ khiếu nại nào phát sinh từ việc sử dụng dịch vụ không vượt quá tổng số phí
            mà người dùng đã thanh toán cho chúng tôi trong vòng 12 tháng gần nhất trước thời điểm phát sinh sự kiện.
          </li>
          <li>
            <strong>Miễn trừ thiệt hại gián tiếp:</strong> The Clara Care không chịu trách nhiệm đối với các thiệt hại phát
            sinh do người dùng tự ý sử dụng thông tin AI để tự điều trị trái với chỉ định của bác sĩ hoặc cung cấp dữ liệu y
            tế sai lệch.
          </li>
          <li>
            <strong>Sự kiện bất khả kháng:</strong> Các bên được miễn trừ trách nhiệm trong các trường hợp bất khả kháng theo
            quy định của Bộ luật Dân sự 2015 (thiên tai, chiến tranh, dịch bệnh, đứt cáp quang biển quốc tế, quyết định khẩn
            cấp của cơ quan nhà nước có thẩm quyền).
          </li>
        </ul>
      </LegalSection>

      {/* Điều 13: Hoàn tiền & Bảo lưu */}
      <LegalSection id="refund-reservation" title="Điều 13: Chính sách hoàn tiền & Bảo lưu quyền lợi">
        <p>
          Chính sách hoàn tiền và bảo lưu thời hạn dịch vụ được áp dụng theo từng gói hợp đồng cụ thể:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            Trường hợp dịch vụ bị gián đoạn do lỗi kỹ thuật kéo dài trên 48 giờ liên tục từ phía nhà cung cấp, người dùng
            được quyền yêu cầu hoàn lại phần phí dịch vụ tương ứng với thời gian gián đoạn hoặc cộng dồn thời hạn sử dụng.
          </li>
          <li>
            Các yêu cầu hoàn phí hợp lệ sẽ được đối soát và xử lý hoàn trả vào tài khoản nguồn trong thời hạn 7 ngày làm
            việc.
          </li>
        </ul>
      </LegalSection>

      {/* Điều 14: Điều khoản thi hành & Tranh chấp */}
      <LegalSection id="final-provisions" title="Điều 14: Điều khoản thi hành & Giải quyết tranh chấp">
        <p>
          Thỏa thuận này có hiệu lực kể từ thời điểm công bố trên website chính thức và áp dụng cho toàn bộ hoạt động giao
          kết trên nền tảng The Clara Care.
        </p>
        <p>
          <strong>Cơ chế giải quyết tranh chấp:</strong> Mọi tranh chấp, bất đồng phát sinh từ hoặc liên quan đến Thỏa
          thuận này trước hết sẽ được giải quyết thông qua thương lượng, hòa giải thiện chí giữa các bên trong thời hạn 30
          ngày. Trường hợp không đạt được thỏa thuận qua hòa giải, tranh chấp sẽ được đưa ra giải quyết tại Trung tâm
          Trọng tài Quốc tế Việt Nam (VIAC) hoặc Tòa án nhân dân có thẩm quyền tại Thành phố Hà Nội hoặc Thành phố Hồ Chí
          Minh theo đúng quy định của pháp luật Việt Nam.
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
