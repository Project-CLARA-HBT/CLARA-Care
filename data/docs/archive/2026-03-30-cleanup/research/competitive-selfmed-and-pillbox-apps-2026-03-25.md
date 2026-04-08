# Nghiên cứu đối thủ: Self-med / Pillbox / DDI apps (cập nhật 2026-03-25)

## 1) Phạm vi và cách đọc

- **Ngày chốt dữ liệu:** 2026-03-25.
- **Nguồn ưu tiên:** website/chính sách/help center/app store chính thức.
- **Nhóm app ưu tiên theo yêu cầu:** Medisafe, MyTherapy, Drugs.com, WebMD, CareClinic, Dosecast, MyMeds.
- **Nhóm liên quan Việt Nam (VN-relevant):** Pharmacity, Long Châu, YouMed.
- **Lưu ý:** Một số app có dữ liệu công khai mang tính marketing; những điểm chưa đủ bằng chứng được đánh dấu rõ là “chưa thấy công bố rõ”.

---

## 2) Executive summary (ngắn)

1. **Mô hình “tủ thuốc lâu dài” (permanent cabinet) là chuẩn chung**: đa số app lưu danh mục thuốc + lịch dùng + lịch sử tuân thủ theo hồ sơ cá nhân/gia đình, không phải phiên dùng tạm.
2. **DDI có 2 mô hình trigger chính**:
   - **Proactive khi thêm thuốc vào tủ thuốc** (Medisafe, một phần Drugs.com profile).
   - **On-demand checker** (WebMD, Drugs.com Interaction Checker).
3. **Barcode/OCR/invoice scan chưa phải baseline của nhóm reminder lớn**: phần lớn vẫn ưu tiên nhập tay + chọn từ drug DB; scan chủ yếu xuất hiện ở vài app/flow riêng (CareClinic scan ảnh toa, CareZone scan lọ thuốc, Pharmacity tối ưu upload toa + quét mã sản phẩm).
4. **Family dashboard + escalation là điểm khác biệt lớn**:
   - Mạnh: Medisafe (Medfriend), Dosecast (Family Share), CareClinic (Care Team), MyMeds (legacy Circle of Care).
   - Yếu/không rõ: WebMD, MyTherapy (nghiêng self-management + chia sẻ cho bác sĩ).
5. **Refill/reminder pattern tốt nhất hiện tại** thường là đa lớp: nhắc chính + nhắc lặp/nag + refill trước hạn + cảnh báo bỏ liều cho caregiver.

---

## 3) Phân tích chi tiết theo app ưu tiên

## 3.1 Medisafe

- **Core:** pillbox, nhắc uống thuốc, refill reminder, đồng bộ gia đình, cảnh báo DDI, import thuốc từ Health Records (US).
- **UX flow điển hình:** Add med vào Pillbox -> đặt lịch liều -> bật refill -> theo dõi taken/missed -> nếu bỏ liều nhiều lần thì Medfriend nhận push.
- **Persistence:** hồ sơ tài khoản + pillbox/history lâu dài; có cơ chế sync giữa người dùng và Medfriend/family.
- **DDI trigger:** có trigger proactive khi thêm thuốc mới gây tương tác “major/severe” trong virtual pillbox (alert vào feed/updates).
- **Scan/OCR:** không thấy nhấn mạnh barcode/OCR hóa đơn trong tài liệu chính; thay vào đó có import từ Health Records iPhone.
- **Family dashboard/escalation:** rất mạnh (Medfriend sync, cảnh báo bỏ liều cho người thân/caregiver).
- **Refill/reminder:** có refill reminder lặp hàng ngày cho tới khi refill.

## 3.2 MyTherapy

- **Core:** nhắc thuốc, nhật ký uống thuốc, symptom/measurement diary, nhắc refill gói thuốc/đơn thuốc, xuất báo cáo cho bác sĩ.
- **UX flow:** Add medication (search DB hoặc nhập tay) -> tạo lịch nhắc -> xác nhận taken/skipped -> ghi triệu chứng/chỉ số -> xuất báo cáo khám.
- **Persistence:** nhật ký điều trị cá nhân được duy trì liên tục (“anytime, anywhere”), phù hợp mô hình tủ thuốc dài hạn.
- **DDI trigger:** trong landing chính chưa thấy công bố rõ trigger DDI chủ động; nội dung App Store có nhắc kiểm tra adverse interactions nhưng mức tự động hóa chưa mô tả rõ.
- **Scan/OCR:** chưa thấy công bố rõ barcode/OCR toa/hóa đơn trong nguồn khảo sát.
- **Family dashboard/escalation:** chưa thấy công bố rõ dashboard caregiver chuyên dụng như Medisafe/Dosecast.
- **Refill/reminder:** mạnh ở nhắc đúng giờ + nhắc gói thuốc/đơn tiếp theo.

## 3.3 Drugs.com Medication Guide

- **Core:** My Med List, Interaction Checker, Pill Identifier, reminders/alerts, FDA alerts, profile cho bản thân & gia đình.
- **UX flow:** tạo profile -> nhập danh sách thuốc -> theo dõi interaction/reminder/alerts -> dùng checker khi cần.
- **Persistence:** account-based, có multiple profiles, usable offline cho My Med List.
- **DDI trigger:** cả hai dạng: (1) interaction trong My Med List + alerts; (2) Interaction Checker theo yêu cầu.
- **Scan/OCR:** có Pill Identifier bằng imprint/color/shape (không phải OCR toa/hóa đơn theo nghĩa đầy đủ).
- **Family dashboard/escalation:** có hồ sơ tách cho thành viên gia đình; escalation caregiver chuyên sâu chưa thấy mô tả mạnh.
- **Refill/reminder:** có reminder/alerts trong health profile.

## 3.4 WebMD (core app, không còn “standalone reminder app” tách biệt rõ)

- **Core:** symptom checker, medication reminders, Drug Interaction Checker, pill images, sync reminders đa thiết bị khi đăng nhập.
- **UX flow:** thêm thuốc/lịch dùng -> nhận reminder -> kiểm tra tương tác khi cần bằng Interaction Checker.
- **Persistence:** dựa trên tài khoản WebMD, sync sang thiết bị khác.
- **DDI trigger:** chủ yếu **on-demand** (nhập >=2 thuốc để check).
- **Scan/OCR:** chưa thấy công bố rõ barcode/OCR toa/hóa đơn.
- **Family dashboard/escalation:** chưa thấy công bố rõ.
- **Refill/reminder:** reminder theo lịch cá nhân, không thấy pattern escalation caregiver chuyên sâu.

## 3.5 CareClinic

- **Core:** medication tracker + symptom tracker + care plan + caregiver/team sharing.
- **UX flow:** tạo care plan -> thêm thuốc (DB/search/scan toa) -> reminder + check-in -> theo dõi side effects/adherence -> chia sẻ dữ liệu cho care team.
- **Persistence:** profile có lịch sử medication/symptom, hỗ trợ sync đa thiết bị, export báo cáo.
- **DDI trigger:** nguồn public mô tả có kiểm tra tương tác nguy hiểm/giảm nguy cơ interaction; cần xác thực thêm ở tài liệu kỹ thuật sâu nếu dùng cho claim lâm sàng.
- **Scan/OCR:** FAQ nêu rõ có thể chụp toa thuốc/rx form để auto scan và nhập thuốc.
- **Family dashboard/escalation:** mạnh (care team, dependent profile, caregiver alerts khi bỏ liều).
- **Refill/reminder:** reminders nhiều lớp + refill tracking trước khi hết thuốc.

## 3.6 Dosecast

- **Core:** lịch dùng thuốc linh hoạt (fixed/interval/as-needed), history đầy đủ, refill alerts, multi-person support, CloudSync.
- **UX flow:** +New Pill -> chọn thuốc từ DB -> đặt lịch -> reminder -> log taken/skipped/postponed -> history/email export -> family share qua sync code.
- **Persistence:** mạnh (CloudSync + backup/restore cloud, history lâu dài).
- **DDI trigger:** chưa thấy công bố DDI checker mạnh như Medisafe/Drugs.com.
- **Scan/OCR:** chưa thấy OCR toa/hóa đơn; có drug DB + custom drug photo.
- **Family dashboard/escalation:** mạnh (Caregiver & Family Share, multi-device/multi-person).
- **Refill/reminder:** có secondary nag reminder, continuous alarm until acknowledged, refill alerts.

## 3.7 MyMeds

- **Core (theo nguồn còn công khai):** nhắc liều + refill qua text/email/push, sync với người thân/healthcare team, medication history analytics.
- **UX flow:** tạo account -> thêm thuốc -> nhắc liều/refill -> theo dõi usage history -> chia sẻ với care circle/team.
- **Persistence:** có nền tảng real-time medication history (PBM/Medicare integration theo trang giới thiệu).
- **DDI trigger:** chưa thấy công bố rõ trigger DDI tự động trong tài liệu hiện tại.
- **Scan/OCR:** chưa thấy công bố rõ OCR/barcode.
- **Family dashboard/escalation:** có dấu hiệu hỗ trợ dependents/circle-of-care và notify khi quên thuốc (nguồn App Store lịch sử update cũ).
- **Rủi ro đánh giá:** dữ liệu App Store cho MyMeds có dấu hiệu cũ (release notes 2016-2018), cần kiểm chứng tình trạng sản phẩm hiện tại trước khi benchmark sâu.

---

## 4) VN-relevant options

## 4.1 Pharmacity

- **Điểm đáng chú ý:** tài liệu chính thức nêu rõ app có lưu trữ đơn thuốc, nhắc uống thuốc, lịch tiêm vắc xin, refill đơn hàng.
- **Scan/OCR/barcode pattern:** release notes App Store nêu “tối ưu upload đơn thuốc”, thêm quét mã sản phẩm/QR tra giá; phù hợp pattern nhập liệu bằng ảnh + mã tại nhà thuốc.
- **DDI/family/escalation:** chưa thấy công bố rõ DDI checker hoặc escalation caregiver kiểu Medfriend.

## 4.2 Long Châu

- **Điểm đáng chú ý:** release notes App Store (2025) có nêu “Tủ thuốc gia đình” theo nhóm bệnh, cho thấy hướng tới permanent family cabinet.
- **DDI/scan/escalation:** chưa thấy công bố rõ trigger DDI hoặc escalation bỏ liều trong nguồn khảo sát.

## 4.3 YouMed

- **Điểm đáng chú ý:** app đặt khám có “nhắc đi khám, nhắc uống thuốc”; có yếu tố đặt giúp người thân và trả toa/kết quả.
- **Định vị:** không phải pillbox chuyên sâu nhưng là lựa chọn VN hữu ích cho workflow khám -> toa -> nhắc dùng thuốc.

---

## 5) Ma trận so sánh tính năng (2026-03-25)

| App | Permanent medicine cabinet (không session) | DDI check + trigger | Barcode/OCR/invoice pattern | Family dashboard | Escalation alerts | Refill/reminder pattern | Persistence/data |
|---|---|---|---|---|---|---|---|
| **Medisafe** | **Mạnh** (virtual pillbox lâu dài) | **Mạnh** (proactive alert khi thêm thuốc major/severe; interaction info) | Thấp-vừa (không thấy OCR hóa đơn; có import Health Records) | **Mạnh** (Medfriend + family sync) | **Mạnh** (missed-dose push cho Medfriend sau nhiều lần nhắc) | **Mạnh** (dose + refill) | Tài khoản + sync + lịch sử |
| **MyTherapy** | **Mạnh** (med plan + diary) | Trung bình/không rõ trigger tự động | Thấp (chưa thấy OCR/barcode rõ) | Thấp-trung bình (chia sẻ bác sĩ tốt, caregiver dashboard chưa rõ) | Thấp-trung bình | **Mạnh** (dose + package/prescription refill) | Nhật ký điều trị liên tục |
| **Drugs.com** | **Mạnh** (My Med List + multiple profiles) | **Mạnh** (checker + interaction data trong profile) | Trung bình (pill identifier theo imprint/shape/color; không thấy OCR hóa đơn) | Trung bình (multiple profiles family) | Thấp-trung bình | Trung bình-mạnh (reminders/alerts + FDA alerts) | Account + offline access |
| **WebMD** | Trung bình (med schedules trong app account) | Trung bình-mạnh (on-demand checker rõ) | Thấp | Thấp | Thấp | Trung bình (med reminders, sync đa thiết bị) | Account sync |
| **CareClinic** | **Mạnh** | Trung bình-mạnh (public claim có interaction checks) | **Mạnh** (scan ảnh toa/rx form) | **Mạnh** (care team/dependents) | **Mạnh** (caregiver alerts missed dose) | **Mạnh** (smart reminders + refill tracking) | Sync đa thiết bị + report/export |
| **Dosecast** | **Mạnh** | Thấp-trung bình (không thấy DDI checker nổi bật) | Thấp-trung bình (DB + ảnh thuốc, không OCR toa rõ) | **Mạnh** (Family Share) | **Mạnh** (nag + continuous alarms) | **Rất mạnh** (schedule linh hoạt + refill) | CloudSync + backup/restore |
| **MyMeds** | Trung bình-mạnh | Không rõ | Không rõ | Trung bình (loved ones/circle-of-care) | Trung bình (legacy notify dependents) | Trung bình-mạnh (text/email/push + refill) | Có claim real-time PBM/Medicare; dữ liệu public cũ |
| **Pharmacity (VN)** | Trung bình (lưu đơn/tính năng chăm sóc) | Không rõ | Trung bình-mạnh (upload đơn thuốc + quét mã sản phẩm/QR giá) | Thấp-trung bình | Không rõ | Trung bình (nhắc uống + refill đơn) | App account |
| **Long Châu (VN)** | Trung bình-mạnh (“Tủ thuốc gia đình”) | Không rõ | Không rõ | Trung bình (hướng gia đình) | Không rõ | Không rõ | App account |
| **YouMed (VN)** | Trung bình (toa + hồ sơ khám) | Không rõ | Không rõ | Trung bình (đặt giúp người thân) | Thấp | Trung bình (nhắc khám + nhắc uống thuốc) | App account |

---

## 6) Mẫu thiết kế rút ra (đặc biệt cho các yêu cầu bắt buộc)

## 6.1 Permanent medicine cabinet model (không session)

Mẫu tốt nhất từ Medisafe/Dosecast/Drugs.com/CareClinic:

- `User` có nhiều `Profile` (self, dependent, family member).
- `MedicineMaster` (chuẩn hóa tên hoạt chất/brand/form/strength).
- `CabinetItem` (thuốc đang dùng, tồn kho, refill, prescriber/pharmacy).
- `Regimen` (lịch liều linh hoạt: fixed, interval, PRN, cycle, pause/suspend).
- `DoseEvent` (taken/skipped/postponed/missed + timestamp).
- `AdherenceTimeline` + export report.

## 6.2 DDI check triggers

Nên triển khai 3 mức trigger:

1. **On add/update medication (proactive):** giống Medisafe, check ngay khi thêm/chỉnh thuốc và cảnh báo theo mức độ.
2. **On demand checker:** người dùng tự tra nhanh khi muốn thêm OTC/supplement.
3. **On background reconciliation:** chạy định kỳ khi profile đổi, phát hiện tương tác mới theo guideline DB update.

Severity mẫu: `minor / moderate / major / severe`; với `major/severe` bắt buộc hiển thị CTA rõ: “liên hệ bác sĩ/dược sĩ”.

## 6.3 Barcode/OCR invoice/prescription patterns

Thực tế thị trường cho thấy 4 pattern:

1. **Manual + DB search** (phổ biến nhất).
2. **Pill ID (imprint/shape/color)** để xác định viên thuốc (Drugs.com).
3. **Scan ảnh toa/rx** để auto fill trường thuốc-liều (CareClinic).
4. **Upload đơn + quét mã sản phẩm/QR** ở app nhà thuốc VN (Pharmacity).

Kết luận: **OCR hóa đơn/đơn thuốc là lợi thế cạnh tranh**, chưa thành baseline của nhóm app reminder truyền thống.

## 6.4 Family dashboard

Mẫu mạnh:

- Dashboard theo từng dependent.
- Dòng trạng thái realtime: upcoming dose, missed dose, refill risk.
- Quyền theo vai trò: owner / caregiver / read-only clinician.
- Log hành động có audit trail.

## 6.5 Escalation alerts

Pattern hiệu quả nhất (quan sát từ Medisafe, Dosecast, CareClinic):

1. Nhắc chính tại giờ dùng.
2. Nhắc lặp (nag) sau `x` phút nếu chưa acknowledge.
3. Tăng cấp kênh (push -> SMS/call tùy cấu hình).
4. Báo caregiver khi quá ngưỡng bỏ liều.
5. Tùy chọn “continuous alarm until acknowledged” cho nhóm nguy cơ cao.

## 6.6 Refill/reminder patterns

- Theo số lượng còn lại + số ngày dùng trung bình.
- Cảnh báo đa mốc (7 ngày, 3 ngày, 1 ngày).
- Nhắc lặp đến khi người dùng xác nhận đã refill.
- Hỗ trợ khác biệt giữa chronic meds vs PRN meds.

---

## 7) Đề xuất kiến trúc module **CLARA Self-Med** (từ benchmark)

## 7.1 Kiến trúc logic đề xuất

1. **Cabinet Service**
- Quản lý `Profile`, `CabinetItem`, `Regimen`, `DoseEvent`, `RefillState`.

2. **Medication Knowledge Service**
- Drug normalization, synonym mapping, RxNorm/ATC mapping (nếu áp dụng).
- DDI engine + food/alcohol/allergy/condition checks.

3. **Ingestion Service (Manual + Scan)**
- Manual entry wizard.
- Barcode/QR parser.
- OCR pipeline cho toa/hóa đơn (image preprocess -> OCR -> entity extraction -> confidence scoring -> human confirm).

4. **Reminder & Escalation Engine**
- Scheduler đa timezone.
- Multi-channel notification.
- Escalation policy engine theo profile nguy cơ.

5. **Family & Care Team Service**
- Role-based sharing.
- Caregiver dashboard realtime.
- Missed-dose webhook/push cho người thân.

6. **Adherence & Insights Service**
- Tính adherence score.
- Phát hiện pattern bỏ liều/refill gaps.
- Export report cho bác sĩ.

7. **Compliance/Security Layer**
- Encryption at rest/in transit.
- Audit log, consent, data retention policy.
- Regional config (US/VN data & legal localization).

## 7.2 Event triggers khuyến nghị

- `MED_ADDED` -> chuẩn hóa thuốc -> chạy DDI -> nếu severity >= threshold thì alert ngay.
- `DOSE_MISSED` -> local nag -> quá timeout -> caregiver escalation.
- `STOCK_BELOW_THRESHOLD` -> refill workflow.
- `NEW_EXTERNAL_RX` (import từ EHR/pharmacy) -> reconcile cabinet.

## 7.3 UX flow đề xuất cho CLARA (MVP -> v2)

- **MVP:** manual add + schedule + dose confirm + refill + caregiver escalation + on-demand DDI.
- **v1.5:** proactive DDI on add/edit + family dashboard đầy đủ.
- **v2:** OCR toa/hóa đơn + barcode/QR + pharmacy/EHR connectors.

---

## 8) Rủi ro & khoảng trống cần lưu ý khi triển khai

1. **False positive DDI** có thể gây “alert fatigue”; cần severity gating + plain-language explanation.
2. **OCR sai thuốc/liều** là rủi ro an toàn; bắt buộc bước xác nhận người dùng trước khi commit cabinet.
3. **Caregiver escalation** dễ xâm phạm riêng tư nếu không có consent/role rõ.
4. **Nguồn dữ liệu MyMeds công khai có dấu hiệu cũ**, không nên dùng làm chuẩn kỹ thuật chính cho roadmap.

---

## 9) Tài liệu tham chiếu

### Medisafe
1. https://apps.apple.com/us/app/medisafe-medication-management/id573916946
2. https://www.medisafe.com/medisafe-launches-feature-to-alert-users-of-potentially-harmful-drug-interactions/
3. https://medisafeapp.com/pro-tip-add-a-medfriend/
4. https://www.medisafe.com/faq/how-do-i-set-a-refill-reminder-when-i-add-my-med-2/

### MyTherapy
5. https://www.mytherapyapp.com/
6. https://apps.apple.com/us/app/meds-pill-reminder-mytherapy/id662170995

### Drugs.com
7. https://apps.apple.com/us/app/drugs-com-medication-guide/id599471042
8. https://www.drugs.com/mednotes/
9. https://www.drugs.com/apps/?pStoreID=contenttest

### WebMD
10. https://apps.apple.com/us/app/webmd-symptom-checker/id295076329
11. https://customercare.webmd.com/hc/en-us/articles/19689436362509-Tell-me-about-the-core-WebMD-App

### CareClinic
12. https://careclinic.io/medicine-tracker/
13. https://careclinic.io/caregiver-app/
14. https://apps.apple.com/us/app/tracker-reminder-careclinic/id1455648231

### Dosecast
15. https://dosecast.com/features/
16. https://dosecast.com/users-guide/

### MyMeds
17. https://www.myhealthapplication.com/app/mymeds
18. https://apps.apple.com/in/app/mymeds-med-tracking-made-easy/id541882256

### VN-relevant
19. https://www.pharmacity.vn/page/the-le-chuong-trinh-the-thanh-vien
20. https://apps.apple.com/do/app/pharmacity-nh%C3%A0-thu%E1%BB%91c-uy-t%C3%ADn/id1414835869
21. https://apps.apple.com/vn/app/long-ch%C3%A2u-chuy%C3%AAn-gia-thu%E1%BB%91c/id1586071844
22. https://apps.apple.com/vn/app/youmed-%E1%BB%A9ng-d%E1%BB%A5ng-%C4%91%E1%BA%B7t-kh%C3%A1m/id1466077723

### Bổ sung benchmark scan pill bottle (ngoài shortlist ưu tiên)
23. https://carezone.com/

