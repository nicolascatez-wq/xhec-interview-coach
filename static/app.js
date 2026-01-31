/**
 * X-HEC Interview Coach - Frontend Application
 * Voice-to-voice interview training with Web Speech API
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
    presentationDone: false,
    currentQuestion: null,
    questionsAnswered: 0,
    totalQuestions: 0,
    
    // Voice
    isRecording: false,
    currentTranscript: '',
    recognition: null,
    synthesis: window.speechSynthesis
};

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
    questionDisplay: document.getElementById('questionDisplay'),
    currentQuestion: document.getElementById('currentQuestion'),
    voiceBtn: document.getElementById('voiceBtn'),
    voiceStatus: document.getElementById('voiceStatus'),
    transcriptBox: document.getElementById('transcriptBox'),
    transcriptText: document.getElementById('transcriptText'),
    clearTranscript: document.getElementById('clearTranscript'),
    submitResponse: document.getElementById('submitResponse'),
    feedbackBox: document.getElementById('feedbackBox'),
    feedbackText: document.getElementById('feedbackText'),
    nextQuestionBtn: document.getElementById('nextQuestionBtn'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
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
    // Hide all steps
    [elements.stepUpload, elements.stepMode, elements.stepInterview, elements.stepSummary].forEach(step => {
        step.style.display = 'none';
    });
    // Show target step
    stepElement.style.display = 'block';
}

function updateProgress() {
    const percent = state.totalQuestions > 0 
        ? (state.questionsAnswered / state.totalQuestions) * 100 
        : 0;
    elements.progressFill.style.width = `${percent}%`;
    elements.progressText.textContent = `${state.questionsAnswered} / ${state.totalQuestions} questions`;
}

// ============ Web Speech API - Speech Recognition ============

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        showToast('⚠️ La reconnaissance vocale n\'est pas supportée par ce navigateur. Utilisez Chrome ou Edge.');
        return false;
    }
    
    state.recognition = new SpeechRecognition();
    state.recognition.lang = 'fr-FR';
    state.recognition.continuous = true;
    state.recognition.interimResults = true;
    
    state.recognition.onstart = () => {
        state.isRecording = true;
        elements.voiceBtn.classList.add('recording');
        elements.voiceBtn.querySelector('.voice-text').textContent = 'En écoute...';
        elements.voiceStatus.querySelector('.status-text').textContent = '🔴 Enregistrement en cours';
        elements.transcriptBox.style.display = 'block';
    };
    
    state.recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript;
            }
        }
        
        if (finalTranscript) {
            state.currentTranscript += finalTranscript;
        }
        
        elements.transcriptText.textContent = state.currentTranscript + interimTranscript;
        
        // Show submit button when we have content
        if (state.currentTranscript.trim().length > 10) {
            elements.submitResponse.style.display = 'block';
        }
    };
    
    state.recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') {
            elements.voiceStatus.querySelector('.status-text').textContent = 'Pas de parole détectée. Réessayez.';
        } else {
            showToast(`Erreur de reconnaissance: ${event.error}`);
        }
    };
    
    state.recognition.onend = () => {
        state.isRecording = false;
        elements.voiceBtn.classList.remove('recording');
        elements.voiceBtn.querySelector('.voice-text').textContent = 'Appuie pour parler';
        elements.voiceStatus.querySelector('.status-text').textContent = 'Prêt à écouter';
    };
    
    return true;
}

function toggleRecording() {
    if (state.isRecording) {
        state.recognition.stop();
    } else {
        state.currentTranscript = '';
        elements.transcriptText.textContent = '';
        elements.submitResponse.style.display = 'none';
        state.recognition.start();
    }
}

// ============ Web Speech API - Text to Speech ============

function speak(text, onEnd = null) {
    // Stop any ongoing speech
    state.synthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'fr-FR';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    // Try to find a French voice
    const voices = state.synthesis.getVoices();
    const frenchVoice = voices.find(v => v.lang.startsWith('fr')) || voices[0];
    if (frenchVoice) {
        utterance.voice = frenchVoice;
    }
    
    utterance.onstart = () => {
        elements.coachSpeaking.style.display = 'flex';
    };
    
    utterance.onend = () => {
        elements.coachSpeaking.style.display = 'none';
        if (onEnd) onEnd();
    };
    
    utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event);
        elements.coachSpeaking.style.display = 'none';
        if (onEnd) onEnd();
    };
    
    state.synthesis.speak(utterance);
}

// Load voices when available
if (state.synthesis) {
    state.synthesis.onvoiceschanged = () => {
        console.log('Voices loaded:', state.synthesis.getVoices().length);
    };
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

async function createSession(mode) {
    const formData = new FormData();
    formData.append('mode', mode);
    formData.append('dossier_text', state.dossierText);
    
    const response = await fetch('/api/session/create', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Session creation failed');
    }
    
    return response.json();
}

async function startInterview(presentation) {
    const response = await fetch('/api/interview/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: state.sessionId,
            message: presentation
        })
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start interview');
    }
    
    return response.json();
}

async function submitResponseAPI(question, response_text) {
    const response = await fetch('/api/interview/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: state.sessionId,
            question: question,
            response: response_text
        })
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to submit response');
    }
    
    return response.json();
}

async function getNextQuestion() {
    const formData = new FormData();
    formData.append('session_id', state.sessionId);
    
    const response = await fetch('/api/interview/next-question', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get next question');
    }
    
    return response.json();
}

async function getSummary() {
    const formData = new FormData();
    formData.append('session_id', state.sessionId);
    
    const response = await fetch('/api/interview/summary', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get summary');
    }
    
    return response.json();
}

async function getTranscript() {
    const response = await fetch(`/api/interview/transcript/${state.sessionId}`);
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to get transcript');
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
        
        // Store parsed data
        state.dossierText = result._dossier_text;
        state.questionsList = result._questions_list;
        state.totalQuestions = result.questions_count;
        
        // Show preview
        elements.questionsCount.textContent = result.questions_count;
        elements.uploadPreview.style.display = 'block';
        
        hideLoading();
        
        // Move to mode selection after short delay
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
        // Visual selection
        elements.modeCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        
        const mode = card.dataset.mode;
        state.mode = mode;
        
        showLoading('Préparation de la session...');
        
        try {
            const result = await createSession(mode);
            state.sessionId = result.session_id;
            state.totalQuestions = result.questions_count;
            
            hideLoading();
            
            // Initialize speech recognition
            if (!initSpeechRecognition()) {
                showToast('Reconnaissance vocale non disponible. Vous pouvez toujours utiliser l\'app en mode texte.');
            }
            
            // Move to interview
            showStep(elements.stepInterview);
            updateProgress();
            
            // Welcome message
            const welcomeMsg = "Bienvenue ! Commence par te présenter en 2-3 minutes. Qui es-tu, ton parcours, et pourquoi X-HEC ?";
            elements.coachMessage.querySelector('p').textContent = welcomeMsg;
            speak(welcomeMsg);
            
        } catch (error) {
            hideLoading();
            showToast(error.message);
        }
    });
});

// Voice Button
elements.voiceBtn.addEventListener('click', () => {
    if (!state.recognition) {
        showToast('Reconnaissance vocale non initialisée');
        return;
    }
    toggleRecording();
});

// Clear Transcript
elements.clearTranscript.addEventListener('click', () => {
    state.currentTranscript = '';
    elements.transcriptText.textContent = '';
    elements.submitResponse.style.display = 'none';
});

// Submit Response
elements.submitResponse.addEventListener('click', async () => {
    if (!state.currentTranscript.trim()) {
        showToast('Enregistre d\'abord ta réponse');
        return;
    }
    
    // Stop recording if still going
    if (state.isRecording) {
        state.recognition.stop();
    }
    
    showLoading('Analyse de ta réponse...');
    
    try {
        if (!state.presentationDone) {
            // This is the presentation
            const result = await startInterview(state.currentTranscript);
            state.presentationDone = true;
            
            hideLoading();
            
            // Extract question from coach response
            const coachResponse = result.coach_response;
            elements.coachMessage.querySelector('p').textContent = coachResponse;
            
            // Extract and display the question part
            state.currentQuestion = extractQuestion(coachResponse);
            if (state.currentQuestion) {
                elements.questionDisplay.style.display = 'block';
                elements.currentQuestion.textContent = state.currentQuestion;
            }
            
            // Clear transcript for next response
            state.currentTranscript = '';
            elements.transcriptText.textContent = '';
            elements.submitResponse.style.display = 'none';
            
            // Speak the response
            speak(coachResponse);
            
        } else {
            // This is a response to a question
            const question = state.currentQuestion || 'Question précédente';
            const result = await submitResponseAPI(question, state.currentTranscript);
            
            state.questionsAnswered = result.questions_answered;
            updateProgress();
            
            hideLoading();
            
            if (state.mode === 'question_by_question' && result.feedback) {
                // Show feedback for Mode 1
                elements.feedbackBox.style.display = 'block';
                elements.feedbackText.textContent = result.feedback;
                speak(result.feedback);
            } else {
                // Mode 2 - just move to next question
                await loadNextQuestion();
            }
            
            // Clear transcript
            state.currentTranscript = '';
            elements.transcriptText.textContent = '';
            elements.submitResponse.style.display = 'none';
        }
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
});

// Next Question Button (Mode 1)
elements.nextQuestionBtn.addEventListener('click', async () => {
    elements.feedbackBox.style.display = 'none';
    await loadNextQuestion();
});

async function loadNextQuestion() {
    showLoading('Question suivante...');
    
    try {
        const result = await getNextQuestion();
        
        hideLoading();
        
        if (result.interview_complete) {
            // Interview is done, go to summary
            await showSummary();
        } else {
            // Display next question
            const nextQ = result.question;
            elements.coachMessage.querySelector('p').textContent = nextQ;
            
            state.currentQuestion = extractQuestion(nextQ);
            if (state.currentQuestion) {
                elements.questionDisplay.style.display = 'block';
                elements.currentQuestion.textContent = state.currentQuestion;
            }
            
            speak(nextQ);
        }
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
    }
}

function extractQuestion(text) {
    // Try to extract just the question from coach's response
    const lines = text.split('\n').filter(l => l.trim());
    const questionLine = lines.find(l => l.includes('?'));
    return questionLine || text.substring(0, 200);
}

// End Session
elements.endSessionBtn.addEventListener('click', async () => {
    if (confirm('Veux-tu vraiment terminer la session ?')) {
        await showSummary();
    }
});

async function showSummary() {
    showLoading('Génération du résumé...');
    
    try {
        const result = await getSummary();
        
        hideLoading();
        
        // Update summary display
        elements.summaryQuestionsCount.textContent = state.questionsAnswered;
        elements.summaryMode.textContent = state.mode === 'question_by_question' 
            ? 'Q&R' 
            : '20 min';
        elements.summaryContent.innerHTML = formatMarkdown(result.summary);
        
        showStep(elements.stepSummary);
        
    } catch (error) {
        hideLoading();
        showToast(error.message);
        // Still show summary step even if summary generation failed
        showStep(elements.stepSummary);
        elements.summaryContent.textContent = 'Impossible de générer le résumé. Télécharge le transcript pour voir tes échanges.';
    }
}

function formatMarkdown(text) {
    // Basic markdown formatting
    return text
        .replace(/## (.*)/g, '<h2>$1</h2>')
        .replace(/### (.*)/g, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/- (.*)/g, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

// Download Transcript
elements.downloadTranscript.addEventListener('click', async () => {
    try {
        const result = await getTranscript();
        
        // Create download
        const blob = new Blob([result.transcript], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `xhec-interview-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
    } catch (error) {
        showToast(error.message);
    }
});

// New Session
elements.newSession.addEventListener('click', () => {
    // Reset state
    state.dossierFile = null;
    state.dossierText = '';
    state.questionsList = [];
    state.sessionId = null;
    state.mode = null;
    state.presentationDone = false;
    state.currentQuestion = null;
    state.questionsAnswered = 0;
    state.totalQuestions = 0;
    state.currentTranscript = '';
    
    // Reset UI
    elements.dossierStatus.textContent = 'Aucun fichier sélectionné';
    elements.dossierZone.classList.remove('has-file');
    elements.dossierInput.value = '';
    elements.uploadBtn.disabled = true;
    elements.uploadPreview.style.display = 'none';
    elements.modeCards.forEach(c => c.classList.remove('selected'));
    elements.questionDisplay.style.display = 'none';
    elements.transcriptBox.style.display = 'none';
    elements.feedbackBox.style.display = 'none';
    
    showStep(elements.stepUpload);
});

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 X-HEC Interview Coach initialized');
    
    // Check browser compatibility
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        elements.connectionStatus.querySelector('.status-dot').style.background = 'var(--warning)';
        elements.connectionStatus.querySelector('.status-text').textContent = 'Voice limité';
    }
});
