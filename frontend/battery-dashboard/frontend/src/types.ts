export interface CellParameters {
  manufacturer: string | null;
  cell_model: string | null;
  chemistry: string | null;
  nominal_voltage: number | null;
  maximum_voltage: number | null;
  minimum_voltage: number | null;
  nominal_capacity: number | null;
  standard_charge_current: number | null;
  pre_charge_current?: number | null;
  standard_charge_current_string?: string | null;
  maximum_charge_current: number | null;
  maximum_continuous_discharge_current: number | null;
  operating_temperature_min: number | null;
  operating_temperature_max: number | null;
  weight: number | null;
  pulse_discharge_current?: number | null;
  ac_internal_resistance?: number | null;
  dc_internal_resistance?: number | null;
  internal_resistance?: number | null;
  cycle_life?: number | null;
  charge_temperature_min?: number | null;
  charge_temperature_max?: number | null;
  discharge_temperature_min?: number | null;
  discharge_temperature_max?: number | null;
  storage_temperature_min?: number | null;
  storage_temperature_max?: number | null;
  diameter?: number | null;
  height?: number | null;
  gravimetric_energy_density?: number | null;
  volumetric_energy_density?: number | null;
  shape?: string | null;
  can_material?: string | null;
  minimum_capacity?: number | null;
  energy_wh?: number | null;
}

export interface PackParameters {
  pack_nominal_voltage: number;
  pack_maximum_voltage: number;
  pack_minimum_voltage: number;
  pack_capacity: number;
  pack_energy_wh: number;
  pack_standard_charge_current: number;
  pack_maximum_discharge_current: number;
}

export interface FaultThresholds {
  overvoltage_warning: number;
  overvoltage_critical: number;
  overcurrent_warning: number;
  overcurrent_critical: number;
  overtemperature_normal_min: number;
  overtemperature_normal_max: number;
  overtemperature_warning_min: number;
  overtemperature_warning_max: number;
  overtemperature_critical: number;
}

export interface ReconfigurationItem {
  parameter: string;
  current_setting: string;
  new_setting: string;
}

export interface AdaptationMetrics {
  base_chemistry: string;
  detected_chemistry: string;
  compatibility_score: number;
  recommendation_text: string;
  expected_accuracy: number;
  reconfiguration_items: ReconfigurationItem[];
}

export interface CalculationResponse {
  cell: CellParameters;
  pack: PackParameters;
  thresholds: FaultThresholds;
  adaptation: AdaptationMetrics;
}

export interface CalculateRequest {
  cell_parameters: CellParameters;
  series_cells: number;
  parallel_cells: number;
}
