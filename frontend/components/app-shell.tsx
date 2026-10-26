"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/features/auth/auth-context";
import type { Role } from "@/lib/types";

const homeFor = (role: Role) => role === "sensor" ? "/simulacion" : "/parkings";

export function Protected({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user } = useAuth();
  const router = useRouter();
  const allowed = !roles || (!!user && roles.includes(user.role));
  useEffect(() => {
    if (!user) router.replace("/login");
    else if (roles && !roles.includes(user.role)) router.replace(homeFor(user.role));
  }, [roles, router, user]);
  if (!user || !allowed) return <main className="center-state">Verificando sesión…</main>;
  return <>{children}</>;
}

export function AppShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const links = user?.role === "sensor"
    ? [["/simulacion", "Sensores"]]
    : [
        ["/parkings", "Estacionamientos"],
        ["/reservas", "Mis reservas"],
        ...(user?.role === "admin" ? [["/metricas", "Métricas"]] : []),
      ];
  const home = user ? homeFor(user.role) : "/login";
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Link href={home} className="brand"><span>P</span> ParkingUM</Link>
        <nav>{links.map(([href, label]) => <Link key={href} href={href} className={pathname === href ? "active" : ""}>{label}</Link>)}</nav>
        <div className="user-panel">
          <strong>{user?.name}</strong>
          <small>{user?.email}</small>
          <button className="text-button" onClick={() => { logout(); router.replace("/login"); }}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="content">
        <header className="page-heading"><div><p className="eyebrow"> Gestión inteligente de estacionamientos </p><h1>{title}</h1><p className="muted">{subtitle}</p></div><span className="live-dot">En línea</span></header>
        {children}
      </main>
    </div>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return <div role="alert" className="notice error">{message}</div>;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}
