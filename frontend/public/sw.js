const CACHE = "open-tennis-shell-v1";
const PUBLIC_FILES = ["/offline.html", "/manifest.webmanifest", "/icon.svg", "/icon-192.png",
  "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png"];
const CACHE_PREFIX = "open-tennis-shell-";

function cacheKey(url) {
  return new Request(url, { method: "GET", credentials: "omit" });
}

async function storeResponse(url, response) {
  const cache = await caches.open(CACHE);
  await cache.put(cacheKey(url), response);
  const entries = await cache.keys();
  const assets = entries.filter((entry) => new URL(entry.url).pathname.startsWith("/_next/static/"));
  for (const entry of assets.slice(0, Math.max(0, assets.length - 80))) await cache.delete(entry);
}

async function reportFailure(code) {
  const pages = await self.clients.matchAll({ type: "window" });
  for (const page of pages) page.postMessage({ type: "OFFLINE_ERROR", code });
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (const path of PUBLIC_FILES) {
      const response = await fetch(path, { credentials: "omit" });
      if (!response.ok) throw new Error("Public offline asset unavailable");
      await cache.put(cacheKey(new URL(path, self.location.origin).href), response);
    }
    await self.skipWaiting();
  })().catch(async () => {
    await reportFailure("OFFLINE_INSTALL_FAILED");
    throw new Error("Offline installation failed");
  }));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(CACHE_PREFIX) && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "PREPARE_SHELL") return;
  event.waitUntil((async () => {
    const response = await fetch("/", { credentials: "include", cache: "no-store" });
    if (!response.ok || response.headers.get("x-open-tennis-shell") !== "1") {
      throw new Error("Authenticated application shell unavailable");
    }
    const html = await response.clone().text();
    const files = [...new Set(html.match(/\/_next\/static\/[^"'<>\\\s]+/g) || [])];
    for (const file of files) {
      const url = new URL(file.replaceAll("&amp;", "&"), self.location.origin);
      if (url.origin !== self.location.origin || !url.pathname.startsWith("/_next/static/")) continue;
      const asset = await fetch(url.href, { credentials: "omit" });
      if (!asset.ok) throw new Error("Application asset unavailable");
      await storeResponse(url.href, asset);
    }
    await storeResponse(new URL("/", self.location.origin).href, response);
    for (const page of await self.clients.matchAll({ type: "window" })) {
      page.postMessage({ type: "OFFLINE_READY" });
    }
  })().catch(async () => {
    const cache = await caches.open(CACHE);
    const existing = await cache.match(cacheKey(new URL("/", self.location.origin).href));
    await reportFailure(existing ? "SHELL_REFRESH_FAILED" : "SHELL_SAVE_FAILED");
  }));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin ||
      url.pathname.startsWith("/api/") || url.pathname === "/sw.js") return;
  if (event.request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(event.request);
        if (response.ok && url.pathname === "/" &&
            response.headers.get("x-open-tennis-shell") === "1" &&
            response.headers.get("content-type")?.includes("text/html")) {
          event.waitUntil(storeResponse(new URL("/", self.location.origin).href, response.clone())
            .catch(() => reportFailure("SHELL_SAVE_FAILED")));
        }
        return response;
      } catch {
        const cache = await caches.open(CACHE);
        return await cache.match(cacheKey(new URL("/", self.location.origin).href)) ||
          await cache.match(cacheKey(new URL("/offline.html", self.location.origin).href)) ||
          new Response("Offline page unavailable. Please reconnect.", { status: 503 });
      }
    })());
    return;
  }
  if (url.pathname.startsWith("/_next/static/") || PUBLIC_FILES.includes(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(cacheKey(url.href));
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) event.waitUntil(storeResponse(url.href, response.clone())
        .catch(() => reportFailure("ASSET_SAVE_FAILED")));
      return response;
    })());
  }
});
