"use strict";

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { Navbar } from "@/components/Navbar";
import { ToastProvider, Toaster } from "@/components/Toast";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "TermTerminal — Isolated Web Terminal Platform",
  description: "Secure, multi-user isolated terminal platform for community VPS drops.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full font-sans" style={{ fontFamily: inter.style.fontFamily }}>
        <AuthProvider>
          <div className="flex flex-col h-full">
            <ToastProvider>
              <Toaster position="bottom-center" />
              <main className="flex-1">{children}</main>
            </ToastProvider>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
