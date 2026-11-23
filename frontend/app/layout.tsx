import type { Metadata, Viewport } from "next";

import { themeInitScript } from "@/features/theme/theme";

import { Providers } from "./providers";
import "./globals.css";

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafafc" },
    { media: "(prefers-color-scheme: dark)", color: "#16171f" },
  ],
};

export const metadata: Metadata = {
  title: { default: "XploAds — AI advertising automation", template: "%s · XploAds" },
  description: "Plan, create, publish and optimize Facebook and Instagram ads with AI — with you in control of spend.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the theme script sets class/style on <html> before React hydrates.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
