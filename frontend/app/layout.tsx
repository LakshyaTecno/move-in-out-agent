import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Move Assistant",
  description: "Agentic move-in / move-out workflow for residential communities",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-slate-200 bg-white">
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3 text-sm">
            <Link href="/" className="font-semibold text-brand">
              Move Assistant
            </Link>
            <Link href="/resident" className="text-slate-600 hover:text-slate-900">
              Resident
            </Link>
            <Link href="/admin" className="text-slate-600 hover:text-slate-900">
              Admin
            </Link>
            <Link href="/communities" className="text-slate-600 hover:text-slate-900">
              Community rules
            </Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
