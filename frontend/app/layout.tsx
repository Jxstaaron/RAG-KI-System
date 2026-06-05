import type { Metadata } from "next";
import "./globals.css";

// Metadaten, die Next.js in den HTML-Head schreibt.
export const metadata: Metadata = {
  title: "PDF Lernassistent",
  description: "RAG-basierter Lernassistent für PDF-Dateien",
};

// RootLayout ist der äußere Rahmen der gesamten Next.js-App.
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
