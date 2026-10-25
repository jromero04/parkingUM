"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell, EmptyState, ErrorNotice, Protected } from "@/components/app-shell";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";
import type { MetricsSummary, SensorAlert } from "@/lib/types";

export default function MetricsPage() {
  const { token, request } = useAuth();
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [alerts, setAlerts] = useState<SensorAlert[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [metrics, alertResult] = await Promise.all([
        request<MetricsSummary>("/api/v1/metricas/resumen"),
        request<{ items: SensorAlert[] }>("/api/v1/metricas/alertas?limit=100"),
      ]);
      setSummary(metrics); setAlerts(alertResult.items); setError(null);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudieron cargar las métricas.");
    }
  }, [request, token]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 5000);
    return () => { window.clearTimeout(initialLoad); window.clearInterval(timer); };
  }, [load]);

  return <Protected admin><AppShell title="Métricas" subtitle="Proyección eventual del estado operativo del sistema.">
    {error && <ErrorNotice message={error} />}
    {!summary ? <div className="center-state">Cargando métricas…</div> : <>
      <section className="metric-grid"><Metric label="Plazas totales" value={summary.spots.total} /><Metric label="Disponibles" value={summary.spots.available} tone="green" /><Metric label="Ocupadas" value={summary.spots.occupied} tone="red" /><Metric label="Reservadas" value={summary.spots.reserved} tone="blue" /><Metric label="Sin datos" value={summary.spots.unknown} tone="amber" /><Metric label="Ocupación" value={summary.occupancy.percentage === null ? "—" : `${summary.occupancy.percentage}%`} /></section>
      <section className="dashboard-grid"><article className="panel"><p className="eyebrow">Reservas</p><h2>Actividad acumulada</h2><dl className="summary-list"><div><dt>Confirmadas actualmente</dt><dd>{summary.reservations.confirmed_current}</dd></div><div><dt>Creadas</dt><dd>{summary.reservations.created_total}</dd></div><div><dt>Canceladas</dt><dd>{summary.reservations.cancelled_total}</dd></div></dl></article><article className="panel"><p className="eyebrow">Alertas</p><h2>Sensores sin datos vigentes</h2>{alerts.length === 0 ? <EmptyState>No hay alertas activas.</EmptyState> : <ul className="alert-list">{alerts.map((alert) => <li key={alert.spot_id}><span className="alert-mark">!</span><div><strong>Plaza {alert.spot_id.slice(0, 8)}</strong><p>{alert.message}</p><small>Desde {new Date(alert.since).toLocaleString("es-UY")}</small></div></li>)}</ul>}</article></section>
      <p className="data-time">Calculado: {new Date(summary.computed_at).toLocaleString("es-UY")}</p>
    </>}
  </AppShell></Protected>;
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: string }) {
  return <article className={`metric metric-${tone}`}><span>{label}</span><strong>{value}</strong></article>;
}
