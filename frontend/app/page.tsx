import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <nav className="landing-nav"><div className="brand"><span>P</span> Parking SD</div><div><Link href="/login" className="link-button">Ingresar</Link><Link href="/registro" className="primary-button">Crear cuenta</Link></div></nav>
      <section className="hero">
        <div><p className="eyebrow">Disponibilidad en tiempo real</p><h1>Encontrá tu lugar.<br /><em>Sin dar vueltas.</em></h1><p>Consultá plazas, reservá en segundos y seguí el estado de tu estacionamiento desde un único lugar.</p><div className="hero-actions"><Link href="/registro" className="primary-button">Empezar ahora</Link><Link href="/login" className="secondary-button">Ya tengo cuenta</Link></div></div>
        <div className="hero-card"><div className="parking-preview"><span className="preview-label">Parking Central</span><strong>A-01</strong><span className="status status-available">Disponible</span></div><div className="pulse-ring" /></div>
      </section>
      <section className="value-grid"><article><strong>01</strong><h2>Datos actuales</h2><p>Los sensores mantienen la disponibilidad de cada plaza al día.</p></article><article><strong>02</strong><h2>Reserva segura</h2><p>Cada operación es idempotente y recuperable ante fallos.</p></article><article><strong>03</strong><h2>Visión operativa</h2><p>Administradores acceden a métricas y alertas de sensores.</p></article></section>
    </main>
  );
}
