/**
 * X-HEC Interview Coach - Frontend Application
 * Real-time voice-to-voice with OpenAI Realtime API
 * v2.1 - Clean UI with toggle mic
 */

// ============ State Management ============
const state = {
    // Files
    dossierFile: null,
    dossierText: '',
    questionsList: [],
    
    // Session
    sessionId: null,
    mode: null,
    questionsCount: 0,
    
    // WebSocket & Audio
    websocket: null,
    audioContext: null,
    mediaStream: null,
    audioWorklet: null,
    isConnected: false,
    isRecording: false,
    isSpeaking: false,
    
    // Audio playback
    audioQueue: [],
    isPlaying: false,
    
    // Transcript (only stored, not displayed live)
    transcript: []
};

// ============ Audio Configuration ============
const SAMPLE_RATE = 24000;

// ============ DOM Elements ============
const elements = {
    // Steps
    stepUpload: document.getElementById('stepUpload'),
    stepMode: document.getElementById('stepMode'),
    stepInterview: document.getElementById('stepInterview'),
    stepSummary: document.getElementById('stepSummary'),
    
    // Upload
    dossierInput: document.getElementById('dossierInput'),
    dossierStatus: document.getElementById('dossierStatus'),
    dossierZone: document.getElementById('dossierZone'),
    uploadBtn: document.getElementById('uploadBtn'),
    uploadForm: document.getElementById('uploadForm'),
    uploadPreview: document.getElementById('uploadPreview'),
    questionsCount: document.getElementById('questionsCount'),
    
    // Mode
    modeCards: document.querySelectorAll('.mode-card'),
    
    // Interview
    voiceBlob: document.getElementById('voiceBlob'),
    statusText: document.getElementById('statusText'),
    voiceBtn: document.getElementById('voiceBtn'),
    endSessionBtn: document.getElementById('endSessionBtn'),
    
    // Summary
    summaryContent: document.getElementById('summaryContent'),
    downloadTranscript: document.getElementById('downloadTranscript'),
    newSession: document.getElementById('newSession'),
    
    // UI
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage')
};

// ============ Utility Functions ============

function showLoading(text = 'Chargement...') {
    elements.loadingText.textContent = text;
    elements.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
}

function showToast(message, duration = 4000) {
    elements.toastMessage.textContent = message;
    elements.toast.style.display = 'flex';
    setTimeout(() => {
        elements.toast.style.display = 'none';
    }, duration);
}

function showStep(stepElement) {
    [elements.stepUpload, elements.stepMode, elements.stepInterview, elements.stepSummary].forEach(step => {
        if (step) step.style.display = 'none';
    });
    if (stepElement) stepElement.style.display = 'flex';
}

function updateStatus(text) {
    if (elements.statusText) {
        elements.statusText.textContent = text;
    }
}

function setBlobState(state) {
    // States: 'idle', 'listening', 'speaking'
    if (!elements.voiceBlob) return;
    
    elements.voiceBlob.classList.remove('idle', 'listening', 'speaking');
    elements.voiceBlob.classList.add(state);
}

// ============ Audio Handling ============

async function initAudio() {
    try {
        state.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });
        
        state.audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        await state.audioContext.audioWorklet.addModule('/static/audio-processor.js');
        
        console.log('✅ Audio initialized');
        return true;
        
    } catch (error) {
        console.error('❌ Audio init failed:', error);
        showToast('Erreur: Impossible d\'accéder au microphone.');
        return false;
    }
}

function startRecording() {
    if (!state.mediaStream || !state.audioContext || !state.websocket) return;
    
    const source = state.audioContext.createMediaStreamSource(state.mediaStream);
    state.audioWorklet = new AudioWorkletNode(state.audioContext, 'audio-processor');
    
    state.audioWorklet.port.onmessage = (event) => {
        if (state.isRecording && state.websocket?.readyState === WebSocket.OPEN) {
            const float32Data = event.data;
            const int16Data = new Int16Array(float32Data.length);
            
            for (let i = 0; i < float32Data.length; i++) {
                const s = Math.max(-1, Math.min(1, float32Data[i]));
                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            const base64 = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)));
            state.websocket.send(JSON.stringify({ type: 'audio', data: base64 }));
        }
    };
    
    source.connect(state.audioWorklet);
    state.audioWorklet.connect(state.audioContext.destination);
    
    state.isRecording = true;
    updateRecordingUI(true);
}

function stopRecording() {
    if (state.audioWorklet) {
        state.audioWorklet.disconnect();
        state.audioWorklet = null;
    }
    state.isRecording = false;
    updateRecordingUI(false);
    
    if (state.websocket?.readyState === WebSocket.OPEN) {
        state.websocket.send(JSON.stringify({ type: 'commit' }));
    }
}

function updateRecordingUI(recording) {
    if (recording) {
        elements.voiceBtn.classList.add('recording');
        elements.voiceBtn.querySelector('.mic-icon').textContent = '⏹';
        updateStatus('Je t\'écoute...');
        setBlobState('listening');
    } else {
        elements.voiceBtn.classList.remove('recording');
        elements.voiceBtn.querySelector('.mic-icon').textContent = '🎤';
        updateStatus('Appuie pour parler');
        setBlobState('idle');
    }
}

// Toggle recording (click to start, click to stop)
function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
    } else {
        // If AI is speaking, interrupt it
        if (state.isSpeaking) {
            interruptPlayback();
        }
        startRecording();
    }
}

// ============ Audio Playback ============

async function playAudioChunk(base64Audio) {
    if (!state.audioContext) return;
    
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x8000;
    }
    
    const audioBuffer = state.audioContext.createBuffer(1, float32.length, SAMPLE_RATE);
    audioBuffer.copyToChannel(float32, 0);
    
    state.audioQueue.push(audioBuffer);
    
    if (!state.isPlaying) {
        playNextInQueue();
    }
}

function playNextInQueue() {
    if (state.audioQueue.length === 0) {
        state.isPlaying = false;
        state.isSpeaking = false;
        setBlobState('idle');
        updateStatus('Appuie pour parler');
        return;
    }
    
    state.isPlaying = true;
    state.isSpeaking = true;
    setBlobState('speaking');
    updateStatus('Le coach parle...');
    
    const buffer = state.audioQueue.shift();
    const source = state.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioContext.destination);
    source.onended = playNextInQueue;
    source.start();
}

function interruptPlayback() {
    state.audioQueue = [];
    state.isPlaying = false;
    state.isSpeaking = false;
    setBlobState('idle');
    
    if (state.websocket?.readyState === WebSocket.OPEN) {
        state.websocket.send(JSON.stringify({ type: 'interrupt' }));
    }
}

// ============ WebSocket Connection ============

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/interview/${state.sessionId}`;
    
    updateStatus('Connexion...');
    
    state.websocket = new WebSocket(wsUrl);
    
    state.websocket.onopen = () => {
        console.log('✅ WebSocket connected');
        state.isConnected = true;
        updateStatus('Connecté - Appuie pour parler');
        setBlobState('idle');
        showStep(elements.stepInterview);
        hideLoading();
    };
    
    state.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'audio':
                playAudioChunk(data.data);
                break;
                
            case 'transcript':
                // Store transcript but don't display live
                if (data.text && data.text.trim()) {
                    state.transcript.push({
                        role: data.role,
                        text: data.text,
                        timestamp: new Date()
                    });
                }
                break;
                
            case 'status':
                console.log('Status:', data.status);
                break;
                
            case 'error':
                console.error('Server error:', data.message);
                showToast(`Erreur: ${data.message}`);
                break;
        }
    };
    
    state.websocket.onclose = () => {
        console.log('WebSocket closed');
        state.isConnected = false;
        updateStatus('Déconnecté');
    };
    
    state.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        showToast('Erreur de connexion');
    };
}

function disconnectWebSocket() {
    if (state.websocket) {
        state.websocket.send(JSON.stringify({ type: 'end' }));
        state.websocket.close();
        state.websocket = null;
    }
    state.isConnected = false;
}

// ============ API Functions ============

async function uploadDossier() {
    const formData = new FormData();
    formData.append('dossier', state.dossierFile);
    
    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
    }
    
    return response.json();
}

async function prepareSession(mode) {
    const formData = new FormData();
    formData.append('mode', mode);
    formData.append('dossier_text', state.dossierText);
    
    const response = await fetch('/api/session/prepare', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Session preparation failed');
    }
    
    return response.json();
}

// ============ Event Handlers ============

// File Upload
if (elements.dossierInput) {
elements.dossierInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        state.dossierFile = file;
        elements.dossierStatus.textContent = file.name;
        elements.dossierZone.classList.add('has-file');
        elements.uploadBtn.disabled = false;
    } else {
        elements.uploadBtn.disabled = true;
    }
});
}

if (elements.uploadForm) {
elements.uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    showLoading('Analyse de ton dossier...');
    
    try {
        const result = await uploadDossier();
        
        state.dossierText = result._dossier_text;
        state.questionsList = result._questions_list;
            state.questionsCount = result.questions_count;
        
        elements.questionsCount.textContent = result.questions_count;
        elements.uploadPreview.style.display = 'block';
        
        hideLoading();
        
        setTimeout(() => {
            showStep(elements.stepMode);
            }, 800);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
});
}

// Mode Selection
elements.modeCards.forEach(card => {
    card.addEventListener('click', async () => {
        elements.modeCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        
        const mode = card.dataset.mode;
        state.mode = mode;
        
        showLoading('Connexion au coach IA...');
        
        try {
            const audioReady = await initAudio();
            if (!audioReady) {
            hideLoading();
                return;
            }
            
            const result = await prepareSession(mode);
            state.sessionId = result.session_id;
            
            connectWebSocket();
            
        } catch (error) {
            hideLoading();
            showToast(error.message);
        }
    });
});

// Voice Button - Toggle (click to start/stop)
if (elements.voiceBtn) {
elements.voiceBtn.addEventListener('click', () => {
        if (!state.isConnected) {
            showToast('Non connecté au serveur');
        return;
    }
    toggleRecording();
});
}

// End Session
if (elements.endSessionBtn) {
    elements.endSessionBtn.addEventListener('click', async () => {
        if (confirm('Terminer la session ?')) {
            disconnectWebSocket();
            showSummary();
        }
    });
}

function showSummary() {
    // Format transcript for summary
    let summaryHtml = '';
    
    if (state.transcript.length === 0) {
        summaryHtml = '<p class="no-transcript">Aucun échange enregistré.</p>';
    } else {
        summaryHtml = '<div class="transcript-list">';
        state.transcript.forEach(item => {
            const role = item.role === 'assistant' ? 'Coach' : 'Vous';
            const roleClass = item.role === 'assistant' ? 'coach' : 'user';
            summaryHtml += `
                <div class="transcript-item ${roleClass}">
                    <span class="transcript-role">${role}</span>
                    <p class="transcript-text">${item.text}</p>
                </div>
            `;
        });
        summaryHtml += '</div>';
    }
    
    elements.summaryContent.innerHTML = summaryHtml;
        showStep(elements.stepSummary);
}

// Download Transcript
if (elements.downloadTranscript) {
    elements.downloadTranscript.addEventListener('click', () => {
        let text = '=== X-HEC Interview Coach - Transcript ===\n\n';
        text += `Date: ${new Date().toLocaleDateString('fr-FR')}\n`;
        text += `Mode: ${state.mode === 'question_by_question' ? 'Question par Question' : 'Simulation 20 min'}\n\n`;
        text += '---\n\n';
        
        state.transcript.forEach(item => {
            const role = item.role === 'assistant' ? 'Coach' : 'Vous';
            text += `[${role}]\n${item.text}\n\n`;
        });
        
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `xhec-interview-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
    }

// New Session
if (elements.newSession) {
elements.newSession.addEventListener('click', () => {
    state.dossierFile = null;
    state.dossierText = '';
    state.questionsList = [];
    state.sessionId = null;
    state.mode = null;
        state.transcript = [];
        state.audioQueue = [];
        
        if (state.mediaStream) {
            state.mediaStream.getTracks().forEach(track => track.stop());
            state.mediaStream = null;
        }
        if (state.audioContext) {
            state.audioContext.close();
            state.audioContext = null;
        }
        
        elements.dossierStatus.textContent = 'Glisse ton fichier ici';
    elements.dossierZone.classList.remove('has-file');
    elements.dossierInput.value = '';
    elements.uploadBtn.disabled = true;
    elements.uploadPreview.style.display = 'none';
    elements.modeCards.forEach(c => c.classList.remove('selected'));
    
    showStep(elements.stepUpload);
});
}

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 X-HEC Interview Coach v2.1');
    showStep(elements.stepUpload);
});
