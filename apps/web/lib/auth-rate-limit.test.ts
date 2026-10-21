import { beforeEach, describe, expect, it } from "vitest";
import {
  RATE_LIMIT_CONFIG,
  clearAllAuthRateLimits,
  extractRetryAfter,
  getAuthCooldownRemaining,
  getAuthRateLimitRecord,
  isRateLimitOrLockoutError,
  normalizeAuthIdentifier,
  recordAuthFailure,
  recordAuthSuccess,
  setAuthCaptchaSolved,
} from "./auth-rate-limit";

describe("auth-rate-limit module", () => {
  beforeEach(() => {
    clearAllAuthRateLimits();
  });

  describe("normalizeAuthIdentifier", () => {
    it("lowercases and trims emails", () => {
      expect(normalizeAuthIdentifier("  User@Example.COM  ")).toBe("user@example.com");
    });

    it("returns anonymous for empty or undefined identifiers", () => {
      expect(normalizeAuthIdentifier("")).toBe("anonymous");
      expect(normalizeAuthIdentifier(null)).toBe("anonymous");
      expect(normalizeAuthIdentifier(undefined)).toBe("anonymous");
    });
  });

  describe("extractRetryAfter", () => {
    it("extracts direct retryAfter numeric property", () => {
      expect(extractRetryAfter({ retryAfter: 45 })).toBe(45);
    });

    it("extracts retry_after_seconds from response data", () => {
      const err = { response: { data: { retry_after_seconds: 60 } } };
      expect(extractRetryAfter(err)).toBe(60);
    });

    it("extracts Retry-After header string", () => {
      const err = { response: { headers: { "retry-after": "120" } } };
      expect(extractRetryAfter(err)).toBe(120);
    });

    it("parses Vietnamese retry text from message", () => {
      const err = new Error("Tạm khóa đăng nhập do quá nhiều lần thử sai. Thử lại sau 60s");
      expect(extractRetryAfter(err)).toBe(60);
    });

    it("parses English retry text from message", () => {
      const err = new Error("Rate limit exceeded. Try again in 30 seconds");
      expect(extractRetryAfter(err)).toBe(30);
    });

    it("returns null when no retry info is present", () => {
      expect(extractRetryAfter(new Error("Sai mật khẩu"))).toBeNull();
      expect(extractRetryAfter(null)).toBeNull();
    });
  });

  describe("isRateLimitOrLockoutError", () => {
    it("identifies 429 HTTP status", () => {
      const res = isRateLimitOrLockoutError({ status: 429 });
      expect(res.isRateLimited).toBe(true);
    });

    it("identifies lockout messages and extracts retry duration", () => {
      const res = isRateLimitOrLockoutError(
        new Error("Tạm khóa đăng nhập do quá nhiều lần thử sai. Thử lại sau 60s"),
      );
      expect(res.isRateLimited).toBe(true);
      expect(res.isLockedOut).toBe(true);
      expect(res.retryAfter).toBe(60);
    });

    it("does not flag regular credential failure as rate limited", () => {
      const res = isRateLimitOrLockoutError(new Error("Sai email hoặc mật khẩu"));
      expect(res.isRateLimited).toBe(false);
      expect(res.isLockedOut).toBe(false);
      expect(res.retryAfter).toBeNull();
    });
  });

  describe("Progressive delay escalation and lockout", () => {
    const testEmail = "test@example.com";

    it("progressively increases delay with each failure", () => {
      // 1st failure: 0s
      const f1 = recordAuthFailure("login", testEmail);
      expect(f1.failedCount).toBe(1);
      expect(f1.cooldownSeconds).toBe(0);
      expect(f1.captchaRequired).toBe(false);
      expect(f1.isLockedOut).toBe(false);

      // 2nd failure: 1s
      const f2 = recordAuthFailure("login", testEmail);
      expect(f2.failedCount).toBe(2);
      expect(f2.cooldownSeconds).toBe(1);
      expect(f2.captchaRequired).toBe(false);

      // 3rd failure: 3s + captcha required
      const f3 = recordAuthFailure("login", testEmail);
      expect(f3.failedCount).toBe(3);
      expect(f3.cooldownSeconds).toBe(3);
      expect(f3.captchaRequired).toBe(true);

      // 4th failure: 5s
      const f4 = recordAuthFailure("login", testEmail);
      expect(f4.failedCount).toBe(4);
      expect(f4.cooldownSeconds).toBe(5);
      expect(f4.captchaRequired).toBe(true);

      // 5th failure: 30s extended lockout
      const f5 = recordAuthFailure("login", testEmail);
      expect(f5.failedCount).toBe(5);
      expect(f5.cooldownSeconds).toBe(RATE_LIMIT_CONFIG.EXTENDED_LOCKOUT_SECONDS);
      expect(f5.isLockedOut).toBe(true);
    });

    it("honors server retry-after override and enters lockout", () => {
      const result = recordAuthFailure("login", testEmail, 60);
      expect(result.cooldownSeconds).toBe(60);
      expect(result.isLockedOut).toBe(true);
      const remaining = getAuthCooldownRemaining("login", testEmail);
      expect(remaining).toBeGreaterThanOrEqual(58);
      expect(remaining).toBeLessThanOrEqual(60);
    });

    it("maintains separate failure state for login and otp contexts", () => {
      recordAuthFailure("login", testEmail);
      recordAuthFailure("login", testEmail);

      const loginRecord = getAuthRateLimitRecord("login", testEmail);
      const otpRecord = getAuthRateLimitRecord("otp", testEmail);

      expect(loginRecord.failedCount).toBe(2);
      expect(otpRecord.failedCount).toBe(0);
    });

    it("invalidates captcha solution on subsequent failure", () => {
      recordAuthFailure("login", testEmail);
      recordAuthFailure("login", testEmail);
      recordAuthFailure("login", testEmail);

      setAuthCaptchaSolved("login", testEmail, true);
      let record = getAuthRateLimitRecord("login", testEmail);
      expect(record.captchaSolved).toBe(true);

      recordAuthFailure("login", testEmail);
      record = getAuthRateLimitRecord("login", testEmail);
      expect(record.captchaSolved).toBe(false);
    });

    it("clears rate limit state on successful authentication", () => {
      recordAuthFailure("login", testEmail);
      recordAuthFailure("login", testEmail);
      recordAuthFailure("login", testEmail);

      expect(getAuthRateLimitRecord("login", testEmail).failedCount).toBe(3);

      recordAuthSuccess("login", testEmail);

      const cleared = getAuthRateLimitRecord("login", testEmail);
      expect(cleared.failedCount).toBe(0);
      expect(cleared.lockedUntil).toBe(0);
      expect(cleared.captchaRequired).toBe(false);
    });
  });
});
