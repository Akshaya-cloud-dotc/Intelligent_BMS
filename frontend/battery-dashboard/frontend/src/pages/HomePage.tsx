import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

const HomePage = () => {
  const navigate = useNavigate();

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { 
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } }
  };

  return (
    <div className="min-h-screen pb-16" style={{ backgroundColor: '#F7F7F7', color: '#333333', fontFamily: 'Inter, system-ui, sans-serif' }}>
      
      {/* Top Banner */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full py-16 px-8 mb-12 flex flex-col items-center justify-center text-center"
        style={{ backgroundColor: '#FCF7D9' }}
      >
        <h1 className="text-4xl md:text-5xl font-bold mb-4" style={{ color: '#4A4A4A' }}>
          Intelligent Battery Pack for Fault Detection
        </h1>
        <p className="text-lg md:text-xl font-medium" style={{ color: '#737373' }}>
          AI-powered battery parameter extraction and fault prediction.
        </p>
      </motion.div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="max-w-5xl mx-auto px-6 space-y-8"
      >
        {/* First Row: Two Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Main Card: Fault Detection */}
          <motion.div 
            variants={itemVariants}
            whileHover={{ scale: 1.02 }}
            className="md:col-span-2 bg-white rounded-[24px] p-8 md:p-12 border shadow-sm relative overflow-hidden flex flex-col justify-center"
            style={{ borderColor: '#EAEAEA', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}
          >
            <div className="absolute -top-4 -right-4 text-[120px] font-bold leading-none opacity-5 pointer-events-none">01</div>
            <h2 className="text-[24px] md:text-[32px] font-bold tracking-widest uppercase mb-8" style={{ color: '#4A4A4A' }}>FAULT DETECTION</h2>
            <button 
              onClick={() => {
                window.location.href = 'http://127.0.0.1:5000/';
              }}
              className="px-6 py-3 rounded-full font-semibold self-start flex items-center gap-2 transition-colors"
              style={{ backgroundColor: '#F0F0F0', color: '#555555' }}
            >
              OPEN <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>

          {/* Secondary Card: Multi-Chemistry Dashboard */}
          <motion.div 
            variants={itemVariants}
            whileHover={{ scale: 1.02 }}
            className="md:col-span-1 bg-white rounded-[24px] p-8 border shadow-sm relative overflow-hidden flex flex-col justify-center"
            style={{ borderColor: '#EAEAEA', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}
          >
            <div className="absolute -top-4 -right-4 text-[120px] font-bold leading-none opacity-5 pointer-events-none">02</div>
            <h2 className="text-[14px] font-bold tracking-widest uppercase mb-8" style={{ color: '#888888' }}>MULTI-CHEMISTRY DASHBOARD ★</h2>
            <button 
              onClick={() => navigate('/configurator')}
              className="px-6 py-3 rounded-full font-semibold self-start flex items-center gap-2 transition-colors"
              style={{ backgroundColor: '#F0F0F0', color: '#555555' }}
            >
              OPEN <ArrowRight className="w-4 h-4" />
            </button>
          </motion.div>
        </div>

        {/* Team Information Card */}
        <motion.div 
          variants={itemVariants}
          whileHover={{ scale: 1.02 }}
          className="bg-white rounded-[24px] p-12 border shadow-sm flex flex-col items-center justify-center text-center mx-auto max-w-3xl"
          style={{ borderColor: '#EAEAEA', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}
        >
          <h2 className="text-[14px] font-bold tracking-widest uppercase mb-6" style={{ color: '#888888' }}>
            Team Information
          </h2>
          <h3 className="text-[32px] md:text-[40px] font-bold mb-4" style={{ color: '#4A4A4A' }}>
            TEAM ANS_4X
          </h3>
          <p className="text-[18px] md:text-[20px] font-medium" style={{ color: '#737373' }}>
            PSG Institute of Technology and Applied Research
          </p>
        </motion.div>

      </motion.div>
    </div>
  );
};

export default HomePage;
