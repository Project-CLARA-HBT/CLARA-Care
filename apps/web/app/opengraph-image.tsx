import { ImageResponse } from "next/og";

export const alt = "✦ CLARA Care - Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "52px 60px",
          backgroundColor: "#020617",
          backgroundImage:
            "radial-gradient(circle at 90% 12%, rgba(14, 165, 233, 0.25) 0%, transparent 50%), " +
            "radial-gradient(circle at 10% 88%, rgba(2, 132, 199, 0.18) 0%, transparent 45%), " +
            "radial-gradient(circle at 50% 50%, rgba(56, 189, 248, 0.05) 0%, transparent 60%), " +
            "linear-gradient(135deg, #020617 0%, #081325 45%, #030712 100%)",
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Subtle decorative inner border */}
        <div
          style={{
            position: "absolute",
            top: 20,
            left: 20,
            right: 20,
            bottom: 20,
            borderRadius: "20px",
            border: "1px solid rgba(56, 189, 248, 0.15)",
            pointerEvents: "none",
            display: "flex",
          }}
        />

        {/* Header: Brand & Live Clinical Tag */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          {/* Brand: Glowing Jewel Icon + ✦ CLARA Care */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
            }}
          >
            {/* Jewel Icon */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "52px",
                height: "52px",
                borderRadius: "14px",
                backgroundColor: "rgba(14, 165, 233, 0.18)",
                border: "1.5px solid rgba(56, 189, 248, 0.6)",
                boxShadow:
                  "0 0 24px rgba(14, 165, 233, 0.4), inset 0 0 12px rgba(56, 189, 248, 0.2)",
              }}
            >
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
                <path
                  d="M6 3L18 3L22 9L12 22L2 9L6 3Z"
                  fill="url(#og-jewel-gradient)"
                  stroke="#38bdf8"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
                <path
                  d="M2 9H22M6 3L10 9L12 22L14 9L18 3"
                  stroke="#bae6fd"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                  strokeOpacity="0.85"
                />
                <defs>
                  <linearGradient
                    id="og-jewel-gradient"
                    x1="2"
                    y1="3"
                    x2="22"
                    y2="22"
                    gradientUnits="userSpaceOnUse"
                  >
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="50%" stopColor="#0284c7" />
                    <stop offset="100%" stopColor="#0369a1" />
                  </linearGradient>
                </defs>
              </svg>
            </div>

            {/* Brand Title */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                fontSize: "32px",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                color: "#ffffff",
              }}
            >
              <span
                style={{
                  color: "#38bdf8",
                  marginRight: "10px",
                  fontSize: "30px",
                  display: "flex",
                }}
              >
                ✦
              </span>
              <span>CLARA</span>
              <span
                style={{
                  marginLeft: "10px",
                  color: "#38bdf8",
                }}
              >
                Care
              </span>
            </div>
          </div>

          {/* Clinical Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 18px",
              borderRadius: "9999px",
              backgroundColor: "rgba(14, 165, 233, 0.12)",
              border: "1px solid rgba(56, 189, 248, 0.35)",
              color: "#7dd3fc",
              fontSize: "14px",
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#38bdf8",
                boxShadow: "0 0 10px #38bdf8",
                display: "flex",
              }}
            />
            <span>Clinical AI System</span>
          </div>
        </div>

        {/* Center Main Content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: "12px",
            marginBottom: "12px",
          }}
        >
          {/* Tagline pill */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              marginBottom: "18px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "6px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(56, 189, 248, 0.12)",
                border: "1px solid rgba(56, 189, 248, 0.28)",
                color: "#38bdf8",
                fontSize: "13px",
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Safety-First Medical AI
            </div>
          </div>

          {/* Headline */}
          <div
            style={{
              fontSize: "50px",
              fontWeight: 800,
              lineHeight: 1.18,
              letterSpacing: "-0.03em",
              color: "#ffffff",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <span>Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam</span>
          </div>

          {/* Subtitle */}
          <div
            style={{
              fontSize: "21px",
              fontWeight: 500,
              lineHeight: 1.45,
              color: "#94a3b8",
              marginTop: "16px",
              display: "flex",
              alignItems: "center",
            }}
          >
            <span>Kiểm chứng FIDES • Dược thư Quốc gia • LifeMap • SOAP Scribe • Bảo mật Zero-CoT</span>
          </div>

          {/* Feature Pills */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              marginTop: "32px",
            }}
          >
            {/* Pill 1: DDI Checker */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "12px 20px",
                borderRadius: "12px",
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(56, 189, 248, 0.35)",
                boxShadow: "0 4px 16px rgba(0, 0, 0, 0.3)",
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
                <path d="m8.5 8.5 7 7" />
              </svg>
              <span
                style={{
                  fontSize: "17px",
                  fontWeight: 600,
                  color: "#f0f9ff",
                }}
              >
                DDI Checker
              </span>
            </div>

            {/* Pill 2: Multidisciplinary Council */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "12px 20px",
                borderRadius: "12px",
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(56, 189, 248, 0.35)",
                boxShadow: "0 4px 16px rgba(0, 0, 0, 0.3)",
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
              <span
                style={{
                  fontSize: "17px",
                  fontWeight: 600,
                  color: "#f0f9ff",
                }}
              >
                Multidisciplinary Council
              </span>
            </div>

            {/* Pill 3: Living Evidence Hub */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "12px 20px",
                borderRadius: "12px",
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(56, 189, 248, 0.35)",
                boxShadow: "0 4px 16px rgba(0, 0, 0, 0.3)",
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
              <span
                style={{
                  fontSize: "17px",
                  fontWeight: 600,
                  color: "#f0f9ff",
                }}
              >
                Living Evidence Hub
              </span>
            </div>
          </div>
        </div>

        {/* Footer / Trust Bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            paddingTop: "18px",
            borderTop: "1px solid rgba(56, 189, 248, 0.15)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              color: "#38bdf8",
              fontSize: "16px",
              fontWeight: 600,
            }}
          >
            <span>theclaracare.com</span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              color: "#64748b",
              fontSize: "14px",
              fontWeight: 500,
            }}
          >
            <span>Chuẩn an toàn Y tế • Bảo mật Zero-PII • Bộ Y Tế & Dược Thư VN</span>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
