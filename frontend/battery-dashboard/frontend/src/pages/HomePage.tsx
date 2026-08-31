import { useNavigate } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';

const HomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F3F4F6] selection:bg-[#D9C3B0] selection:text-[#0A0A0B] pb-24" style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif' }}>
      
      {/* Editorial Header */}
      <header className="max-w-7xl mx-auto px-8 pt-8 pb-12 flex justify-between items-baseline border-b border-[#1F1F23]">
        <div className="text-xs font-mono tracking-[0.25em] text-[#A1A1AA]">
          AI-PBMS // SYSTEM
        </div>
        <div className="text-xs font-mono tracking-[0.2em] text-[#D9C3B0] uppercase">
          PSG iTech · Staging
        </div>
      </header>

      {/* Hero Section - Intentional Composition & Asymmetry */}
      <section className="max-w-7xl mx-auto px-8 pt-20 pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* Main Title - Columns 1 to 8 */}
          <div className="lg:col-span-8">
            <span className="text-[10px] font-mono tracking-[0.3em] text-[#D9C3B0] uppercase block mb-4">
              [ 01 / INTRODUCTION ]
            </span>
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-extralight tracking-tight leading-[1.05] text-[#F3F4F6] max-w-3xl">
              Intelligent battery management and predictive diagnostics.
            </h1>
          </div>

          {/* Subtitle / Paragraph - Columns 9 to 12 (Shifted down slightly on desktop for composition) */}
          <div className="lg:col-span-4 lg:pt-16">
            <p className="text-[#9CA3AF] text-sm md:text-base font-light leading-relaxed max-w-sm">
              A professional-grade diagnostic platform designed for mission-critical electrical systems. Monitors live parameters, evaluates time-series battery health, and automates multi-chemistry spec configuration.
            </p>
          </div>

        </div>
      </section>

      {/* Dual Interface Options - Asymmetric Card Grid */}
      <section className="max-w-7xl mx-auto px-8 pb-28">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          
          {/* Card 1: Telemetry Dashboard (55% Width on Desktop) */}
          <div className="lg:col-span-7 bg-[#121214] border border-[#1F1F23] p-10 flex flex-col justify-between min-h-[420px] transition-colors duration-300 hover:border-[#3F3F46] group">
            <div>
              <span className="text-[10px] font-mono tracking-[0.3em] text-[#D9C3B0] uppercase block mb-8">
                INTERFACE _ 01
              </span>
              <h2 className="text-2xl md:text-3xl font-light tracking-tight text-[#F3F4F6] mb-4">
                Real-Time Diagnostics & Anomaly Stream
              </h2>
              <p className="text-[#9CA3AF] text-sm leading-relaxed max-w-md font-light">
                Continuous cell-by-cell voltage mapping, live temperature drift analysis, and predictive categorical fault detection. Integrates directly with hardware BLE gateways.
              </p>
            </div>
            <button 
              onClick={() => {
                window.location.href = window.location.origin + '/live-monitor';
              }}
              className="mt-12 flex items-center gap-2 text-xs font-mono tracking-wider uppercase text-[#D9C3B0] border-b border-[#D9C3B0]/30 pb-1 w-fit transition-all duration-300 hover:border-[#D9C3B0] group-hover:text-white"
            >
              Enter Live Monitor <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Card 2: Configuration & ML Training (45% Width on Desktop) */}
          <div className="lg:col-span-5 bg-[#121214] border border-[#1F1F23] p-10 flex flex-col justify-between min-h-[420px] transition-colors duration-300 hover:border-[#3F3F46] group">
            <div>
              <span className="text-[10px] font-mono tracking-[0.3em] text-[#D9C3B0] uppercase block mb-8">
                INTERFACE _ 02
              </span>
              <h2 className="text-2xl md:text-3xl font-light tracking-tight text-[#F3F4F6] mb-4">
                Multi-Chemistry Spec Configurator
              </h2>
              <p className="text-[#9CA3AF] text-sm leading-relaxed max-w-sm font-light">
                Extract nominal cell parameters from datasheets, calibrate fault thresholds, and retrain custom XGBoost ML classifiers using local dataset logging.
              </p>
            </div>
            <button 
              onClick={() => navigate('/configurator')}
              className="mt-12 flex items-center gap-2 text-xs font-mono tracking-wider uppercase text-[#D9C3B0] border-b border-[#D9C3B0]/30 pb-1 w-fit transition-all duration-300 hover:border-[#D9C3B0] group-hover:text-white"
            >
              Open Configurator <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

        </div>
      </section>

      {/* Technical Specifications Grid - Architectural Structure */}
      <footer className="max-w-7xl mx-auto px-8 border-t border-[#1F1F23] pt-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <span className="text-[9px] font-mono tracking-widest text-[#71717A] uppercase block mb-2">
              DEVELOPED BY
            </span>
            <div className="text-sm font-light text-[#F3F4F6]">
              TEAM ANS_4X
            </div>
            <div className="text-xs text-[#9CA3AF] mt-0.5">
              PSG Institute of Technology
            </div>
          </div>
          
          <div>
            <span className="text-[9px] font-mono tracking-widest text-[#71717A] uppercase block mb-2">
              ACQUISITION RATE
            </span>
            <div className="text-sm font-light text-[#F3F4F6]">
              1.0 Hz (Continuous)
            </div>
            <div className="text-xs text-[#9CA3AF] mt-0.5">
              Low-latency BLE gateway
            </div>
          </div>

          <div>
            <span className="text-[9px] font-mono tracking-widest text-[#71717A] uppercase block mb-2">
              CLASSIFICATION CORE
            </span>
            <div className="text-sm font-light text-[#F3F4F6]">
              XGBoost Anomaly Model
            </div>
            <div className="text-xs text-[#9CA3AF] mt-0.5">
              92.8% Cross-Validation Score
            </div>
          </div>

          <div>
            <span className="text-[9px] font-mono tracking-widest text-[#71717A] uppercase block mb-2">
              SYSTEM BUILD
            </span>
            <div className="text-sm font-light text-[#F3F4F6]">
              v4.2-Staging
            </div>
            <div className="text-xs text-[#9CA3AF] mt-0.5">
              Railway Cloud Deploy
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
};

export default HomePage;
