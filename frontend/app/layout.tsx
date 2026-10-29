import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Passport Studio | Your next adventure starts here",
  description: "Turn a photo into a passport-sized JPEG with a clean white background. Choose your country, upload, and download.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
