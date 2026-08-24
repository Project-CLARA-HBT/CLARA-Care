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
import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân | The Clara Care",
  description:
    "Chính sách bảo vệ dữ liệu cá nhân, quyền của chủ thể dữ liệu (DSAR) theo Nghị định 13/2023/NĐ-CP, cam kết Zero-PII/Zero-CoT và minh bạch AI theo Luật 134/2025.",
};

const PRIVACY_SECTIONS: LegalSectionMeta[] = [
  { id: "scope", title: "1. Phạm vi áp dụng & Phân định vai trò" },
  { id: "data-categories", title: "2. Danh mục dữ liệu & Dữ liệu nhạy cảm" },
  { id: "zero-cot-guarantee", title: "3. Cam kết Zero-PII & Chuẩn Zero-CoT" },
  { id: "purposes-legal-basis", title: "4. Mục đích & Căn cứ pháp lý xử lý" },
  { id: "retention", title: "5. Thời hạn lưu trữ & Hủy dữ liệu" },
  { id: "sharing-policy", title: "6. Chia sẻ dữ liệu & Cam kết không bán thông tin" },
  { id: "processors", title: "7. Danh sách bên xử lý dữ liệu (NĐ 13/2023)" },
  { id: "security-measures", title: "8. Biện pháp an toàn thông tin & Mã hóa" },
  { id: "user-rights", title: "9. Quyền của chủ thể dữ liệu (DSAR)" },
  { id: "dsar-process", title: "10. Quy trình thực hiện DSAR & SLA tiếp nhận" },
  { id: "cross-border", title: "11. Chuyển dữ liệu xuyên biên giới & TIA" },
  { id: "ai-transparency", title: "12. Minh bạch AI (Luật 134/2025 & Luật Khám bệnh 2023)" },
  { id: "contact-dpo", title: "13. Cán bộ bảo vệ dữ liệu (DPO) & Cập nhật" },
];

/**
 * Third-party processors that may receive personal data, including offshore
 * model processors (regulatory-compliance Requirement 4.5). Surfaced here so the
 * privacy policy is the single public source of the processor + jurisdiction
 * list, consistent with the `TransferRegistry`.
 */
const THIRD_PARTY_PROCESSORS = [
  {
    name: "YEScale — điểm cuối DeepSeek (LLM, mô hình deepseek-v4-pro và deepseek-v4-flash)",
    purpose:
      "Suy luận mô hình ngôn ngữ lớn / LLM inference (sinh câu trả lời lâm sàng tham vấn)",
    jurisdiction: "Ngoài lãnh thổ Việt Nam (offshore / non-VN)",
    data: "Nội dung truy vấn đã tối thiểu hóa, loại trừ định danh trực tiếp khi khả thi; không lưu nội dung chuyển giao",
    safeguards: "Đánh giá TIA, đường truyền mã hóa TLS 1.3, không lưu vết huấn luyện mô hình",
  },
  {
    name: "YEScale — điểm cuối embedding (tương thích OpenAI, api.yescale.io)",
    purpose:
      "Tạo vector embedding phục vụ truy xuất ngữ nghĩa y văn (RAG Living Evidence)",
    jurisdiction: "Ngoài lãnh thổ Việt Nam (offshore / non-VN)",
    data: "Đoạn văn bản y khoa cần lập chỉ mục/truy xuất, đã khử định danh",
    safeguards: "Đánh giá TIA, mã hóa kênh truyền, không lưu nội dung",
  },
  {
    name: "Hạ tầng máy chủ lưu trữ và vận hành cơ sở dữ liệu",
    purpose: "Lưu trữ dữ liệu PHR, tài khoản, xác thực và vận hành dịch vụ",
    jurisdiction: "Việt Nam / Vùng dữ liệu chỉ định theo cấu hình triển khai",
    data: "Dữ liệu tài khoản, hồ sơ sức khỏe cá nhân (PHR) và audit log vận hành",
    safeguards: "Mã hóa AES-256 at-rest, sao lưu định kỳ, kiểm soát phân quyền RBAC",
  },
] as const;

export default function PrivacyPolicyPage() {
  return (
    <LegalPageShell
      policyKey="privacy"
      title="Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân"
      summary="The Clara Care cam kết bảo vệ toàn diện dữ liệu sức khỏe và thông tin cá nhân của bạn theo Nghị định 13/2023/NĐ-CP, áp dụng chuẩn an toàn Zero-PII Telemetry và tuyệt đối không lưu trữ chuỗi suy luận logic (Zero-CoT), đồng thời tuân thủ đầy đủ Luật Khám bệnh 2023 và Luật Trí tuệ nhân tạo 134/2025/QH15."
      updatedAt={LEGAL_UPDATED_AT}
      version={LEGAL_POLICY_VERSION}
      sections={PRIVACY_SECTIONS}
      highlights={[
        "Tuân thủ nghiêm ngặt Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.",
        "Chuẩn Zero-CoT: Tuyệt đối không lưu trữ vĩnh viễn chuỗi suy luận logic nội bộ.",
        "Zero-PII Telemetry: Mọi chỉ số vận hành và log lỗi đều loại bỏ hoàn toàn dữ liệu định danh.",
        "Không dùng dữ liệu cá nhân hay hồ sơ sức khỏe (PHR) để huấn luyện mô hình AI công cộng.",
      ]}
      relatedControls={[
        {
          href: "/legal/consent",
          label: "Đồng thuận sử dụng y tế",
          description: "Điều khoản đồng thuận lâm sàng có hiệu lực",
        },
        {
          href: "/legal/terms",
          label: "Điều khoản sử dụng",
          description: "Ranh giới pháp lý & trách nhiệm dịch vụ",
        },
        {
          href: "/legal",
          label: "Trung tâm pháp lý",
          description: "Tổng hợp toàn bộ chính sách hệ sinh thái",
        },
      ]}
    >
      {/* 1. Phạm vi áp dụng */}
      <LegalSection
        id="scope"
        title="1. Phạm vi áp dụng & Phân định vai trò"
        badge="Phạm vi hệ thống"
      >
        <p>
          Chính sách quyền riêng tư này áp dụng cho toàn bộ người dùng truy cập hoặc sử dụng các
          dịch vụ của <strong>The Clara Care</strong>, bao gồm giao diện web (
          <span className="font-mono text-xs">{LEGAL_PRIMARY_DOMAIN}</span>), ứng dụng di động, các
          giao diện lập trình ứng dụng (API), các module chuyên môn (Research, Council, Self-Medication,
          CareGuard, Scribe, PHR, Lifemap) và không gian quản trị hệ thống.
        </p>
        <p>
          Hệ thống phân định rành mạch quyền hạn và dữ liệu giữa hai nhóm chủ thể:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Người dùng cuối (End-Users / Bệnh nhân / Thân nhân):</strong> Dữ liệu tài khoản cá
            nhân, hồ sơ sức khỏe cá nhân (PHR), toa thuốc, kết quả đo sinh hiệu, nội dung tương tác tham
            vấn và dữ liệu lịch sử đồng thuận.
          </li>
          <li>
            <strong>Quản trị viên và Chuyên gia y tế (Admins / Doctors / Researchers):</strong> Nhật ký thao
            tác quản trị, cấu hình danh mục y khoa, dữ liệu giám sát vận hành hệ thống và báo cáo kiểm
            toán an toàn.
          </li>
        </ul>
        <p>
          Nguyên tắc phân quyền theo vai trò (RBAC) được thực thi nghiêm ngặt tại tầng gateway máy chủ;
          quản trị viên không có quyền xem thông tin cá nhân chưa khử định danh của người dùng nếu không
          có sự chấp thuận hợp lệ hoặc căn cứ điều tra sự cố được pháp luật cho phép.
        </p>
      </LegalSection>

      {/* 2. Danh mục dữ liệu */}
      <LegalSection
        id="data-categories"
        title="2. Danh mục dữ liệu được thu thập & Dữ liệu sức khỏe nhạy cảm"
        badge="Phân loại dữ liệu"
      >
        <p>
          Theo quy định tại <strong>Điều 2 và Điều 9 Nghị định 13/2023/NĐ-CP</strong>, The Clara Care
          thu thập và xử lý hai nhóm dữ liệu:
        </p>
        <div className="space-y-3">
          <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              A. Dữ liệu cá nhân cơ bản
            </h3>
            <ul className="list-disc space-y-1.5 pl-5 text-xs sm:text-sm">
              <li>Thông tin tài khoản: Họ tên, địa chỉ email, số điện thoại đăng ký, mật khẩu băm mật mã.</li>
              <li>Thông tin định danh phiên: Cookie phiên làm việc an toàn, token ủy quyền xác thực.</li>
              <li>Tùy chọn hiển thị: Ngôn ngữ (vi/en), chế độ màu giao diện, trạng thái onboarding.</li>
            </ul>
          </div>

          <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)]/70 bg-[var(--status-warn-bg)]/20 p-4 space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--status-warn-text)]">
              B. Dữ liệu cá nhân nhạy cảm (Dữ liệu y tế & Sức khỏe)
            </h3>
            <p className="text-xs sm:text-sm">
              Theo quy định pháp luật Việt Nam, thông tin về tình trạng sức khỏe và đời tư cá nhân là
              <strong> dữ liệu cá nhân nhạy cảm</strong>, chỉ được xử lý khi có sự đồng thuận rõ ràng của
              bạn:
            </p>
            <ul className="list-disc space-y-1.5 pl-5 text-xs sm:text-sm">
              <li>Hồ sơ sức khỏe cá nhân (PHR): Tiền sử bệnh, bệnh nền, chẩn đoán quá khứ, thông tin phẫu thuật.</li>
              <li>Tủ thuốc & Điều trị: Danh mục thuốc đang sử dụng, tiền sử dị ứng, tiền sử tác dụng phụ.</li>
              <li>Chỉ số sinh hiệu: Huyết áp, đường huyết, nhịp tim, chỉ số SpO2, cân nặng, chiều cao.</li>
              <li>Tài liệu y khoa tải lên: Hình ảnh đơn thuốc, phiếu xét nghiệm, hồ sơ xuất viện (OCR/Vision).</li>
              <li>Bản ghi âm hội thoại y tế (Scribe): Bản ghi phiên làm việc chuyên môn phục vụ tạo tóm tắt lâm sàng.</li>
            </ul>
          </div>
        </div>
      </LegalSection>

      {/* 3. Cam kết Zero-PII & Chuẩn Zero-CoT */}
      <LegalSection
        id="zero-cot-guarantee"
        title="3. Cam kết Bảo đảm Zero-PII Telemetry & Chuẩn Zero-CoT"
        badge="An toàn cốt lõi"
      >
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--status-ok-border)]/60 bg-[var(--status-ok-bg)]/30 p-5 space-y-3">
          <div className="flex items-center gap-2 text-[var(--status-ok-text)]">
            <Icon name="check" size="1.2rem" />
            <h3 className="text-sm font-bold">
              Bảo đảm Bất biến về Quyền riêng tư (Privacy Invariants)
            </h3>
          </div>
          <p className="text-xs sm:text-sm leading-relaxed text-[var(--text-primary)]">
            The Clara Care áp dụng các tiêu chuẩn an ninh kỹ thuật tiên tiến nhất để bảo đảm dữ liệu của
            bạn không bị rò rỉ hoặc sử dụng sai mục đích:
          </p>
        </div>

        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <h4 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-[var(--brand-500)]" />
              1. Zero-PII Telemetry (Không thu thập PII trong hệ thống giám sát)
            </h4>
            <p>
              Toàn bộ luồng dữ liệu đo lường kỹ thuật, nhật ký sự kiện, phân tích lưu lượng và cảnh báo
              lỗi hệ thống (telemetry) được thiết kế theo nguyên tắc <strong>hoàn toàn không chứa PII</strong>.
              Hệ thống loại bỏ triệt để họ tên, địa chỉ email, triệu chứng lâm sàng, câu hỏi nguyên văn và
              danh mục thuốc của người dùng ra khỏi mọi bản ghi phân tích; chỉ thu thập số lượng đếm
              (counts), phân phối tổng hợp (distributions), thời gian phản hồi (percentiles) và mã trạng thái
              lỗi kỹ thuật.
            </p>
          </div>

          <div className="space-y-2">
            <h4 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-[var(--brand-500)]" />
              2. Chuẩn Zero-CoT (Zero Chain-of-Thought Retention)
            </h4>
            <p>
              Trong quá trình các tác tử AI (CareGuard, Council, FIDES) thực hiện phân tích đối chiếu y
              văn, các bước suy luận trung gian (chuỗi logic nội bộ - Chain-of-Thought) chỉ tồn tại trong
              bộ nhớ tạm thời (ephemeral memory) trong thời gian tính toán request. Sau khi câu trả lời
              tổng hợp được kiểm duyệt an toàn, <strong>toàn bộ chuỗi suy luận CoT lập tức bị hủy bỏ</strong>.
              Hệ thống tuyệt đối không lưu trữ CoT vào cơ sở dữ liệu dài hạn và không để lộ CoT qua API công
              khai.
            </p>
          </div>

          <div className="space-y-2">
            <h4 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-[var(--brand-500)]" />
              3. Tuyệt đối không dùng dữ liệu người dùng để huấn luyện AI công cộng
            </h4>
            <p>
              The Clara Care <strong>tuyệt đối không sử dụng</strong> dữ liệu cá nhân, câu hỏi lâm sàng,
              dữ liệu PHR hay các tài liệu y tế của bạn để huấn luyện hoặc tái huấn luyện các mô hình AI
              thương mại hay mô hình nền tảng công cộng của bên thứ ba.
            </p>
          </div>
        </div>
      </LegalSection>

      {/* 4. Mục đích & Căn cứ pháp lý */}
      <LegalSection
        id="purposes-legal-basis"
        title="4. Mục đích & Căn cứ pháp lý xử lý dữ liệu"
        badge="Căn cứ pháp lý"
      >
        <p>
          The Clara Care xử lý dữ liệu cá nhân và dữ liệu y tế dựa trên các căn cứ pháp lý quy định tại
          <strong> Nghị định 13/2023/NĐ-CP</strong>, <strong>Luật Giao dịch điện tử 2023</strong>,
          <strong> Luật An toàn thông tin mạng 2015</strong> và <strong>Luật Khám bệnh, chữa bệnh 2023</strong>:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Sự đồng ý của chủ thể dữ liệu (Điều 11 NĐ 13/2023):</strong> Áp dụng cho việc xử lý
            dữ liệu y tế nhạy cảm, tra cứu tương tác thuốc, phân tích hồ sơ sức khỏe và suy luận mô hình AI.
          </li>
          <li>
            <strong>Thực hiện thỏa thuận cung cấp dịch vụ:</strong> Duy trì tài khoản, xác thực bảo mật,
            lưu trữ hồ sơ cá nhân và hiển thị kết quả người dùng yêu cầu.
          </li>
          <li>
            <strong>Nghĩa vụ pháp lý và lưu vết kiểm toán:</strong> Lưu trữ bản ghi xác thực đồng thuận
            và audit log ẩn danh nhằm đáp ứng nghĩa vụ giải trình theo quy định của cơ quan nhà nước có
            thẩm quyền.
          </li>
          <li>
            <strong>Tình huống khẩn cấp bảo vệ tính mạng (Điều 17 NĐ 13/2023):</strong> Kích hoạt luồng
            chuyển hướng cấp cứu khẩn cấp y tế (Emergency Fast-Path) khi phát hiện dấu hiệu đe dọa sinh mạng.
          </li>
        </ul>
      </LegalSection>

      {/* 5. Thời hạn lưu trữ */}
      <LegalSection
        id="retention"
        title="5. Thời hạn lưu trữ & Chính sách hủy/ẩn danh hóa dữ liệu"
        badge="Vòng đời dữ liệu"
      >
        <p>
          Dữ liệu cá nhân chỉ được lưu trữ trong khoảng thời gian cần thiết để hoàn thành các mục đích đã
          được người dùng đồng thuận, hoặc theo thời hạn bắt buộc của pháp luật hiện hành:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Dữ liệu tài khoản & PHR:</strong> Được lưu giữ trong suốt thời gian tài khoản hoạt
            động. Người dùng có thể chỉnh sửa hoặc yêu cầu xóa bất kỳ lúc nào.
          </li>
          <li>
            <strong>Bản ghi tương tác tham vấn tạm thời:</strong> Được quản lý theo tùy chọn phiên làm việc;
            người dùng có thể chủ động xóa lịch sử hội thoại trên giao diện.
          </li>
          <li>
            <strong>Nhật ký kiểm toán an toàn (Audit Trails):</strong> Được khử định danh hoàn toàn và lưu
            trữ theo chu kỳ tuân thủ an ninh mạng để phòng chống gian lận và sự cố kỹ thuật.
          </li>
        </ul>
        <p>
          Khi tài khoản bị đóng hoặc khi có yêu cầu xóa hợp lệ từ chủ thể dữ liệu, hệ thống sẽ thực hiện
          quy trình xóa an toàn (crypto-shredding) hoặc ẩn danh hóa vĩnh viễn không thể khôi phục.
        </p>
      </LegalSection>

      {/* 6. Chia sẻ dữ liệu & Cam kết không bán */}
      <LegalSection
        id="sharing-policy"
        title="6. Chia sẻ dữ liệu & Cam kết tuyệt đối không bán thông tin"
        badge="Cam kết độc lập"
      >
        <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
          <p className="font-bold text-[var(--text-primary)]">
            Cam kết cốt lõi: The Clara Care không bao giờ bán, cho thuê hay thương mại hóa dữ liệu cá nhân
            và dữ liệu sức khỏe của người dùng cho bất kỳ bên thứ ba, công ty dược phẩm hay mạng lưới
            quảng cáo nào.
          </p>
        </div>
        <p>
          Hệ thống chỉ chia sẻ dữ liệu trong các trường hợp giới hạn nghiêm ngặt sau:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Với các đối tác xử lý hạ tầng kỹ thuật (được liệt kê tại Mục 7) có cam kết bảo mật theo hợp đồng
            xử lý dữ liệu (DPA) và tuân thủ Nghị định 13/2023/NĐ-CP.
          </li>
          <li>
            Khi có yêu cầu bằng văn bản hợp pháp từ cơ quan tiến hành tố tụng hoặc cơ quan quản lý nhà nước
            Việt Nam có thẩm quyền theo đúng trình tự luật định.
          </li>
        </ul>
      </LegalSection>

      {/* 7. Danh sách bên xử lý dữ liệu */}
      <LegalSection
        id="processors"
        title="7. Danh sách bên xử lý dữ liệu và quyền tài phán"
        badge="Nghị định 13/2023"
      >
        <p>
          Thực hiện <strong>Điều 25–27 Nghị định 13/2023/NĐ-CP</strong> về quản lý bên xử lý dữ liệu và
          chuyển dữ liệu ra nước ngoài, dưới đây là danh mục các đơn vị xử lý được cấp quyền kỹ thuật tối
          thiểu trong hệ thống:
        </p>

        <div className="overflow-x-auto">
          <table className="mt-2 w-full border-collapse text-left text-xs sm:text-[13px]">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-primary)] bg-[var(--surface-muted)]/60">
                <th className="p-3 font-bold">Bên xử lý dữ liệu</th>
                <th className="p-3 font-bold">Mục đích xử lý</th>
                <th className="p-3 font-bold">Quyền tài phán</th>
                <th className="p-3 font-bold">Phạm vi dữ liệu</th>
                <th className="p-3 font-bold">Biện pháp bảo vệ</th>
              </tr>
            </thead>
            <tbody>
              {THIRD_PARTY_PROCESSORS.map((p) => (
                <tr
                  key={p.name}
                  className="border-b border-[color:var(--shell-border)]/70 align-top hover:bg-[var(--surface-muted)]/30"
                >
                  <td className="p-3 font-semibold text-[var(--text-primary)]">{p.name}</td>
                  <td className="p-3">{p.purpose}</td>
                  <td className="p-3">{p.jurisdiction}</td>
                  <td className="p-3">{p.data}</td>
                  <td className="p-3 text-[11px] text-[var(--text-muted)]">{p.safeguards}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 8. Biện pháp an toàn thông tin */}
      <LegalSection
        id="security-measures"
        title="8. Biện pháp an toàn thông tin & Mã hóa kỹ thuật"
        badge="An ninh mạng"
      >
        <p>
          The Clara Care áp dụng các tiêu chuẩn an toàn kỹ thuật theo <strong>Luật An toàn thông tin mạng 2015</strong> và
          thông lệ bảo mật y tế quốc tế:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Mã hóa đầu cuối:</strong> Dữ liệu lưu trữ (at-rest) được mã hóa bằng chuẩn AES-256; dữ
            liệu truyền tải (in-transit) sử dụng TLS 1.3 với chuẩn mã hóa cấp cao.
          </li>
          <li>
            <strong>Bảo vệ phiên & Chống tấn công:</strong> Áp dụng cơ chế CSRF token cho toàn bộ các yêu
            cầu thay đổi dữ liệu (mutations), phân tách cookie phiên `SameSite=Lax` và cấm truy cập chéo
            nguồn không hợp lệ.
          </li>
          <li>
            <strong>Phân vùng dữ liệu:</strong> Tách biệt vật lý và logic giữa dữ liệu tài khoản, dữ liệu
            lâm sàng PHR và dữ liệu nhật ký hệ thống.
          </li>
          <li>
            <strong>Quy trình xử lý sự cố:</strong> Kế hoạch phản ứng sự cố an ninh mạng định kỳ, thông
            báo cho cơ quan quản lý và người dùng trong thời hạn luật định khi có sự cố lộ lọt thông tin.
          </li>
        </ul>
      </LegalSection>

      {/* 9. Quyền của chủ thể dữ liệu */}
      <LegalSection
        id="user-rights"
        title="9. Quyền của chủ thể dữ liệu theo Nghị định 13/2023/NĐ-CP"
        badge="Quyền của bạn"
      >
        <p>
          Theo quy định tại <strong>Điều 9 và Điều 14–16 Nghị định 13/2023/NĐ-CP</strong>, bạn có đầy đủ
          11 quyền hợp pháp đối với dữ liệu cá nhân của mình:
        </p>
        <div className="grid gap-3 sm:grid-cols-2 pt-2">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">1. Quyền được biết</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Được thông báo rõ ràng về các hoạt động xử lý dữ liệu cá nhân của mình.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">2. Quyền đồng ý & rút đồng thuận</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Tự do cấp hoặc rút lại sự đồng ý đối với từng mục đích xử lý bất kỳ lúc nào.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">3. Quyền truy cập & xem dữ liệu</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Xem trực tiếp và yêu cầu cung cấp bản sao hồ sơ sức khỏe và thông tin cá nhân.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">4. Quyền xóa dữ liệu</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Yêu cầu xóa vĩnh viễn hoặc ẩn danh hóa thông tin cá nhân khi không còn nhu cầu.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">5. Quyền hạn chế xử lý</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Yêu cầu tạm ngưng hoặc hạn chế phạm vi xử lý dữ liệu trong các trường hợp tranh chấp.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">6. Quyền cung cấp dữ liệu (Portability)</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Trích xuất toàn bộ dữ liệu PHR dưới định dạng chuẩn máy đọc được (JSON/CSV).
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">7. Quyền phản đối xử lý dữ liệu</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Phản đối việc xử lý dữ liệu nhằm mục đích quảng cáo, tiếp thị hoặc phân tích tự động.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-1">
            <span className="text-xs font-bold text-[var(--text-brand)]">8. Quyền khiếu nại & khởi kiện</span>
            <p className="text-xs text-[var(--text-secondary)]">
              Khiếu nại tới Cục An ninh mạng và phòng, chống tội phạm công nghệ cao hoặc cơ quan có thẩm quyền.
            </p>
          </div>
        </div>
      </LegalSection>

      {/* 10. Quy trình thực hiện DSAR */}
      <LegalSection
        id="dsar-process"
        title="10. Quy trình thực hiện DSAR & SLA tiếp nhận xử lý"
        badge="Thực thi quyền"
      >
        <p>
          Người dùng đã đăng nhập có thể chủ động thực hiện quyền của mình thông qua các công cụ tự phục vụ:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Trang Dữ liệu của tôi (DSAR Portal):</strong> Truy cập mục cài đặt tài khoản để tải
            xuống tệp trích xuất dữ liệu, gửi yêu cầu chỉnh sửa hoặc yêu cầu đóng tài khoản và xóa dữ liệu.
          </li>
          <li>
            <strong>Trung tâm Đồng thuận:</strong> Bật/tắt đồng thuận xử lý dữ liệu nhạy cảm hoặc đồng thuận
            xử lý mô hình xuyên biên giới bất cứ lúc nào.
          </li>
          <li>
            <strong>Gửi yêu cầu qua DPO:</strong> Gửi email trực tiếp tới{" "}
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
              {LEGAL_CONTACT_EMAIL}
            </a>{" "}
            kèm thông tin xác thực chủ sở hữu tài khoản.
          </li>
        </ul>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 space-y-1.5 text-xs sm:text-sm">
          <p className="font-bold text-[var(--text-primary)]">Cam kết thời hạn xử lý (SLA):</p>
          <p className="text-[var(--text-secondary)]">
            Mọi yêu cầu thực thi quyền chủ thể dữ liệu (DSAR) được tiếp nhận và xử lý trong thời hạn tối đa
            <strong> 72 giờ làm việc</strong> kể từ thời điểm nhận đủ thông tin xác thực danh tính hợp lệ.
          </p>
        </div>
      </LegalSection>

      {/* 11. Chuyển dữ liệu xuyên biên giới */}
      <LegalSection
        id="cross-border"
        title="11. Chuyển dữ liệu xuyên biên giới & Đánh giá tác động (TIA)"
        badge="Nghị định 13 - Điều 25"
      >
        <p>
          Để cung cấp khả năng suy luận lâm sàng tiên tiến và đối chiếu y văn toàn cầu, hệ thống có thể
          cần chuyển một phần dữ liệu truy vấn đã tối thiểu hóa tới các điểm cuối mô hình đặt ngoài lãnh
          thổ Việt Nam (như mô tả tại Mục 7).
        </p>
        <p>
          Việc chuyển dữ liệu xuyên biên giới được quản lý chặt chẽ theo các điều kiện:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Chỉ thực hiện khi có <strong>sự đồng ý rõ ràng</strong> của người dùng về việc xử lý bởi mô
            hình bên thứ ba.
          </li>
          <li>
            Đã lập <strong>Hồ sơ đánh giá tác động chuyển dữ liệu ra nước ngoài (TIA)</strong> theo đúng
            mẫu quy định tại Nghị định 13/2023/NĐ-CP và lưu trữ tại hồ sơ tuân thủ.
          </li>
          <li>
            Khi người dùng không đồng ý hoặc rút đồng thuận xuyên biên giới, hệ thống tự động chuyển sang
            luồng xử lý nội địa hoặc chế độ trả lời suy giảm gắn nhãn rõ ràng mà không làm mất dữ liệu PHR.
          </li>
        </ul>
      </LegalSection>

      {/* 12. Minh bạch AI & Luật Khám bệnh */}
      <LegalSection
        id="ai-transparency"
        title="12. Minh bạch hệ thống AI (Luật 134/2025 & Luật Khám bệnh 2023)"
        badge="Quy chuẩn AI & Y tế"
      >
        <p>
          The Clara Care vận hành tuân thủ <strong>Luật Trí tuệ nhân tạo số 134/2025/QH15</strong> và
          <strong> Luật Khám bệnh, chữa bệnh 2023 (Luật số 15/2023/QH15)</strong>:
        </p>
        <div className="space-y-3 pt-1">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
              Phân loại AI rủi ro cao & Giám sát con người (Human-in-the-Loop)
            </h4>
            <p className="text-xs sm:text-sm">
              Theo Luật AI 134/2025, CLARA được phân loại là <strong>hệ thống AI rủi ro cao trong lĩnh vực y tế</strong>.
              Mọi khuyến nghị của hệ thống chỉ mang tính chất thông tin tham khảo, không có giá trị thay thế
              chỉ định chuyên môn của bác sĩ có chứng chỉ hành nghề theo Luật Khám bệnh 2023.
            </p>
          </div>

          <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
            <li>
              <strong>Minh bạch phiên bản & Nguồn y văn:</strong> Hệ thống công khai họ mô hình (DeepSeek),
              phiên bản thuật toán và trích dẫn trực tiếp nguồn y văn chuẩn hóa (Living Evidence, Dược thư
              quốc gia, PubMed).
            </li>
            <li>
              <strong>Cảnh báo chế độ suy giảm (Degraded Mode):</strong> Khi dịch vụ mô hình bên ngoài gián
              đoạn, hệ thống thông báo minh bạch cho người dùng về trạng thái vận hành dự phòng nội bộ.
            </li>
            <li>
              <strong>Luồng cấp cứu khẩn cấp (Emergency Fast-Path):</strong> Khi phát hiện triệu chứng nguy
              cấp, hệ thống bỏ qua bước phân tích chẩn đoán và hướng dẫn người dùng gọi ngay 115 hoặc đến
              cơ sở y tế gần nhất.
            </li>
          </ul>
        </div>
      </LegalSection>

      {/* 13. Cán bộ bảo vệ dữ liệu (DPO) */}
      <LegalSection
        id="contact-dpo"
        title="13. Cán bộ bảo vệ dữ liệu (DPO) & Cập nhật chính sách"
        badge="Thông tin liên hệ"
      >
        <p>
          Mọi thắc mắc, phản ánh hoặc yêu cầu hỗ trợ thực thi quyền riêng tư vui lòng liên hệ trực tiếp với
          Cán bộ bảo vệ dữ liệu của The Clara Care:
        </p>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 text-xs sm:text-sm">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Chủ thể vận hành:</span>
            <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Email DPO:</span>
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="font-bold text-[var(--text-brand)] hover:underline">
              {LEGAL_CONTACT_EMAIL}
            </a>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Hotline tuân thủ:</span>
            <a href={`tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`} className="font-bold text-[var(--text-primary)] hover:underline">
              {LEGAL_CONTACT_PHONE}
            </a>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span className="text-[var(--text-muted)]">Phiên bản chính sách hiện hành:</span>
            <span className="font-mono font-bold text-[var(--text-brand)]">{LEGAL_POLICY_VERSION} ({LEGAL_UPDATED_AT})</span>
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)] pt-1">
          Chính sách này có thể được điều chỉnh khi có sự thay đổi về quy định pháp luật hoặc kiến trúc
          công nghệ. Mọi thay đổi lớn sẽ được thông báo công khai trước khi có hiệu lực thi hành.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}

