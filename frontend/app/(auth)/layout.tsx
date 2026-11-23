import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/features/theme/theme";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-secondary/60 to-background px-4 py-12">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="mb-8">
        <Logo />
      </div>
      <div className="w-full max-w-md">{children}</div>
      <p className="mt-8 text-xs text-muted-foreground">© Xplosys. XploAds keeps you in control of every publish and every rupee or dollar spent.</p>
    </div>
  );
}
