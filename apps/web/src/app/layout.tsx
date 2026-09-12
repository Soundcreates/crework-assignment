import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Lead Intelligence",
  description: "AI-powered sales intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');var d=document.documentElement;if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){d.classList.add('dark');}else{d.classList.remove('dark');}}catch(e){}})();`,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-[radial-gradient(circle_at_top,_#f8fafc,_#eef2ff_45%,_#f4f4f5)] text-zinc-900 antialiased dark:bg-[radial-gradient(circle_at_top,_#09090b,_#0f172a_45%,_#18181b)] dark:text-zinc-100 transition-colors duration-200`}
      >
        <ThemeProvider>
          <header className="border-b border-zinc-200/80 bg-white/70 backdrop-blur dark:border-zinc-800/80 dark:bg-zinc-950/70">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
              <Link href="/" className="font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
                Lead Intelligence
              </Link>
              <nav className="flex items-center gap-5 text-sm text-zinc-600 dark:text-zinc-400">
                <Link href="/dashboard" className="hover:text-zinc-900 dark:hover:text-zinc-100">
                  Dashboard
                </Link>
                <Link href="/discover" className="hover:text-zinc-900 dark:hover:text-zinc-100">
                  Discover
                </Link>
                <ThemeToggle />
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
