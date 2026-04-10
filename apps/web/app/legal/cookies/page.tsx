import LegalPageShell, { LegalSection } from "@/components/legal/legal-page-shell";
import { LEGAL_UPDATED_AT } from "@/lib/legal";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chính sách cookie | The Clara Care",
  description: "Mô tả cách The Clara Care sử dụng cookie để vận hành, bảo mật và ghi nhớ tuỳ chọn người dùng.",
};

const COOKIE_SECTIONS = [
  { id: "definition", label: "Cookie là gì" },
  { id: "categories", label: "Nhóm cookie sử dụng" },
  { id: "purposes", label: "Mục đích sử dụng" },
  { id: "storage-duration", label: "Thời hạn lưu" },
  { id: "management", label: "Quản lý cookie" },
  { id: "impact", label: "Ảnh hưởng khi tắt" },
  { id: "updates", label: "Cập nhật chính sách" },
] as const;

export default function CookiePolicyPage() {
  return (
    <LegalPageShell
      policyKey="cookies"
      title="Chính sách cookie"
      summary="Cookie giúp The Clara Care duy trì phiên đăng nhập an toàn, ghi nhớ cấu hình hiển thị và tối ưu trải nghiệm sử dụng theo ngữ cảnh làm việc của người dùng."
      updatedAt={LEGAL_UPDATED_AT}
      sections={COOKIE_SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      highlights={[
        "Không dùng cookie để bán dữ liệu cá nhân.",
        "Ưu tiên cookie cần thiết cho bảo mật và vận hành.",
        "Người dùng có thể quản lý cookie tại trình duyệt.",
      ]}
    >
      <LegalSection id="definition" title="1. Cookie là gì">
        <p>
          Cookie là tệp dữ liệu nhỏ được trình duyệt lưu lại để nhận diện phiên truy cập, ghi nhớ trạng thái đăng nhập và duy trì
          một số cài đặt của người dùng giữa các lần sử dụng dịch vụ.
        </p>
      </LegalSection>

      <LegalSection id="categories" title="2. Các nhóm cookie được sử dụng">
        <ul className="list-disc space-y-2 pl-5">
          <li>Cookie cần thiết: xác thực phiên, chống truy cập trái phép, đảm bảo chức năng bảo mật cốt lõi.</li>
          <li>Cookie chức năng: ghi nhớ tùy chọn giao diện như light/dark mode hoặc ngôn ngữ hiển thị.</li>
          <li>Cookie hiệu năng: phục vụ đo lường kỹ thuật cơ bản nhằm cải thiện độ ổn định hệ thống (khi được bật).</li>
        </ul>
      </LegalSection>

      <LegalSection id="purposes" title="3. Mục đích sử dụng cookie">
        <ul className="list-disc space-y-2 pl-5">
          <li>Duy trì trạng thái đăng nhập để hạn chế thao tác lặp lại trong phiên làm việc.</li>
          <li>Tăng cường khả năng phát hiện bất thường và giảm nguy cơ chiếm quyền phiên.</li>
          <li>Cá nhân hóa trải nghiệm trình bày giao diện theo tùy chọn người dùng.</li>
        </ul>
      </LegalSection>

      <LegalSection id="storage-duration" title="4. Thời hạn lưu trữ cookie">
        <p>
          Một số cookie chỉ tồn tại trong phiên hiện tại (session cookie), số khác có thể tồn tại lâu hơn để ghi nhớ cài đặt. Thời
          hạn cụ thể phụ thuộc loại cookie và mục tiêu vận hành tương ứng.
        </p>
      </LegalSection>

      <LegalSection id="management" title="5. Cách quản lý cookie">
        <p>
          Người dùng có thể xóa, chặn hoặc giới hạn cookie trong phần cài đặt trình duyệt. Mỗi trình duyệt có cơ chế khác nhau,
          nên bạn cần tham khảo tài liệu hướng dẫn của trình duyệt đang sử dụng.
        </p>
      </LegalSection>

      <LegalSection id="impact" title="6. Ảnh hưởng khi tắt cookie">
        <p>
          Nếu vô hiệu hóa cookie cần thiết, một số chức năng như đăng nhập, duy trì phiên hoặc lưu cài đặt giao diện có thể không
          hoạt động đúng như thiết kế. Điều này có thể làm gián đoạn trải nghiệm sử dụng The Clara Care.
        </p>
      </LegalSection>

      <LegalSection id="updates" title="7. Cập nhật chính sách cookie">
        <p>
          Chính sách cookie có thể được điều chỉnh theo thay đổi kỹ thuật và quy định tuân thủ. Bản cập nhật mới nhất luôn được
          công bố tại Policy Center thuộc The Clara Care.
        </p>
      </LegalSection>
    </LegalPageShell>
  );
}
