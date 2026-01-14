import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Script from "next/script";
import ColorInjector from "./components/ColorInjector";
import SettingsInitializer from "./components/SettingsInitializer";
import { AuthProvider } from "./context/AuthContext";
import AuthGuard from "./components/AuthGuard";

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
    icon: '/favicon.ico',
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
        {/* Authentication context + guard */}
        <AuthProvider>
          <AuthGuard>
            {children}
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
