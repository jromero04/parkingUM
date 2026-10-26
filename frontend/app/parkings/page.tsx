"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell, EmptyState, ErrorNotice, Protected } from "@/components/app-shell";
import { ParkingMap } from "@/components/parking-map";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";
import type { Parking, Spot } from "@/lib/types";

export default function ParkingsPage() {
  const { token, request } = useAuth();
  const [parkings, setParkings] = useState<Parking[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [spots, setSpots] = useState<Spot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reservingId, setReservingId] = useState<string | null>(null);

  const loadSpots = useCallback(async (parkingId: string) => {
    if (!token || !parkingId) return;
    const result = await request<Spot[]>(`/api/v1/parkings/${parkingId}/plazas`);
    setSpots(result);
  }, [request, token]);

  useEffect(() => {
    if (!token) return;
    request<Parking[]>("/api/v1/parkings")
      .then((items) => { setParkings(items); const first = items[0]?.id ?? ""; setSelected(first); return loadSpots(first); })
      .catch((problem) => setError(problem instanceof ApiError ? problem.message : "No se pudieron cargar los estacionamientos."))
      .finally(() => setLoading(false));
  }, [loadSpots, request, token]);

  useEffect(() => {
    if (!selected) return;
    const timer = window.setInterval(() => loadSpots(selected).catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, [loadSpots, selected]);

  async function reserve(spot: Spot) {
    if (!token) return;
    setError(null); setMessage(null); setReservingId(spot.id);
    try {
      const result = await request<{ reservation: { status: string } }>("/api/v1/reservas", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ parking_id: spot.parking_id, spot_id: spot.id }),
      });
      setMessage(result.reservation.status === "confirmed" ? `La plaza ${spot.label} quedó reservada.` : "La reserva continúa procesándose.");
      await loadSpots(selected);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudo crear la reserva.");
    } finally { setReservingId(null); }
  }

  return <Protected roles={["user", "admin"]}><AppShell title="Estacionamientos" subtitle="La disponibilidad se actualiza automáticamente.">
    <section className="toolbar">
      <label>Estacionamiento<select value={selected} onChange={(event) => { setSelected(event.target.value); setLoading(true); loadSpots(event.target.value).catch(() => setError("No se pudieron cargar las plazas.")).finally(() => setLoading(false)); }}>{parkings.map((parking) => <option key={parking.id} value={parking.id}>{parking.name} · {parking.address}</option>)}</select></label>
      <button className="secondary-button" onClick={() => loadSpots(selected)}>Actualizar</button>
    </section>
    {error && <ErrorNotice message={error} />}{message && <div className="notice success">{message}</div>}
    {loading ? <div className="center-state">Cargando plazas…</div> : spots.length === 0 ? <EmptyState>No hay plazas configuradas.</EmptyState> : <ParkingMap spots={spots} reservingId={reservingId} onReserve={reserve} />}
  </AppShell></Protected>;
}
