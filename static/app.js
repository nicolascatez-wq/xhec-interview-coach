/**
 * X-HEC Interview Coach - Frontend Application
 * Sequential voice flow with Whisper + GPT-4 + TTS
 * v3.1 - Fixed flow
 */

// ============ State Management ============
const state = {
    // Session
    sessionId: null,
    mode: null,
    dossierText: '',
    
    // Themes & Questions
    themes: {},
    currentTheme: null,
    currentQuestions: [],
    currentQuestion: null,
    
    // Interview state
    hasAnsweredCurrentQuestion: false,
    questionsAnswered: 0,
    
    // Audio
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    isPlaying: false,
    isProcessing: false,
    
    // Transcript (for download)
    transcript: []
};

// ============ DOM Elements ============
const $ = (id) => document.getElementById(id);

const elements = {
    // Steps
    stepUpload: $('stepUpload'),
    stepMode: $('stepMode'),
    stepThemes: $('stepThemes'),
    stepQuestions: $('stepQuestions'),
    stepInterview: $('stepInterview'),
    stepDebrief: $('stepDebrief'),
    
    // Upload
    uploadForm: $('uploadForm'),
    dossierInput: $('dossierInput'),
    dossierZone: $('dossierZone'),
    dossierStatus: $('dossierStatus'),
    uploadBtn: $('uploadBtn'),
    
    // Mode
    modeCards: document.querySelectorAll('.mode-card'),
    
    // Themes
    themesGrid: $('themesGrid'),
    backToMode: $('backToMode'),
    
    // Questions
    selectedThemeTitle: $('selectedThemeTitle'),
    questionsList: $('questionsList'),
    randomQuestionBtn: $('randomQuestionBtn'),
    backToThemes: $('backToThemes'),
    
    // Interview
    coachMessage: $('coachMessage'),
    coachText: $('coachText'),
    voiceCircle: $('voiceCircle'),
    voiceStatus: $('voiceStatus'),
    nextQuestionBtn: $('nextQuestionBtn'),
    endSessionBtn: $('endSessionBtn'),
    
    // Debrief
    debriefContent: $('debriefContent'),
    downloadTranscript: $('downloadTranscript'),
    newSession: $('newSession'),
    
    // UI
    loadingOverlay: $('loadingOverlay'),
    loadingText: $('loadingText'),
    toast: $('toast'),
    toastMessage: $('toastMessage'),
    audioPlayer: $('audioPlayer')
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

function showStep(stepId) {
    const steps = ['stepUpload', 'stepMode', 'stepThemes', 'stepQuestions', 'stepInterview', 'stepDebrief'];
    steps.forEach(id => {
        const el = $(id);
        if (el) el.style.display = id === stepId ? 'flex' : 'none';
    });
}

function setVoiceState(newState) {
    // States: idle, recording, speaking, processing
    elements.voiceCircle.classList.remove('recording', 'speaking', 'processing');
    if (newState !== 'idle') {
        elements.voiceCircle.classList.add(newState);
    }
    
    const statusTexts = {
        idle: 'Clique pour répondre',
        recording: 'Clique quand tu as fini',
        speaking: 'Le coach parle...',
        processing: 'Traitement en cours...'
    };
    elements.voiceStatus.textContent = statusTexts[newState] || '';
}

function updateNextQuestionButton() {
    if (state.hasAnsweredCurrentQuestion) {
        elements.nextQuestionBtn.textContent = 'Question suivante';
            } else {
        elements.nextQuestionBtn.textContent = 'Passer cette question';
    }
}

// ============ Audio Functions ============

async function initMediaRecorder() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true
            }
        });
        
        state.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                state.audioChunks.push(event.data);
            }
        };
        
        state.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
            state.audioChunks = [];
            await processUserAudio(audioBlob);
        };
        
        return true;
    } catch (error) {
        console.error('Microphone access denied:', error);
        showToast('Erreur: Accès au microphone refusé');
        return false;
    }
}

function startRecording() {
    if (!state.mediaRecorder || state.isRecording || state.isProcessing || state.isPlaying) return;
    
    state.audioChunks = [];
    state.mediaRecorder.start();
    state.isRecording = true;
    setVoiceState('recording');
}

function stopRecording() {
    if (!state.mediaRecorder || !state.isRecording) return;
    
    state.mediaRecorder.stop();
    state.isRecording = false;
    setVoiceState('processing');
    state.isProcessing = true;
}

function toggleRecording() {
    if (state.isPlaying) {
        // Stop playback if needed
        elements.audioPlayer.pause();
        state.isPlaying = false;
    }
    
    if (state.isRecording) {
        stopRecording();
    } else if (!state.isProcessing) {
        startRecording();
    }
}

async function processUserAudio(audioBlob) {
    try {
        // 1. Transcribe with Whisper
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        const transcribeRes = await fetch('/api/transcribe', {
            method: 'POST',
            body: formData
        });
        
        if (!transcribeRes.ok) throw new Error('Transcription failed');
        
        const { text: userText } = await transcribeRes.json();
        
        // Add to transcript
        state.transcript.push({ role: 'user', content: userText });
        
        // 2. Send to backend for response
        const responseFormData = new FormData();
        responseFormData.append('user_text', userText);
        
        const responseRes = await fetch(`/api/session/${state.sessionId}/respond`, {
            method: 'POST',
            body: responseFormData
        });
        
        if (!responseRes.ok) throw new Error('Response failed');
        
        const responseData = await responseRes.json();
        
        // Add to transcript
        state.transcript.push({ role: 'assistant', content: responseData.text });
        
        // Mark that user has answered
        state.hasAnsweredCurrentQuestion = true;
        state.questionsAnswered++;
        updateNextQuestionButton();
        
        // 3. Display and play response
        elements.coachText.textContent = responseData.text;
        await playAudioBase64(responseData.audio_base64);
        
    } catch (error) {
        console.error('Process error:', error);
        showToast('Erreur de traitement');
    } finally {
        state.isProcessing = false;
        setVoiceState('idle');
    }
}

async function playAudioBase64(base64Audio) {
    return new Promise((resolve) => {
        const audioData = atob(base64Audio);
        const arrayBuffer = new ArrayBuffer(audioData.length);
        const uint8Array = new Uint8Array(arrayBuffer);
        for (let i = 0; i < audioData.length; i++) {
            uint8Array[i] = audioData.charCodeAt(i);
        }
        
        const blob = new Blob([uint8Array], { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);
        
        elements.audioPlayer.src = url;
        state.isPlaying = true;
        setVoiceState('speaking');
        
        elements.audioPlayer.onended = () => {
            state.isPlaying = false;
            setVoiceState('idle');
            URL.revokeObjectURL(url);
            resolve();
        };
        
        elements.audioPlayer.onerror = () => {
            state.isPlaying = false;
            setVoiceState('idle');
            URL.revokeObjectURL(url);
            resolve();
        };
        
        elements.audioPlayer.play();
    });
}

// ============ API Functions ============

async function uploadDossier(file) {
    const formData = new FormData();
    formData.append('dossier', file);
    
    const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    
    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Upload failed');
    }
    
    return res.json();
}

async function createSession(mode, dossierText) {
    const formData = new FormData();
    formData.append('mode', mode);
    formData.append('dossier_text', dossierText);
    
    const res = await fetch('/api/session/create', {
        method: 'POST',
        body: formData
    });
    
    if (!res.ok) throw new Error('Session creation failed');
    
    return res.json();
}

async function getSessionIntro() {
    const res = await fetch(`/api/session/${state.sessionId}/intro`);
    if (!res.ok) throw new Error('Failed to get intro');
    return res.json();
}

async function getThemes() {
    const res = await fetch('/api/themes');
    if (!res.ok) throw new Error('Failed to get themes');
    return res.json();
}

async function getThemeQuestions(theme) {
    const res = await fetch(`/api/themes/${encodeURIComponent(theme)}/questions?session_id=${state.sessionId}`);
    if (!res.ok) throw new Error('Failed to get questions');
    return res.json();
}

async function selectTheme(theme) {
    const formData = new FormData();
    formData.append('theme', theme);
    
    const res = await fetch(`/api/session/${state.sessionId}/select-theme`, {
        method: 'POST',
        body: formData
    });
    
    if (!res.ok) throw new Error('Failed to select theme');
    return res.json();
}

async function selectQuestion(question = null, random = false) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d712d6a5-4cbe-4e45-9537-f408a7e04dec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:selectQuestion:entry',message:'Calling selectQuestion',data:{question:question,random:random,sessionId:state.sessionId,currentTheme:state.currentTheme},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,B,C'})}).catch(()=>{});
    // #endregion
    
    const formData = new FormData();
    if (question) formData.append('question', question);
    formData.append('random', random.toString());
    
    const res = await fetch(`/api/session/${state.sessionId}/select-question`, {
        method: 'POST',
        body: formData
    });
    
    // #region agent log
    const resText = await res.clone().text();
    fetch('http://127.0.0.1:7242/ingest/d712d6a5-4cbe-4e45-9537-f408a7e04dec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:selectQuestion:response',message:'API response',data:{ok:res.ok,status:res.status,body:resText},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,D,E'})}).catch(()=>{});
    // #endregion
    
    if (!res.ok) throw new Error('Failed to select question');
    return res.json();
}

async function getDebrief() {
    const res = await fetch(`/api/session/${state.sessionId}/debrief`, {
        method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to get debrief');
    return res.json();
}

// ============ UI Rendering ============

function renderThemes(themes) {
    elements.themesGrid.innerHTML = '';
    
    Object.entries(themes).forEach(([theme, count]) => {
        const card = document.createElement('div');
        card.className = 'theme-card';
        card.innerHTML = `
            <h4>${theme}</h4>
            <span class="count">${count} questions</span>
        `;
        card.onclick = () => handleThemeSelect(theme);
        elements.themesGrid.appendChild(card);
    });
}

function renderQuestions(questions) {
    elements.questionsList.innerHTML = '';
    
    if (questions.length === 0) {
        elements.questionsList.innerHTML = '<p class="no-questions">Plus de questions disponibles dans ce thème</p>';
        return;
    }
    
    questions.forEach(question => {
        const item = document.createElement('div');
        item.className = 'question-item';
        item.textContent = question;
        item.onclick = () => handleQuestionSelect(question);
        elements.questionsList.appendChild(item);
    });
}

function renderDebrief(debrief) {
    let html = '';
    
    // Points forts
    if (debrief.points_forts && debrief.points_forts.length > 0) {
        html += `
            <div class="debrief-section strengths">
                <h3>✓ Points forts</h3>
                ${debrief.points_forts.map(p => `
                    <div class="debrief-item">
                        <h4>${p.titre}</h4>
                        <p>${p.detail}</p>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Points à améliorer
    if (debrief.points_amelioration && debrief.points_amelioration.length > 0) {
        html += `
            <div class="debrief-section improvements">
                <h3>⚡ Points à améliorer</h3>
                ${debrief.points_amelioration.map(p => `
                    <div class="debrief-item">
                        <h4>${p.titre}</h4>
                        <p>${p.detail}</p>
                        ${p.conseil ? `<p class="conseil">💡 ${p.conseil}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Note globale
    if (debrief.note_globale) {
        html += `
            <div class="debrief-section score">
                <h3>📊 Note globale</h3>
                <div class="score-display">
                    <span class="score-number">${debrief.note_globale.score}</span>
                    <p class="score-comment">${debrief.note_globale.commentaire}</p>
                </div>
            </div>
        `;
    }
    
    // Prochain objectif
    if (debrief.prochain_objectif) {
        html += `
            <div class="next-objective">
                <h4>🎯 Pour ta prochaine session</h4>
                <p>${debrief.prochain_objectif}</p>
            </div>
        `;
    }
    
    elements.debriefContent.innerHTML = html;
}

// ============ Event Handlers ============

async function handleUpload(e) {
    e.preventDefault();
    
    const file = elements.dossierInput.files[0];
    if (!file) return;
    
    showLoading('Analyse de ton dossier...');
    
    try {
        const result = await uploadDossier(file);
        state.dossierText = result._dossier_text;
        
        hideLoading();
        showStep('stepMode');
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

async function handleModeSelect(mode) {
    state.mode = mode;
    
    showLoading('Préparation de ta session...');
    
    try {
        // Create session
        const sessionResult = await createSession(mode, state.dossierText);
        state.sessionId = sessionResult.session_id;
        
        // Initialize microphone
        const micReady = await initMediaRecorder();
        if (!micReady) {
            hideLoading();
            return;
        }
        
        if (mode === 'question_by_question') {
            // Load themes and show theme selection
            const themesResult = await getThemes();
            state.themes = themesResult.themes;
            renderThemes(state.themes);
            
            hideLoading();
            showStep('stepThemes');
        } else {
            // Full interview mode - start directly
            const introResult = await getSessionIntro();
            
            state.transcript.push({ role: 'assistant', content: introResult.text });
            elements.coachText.textContent = introResult.text;
            
            // Reset question state for interview
            state.hasAnsweredCurrentQuestion = false;
            updateNextQuestionButton();
            
            hideLoading();
            showStep('stepInterview');
            
            await playAudioBase64(introResult.audio_base64);
        }
        } catch (error) {
            hideLoading();
            showToast(error.message);
        }
}

async function handleThemeSelect(theme) {
    state.currentTheme = theme;
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/d712d6a5-4cbe-4e45-9537-f408a7e04dec',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:handleThemeSelect',message:'Theme selected',data:{theme:theme,sessionId:state.sessionId},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    showLoading('Chargement des questions...');
    
    try {
        // Set theme on backend session (REQUIRED for select-question to work)
        await selectTheme(theme);
        
        // Get available questions for this theme
        const questionsResult = await getThemeQuestions(theme);
        state.currentQuestions = questionsResult.questions;
        
        elements.selectedThemeTitle.textContent = theme;
        renderQuestions(state.currentQuestions);
            
            hideLoading();
        showStep('stepQuestions');
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

async function handleQuestionSelect(question) {
    showLoading('Préparation de la question...');
    
    try {
        const result = await selectQuestion(question, false);
        
        if (!result.success) {
            hideLoading();
            showToast(result.message);
            return;
        }
        
        state.currentQuestion = result.question;
        state.hasAnsweredCurrentQuestion = false;
        updateNextQuestionButton();
        
        elements.coachText.textContent = result.text;
        state.transcript.push({ role: 'assistant', content: result.text });
        
        hideLoading();
        showStep('stepInterview');
        
        await playAudioBase64(result.audio_base64);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

async function handleRandomQuestion() {
    showLoading('Tirage d\'une question...');
    
    try {
        const result = await selectQuestion(null, true);
        
        if (!result.success) {
            hideLoading();
            showToast(result.message || 'Plus de questions disponibles');
            // Refresh the questions list
            if (state.currentTheme) {
                const questionsResult = await getThemeQuestions(state.currentTheme);
                state.currentQuestions = questionsResult.questions;
                renderQuestions(state.currentQuestions);
            }
            showStep('stepQuestions');
            return;
        }
        
        state.currentQuestion = result.question;
        state.hasAnsweredCurrentQuestion = false;
        updateNextQuestionButton();
        
        elements.coachText.textContent = result.text;
        state.transcript.push({ role: 'assistant', content: result.text });
        
        hideLoading();
        showStep('stepInterview');
        
        await playAudioBase64(result.audio_base64);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

async function handleNextQuestion() {
    // Go back to question selection to choose next question
    showLoading('Chargement...');
    
    try {
        // Refresh questions list (to remove already asked ones)
        const questionsResult = await getThemeQuestions(state.currentTheme);
        state.currentQuestions = questionsResult.questions;
        renderQuestions(state.currentQuestions);
        
        // Reset state for new question
        state.currentQuestion = null;
        state.hasAnsweredCurrentQuestion = false;
        updateNextQuestionButton();
        
        hideLoading();
        showStep('stepQuestions');
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

async function handleEndSession() {
    if (state.questionsAnswered === 0) {
        showToast('Réponds à au moins une question avant de terminer');
        return;
    }
    
    showLoading('Génération du débrief...');
    
    try {
        const result = await getDebrief();
        
        renderDebrief(result.debrief);
        
        hideLoading();
        showStep('stepDebrief');
        
        // Play summary audio
        await playAudioBase64(result.audio_base64);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

function handleDownloadTranscript() {
    let text = '=== X-HEC Interview Coach - Transcript ===\n\n';
    text += `Date: ${new Date().toLocaleDateString('fr-FR')}\n`;
    text += `Mode: ${state.mode === 'question_by_question' ? 'Question par Question' : 'Simulation 20 min'}\n\n`;
    text += '---\n\n';
    
    state.transcript.forEach(item => {
        const role = item.role === 'assistant' ? 'Coach' : 'Moi';
        text += `[${role}]\n${item.content}\n\n`;
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
    }

function handleNewSession() {
    // Reset state
    state.sessionId = null;
    state.mode = null;
    state.dossierText = '';
    state.themes = {};
    state.currentTheme = null;
    state.currentQuestions = [];
    state.currentQuestion = null;
    state.hasAnsweredCurrentQuestion = false;
    state.questionsAnswered = 0;
    state.transcript = [];
    
    // Stop media recorder
    if (state.mediaRecorder && state.mediaRecorder.stream) {
        state.mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    state.mediaRecorder = null;
    
    // Reset UI
    elements.dossierInput.value = '';
    elements.dossierZone.classList.remove('has-file');
    elements.dossierStatus.textContent = 'Dépose ton dossier de candidature';
    elements.uploadBtn.disabled = true;
    elements.modeCards.forEach(c => c.classList.remove('selected'));
    
    showStep('stepUpload');
}

// ============ Event Listeners ============

// Upload
elements.dossierInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        elements.dossierStatus.textContent = file.name;
        elements.dossierZone.classList.add('has-file');
        elements.uploadBtn.disabled = false;
    }
});

elements.uploadForm.addEventListener('submit', handleUpload);

// Mode selection
elements.modeCards.forEach(card => {
    card.addEventListener('click', () => {
        elements.modeCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        handleModeSelect(card.dataset.mode);
    });
});

// Navigation buttons
elements.backToMode.addEventListener('click', () => showStep('stepMode'));
elements.backToThemes.addEventListener('click', () => showStep('stepThemes'));

// Questions
elements.randomQuestionBtn.addEventListener('click', handleRandomQuestion);

// Voice circle - toggle recording
elements.voiceCircle.addEventListener('click', toggleRecording);

// Interview controls
elements.nextQuestionBtn.addEventListener('click', handleNextQuestion);
elements.endSessionBtn.addEventListener('click', handleEndSession);

// Debrief
elements.downloadTranscript.addEventListener('click', handleDownloadTranscript);
elements.newSession.addEventListener('click', handleNewSession);

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 X-HEC Interview Coach v3.1');
    showStep('stepUpload');
});
