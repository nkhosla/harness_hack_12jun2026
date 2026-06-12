import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cicero",
  description: "Your next five moves, ranked by what voters care about.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas text-ink min-h-screen flex flex-col">

        {/* Full-bleed header */}
        <header className="w-full sticky top-0 z-50 bg-canvas/95 backdrop-blur-sm border-b border-border">
          <div className="max-w-page mx-auto px-8 h-14 flex items-center">
            <span className="text-sm font-bold tracking-[0.12em] uppercase text-accent select-none">
              Cicero
            </span>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1">
          {children}
        </div>

        {/* Full-bleed footer */}
        <footer className="w-full h-14 bg-ink" aria-hidden="true" />

      </body>
    </html>
  );
}
