import './App.css'

function App() {
  return (
    <main className="page">
      <div className='warning'>
        <div class="warning-icon">⚠️</div>
          <div class="warning-content">
           <div class="warning-title">Note</div>
          <p className="warning-text">This is a demo version. If you find any bugs or encounter any issues please report to: riyadhg002@gmail.com</p> 
        </div>
      </div>

      {/* Hero */}
      <section id="home" className="hero">

        <div className="hero-doodle doodle-star">✦</div>
        <div className="hero-doodle doodle-heart">♡</div>
        <div className="hero-doodle doodle-sparkle">✧</div>

        <div className="hero-text">
          <p className="eyebrow">WELCOME TO OUR LITTLE CORNER</p>

          <h1>
            Just two people
            <br />
            <span>hanging out.</span>
          </h1>

          <p className="hero-description">
            Watch something, talk nonsense, play a game,
            or just exist here together.
          </p>

          <div className="hero-buttons">
            <a href="#watch" className="button button-yellow">
              Let's Watch →
            </a>

            <a href="/rooms" className="button button-pink">
              Say something
            </a>
          </div>
        </div>

        <div className="hero-card">
          <div className="tape"></div>

          <div className="mini-screen">
            <span>●</span>
            <p>Currently hanging out</p>
          </div>

          <div className="hero-card-content">
            <div className="avatar avatar-one">X</div>
            <div className="plus">+</div>
            <div className="avatar avatar-two">Y</div>
          </div>

          <p className="tiny-note">
            Do be do be do
          </p>
        </div>

      </section>


      {/* Main Content */}
      <section className="content-grid">

        {/* Watch */}
        <div id="watch" className="section-card watch-card">
          <div className="card-label">🎬 MOVIE CORNER</div>

          <h2>What are we watching?</h2>

          <div className="video-placeholder">
            <div className="play-button">▶</div>

            <div className="video-lines">
              <span></span>
              <span></span>
              <span></span>
            </div>

            <p>Your video goes here</p>
          </div>

          <div className="watch-controls">
            <button>◀</button>
            <button className="big-control">▶</button>
            <button>▶▶</button>

            <div className="progress">
              <div></div>
            </div>

            <span>00:00</span>
          </div>
        </div>


        {/* Chat */}
        <div id="chat" className="section-card chat-card">
          <div className="card-label">💬 THE YAPPING ZONE</div>

          <h2>Say something.</h2>

          <div className="chat-window">

            <div className="message message-left">
              <div className="chat-avatar blue">X</div>
              <div>
                <span className="name">Xavier</span>
                <p>Where did you disappear?</p>
              </div>
            </div>

            <div className="message message-right">
              <div>
                <span className="name">R</span>
                <p>I was busy being mysterious.</p>
              </div>
              <div className="chat-avatar yellow">R</div>
            </div>

            <div className="message message-left">
              <div className="chat-avatar blue">X</div>
              <div>
                <span className="name">Xavier</span>
                <p>Sure you were.</p>
              </div>
            </div>

          </div>

          <div className="chat-input">
            <input
              type="text"
              placeholder="Type something silly..."
            />
            <button>Send!</button>
          </div>
        </div>


        {/* Games */}
        <div id="games" className="section-card games-card">
          <div className="card-label">🎮 PLAYGROUND</div>

          <h2>Do something stupid.</h2>

          <div className="games-grid">

            <button className="game-button game-pink">
              <span>⭕</span>
              Tic Tac Toe
            </button>

            <button className="game-button game-blue">
              <span>🃏</span>
              Cards
            </button>

            <button className="game-button game-green">
              <span>❓</span>
              Would You Rather
            </button>

            <button className="game-button game-orange">
              <span>🎨</span>
              Draw
            </button>

          </div>
        </div>
      </section>


      {/* Footer */}
      <footer>
        <p>Made for wasting time together ✦</p>
        <span>♡</span>
      </footer>

    </main>
  )
}

export default App