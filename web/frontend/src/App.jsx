import { useState } from "react";
import {
  Activity, Brain, Bone, HeartPulse, Wind,
  Search, Settings, Home, BookOpen,
  Maximize2, RotateCcw, ZoomIn, ZoomOut,
  ChevronRight, Menu, Sparkles
} from "lucide-react";

import "./App.css";

const systems = [
  { name: "Skeletal System", icon: Bone, color: "#64748b" },
  { name: "Muscular System", icon: Activity, color: "#dc7777" },
  { name: "Nervous System", icon: Brain, color: "#a78bfa" },
  { name: "Circulatory System", icon: HeartPulse, color: "#e66b78" },
  { name: "Respiratory System", icon: Wind, color: "#60a5fa" },
];

function App() {
  const [selected, setSelected] = useState("Skeletal System");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">H</div>
          <div>
            <h2>HoloHuman<span>3D</span></h2>
            <small>ANATOMY EXPLORATION PLATFORM</small>
          </div>
        </div>

        <nav>
          <a className="active"><Home size={17} /> Explore</a>
          <a><BookOpen size={17} /> Learn</a>
          <a><Activity size={17} /> Quiz</a>
        </nav>

        <div className="top-actions">
          <button className="icon-button"><Search size={19} /></button>
          <button className="icon-button"><Settings size={19} /></button>
          <div className="avatar">U</div>
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar">
          <div className="section-heading">
            <span>BODY SYSTEMS</span>
            <button className="icon-button"><Menu size={17} /></button>
          </div>

          <div className="system-list">
            {systems.map(({ name, icon: Icon, color }) => (
              <button
                key={name}
                className={`system-item ${selected === name ? "selected" : ""}`}
                onClick={() => setSelected(name)}
              >
                <Icon size={19} color={color} />
                <span>{name}</span>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>

          <div className="sidebar-bottom">
            <Sparkles size={18} />
            <div>
              <strong>Explore deeper</strong>
              <p>Discover the human body, one layer at a time.</p>
            </div>
          </div>
        </aside>

        <section className="viewer">
          <div className="viewer-heading">
            <div>
              <span className="eyebrow">3D ANATOMY VIEWER</span>
              <h1>Explore the human body</h1>
              <p>Discover anatomy through interactive 3D exploration.</p>
            </div>
            <button className="view-button">
              <Maximize2 size={16} /> Expand
            </button>
          </div>

          <div className="model-stage">
            <div className="model-placeholder">
              <div className="model-circle">
                <Activity size={65} strokeWidth={1} />
              </div>
              <h2>3D Anatomy Workspace</h2>
              <p>Your interactive human anatomy model will appear here.</p>
              <span className="coming-soon">3D MODEL IN DEVELOPMENT</span>
            </div>

            <div className="viewer-controls">
              <button title="Zoom in"><ZoomIn /></button>
              <button title="Zoom out"><ZoomOut /></button>
              <button title="Reset view"><RotateCcw /></button>
            </div>

            <div className="viewer-label">CURRENT VIEW · HUMAN ANATOMY</div>
          </div>

          <div className="viewer-footer">
            <span><span className="status-dot" /> Viewer ready</span>
            <span>Gesture controls · Coming soon</span>
          </div>
        </section>

        <aside className="details">
          <span className="eyebrow">ANATOMY DETAILS</span>
          <h2>{selected}</h2>
          <p className="details-description">
            Explore the structures, functions and relationships within
            this body system.
          </p>

          <div className="detail-card">
            <span>OVERVIEW</span>
            <p>
              Detailed anatomical information will be available
              when the 3D model and educational database are integrated.
            </p>
          </div>

          <div className="detail-card">
            <span>LEARNING PATH</span>
            <div className="learning-step">01 · System overview</div>
            <div className="learning-step">02 · Major structures</div>
            <div className="learning-step">03 · Individual organs</div>
            <div className="learning-step">04 · Microscopic anatomy</div>
          </div>

          <button className="learn-button">
            <BookOpen size={17} /> Explore this system
          </button>
        </aside>
      </main>
    </div>
  );
}

export default App;