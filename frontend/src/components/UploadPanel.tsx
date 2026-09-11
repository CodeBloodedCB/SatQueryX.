import { useRef, useState } from 'react';
import { apiClient } from '../api/client';

interface UploadPanelProps {
  image1Id: string | null;
  image2Id: string | null;
  onUpload1: (imageId: string) => void;
  onUpload2: (imageId: string) => void;
}

export const UploadPanel = ({ image1Id, image2Id, onUpload1, onUpload2 }: UploadPanelProps) => {
  const [uploading1, setUploading1] = useState(false);
  const [uploading2, setUploading2] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef1 = useRef<HTMLInputElement>(null);
  const fileInputRef2 = useRef<HTMLInputElement>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>, isImage1: boolean) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);

    if (isImage1) setUploading1(true);
    else setUploading2(true);

    try {
      const response = await apiClient.uploadImage(file);
      if (!response?.image_id) throw new Error('Backend did not return an image ID.');
      if (isImage1) onUpload1(response.image_id);
      else onUpload2(response.image_id);
    } catch (err: any) {
      setError(err?.message || 'Upload failed');
    } finally {
      if (isImage1) setUploading1(false);
      else setUploading2(false);
      if (isImage1 && fileInputRef1.current) fileInputRef1.current.value = '';
      if (!isImage1 && fileInputRef2.current) fileInputRef2.current.value = '';
    }
  };

  return (
    <div className="panel upload-panel">
      <div className="panel-header">
        <h2 className="panel-title">Input</h2>
        <span className="badge badge--success">LIVE INPUT</span>
      </div>

      <div className="preset-section">
        <div className="preset-label">Real imagery only</div>
        <p className="text-secondary" style={{ fontSize: '11px', margin: '0 0 8px' }}>
          Upload PNG, JPEG or GeoTIFF scenes. No fabricated demo IDs are loaded.
        </p>
      </div>

      <div className="upload-zone">
        <div className="upload-zone__header">
          <h3 className="upload-zone__title">Baseline / Primary</h3>
          {image1Id && <span className="badge badge--accent">ACTIVE</span>}
        </div>
        {image1Id ? (
          <div className="upload-zone__status" title={image1Id}>✓ {image1Id}</div>
        ) : (
          <div className="upload-zone__placeholder">
            {uploading1 ? 'Uploading to FastAPI…' : 'Choose the primary satellite scene'}
          </div>
        )}
        <input
          type="file"
          ref={fileInputRef1}
          onChange={(e) => void handleFileChange(e, true)}
          accept="image/png,image/jpeg,image/tiff,.tif,.tiff"
          className="hidden"
          aria-label="Upload primary image"
        />
        <button className="btn btn--ghost btn--full btn--sm" onClick={() => fileInputRef1.current?.click()} disabled={uploading1} style={{ marginTop: 'var(--space-2)' }}>
          {uploading1 ? 'Uploading…' : image1Id ? 'Replace Primary' : 'Upload Primary'}
        </button>
      </div>

      <div className="upload-zone">
        <div className="upload-zone__header">
          <h3 className="upload-zone__title">Secondary / T1 / SAR</h3>
          {image2Id && <span className="badge badge--accent">ACTIVE</span>}
        </div>
        {image2Id ? (
          <div className="upload-zone__status" title={image2Id}>✓ {image2Id}</div>
        ) : (
          <div className="upload-zone__placeholder">
            {uploading2 ? 'Uploading to FastAPI…' : 'Optional: second date or SAR scene'}
          </div>
        )}
        <input
          type="file"
          ref={fileInputRef2}
          onChange={(e) => void handleFileChange(e, false)}
          accept="image/png,image/jpeg,image/tiff,.tif,.tiff"
          className="hidden"
          aria-label="Upload secondary image"
        />
        <button className="btn btn--ghost btn--full btn--sm" onClick={() => fileInputRef2.current?.click()} disabled={uploading2} style={{ marginTop: 'var(--space-2)' }}>
          {uploading2 ? 'Uploading…' : image2Id ? 'Replace Secondary' : 'Upload Secondary'}
        </button>
      </div>

      {error && (
        <div className="error-state" role="alert" style={{ marginTop: '8px' }}>
          {error}
        </div>
      )}
    </div>
  );
};
