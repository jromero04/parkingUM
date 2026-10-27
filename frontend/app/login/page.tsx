"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthCard, Field } from "@/components/auth-card";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      const user = await login(String(data.get("email")), String(data.get("password")));
      router.replace(user.role === "sensor" ? "/simulacion" : user.role === "admin" ? "/metricas" : "/parkings");
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No pudimos conectar con el servidor.");
      setLoading(false);
    }
  }

  return <AuthCard title="Bienvenido!" description="Ingresá para consultar y reservar plazas." footer={<>¿No tenés cuenta? <Link href="/registro">Registrate</Link></>}>
    <form className="form" onSubmit={submit}>
      <Field label="Correo electrónico" name="email" type="email" autoComplete="email" placeholder="tu@correo.com" />
      <Field label="Contraseña" name="password" type="password" autoComplete="current-password" placeholder="••••••••••••" />
      {error && <p role="alert" className="notice error">{error}</p>}
      <button className="primary-button full" disabled={loading}>{loading ? "Ingresando…" : "Iniciar sesión"}</button>
    </form>
  </AuthCard>;
}
