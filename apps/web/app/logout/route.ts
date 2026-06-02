import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const SERVER_API_BASE = (process.env.NEXT_SERVER_API_PROXY || "http://api:8000/api/v1").replace(/\/+$/, "");
const COOKIE_PATH = process.env.AUTH_COOKIE_PATH?.trim() || "/";
const COOKIE_DOMAIN = process.env.AUTH_COOKIE_DOMAIN?.trim() || undefined;
const ACCESS_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_ACCESS_COOKIE?.trim() || "clara_access_token";
const REFRESH_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_REFRESH_COOKIE?.trim() || "clara_refresh_token";
const CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_CSRF_COOKIE?.trim() || "clara_csrf_token";
const CLIENT_SESSION_COOKIE_NAME =
  process.env.NEXT_PUBLIC_AUTH_CLIENT_SESSION_COOKIE?.trim() || "clara_client_session";
const CLEAR_COOKIE_NAMES = [
  ACCESS_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  CSRF_COOKIE_NAME,
  CLIENT_SESSION_COOKIE_NAME,
];

async function bestEffortApiLogout(request: NextRequest): Promise<void> {
  const cookie = request.headers.get("cookie");
  if (!cookie) {
    return;
  }

  try {
    await fetch(`${SERVER_API_BASE}/auth/logout`, {
      method: "POST",
      headers: { cookie },
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    // Local cookie clearing below is the critical step for logout consistency.
  }
}

function expireCookie(response: NextResponse, request: NextRequest, name: string): void {
  response.cookies.set({
    name,
    value: "",
    expires: new Date(0),
    path: COOKIE_PATH,
    domain: COOKIE_DOMAIN,
    secure: request.nextUrl.protocol === "https:",
    sameSite: "lax",
  });
}

async function handleLogout(request: NextRequest): Promise<NextResponse> {
  await bestEffortApiLogout(request);

  const response = new NextResponse(null, { status: 303 });
  response.headers.set("Location", "/login");
  for (const name of CLEAR_COOKIE_NAMES) {
    expireCookie(response, request, name);
  }
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  return handleLogout(request);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  return handleLogout(request);
}
