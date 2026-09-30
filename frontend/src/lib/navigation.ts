export function linkTo(kind: string, id?: string | number): string {
  return `#/${kind}${id === undefined ? "" : `/${encodeURIComponent(String(id))}`}`;
}

export function navigate(kind: string, id?: string | number) {
  window.location.hash = linkTo(kind, id);
}

export function safeHref(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  if (/^#[^#]/.test(value)) return value;
  try {
    const url = new URL(value);
    if ((url.protocol === "https:" || url.protocol === "http:") && !url.username && !url.password) {
      return url.href;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export function formatDate(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}
