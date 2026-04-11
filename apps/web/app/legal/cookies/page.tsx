import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách cookie | The Clara Care",
  description: "Mô tả cách The Clara Care dùng cookie cho xác thực phiên, bảo mật và trải nghiệm người dùng.",
};

const COOKIE_SECTIONS = [
  { id: "definition", label: "Cookie là gì" },
  { id: "essential", label: "Cookie bắt buộc" },
  { id: "functional", label: "Cookie chức năng" },
  { id: "purposes", label: "Mục đích sử dụng" },
  { id: "duration", label: "Thời hạn lưu trữ" },
  { id: "management", label: "Quản lý cookie" },
  { id: "impact", label: "Ảnh hưởng khi tắt cookie" },
  { id: "updates", label: "Cập nhật chính sách" },
] as const;

export default function CookiePolicyPage() {
  return (
    <LegalPageShell
      policyKey="cookies"
      title="Chính sách cookie"
      summary="The Clara Care sử dụng cookie chủ yếu cho xác thực phiên, bảo mật truy cập và duy trì trải nghiệm sử dụng ổn định giữa các lần truy cập."
      updatedAt={LEGAL_UPDATED_AT}
      sections={COOKIE_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Cookie xác thực và CSRF là lớp bảo mật cốt lõi của hệ thống.",
        "Không dùng cookie để bán dữ liệu cá nhân.",
        "Người dùng có thể quản lý cookie tại trình duyệt.",
      ]}
    >
      <LegalSection id="definition" title="1. Cookie là gì">
        <p>
          Cookie là dữ liệu nhỏ được trình duyệt lưu lại để nhận diện phiên truy cập, ghi nhớ trạng thái và hỗ trợ hoạt động bảo
          mật giữa các request.
        </p>
      </LegalSection>

      <LegalSection id="essential" title="2. Nhóm cookie bắt buộc cho hệ thống">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Cookie phiên truy cập: ví dụ <span className="font-mono">clara_access_token</span>,{" "}
            <span className="font-mono">clara_refresh_token</span> để xác thực và duy trì phiên đăng nhập.
          </li>
          <li>
            Cookie CSRF: ví dụ <span className="font-mono">clara_csrf_token</span> khi tính năng CSRF được bật để giảm rủi ro giả
            mạo request.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="functional" title="3. Cookie chức năng">
        <p>
          Hệ thống có thể sử dụng cookie chức năng để ghi nhớ một số tùy chọn trải nghiệm cơ bản trong quá trình sử dụng, tùy theo
          cấu hình triển khai từng môi trường.
        </p>
      </LegalSection>

      <LegalSection id="purposes" title="4. Mục đích sử dụng cookie">
        <ul className="list-disc space-y-2 pl-5">
          <li>Xác thực người dùng và duy trì phiên làm việc an toàn.</li>
          <li>Hỗ trợ cơ chế chống truy cập trái phép và chống giả mạo phiên.</li>
          <li>Giảm thao tác lặp lại và tăng tính liên tục khi điều hướng giữa các module.</li>
        </ul>
      </LegalSection>

      <LegalSection id="duration" title="5. Thời hạn lưu trữ cookie">
        <p>
          Một số cookie tồn tại trong phiên hiện tại, một số cookie có thể tồn tại dài hơn theo thời gian sống phiên xác thực đã
          cấu hình. Khi cookie hết hạn, người dùng có thể cần đăng nhập lại.
        </p>
      </LegalSection>

      <LegalSection id="management" title="6. Quản lý cookie">
        <p>
          Bạn có thể xem, xóa hoặc chặn cookie trong phần cài đặt trình duyệt. Mỗi trình duyệt có cách quản lý khác nhau, vui lòng
          tham khảo tài liệu chính thức của trình duyệt bạn đang dùng.
        </p>
      </LegalSection>

      <LegalSection id="impact" title="7. Ảnh hưởng khi vô hiệu hóa cookie">
        <p>
          Nếu tắt cookie bắt buộc, các chức năng đăng nhập, làm mới phiên hoặc bảo vệ CSRF có thể hoạt động không đúng thiết kế,
          làm gián đoạn trải nghiệm và có thể khiến một số module không thể truy cập.
        </p>
      </LegalSection>

      <LegalSection id="updates" title="8. Cập nhật chính sách cookie">
        <p>
          Chính sách cookie có thể được cập nhật khi thay đổi cơ chế xác thực, bảo mật hoặc yêu cầu tuân thủ. Bản mới nhất luôn
          được công bố tại Policy Hub của The Clara Care.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
