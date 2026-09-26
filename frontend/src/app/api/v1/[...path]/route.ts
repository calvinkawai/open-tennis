import { type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function failure(status: number, code: string) {
  return Response.json({ detail: "Backend request could not be completed.", code }, {
    status, headers: { "Cache-Control": "no-store" },
  });
}

async function forward(request: NextRequest) {
  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    const expectedOrigin = process.env.PUBLIC_ORIGIN ||
      `${request.nextUrl.protocol}//${request.headers.get("host") || request.nextUrl.host}`;
    if (request.headers.get("sec-fetch-site") === "cross-site" ||
        (origin && origin !== expectedOrigin.replace(/\/$/, ""))) return failure(403, "origin_rejected");
    if (!request.headers.get("content-type")?.startsWith("application/json")) return failure(415, "json_required");
  }
  let origin: URL;
  try {
    origin = new URL(process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000");
    if (!["http:", "https:"].includes(origin.protocol) || origin.username || origin.password ||
      origin.pathname !== "/" || origin.search || origin.hash) return failure(503, "backend_configuration");
  } catch {
    return failure(503, "backend_configuration");
  }
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, origin);
  const headers = new Headers({ Accept: "application/json" });
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("Authorization", authorization);
  for (const name of ["origin", "sec-fetch-site"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  let body: string | undefined;
  if (request.method !== "GET") {
    body = await request.text();
    if (new TextEncoder().encode(body).byteLength > 1_048_576) return failure(413, "body_too_large");
    headers.set("Content-Type", "application/json");
  }
  try {
    const response = await fetch(target, {
      method: request.method, headers, body, cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(120_000)]),
    });
    if (response.status >= 300 && response.status < 400) return failure(502, "unexpected_redirect");
    const outgoing = new Headers({
      "Content-Type": response.headers.get("content-type") || "application/json",
      "Cache-Control": "private, no-store",
    });
    for (const header of ["www-authenticate", "x-request-id"]) {
      const value = response.headers.get(header);
      if (value) outgoing.set(header, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch (error) {
    return failure(
      error instanceof DOMException && error.name === "TimeoutError" ? 504 : 502,
      "backend_unavailable",
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
