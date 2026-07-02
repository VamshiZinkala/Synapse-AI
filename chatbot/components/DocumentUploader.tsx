import React, { useState, useRef, SetStateAction, RefObject } from 'react';
import { GoPlus } from "react-icons/go";
interface DocumentUploaderProps {
    disabled: boolean;
    onFilesSelected: (files: File[]) => void;
}

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({ disabled, onFilesSelected }) => {
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    // Triggered when file is dragged over the component bounds
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        if (!disabled) {
            setIsDragging(true);
        }
    };

    // Triggered when file leaves the component bounds
    const handleDragLeave = () => {
        setIsDragging(false);
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (disabled) return;

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            // Convert FileList to Array
            onFilesSelected(Array.from(e.dataTransfer.files));
        }
    };

    // Handle manual file seletion via input
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            onFilesSelected(Array.from(e.target.files));
        }

        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    return (
        <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{
                border: isDragging ? '2px dashed #3b82f6' : 'none',
                backgroundColor: isDragging ? 'rgba(255,255,255,0.1)' : 'transparent',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.6 : 1,
                transition: 'all 0.2s ease',
            }}
            onClick={() => !disabled && fileInputRef.current?.click()}
            className='flex shrink-0 items-center justify-center rounded-full p-2 hover:bg-white/10'
        >
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept='.txt,.md,.pdf,.docx,.csv,.xlsx,image/*'
                style={{ display: 'none' }}
                disabled={disabled}
            />
            <GoPlus size={24} className={`transition-transform duration-200 ${isDragging ? 'rotate-90 scale-110 text-cyan-400' : 'text-white/70 hover:text-white'}`} />
        </div>
    )


}