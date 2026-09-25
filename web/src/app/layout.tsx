import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider, themeScript } from "@/components/theme-provider";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Qualifyr",
  description: "Buyer-only GTM lead engine",
};

/** Root layout: fonts, theme, nothing else.
 *
 * Deliberately does NOT render AppShell any more. Each route group brings its own chrome
 * - (marketing) a nav and footer, (auth) a split panel, (app) the dashboard sidebar - so
 * that a public page is not forced to wear the signed-in furniture.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <head>
        {/* Before first paint: see themeScript's comment. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
