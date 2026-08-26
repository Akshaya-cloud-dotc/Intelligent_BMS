from pydantic import BaseModel
from typing import Optional, List

class CellParameters(BaseModel):
    manufacturer: Optional[str] = None
    cell_model: Optional[str] = None
    chemistry: Optional[str] = None
    nominal_voltage: Optional[float] = None
    maximum_voltage: Optional[float] = None
    minimum_voltage: Optional[float] = None
    nominal_capacity: Optional[float] = None
    standard_charge_current: Optional[float] = None
    pre_charge_current: Optional[float] = None
    standard_charge_current_string: Optional[str] = None
    maximum_charge_current: Optional[float] = None
    maximum_continuous_discharge_current: Optional[float] = None
    operating_temperature_min: Optional[float] = None
    operating_temperature_max: Optional[float] = None
    weight: Optional[float] = None
    pulse_discharge_current: Optional[float] = None
    ac_internal_resistance: Optional[float] = None
    dc_internal_resistance: Optional[float] = None
    internal_resistance: Optional[float] = None
    cycle_life: Optional[float] = None
    charge_temperature_min: Optional[float] = None
    charge_temperature_max: Optional[float] = None
    discharge_temperature_min: Optional[float] = None
    discharge_temperature_max: Optional[float] = None
    storage_temperature_min: Optional[float] = None
    storage_temperature_max: Optional[float] = None
    diameter: Optional[float] = None
    height: Optional[float] = None
    gravimetric_energy_density: Optional[float] = None
    volumetric_energy_density: Optional[float] = None
    shape: Optional[str] = None
    can_material: Optional[str] = None
    minimum_capacity: Optional[float] = None
    energy_wh: Optional[float] = None

class PackParameters(BaseModel):
    pack_nominal_voltage: float
    pack_maximum_voltage: float
    pack_minimum_voltage: float
    pack_capacity: float
    pack_energy_wh: float
    pack_standard_charge_current: float
    pack_maximum_discharge_current: float

class FaultThresholds(BaseModel):
    overvoltage_warning: float
    overvoltage_critical: float
    overcurrent_warning: float
    overcurrent_critical: float
    overtemperature_normal_min: Optional[float] = None
    overtemperature_normal_max: Optional[float] = None
    overtemperature_warning_min: Optional[float] = None
    overtemperature_warning_max: Optional[float] = None
    overtemperature_critical: Optional[float] = None

class CalculateRequest(BaseModel):
    cell_parameters: CellParameters
    series_cells: int
    parallel_cells: int

class ReconfigurationItem(BaseModel):
    parameter: str
    current_setting: str
    new_setting: str

class AdaptationMetrics(BaseModel):
    base_chemistry: str
    detected_chemistry: str
    compatibility_score: float
    recommendation_text: str
    expected_accuracy: float
    reconfiguration_items: List[ReconfigurationItem]

class CalculationResponse(BaseModel):
    cell: CellParameters
    pack: PackParameters
    thresholds: FaultThresholds
    adaptation: AdaptationMetrics

CalculationResponse.model_rebuild()
