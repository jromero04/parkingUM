"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthCard, Field } from "@/components/auth-card";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      await register(String(data.get("name")), String(data.get("email")), String(data.get("password")));
      router.replace("/parkings");
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No pudimos conectar con el servidor.");
      setLoading(false);
    }
  }

  return <AuthCard title="Creá tu cuenta" description="Registrate para empezar a reservar." footer={<>¿Ya tenés cuenta? <Link href="/login">Ingresá</Link></>}>
    <form className="form" onSubmit={submit}>
      <Field label="Nombre" name="name" minLength={1} maxLength={100} autoComplete="name" placeholder="Juan Pérez" />
      <Field label="Correo electrónico" name="email" type="email" autoComplete="email" placeholder="tu@correo.com" />
      <Field label="Contraseña" name="password" type="password" minLength={12} maxLength={128} autoComplete="new-password" placeholder="Mínimo 12 caracteres" />
      <p className="field-help">Usá entre 12 y 128 caracteres.</p>
      {error && <p role="alert" className="notice error">{error}</p>}
      <button className="primary-button full" disabled={loading}>{loading ? "Creando cuenta…" : "Crear cuenta"}</button>
    </form>
  </AuthCard>;
}
