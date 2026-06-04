import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PDF Learning Assistant",
  description: "RAG-powered PDF study assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
