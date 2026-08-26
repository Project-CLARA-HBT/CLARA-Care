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
import { CookieManagerControl } from "./cookie-manager";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách cookie & Quản lý phiên làm việc | The Clara Care",
  description:
    "Mô tả chi tiết cách The Clara Care sử dụng cookie thiết yếu, token bảo mật (CSRF, X-Session) và tùy chọn giao diện; cam kết 100% không theo dõi quảng cáo bên thứ ba theo Nghị định 13/2023/NĐ-CP.",
};

const COOKIE_SECTIONS: LegalSectionMeta[] = [
  { id: "definition", label: "Cookie là gì", title: "1. Cookie là gì & Nguyên tắc áp dụng" },
  { id: "categories", label: "Nhóm cookie sử dụng", title: "2. Nhóm cookie sử dụng (Các nhóm cookie được sử dụng)" },
  { id: "essential-session", label: "Cookie phiên thiết yếu", title: "3. Cookie phiên làm việc thiết yếu (Essential Session)" },
  { id: "security-tokens", label: "Token bảo mật & CSRF", title: "4. Token bảo mật & Phòng chống tấn công (Security Tokens)" },
  { id: "preferences", label: "Tùy chọn giao diện", title: "5. Cookie lưu tùy chọn giao diện (Preferences)" },
  { id: "zero-tracking", label: "Cam kết không theo dõi", title: "6. Cam kết Zero Third-Party Tracking & Zero Profiling" },
  { id: "purposes", label: "Mục đích sử dụng", title: "7. Mục đích sử dụng cookie" },
  { id: "storage-duration", label: "Thời hạn lưu", title: "8. Thời hạn lưu trữ cookie" },
  { id: "management", label: "Quản lý cookie", title: "9. Cơ chế & Công cụ quản lý cookie" },
  { id: "impact", label: "Ảnh hưởng khi tắt", title: "10. Ảnh hưởng khi tắt cookie" },
  { id: "updates", label: "Cập nhật chính sách", title: "11. Cập nhật chính sách & Liên hệ DPO" },
];

export default function CookiePolicyPage() {
  return (
    <LegalPageShell
      policyKey="cookies"
      title="Chính sách cookie"
      summary="The Clara Care chỉ sử dụng cookie và các công nghệ lưu trữ cục bộ cần thiết để duy trì phiên đăng nhập an toàn, bảo vệ chống tấn công CSRF/chiếm quyền phiên, và ghi nhớ tùy chọn giao diện. Hệ thống cam kết tuyệt đối KHÔNG sử dụng cookie quảng cáo của bên thứ ba hoặc xây dựng hồ sơ hành vi người dùng."
      updatedAt={LEGAL_UPDATED_AT}
      version={LEGAL_POLICY_VERSION}
      sections={COOKIE_SECTIONS}
      highlights={[
        "Không dùng cookie để bán dữ liệu cá nhân hay lập hồ sơ hành vi.",
        "Ưu tiên cookie cần thiết cho bảo mật, chống CSRF và xác thực phiên.",
        "Zero cookie bên thứ ba (không Google Ads, Meta Pixel, hay data broker).",
        "Người dùng có thể chủ động kiểm tra và quản lý cookie tại trình duyệt.",
      ]}
      relatedControls={[
        {
          href: "/legal/privacy",
          label: "Chính sách quyền riêng tư",
          description: "Bảo vệ dữ liệu y tế nhạy cảm & DSAR",
        },
        {
          href: "/legal/consent",
          label: "Đồng thuận y tế",
          description: "Ranh giới lâm sàng & quyền rút đồng thuận",
        },
        {
          href: "/safety",
          label: "Tuyên ngôn an toàn lâm sàng",
          description: "Chuẩn Zero-CoT và hàng rào FIDES",
        },
        {
          href: "/legal",
          label: "Trung tâm pháp lý",
          description: "Mục lục chính sách chính thức của hệ thống",
        },
      ]}
    >
      {/* 1. Cookie là gì */}
      <LegalSection id="definition" title="1. Cookie là gì" badge="Khái niệm cơ bản">
        <p>
          Cookie là tệp dữ liệu nhỏ được máy chủ gửi đến trình duyệt của bạn khi bạn truy cập dịch vụ
          <strong> The Clara Care</strong> (domain: <code className="text-xs font-mono font-bold text-[var(--text-brand)]">{LEGAL_PRIMARY_DOMAIN}</code>).
          Trình duyệt sẽ lưu trữ các tệp này để nhận diện phiên truy cập, ghi nhớ trạng thái đăng nhập,
          bảo vệ luồng trao đổi dữ liệu y tế và duy trì các cài đặt giao diện giữa các phiên làm việc.
        </p>
        <p>
          Bên cạnh cookie HTTP tiêu chuẩn, The Clara Care còn sử dụng các cơ chế lưu trữ trình duyệt an toàn
          như <code>localStorage</code> và <code>sessionStorage</code> để lưu trữ tạm thời các tùy chọn hiển thị
          phi cá nhân hóa mà không gửi kèm vào mỗi yêu cầu mạng.
        </p>
      </LegalSection>

      {/* 2. Nhóm cookie sử dụng */}
      <LegalSection id="categories" title="2. Nhóm cookie sử dụng (Các nhóm cookie được sử dụng)" badge="Phân loại chính thức">
        <p>The Clara Care phân loại và kiểm soát nghiêm ngặt các nhóm cookie theo 3 mục đích vận hành duy nhất:</p>
        <div className="grid gap-3 pt-1 sm:grid-cols-3">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-1.5">
            <span className="text-xs font-black uppercase tracking-wider text-[var(--text-brand)]">1. Thiết yếu (Essential)</span>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Xác thực phiên, duy trì tính liên tục của tài khoản, chống truy cập trái phép và bảo đảm chức năng bảo mật cốt lõi.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-1.5">
            <span className="text-xs font-black uppercase tracking-wider text-[var(--status-ok-text)]">2. Bảo mật (Security)</span>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Chống tấn công CSRF, ngăn ngừa giả mạo phiên làm việc, chống tấn công replay và bảo vệ các giao dịch dữ liệu lâm sàng.
            </p>
          </div>
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-1.5">
            <span className="text-xs font-black uppercase tracking-wider text-amber-500">3. Tùy chọn (Preferences)</span>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Ghi nhớ cấu hình hiển thị cá nhân như chế độ Dark/Light mode, ngôn ngữ Tiếng Việt/Tiếng Anh và giảm chuyển động (A11y).
            </p>
          </div>
        </div>
      </LegalSection>

      {/* 3. Cookie phiên thiết yếu */}
      <LegalSection
        id="essential-session"
        title="3. Cookie phiên làm việc thiết yếu (Essential Session Cookies)"
        badge="Bắt buộc vận hành"
      >
        <p>
          Đây là các cookie bắt buộc để nền tảng có thể vận hành và nhận diện phiên làm việc an toàn của bạn.
          Các cookie này được gắn cờ bảo mật cao nhất: <code>HttpOnly</code> (ngăn truy cập từ JavaScript độc hại),
          <code>Secure</code> (chỉ truyền qua kênh HTTPS mã hóa TLS 1.3) và <code>SameSite=Strict/Lax</code>.
        </p>
        <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[var(--surface-muted)] text-[var(--text-primary)] font-bold border-b border-[color:var(--shell-border)]">
              <tr>
                <th className="p-3">Tên Cookie</th>
                <th className="p-3">Mục đích kỹ thuật</th>
                <th className="p-3">Thuộc tính bảo vệ</th>
                <th className="p-3">Thời hạn lưu trữ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)] text-[var(--text-secondary)]">
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-brand)]">clara_access_token</td>
                <td className="p-3">JWT xác thực phiên người dùng, cấp quyền gọi API cổng dịch vụ y tế.</td>
                <td className="p-3 font-mono text-[11px]">HttpOnly, Secure, SameSite=Strict</td>
                <td className="p-3">15 - 60 phút (xoay vòng liên tục)</td>
              </tr>
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-brand)]">clara_refresh_token</td>
                <td className="p-3">Cấp mới access token an toàn mà không cần đăng nhập lại thủ công.</td>
                <td className="p-3 font-mono text-[11px]">HttpOnly, Secure, SameSite=Strict</td>
                <td className="p-3">7 đến 30 ngày</td>
              </tr>
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-brand)]">clara_client_session</td>
                <td className="p-3">Dấu hiệu phiên phía trình duyệt hỗ trợ định tuyến Edge trước hydration.</td>
                <td className="p-3 font-mono text-[11px]">Secure, SameSite=Lax</td>
                <td className="p-3">30 ngày</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 4. Token bảo mật & CSRF */}
      <LegalSection
        id="security-tokens"
        title="4. Token bảo mật & Phòng chống tấn công (Security Tokens)"
        badge="An ninh dữ liệu"
      >
        <p>
          Để đáp ứng tiêu chuẩn an toàn thông tin y tế theo Nghị định 13/2023/NĐ-CP và Luật An toàn thông tin mạng,
          hệ thống triển khai các token phòng thủ chủ động:
        </p>
        <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[var(--surface-muted)] text-[var(--text-primary)] font-bold border-b border-[color:var(--shell-border)]">
              <tr>
                <th className="p-3">Tên Token / Cơ chế</th>
                <th className="p-3">Chức năng phòng vệ</th>
                <th className="p-3">Thuộc tính bảo mật</th>
                <th className="p-3">Thời hạn</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)] text-[var(--text-secondary)]">
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-brand)]">clara_csrf_token</td>
                <td className="p-3">Phòng chống tấn công Cross-Site Request Forgery cho mọi mutation có trạng thái (cập nhật thuốc, xóa hồ sơ).</td>
                <td className="p-3 font-mono text-[11px]">SameSite=Strict, Secure</td>
                <td className="p-3">Theo phiên làm việc (Session)</td>
              </tr>
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-brand)]">X-Session-ID / clara_sec_nonce</td>
                <td className="p-3">Mã ngẫu nhiên định danh phiên kết nối, ngăn chặn tấn công phát lại (Replay Attacks) và chiếm quyền phiên.</td>
                <td className="p-3 font-mono text-[11px]">Cryptographic Nonce (CSPRNG)</td>
                <td className="p-3">Thời gian thực</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 5. Tùy chọn giao diện */}
      <LegalSection
        id="preferences"
        title="5. Cookie & Bộ nhớ lưu tùy chọn giao diện (Preferences)"
        badge="Trải nghiệm người dùng"
      >
        <p>
          Các khóa dữ liệu này được lưu tại trình duyệt nhằm cá nhân hóa giao diện và nâng cao khả năng tiếp cận (Accessibility - A11y):
        </p>
        <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[var(--surface-muted)] text-[var(--text-primary)] font-bold border-b border-[color:var(--shell-border)]">
              <tr>
                <th className="p-3">Tên khóa</th>
                <th className="p-3">Lưu trữ tại</th>
                <th className="p-3">Giá trị lưu trữ</th>
                <th className="p-3">Mục đích</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--shell-border)] text-[var(--text-secondary)]">
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-primary)]">clara-theme</td>
                <td className="p-3 font-mono text-[11px]">localStorage</td>
                <td className="p-3 font-mono text-[11px]">&apos;dark&apos; | &apos;light&apos; | &apos;system&apos;</td>
                <td className="p-3">Ghi nhớ chế độ hiển thị sáng/tối.</td>
              </tr>
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-primary)]">clara-ui-language</td>
                <td className="p-3 font-mono text-[11px]">localStorage</td>
                <td className="p-3 font-mono text-[11px]">&apos;vi&apos; | &apos;en&apos;</td>
                <td className="p-3">Ghi nhớ ngôn ngữ giao diện ưa thích.</td>
              </tr>
              <tr className="hover:bg-[var(--surface-muted)]/30">
                <td className="p-3 font-mono font-bold text-[var(--text-primary)]">clara-reduced-motion</td>
                <td className="p-3 font-mono text-[11px]">localStorage</td>
                <td className="p-3 font-mono text-[11px]">&apos;reduce&apos; | &apos;normal&apos;</td>
                <td className="p-3">Tùy chọn giảm chuyển động cho người nhạy cảm tiền đình.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </LegalSection>

      {/* 6. Zero Third-Party Tracking */}
      <LegalSection
        id="zero-tracking"
        title="6. Cam kết tuyệt đối: Zero Third-Party Ad Tracking & Zero Profiling"
        badge="Quyền riêng tư tuyệt đối"
      >
        <div className="rounded-xl border border-[color:var(--status-ok-border)]/80 bg-[var(--status-ok-bg)]/25 p-5 space-y-3">
          <p className="font-bold text-[var(--text-primary)]">
            Tôn chỉ bảo vệ quyền riêng tư y tế trong The Clara Care:
          </p>
          <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm text-[var(--text-secondary)]">
            <li>
              <strong>KHÔNG có cookie quảng cáo của bên thứ ba:</strong> Chúng tôi tuyệt đối không tích hợp Google Ads,
              Facebook Pixel, Criteo, TikTok Tracker hoặc bất kỳ mạng lưới quảng cáo nào.
            </li>
            <li>
              <strong>KHÔNG lập hồ sơ hành vi (Behavioral Profiling):</strong> Dữ liệu duyệt web và truy vấn y tế
              của bạn không bao giờ bị xâu chuỗi để phân tích tâm lý hoặc tạo hồ sơ thương mại.
            </li>
            <li>
              <strong>KHÔNG bán hoặc chia sẻ dữ liệu cho Data Brokers:</strong> Mọi thông tin cookie chỉ có giá trị nội bộ
              trong phạm vi tên miền chính thức của The Clara Care.
            </li>
          </ul>
        </div>
      </LegalSection>

      {/* 7. Mục đích sử dụng */}
      <LegalSection id="purposes" title="7. Mục đích sử dụng cookie" badge="Mục đích xử lý">
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>Duy trì trạng thái đăng nhập liên tục để hạn chế thao tác xác thực lặp lại trong phiên làm việc.</li>
          <li>Tăng cường khả năng phát hiện bất thường mạng, ngăn ngừa rủi ro chiếm quyền điều khiển tài khoản y tế.</li>
          <li>Cá nhân hóa trải nghiệm hiển thị (ngôn ngữ, độ tương phản, theme) theo nhu cầu người dùng.</li>
          <li>Đảm bảo các quy chuẩn bảo vệ dữ liệu nhạy cảm theo quy định của pháp luật Việt Nam.</li>
        </ul>
      </LegalSection>

      {/* 8. Thời hạn lưu trữ */}
      <LegalSection id="storage-duration" title="8. Thời hạn lưu trữ cookie" badge="Thời hạn lưu vết">
        <p>
          Thời hạn lưu trữ cookie được ấn định nghiêm ngặt theo vòng đời tối thiểu cần thiết:
        </p>
        <ul className="list-disc space-y-2 pl-5 text-xs sm:text-sm">
          <li>
            <strong>Cookie phiên (Session Cookies):</strong> Tự động xóa ngay khi bạn đóng tab hoặc cửa sổ trình duyệt.
          </li>
          <li>
            <strong>Cookie xác thực phiên mở rộng (Persistent Refresh Tokens):</strong> Tối đa 30 ngày và tự hủy khi bạn thực hiện thao tác Đăng xuất.
          </li>
          <li>
            <strong>Bộ nhớ tùy chọn cục bộ (Local Preferences):</strong> Lưu trữ cho đến khi bạn chủ động xóa dữ liệu trình duyệt hoặc nhấn nút đặt lại tại mục bên dưới.
          </li>
        </ul>
      </LegalSection>

      {/* 9. Quản lý cookie */}
      <LegalSection id="management" title="9. Cơ chế & Công cụ quản lý cookie" badge="Quyền kiểm soát">
        <p>
          Bạn có toàn quyền kiểm tra, cấu hình hoặc xóa cookie bất cứ lúc nào thông qua trình duyệt của mình:
        </p>
        <ul className="list-disc space-y-1.5 pl-5 text-xs sm:text-sm">
          <li><strong>Google Chrome:</strong> Cài đặt &rarr; Quyền riêng tư và bảo mật &rarr; Cookie của bên thứ ba.</li>
          <li><strong>Apple Safari:</strong> Tùy chọn &rarr; Quyền riêng tư &rarr; Chặn tất cả cookie.</li>
          <li><strong>Mozilla Firefox:</strong> Cài đặt &rarr; Quyền riêng tư & Bảo mật &rarr; Cookie và dữ liệu trang web.</li>
          <li><strong>Microsoft Edge:</strong> Cài đặt &rarr; Quyền và cookie trang web &rarr; Quản lý và xóa cookie.</li>
        </ul>

        <div className="pt-2">
          <CookieManagerControl />
        </div>
      </LegalSection>

      {/* 10. Ảnh hưởng khi tắt */}
      <LegalSection id="impact" title="10. Ảnh hưởng khi tắt cookie" badge="Lưu ý kỹ thuật">
        <p>
          Nếu bạn tắt hoặc chặn hoàn toàn cookie trên trình duyệt:
        </p>
        <div className="rounded-xl border border-[color:var(--status-warn-border)]/70 bg-[var(--status-warn-bg)]/20 p-4 space-y-2 text-xs sm:text-sm">
          <p className="font-bold text-[var(--text-primary)]">Lưu ý quan trọng:</p>
          <p className="text-[var(--text-secondary)]">
            Việc tắt các cookie thiết yếu sẽ khiến bạn <strong>không thể đăng nhập</strong>, không thể duy trì phiên bảo mật
            để tra cứu hồ sơ PHR hoặc sử dụng các tính năng an toàn y tế như CareGuard hay Clinical Council.
            Các tùy chọn giao diện cá nhân cũng sẽ trở về mặc định mỗi lần tải lại trang.
          </p>
        </div>
      </LegalSection>

      {/* 11. Cập nhật chính sách & DPO */}
      <LegalSection id="updates" title="11. Cập nhật chính sách cookie & Liên hệ DPO" badge="Thông tin liên hệ">
        <p>
          Chính sách cookie này được rà soát và cập nhật định kỳ nhằm đảm bảo phù hợp với các cải tiến công nghệ và quy định
          pháp luật hiện hành:
        </p>
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 text-xs sm:text-sm">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Chủ thể quản trị:</span>
            <span className="font-bold text-[var(--text-primary)]">{LEGAL_OPERATOR_NAME}</span>
          </div>
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <span className="text-[var(--text-muted)]">Email Cán bộ bảo vệ dữ liệu (DPO):</span>
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
            <span className="text-[var(--text-muted)]">Phiên bản hiệu lực:</span>
            <span className="font-mono font-bold text-[var(--text-brand)]">{LEGAL_POLICY_VERSION} ({LEGAL_UPDATED_AT})</span>
          </div>
        </div>
      </LegalSection>
    </LegalPageShell>
  );
}
