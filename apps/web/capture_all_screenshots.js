const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.BASE_URL || 'https://theclaracare.com';
const OUTPUT_DIR = path.join(__dirname, '../../docs/ui-transformation-v3/screenshots');

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const PUBLIC_PAGES = [
  { name: '01_landing_home', path: '/', title: 'Trang chủ CLARA Care (Landing Page)' },
  { name: '02_auth_login', path: '/login', title: 'Màn hình Đăng nhập (Sign In)' },
  { name: '03_auth_register', path: '/register', title: 'Màn hình Đăng ký tài khoản (Sign Up)' },
  { name: '04_auth_forgot_password', path: '/forgot-password', title: 'Màn hình Quên mật khẩu' },
  { name: '05_auth_verify_email', path: '/verify-email', title: 'Màn hình Xác thực Email' },
  { name: '06_help_guide_center', path: '/huong-dan', title: 'Trung tâm Hướng dẫn & Trợ giúp (Guide Center)' },
  { name: '07_legal_terms', path: '/legal/terms', title: 'Điều khoản sử dụng (Terms of Service)' },
  { name: '08_legal_privacy', path: '/legal/privacy', title: 'Chính sách quyền riêng tư (Privacy Policy)' },
  { name: '09_legal_consent', path: '/legal/consent', title: 'Đồng thuận Y tế (Medical Consent)' },
];

const AUTH_PAGES = [
  // Consumer / Personal Experience
  { name: '10_consumer_today_dashboard', path: '/today', title: 'Bảng điều khiển Hôm nay (Today Dashboard)' },
  { name: '11_ask_clara_chat', path: '/chat', title: 'Trò chuyện & Hỏi CLARA (Ask CLARA Chat)' },
  { name: '12_medicines_hub', path: '/medicines', title: 'Trung tâm Quản lý Thuốc (Medicines Tri-Concept)' },
  { name: '13_medicines_add_flow', path: '/medicines/add', title: 'Thêm thuốc vào tủ (Add Medicine)' },
  { name: '14_phr_health_records', path: '/phr', title: 'Hồ sơ Sức khỏe Cá nhân (Personal Health Record)' },
  { name: '15_visits_preparation', path: '/visits', title: 'Chuẩn bị Khám & Lịch sử Khám (Visits)' },
  { name: '16_lifemap_journey', path: '/lifemap', title: 'Hành trình Sức khỏe LifeMap' },
  { name: '17_family_sharing', path: '/family', title: 'Chia sẻ Gia đình & Vòng Chăm sóc (Family Circle)' },
  { name: '18_profile_you_overview', path: '/you', title: 'Tổng quan Hồ sơ & Thẻ Cấp Cứu Bento Grid' },
  { name: '19_privacy_ai_transparency', path: '/you/privacy', title: 'Trung tâm Quyền riêng tư & Minh bạch AI (Zero-CoT)' },
  { name: '20_sharing_management', path: '/you/sharing', title: 'Quản lý Quyền Truy cập & Chia sẻ' },
  { name: '21_notifications_settings', path: '/you/notifications', title: 'Cài đặt Thông báo & Nhắc nhở' },
  { name: '22_connected_integrations', path: '/you/integrations', title: 'Thiết bị & Kết nối Dữ liệu (Integrations)' },

  // Clinical Experience (Doctor Workspace)
  { name: '23_clinical_command_center', path: '/clinical', title: 'Trung tâm Lâm sàng & Hội chẩn (Clinician Command Center)' },
  { name: '24_council_case_hub', path: '/council', title: 'Hội đồng Hội chẩn AI (Council Workspace)' },
  { name: '25_council_new_case', path: '/council/new', title: 'Khởi tạo Ca Hội chẩn Mới (New Council Case)' },
  { name: '26_council_intake_form', path: '/council/new/intake', title: 'Nhập liệu Bệnh sử & Triệu chứng Ca bệnh' },
  { name: '27_council_specialists_select', path: '/council/new/specialists', title: 'Lựa chọn Hội đồng Chuyên khoa' },
  { name: '28_council_review_checklist', path: '/council/new/review', title: 'Xem lại Ca bệnh trước khi Deliberate' },
  { name: '29_scribe_clinical_notes', path: '/scribe', title: 'Ghi chép Khám Lâm sàng SOAP (CLARA Scribe)' },
  { name: '30_living_evidence_workspace', path: '/evidence', title: 'Không gian Bằng chứng Sống (Living Evidence)' },
  { name: '31_research_sources_hub', path: '/research/source-hub', title: 'Trung tâm Nguồn Tri thức Y khoa' },

  // Administration Experience (Admin Workspace)
  { name: '32_admin_system_overview', path: '/admin/overview', title: 'Tổng quan Quản trị Hệ thống (Admin Overview)' },
  { name: '33_admin_observability', path: '/admin/observability', title: 'Giám sát & Đo kiểm Telemetry (Observability)' },
  { name: '34_admin_audit_log', path: '/admin/audit-log', title: 'Nhật ký Kiểm toán Bất biến (Audit Log)' },
  { name: '35_admin_dsar_requests', path: '/admin/dsar', title: 'Xử lý Yêu cầu Dữ liệu Cá nhân (DSAR)' },
  { name: '36_admin_knowledge_sources', path: '/admin/knowledge-sources', title: 'Quản lý Nguồn Tri thức & Ingestion' },
  { name: '37_admin_rag_ingestion', path: '/admin/rag-ingestion', title: 'Tiến trình Nhập liệu & Chỉ mục RAG' },
];

async function run() {
  console.log(`🚀 Starting screenshot capture from: ${BASE_URL}`);
  console.log(`📁 Saving to directory: ${OUTPUT_DIR}\n`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const capturedScreenshots = [];

  // 1. Capture Public Pages (Desktop & Mobile)
  console.log('--- 1. Capturing Public Pages ---');
  for (const item of PUBLIC_PAGES) {
    const targetUrl = `${BASE_URL}${item.path}`;
    console.log(`📸 [Public] ${item.title} -> ${item.path}`);

    // Desktop
    const desktopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    });
    const desktopPage = await desktopContext.newPage();
    try {
      await desktopPage.goto(targetUrl, { waitUntil: 'networkidle', timeout: 20000 });
      await desktopPage.waitForTimeout(1000);
      const desktopFile = `${item.name}_desktop.png`;
      await desktopPage.screenshot({
        path: path.join(OUTPUT_DIR, desktopFile),
        fullPage: true
      });
      capturedScreenshots.push({
        ...item,
        desktopFile,
        type: 'Public'
      });
    } catch (e) {
      console.error(`  ❌ Desktop failed for ${item.path}: ${e.message}`);
    } finally {
      await desktopContext.close();
    }

    // Mobile
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
      isMobile: true,
      hasTouch: true
    });
    const mobilePage = await mobileContext.newPage();
    try {
      await mobilePage.goto(targetUrl, { waitUntil: 'networkidle', timeout: 20000 });
      await mobilePage.waitForTimeout(1000);
      const mobileFile = `${item.name}_mobile.png`;
      await mobilePage.screenshot({
        path: path.join(OUTPUT_DIR, mobileFile),
        fullPage: true
      });
      const last = capturedScreenshots[capturedScreenshots.length - 1];
      if (last && last.name === item.name) {
        last.mobileFile = mobileFile;
      }
    } catch (e) {
      console.error(`  ❌ Mobile failed for ${item.path}: ${e.message}`);
    } finally {
      await mobileContext.close();
    }
  }

  // 2. Perform Login and Setup Authenticated Context
  console.log('\n--- 2. Authenticating as Admin/Doctor ---');
  const authContext = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const loginPage = await authContext.newPage();
  try {
    await loginPage.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 20000 });
    await loginPage.fill('#login-email', 'admin@example.com');
    await loginPage.fill('#login-password', 'Clara!f370141b91b75163c792411f3e4f44ebb6c90d2142c29a47');
    await loginPage.click('button[type="submit"]');
    await loginPage.waitForTimeout(2500);
    console.log('✅ Logged in successfully!');
  } catch (e) {
    console.error('❌ Login failed:', e.message);
  }

  const storageState = await authContext.storageState();
  await authContext.close();

  // 3. Capture Authenticated Pages
  console.log('\n--- 3. Capturing Authenticated Pages ---');
  for (const item of AUTH_PAGES) {
    const targetUrl = `${BASE_URL}${item.path}`;
    console.log(`📸 [Auth] ${item.title} -> ${item.path}`);

    // Desktop
    const desktopContext = await browser.newContext({
      storageState,
      viewport: { width: 1440, height: 900 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    });
    const desktopPage = await desktopContext.newPage();
    try {
      await desktopPage.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await desktopPage.waitForTimeout(2000);
      const desktopFile = `${item.name}_desktop.png`;
      await desktopPage.screenshot({
        path: path.join(OUTPUT_DIR, desktopFile),
        fullPage: true
      });
      capturedScreenshots.push({
        ...item,
        desktopFile,
        type: 'Authenticated'
      });
    } catch (e) {
      console.error(`  ❌ Desktop failed for ${item.path}: ${e.message}`);
    } finally {
      await desktopContext.close();
    }

    // Mobile
    const mobileContext = await browser.newContext({
      storageState,
      viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
      isMobile: true,
      hasTouch: true
    });
    const mobilePage = await mobileContext.newPage();
    try {
      await mobilePage.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await mobilePage.waitForTimeout(2000);
      const mobileFile = `${item.name}_mobile.png`;
      await mobilePage.screenshot({
        path: path.join(OUTPUT_DIR, mobileFile),
        fullPage: true
      });
      const last = capturedScreenshots[capturedScreenshots.length - 1];
      if (last && last.name === item.name) {
        last.mobileFile = mobileFile;
      }
    } catch (e) {
      console.error(`  ❌ Mobile failed for ${item.path}: ${e.message}`);
    } finally {
      await mobileContext.close();
    }
  }

  await browser.close();

  // 4. Generate Catalog Index Markdown
  console.log('\n--- 4. Generating Index Catalog ---');
  let indexMd = `# CLARA Care — Toàn Bộ Ảnh Chụp Giao Diện (Screenshots Catalog)

**Hệ thống:** CLARA Care (Next.js 15 + Tailwind CSS + CLARA Spatial Care v3.0)  
**Địa chỉ Live:** [https://theclaracare.com/](https://theclaracare.com/)  
**Thời gian chụp:** ${new Date().toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}  
**Thư mục lưu trữ:** \`docs/ui-transformation-v3/screenshots/\`  

---

## Danh Sách Chi Tiết Các Màn Hình

| STT | Tên Màn Hình / Chức Năng | Đường Dẫn (Route) | Phân Loại | Ảnh Desktop (1440px) | Ảnh Mobile (390px) |
|---|---|---|---|:---:|:---:|
`;

  capturedScreenshots.forEach((item, idx) => {
    const desktopLink = item.desktopFile ? `[Xem ảnh](${item.desktopFile})` : '-';
    const mobileLink = item.mobileFile ? `[Xem ảnh](${item.mobileFile})` : '-';
    indexMd += `| ${idx + 1} | **${item.title}** | \`${item.path}\` | ${item.type} | ${desktopLink} | ${mobileLink} |\n`;
  });

  indexMd += `
---

## Xem Trước Một Số Màn Hình Trọng Tâm

### 1. Bảng Điều Khiển "Hôm Nay" (Today Dashboard)
![Today Dashboard](10_consumer_today_dashboard_desktop.png)

### 2. Trung Tâm Lâm Sàng Bác Sĩ (Clinician Command Center)
![Clinical Command Center](23_clinical_command_center_desktop.png)

### 3. Hội Đồng Hội Chẩn AI (Council Workspace)
![Council Workspace](24_council_case_hub_desktop.png)

### 4. Ghi Chép Khám Lâm Sàng SOAP (CLARA Scribe)
![Scribe SOAP](29_scribe_clinical_notes_desktop.png)

### 5. Hồ Sơ & Thẻ Cấp Cứu Bento Grid (Emergency Medical Card)
![Profile Overview](18_profile_you_overview_desktop.png)
`;

  fs.writeFileSync(path.join(OUTPUT_DIR, 'INDEX.md'), indexMd);
  console.log('✅ Generated INDEX.md successfully!');
  console.log(`🎉 Total screens captured: ${capturedScreenshots.length * 2} screenshot files.`);
}

run().catch(console.error);
