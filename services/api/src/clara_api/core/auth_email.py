from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from clara_api.core.config import Settings

logger = logging.getLogger(__name__)


def should_expose_action_token_preview(settings: Settings) -> bool:
    if settings.environment.lower() == "production":
        return False
    if settings.auth_expose_action_token_preview:
        return True
    return settings.auth_email_delivery_mode == "preview"


def _build_action_link(settings: Settings, action: str, token: str) -> str:
    if action == "verify_email":
        path = settings.auth_verify_email_path
    elif action == "reset_password":
        path = settings.auth_reset_password_path
    elif action == "login_otp":
        path = "/login"
    else:
        path = "/"
    base = settings.auth_public_web_base_url.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}?token={quote(token)}"


def _build_html_template(
    *,
    preheader: str,
    badge_text: str,
    title: str,
    greeting: str,
    message_paragraphs: list[str],
    highlight_code: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
    footer_note: str,
) -> str:
    """Renders a premier, responsive, medical-grade HTML email for CLARA Care."""
    paragraphs_html = "".join(
        f'<p style="margin: 0 0 16px 0; font-size: 15px; line-height: 24px; color: #334155;">{p}</p>'
        for p in message_paragraphs
    )

    highlight_box_html = ""
    if highlight_code:
        highlight_box_html = f"""
        <div style="margin: 24px 0; padding: 20px; background-color: #F0F7FF; border: 1px solid #BAE6FD; border-radius: 12px; text-align: center;">
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #0284C7; margin-bottom: 6px;">Mã xác thực bảo mật</div>
          <div style="font-size: 32px; font-weight: 800; letter-spacing: 0.25em; color: #0369A1; font-family: 'SF Mono', Consolas, Monaco, monospace;">{highlight_code}</div>
        </div>
        """

    cta_button_html = ""
    if cta_text and cta_url:
        cta_button_html = f"""
        <div style="margin: 28px 0 20px 0; text-align: center;">
          <!--[if mso]>
          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{cta_url}" style="height:48px;v-text-anchor:middle;width:240px;" arcsize="20%" stroke="f" fillcolor="#0284C7">
            <w:anchorlock/>
            <center style="color:#ffffff;font-family:sans-serif;font-size:15px;font-weight:bold;">{cta_text}</center>
          </v:roundrect>
          <![endif]-->
          <!--[if !mso]><!-->
          <a href="{cta_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #0284C7; color: #ffffff; font-size: 15px; font-weight: 600; text-decoration: none; padding: 13px 32px; border-radius: 10px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);">{cta_text} &rarr;</a>
          <!--<![endif]-->
        </div>
        <div style="margin: 0 0 20px 0; font-size: 12px; line-height: 18px; color: #64748B; text-align: center;">
          Nếu nút không hoạt động, sao chép liên kết này vào trình duyệt:<br>
          <a href="{cta_url}" target="_blank" rel="noopener noreferrer" style="color: #0284C7; word-break: break-all; text-decoration: underline;">{cta_url}</a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    @media only screen and (max-width: 600px) {{
      .email-container {{ width: 100% !important; padding: 16px !important; }}
      .email-card {{ padding: 24px 20px !important; border-radius: 12px !important; }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;">
  <div style="display: none; font-size: 1px; color: #F8FAFC; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
    {preheader}
  </div>

  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; padding: 40px 0;">
    <tr>
      <td align="center">
        <!-- Main Wrapper Container -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="560" class="email-container" style="max-width: 560px; width: 100%; margin: 0 auto;">
          <!-- Header Logo / Brand -->
          <tr>
            <td align="center" style="padding-bottom: 24px;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="vertical-align: middle;">
                    <div style="display: inline-block; width: 36px; height: 36px; background-color: #0284C7; border-radius: 10px; text-align: center; line-height: 36px; color: #FFFFFF; font-size: 20px; font-weight: 800;">+</div>
                  </td>
                  <td style="padding-left: 10px; vertical-align: middle;">
                    <span style="font-size: 20px; font-weight: 800; letter-spacing: 0.05em; color: #0F172A;">CLARA</span>
                    <span style="font-size: 14px; font-weight: 500; color: #64748B; margin-left: 4px;">Care</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main White Card -->
          <tr>
            <td>
              <div class="email-card" style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 36px 32px; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);">
                
                <!-- Badge Category -->
                <div style="display: inline-block; padding: 4px 10px; background-color: #E0F2FE; border-radius: 9999px; font-size: 12px; font-weight: 600; color: #0369A1; margin-bottom: 16px;">
                  {badge_text}
                </div>

                <!-- Title Heading -->
                <h1 style="margin: 0 0 20px 0; font-size: 22px; font-weight: 700; color: #0F172A; line-height: 30px;">
                  {title}
                </h1>

                <!-- Salutation -->
                <p style="margin: 0 0 16px 0; font-size: 15px; font-weight: 600; color: #1E293B;">
                  {greeting}
                </p>

                <!-- Body Content Paragraphs -->
                {paragraphs_html}

                <!-- Highlight Code (e.g. OTP) -->
                {highlight_box_html}

                <!-- CTA Button (e.g. Verify Link) -->
                {cta_button_html}

                <!-- Security & Notice Footer in Card -->
                <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #F1F5F9; font-size: 13px; line-height: 20px; color: #64748B;">
                  {footer_note}
                </div>
              </div>
            </td>
          </tr>

          <!-- Footer Metadata -->
          <tr>
            <td align="center" style="padding-top: 28px; font-size: 12px; line-height: 18px; color: #94A3B8; text-align: center;">
              <p style="margin: 0 0 6px 0;">
                &copy; 2026 CLARA Care &bull; Trợ lý Y tế Thông minh & An toàn Dữ liệu Sức khỏe
              </p>
              <p style="margin: 0; color: #CBD5E1;">
                Email được gửi tự động từ hệ thống bảo mật theclaracare.com. Vui lòng không trả lời thư này.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _build_message(
    action: str,
    *,
    action_link: str,
    token: str,
    settings: Settings,
) -> tuple[str, str, str]:
    """Returns (Subject, PlainTextBody, HtmlBody)."""
    if action == "login_otp":
        subject = f"[CLARA Care] Mã OTP đăng nhập của bạn: {token}"
        plain_text = (
            "Chào bạn,\n\n"
            f"Mã OTP đăng nhập CLARA của bạn là: {token}\n\n"
            f"Mã này có hiệu lực trong {settings.auth_login_otp_ttl_minutes} phút. "
            "Vì lý do an toàn, vui lòng tuyệt đối không chia sẻ mã này cho bất kỳ ai.\n\n"
            "Nếu bạn không yêu cầu đăng nhập, hãy đổi mật khẩu ngay lập tức.\n\n"
            "— Đội ngũ CLARA Care"
        )
        html_body = _build_html_template(
            preheader=f"Mã OTP đăng nhập của bạn là {token}. Hiệu lực trong {settings.auth_login_otp_ttl_minutes} phút.",
            badge_text="Bảo mật Đăng nhập",
            title="Mã OTP Xác Thực Đăng Nhập",
            greeting="Kính chào Quý người dùng,",
            message_paragraphs=[
                "Bạn hoặc ai đó đang thực hiện đăng nhập vào tài khoản <strong>CLARA Care</strong>.",
                f"Vui lòng sử dụng mã OTP dưới đây để hoàn tất quá trình xác thực. Mã có hiệu lực trong vòng <strong>{settings.auth_login_otp_ttl_minutes} phút</strong>.",
            ],
            highlight_code=token,
            footer_note="<strong>Lưu ý an toàn:</strong> Không chia sẻ mã xác thực này cho bất kỳ ai, kể cả nhân viên hỗ trợ CLARA. Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua thư hoặc đổi mật khẩu.",
        )
        return subject, plain_text, html_body

    if action == "verify_email":
        subject = "[CLARA Care] Xác thực email để kích hoạt tài khoản của bạn"
        plain_text = (
            "Chào bạn,\n\n"
            "Cảm ơn bạn đã đăng ký tài khoản tại CLARA Care.\n"
            f"Vui lòng bấm vào liên kết sau để xác thực email và kích hoạt tài khoản:\n{action_link}\n\n"
            f"Liên kết có hiệu lực trong vòng {settings.auth_action_token_ttl_minutes} phút.\n"
            "Nếu bạn không tạo tài khoản này, vui lòng bỏ qua email.\n\n"
            "— Đội ngũ CLARA Care"
        )
        html_body = _build_html_template(
            preheader="Kích hoạt tài khoản CLARA Care của bạn để bắt đầu sử dụng trợ lý y tế.",
            badge_text="Kích hoạt tài khoản",
            title="Chào mừng bạn đến với CLARA Care",
            greeting="Kính chào Quý người dùng,",
            message_paragraphs=[
                "Cảm ơn bạn đã tin tưởng và đăng ký sử dụng <strong>CLARA Care</strong> — Trợ lý sức khỏe thông minh và bảo mật dành cho người Việt.",
                f"Để hoàn tất thiết lập và bảo vệ dữ liệu y tế cá nhân, vui lòng bấm nút xác thực email dưới đây. Liên kết có hiệu lực trong <strong>{settings.auth_action_token_ttl_minutes} phút</strong>.",
            ],
            cta_text="Xác Thực Tài Khoản Ngay",
            cta_url=action_link,
            footer_note="<strong>Bảo vệ quyền riêng tư:</strong> CLARA Care tuân thủ nghiêm ngặt quy chuẩn bảo mật y tế và bảo vệ dữ liệu cá nhân (PDPD). Nếu bạn không đăng ký tài khoản này, hãy an tâm bỏ qua thư.",
        )
        return subject, plain_text, html_body

    subject = "[CLARA Care] Yêu cầu đặt lại mật khẩu tài khoản"
    plain_text = (
        "Chào bạn,\n\n"
        "Hệ thống vừa nhận được yêu cầu đặt lại mật khẩu cho tài khoản CLARA Care của bạn.\n"
        f"Vui lòng truy cập liên kết sau để tạo mật khẩu mới:\n{action_link}\n\n"
        f"Liên kết có hiệu lực trong vòng {settings.auth_action_token_ttl_minutes} phút.\n"
        "Nếu bạn không gửi yêu cầu này, vui lòng bỏ qua thư. Mật khẩu hiện tại của bạn vẫn được bảo vệ.\n\n"
        "— Đội ngũ CLARA Care"
    )
    html_body = _build_html_template(
        preheader="Yêu cầu đặt lại mật khẩu tài khoản CLARA Care.",
        badge_text="Khôi phục tài khoản",
        title="Đặt Lại Mật Khẩu CLARA",
        greeting="Kính chào Quý người dùng,",
        message_paragraphs=[
            "Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản CLARA Care liên kết với địa chỉ email này.",
            f"Vui lòng nhấn vào nút bên dưới để tiến hành tạo mật khẩu mới an toàn. Liên kết có hiệu lực trong <strong>{settings.auth_action_token_ttl_minutes} phút</strong>.",
        ],
        cta_text="Đặt Lại Mật Khẩu",
        cta_url=action_link,
        footer_note="<strong>Lưu ý bảo mật:</strong> Nếu bạn không gửi yêu cầu này, có thể ai đó đã nhập nhầm email của bạn. Mật khẩu hiện tại của bạn vẫn hoàn toàn an toàn và không bị thay đổi.",
    )
    return subject, plain_text, html_body


def _send_via_smtp(
    settings: Settings,
    *,
    recipient: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> str:
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP missing host/from email; auth email skipped")
        return "failed"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"CLARA Care <{settings.smtp_from_email}>"
    msg["To"] = recipient

    # Set multipart alternative: plain text fallback + high-fidelity responsive HTML
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        logger.warning(
            "SMTP authentication failed (host=%s, port=%d, username=%s): %s. "
            "If using Gmail, an App Password may be required.",
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            exc,
        )
        return "failed"
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send auth email")
        return "failed"
    return "sent"


def dispatch_action_email(
    settings: Settings,
    *,
    action: str,
    recipient: str,
    token: str,
) -> str:
    mode = settings.auth_email_delivery_mode
    link = _build_action_link(settings, action=action, token=token)
    subject, plain_body, html_body = _build_message(
        action, action_link=link, token=token, settings=settings
    )

    if mode == "disabled":
        return "disabled"

    if mode == "preview":
        logger.info("auth email preview dispatched action=%s", action)
        return "preview"

    return _send_via_smtp(
        settings,
        recipient=recipient,
        subject=subject,
        plain_body=plain_body,
        html_body=html_body,
    )
