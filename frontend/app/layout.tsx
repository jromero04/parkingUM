import type { Metadata } from "next";

import { AuthProvider } from "@/features/auth/auth-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Parking SD",
  description: "Reservas de estacionamiento en tiempo real",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="es"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
