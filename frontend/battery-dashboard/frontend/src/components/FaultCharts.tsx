import React from 'react';
import { FaultThresholds } from '../types';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface Props {
  faults: FaultThresholds;
}

export const FaultCharts: React.FC<Props> = ({ faults }) => {
  const createData = (warning: number, critical: number) => {
    return [
      { name: 'Safe', value: warning, color: '#5B9B6B' },
      { name: 'Warning', value: critical - warning, color: '#F2E8CF' },
    ];
  };

  const GaugeChart = ({ title, data, criticalValue, unit }: any) => (
    <div className="flex flex-col items-center">
      <h4 className="card-label mb-6 text-[16px] text-center">{title}</h4>
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={90}
              outerRadius={130}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((entry: any, index: number) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ backgroundColor: '#FDFDFF', borderColor: '#E6E2F0', borderRadius: '12px' }} itemStyle={{ color: '#4E4B66' }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-8 text-center flex items-baseline justify-center">
        <span className="font-bold leading-none" style={{ color: '#C3923F', fontSize: '48px' }}>{criticalValue.toFixed(2)}</span>
        <span className="font-bold ml-2 text-[24px]" style={{ color: '#C3923F' }}>{unit}</span>
      </div>
      <div className="card-label mt-2 text-[14px]">Critical Limit</div>
    </div>
  );

  return (
    <div className="glass-card">
      <h2 className="section-title mb-10 border-b pb-2 text-[20px]" style={{ borderColor: '#E6E2F0' }}>
        Fault Thresholds
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pb-4">
        <GaugeChart
          title="Overvoltage Limit"
          data={createData(faults.overvoltage_warning, faults.overvoltage_critical)}
          criticalValue={faults.overvoltage_critical}
          unit="V"
        />
        <GaugeChart
          title="Overcurrent Limit"
          data={createData(faults.overcurrent_warning, faults.overcurrent_critical)}
          criticalValue={faults.overcurrent_critical}
          unit="A"
        />
        {faults.overtemperature_critical !== null ? (
           <GaugeChart
            title="Overtemperature Limit"
            data={createData(faults.overtemperature_warning_min || 45, faults.overtemperature_critical)}
            criticalValue={faults.overtemperature_critical}
            unit="°C"
          />
        ) : (
          <div className="flex items-center justify-center h-full secondary-text italic text-center">
            Temperature data unavailable
          </div>
        )}
      </div>
    </div>
  );
};
