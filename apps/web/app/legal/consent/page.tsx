import LegalPageShell from "@/components/legal/legal-page-shell";
import { LEGAL_CONTACT_EMAIL, LEGAL_POLICY_VERSION, LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Đồng thuận sử dụng y tế | Project CLARA",
  description:
    "Điều khoản đồng thuận bắt buộc khi dùng các tính năng có rủi ro lâm sàng trong Project CLARA.",
};

export default function MedicalConsentPage() {
  return (
    <LegalPageShell
      title="Đồng thuận sử dụng y tế"
      summary="Tài liệu này áp dụng cho các tính năng có rủi ro lâm sàng như Self-Med, CareGuard và các luồng liên quan đến an toàn thuốc."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">1. Bản chất của hệ thống</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Project CLARA là công cụ hỗ trợ tham khảo. Nội dung do hệ thống tạo ra không thay thế tư vấn trực tiếp của bác
          sĩ và không được xem là chỉ định điều trị cuối cùng.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">2. Cam kết của người dùng khi đồng thuận</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-[var(--text-secondary)]">
          <li>Không dùng CLARA để tự chẩn đoán hoặc tự kê đơn.</li>
          <li>Luôn kiểm chứng thông tin trước khi áp dụng vào quyết định chuyên môn.</li>
          <li>Liên hệ cơ sở y tế khi có dấu hiệu cấp cứu hoặc bất thường nghiêm trọng.</li>
        </ul>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">3. Tình huống khẩn cấp</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Nếu xuất hiện các triệu chứng cấp cứu (khó thở nặng, đau ngực dữ dội, rối loạn ý thức, co giật, sốc phản vệ...),
          bạn cần gọi cấp cứu hoặc đến cơ sở y tế gần nhất ngay lập tức.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">4. Dữ liệu liên quan đến đồng thuận</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Hệ thống lưu trạng thái đồng thuận (phiên bản điều khoản, thời điểm chấp thuận, user context) để phục vụ kiểm
          soát truy cập, audit và tuân thủ vận hành.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">5. Rút lại đồng thuận</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Bạn có thể liên hệ quản trị hệ thống để yêu cầu cập nhật trạng thái đồng thuận. Một số tính năng an toàn thuốc
          có thể bị khóa cho đến khi đồng thuận được xác nhận lại.
        </p>
      </article>

      <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">6. Liên hệ hỗ trợ</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Phiên bản consent hiện tại: <span className="font-semibold">{LEGAL_POLICY_VERSION}</span>.
        </p>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
          Nếu cần hỗ trợ về nội dung đồng thuận, vui lòng gửi email tới{" "}
          <a className="font-semibold text-[var(--text-brand)] hover:underline" href={`mailto:${LEGAL_CONTACT_EMAIL}`}>
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </article>
    </LegalPageShell>
  );
}
