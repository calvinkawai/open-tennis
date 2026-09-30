import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

const publicAssets = new Set([
  "/sw.js", "/offline.html", "/manifest.webmanifest", "/icon.svg", "/brand.svg",
  "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png",
]);

function equalSecret(left: string, right: string) {
  return timingSafeEqual(
    createHash("sha256").update(left).digest(),
    createHash("sha256").update(right).digest(),
  );
}

function isOwner(header: string | null, username: string, password: string) {
  if (!header || header.length > 4096) return false;
  const match = /^Basic ([A-Za-z0-9+/]+={0,2})$/i.exec(header);
  if (!match) return false;
  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.from(match[1], "base64"));
  } catch {
    return false;
  }
  const separator = decoded.indexOf(":");
  if (separator < 0) return false;
  const validUsername = equalSecret(decoded.slice(0, separator), username);
  const validPassword = equalSecret(decoded.slice(separator + 1), password);
  return validUsername && validPassword;
}

function accessPage(status: 401 | 503) {
  const setup = status === 503;
  const title = setup ? "尚未完成私有访问设置" : "只属于你的球场手册";
  const text = setup
    ? "服务端尚未设置 OWNER_PASSWORD。请由部署者在运行环境配置本人访问密码后重启服务。密码不会发送到页面。"
    : "请在浏览器的身份验证窗口输入本人用户名与密码。Open Tennis 没有公开注册入口。";
  return new NextResponse(`<!doctype html><html lang="zh-CN"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>${title} · Open Tennis</title>
    <style>body{margin:0;background:#172928;color:#eef0df;font:17px/1.8 system-ui,sans-serif}
    main{max-width:40rem;margin:15vh auto;padding:2rem}small{color:#d9c17d;letter-spacing:.16em}
    h1{font-size:clamp(1.8rem,5vw,2.6rem);font-weight:550}p{color:#becdc4}a{display:inline-flex;
    align-items:center;min-height:44px;color:#deedae;padding:.25rem 1rem;border:1px solid #6b806f;
    border-radius:8px}a:focus-visible{outline:3px solid #d9c17d}</style>
    <main><small>OPEN TENNIS / PRIVATE</small><h1>${title}</h1><p>${text}</p>
    <a href="/">重新打开</a></main></html>`, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      ...(setup ? {} : { "WWW-Authenticate": 'Basic realm="Open Tennis", charset="UTF-8"' }),
    },
  });
}

export function proxy(request: NextRequest) {
  if (publicAssets.has(request.nextUrl.pathname)) return NextResponse.next();
  const password = process.env.OWNER_PASSWORD;
  if (!password) return accessPage(503);
  if (!isOwner(request.headers.get("authorization"), process.env.OWNER_USERNAME || "owner", password)) {
    return accessPage(401);
  }
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = { matcher: ["/((?!_next/static/).*)"] };
