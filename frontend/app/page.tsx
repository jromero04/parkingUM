
import Link from "next/link";

export default function Home() {
    return (
        <main className="landing">
            <nav className="landing-nav">
                <div className="brand">
                    <span>P</span> ParkingUM
                </div>

                <div>
                    <Link href="/login" className="link-button">
                        Ingresar
                    </Link>
                    <Link href="/registro" className="primary-button">
                        Crear cuenta
                    </Link>
                </div>
            </nav>

            <section className="hero">
                <div>
                    <p className="eyebrow">Disponibilidad en tiempo real</p>

                    <h1>
                        Encontrá tu lugar.

                        <br />

                        <em>Sin dar vueltas.
                        </em>
                    </h1>

                    <p>
                        Consultá plazas, reservá en segundos y seguí el estado de tu
                        estacionamiento desde un único lugar.
                    </p>

                    <div className="hero-actions">
                        <Link href="/registro" className="primary-button">
                            Empezar ahora
                        </Link>
                        <Link href="/login" className="secondary-button">
                            Ya tengo cuenta
                        </Link>
                    </div>
                </div>

                {/* Ilustración minimalista de estacionamiento */}
                <div className="hero-card">
                    <div className="parking-illustration">
                        <div className="parking-illustration-header">
                            <span className="parking-dot" />
                            <span>ESTACIONAMIENTO</span>
                        </div>

                        <div className="parking-spaces">
                            <div className="parking-space">
                                <span>A-01</span>
                                <svg viewBox="0 0 40 64" fill="none">
                                    <rect
                                        x="6"
                                        y="2"
                                        width="28"
                                        height="60"
                                        rx="8"
                                        fill="#DBEEFA"
                                        stroke="#1677C8"
                                        strokeWidth="1.5"
                                    />
                                    <rect
                                        x="10"
                                        y="12"
                                        width="20"
                                        height="10"
                                        rx="3"
                                        fill="#FFFFFF"
                                        stroke="#91C8EB"
                                    />
                                    <rect
                                        x="10"
                                        y="42"
                                        width="20"
                                        height="8"
                                        rx="2"
                                        fill="#FFFFFF"
                                        stroke="#91C8EB"
                                    />
                                    <rect x="3" y="18" width="3" height="8" rx="1" fill="#1677C8" />
                                    <rect x="34" y="38" width="3" height="8" rx="1" fill="#1677C8" />
                                </svg>
                                <span className="space-indicator" />
                            </div>

                            <div className="parking-space parking-space-available">
                                <span>A-02</span>
                                <svg viewBox="0 0 40 64" fill="none">
                                    <rect
                                        x="6"
                                        y="2"
                                        width="28"
                                        height="60"
                                        rx="8"
                                        fill="#FFFFFF"
                                        stroke="#B8C8D8"
                                        strokeWidth="1.5"
                                    />
                                    <rect
                                        x="10"
                                        y="12"
                                        width="20"
                                        height="10"
                                        rx="3"
                                        fill="#F1F5F9"
                                        stroke="#CBD5E1"
                                    />
                                    <rect
                                        x="10"
                                        y="42"
                                        width="20"
                                        height="8"
                                        rx="2"
                                        fill="#F1F5F9"
                                        stroke="#CBD5E1"
                                    />
                                </svg>
                                <span className="space-indicator" />
                            </div>

                            <div className="parking-space">
                                <span>A-03</span>
                                <svg viewBox="0 0 40 64" fill="none">
                                    <rect
                                        x="6"
                                        y="2"
                                        width="28"
                                        height="60"
                                        rx="8"
                                        fill="#DBEEFA"
                                        stroke="#1677C8"
                                        strokeWidth="1.5"
                                    />
                                    <rect
                                        x="10"
                                        y="12"
                                        width="20"
                                        height="10"
                                        rx="3"
                                        fill="#FFFFFF"
                                        stroke="#91C8EB"
                                    />
                                    <rect
                                        x="10"
                                        y="42"
                                        width="20"
                                        height="8"
                                        rx="2"
                                        fill="#FFFFFF"
                                        stroke="#91C8EB"
                                    />
                                    <rect x="3" y="30" width="3" height="8" rx="1" fill="#1677C8" />
                                    <rect x="34" y="18" width="3" height="8" rx="1" fill="#1677C8" />
                                </svg>
                                <span className="space-indicator" />
                            </div>
                        </div>

                        <div className="parking-legend">
              <span>
                <i className="legend-available" />
                Disponible
              </span>
                            <span>
                <i className="legend-occupied" />
                Ocupado
              </span>
                        </div>
                    </div>
                </div>
            </section>
            <section className="about-section">
                <div className="about-content">
                    <p className="eyebrow">CONOCÉ NUESTRA PROPUESTA</p>
                    <h2>Acerca de ParkingUM</h2>
                    <p className="about-description">
                        ParkingUM es una plataforma pensada para facilitar la búsqueda y
                        reserva de estacionamientos. Su objetivo es que puedas consultar
                        la disponibilidad de plazas, reservar un lugar y gestionar tus
                        reservas desde un solo sitio, de forma sencilla y organizada.
                    </p>

                    <div className="about-features">
                        <article className="about-feature">
                            <span className="about-icon">⌕</span>
                            <div>
                                <h3>Encontrá tu lugar</h3>
                                <p>Consultá las plazas disponibles sin complicaciones.</p>
                            </div>
                        </article>

                        <article className="about-feature">
                            <span className="about-icon">✓</span>
                            <div>
                                <h3>Reservá fácilmente</h3>
                                <p>Gestioná tus reservas desde la plataforma.</p>
                            </div>
                        </article>

                        <article className="about-feature">
                            <span className="about-icon">▦</span>
                            <div>
                                <h3>Todo en un solo lugar</h3>
                                <p>
                                    Accedé a la información de tus estacionamientos y reservas
                                    de manera organizada.
                                </p>
                            </div>
                        </article>
                    </div>
                </div>
            </section>
        </main>
    );
}

