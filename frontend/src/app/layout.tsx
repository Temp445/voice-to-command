import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { Toaster } from "@/components/ui/toaster";
import { ShortcutManager } from "@/components/layout/ShortcutManager";
import { WebSocketManager } from "@/hooks/useWebSocket";
import { AuthWrapper } from "@/components/auth/AuthWrapper";

import { LoadingOverlay } from "@/components/layout/LoadingOverlay";

export const metadata: Metadata = {
  title: "ACE Voice Controller",
  description: "AI-powered desktop voice control and automation system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <AuthWrapper>
          <ThemeProvider>{children}</ThemeProvider>
          <Toaster />
          <ShortcutManager />
          <WebSocketManager />
          <LoadingOverlay />
        </AuthWrapper>
      </body>
    </html>
  );
}
