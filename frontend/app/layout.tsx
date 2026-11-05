import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const displayFont = localFont({
  src: "../assets/fonts/bricolage-grotesque-latin-wght-normal.woff2",
  variable: "--font-display",
  weight: "200 800",
  display: "swap",
});

const bodyFont = localFont({
  src: "../assets/fonts/dm-sans-latin-wght-normal.woff2",
  variable: "--font-body",
  weight: "100 1000",
  display: "swap",
});

const headlineFont = localFont({
  src: "../assets/fonts/gothic-a1-latin-700-normal.woff2",
  variable: "--font-headline",
  weight: "700",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Passport Studio | Passport photos without the photo booth",
  description: "Turn a photo into a passport-sized JPEG with a clean white background. Choose your country, upload, and download.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${displayFont.variable} ${bodyFont.variable} ${headlineFont.variable}`}><body>{children}</body></html>;
}
