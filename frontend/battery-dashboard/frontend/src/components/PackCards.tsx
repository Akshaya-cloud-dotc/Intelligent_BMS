import React from 'react';
import { PackParameters } from '../types';

interface Props {
  params: PackParameters;
}

export const PackCards: React.FC<Props> = ({ params }) => {
  const cards = [
    {
      title: 'Pack Nominal Voltage',
      value: params.pack_nominal_voltage.toFixed(2),
      unit: 'V',
    },
    {
      title: 'Pack Capacity',
      value: params.pack_capacity.toFixed(2),
      unit: 'Ah',
    },
    {
      title: 'Pack Energy',
      value: params.pack_energy_wh.toFixed(2),
      unit: 'Wh',
    },
    {
      title: 'Pack Std. Charge Current',
      value: params.pack_standard_charge_current.toFixed(2),
      unit: 'A',
    },
    {
      title: 'Pack Max. Discharge Current',
      value: params.pack_maximum_discharge_current.toFixed(2),
      unit: 'A',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-[24px]">
      {cards.map((card, idx) => (
        <div
          key={idx}
          className="glass-card flex flex-col justify-center items-center py-10"
        >
          <h3 className="card-label mb-4 text-[16px] text-center">
            {card.title}
          </h3>
          <div className="flex items-baseline space-x-2">
            <span className="font-bold text-[64px] leading-none" style={{ color: '#5E84B7' }}>
              {card.value}
            </span>
            <span className="font-bold text-[24px]" style={{ color: '#9B98B5' }}>
              {card.unit}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};
