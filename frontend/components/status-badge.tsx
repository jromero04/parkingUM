import type { Availability, ReservationStatus } from "@/lib/types";

const labels: Record<Availability | ReservationStatus, string> = {
  available: "Disponible",
  reserved: "Reservada",
  occupied: "Ocupada",
  unknown: "Sin datos",
  pending: "Pendiente",
  confirmed: "Confirmada",
  cancel_pending: "Cancelando",
  cancelled: "Cancelada",
  rejected: "Rechazada",
};

export function StatusBadge({ status }: { status: Availability | ReservationStatus }) {
  return <span className={`status status-${status}`}>{labels[status]}</span>;
}
