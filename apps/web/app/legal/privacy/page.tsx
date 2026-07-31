import LegalPageShell, {
  LegalSection,
} from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư | The Clara Care",
  description:
    "Mô tả cách The Clara Care thu thập, sử dụng, lưu trữ và bảo vệ dữ liệu người dùng.",
};

const PRIVACY_SECTIONS = [
  { id: "scope", label: "Phạm vi áp dụng" },
  { id: "user-admin-scope", label: "Phạm vi dữ liệu: người dùng và admin" },
  { id: "data-categories", label: "Danh mục dữ liệu" },
  { id: "processing-purpose", label: "Mục đích xử lý" },
  { id: "legal-basis", label: "Căn cứ xử lý" },
  { id: "retention", label: "Lưu trữ dữ liệu" },
  { id: "sharing", label: "Chia sẻ với bên thứ ba" },
  { id: "processors", label: "Danh sách bên xử lý dữ liệu" },
  { id: "security", label: "An toàn thông tin" },
  { id: "user-rights", label: "Quyền của người dùng" },
  { id: "dsar", label: "Cách thực hiện quyền (DSAR)" },
  { id: "cross-border", label: "Chuyển dữ liệu xuyên biên giới" },
  { id: "ai-transparency", label: "Minh bạch hệ thống AI (Luật 134/2025)" },
  { id: "contact", label: "Liên hệ & cập nhật" },
] as const;

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
      "Suy luận mô hình ngôn ngữ lớn / large language model inference (sinh câu trả lời)",
    jurisdiction: "Ngoài lãnh thổ Việt Nam (offshore / non-VN)",
    data: "Nội dung truy vấn đã tối thiểu hóa, loại trừ định danh trực tiếp khi khả thi; không lưu nội dung chuyển giao",
  },
  {
    name: "YEScale — điểm cuối embedding (tương thích OpenAI, api.yescale.io)",
    purpose:
      "Tạo vector embedding / embedding generation phục vụ truy xuất ngữ nghĩa",
    jurisdiction: "Ngoài lãnh thổ Việt Nam (offshore / non-VN)",
    data: "Đoạn văn bản cần lập chỉ mục/truy xuất, đã tối thiểu hóa; không lưu nội dung chuyển giao",
  },
  {
    name: "Hạ tầng lưu trữ và vận hành / hosting & operations",
    purpose: "Lưu trữ dữ liệu, vận hành dịch vụ, sao lưu",
    jurisdiction: "Theo cấu hình triển khai / per deployment configuration",
    data: "Dữ liệu tài khoản, dữ liệu người dùng và log vận hành",
  },
] as const;

export default function PrivacyPolicyPage() {
  return (
    <LegalPageShell
      policyKey="privacy"
      title="Chính sách quyền riêng tư"
      summary="Chính sách này mô tả cách The Clara Care quản trị dữ liệu cá nhân và dữ liệu vận hành, bao gồm phạm vi dữ liệu của người dùng cuối và tài khoản quản trị hệ thống."
      updatedAt={LEGAL_UPDATED_AT}
      sections={PRIVACY_SECTIONS.map((item) => ({
        id: item.id,
        label: item.label,
      }))}
      highlights={[
        "Thu thập tối thiểu theo mục tiêu nghiệp vụ rõ ràng.",
        "Ưu tiên khử định danh ở các luồng phân tích không cần nhận diện cá nhân.",
        "Mọi truy cập nhạy cảm đều ghi nhận audit trail.",
        "Người dùng có quyền yêu cầu xem/chỉnh sửa/xóa dữ liệu theo quy định.",
      ]}
    >
      <LegalSection id="scope" title="1. Phạm vi áp dụng">
        <p>
          Chính sách áp dụng cho toàn bộ dịch vụ The Clara Care, gồm giao diện
          web, API và các module như Research, Council, Self-Med, CareGuard,
          Scribe, bảng quản trị hệ thống và các thành phần tích hợp liên quan.
        </p>
        <p>
          Chính sách này được áp dụng cho cả tài khoản cá nhân, tài khoản tổ
          chức và tài khoản quản trị khi truy cập các tài nguyên thuộc hệ thống.
        </p>
      </LegalSection>

      <LegalSection
        id="user-admin-scope"
        title="2. Phạm vi dữ liệu: người dùng và admin"
      >
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-bold">Người dùng cuối:</span> dữ liệu tài
            khoản, truy vấn, tài liệu tải lên, dữ liệu thuốc, bản ghi hội thoại
            và dữ liệu đồng thuận.
          </li>
          <li>
            <span className="font-bold">Quản trị viên (admin):</span> dữ liệu
            cấu hình hệ thống, nhật ký thao tác quản trị, bản ghi audit và dữ
            liệu giám sát vận hành.
          </li>
          <li>
            <span className="font-bold">Nguyên tắc tách biệt:</span> dữ liệu
            người dùng và dữ liệu vận hành quản trị được tách quyền truy cập
            theo vai trò, chỉ mở khi có nhu cầu hợp lệ phục vụ vận hành, hỗ trợ
            hoặc tuân thủ pháp luật.
          </li>
        </ul>
      </LegalSection>

      <LegalSection
        id="data-categories"
        title="3. Danh mục dữ liệu được thu thập"
      >
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Dữ liệu tài khoản: họ tên, email, vai trò, trạng thái xác thực,
            thông tin phiên đăng nhập.
          </li>
          <li>
            Dữ liệu vận hành: log request/response, tín hiệu lỗi, timestamp, chỉ
            số chất lượng và hiệu năng.
          </li>
          <li>
            Dữ liệu người dùng cung cấp: truy vấn, tài liệu tải lên, thông tin
            thuốc, nội dung ghi chú, bản tóm tắt lâm sàng.
          </li>
          <li>
            Dữ liệu đồng thuận: phiên bản consent, thời điểm chấp thuận, user
            context dùng cho kiểm chứng pháp lý.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="processing-purpose" title="4. Mục đích xử lý dữ liệu">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Cung cấp chức năng cốt lõi của sản phẩm và duy trì trải nghiệm sử
            dụng ổn định.
          </li>
          <li>
            Nâng cao chất lượng suy luận, truy xuất bằng chứng và khả năng kiểm
            chứng câu trả lời.
          </li>
          <li>
            Phát hiện, điều tra, ngăn chặn hành vi bất thường hoặc truy cập trái
            phép.
          </li>
          <li>
            Đáp ứng nghĩa vụ tuân thủ pháp luật, yêu cầu kiểm toán và quy trình
            quản trị nội bộ.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="legal-basis" title="5. Căn cứ xử lý dữ liệu">
        <p>
          The Clara Care xử lý dữ liệu dựa trên: (i) sự đồng ý của người dùng
          đối với các tính năng nhạy cảm; (ii) nhu cầu thực hiện hợp đồng/dịch
          vụ; (iii) nghĩa vụ pháp lý hợp lệ; và (iv) lợi ích chính đáng về an
          toàn vận hành hệ thống.
        </p>
        <p>
          Các căn cứ này được diễn giải theo quy định pháp luật Việt Nam hiện
          hành, bao gồm Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân, Luật
          An toàn thông tin mạng 2015 và Luật An ninh mạng 2018.
        </p>
      </LegalSection>

      <LegalSection id="retention" title="6. Chính sách lưu trữ và xóa dữ liệu">
        <p>
          Dữ liệu được lưu trong thời gian cần thiết để phục vụ mục đích nêu
          trên, hoặc theo yêu cầu pháp lý hiện hành. Sau khi hết thời gian lưu
          trữ, dữ liệu sẽ được xóa hoặc ẩn danh hóa theo quy trình kỹ thuật.
        </p>
        <p>
          Với log vận hành và audit trail, hệ thống có thể lưu dài hơn để phục
          vụ điều tra sự cố, truy vết và đối chiếu tuân thủ.
        </p>
      </LegalSection>

      <LegalSection id="sharing" title="7. Chia sẻ dữ liệu với bên thứ ba">
        <p>
          Hệ thống chỉ chia sẻ dữ liệu trong phạm vi cần thiết cho vận hành, ví
          dụ đối tác hạ tầng, dịch vụ xử lý hỗ trợ hoặc khi có yêu cầu pháp lý
          hợp lệ từ cơ quan có thẩm quyền.
        </p>
        <p>The Clara Care không bán dữ liệu cá nhân cho bên thứ ba.</p>
      </LegalSection>

      <LegalSection
        id="processors"
        title="8. Danh sách bên xử lý dữ liệu và quyền tài phán"
      >
        <p>
          Theo Điều 25–27 Nghị định 13/2023/NĐ-CP, dưới đây là danh sách các bên
          xử lý dữ liệu (data processor) có thể nhận dữ liệu cá nhân, bao gồm
          các bên xử lý đặt ngoài lãnh thổ Việt Nam phục vụ suy luận mô hình AI
          và truy xuất ngữ nghĩa. Mỗi bên đều có đánh giá tác động chuyển dữ
          liệu (TIA) tương ứng được lưu trong hồ sơ tuân thủ.
        </p>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-primary)]">
                <th className="py-2 pr-3 font-bold">Bên xử lý</th>
                <th className="py-2 pr-3 font-bold">Mục đích</th>
                <th className="py-2 pr-3 font-bold">Quyền tài phán</th>
                <th className="py-2 font-bold">Dữ liệu chuyển giao</th>
              </tr>
            </thead>
            <tbody>
              {THIRD_PARTY_PROCESSORS.map((processor) => (
                <tr
                  key={processor.name}
                  className="border-b border-[color:var(--shell-border)] align-top"
                >
                  <td className="py-2 pr-3 font-semibold text-[var(--text-primary)]">
                    {processor.name}
                  </td>
                  <td className="py-2 pr-3">{processor.purpose}</td>
                  <td className="py-2 pr-3">{processor.jurisdiction}</td>
                  <td className="py-2">{processor.data}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </LegalSection>

      <LegalSection id="security" title="9. Biện pháp an toàn thông tin">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Kiểm soát truy cập theo vai trò, nguyên tắc tối thiểu quyền hạn và
            phân tách môi trường vận hành.
          </li>
          <li>
            Giám sát bảo mật liên tục, cảnh báo bất thường và quy trình phản ứng
            sự cố theo mức độ ưu tiên.
          </li>
          <li>
            Ghi nhận nhật ký truy cập nhạy cảm để phục vụ truy vết, kiểm tra và
            hậu kiểm.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="user-rights" title="10. Quyền của chủ thể dữ liệu">
        <p>
          Theo Điều 9 và Điều 14–16 Nghị định 13/2023/NĐ-CP, chủ thể dữ liệu có
          các quyền: truy cập, chỉnh sửa, xóa, hạn chế xử lý, yêu cầu cung cấp
          (xuất) dữ liệu và rút lại đồng thuận. The Clara Care có thể cần xác
          minh danh tính trước khi xử lý các yêu cầu này nhằm đảm bảo an toàn
          thông tin.
        </p>
      </LegalSection>

      <LegalSection
        id="dsar"
        title="11. Cách thực hiện quyền của chủ thể dữ liệu (DSAR)"
      >
        <p>
          Người dùng đã đăng nhập có thể tự thực hiện các quyền dữ liệu của mình
          qua trang{" "}
          <span className="font-bold text-[var(--text-brand)]">
            Dữ liệu của tôi
          </span>{" "}
          (<span className="font-mono">/account/data</span>), bao gồm: xuất dữ
          liệu dưới định dạng máy đọc được, yêu cầu chỉnh sửa, hạn chế xử lý,
          rút đồng thuận và xóa/ẩn danh hóa dữ liệu.
        </p>
        <p>
          Việc cấp và rút đồng thuận theo từng mục đích được quản lý tại{" "}
          <span className="font-bold text-[var(--text-brand)]">
            Trung tâm đồng thuận
          </span>{" "}
          (<span className="font-mono">/account/consent</span>). Mỗi yêu cầu
          được ghi nhận và theo dõi theo thời hạn xử lý luật định; nhật ký DSAR
          chỉ lưu loại yêu cầu, thời điểm và trạng thái, không lưu thêm dữ liệu
          định danh.
        </p>
        <p>
          Khi yêu cầu xóa được hoàn tất, dữ liệu cá nhân của bạn sẽ được xóa
          hoặc ẩn danh hóa không thể khôi phục, trong khi các bản ghi audit/tuân
          thủ (không chứa dữ liệu định danh) được giữ lại theo nghĩa vụ pháp lý.
        </p>
      </LegalSection>

      <LegalSection
        id="cross-border"
        title="12. Chuyển dữ liệu xuyên biên giới"
      >
        <p>
          Một số chức năng (suy luận mô hình ngôn ngữ, tạo embedding) cần chuyển
          dữ liệu tới bên xử lý đặt ngoài lãnh thổ Việt Nam — xem danh sách tại
          mục “Danh sách bên xử lý dữ liệu”. Việc chuyển dữ liệu xuyên biên giới
          chỉ được thực hiện khi có đồng thuận “Xử lý bởi mô hình bên thứ ba /
          xuyên biên giới” của bạn.
        </p>
        <p>
          Khi đồng thuận này vắng mặt, hệ thống không gửi dữ liệu nhạy cảm có
          khả năng định danh ra bên xử lý ngoài lãnh thổ: thay vào đó sử dụng
          đường xử lý nội địa nếu có, hoặc trả lời dự phòng nội bộ (được gắn
          nhãn suy giảm). Mọi yêu cầu chuyển ra ngoài đều được tối thiểu hóa dữ
          liệu và ghi nhận sự kiện không chứa dữ liệu định danh.
        </p>
      </LegalSection>

      <LegalSection
        id="ai-transparency"
        title="13. Minh bạch hệ thống AI (Luật 134/2025/QH15)"
      >
        <p>
          The Clara Care là một hệ thống trí tuệ nhân tạo hỗ trợ thông tin y tế.
          Theo Luật Trí tuệ nhân tạo số 134/2025/QH15 (có hiệu lực từ
          01/03/2026), CLARA được phân loại là{" "}
          <span className="font-bold">hệ thống AI rủi ro cao</span> trong lĩnh
          vực y tế và luôn duy trì sự giám sát của con người.
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            CLARA cung cấp thông tin tham khảo và hỗ trợ ra quyết định; CLARA
            không kê đơn, không đưa ra chẩn đoán xác định và không thay thế bác
            sĩ hoặc nhân viên y tế có giấy phép.
          </li>
          <li>
            Mỗi câu trả lời đều kèm chỉ dẫn tham vấn chuyên môn y tế; các nội
            dung khẩn cấp được chuyển hướng tới dịch vụ cấp cứu mà không suy
            luận chẩn đoán.
          </li>
          <li>
            Hệ thống công bố họ mô hình và phiên bản mô hình được dùng để tạo
            câu trả lời; khi câu trả lời đến từ đường dự phòng nội bộ, hệ thống
            gắn nhãn rõ là phản hồi suy giảm/dự phòng.
          </li>
          <li>
            Thông báo minh bạch về hệ thống AI được phiên bản hóa; khi có phiên
            bản mới, bạn được yêu cầu xác nhận lại trước khi tiếp tục sử dụng
            nội dung y tế.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="contact" title="14. Liên hệ và cập nhật chính sách">
        <p>
          Mọi yêu cầu liên quan quyền riêng tư hoặc dữ liệu cá nhân vui lòng gửi
          về{" "}
          <a
            className="font-bold text-[var(--text-brand)] hover:underline"
            href={`mailto:${LEGAL_CONTACT_EMAIL}`}
          >
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
        <p>
          Chính sách có thể được cập nhật theo thay đổi pháp lý hoặc thay đổi
          kiến trúc hệ thống. Phiên bản mới nhất luôn được công bố tại mục Thỏa
          thuận người dùng của The Clara Care.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
