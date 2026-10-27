"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell, EmptyState, ErrorNotice, Protected } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/lib/api";
import type { Parking, Reservation, Spot } from "@/lib/types";

type ReservationCollection = { items: Reservation[]; next_cursor: string | null };

export default function ReservationsPage() {
  const { token, request } = useAuth();
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [parkings, setParkings] = useState<Parking[]>([]);
  const [spots, setSpots] = useState<Record<string, Spot>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [reservationResult, parkingResult] = await Promise.all([
        request<ReservationCollection>("/api/v1/reservas?limit=100"),
        request<Parking[]>("/api/v1/parkings"),
      ]);
      setReservations(reservationResult.items.slice().reverse());
      setParkings(parkingResult);
      const spotGroups = await Promise.all(parkingResult.map((parking) => request<Spot[]>(`/api/v1/parkings/${parking.id}/plazas`)));
      setSpots(Object.fromEntries(spotGroups.flat().map((spot) => [spot.id, spot])));
      setError(null);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudieron cargar las reservas.");
    } finally { setLoading(false); }
  }, [request, token]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);
  const hasPending = useMemo(() => reservations.some((item) => item.status === "pending" || item.status === "cancel_pending"), [reservations]);
  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [hasPending, load]);

  async function cancel(reservation: Reservation) {
    if (!token) return;
    try {
      await request(`/api/v1/reservas/${reservation.id}/cancelacion`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      await load();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "No se pudo cancelar la reserva.");
    }
  }

  const parkingNames = Object.fromEntries(parkings.map((parking) => [parking.id, parking.name]));
  return <Protected roles={["user"]}><AppShell title="Mis reservas" subtitle="Las operaciones pendientes se actualizan cada dos segundos.">
    {error && <ErrorNotice message={error} />}
    {loading ? <div className="center-state">Cargando reservas…</div> : reservations.length === 0 ? <EmptyState>Todavía no hiciste ninguna reserva.</EmptyState> : <section className="reservation-list">{reservations.map((reservation) => <article className="reservation-card" key={reservation.id}><div><div className="reservation-title"><h2>{parkingNames[reservation.parking_id] ?? "Estacionamiento"} · Plaza {spots[reservation.spot_id]?.label ?? "—"}</h2><StatusBadge status={reservation.status} /></div><p className="muted small">Creada el {new Date(reservation.created_at).toLocaleString("es-UY")}</p><p className="reservation-id">{reservation.id}</p></div><div className="reservation-actions"><span>Versión {reservation.version}</span>{["pending", "confirmed"].includes(reservation.status) && <button className="danger-button" onClick={() => cancel(reservation)}>Cancelar</button>}</div></article>)}</section>}
  </AppShell></Protected>;
}
