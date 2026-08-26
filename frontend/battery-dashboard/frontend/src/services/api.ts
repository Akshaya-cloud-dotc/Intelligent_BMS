import { CellParameters, CalculationResponse } from '../types';

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
  ? 'http://localhost:8000' 
  : 'https://floppy-sites-ring.loca.lt';

export const uploadPdf = async (file: File): Promise<CellParameters> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Failed to upload and parse PDF');
  }

  return response.json();
};

export const calculatePack = async (
  cellParams: CellParameters,
  s: number,
  p: number
): Promise<CalculationResponse> => {
  const response = await fetch(`${API_BASE_URL}/calculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      cell_parameters: cellParams,
      series_cells: s,
      parallel_cells: p,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to calculate pack parameters');
  }

  return response.json();
};

export const saveActiveProfile = async (
  cellParams: CellParameters,
  faultThresholds: any
): Promise<{ status: string }> => {
  const response = await fetch(`${API_BASE_URL}/save_active_profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cell_parameters: cellParams, thresholds: faultThresholds }),
  });
  if (!response.ok) throw new Error('Failed to save active profile');
  return response.json();
};

export const trainModel = async (file: File, uploadMode: 'replace' | 'append' = 'replace'): Promise<{ status: string, message: string, stats?: any }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('upload_mode', uploadMode);
  const response = await fetch(`${API_BASE_URL}/train_model`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const errData = await response.json().catch(() => null);
    throw new Error(errData?.detail || 'Failed to train model');
  }
  return response.json();
};
