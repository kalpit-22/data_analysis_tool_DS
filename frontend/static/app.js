// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-btn');
const fileInfo = document.getElementById('file-info');
const fileNameSpan = document.getElementById('file-name');
const removeFileBtn = document.getElementById('remove-file-btn');
const queryInput = document.getElementById('query-input');
const analyzeBtn = document.getElementById('analyze-btn');
const uploadSection = document.getElementById('upload-section');
const executionSection = document.getElementById('execution-section');
const feedContainer = document.getElementById('feed-container');
const resultsContainer = document.getElementById('results-container');
const mainSpinner = document.getElementById('main-spinner');
const navStatusText = document.getElementById('nav-status-text');

let currentFile = null;
let sessionToken = null;

// ── File Upload Logic ──
browseBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFile(e.target.files[0]);
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

removeFileBtn.addEventListener('click', () => {
    currentFile = null;
    fileInput.value = '';
    fileInfo.classList.add('hidden');
    browseBtn.classList.remove('hidden');
    dropZone.querySelector('p').classList.remove('hidden');
    dropZone.querySelector('.or').classList.remove('hidden');
    dropZone.querySelector('.icon-large').classList.remove('hidden');
    validateForm();
});

queryInput.addEventListener('input', validateForm);

function handleFile(file) {
    if (!file.name.endsWith('.csv')) {
        alert("Only CSV files are supported.");
        return;
    }
    currentFile = file;
    fileNameSpan.textContent = file.name;
    
    fileInfo.classList.remove('hidden');
    browseBtn.classList.add('hidden');
    dropZone.querySelector('p').classList.add('hidden');
    dropZone.querySelector('.or').classList.add('hidden');
    dropZone.querySelector('.icon-large').classList.add('hidden');
    
    validateForm();
}

function validateForm() {
    analyzeBtn.disabled = !(currentFile && queryInput.value.trim().length > 0);
}

// ── API Interaction ──
analyzeBtn.addEventListener('click', async () => {
    if (!currentFile || !queryInput.value.trim()) return;

    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
    navStatusText.textContent = "Uploading...";
    
    try {
        // 1. Upload File
        const formData = new FormData();
        formData.append('file', currentFile);
        
        const res = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error("Upload failed");
        
        const data = await res.json();
        sessionToken = data.token;
        
        // 2. Start SSE Stream
        startAnalysisStream(queryInput.value.trim());

    } catch (err) {
        alert("Error: " + err.message);
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Launch Analysis';
        navStatusText.textContent = "Ready";
    }
});

function startAnalysisStream(query) {
    // Switch UI
    uploadSection.classList.add('hidden');
    executionSection.classList.remove('hidden');
    mainSpinner.classList.remove('hidden');
    resultsContainer.innerHTML = '';
    resultsContainer.classList.remove('empty-state');
    feedContainer.innerHTML = '';
    navStatusText.textContent = "Analyzing...";

    const es = new EventSource(`/analyze?token=${sessionToken}&request=${encodeURIComponent(query)}`);

    let currentStepEl = null;

    es.onmessage = (e) => {
        const data = JSON.parse(e.data);
        
        if (data.type === 'schema') {
            appendLog('System', 'Dataset profiled successfully. Generating plan...');
        }
        else if (data.type === 'plan') {
            appendLog('Planner', `Generated plan with ${data.steps.length} steps.`);
        }
        else if (data.type === 'step_start') {
            currentStepEl = createStepCard(data);
            feedContainer.appendChild(currentStepEl);
            scrollToBottom(feedContainer);
        }
        else if (data.type === 'step_attempt') {
            if (currentStepEl) {
                const badge = currentStepEl.querySelector('.step-badge');
                badge.className = 'step-badge running';
                badge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Attempt ${data.attempt}/${data.max}`;
            }
        }
        else if (data.type === 'step_result') {
            if (currentStepEl) {
                const badge = currentStepEl.querySelector('.step-badge');
                if (data.approved) {
                    badge.className = 'step-badge success';
                    badge.innerHTML = '<i class="fa-solid fa-check"></i> Approved';
                    currentStepEl.classList.add('success');
                } else {
                    badge.className = 'step-badge error';
                    badge.innerHTML = '<i class="fa-solid fa-xmark"></i> Rejected';
                    
                    const feedback = document.createElement('div');
                    feedback.className = 'step-feedback';
                    feedback.innerHTML = `<strong>Feedback:</strong> ${data.suggestion || data.reason}`;
                    currentStepEl.appendChild(feedback);
                }
                scrollToBottom(feedContainer);
            }
        }
        else if (data.type === 'artifact') {
            renderArtifact(data);
        }
        else if (data.type === 'done') {
            mainSpinner.classList.add('hidden');
            es.close();
            appendLog('System', 'Analysis complete.');
            navStatusText.textContent = "Complete";
        }
        else if (data.type === 'error') {
            mainSpinner.classList.add('hidden');
            es.close();
            appendLog('Error', data.message, true);
            navStatusText.textContent = "Error";
        }
    };

    es.onerror = () => {
        es.close();
        mainSpinner.classList.add('hidden');
        appendLog('Error', 'Lost connection to server.', true);
        navStatusText.textContent = "Error";
    };
}

// ── UI Helpers ──
function createStepCard(data) {
    const card = document.createElement('div');
    card.className = 'step-card active';
    card.innerHTML = `
        <div class="step-header">
            <span class="step-title">Step ${data.step}/${data.total}: ${data.name}</span>
            <span class="step-badge running"><i class="fa-solid fa-spinner fa-spin"></i> Starting</span>
        </div>
        <div class="step-desc">${data.description}</div>
    `;
    return card;
}

function appendLog(source, msg, isError=false) {
    const div = document.createElement('div');
    div.style.fontSize = '0.85rem';
    div.style.padding = '0.5rem';
    div.style.color = isError ? 'var(--error)' : 'var(--text-secondary)';
    div.innerHTML = `<strong>[${source}]</strong> ${msg}`;
    feedContainer.appendChild(div);
    scrollToBottom(feedContainer);
}

function renderArtifact(data) {
    const card = document.createElement('div');
    card.className = 'artifact-card';
    
    let content = '';
    if (data.mime.startsWith('image/')) {
        content = `<img src="data:${data.mime};base64,${data.data}" alt="${data.filename}">`;
    } else if (data.mime === 'text/csv' || data.filename.endsWith('.csv')) {
        // Base64 decode CSV
        const csvStr = atob(data.data);
        const allRows = csvStr.split('\n');
        const rows = allRows.slice(0, 1000); // preview up to 1000 rows
        
        let table = '<div style="max-height: 400px; overflow-y: auto; width: 100%;">';
        table += '<table>';
        rows.forEach((row, i) => {
            if (!row.trim()) return;
            table += '<tr>';
            row.split(',').forEach(cell => {
                table += i === 0 ? `<th>${cell}</th>` : `<td>${cell}</td>`;
            });
            table += '</tr>';
        });
        table += '</table></div>';
        
        if (allRows.length > 1000) {
            table += `<p style="font-size:0.8rem; margin-top:0.5rem; color:var(--text-secondary);">Showing preview (first 1000 rows of ${allRows.length})</p>`;
        }
        content = table;
    } else {
        content = `<p>File generated: ${data.filename}</p>`;
    }

    card.innerHTML = `
        <div class="artifact-header">
            <i class="fa-solid fa-file"></i> ${data.filename}
        </div>
        <div class="artifact-body">
            ${content}
        </div>
    `;
    
    resultsContainer.appendChild(card);
    scrollToBottom(resultsContainer);
}

function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}
