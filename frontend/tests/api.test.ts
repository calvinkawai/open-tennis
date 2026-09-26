import { describe, expect, it } from "vitest";
import { ApiClient, ApiError } from "../src/lib/api";

describe("same-origin API boundary", () => {
  it("announces unreachable transport without claiming the operation succeeded", async () => {
    let announced = 0;
    const listener = () => { announced += 1; };
    window.addEventListener("open-tennis:connection-lost", listener);
    try {
      const api = new ApiClient(async () => { throw new TypeError("network unavailable"); });
      await expect(api.status()).rejects.toMatchObject({ status: 0 });
      expect(announced).toBe(1);
    } finally {
      window.removeEventListener("open-tennis:connection-lost", listener);
    }
  });
  it("shows an unauthorized state even when the auth gateway returns HTML", async () => {
    const api = new ApiClient(async () =>
      new Response("<html>Private gateway</html>", {
        status: 401,
        headers: { "content-type": "text/html" },
      }),
    );

    await expect(api.listWiki("technical")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "访问验证已失效。请重新验证本人身份。",
    });
    await expect(api.listWiki("technical")).rejects.toBeInstanceOf(ApiError);
  });

  it("opens opaque source IDs without interpreting them as path or query syntax", async () => {
    const requests: { url: string; init: RequestInit | undefined }[] = [];
    const api = new ApiClient(async (url, init) => {
      requests.push({ url: String(url), init });
      return Response.json({
        id: "source/a?b#c", kind: "technical", title: "测试来源", excerpt: "测试片段",
        revision: "source-v1", source_url: null, content: "测试原文",
      });
    });
    expect((await api.evidence("source/a?b#c")).content).toBe("测试原文");
    expect(requests[0].url).toBe("/api/v1/evidence/source%2Fa%3Fb%23c");
    expect(requests[0].init).toMatchObject({ credentials: "include", cache: "no-store" });
    expect(new Headers(requests[0].init?.headers).has("Authorization")).toBe(false);
  });
});
