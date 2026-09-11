import { useEffect, useState } from 'react';
import './App.css';
import { UploadPanel } from './components/UploadPanel';
import { QueryPanel } from './components/QueryPanel';
import { MapViewer } from './components/MapViewer';
import { ResultPanel } from './components/ResultPanel';
import { EvidencePanel } from './components/EvidencePanel';
import { AuditModal } from './components/AuditModal';
import { GodsEyeExplorer } from './components/GodsEyeExplorer';
import { ChatBot } from './components/ChatBot';
import { apiClient } from './api/client';

function App() {
  const [image1Id, setImage1Id] = useState<string | null>(null);
  const [image2Id, setImage2Id] = useState<string | null>(null);
  const [activeRoi, setActiveRoi] = useState<any | null>(null);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [showGlobe, setShowGlobe] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [aiEngine, setAiEngine] = useState('checking');

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const health = await apiClient.checkHealth();
      if (cancelled) return;
      setBackendStatus(health.status === 'ok' ? 'online' : 'offline');
      setAiEngine(health.ai_engine || 'Deterministic CV fallback');
    };
    void check();
    const timer = window.setInterval(check, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const handlePrimaryUpload = (id: string) => {
    setImage1Id(id);
    setActiveRoi(null);
    setQueryResult(null);
  };

  const handleSecondaryUpload = (id: string) => {
    setImage2Id(id || null);
    setQueryResult(null);
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="app-header__brand">
          <h1 className="app-header__logo">
            Sat<span className="app-header__logo-accent">Query</span> AI
          </h1>
          <span className="app-header__tag">SIH26167 • ISRO</span>
          <span className={`badge ${backendStatus === 'online' ? 'badge--success' : backendStatus === 'offline' ? 'badge--danger' : 'badge--warning'}`}>
            API {backendStatus.toUpperCase()}
          </span>
        </div>
        <div className="app-header__actions flex gap-2">
          <span className="text-secondary" style={{ fontSize: '11px' }} title={aiEngine}>
            AI: {aiEngine}
          </span>
          <button
            className="btn btn--secondary btn--sm"
            onClick={() => setShowGlobe(true)}
            style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)' }}
          >
            🌍 3D Earth Explorer
          </button>
          <button className="btn btn--ghost btn--sm" onClick={() => setShowAudit(true)}>
            Audit Trail
          </button>
        </div>
      </header>

      <aside className="app-layout__sidebar-left">
        <UploadPanel
          image1Id={image1Id}
          image2Id={image2Id}
          onUpload1={handlePrimaryUpload}
          onUpload2={handleSecondaryUpload}
        />
        <QueryPanel
          image1Id={image1Id}
          image2Id={image2Id}
          activeRoi={activeRoi}
          onClearRoi={() => setActiveRoi(null)}
          onQueryResult={setQueryResult}
        />
      </aside>

      <main className="app-layout__main">
        <MapViewer
          image1Id={image1Id}
          image2Id={image2Id}
          queryResult={queryResult}
          activeRoi={activeRoi}
          onRoiChange={setActiveRoi}
        />
      </main>

      <aside className="app-layout__sidebar-right">
        <ResultPanel result={queryResult} />
      </aside>

      <section className="app-layout__bottom">
        <EvidencePanel queryResult={queryResult} />
      </section>

      {showAudit && <AuditModal onClose={() => setShowAudit(false)} />}
      {showGlobe && (
        <GodsEyeExplorer
          isOpen={showGlobe}
          onClose={() => setShowGlobe(false)}
          onSelectImagery={async (id) => {
            setImage1Id(id);
            setImage2Id(null);
            setActiveRoi(null);
            setQueryResult(null);
            try {
              const capRes = await apiClient.generateCaption(id);
              setQueryResult(capRes);
            } catch (err: any) {
              setQueryResult({ error: err.message });
            }
          }}
          onCompareImagery={async (id1, id2) => {
            setImage1Id(id1);
            setImage2Id(id2);
            setActiveRoi(null);
            try {
              const compRes = await apiClient.compareImages(id1, id2);
              setQueryResult(compRes);
            } catch (err: any) {
              setQueryResult({ error: err.message });
            }
          }}
        />
      )}
      <ChatBot activeImageId={image1Id} />
    </div>
  );
}

export default App;
