const startAndstopBtn = document.getElementById('startAndstopBtn');
const chatLog = document.getElementById('chat-log');
const loadingIndicator = document.getElementById('loading');

let isRecording = false;
let stream;
let mediaRecorder;
let audioChunks = [];

function addTextMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', type);
    messageDiv.textContent = text;
    chatLog.appendChild(messageDiv);
    chatLog.scrollTop = chatLog.scrollHeight;

    // 🔊 If Gemini's reply, trigger TTS
    if (type === 'received') {
        playTTS(text);
    }
}

// 🔊 Request TTS from backend and play automatically
async function playTTS(text) {
    try {
        const response = await fetch('/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        if (!response.ok) throw new Error('TTS request failed');
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        const audio = new Audio(audioUrl);
        audio.play();
    } catch (err) {
        console.error('TTS error:', err);
    }
}


async function startRecording() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    source.connect(processor);
    processor.connect(audioContext.destination);

    const ws = new WebSocket(`ws://${window.location.host}/transcribe-stream`);
    ws.binaryType = 'arraybuffer';

    let partialTranscript = '';
    let finalTranscript = '';

    ws.onopen = () => {
        processor.onaudioprocess = (e) => {
            if (!isRecording) return;
            const input = e.inputBuffer.getChannelData(0);
            // Convert to 16-bit PCM
            const pcm = new Int16Array(input.length);
            for (let i = 0; i < input.length; i++) {
                let s = Math.max(-1, Math.min(1, input[i]));
                pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            ws.send(pcm.buffer);
        };
    };

    ws.onmessage = (event) => {
        // Each message is a final transcript
        finalTranscript = event.data;
        loadingIndicator.style.display = 'none';
        addTextMessage(finalTranscript, 'sent');
        // After final transcript, stop recording and send to backend for Gemini+TTS
        stopRecording();
        sendToBackend(finalTranscript);
    };

    ws.onerror = (err) => {
        addTextMessage('Streaming transcription error.', 'received');
        stopRecording();
    };

    isRecording = true;
    startAndstopBtn.textContent = 'Stop Recording';
    loadingIndicator.style.display = 'block';
    // No UI message for recording started
}


function stopRecording() {
    if (isRecording && stream) {
        stream.getTracks().forEach(track => track.stop());
        isRecording = false;
        startAndstopBtn.textContent = 'Start Recording';
    }
}

// Send transcript to backend for Gemini+TTS
async function sendToBackend(transcript) {
    loadingIndicator.style.display = 'block';
    try {
        const response = await fetch('/process-audio/' + crypto.randomUUID(), {
            method: 'POST',
            body: new Blob([transcript], { type: 'text/plain' })
        });
        const data = await response.json();
        if (data.gemini) {
            addTextMessage(data.gemini, 'received');
        }
    } catch (err) {
        addTextMessage('Error contacting server for Gemini/TTS.', 'received');
    }
    loadingIndicator.style.display = 'none';
}

startAndstopBtn.addEventListener('click', () => {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
});   
