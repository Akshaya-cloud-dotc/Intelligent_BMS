import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Shield, Sliders, Users } from 'lucide-react';

const HomePage = () => {
  const navigate = useNavigate();

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { 
      opacity: 1,
      transition: { staggerChildren: 0.12 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { 
      opacity: 1, 
      y: 0, 
      transition: { type: 'spring', stiffness: 100, damping: 18 } 
    }
  };

  return (
    <div className="min-h-screen pb-20 bg-slate-50" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
      
      {/* Sleek Hero Header */}
      <div className="relative w-full py-20 px-6 text-center bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white rounded-b-[40px] shadow-lg overflow-hidden">
        {/* Glow decorative background blobs */}
        <div className="absolute top-[-50%] left-[-20%] w-[600px] h-[600px] rounded-full bg-indigo-500/10 blur-[120px] pointer-events-none"></div>
        <div className="absolute bottom-[-50%] right-[-20%] w-[600px] h-[600px] rounded-full bg-blue-500/10 blur-[120px] pointer-events-none"></div>

        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="relative max-w-4xl mx-auto z-10"
        >
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight mt-6 mb-4 text-white leading-tight">
            Intelligent Battery Management System
          </h1>
          <p className="text-base md:text-lg text-slate-300 font-medium max-w-2xl mx-auto">
            Edge-to-cloud AI platform for battery parameter extraction, multi-chemistry configurations, and time-series ML fault detection.
          </p>
        </motion.div>
      </div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="max-w-6xl mx-auto px-6 -mt-10 space-y-10 relative z-20"
      >
        {/* Choice Cards (2-column layout) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* Card 1: Fault Detection */}
          <motion.div 
            variants={itemVariants}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            className="bg-white rounded-[24px] p-8 md:p-10 border border-slate-100 shadow-xl shadow-slate-200/50 relative overflow-hidden flex flex-col justify-between"
          >
            <div className="absolute top-6 right-6 text-indigo-500/5 pointer-events-none">
              <Shield size={160} />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3.5 rounded-2xl bg-indigo-50 text-indigo-600">
                  <Shield className="w-7 h-7" />
                </div>
                <span className="text-[12px] font-bold text-indigo-600 uppercase tracking-widest">
                  Live Stream (Layer 1 & 2)
                </span>
              </div>
              <h2 className="text-[24px] md:text-[28px] font-extrabold text-slate-800 mb-4">
                Real-Time Telemetry & Fault Detection
              </h2>
              <p className="text-slate-500 text-sm md:text-base leading-relaxed mb-8">
                Stream live data from your battery pack, monitor cell voltages, compute power/energy, and run predictive machine learning models to identify cell imbalances or weak cell anomalies.
              </p>
            </div>
            <button 
              onClick={() => {
                window.location.href = window.location.origin + '/live-monitor';
              }}
              className="w-full md:w-fit px-8 py-3.5 rounded-full font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              Open Live Monitor <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>

          {/* Card 2: Multi-Chemistry Configurator */}
          <motion.div 
            variants={itemVariants}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            className="bg-white rounded-[24px] p-8 md:p-10 border border-slate-100 shadow-xl shadow-slate-200/50 relative overflow-hidden flex flex-col justify-between"
          >
            <div className="absolute top-6 right-6 text-slate-800/5 pointer-events-none">
              <Sliders size={160} />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3.5 rounded-2xl bg-slate-50 text-slate-700">
                  <Sliders className="w-7 h-7" />
                </div>
                <span className="text-[12px] font-bold text-slate-600 uppercase tracking-widest">
                  Configuration Engine
                </span>
              </div>
              <h2 className="text-[24px] md:text-[28px] font-extrabold text-slate-800 mb-4">
                Multi-Chemistry Configurator
              </h2>
              <p className="text-slate-500 text-sm md:text-base leading-relaxed mb-8">
                Upload cell specification PDFs to extract internal chemistry profiles, configure pack sizes, and retrain custom XGBoost ML classification models with your local CSV data.
              </p>
            </div>
            <button 
              onClick={() => navigate('/configurator')}
              className="w-full md:w-fit px-8 py-3.5 rounded-full font-bold text-white bg-slate-800 hover:bg-slate-900 transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-slate-800/20"
            >
              Open Configurator <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>
        </div>

        {/* Team Information Footer Card */}
        <motion.div 
          variants={itemVariants}
          className="bg-white rounded-[24px] p-8 md:p-10 border border-slate-100 shadow-md flex flex-col md:flex-row items-center justify-between gap-6"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-slate-50 text-slate-600 hidden sm:block">
              <Users className="w-6 h-6" />
            </div>
            <div className="text-center md:text-left">
              <h4 className="text-[12px] font-bold text-slate-400 uppercase tracking-widest mb-1">Developed By</h4>
              <h3 className="text-2xl md:text-3xl font-black text-slate-800">TEAM ANS_4X</h3>
              <p className="text-sm font-medium text-slate-500 mt-1">PSG Institute of Technology and Applied Research</p>
            </div>
          </div>
          <span className="px-5 py-2 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100 uppercase tracking-wider">
            PSG iTech
          </span>
        </motion.div>

      </motion.div>
    </div>
  );
};

export default HomePage;
