"use client";

import { FormEvent, useId, useMemo, useRef, useState } from "react";

import type { Spot, SpotUsageItem } from "@/lib/types";

type ParkingMapProps = {
  spots: Spot[];
  reservingId?: string | null;
  onReserve?: (spot: Spot) => Promise<void>;
  mode?: "reservation" | "occupancy" | "usage";
  occupancyPercentage?: number | null;
  usageItems?: SpotUsageItem[];
  totalUses?: number;
};

type Row = { x: number; y: number; count: number; first: number };
type Zone = { id: "A" | "B" | "C"; name: string; rows: Row[] };

const ZONES: Zone[] = [
  { id: "A", name: "Zona A", rows: [
    { x: 70, y: 72, count: 18, first: 1 }, { x: 88, y: 72, count: 18, first: 19 },
    { x: 134, y: 72, count: 18, first: 37 }, { x: 152, y: 72, count: 18, first: 55 },
  ] },
  { id: "B", name: "Zona B", rows: [
    { x: 206, y: 190, count: 9, first: 1 }, { x: 224, y: 190, count: 9, first: 10 },
  ] },
  { id: "C", name: "Zona C", rows: [
    { x: 285, y: 364, count: 13, first: 1 }, { x: 303, y: 364, count: 13, first: 14 },
    { x: 349, y: 364, count: 13, first: 27 }, { x: 367, y: 364, count: 13, first: 40 },
    { x: 413, y: 364, count: 13, first: 53 }, { x: 431, y: 364, count: 13, first: 66 },
  ] },
];

const STATUS_LABEL = {
  available: "Libre",
  reserved: "Reservada",
  occupied: "Ocupada",
  unknown: "Sin datos",
};

export function ParkingMap({ spots, reservingId = null, onReserve, mode = "reservation", occupancyPercentage = null, usageItems = [], totalUses = 0 }: ParkingMapProps) {
  const instanceId = useId();
  const byLabel = useMemo(() => Object.fromEntries(spots.map((spot) => [spot.label, spot])), [spots]);
  const usageBySpot = useMemo(() => Object.fromEntries(usageItems.map((item) => [item.spot_id, item])), [usageItems]);
  const maximumUses = useMemo(() => Math.max(0, ...usageItems.map((item) => item.uses)), [usageItems]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mapMessage, setMapMessage] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const occupancyMode = mode === "occupancy";
  const usageMode = mode === "usage";
  const selected = spots.find((spot) => spot.id === selectedId && (!occupancyMode || spot.availability === "occupied")) ?? null;
  const selectedUsage = selected ? usageBySpot[selected.id] : null;
  const occupiedSpots = spots.filter((spot) => spot.availability === "occupied");

  const counts = spots.reduce((result, spot) => {
    result[spot.availability] += 1;
    return result;
  }, { available: 0, reserved: 0, occupied: 0, unknown: 0 });

  function choose(spot: Spot) {
    const selectable = usageMode || (occupancyMode ? spot.availability === "occupied" : spot.availability === "available");
    if (!selectable) {
      setMapMessage(`La plaza ${spot.label} está ${STATUS_LABEL[spot.availability].toLowerCase()}.`);
      return;
    }
    setSelectedId(spot.id);
    setMapMessage(null);
  }

  function search(event: FormEvent) {
    event.preventDefault();
    const match = /^([ABC])\s*-?\s*(\d{1,2})$/i.exec(query.trim());
    const label = match ? `${match[1].toUpperCase()}-${match[2].padStart(2, "0")}` : "";
    const spot = byLabel[label];
    if (!spot) {
      setMapMessage("Escribí un código válido, por ejemplo C-12.");
      return;
    }
    document.getElementById(`spot-${instanceId}-${spot.id}`)?.focus();
    choose(spot);
  }

  function usageColor(uses: number) {
    if (!uses || !maximumUses) return "#e2e8f0";
    const intensity = Math.sqrt(uses / maximumUses);
    return `hsl(${48 - 44 * intensity} 88% ${82 - 34 * intensity}%)`;
  }

  return <section className={`parking-map-experience${occupancyMode ? " parking-map-occupancy" : ""}${usageMode ? " parking-map-usage" : ""}`}>
    <div className="map-toolbar">
      {usageMode ? <div className="usage-map-legend" aria-label="Escala de frecuencia de uso">
        <span>Sin usos</span><i /><span>Más utilizada</span>
      </div> : <div className="map-legend" aria-label="Referencias">
        <span><i className="map-dot map-dot-available" />Libre</span>
        <span><i className="map-dot map-dot-reserved" />Reservada</span>
        <span><i className="map-dot map-dot-occupied" />Ocupada</span>
        <span><i className="map-dot map-dot-unknown" />Sin datos</span>
        <span><i className="map-dot map-dot-selected" />{occupancyMode ? "Plaza consultada" : "Tu selección"}</span>
      </div>}
      <form className="map-search" onSubmit={search}>
        <label className="sr-only" htmlFor={`spot-search-${instanceId}`}>Buscar plaza</label>
        <input id={`spot-search-${instanceId}`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar: C-12" maxLength={6} />
        <button className="secondary-button" type="submit">Ir</button>
        <button className="secondary-button zoom-button" type="button" aria-label="Alejar" onClick={() => setZoom((value) => Math.max(1, value - .5))}>−</button>
        <button className="secondary-button zoom-button" type="button" aria-label="Acercar" onClick={() => setZoom((value) => Math.min(2.5, value + .5))}>+</button>
      </form>
    </div>

    <div className="parking-map-layout">
      <div className="parking-map-scroll" ref={scrollRef}>
        <svg className="parking-map" style={{ width: `${zoom * 100}%` }} viewBox="0 0 680 630" role="group" aria-label="Plano del estacionamiento">
          <defs><marker id="north-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></marker></defs>
          <rect className="map-road" x="20" y="30" width="28" height="330" /><rect className="map-road" x="48" y="332" width="227" height="28" />
          <text className="map-road-label" x="160" y="346" textAnchor="middle" dominantBaseline="central">Calle interna</text>
          <rect className="map-road" x="470" y="30" width="28" height="544" /><rect className="map-road" x="150" y="546" width="320" height="28" />
          <text className="map-road-label" x="310" y="560" textAnchor="middle" dominantBaseline="central">Acceso Espacio Ciencia</text>
          <rect className="map-lot" x="60" y="40" width="120" height="270" rx="4" /><text className="map-lot-label" x="120" y="58" textAnchor="middle" dominantBaseline="central">Zona A</text>
          <rect className="map-lot" x="200" y="160" width="70" height="150" rx="4" /><text className="map-lot-label" x="235" y="178" textAnchor="middle" dominantBaseline="central">Zona B</text>
          <rect className="map-lot" x="275" y="332" width="190" height="210" rx="4" /><text className="map-lot-label" x="370" y="350" textAnchor="middle" dominantBaseline="central">Zona C</text>
          <rect className="map-building" x="200" y="112" width="56" height="26" rx="4" /><text className="map-building-small" x="228" y="125" textAnchor="middle" dominantBaseline="central">Caseta</text>
          <rect className="map-building" x="60" y="385" width="185" height="125" rx="4" /><text className="map-building-label" x="152" y="440" textAnchor="middle" dominantBaseline="central">Espacio Ciencia</text><text className="map-building-small" x="152" y="458" textAnchor="middle" dominantBaseline="central">Museo de ciencia</text>
          <rect className="map-building" x="510" y="170" width="160" height="170" rx="4" /><text className="map-building-label" x="590" y="246" textAnchor="middle" dominantBaseline="central">Universidad de</text><text className="map-building-label" x="590" y="266" textAnchor="middle" dominantBaseline="central">Montevideo</text>
          <rect className="map-building" x="510" y="385" width="160" height="165" rx="4" /><text className="map-building-label" x="590" y="458" textAnchor="middle" dominantBaseline="central">Centro de Eventos</text><text className="map-building-small" x="590" y="478" textAnchor="middle" dominantBaseline="central">del Parque</text>
          <g className="map-north"><line x1="585" y1="95" x2="585" y2="55" markerEnd="url(#north-arrow)" /><text x="585" y="40" textAnchor="middle" dominantBaseline="central">N</text></g>
          {ZONES.flatMap((zone) => zone.rows.flatMap((row) => Array.from({ length: row.count }, (_, index) => {
            const label = `${zone.id}-${String(row.first + index).padStart(2, "0")}`;
            const spot = byLabel[label];
            if (!spot) return null;
            const isSelected = selected?.id === spot.id;
            const usage = usageBySpot[spot.id];
            const usageDescription = `${usage?.uses ?? 0} ${(usage?.uses ?? 0) === 1 ? "uso" : "usos"}`;
            return <rect key={spot.id} id={`spot-${instanceId}-${spot.id}`} className={`map-stall map-stall-${spot.availability}${usageMode ? " map-stall-usage" : ""}${isSelected ? " map-stall-selected" : ""}`}
              style={usageMode ? { fill: usageColor(usage?.uses ?? 0) } : undefined}
              x={row.x} y={row.y + index * 12} width="18" height="12" rx="1.5" role="button"
              tabIndex={(usageMode || (occupancyMode ? spot.availability === "occupied" : spot.availability === "available")) ? 0 : -1} aria-label={usageMode ? `Plaza ${label}, ${usageDescription}` : `Plaza ${label}, ${STATUS_LABEL[spot.availability].toLowerCase()}`}
              onClick={() => choose(spot)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(spot); } }}>
              <title>{usageMode ? `${label} · ${usageDescription}` : `${label} · ${STATUS_LABEL[spot.availability]}`}</title>
            </rect>;
          })))}
        </svg>
      </div>

      <aside className="map-selection" aria-live="polite">
        {!usageMode && <div className="map-counts">
          <span><strong>{counts.available}</strong> libres</span><span><strong>{counts.reserved}</strong> reservadas</span>
          <span><strong>{counts.occupied}</strong> ocupadas</span><span><strong>{counts.unknown}</strong> sin datos</span>
        </div>}
        {usageMode && <div className="usage-map-summary">
          <p className="eyebrow">Frecuencia histórica</p>
          <strong>{totalUses}</strong>
          <p>{totalUses === 1 ? "uso completado" : "usos completados"} en el período</p>
          <small>El color se calcula respecto de la plaza más utilizada.</small>
        </div>}
        {occupancyMode && <div className="occupancy-map-summary">
          <p className="eyebrow">Ocupación actual</p>
          <strong>{occupancyPercentage === null ? "—" : `${occupancyPercentage}%`}</strong>
          <p>{occupiedSpots.length} {occupiedSpots.length === 1 ? "plaza ocupada" : "plazas ocupadas"}</p>
          <div className="occupied-spot-list" aria-label="Plazas ocupadas">
            {occupiedSpots.length === 0 ? <span className="muted">No hay plazas ocupadas.</span> : occupiedSpots.map((spot) =>
              <button key={spot.id} type="button" className={selectedId === spot.id ? "active" : ""} onClick={() => choose(spot)}>{spot.label}</button>
            )}
          </div>
        </div>}
        {selected ? <>
          <p className="eyebrow">{usageMode ? "Frecuencia de uso" : occupancyMode ? "Plaza ocupada" : "Plaza seleccionada"}</p><h2>{selected.label}</h2>
          <p className="muted">{usageMode ? `Zona ${selected.label.split("-")[0]}` : `Zona ${selected.label.split("-")[0]} · Sensor ${selected.sensor_status === "fresh" ? "actualizado" : "sin datos recientes"}`}</p>
          {usageMode ? <dl className="map-spot-details">
            <div><dt>Usos</dt><dd>{selectedUsage?.uses ?? 0}</dd></div>
            <div><dt>Participación</dt><dd>{selectedUsage?.percentage ?? 0}%</dd></div>
            <div><dt>Último uso</dt><dd>{selectedUsage ? new Date(selectedUsage.last_used_at).toLocaleString("es-UY") : "Sin usos"}</dd></div>
          </dl> : <dl className="map-spot-details">
            <div><dt>Estado</dt><dd>{STATUS_LABEL[selected.availability]}</dd></div>
            <div><dt>Último reporte</dt><dd>{selected.last_report_at ? new Date(selected.last_report_at).toLocaleTimeString("es-UY") : "Nunca"}</dd></div>
          </dl>}
          {!occupancyMode && onReserve && <button className="primary-button full" disabled={selected.availability !== "available" || reservingId !== null} onClick={() => onReserve(selected)}>
            {reservingId === selected.id ? "Reservando…" : "Reservar plaza"}
          </button>}
          <button className="secondary-button full" type="button" onClick={() => { setSelectedId(null); setMapMessage(null); }}>{occupancyMode || usageMode ? "Cerrar detalle" : "Cancelar selección"}</button>
        </> : usageMode ? <div className="map-empty-selection"><div className="map-pin">%</div><h2>Consultá una plaza</h2><p className="muted">Seleccioná una plaza para ver su frecuencia de uso en el período.</p></div> : !occupancyMode && <div className="map-empty-selection"><div className="map-pin">P</div><h2>Ninguna plaza elegida</h2><p className="muted">Seleccioná una plaza libre en el mapa o buscala por su código.</p></div>}
        {mapMessage && <p className="map-message">{mapMessage}</p>}
      </aside>
    </div>
  </section>;
}
