import { useState, useEffect } from 'react';
import { UploadCard } from '../components/UploadCard';
import { PackConfiguration } from '../components/PackConfiguration';
import { ParameterTable } from '../components/ParameterTable';
import { PackCards } from '../components/PackCards';
import { FaultCharts } from '../components/FaultCharts';
import { CellParameters, PackParameters, FaultThresholds } from '../types';
import { Activity } from 'lucide-react';
import { motion } from 'framer-motion';
import { DatasetUpload, DatasetInfo } from '../components/DatasetUpload';
import { DatasetInfoCard } from '../components/DatasetInfoCard';
import { uploadPdf, calculatePack, saveActiveProfile, trainModel } from '../services/api';

function BatteryDashboard() {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);
  const [cellParams, setCellParams] = useState<CellParameters | null>(null);
  const [seriesCells, setSeriesCells] = useState<number>(8);
  const [parallelCells, setParallelCells] = useState<number>(2);
  
  const [packParams, setPackParams] = useState<PackParameters | null>(null);
  const [faultThresholds, setFaultThresholds] = useState<FaultThresholds | null>(null);
  const [datasetInfo, setDatasetInfo] = useState<DatasetInfo | null>(null);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const params = await uploadPdf(file);
      setCellParams(params);
      setUploadCount(prev => prev + 1);
    } catch (error) {
      console.error(error);
      alert('Failed to process PDF.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!cellParams || !faultThresholds) return;
    try {
      await saveActiveProfile(cellParams, faultThresholds);
      alert('Active profile saved successfully! The ML Dashboard is now using these thresholds.');
    } catch (error) {
      console.error(error);
      alert('Failed to save active profile.');
    }
  };

  const [uploadMode, setUploadMode] = useState<'replace' | 'append'>('replace');
  const [datasetStats, setDatasetStats] = useState<any>(null);

  const [isTraining, setIsTraining] = useState(false);
  const handleTrainModel = async () => {
    if (!datasetInfo?.rawFile) return;
    setIsTraining(true);
    setDatasetStats(null);
    try {
      const res = await trainModel(datasetInfo.rawFile, uploadMode);
      if (res.status === 'warning') {
        alert(`WARNING: ${res.message}`);
      } else {
        alert(res.message);
      }
      if (res.stats) {
        setDatasetStats(res.stats);
      }
    } catch (error: any) {
      console.error(error);
      alert(error.message || 'Failed to train model.');
    } finally {
      setIsTraining(false);
    }
  };

  const handleParameterChange = (key: keyof CellParameters, value: number | string | null) => {
    if (cellParams) {
      setCellParams({
        ...cellParams,
        [key]: value
      });
    }
  };

  useEffect(() => {
    if (cellParams) {
      const updateCalculations = async () => {
        try {
          const res = await calculatePack(cellParams, seriesCells, parallelCells);
          setPackParams(res.pack);
          setFaultThresholds(res.thresholds);
        } catch (error) {
          console.error(error);
        }
      };
      updateCalculations();
    }
  }, [cellParams, seriesCells, parallelCells]);

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: '#F7F6FA', color: '#4E4B66' }}>
      <div className="max-w-7xl mx-auto space-y-[24px]">
        
        {/* Header */}
        <motion.header 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center space-x-3 mb-4"
        >
          <Activity className="w-8 h-8" style={{ color: '#5E84B7' }} />
          <h1 className="page-title">
            Battery Parameters
          </h1>
        </motion.header>

        {/* Row 1: Extracted Parameters & Pack Configuration (Visible only after upload) */}
        {cellParams && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 lg:grid-cols-12 gap-[24px]"
          >
            <div className="lg:col-span-4 h-fit">
              <PackConfiguration 
                series={seriesCells} 
                parallel={parallelCells} 
                onSeriesChange={setSeriesCells} 
                onParallelChange={setParallelCells} 
              />
            </div>
            <div className="lg:col-span-8 flex flex-col gap-[24px]">
              <ParameterTable 
                key={uploadCount} 
                params={cellParams} 
                onParameterChange={handleParameterChange} 
              />
              <div className="flex justify-end">
                <button 
                  onClick={handleSaveProfile}
                  className="px-6 py-3 rounded-full font-semibold transition-colors"
                  style={{ backgroundColor: '#5E84B7', color: 'white' }}
                >
                  Save as Active Profile
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Row 2: Upload Cards & Info */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-[24px]">
          <div>
            <UploadCard onUpload={handleUpload} isUploading={isUploading} />
          </div>
          <div>
            <DatasetUpload onDatasetParsed={setDatasetInfo} />
          </div>
          <div>
            {datasetInfo ? (
              <div className="flex flex-col gap-4 h-full">
                <DatasetInfoCard info={datasetInfo} stats={datasetStats} />
                <div className="flex items-center gap-6 px-2">
                  <label className="flex items-center space-x-2 text-[14px] cursor-pointer">
                    <input type="radio" value="replace" checked={uploadMode === 'replace'} onChange={() => setUploadMode('replace')} className="accent-indigo-600" />
                    <span className="font-medium text-gray-700">Replace Dataset</span>
                  </label>
                  <label className="flex items-center space-x-2 text-[14px] cursor-pointer">
                    <input type="radio" value="append" checked={uploadMode === 'append'} onChange={() => setUploadMode('append')} className="accent-indigo-600" />
                    <span className="font-medium text-gray-700">Append Dataset</span>
                  </label>
                </div>
                <button 
                  onClick={handleTrainModel}
                  disabled={isTraining}
                  className="w-full px-6 py-3 rounded-xl font-semibold transition-colors flex justify-center items-center h-[52px]"
                  style={{ backgroundColor: isTraining ? '#ccc' : '#8D81B8', color: 'white' }}
                >
                  {isTraining ? 'Training XGBoost Model...' : 'Train ML Model'}
                </button>
              </div>
            ) : (
              <div className="glass-card h-full flex items-center justify-center">
                <p className="secondary-text text-center italic">
                  Upload a dataset to view its information.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Row 3 & 4: Analytics (Visible only after upload) */}
        {cellParams && packParams && faultThresholds && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col gap-[24px]"
          >
            {/* Row 3: Pack Cards */}
            <PackCards params={packParams} />

            {/* Row 4: Fault Thresholds */}
            <FaultCharts faults={faultThresholds} />
          </motion.div>
        )}

      </div>
    </div>
  );
}

export default BatteryDashboard;
