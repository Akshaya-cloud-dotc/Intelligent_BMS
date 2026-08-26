import React from 'react';
import { Database, Hash, Columns, FileType, HardDrive } from 'lucide-react';
import { DatasetInfo } from './DatasetUpload';
import { motion } from 'framer-motion';

interface Props {
  info: DatasetInfo;
  stats?: any;
}

export const DatasetInfoCard: React.FC<Props> = ({ info, stats }) => {
  const formatBytes = (bytes: number, decimals = 2) => {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
  };

  const statBoxes = [
    { label: 'Rows', value: info.rowCount.toLocaleString(), icon: Hash, color: '#A2D2FF' },
    { label: 'Columns', value: info.colCount.toLocaleString(), icon: Columns, color: '#FFC8DD' },
    { label: 'Type', value: info.fileType, icon: FileType, color: '#FFD6A5' },
    { label: 'Size', value: formatBytes(info.fileSize), icon: HardDrive, color: '#BDE0BE' },
  ];

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card"
    >
      <div className="flex items-center space-x-3 mb-6 border-b pb-4" style={{ borderColor: '#E6E2F0' }}>
        <div className="p-2 bg-pastel-bg rounded-lg" style={{ backgroundColor: '#F8F7FF' }}>
          <Database className="w-5 h-5" style={{ color: '#5E84B7' }} />
        </div>
        <div>
          <h2 className="section-title text-[18px] m-0" style={{ color: '#4E4B66' }}>Dataset Information</h2>
          <p className="secondary-text text-[12px] m-0" style={{ color: '#9B98B5' }}>{info.filename}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {statBoxes.map((stat, idx) => (
          <div key={idx} className="flex items-center p-3 rounded-[12px] border" style={{ borderColor: '#F3F4F6', backgroundColor: '#FDFDFF' }}>
            <div className="p-2 rounded-lg mr-3" style={{ backgroundColor: `${stat.color}20` }}>
              <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: '#9B98B5' }}>{stat.label}</p>
              <p className="text-[16px] font-bold" style={{ color: '#4E4B66' }}>{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t pt-4" style={{ borderColor: '#E6E2F0' }}>
        <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: '#9B98B5' }}>Detected Columns</p>
        <div className="flex flex-wrap gap-2 max-h-[120px] overflow-y-auto pr-2 mb-4">
          {info.columns.map((col, idx) => (
            <span 
              key={idx} 
              className="px-2 py-1 rounded-[6px] text-[11px] font-medium border"
              style={{ backgroundColor: '#F7F6FA', borderColor: '#E6E2F0', color: '#6B7280' }}
            >
              {col}
            </span>
          ))}
        </div>
        <div className="p-3 rounded-[8px] bg-blue-50 border border-blue-100 mt-2 text-[12px] text-blue-800">
          <strong>Note:</strong> Real logged fault data provides the highest prediction accuracy. Synthetic fault generation is applied automatically to balance classes and is highly useful for demonstrations and baseline modeling.
        </div>
      </div>
      
      {stats && (
        <div className="border-t pt-4 mt-4" style={{ borderColor: '#E6E2F0' }}>
          <p className="text-[14px] font-bold mb-3" style={{ color: '#4E4B66' }}>Dataset Summary</p>
          <div className="grid grid-cols-3 gap-2 mb-4 text-center">
            <div className="p-2 rounded-lg border bg-gray-50 border-gray-100">
              <p className="text-[11px] text-gray-500 uppercase font-bold">Existing</p>
              <p className="text-[16px] font-bold text-gray-700">{stats.existing_rows.toLocaleString()}</p>
            </div>
            <div className="p-2 rounded-lg border bg-green-50 border-green-100">
              <p className="text-[11px] text-green-600 uppercase font-bold">Appended</p>
              <p className="text-[16px] font-bold text-green-800">+{stats.new_rows.toLocaleString()}</p>
            </div>
            <div className="p-2 rounded-lg border bg-blue-50 border-blue-100">
              <p className="text-[11px] text-blue-600 uppercase font-bold">Final Master</p>
              <p className="text-[16px] font-bold text-blue-800">{stats.final_rows.toLocaleString()}</p>
            </div>
          </div>
          <p className="text-[12px] font-bold uppercase tracking-wider mb-2" style={{ color: '#9B98B5' }}>New Data Modes</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.mode_counts || {}).map(([mode, count]: any) => (
              <span key={mode} className="px-2 py-1 rounded-[6px] text-[11px] font-medium border border-indigo-100 bg-indigo-50 text-indigo-700">
                {mode}: {count.toLocaleString()}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};
