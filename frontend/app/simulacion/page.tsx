"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, ErrorNotice, Protected } from "@/components/app-shell";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";
import type { SimulatedSensor } from "@/lib/types";


export default function SimulationPage() {
  const { token, request } = useAuth();
  const [sensors, setSensors] = useState<SimulatedSensor[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "stopped">("all");
  const [loading, setLoading] = useState(true);
  const [changing, setChanging] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setSensors(await request<SimulatedSensor[]>("/api/v1/simulacion/sensores"));
      setError(null);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudieron cargar los sensores.");
    } finally {
      setLoading(false);
    }
  }, [request, token]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), 5000);
    return () => { window.clearTimeout(initialLoad); window.clearInterval(timer); };
  }, [load]);

  const visible = useMemo(() => sensors.filter((sensor) => {
    const matchesText = sensor.label.toLowerCase().includes(query.trim().toLowerCase());
    return matchesText && (status === "all" || sensor.status === status);
  }), [query, sensors, status]);
  const stopped = sensors.filter((sensor) => sensor.status === "stopped").length;

  async function setFailure(sensor: SimulatedSensor, failed: boolean) {
    setChanging(sensor.label); setError(null); setMessage(null);
    try {
      const updated = await request<SimulatedSensor>(`/api/v1/simulacion/sensores/${sensor.label}`, {
        method: "PUT", body: JSON.stringify({ failed }),
      });
      setSensors((items) => items.map((item) => item.label === updated.label ? updated : item));
      setMessage(failed
        ? `Sensor ${sensor.label} detenido. La alerta aparecerá cuando venza su último reporte.`
        : `Sensor ${sensor.label} reactivado. La alerta desaparecerá al procesarse el próximo reporte.`);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudo cambiar el sensor.");
    } finally {
      setChanging(null);
    }
  }

  return <Protected roles={["sensor"]}><AppShell title="Simulación de sensores" subtitle="Control aislado para provocar y recuperar fallos reales en el flujo distribuido.">
    <section className="simulation-summary">
      <article><span>Sensores configurados</span><strong>{sensors.length}</strong></article>
      <article><span>Publicando</span><strong>{sensors.length - stopped}</strong></article>
      <article className={stopped ? "simulation-alert-count" : ""}><span>Detenidos</span><strong>{stopped}</strong></article>
      <div><strong>Cómo funciona</strong><p>Al detener un sensor deja de emitir heartbeats. Parkings lo marcará sin datos vigentes y Métricas mostrará la alerta automáticamente.</p></div>
    </section>
    <section className="simulation-toolbar">
      <label>Buscar plaza<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ej. C-12" /></label>
      <label>Estado<select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}><option value="all">Todos</option><option value="active">Publicando</option><option value="stopped">Detenidos</option></select></label>
    </section>
    {error && <ErrorNotice message={error} />}
    {message && <div className="notice success">{message}</div>}
    {loading ? <div className="center-state">Cargando sensores…</div> : visible.length === 0 ? <EmptyState>No hay sensores para este filtro.</EmptyState> :
      <div className="sensor-table-wrap"><table className="sensor-table"><thead><tr><th>Plaza</th><th>Sensor</th><th>Secuencia</th><th>Estado físico</th><th>Publicación</th><th><span className="sr-only">Acción</span></th></tr></thead><tbody>{visible.map((sensor) =>
        <tr key={sensor.sensor_id} className={sensor.status === "stopped" ? "sensor-row-stopped" : ""}>
          <td><strong>{sensor.label}</strong></td><td><code>{sensor.sensor_id.slice(0, 8)}</code></td><td>{sensor.sequence}</td>
          <td>{sensor.physical_occupied ? "Ocupada" : "Libre"}</td>
          <td><span className={`sensor-state sensor-state-${sensor.status}`}><i />{sensor.status === "active" ? "Publicando" : "Detenido"}</span></td>
          <td>{sensor.status === "active"
            ? <button className="danger-button" disabled={changing === sensor.label} onClick={() => void setFailure(sensor, true)}>{changing === sensor.label ? "Deteniendo…" : "Detener"}</button>
            : <button className="primary-button" disabled={changing === sensor.label} onClick={() => void setFailure(sensor, false)}>{changing === sensor.label ? "Reactivando…" : "Reactivar"}</button>}</td>
        </tr>)}</tbody></table></div>}
  </AppShell></Protected>;
}
