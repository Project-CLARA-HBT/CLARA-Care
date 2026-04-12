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
  title: "Thỏa thuận người dùng | The Clara Care",
  description:
    "Thỏa thuận người dùng áp dụng khi truy cập website, ứng dụng và dịch vụ The Clara Care.",
};

const SECTIONS = [
  { id: "intro", label: "Lời mở đầu" },
  { id: "legal-basis", label: "Căn cứ pháp lý áp dụng" },
  { id: "definitions", label: "Điều 1: Giải thích từ ngữ" },
  { id: "prohibited", label: "Điều 2: Hành vi bị cấm" },
  { id: "customer-rights", label: "Điều 3: Quyền & nghĩa vụ khách hàng" },
  { id: "provider-rights", label: "Điều 4: Quyền & trách nhiệm nhà cung cấp" },
  { id: "payment", label: "Điều 5: Thanh toán" },
  { id: "renewal", label: "Điều 6: Gia hạn dịch vụ" },
  { id: "suspension", label: "Điều 7: Tạm ngưng/chấm dứt" },
  { id: "update-info", label: "Điều 8: Điều chỉnh thông tin" },
  { id: "support", label: "Điều 9: Hỗ trợ khách hàng" },
  { id: "liability", label: "Điều 10: Giới hạn trách nhiệm" },
  { id: "privacy-link", label: "Điều 11: Bảo mật thông tin" },
  { id: "free-services", label: "Điều 12: Dịch vụ miễn phí" },
  { id: "refund", label: "Điều 13: Hoàn tiền" },
  { id: "reservation", label: "Điều 14: Bảo lưu dịch vụ" },
  { id: "final-terms", label: "Điều khoản cuối" },
  { id: "entity-info", label: "Thông tin chủ thể" },
] as const;

export default function TermsOfServicePage() {
  return (
    <LegalPageShell
      policyKey="terms"
      title="Thỏa thuận người dùng"
      summary="Văn bản này quy định quyền, nghĩa vụ và phạm vi sử dụng dịch vụ The Clara Care cho người dùng cá nhân, tổ chức và quản trị viên khi truy cập website, API và các module chuyên môn."
      updatedAt={LEGAL_UPDATED_AT}
      sections={SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        `Domain chính thức: ${LEGAL_PRIMARY_DOMAIN}`,
        `Chủ thể vận hành: ${LEGAL_OPERATOR_NAME}`,
        `Phiên bản điều khoản: ${LEGAL_POLICY_VERSION}`,
        "Văn bản được rà soát theo quy định pháp luật Việt Nam đang có hiệu lực tại thời điểm ban hành.",
        "Mọi hoạt động dùng dịch vụ đồng nghĩa bạn đã đọc và chấp thuận điều khoản hiện hành.",
      ]}
    >
      <LegalSection id="intro" title="Lời mở đầu">
        <p>
          Chào mừng bạn đến với The Clara Care. Vui lòng đọc kỹ thoả thuận này trước khi đăng ký hoặc sử dụng dịch vụ vì nội dung
          liên quan trực tiếp đến quyền, nghĩa vụ và giới hạn trách nhiệm của các bên trong suốt vòng đời sử dụng dịch vụ.
        </p>
        <p>
          Việc bạn tiếp tục truy cập website, ứng dụng hoặc API của The Clara Care được hiểu là bạn đã đồng ý với toàn bộ điều
          khoản trong văn bản này.
        </p>
      </LegalSection>

      <LegalSection id="legal-basis" title="Căn cứ pháp lý áp dụng">
        <p>
          Thỏa thuận này được xây dựng theo các nguyên tắc tuân thủ pháp luật Việt Nam, bao gồm nhưng không giới hạn ở:
          Bộ luật Dân sự năm 2015, Luật Giao dịch điện tử năm 2023, Luật An toàn thông tin mạng năm 2015,
          Luật An ninh mạng năm 2018 và Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.
        </p>
        <p>
          Trong trường hợp quy định pháp luật thay đổi, The Clara Care có quyền cập nhật nội dung để bảo đảm tính phù hợp
          và công bố phiên bản mới tại mục Thỏa thuận người dùng.
        </p>
      </LegalSection>

      <LegalSection id="definitions" title="Điều 1: Giải thích từ ngữ">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-bold">The Clara Care / Chúng tôi:</span> Hệ sinh thái sản phẩm số do chủ thể vận hành hợp pháp
            triển khai và quản trị.
          </li>
          <li>
            <span className="font-bold">Bạn / Khách hàng:</span> Cá nhân hoặc tổ chức truy cập website và/hoặc sử dụng dịch vụ do
            The Clara Care cung cấp.
          </li>
          <li>
            <span className="font-bold">Dịch vụ:</span> Tất cả sản phẩm, tính năng, API và công cụ hiển thị công khai trên website
            và hệ quản trị của The Clara Care.
          </li>
          <li>
            <span className="font-bold">Không gian quản trị:</span> Khu vực quản trị dịch vụ cho phép bạn quản lý tài nguyên, cấu hình,
            trạng thái vận hành và thông tin tài khoản theo quyền được cấp.
          </li>
          <li>
            <span className="font-bold">Admin:</span> Quyền quản trị cao nhất của một hệ thống hoặc phân hệ kỹ thuật.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="prohibited" title="Điều 2: Các hành vi bị cấm">
        <ul className="list-disc space-y-2 pl-5">
          <li>Sử dụng dịch vụ cho mục đích vi phạm pháp luật Việt Nam, điều ước quốc tế hoặc chuẩn mực đạo đức xã hội.</li>
          <li>
            Lưu trữ/phát tán nội dung bất hợp pháp, xuyên tạc, kích động bạo lực, nội dung bị cấm, nội dung xâm phạm quyền hợp
            pháp của tổ chức/cá nhân khác.
          </li>
          <li>Tải lên mã độc, virus, script phá hoại hoặc công cụ gây gián đoạn dịch vụ, hạ tầng, mạng và dữ liệu.</li>
          <li>Giả mạo tổ chức, cá nhân hoặc nhân sự của The Clara Care để lừa đảo, trục lợi hoặc phát tán thông tin sai sự thật.</li>
          <li>Khai thác tài nguyên vượt ngưỡng cho phép hoặc cố ý gây suy giảm chất lượng cho người dùng khác.</li>
          <li>Thực hiện hành vi spam, lạm dụng email/tin nhắn/cuộc gọi trái quy định pháp luật hiện hành.</li>
          <li>Vi phạm quyền sở hữu trí tuệ, bản quyền phần mềm, nhãn hiệu hoặc bí mật kinh doanh.</li>
        </ul>
      </LegalSection>

      <LegalSection id="customer-rights" title="Điều 3: Quyền và nghĩa vụ của khách hàng">
        <ul className="list-disc space-y-2 pl-5">
          <li>Bạn phải có năng lực pháp lý phù hợp và chịu trách nhiệm về tính trung thực của thông tin đăng ký.</li>
          <li>Bạn phải chủ động cập nhật thông tin khi thay đổi; quá hạn cập nhật có thể bị tạm ngưng dịch vụ.</li>
          <li>Bạn tự quản lý mật khẩu, token, mã xác thực và chịu trách nhiệm mọi hoạt động trên tài khoản của mình.</li>
          <li>
            Bạn phải tự sao lưu dữ liệu quan trọng định kỳ; bản sao lưu hệ thống chủ yếu phục vụ mục tiêu khôi phục sự cố hạ tầng.
          </li>
          <li>Bạn chịu trách nhiệm nội dung lưu trữ, xử lý và truyền tải thông qua tài nguyên đã đăng ký.</li>
          <li>
            Bạn đồng ý nhận các thông báo cần thiết về vận hành như bảo trì, cảnh báo bảo mật, gia hạn, thay đổi điều khoản và
            thông báo khẩn.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="provider-rights" title="Điều 4: Quyền và trách nhiệm của nhà cung cấp">
        <ul className="list-disc space-y-2 pl-5">
          <li>Hỗ trợ kỹ thuật trong phạm vi dịch vụ và quyền hạn vận hành hợp pháp của The Clara Care.</li>
          <li>Tiếp nhận và xử lý khiếu nại theo quy trình nội bộ khi khách hàng cung cấp đủ thông tin xác thực.</li>
          <li>Có quyền yêu cầu khách hàng phối hợp xác minh thông tin khi phát hiện dấu hiệu bất thường hoặc giả mạo.</li>
          <li>
            Có quyền tạm ngưng/chấm dứt dịch vụ và/hoặc chuyển hồ sơ đến cơ quan có thẩm quyền nếu phát hiện vi phạm nghiêm trọng.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="payment" title="Điều 5: Quy định thanh toán">
        <ul className="list-disc space-y-2 pl-5">
          <li>Phí dịch vụ được công bố theo từng gói, từng chu kỳ và có thể bao gồm thuế/phí theo quy định.</li>
          <li>Hoá đơn điện tử được phát hành sau khi thanh toán hợp lệ và dịch vụ kích hoạt thành công.</li>
          <li>Thông tin hoá đơn phải thống nhất với chủ thể sở hữu dịch vụ theo hồ sơ đã xác minh.</li>
        </ul>
      </LegalSection>

      <LegalSection id="renewal" title="Điều 6: Gia hạn dịch vụ">
        <ul className="list-disc space-y-2 pl-5">
          <li>Bạn cần chủ động theo dõi hạn dùng và gia hạn trước ngày hết hạn để tránh gián đoạn dịch vụ.</li>
          <li>Gia hạn chỉ có hiệu lực khi hệ thống ghi nhận thanh toán thành công.</li>
          <li>Tính năng auto-renew là công cụ hỗ trợ, không thay thế trách nhiệm chủ động quản trị dịch vụ của khách hàng.</li>
        </ul>
      </LegalSection>

      <LegalSection id="suspension" title="Điều 7: Tạm ngưng và chấm dứt sử dụng dịch vụ">
        <ul className="list-disc space-y-2 pl-5">
          <li>Dịch vụ có thể tạm ngưng/chấm dứt khi hết hạn, vi phạm điều khoản hoặc theo yêu cầu cơ quan có thẩm quyền.</li>
          <li>Khách hàng phải tự di chuyển dữ liệu trước khi chấm dứt; dữ liệu có thể bị xoá sau thời hạn lưu giữ hệ thống.</li>
          <li>Với dịch vụ trial/free, tài nguyên có thể bị thu hồi ngay khi kết thúc thời gian dùng thử.</li>
        </ul>
      </LegalSection>

      <LegalSection id="update-info" title="Điều 8: Bổ sung, điều chỉnh thông tin khách hàng">
        <p>
          Khách hàng có quyền yêu cầu cập nhật thông tin chủ thể, thông số dịch vụ hoặc dữ liệu hồ sơ sai lệch. Các yêu cầu hợp lệ
          được xử lý theo SLA vận hành. Một số nghiệp vụ có thể phát sinh chi phí xử lý theo chính sách tại thời điểm yêu cầu.
        </p>
      </LegalSection>

      <LegalSection id="support" title="Điều 9: Hỗ trợ khách hàng">
        <ul className="list-disc space-y-2 pl-5">
          <li>Hỗ trợ tập trung cho chủ thể sở hữu dịch vụ hoặc người được uỷ quyền hợp lệ.</li>
          <li>Khách hàng cần sao lưu dữ liệu trước khi yêu cầu thao tác kỹ thuật chuyên sâu.</li>
          <li>
            Trong trường hợp cần hỗ trợ từ xa qua công cụ điều khiển, khách hàng tự chịu trách nhiệm bảo mật dữ liệu ngoài phạm vi
            thao tác dịch vụ đã yêu cầu.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="liability" title="Điều 10: Giới hạn trách nhiệm và từ chối bảo đảm">
        <ul className="list-disc space-y-2 pl-5">
          <li>The Clara Care không chịu trách nhiệm cho thiết bị đầu cuối và môi trường truy cập của khách hàng.</li>
          <li>Không bảo đảm dịch vụ không có lỗi tuyệt đối trong mọi thời điểm hoặc mọi điều kiện mạng.</li>
          <li>
            Không chịu trách nhiệm cho thiệt hại phát sinh do hành vi truy cập trái phép, mã độc, lạm dụng tài khoản hoặc lỗi do bên
            thứ ba nằm ngoài khả năng kiểm soát hợp lý.
          </li>
          <li>
            Dịch vụ AI chỉ mang tính hỗ trợ tham khảo; mọi quyết định nghiệp vụ và lâm sàng thuộc trách nhiệm của người dùng có thẩm
            quyền.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="privacy-link" title="Điều 11: Bảo mật thông tin khách hàng">
        <p>
          The Clara Care quản trị dữ liệu theo nguyên tắc tối thiểu, mục đích rõ ràng và kiểm soát truy cập theo vai trò. Chi tiết
          cách thu thập, xử lý và lưu giữ dữ liệu được công bố riêng tại Chính sách quyền riêng tư.
        </p>
      </LegalSection>

      <LegalSection id="free-services" title="Điều 12: Dịch vụ miễn phí">
        <p>
          The Clara Care có thể cung cấp một số gói miễn phí hoặc ưu đãi dùng thử theo từng thời điểm. Phạm vi tính năng, hạn mức
          tài nguyên và thời hạn sử dụng có thể thay đổi theo chính sách vận hành mà không cần báo trước riêng lẻ cho từng người
          dùng.
        </p>
      </LegalSection>

      <LegalSection id="refund" title="Điều 13: Chính sách hoàn tiền">
        <p>
          Chính sách hoàn tiền áp dụng theo từng loại dịch vụ, từng chu kỳ và tình trạng kích hoạt thực tế. Giá trị hoàn có thể bị
          khấu trừ phần thời gian đã sử dụng, chi phí phát sinh, thuế/phí và phí chuyển khoản ngân hàng (nếu có).
        </p>
        <p>
          Các trường hợp vượt thời hạn hoàn tiền cam kết sẽ xử lý theo điều khoản chất lượng dịch vụ tương ứng tại thời điểm yêu
          cầu.
        </p>
      </LegalSection>

      <LegalSection id="reservation" title="Điều 14: Chính sách bảo lưu thời gian dịch vụ">
        <p>
          Trong một số gói dịch vụ đủ điều kiện, khách hàng có thể yêu cầu bảo lưu thời gian chưa sử dụng để tránh lãng phí tài
          nguyên. Chính sách bảo lưu chỉ áp dụng một số dịch vụ chính và có điều kiện cụ thể theo quy định vận hành hiện hành.
        </p>
      </LegalSection>

      <LegalSection id="final-terms" title="Điều khoản cuối">
        <p>
          Chúng tôi có quyền điều chỉnh, cập nhật, bổ sung hoặc loại bỏ một phần/toàn bộ điều khoản để phù hợp thực tiễn vận hành và
          yêu cầu pháp luật. Bản cập nhật được công bố công khai trên website và có hiệu lực từ thời điểm công bố.
        </p>
        <p>
          Nếu một điều khoản bị tuyên vô hiệu bởi cơ quan có thẩm quyền, các điều khoản còn lại vẫn giữ nguyên hiệu lực. Mọi tranh
          chấp phát sinh được ưu tiên giải quyết bằng thương lượng; nếu không thành, sẽ xử lý theo pháp luật Việt Nam.
        </p>
      </LegalSection>

      <LegalSection id="entity-info" title="Thông tin chủ thể vận hành">
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
