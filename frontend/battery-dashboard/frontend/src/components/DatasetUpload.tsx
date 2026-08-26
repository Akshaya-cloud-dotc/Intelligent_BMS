import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle } from 'lucide-react';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

export interface DatasetInfo {
  filename: string;
  rowCount: number;
  colCount: number;
  fileType: string;
  fileSize: number; // in bytes
  columns: string[];
  rawFile: File;
}

interface Props {
  onDatasetParsed: (info: DatasetInfo) => void;
}

export const DatasetUpload: React.FC<Props> = ({ onDatasetParsed }) => {
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setIsUploading(true);
    setUploadStatus('idle');

    try {
      const extension = file.name.split('.').pop()?.toLowerCase();
      
      if (extension === 'csv') {
        Papa.parse(file, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as any[];
            const columns = results.meta.fields || [];
            onDatasetParsed({
              filename: file.name,
              rowCount: data.length,
              colCount: columns.length,
              fileType: 'CSV',
              fileSize: file.size,
              columns: columns,
              rawFile: file
            });
            setIsUploading(false);
            setUploadStatus('success');
          },
          error: () => {
            setIsUploading(false);
            setUploadStatus('error');
          }
        });
      } else if (['xlsx', 'xls', 'ods'].includes(extension || '')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = new Uint8Array(e.target?.result as ArrayBuffer);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[firstSheetName];
            const json = XLSX.utils.sheet_to_json(worksheet);
            
            let columns: string[] = [];
            if (json.length > 0) {
              columns = Object.keys(json[0] as object);
            }

            onDatasetParsed({
              filename: file.name,
              rowCount: json.length,
              colCount: columns.length,
              fileType: extension?.toUpperCase() || 'XLSX',
              fileSize: file.size,
              columns: columns,
              rawFile: file
            });
            setIsUploading(false);
            setUploadStatus('success');
          } catch (err) {
            setIsUploading(false);
            setUploadStatus('error');
          }
        };
        reader.readAsArrayBuffer(file);
      } else {
        alert('Unsupported file type. Please upload a CSV, XLSX, XLS, or ODS file.');
        setIsUploading(false);
        setUploadStatus('error');
      }
    } catch (error) {
      console.error(error);
      setIsUploading(false);
      setUploadStatus('error');
    }
  };

  return (
    <div className="glass-card">
      <div className="flex items-center space-x-3 mb-6">
        <div className="p-2 bg-pastel-bg rounded-lg" style={{ backgroundColor: '#F8F7FF' }}>
          <FileText className="w-5 h-5" style={{ color: '#CDB4DB' }} />
        </div>
        <div>
          <h2 className="section-title text-[18px] m-0" style={{ color: '#4E4B66' }}>DATASET UPLOAD</h2>
          <p className="secondary-text text-[12px] m-0" style={{ color: '#9B98B5' }}>Supported files: CSV, XLSX, XLS, ODS</p>
        </div>
      </div>

      <div 
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-[16px] p-6 flex flex-col items-center justify-center cursor-pointer transition-all ${
          isUploading ? 'opacity-50' : 'hover:bg-gray-50'
        }`}
        style={{ borderColor: '#E6E2F0' }}
      >
        {isUploading ? (
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mb-2"></div>
        ) : uploadStatus === 'success' ? (
          <CheckCircle className="w-8 h-8 text-green-500 mb-2" style={{ color: '#5B9B6B' }} />
        ) : (
          <Upload className="w-8 h-8 text-gray-400 mb-2" style={{ color: '#CDB4DB' }} />
        )}
        
        <p className="text-[14px] font-medium" style={{ color: '#4E4B66' }}>
          {isUploading ? 'Parsing Dataset...' : uploadStatus === 'success' ? 'Dataset Uploaded Successfully' : 'Click or drag file to upload'}
        </p>
        
        {selectedFile && (
          <p className="text-[12px] mt-2 font-medium truncate max-w-[200px]" style={{ color: '#9B98B5' }}>
            {selectedFile.name}
          </p>
        )}
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel, application/vnd.oasis.opendocument.spreadsheet"
      />
    </div>
  );
};
