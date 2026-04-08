import LegalPageShell from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách quyền riêng tư | Project CLARA",
  description: "Mô tả cách Project CLARA thu thập, sử dụng, lưu trữ và bảo vệ dữ liệu người dùng.",
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPageShell
      title="Chính sách quyền riêng tư"
      summary="Tài liệu này mô tả cách Project CLARA thu thập, sử dụng, lưu trữ và bảo vệ dữ liệu khi bạn dùng hệ thống."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">1. Phạm vi áp dụng</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Chính sách áp dụng cho toàn bộ dịch vụ web của Project CLARA, bao gồm các phân hệ Research, Council, Self-Med,
          CareGuard, Scribe và khu vực quản trị.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">2. Dữ liệu được thu thập</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
          <li>Dữ liệu tài khoản: họ tên, email, vai trò người dùng, thông tin xác thực phiên đăng nhập.</li>
          <li>Dữ liệu sử dụng: lịch sử truy vấn, log vận hành, tín hiệu chất lượng phản hồi và sự kiện hệ thống.</li>
          <li>Dữ liệu do bạn cung cấp: nội dung câu hỏi, tài liệu tải lên, thông tin thuốc và ghi chú liên quan.</li>
          <li>Dữ liệu consent: phiên bản điều khoản đã chấp thuận, thời điểm chấp thuận và trạng thái hiệu lực.</li>
        </ul>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">3. Mục đích sử dụng dữ liệu</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
          <li>Cung cấp chức năng chính của sản phẩm và duy trì phiên làm việc an toàn.</li>
          <li>Nâng cao chất lượng truy xuất bằng chứng, độ ổn định và hiệu suất hệ thống.</li>
          <li>Phát hiện lỗi, điều tra sự cố bảo mật và phục vụ kiểm toán nội bộ.</li>
          <li>Đáp ứng yêu cầu tuân thủ pháp lý khi có căn cứ hợp lệ.</li>
        </ul>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">4. Chia sẻ dữ liệu với bên thứ ba</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          CLARA chỉ chia sẻ dữ liệu trong phạm vi cần thiết để vận hành dịch vụ (ví dụ nhà cung cấp hạ tầng, dịch vụ tích
          hợp), hoặc khi có nghĩa vụ pháp lý. Chúng tôi không bán dữ liệu cá nhân cho bên thứ ba.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">5. Lưu trữ và bảo mật</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
          <li>Dữ liệu được lưu trữ trên hạ tầng có kiểm soát truy cập theo vai trò.</li>
          <li>Log quan trọng được lưu vết để phục vụ audit và điều tra sự cố.</li>
          <li>Các biện pháp kỹ thuật và tổ chức được cập nhật định kỳ theo mức độ rủi ro.</li>
        </ul>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">6. Quyền của người dùng</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Bạn có quyền yêu cầu xem, cập nhật hoặc xóa dữ liệu tài khoản trong phạm vi cho phép của pháp luật và chính sách
          vận hành hiện hành.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">7. Liên hệ</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Mọi yêu cầu liên quan đến quyền riêng tư vui lòng gửi về{" "}
          <a className="font-semibold text-[var(--text-brand)] hover:underline" href={`mailto:${LEGAL_CONTACT_EMAIL}`}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </article>
    </LegalPageShell>
  );
}
