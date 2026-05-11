/* =====================================================================
   MediScribe Rural — Frontend JavaScript
   ===================================================================== */

const API = '';  // same-origin; change to http://localhost:8000 for dev

// Demo encounter note
const DEMO_NOTE = `38-year-old male farmer presenting to rural clinic with 4-day history of:
- Productive cough with yellow-green sputum
- Fever (patient reports feeling hot, measured 38.7°C at home)
- Right-sided chest pain worsening on deep inspiration
- Mild shortness of breath on exertion

Vitals: BP 124/82 mmHg, HR 98 bpm, RR 24/min, Temp 38.8°C, SpO2 92% on room air, Weight 72kg

Past medical history: Hypertension (on amlodipine 5mg OD - last refill 2 months ago)
Allergies: Penicillin (rash)
Social: Non-smoker, drinks alcohol occasionally, works in agricultural field

Physical Exam:
- General: uncomfortable, diaphoretic
- Chest: dullness to percussion right lower lobe, bronchial breath sounds right base, crackles
- No cyanosis, no JVP elevation, no peripheral edema

Recent travel: visited a neighboring village 2 weeks ago.`;

// ─── Health check ───────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();

    const modelBadge = document.getElementById('model-badge');
    modelBadge.textContent = data.model;
    modelBadge.className = 'badge ' + (data.ollama_ok ? 'badge-green' : 'badge-red');

    const kbBadge = document.getElementById('kb-badge');
    kbBadge.textContent = `${data.guideline_chunks} chunks`;

    document.getElementById('offline-badge').classList.toggle('hidden', navigator.onLine);
  } catch {
    const modelBadge = document.getElementById('model-badge');
    modelBadge.textContent = 'Server offline';
    modelBadge.className = 'badge badge-red';
  }
}

// ─── Main processing ────────────────────────────────────────────────────────

async function processNote() {
  const note = document.getElementById('note-input').value.trim();
  if (!note) {
    alert('Please enter an encounter note.');
    return;
  }

  const language = document.getElementById('lang-select').value;
  const topK = parseInt(document.getElementById('topk-select').value, 10);

  // Show loading
  setOutputState('loading');

  try {
    const res = await fetch(`${API}/encounter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note, language, top_k: topK }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    renderResult(data);
    checkHealth(); // refresh KB count
  } catch (err) {
    setOutputState('error', err.message);
  }
}

// ─── Rendering ──────────────────────────────────────────────────────────────

function renderResult(data) {
  // Alerts
  const alertsContainer = document.getElementById('alerts-container');
  alertsContainer.innerHTML = '';
  if (data.alerts && data.alerts.length > 0) {
    data.alerts.forEach(alert => {
      const div = document.createElement('div');
      div.className = `alert alert-${alert.severity}`;
      div.innerHTML = `
        <div class="alert-title">⚠ ${alert.severity.toUpperCase()}: ${escapeHtml(alert.alert_message)}</div>
        <div class="alert-body">Recommended action: ${escapeHtml(alert.recommended_action)}</div>
      `;
      alertsContainer.appendChild(div);
    });
  }

  // Entities
  const entitiesContainer = document.getElementById('entities-container');
  const entitiesContent = document.getElementById('entities-content');
  const entities = data.extracted_entities || {};

  if (Object.keys(entities).length > 0) {
    entitiesContent.innerHTML = '';

    if (entities.diagnoses && entities.diagnoses.length > 0) {
      entitiesContent.innerHTML += `<div class="entity-section">
        <h4>Diagnoses & ICD-10 Codes</h4>
        ${entities.diagnoses.map(d =>
          `<span class="tag"><span class="tag-icd">${escapeHtml(d.icd10_code)}</span> ${escapeHtml(d.name)} <em>(${d.confidence})</em></span>`
        ).join('')}
      </div>`;
    }

    if (entities.medications && entities.medications.length > 0) {
      entitiesContent.innerHTML += `<div class="entity-section">
        <h4>Medications</h4>
        ${entities.medications.map(m =>
          `<span class="tag tag-med">${escapeHtml(m.name)}${m.dose ? ' ' + escapeHtml(m.dose) : ''}${m.frequency ? ' ' + escapeHtml(m.frequency) : ''}</span>`
        ).join('')}
      </div>`;
    }

    if (entities.vitals && Object.keys(entities.vitals).length > 0) {
      const vEntries = Object.entries(entities.vitals)
        .filter(([, v]) => v)
        .map(([k, v]) => `<span class="tag tag-vital">${k.toUpperCase()}: ${escapeHtml(String(v))}</span>`);
      if (vEntries.length > 0) {
        entitiesContent.innerHTML += `<div class="entity-section"><h4>Vitals</h4>${vEntries.join('')}</div>`;
      }
    }

    if (entities.allergies && entities.allergies.length > 0) {
      entitiesContent.innerHTML += `<div class="entity-section">
        <h4>Allergies</h4>
        ${entities.allergies.map(a => `<span class="tag" style="color:#c0392b">⚠ ${escapeHtml(a)}</span>`).join('')}
      </div>`;
    }

    entitiesContainer.classList.remove('hidden');
  } else {
    entitiesContainer.classList.add('hidden');
  }

  // SOAP Note
  const soapContainer = document.getElementById('soap-container');
  const soapContent = document.getElementById('soap-content');
  const guidelineRef = document.getElementById('guideline-ref');

  soapContent.innerHTML = formatSOAP(data.soap_note);
  guidelineRef.textContent = data.guideline_chunks_used > 0
    ? `✓ Grounded with ${data.guideline_chunks_used} guideline chunk(s) from local knowledge base`
    : '⚠ No local guidelines found — consider uploading relevant clinical guidelines';

  soapContainer.classList.remove('hidden');
  document.getElementById('empty-state').classList.add('hidden');
  document.getElementById('loading').classList.add('hidden');
}

function formatSOAP(text) {
  // Bold the SOAP section headers
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

function setOutputState(state, message = '') {
  document.getElementById('loading').classList.toggle('hidden', state !== 'loading');
  document.getElementById('empty-state').classList.toggle('hidden', state !== 'empty');
  document.getElementById('soap-container').classList.add('hidden');
  document.getElementById('entities-container').classList.add('hidden');
  document.getElementById('alerts-container').innerHTML = '';

  if (state === 'error') {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
    document.getElementById('empty-state').innerHTML = `
      <p style="color:#c0392b">⚠ Error: ${escapeHtml(message)}</p>
      <p style="color:#5d6d7e;font-size:.85rem">Check that Ollama is running and the model is loaded.</p>
    `;
  }
}

// ─── Guideline upload ────────────────────────────────────────────────────────

async function uploadGuideline() {
  const fileInput = document.getElementById('guideline-file');
  const statusDiv = document.getElementById('upload-status');

  if (!fileInput.files.length) {
    statusDiv.textContent = 'Please select a file first.';
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  statusDiv.textContent = 'Uploading and ingesting…';

  try {
    const res = await fetch(`${API}/ingest`, { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      statusDiv.innerHTML = `<span style="color:#1a7f5a">✓ Ingested ${data.chunks_added} chunks from "${escapeHtml(data.filename)}". Total: ${data.total_chunks} chunks.</span>`;
      checkHealth();
    } else {
      statusDiv.innerHTML = `<span style="color:#c0392b">Error: ${escapeHtml(data.detail)}</span>`;
    }
  } catch (err) {
    statusDiv.innerHTML = `<span style="color:#c0392b">Upload failed: ${escapeHtml(err.message)}</span>`;
  }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function loadDemo() {
  document.getElementById('note-input').value = DEMO_NOTE;
}

function clearAll() {
  document.getElementById('note-input').value = '';
  setOutputState('empty');
  document.getElementById('empty-state').innerHTML = `
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <rect width="64" height="64" rx="16" fill="#f0faf5"/>
      <path d="M32 14v36M14 32h36" stroke="#1a7f5a" stroke-width="4" stroke-linecap="round" opacity="0.4"/>
    </svg>
    <p>Enter an encounter note and click <strong>Generate SOAP Note</strong></p>
  `;
}

function copySOAP() {
  const text = document.getElementById('soap-content').innerText;
  navigator.clipboard.writeText(text).then(() => {
    alert('SOAP note copied to clipboard!');
  });
}

function printSOAP() {
  const content = document.getElementById('soap-content').innerText;
  const win = window.open('', '_blank');
  win.document.write(`<pre style="font-family:sans-serif;padding:2rem">${escapeHtml(content)}</pre>`);
  win.print();
  win.close();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Init ────────────────────────────────────────────────────────────────────

checkHealth();
setInterval(checkHealth, 30000);  // refresh status every 30s

window.addEventListener('online',  () => document.getElementById('offline-badge').classList.add('hidden'));
window.addEventListener('offline', () => document.getElementById('offline-badge').classList.remove('hidden'));
