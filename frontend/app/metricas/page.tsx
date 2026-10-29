"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell, EmptyState, ErrorNotice, Protected } from "@/components/app-shell";
import { ParkingMap } from "@/components/parking-map";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";
import type { MetricsSummary, SensorAlert, Spot, SpotUsageReport } from "@/lib/types";

export default function MetricsPage() {
  const { token, request } = useAuth();
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [alerts, setAlerts] = useState<SensorAlert[]>([]);
  const [spots, setSpots] = useState<Spot[]>([]);
  const [usagePeriod, setUsagePeriod] = useState<"7d" | "30d" | "all">("30d");
  const [usageReport, setUsageReport] = useState<SpotUsageReport | null>(null);
  const [showOccupancy, setShowOccupancy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [metrics, alertResult, spotResult, usageResult] = await Promise.all([
        request<MetricsSummary>("/api/v1/metricas/resumen"),
        request<{ items: SensorAlert[] }>("/api/v1/metricas/alertas?limit=100"),
        request<Spot[]>("/api/v1/metricas/plazas"),
        request<SpotUsageReport>(`/api/v1/metricas/plazas/mas-utilizadas?periodo=${usagePeriod}&limit=250`),
      ]);
      setSummary(metrics); setAlerts(alertResult.items); setSpots(spotResult); setUsageReport(usageResult); setError(null);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudieron cargar las métricas.");
    }
  }, [request, token, usagePeriod]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 5000);
    return () => { window.clearTimeout(initialLoad); window.clearInterval(timer); };
  }, [load]);

  return <Protected roles={["admin"]}><AppShell title="Métricas" subtitle="Proyección eventual del estado operativo del sistema.">
    {error && <ErrorNotice message={error} />}
    {!summary ? <div className="center-state">Cargando métricas…</div> : <>
      <section className="metric-grid"><Metric label="Plazas totales" value={summary.spots.total} /><Metric label="Disponibles" value={summary.spots.available} tone="green" /><Metric label="Ocupadas" value={summary.spots.occupied} tone="red" /><Metric label="Reservadas" value={summary.spots.reserved} tone="blue" /><Metric label="Sin datos" value={summary.spots.unknown} tone="amber" /><Metric label="Ocupación" value={summary.occupancy.percentage === null ? "—" : `${summary.occupancy.percentage}%`} onClick={() => setShowOccupancy((value) => !value)} expanded={showOccupancy} /></section>
      {showOccupancy && <section className="occupancy-dashboard-panel">
        <div className="occupancy-dashboard-heading"><div><p className="eyebrow">Detalle en tiempo real</p><h2>Plazas ocupadas</h2></div><button className="secondary-button" type="button" onClick={() => setShowOccupancy(false)}>Cerrar mapa</button></div>
        <ParkingMap spots={spots} mode="occupancy" occupancyPercentage={summary.occupancy.percentage} />
      </section>}
      <section className="dashboard-grid"><article className="panel"><p className="eyebrow">Reservas</p><h2>Actividad acumulada</h2><dl className="summary-list"><div><dt>Confirmadas actualmente</dt><dd>{summary.reservations.confirmed_current}</dd></div><div><dt>Creadas</dt><dd>{summary.reservations.created_total}</dd></div><div><dt>Canceladas</dt><dd>{summary.reservations.cancelled_total}</dd></div></dl></article><article className="panel"><p className="eyebrow">Alertas</p><h2>Sensores sin datos vigentes</h2>{alerts.length === 0 ? <EmptyState>No hay alertas activas.</EmptyState> : <ul className="alert-list">{alerts.map((alert) => <li key={alert.spot_id}><span className="alert-mark">!</span><div><strong>Plaza {alert.label}</strong><p>{alert.message}</p><small>Desde {new Date(alert.since).toLocaleString("es-UY")}</small></div></li>)}</ul>}</article></section>
      <section className="panel usage-report-panel">
        <div className="usage-report-heading"><div><p className="eyebrow">Demanda histórica</p><h2>Plazas más utilizadas</h2><p className="muted">Ranking por reservas que completaron su ciclo de uso.</p></div><label>Período<select value={usagePeriod} onChange={(event) => setUsagePeriod(event.target.value as typeof usagePeriod)}><option value="7d">Últimos 7 días</option><option value="30d">Últimos 30 días</option><option value="all">Histórico</option></select></label></div>
        {!usageReport ? <div className="center-state">Cargando reporte…</div> : <>
          <p className="usage-report-total"><strong>{usageReport.total_uses}</strong> usos completados en el período</p>
          <ParkingMap spots={spots} mode="usage" usageItems={usageReport.items} totalUses={usageReport.total_uses} />
          {usageReport.items.length === 0 ? <EmptyState>No hay usos completados en este período.</EmptyState> : <><h3 className="usage-ranking-title">Ranking de las 10 plazas con más usos</h3>
          <ol className="usage-ranking">{usageReport.items.slice(0, 10).map((item, index) => <li key={item.spot_id}>
            <span className="usage-rank">{index + 1}</span><div className="usage-spot"><div><strong>Plaza {item.label}</strong><span>{item.uses} {item.uses === 1 ? "uso" : "usos"} · {item.percentage}%</span></div><div className="usage-bar"><i style={{ width: `${100 * item.uses / usageReport.items[0].uses}%` }} /></div></div><small>Último uso<br />{new Date(item.last_used_at).toLocaleString("es-UY")}</small>
          </li>)}</ol></>}
        </>}
      </section>
      <p className="data-time">Calculado: {new Date(summary.computed_at).toLocaleString("es-UY")}</p>
    </>}
  </AppShell></Protected>;
}

function Metric({ label, value, tone = "neutral", onClick, expanded = false }: { label: string; value: string | number; tone?: string; onClick?: () => void; expanded?: boolean }) {
  if (onClick) return <button type="button" className={`metric metric-${tone} metric-action`} onClick={onClick} aria-expanded={expanded}><span>{label}</span><strong>{value}</strong><small>{expanded ? "Ocultar mapa" : "Ver mapa"}</small></button>;
  return <article className={`metric metric-${tone}`}><span>{label}</span><strong>{value}</strong></article>;
}
