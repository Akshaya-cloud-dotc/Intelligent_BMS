import React from 'react';

interface Props {
  series: number;
  parallel: number;
  onSeriesChange: (val: number) => void;
  onParallelChange: (val: number) => void;
}

export const PackConfiguration: React.FC<Props> = ({
  series,
  parallel,
  onSeriesChange,
  onParallelChange,
}) => {
  return (
    <div className="glass-card flex flex-col justify-center h-full">
      <h2 className="section-title mb-6 border-b pb-2" style={{ borderColor: '#E6E2F0' }}>
        Pack Configuration
      </h2>
      <div className="flex flex-col space-y-8">
        <div className="flex items-center justify-between">
          <label className="card-label">Cells in Series (S)</label>
          <input
            type="number"
            min="1"
            value={series}
            onChange={(e) => onSeriesChange(parseInt(e.target.value) || 1)}
            className="primary-value w-24 text-right bg-transparent focus:outline-none"
            style={{ borderBottom: '2px solid #E6E2F0', paddingBottom: '4px' }}
          />
        </div>
        <div className="flex items-center justify-between">
          <label className="card-label">Cells in Parallel (P)</label>
          <input
            type="number"
            min="1"
            value={parallel}
            onChange={(e) => onParallelChange(parseInt(e.target.value) || 1)}
            className="primary-value w-24 text-right bg-transparent focus:outline-none"
            style={{ borderBottom: '2px solid #E6E2F0', paddingBottom: '4px' }}
          />
        </div>
      </div>
    </div>
  );
};
