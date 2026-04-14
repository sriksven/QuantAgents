import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuantAgents — Multi-Agent Trading Intelligence",
  description:
    "8-agent AI trading platform with adversarial debate, quantum portfolio optimization, and real-time backtesting.",
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
