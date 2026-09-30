import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "../src/app/api/v1/[...path]/route";

afterEach(() => vi.unstubAllGlobals());

it("accepts a same-site write using the real host instead of Next's internal hostname", async () => {
  const upstream = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ imported: 1, unchanged: 0 }));
  vi.stubGlobal("fetch", upstream);
  const request = new NextRequest("http://localhost:3188/api/v1/wiki/import", {
    method: "POST",
    headers: {
      host: "127.0.0.1:3188", origin: "http://127.0.0.1:3188",
      "content-type": "application/json", "sec-fetch-site": "same-origin",
    },
    body: "{}",
  });
  const response = await POST(request);
  expect(response.status).toBe(200);
  expect(upstream).toHaveBeenCalledOnce();
});

it("rejects cross-site writes without contacting the backend", async () => {
  const upstream = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", upstream);
  const response = await POST(new NextRequest("http://localhost:3188/api/v1/wiki/import", {
    method: "POST", body: "{}",
    headers: { host: "localhost:3188", origin: "https://outside.invalid", "content-type": "application/json" },
  }));
  expect(response.status).toBe(403);
  expect(upstream).not.toHaveBeenCalled();
});
