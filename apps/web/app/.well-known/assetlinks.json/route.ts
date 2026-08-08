import { NextResponse } from "next/server";

const FINGERPRINT = /^(?:[A-Fa-f0-9]{2}:){31}[A-Fa-f0-9]{2}$/;

/**
 * Android App Links verification. The certificate fingerprint is public
 * release metadata, but it must be supplied from deployment configuration so
 * this repository never invents or ships a debug-key association.
 */
export function GET() {
  const fingerprint = (process.env.ANDROID_APP_LINK_CERT_SHA256 ?? "")
    .trim()
    .toUpperCase();
  if (!FINGERPRINT.test(fingerprint)) {
    return new NextResponse(null, {
      status: 404,
      headers: { "Cache-Control": "no-store" },
    });
  }

  return NextResponse.json(
    [
      {
        relation: ["delegate_permission/common.handle_all_urls"],
        target: {
          namespace: "android_app",
          package_name: "com.theclaracare.app",
          sha256_cert_fingerprints: [fingerprint],
        },
      },
    ],
    {
      headers: {
        "Cache-Control": "public, max-age=300, must-revalidate",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
