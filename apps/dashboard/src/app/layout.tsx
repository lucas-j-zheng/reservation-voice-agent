import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sam - Voice Reservation Agent",
  description: "AI-powered restaurant reservation system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
