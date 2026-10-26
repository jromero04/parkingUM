"use client";

import { FormEvent, useMemo, useRef, useState } from "react";

import type { Spot } from "@/lib/types";

type ParkingMapProps = {
  spots: Spot[];
  reservingId: string | null;
  onReserve: (spot: Spot) => Promise<void>;
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

export function ParkingMap({ spots, reservingId, onReserve }: ParkingMapProps) {
  const byLabel = useMemo(() => Object.fromEntries(spots.map((spot) => [spot.label, spot])), [spots]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mapMessage, setMapMessage] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const selected = spots.find((spot) => spot.id === selectedId) ?? null;

  const counts = spots.reduce((result, spot) => {
    result[spot.availability] += 1;
    return result;
  }, { available: 0, reserved: 0, occupied: 0, unknown: 0 });

  function choose(spot: Spot) {
    if (spot.availability !== "available") {
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
    document.getElementById(`spot-${spot.id}`)?.focus();
    choose(spot);
  }

  return <section className="parking-map-experience">
    <div className="map-toolbar">
      <div className="map-legend" aria-label="Referencias">
        <span><i className="map-dot map-dot-available" />Libre</span>
        <span><i className="map-dot map-dot-reserved" />Reservada</span>
        <span><i className="map-dot map-dot-occupied" />Ocupada</span>
        <span><i className="map-dot map-dot-unknown" />Sin datos</span>
        <span><i className="map-dot map-dot-selected" />Tu selección</span>
      </div>
      <form className="map-search" onSubmit={search}>
        <label className="sr-only" htmlFor="spot-search">Buscar plaza</label>
        <input id="spot-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar: C-12" maxLength={6} />
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
            const isSelected = selectedId === spot.id;
            return <rect key={spot.id} id={`spot-${spot.id}`} className={`map-stall map-stall-${spot.availability}${isSelected ? " map-stall-selected" : ""}`}
              x={row.x} y={row.y + index * 12} width="18" height="12" rx="1.5" role="button"
              tabIndex={spot.availability === "available" ? 0 : -1} aria-label={`Plaza ${label}, ${STATUS_LABEL[spot.availability].toLowerCase()}`}
              onClick={() => choose(spot)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(spot); } }}>
              <title>{label} · {STATUS_LABEL[spot.availability]}</title>
            </rect>;
          })))}
        </svg>
      </div>

      <aside className="map-selection" aria-live="polite">
        <div className="map-counts">
          <span><strong>{counts.available}</strong> libres</span><span><strong>{counts.reserved}</strong> reservadas</span>
          <span><strong>{counts.occupied}</strong> ocupadas</span><span><strong>{counts.unknown}</strong> sin datos</span>
        </div>
        {selected ? <>
          <p className="eyebrow">Plaza seleccionada</p><h2>{selected.label}</h2>
          <p className="muted">Zona {selected.label.split("-")[0]} · Sensor {selected.sensor_status === "fresh" ? "actualizado" : "sin datos recientes"}</p>
          <dl className="map-spot-details">
            <div><dt>Estado</dt><dd>{STATUS_LABEL[selected.availability]}</dd></div>
            <div><dt>Último reporte</dt><dd>{selected.last_report_at ? new Date(selected.last_report_at).toLocaleTimeString("es-UY") : "Nunca"}</dd></div>
          </dl>
          <button className="primary-button full" disabled={selected.availability !== "available" || reservingId !== null} onClick={() => onReserve(selected)}>
            {reservingId === selected.id ? "Reservando…" : "Reservar plaza"}
          </button>
          <button className="secondary-button full" type="button" onClick={() => { setSelectedId(null); setMapMessage(null); }}>Cancelar selección</button>
        </> : <div className="map-empty-selection"><div className="map-pin">P</div><h2>Ninguna plaza elegida</h2><p className="muted">Seleccioná una plaza libre en el mapa o buscala por su código.</p></div>}
        {mapMessage && <p className="map-message">{mapMessage}</p>}
      </aside>
    </div>
  </section>;
}
