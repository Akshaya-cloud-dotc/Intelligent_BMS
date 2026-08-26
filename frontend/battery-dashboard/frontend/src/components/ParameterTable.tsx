import React, { useState, useEffect } from 'react';
import { CellParameters } from '../types';

interface Props {
  params: CellParameters;
  onParameterChange: (key: keyof CellParameters, value: number | string | null) => void;
}

const EditableCell = ({ value, onBlur, isString = false, placeholder = "Enter value" }: { value: any, onBlur: (val: any) => void, isString?: boolean, placeholder?: string }) => {
  const [localValue, setLocalValue] = useState(value !== null && value !== undefined ? String(value) : '');

  useEffect(() => {
    if (value !== null && value !== undefined) {
      setLocalValue(String(value));
    } else {
      setLocalValue('');
    }
  }, [value]);

  const handleBlur = () => {
    if (localValue.trim() === '') {
      // Reject empty values, restore previous
      setLocalValue(value !== null && value !== undefined ? String(value) : '');
      return;
    }
    
    if (isString) {
      onBlur(localValue);
      return;
    }

    const num = parseFloat(localValue);
    if (isNaN(num)) {
      setLocalValue(value !== null && value !== undefined ? String(value) : '');
    } else {
      // Only call onBlur if changed
      if (num !== value) {
        setLocalValue(String(num));
        onBlur(num);
      } else {
        setLocalValue(String(num)); // clean up formatting
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let raw = e.target.value;
    if (!isString) {
      raw = raw.replace(/[^0-9.-]/g, '');
      if (raw.indexOf('-') > 0) {
        raw = raw.replace(/-/g, (_, offset) => (offset === 0 ? '-' : ''));
      }
      const parts = raw.split('.');
      if (parts.length > 2) {
        raw = parts[0] + '.' + parts.slice(1).join('');
      }
    }
    setLocalValue(raw);
  };

  return (
    <input 
      type="text"
      inputMode={isString ? "text" : "decimal"}
      placeholder={placeholder}
      value={localValue}
      onChange={handleChange}
      onBlur={handleBlur}
      className="w-full bg-white border rounded-[12px] px-3 py-2 text-[14px] focus:outline-none transition-all"
      style={{ borderColor: '#E6E2F0', color: '#4E4B66' }}
    />
  );
};

export const ParameterTable: React.FC<Props> = ({ params, onParameterChange }) => {
  const rows: { label: string; key: keyof CellParameters; unit: string; isString?: boolean }[] = [
    { label: 'Manufacturer', key: 'manufacturer', unit: '', isString: true },
    { label: 'Cell Model', key: 'cell_model', unit: '', isString: true },
    { label: 'Chemistry', key: 'chemistry', unit: '', isString: true },
    { label: 'Nominal Voltage', key: 'nominal_voltage', unit: 'V' },
    { label: 'Maximum Voltage', key: 'maximum_voltage', unit: 'V' },
    { label: 'Cutoff Voltage', key: 'minimum_voltage', unit: 'V' },
    { label: 'Nominal Capacity', key: 'nominal_capacity', unit: 'mAh' },
    { label: 'Energy', key: 'energy_wh', unit: 'Wh' },
    { label: 'Pre-charge Current', key: 'pre_charge_current', unit: 'A' },
    { label: 'Standard Charge Current', key: 'standard_charge_current', unit: 'A' },
    { label: 'Maximum Continuous Discharge Current', key: 'maximum_continuous_discharge_current', unit: 'A' },
    { label: 'Internal Resistance', key: 'internal_resistance', unit: 'mΩ' },
    { label: 'Cell Diameter', key: 'diameter', unit: 'mm' },
    { label: 'Cell Height / Length', key: 'height', unit: 'mm' },
    { label: 'Weight', key: 'weight', unit: 'g' },
    { label: 'Charge Temp Max', key: 'charge_temperature_max', unit: '°C' },
    { label: 'Charge Temp Min', key: 'charge_temperature_min', unit: '°C' },
    { label: 'Discharge Temp Max', key: 'discharge_temperature_max', unit: '°C' },
    { label: 'Discharge Temp Min', key: 'discharge_temperature_min', unit: '°C' },
  ];

  return (
    <div className="glass-card flex flex-col">
      <h2 className="section-title mb-4 border-b pb-2 shrink-0" style={{ borderColor: '#E6E2F0' }}>
        Extracted Cell Parameters
      </h2>
      <div className="pr-2">
        <table className="w-full text-left border-collapse relative">
          <thead style={{ backgroundColor: '#FDFDFF' }}>
            <tr className="card-label">
              <th className="py-2 px-4 border-b font-semibold" style={{ borderColor: '#E6E2F0' }}>Parameter</th>
              <th className="py-2 px-4 border-b font-semibold" style={{ borderColor: '#E6E2F0' }}>Value</th>
              <th className="py-2 px-4 border-b font-semibold" style={{ borderColor: '#E6E2F0' }}>Unit</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              return (
                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3 px-4 border-b secondary-text font-semibold" style={{ borderColor: '#F3F4F6' }}>
                    {row.label}
                  </td>
                  <td className="py-3 px-4 border-b" style={{ borderColor: '#F3F4F6' }}>
                    <div className="flex items-center space-x-2">
                      <EditableCell 
                        value={row.key === 'internal_resistance' ? (params.internal_resistance ?? params.ac_internal_resistance ?? params.dc_internal_resistance) : params[row.key]} 
                        onBlur={(val) => onParameterChange(row.key, val)} 
                        isString={row.isString} 
                      />
                      {row.key === 'standard_charge_current' && params.standard_charge_current_string && (
                        <span className="text-sm font-semibold whitespace-nowrap" style={{ color: '#5E84B7' }}>
                          {params.standard_charge_current_string}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 border-b normal-value" style={{ borderColor: '#F3F4F6', color: '#9B98B5' }}>
                    {row.unit}
                  </td>
                </tr>
              );
            })}
            {/* Charge Temperature Range */}
            <tr className="hover:bg-gray-50 transition-colors">
              <td className="py-3 px-4 border-b secondary-text font-semibold" style={{ borderColor: '#F3F4F6' }}>Charge Temperature Range</td>
              <td className="py-3 px-4 border-b" style={{ borderColor: '#F3F4F6' }}>
                <div className="flex space-x-2 items-center">
                  <div className="w-1/2">
                    <EditableCell 
                      value={params.charge_temperature_min} 
                      onBlur={(val) => onParameterChange('charge_temperature_min', val)} 
                      placeholder="Min"
                    />
                  </div>
                  <span className="secondary-text">to</span>
                  <div className="w-1/2">
                    <EditableCell 
                      value={params.charge_temperature_max} 
                      onBlur={(val) => onParameterChange('charge_temperature_max', val)} 
                      placeholder="Max"
                    />
                  </div>
                </div>
              </td>
              <td className="py-3 px-4 border-b normal-value" style={{ borderColor: '#F3F4F6', color: '#9B98B5' }}>°C</td>
            </tr>
            {/* Discharge Temperature Range */}
            <tr className="hover:bg-gray-50 transition-colors">
              <td className="py-3 px-4 border-b secondary-text font-semibold" style={{ borderColor: '#F3F4F6' }}>Discharge Temperature Range</td>
              <td className="py-3 px-4 border-b" style={{ borderColor: '#F3F4F6' }}>
                <div className="flex space-x-2 items-center">
                  <div className="w-1/2">
                    <EditableCell 
                      value={params.discharge_temperature_min} 
                      onBlur={(val) => onParameterChange('discharge_temperature_min', val)} 
                      placeholder="Min"
                    />
                  </div>
                  <span className="secondary-text">to</span>
                  <div className="w-1/2">
                    <EditableCell 
                      value={params.discharge_temperature_max} 
                      onBlur={(val) => onParameterChange('discharge_temperature_max', val)} 
                      placeholder="Max"
                    />
                  </div>
                </div>
              </td>
              <td className="py-3 px-4 border-b normal-value" style={{ borderColor: '#F3F4F6', color: '#9B98B5' }}>°C</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

