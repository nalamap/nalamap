import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Script from "next/script";
import ColorInjector from "./components/ColorInjector";
import SettingsInitializer from "./components/SettingsInitializer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NaLaMap",
  description:
    "NaLaMap is an open-source platform that helps users find and analyze geospatial data in a natural way. It combines modern web technologies with AI capabilities to create an intuitive interface for interacting with geographic information.",
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/favicon.ico', type: 'image/x-icon' },
    ],
    shortcut: '/favicon.ico',
    apple: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {/* Runtime environment variables injected at container start */}
        <Script src="/runtime-env.js" strategy="beforeInteractive" />
        {/* Initialize settings early to load custom colors */}
        <SettingsInitializer />
        {/* Dynamic CSS color injection */}
        <ColorInjector />
        {children}
      </body>
    </html>
  );
}
