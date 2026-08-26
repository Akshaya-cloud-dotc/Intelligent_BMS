import React, { useCallback, useState } from 'react';
import { UploadCloud, FileType } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props {
  onUpload: (file: File) => void;
  isUploading: boolean;
}

export const UploadCard: React.FC<Props> = ({ onUpload, isUploading }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf') {
        setFileName(file.name);
        onUpload(file);
      } else {
        alert('Please upload a PDF file.');
      }
    }
  }, [onUpload]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type === 'application/pdf') {
        setFileName(file.name);
        onUpload(file);
      }
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card flex flex-col items-center h-full justify-center"
    >
      <h2 className="section-title mb-4 self-start">Cell Datasheet</h2>
      <div
        className={`w-full border border-dashed rounded-[12px] p-8 flex flex-col items-center justify-center transition-colors ${
          isDragOver ? 'bg-[#E4E9F8]' : ''
        }`}
        style={{ borderColor: '#E6E2F0' }}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
      >
        <UploadCloud className="w-10 h-10 mb-3" style={{ color: '#5E84B7' }} />
        <p className="secondary-text mb-4 text-center">Drag and drop your PDF datasheet here</p>
        <label 
          className="px-6 py-2 rounded-[8px] font-semibold cursor-pointer transition-colors shadow-sm"
          style={{ backgroundColor: '#5E84B7', color: '#FFFFFF', fontSize: '14px' }}
        >
          Browse Files
          <input type="file" accept=".pdf" className="hidden" onChange={handleFileInput} disabled={isUploading} />
        </label>
      </div>
      {fileName && (
        <div className="mt-4 flex items-center space-x-2 w-full justify-center" style={{ color: '#5B9B6B' }}>
          <FileType className="w-5 h-5" />
          <span className="secondary-text" style={{ color: '#5B9B6B' }}>{fileName} {isUploading ? '(Processing...)' : '(Uploaded)'}</span>
        </div>
      )}
    </motion.div>
  );
};
