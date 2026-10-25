import Link from "next/link";
import type { ReactNode } from "react";

export function AuthCard({ title, description, children, footer }: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="auth-page">
      <div className="auth-glow" aria-hidden />
      <section className="auth-card">
        <Link href="/" className="brand brand-auth"><span>P</span> ParkingUM</Link>
        <div>
          <p className="eyebrow">Acceso seguro</p>
          <h1>{title}</h1>
          <p className="muted">{description}</p>
        </div>
        {children}
        <footer>{footer}</footer>
      </section>
    </main>
  );
}

export function Field(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, id, ...inputProps } = props;
  const fieldId = id ?? inputProps.name;
  return (
    <label className="field" htmlFor={fieldId}>
      <span>{label}</span>
      <input id={fieldId} required {...inputProps} />
    </label>
  );
}
