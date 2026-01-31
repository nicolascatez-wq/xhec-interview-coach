/**
 * X-HEC Interview Coach - Frontend Application
 * Real-time voice-to-voice with OpenAI Realtime API
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
    
    // Transcript
    transcript: []
};

// ============ Audio Configuration ============
const SAMPLE_RATE = 24000; // OpenAI Realtime uses 24kHz

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
    coachMessage: document.getElementById('coachMessage'),
    coachAvatar: document.getElementById('coachAvatar'),
    coachSpeaking: document.getElementById('coachSpeaking'),
    voiceBtn: document.getElementById('voiceBtn'),
    voiceStatus: document.getElementById('voiceStatus'),
    transcriptBox: document.getElementById('transcriptBox'),
    transcriptText: document.getElementById('transcriptText'),
    endSessionBtn: document.getElementById('endSessionBtn'),
    
    // Summary
    summaryQuestionsCount: document.getElementById('summaryQuestionsCount'),
    summaryMode: document.getElementById('summaryMode'),
    summaryContent: document.getElementById('summaryContent'),
    downloadTranscript: document.getElementById('downloadTranscript'),
    newSession: document.getElementById('newSession'),
    
    // UI
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage'),
    connectionStatus: document.getElementById('connectionStatus')
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
        step.style.display = 'none';
    });
    stepElement.style.display = 'block';
}

function updateConnectionStatus(status, text) {
    const dot = elements.connectionStatus.querySelector('.status-dot');
    const textEl = elements.connectionStatus.querySelector('.status-text');
    
    dot.style.background = status === 'connected' ? 'var(--success)' : 
                           status === 'connecting' ? 'var(--warning)' : 'var(--error)';
    textEl.textContent = text;
}

function addToTranscript(role, text) {
    state.transcript.push({ role, text, timestamp: new Date() });
    
    // Update UI
    const roleLabel = role === 'assistant' ? '🎓 Coach' : '👤 Vous';
    const entry = document.createElement('div');
    entry.className = `transcript-entry transcript-${role}`;
    entry.innerHTML = `<strong>${roleLabel}:</strong> ${text}`;
    
    if (!elements.transcriptBox.querySelector('.transcript-entries')) {
        elements.transcriptBox.innerHTML = '<div class="transcript-entries"></div>';
    }
    elements.transcriptBox.querySelector('.transcript-entries').appendChild(entry);
    elements.transcriptBox.scrollTop = elements.transcriptBox.scrollHeight;
}

// ============ Audio Handling ============

async function initAudio() {
    try {
        // Request microphone access
        state.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });
        
        // Create audio context
        state.audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        
        // Load audio worklet for processing
        await state.audioContext.audioWorklet.addModule('/static/audio-processor.js');
        
        console.log('✅ Audio initialized');
        return true;
        
    } catch (error) {
        console.error('❌ Audio init failed:', error);
        showToast('Erreur: Impossible d\'accéder au microphone. Vérifiez les permissions.');
        return false;
    }
}

function startRecording() {
    if (!state.mediaStream || !state.audioContext || !state.websocket) return;
    
    const source = state.audioContext.createMediaStreamSource(state.mediaStream);
    state.audioWorklet = new AudioWorkletNode(state.audioContext, 'audio-processor');
    
    state.audioWorklet.port.onmessage = (event) => {
        if (state.isRecording && state.websocket?.readyState === WebSocket.OPEN) {
            // Convert Float32 to Int16 PCM
            const float32Data = event.data;
            const int16Data = new Int16Array(float32Data.length);
            
            for (let i = 0; i < float32Data.length; i++) {
                const s = Math.max(-1, Math.min(1, float32Data[i]));
                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Send as base64
            const base64 = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)));
            state.websocket.send(JSON.stringify({ type: 'audio', data: base64 }));
        }
    };
    
    source.connect(state.audioWorklet);
    state.audioWorklet.connect(state.audioContext.destination);
    
    state.isRecording = true;
    updateVoiceUI(true);
}

function stopRecording() {
    if (state.audioWorklet) {
        state.audioWorklet.disconnect();
        state.audioWorklet = null;
    }
    state.isRecording = false;
    updateVoiceUI(false);
    
    // Commit audio buffer
    if (state.websocket?.readyState === WebSocket.OPEN) {
        state.websocket.send(JSON.stringify({ type: 'commit' }));
    }
}

function updateVoiceUI(recording) {
    if (recording) {
        elements.voiceBtn.classList.add('recording');
        elements.voiceBtn.querySelector('.voice-text').textContent = 'En écoute...';
        elements.voiceStatus.querySelector('.status-text').textContent = '🔴 Parlez maintenant';
    } else {
        elements.voiceBtn.classList.remove('recording');
        elements.voiceBtn.querySelector('.voice-text').textContent = 'Appuie pour parler';
        elements.voiceStatus.querySelector('.status-text').textContent = 'Prêt';
    }
}

// ============ Audio Playback ============

async function playAudioChunk(base64Audio) {
    if (!state.audioContext) return;
    
    // Decode base64 to Int16 PCM
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    
    // Convert Int16 to Float32 for Web Audio
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x8000;
    }
    
    // Create audio buffer
    const audioBuffer = state.audioContext.createBuffer(1, float32.length, SAMPLE_RATE);
    audioBuffer.copyToChannel(float32, 0);
    
    // Queue for playback
    state.audioQueue.push(audioBuffer);
    
    if (!state.isPlaying) {
        playNextInQueue();
    }
}

function playNextInQueue() {
    if (state.audioQueue.length === 0) {
        state.isPlaying = false;
        state.isSpeaking = false;
        elements.coachSpeaking.style.display = 'none';
        return;
    }
    
    state.isPlaying = true;
    state.isSpeaking = true;
    elements.coachSpeaking.style.display = 'flex';
    
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
    elements.coachSpeaking.style.display = 'none';
    
    if (state.websocket?.readyState === WebSocket.OPEN) {
        state.websocket.send(JSON.stringify({ type: 'interrupt' }));
    }
}

// ============ WebSocket Connection ============

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/interview/${state.sessionId}`;
    
    updateConnectionStatus('connecting', 'Connexion...');
    
    state.websocket = new WebSocket(wsUrl);
    
    state.websocket.onopen = () => {
        console.log('✅ WebSocket connected');
        state.isConnected = true;
        updateConnectionStatus('connected', 'Connecté');
        
        // Show interview step
        showStep(elements.stepInterview);
        hideLoading();
        
        // Update coach message
        elements.coachMessage.querySelector('p').textContent = 
            "Je suis connecté ! Appuie sur le micro et présente-toi en 2-3 minutes. Qui es-tu, ton parcours, et pourquoi X-HEC ?";
    };
    
    state.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'audio':
                playAudioChunk(data.data);
                break;
                
            case 'transcript':
                if (data.text && data.text.trim()) {
                    addToTranscript(data.role, data.text);
                    if (data.role === 'assistant') {
                        elements.coachMessage.querySelector('p').textContent = data.text;
                    }
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
        updateConnectionStatus('disconnected', 'Déconnecté');
    };
    
    state.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus('error', 'Erreur connexion');
        showToast('Erreur de connexion au serveur');
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
        }, 1000);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
});

// Mode Selection
elements.modeCards.forEach(card => {
    card.addEventListener('click', async () => {
        elements.modeCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        
        const mode = card.dataset.mode;
        state.mode = mode;
        
        showLoading('Connexion au coach IA...');
        
        try {
            // Initialize audio
            const audioReady = await initAudio();
            if (!audioReady) {
                hideLoading();
                return;
            }
            
            // Prepare session
            const result = await prepareSession(mode);
            state.sessionId = result.session_id;
            
            // Connect WebSocket
            connectWebSocket();
            
        } catch (error) {
            hideLoading();
            showToast(error.message);
        }
    });
});

// Voice Button - Push to talk
elements.voiceBtn.addEventListener('mousedown', () => {
    if (!state.isConnected) {
        showToast('Non connecté au serveur');
        return;
    }
    
    // Interrupt AI if speaking
    if (state.isSpeaking) {
        interruptPlayback();
    }
    
    startRecording();
});

elements.voiceBtn.addEventListener('mouseup', () => {
    if (state.isRecording) {
        stopRecording();
    }
});

elements.voiceBtn.addEventListener('mouseleave', () => {
    if (state.isRecording) {
        stopRecording();
    }
});

// Touch support for mobile
elements.voiceBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (!state.isConnected) {
        showToast('Non connecté au serveur');
        return;
    }
    
    if (state.isSpeaking) {
        interruptPlayback();
    }
    
    startRecording();
});

elements.voiceBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    if (state.isRecording) {
        stopRecording();
    }
});

// End Session
elements.endSessionBtn.addEventListener('click', async () => {
    if (confirm('Veux-tu vraiment terminer la session ?')) {
        disconnectWebSocket();
        showSummary();
    }
});

function showSummary() {
    elements.summaryQuestionsCount.textContent = state.transcript.filter(t => t.role === 'assistant').length;
    elements.summaryMode.textContent = state.mode === 'question_by_question' ? 'Q&R' : '20 min';
    
    // Format transcript for summary
    let summaryHtml = '<h3>Transcript de la session</h3>';
    state.transcript.forEach(item => {
        const role = item.role === 'assistant' ? '🎓 Coach' : '👤 Vous';
        summaryHtml += `<p><strong>${role}:</strong> ${item.text}</p>`;
    });
    
    elements.summaryContent.innerHTML = summaryHtml;
    showStep(elements.stepSummary);
}

// Download Transcript
elements.downloadTranscript.addEventListener('click', () => {
    let text = '=== X-HEC Interview Coach - Transcript ===\n\n';
    text += `Date: ${new Date().toLocaleDateString('fr-FR')}\n`;
    text += `Mode: ${state.mode}\n\n`;
    
    state.transcript.forEach(item => {
        const role = item.role === 'assistant' ? 'Coach' : 'Vous';
        text += `${role}: ${item.text}\n\n`;
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

// New Session
elements.newSession.addEventListener('click', () => {
    // Reset state
    state.dossierFile = null;
    state.dossierText = '';
    state.questionsList = [];
    state.sessionId = null;
    state.mode = null;
    state.transcript = [];
    state.audioQueue = [];
    
    // Cleanup audio
    if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(track => track.stop());
        state.mediaStream = null;
    }
    if (state.audioContext) {
        state.audioContext.close();
        state.audioContext = null;
    }
    
    // Reset UI
    elements.dossierStatus.textContent = 'Aucun fichier sélectionné';
    elements.dossierZone.classList.remove('has-file');
    elements.dossierInput.value = '';
    elements.uploadBtn.disabled = true;
    elements.uploadPreview.style.display = 'none';
    elements.modeCards.forEach(c => c.classList.remove('selected'));
    elements.transcriptBox.innerHTML = '';
    
    updateConnectionStatus('disconnected', 'Prêt');
    showStep(elements.stepUpload);
});

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 X-HEC Interview Coach v2.0 (OpenAI Realtime)');
    updateConnectionStatus('disconnected', 'Prêt');
});
