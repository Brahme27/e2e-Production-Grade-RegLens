import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "RegLens: regulatory change-impact copilot",
  description: "Cited, time-aware answers over RBI, SEBI, FCA and PRA regulation, and policy gap analysis.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <header className="bg-brand">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 md:flex-row md:items-center md:justify-between">
            <div className="text-lg font-bold text-white">
              RegLens <span className="font-normal text-slate-300">· RBI · SEBI · FCA · PRA</span>
            </div>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="py-4 text-center text-xs text-slate-500">
          Portfolio project · information only, not legal advice · always check the cited source
        </footer>
      </body>
    </html>
  );
}
