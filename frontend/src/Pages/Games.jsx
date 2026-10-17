function Games() {
  return (
    <main className="page games-page-shell">
      <section className="games-under-construction" aria-labelledby="games-title">
        <div className="games-glow games-glow-one" aria-hidden="true" />
        <div className="games-glow games-glow-two" aria-hidden="true" />
        <div className="games-glow games-glow-three" aria-hidden="true" />

        <div className="games-panel">
          <p className="eyebrow">GAME ROOM</p>
          <h1 id="games-title">Multiplayer games are on the way.</h1>
          <p>
            We’re building a playful space for room-based games, but this feature is still under construction.
            Expect a more complete arcade experience soon.
          </p>

          <div className="games-badges" aria-label="Upcoming game features">
            <span>Room games</span>
            <span>Live play</span>
            <span>Friendly chaos</span>
          </div>

          <div className="games-progress" aria-hidden="true">
            <div className="games-progress-bar" />
          </div>
        </div>
      </section>
    </main>
  )
}

export default Games
