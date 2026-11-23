import type { Metadata } from "next";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "XploAds — AI advertising automation", template: "%s · XploAds" },
  description: "Plan, create, publish and optimize Facebook and Instagram ads with AI — with you in control of spend.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
