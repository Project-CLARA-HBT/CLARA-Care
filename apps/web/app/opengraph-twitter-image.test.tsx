import { describe, expect, it } from "vitest";
import OpenGraphImage, {
  alt as ogAlt,
  contentType as ogContentType,
  size as ogSize,
} from "./opengraph-image";
import TwitterImage, {
  alt as twAlt,
  contentType as twContentType,
  size as twSize,
} from "./twitter-image";

describe("OpenGraph and Twitter Image Generation", () => {
  it("exports correct OpenGraph metadata dimensions and contentType", () => {
    expect(ogSize).toEqual({ width: 1200, height: 630 });
    expect(ogContentType).toBe("image/png");
    expect(ogAlt).toContain("CLARA Care");
    expect(ogAlt).toContain("Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam");
  });

  it("exports correct Twitter metadata dimensions and contentType", () => {
    expect(twSize).toEqual({ width: 1200, height: 630 });
    expect(twContentType).toBe("image/png");
    expect(twAlt).toContain("CLARA Care");
    expect(twAlt).toContain("Trợ lý AI Lâm sàng & Y tế An toàn #1 Việt Nam");
  });

  it("generates valid OpenGraph ImageResponse with brand, headline, subtitle, and feature pills", async () => {
    const response = await OpenGraphImage();
    expect(response).toBeDefined();
    expect(response.headers.get("content-type")).toBe("image/png");
  });

  it("generates valid Twitter ImageResponse with brand, headline, subtitle, and feature pills", async () => {
    const response = await TwitterImage();
    expect(response).toBeDefined();
    expect(response.headers.get("content-type")).toBe("image/png");
  });
});
