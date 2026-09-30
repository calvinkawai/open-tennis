import type { Metadata, Viewport } from "next";
import { themeScript } from "../lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "Open Tennis · 球场页边",
  description: "A private tennis knowledge wiki and training journal.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Open Tennis", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/apple-touch-icon.png" },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f3f2ea" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" suppressHydrationWarning>
    <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
    <body>{children}</body>
  </html>;
}
