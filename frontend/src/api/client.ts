const configuredApiUrl = ((import.meta as any).env?.VITE_API_URL || '').trim();
const productionApiUrl = 'https://satquery-backend-1809.onrender.com';

// In production the frontend talks directly to the deployed FastAPI service.
// Locally, VITE_API_URL can point at another backend (default: localhost:8000).
export const API_BASE_URL = `${(
  configuredApiUrl || ((import.meta as any).env?.PROD ? productionApiUrl : 'http://localhost:8000')
).replace(/\/+$/, '')}/api`;

async function requestJson(path: string, init?: RequestInit) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(`Cannot reach SatQuery backend at ${API_BASE_URL}. Start FastAPI locally or set VITE_API_URL.`);
  }

  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => '');

  if (!response.ok) {
    const message = typeof data === 'object' && data?.detail
      ? data.detail
      : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export const apiClient = {
  async uploadImage(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return requestJson('/upload', { method: 'POST', body: formData });
  },

  async executeQuery(imageId: string, query: string, imageId2?: string | null) {
    return requestJson('/query', json({ image_id: imageId, query, image_id_2: imageId2 || undefined }));
  },

  async submitQuery(imageId: string, query: string, imageId2?: string | null) {
    return this.executeQuery(imageId, query, imageId2);
  },

  async generateCaption(imageId: string) {
    return requestJson('/caption', json({ image_id: imageId }));
  },

  async compareImages(imageId1: string, imageId2: string, timelineIds?: string[]) {
    return requestJson('/analyze/change', json({ image_id_1: imageId1, image_id_2: imageId2, timeline_image_ids: timelineIds }));
  },

  async analyzeChange(imageId1: string, imageId2: string, timelineIds?: string[]) {
    return this.compareImages(imageId1, imageId2, timelineIds);
  },

  async fuseImages(imageId1: string, imageId2: string) {
    return requestJson('/fuse', json({ image_id_1: imageId1, image_id_2: imageId2 }));
  },

  async getAuditLogs() {
    return requestJson('/audit');
  },

  async sendChatMessage(message: string, history: ChatMessage[] = [], imageId?: string | null) {
    return requestJson('/chat', json({ message, history, image_id: imageId || null }));
  },

  async analyzeRegion(imageId: string, roiGeometry: any, question?: string, task?: string) {
    return requestJson('/analyze/region', json({
      image_id: imageId,
      roi_geometry: roiGeometry,
      question: question || 'Analyze this region',
      task: task || 'vqa',
    }));
  },

  async analyzeEscalate(imageId: string, question: string, sarImageId?: string | null) {
    return requestJson('/analyze/escalate', json({
      image_id: imageId,
      question,
      sar_image_id: sarImageId || null,
      force_high_precision: true,
    }));
  },

  async getTeeShowcases() {
    return requestJson('/tee/showcases');
  },

  async extractTeeImagery(bbox: number[], date: string, locationId?: string) {
    return requestJson('/tee/extract', json({ bbox, date, location_id: locationId, source: 'NASA_GIBS' }));
  },

  async geocodeLocation(query: string) {
    return requestJson(`/tee/geocode?q=${encodeURIComponent(query)}`);
  },

  async searchCatalog(params: { bbox: number[]; startDate: string; endDate: string; sensor?: string; cloudMax?: number; limit?: number }) {
    return requestJson('/tee/search', json({
      bbox: params.bbox,
      start_date: params.startDate,
      end_date: params.endDate,
      sensor: params.sensor || 'ALL',
      cloud_max: params.cloudMax ?? 30,
      limit: params.limit || 10,
    }));
  },

  async validatePair(imageId1: string, imageId2: string, task?: string) {
    return requestJson('/validate/pair', json({ image_id_1: imageId1, image_id_2: imageId2, task: task || 'change_detection' }));
  },

  async checkHealth(): Promise<{ status: string; service?: string; ai_engine?: string }> {
    try {
      return await requestJson('/health');
    } catch {
      return { status: 'offline' };
    }
  },

  startTabKeepAlive(intervalMinutes = 5) {
    if (typeof window === 'undefined') return;
    const timer = window.setInterval(() => { void this.checkHealth(); }, intervalMinutes * 60 * 1000);
    return () => window.clearInterval(timer);
  },
};
