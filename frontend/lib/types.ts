export type Role = "user" | "admin" | "sensor";

export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  created_at: string;
};

export type Parking = { id: string; name: string; address: string; created_at: string };

export type Availability = "available" | "reserved" | "occupied" | "unknown";

export type Spot = {
  id: string;
  parking_id: string;
  sensor_id: string;
  label: string;
  physical_occupied: boolean | null;
  assigned_reservation_id: string | null;
  sensor_status: "fresh" | "stale";
  last_report_at: string | null;
  sensor_expires_at: string | null;
  availability: Availability;
  version: number;
  updated_at: string;
};

export type ReservationStatus = "pending" | "confirmed" | "occupied" | "used" | "cancel_pending" | "cancelled" | "rejected";

export type Reservation = {
  id: string;
  user_id: string;
  parking_id: string;
  spot_id: string;
  status: ReservationStatus;
  ever_confirmed: boolean;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  occupied_at: string | null;
  used_at: string | null;
  cancelled_at: string | null;
  failure_code: string | null;
  version: number;
};

export type MetricsSummary = {
  parking_id: string | null;
  spots: { total: number; available: number; reserved: number; occupied: number; unknown: number; assigned_total: number; physically_occupied_fresh: number };
  reservations: { confirmed_current: number; created_total: number; cancelled_total: number };
  occupancy: { occupied_fresh: number; fresh_total: number; percentage: number | null };
  last_projected_at: string | null;
  computed_at: string;
  consistency: "eventual";
};

export type SensorAlert = {
  spot_id: string;
  parking_id: string;
  sensor_id: string;
  label: string;
  code: "SENSOR_DATA_STALE";
  since: string;
  last_report_at: string | null;
  message: string;
};

export type SimulatedSensor = {
  label: string;
  sensor_id: string;
  spot_id: string;
  status: "active" | "stopped";
  sequence: number;
  physical_occupied: boolean;
  updated_at: string;
};
