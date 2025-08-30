// --- API Key Modal Logic ---
function allKeysPresent() {
  return (
    localStorage.getItem('murfKey') &&
    localStorage.getItem('assemblyKey') &&
    localStorage.getItem('geminiKey')
  );
}

function updateKeyStatus() {
  const status = document.getElementById('keyStatus');
  if (allKeysPresent()) {
    status.textContent = '✅ All API keys saved!';
    document.getElementById('startAndstopBtn').disabled = false;
  } else {
    status.textContent = 'Please enter all API keys.';
    document.getElementById('startAndstopBtn').disabled = true;
  }
}

function showApiKeyModal() {
  document.getElementById('apikey-modal').classList.add('show');
  document.getElementById('apikey-blur-overlay').classList.add('show');
  setTimeout(() => {
    document.getElementById('geminiKey').focus();
  }, 200);
}
function hideApiKeyModal() {
  document.getElementById('apikey-modal').classList.remove('show');
  document.getElementById('apikey-blur-overlay').classList.remove('show');
}

window.addEventListener('DOMContentLoaded', () => {
  const mainContainer = document.querySelector('.container');
  const fabBtn = document.getElementById('openApiKeyModalBtn');
  const modal = document.getElementById('apikey-modal');
  const overlay = document.getElementById('apikey-blur-overlay');
  // Prefill fields if keys exist
  ['murfKey','assemblyKey','geminiKey'].forEach(k => {
    const v = localStorage.getItem(k);
    if (v) document.getElementById(k).value = v;
  });
  updateKeyStatus();
  function setMainAppVisible(visible) {
    if (visible) {
      mainContainer.style.display = '';
      fabBtn.style.display = '';
    } else {
      mainContainer.style.display = 'none';
      fabBtn.style.display = 'none';
    }
  }
  function showApiKeyModalFixed() {
    modal.classList.add('show');
    overlay.classList.add('show');
    setTimeout(() => {
      document.getElementById('geminiKey').focus();
    }, 200);
  }
  function hideApiKeyModalFixed() {
    modal.classList.remove('show');
    overlay.classList.remove('show');
  }
  document.getElementById('saveKeysBtn').onclick = () => {
    const murf = document.getElementById('murfKey').value.trim();
    const assembly = document.getElementById('assemblyKey').value.trim();
    const gemini = document.getElementById('geminiKey').value.trim();
    localStorage.setItem('murfKey', murf);
    localStorage.setItem('assemblyKey', assembly);
    localStorage.setItem('geminiKey', gemini);
    updateKeyStatus();
    if (allKeysPresent()) {
      setTimeout(() => {
        hideApiKeyModalFixed();
        setMainAppVisible(true);
        document.getElementById('startAndstopBtn').disabled = false;
      }, 400);
    }
  };
  ['murfKey','assemblyKey','geminiKey'].forEach(k => {
    document.getElementById(k).addEventListener('input', updateKeyStatus);
  });
  fabBtn.onclick = showApiKeyModalFixed;
  // On first load, always show modal if any key missing
  if (!allKeysPresent()) {
    showApiKeyModalFixed();
    setMainAppVisible(false);
  } else {
    setMainAppVisible(true);
  }
});

// --- Start/Stop Button Logic ---
let streamingActive = false;
// Attach start/stop handler only once DOM is loaded
window.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('startAndstopBtn');
  startBtn.onclick = () => {
    if (!streamingActive) {
      startStreamingVoiceAgent();
      startBtn.textContent = '⏹️ Stop Recording';
      streamingActive = true;
    } else {
      stopStreamingVoiceAgent();
      startBtn.textContent = '🎤 Start Recording';
      streamingActive = false;
    }
  };
});
// --- Streaming Voice Agent ---
let wsVoice = null;
let audioStreamContext = null;
let audioStreamSource = null;
let audioStreamQueue = [];
let audioStreamPlaying = false;

async function startStreamingVoiceAgent() {
  // Send API keys as first message after connect
 const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
wsVoice = new WebSocket(`${wsProtocol}//${location.host}/ws/voice`);
  wsVoice.binaryType = "arraybuffer";
  wsVoice.onopen = () => {
    console.log("Voice WebSocket connected");
    // Send keys as JSON
    wsVoice.send(JSON.stringify({
      murfKey: localStorage.getItem('murfKey'),
      assemblyKey: localStorage.getItem('assemblyKey'),
      geminiKey: localStorage.getItem('geminiKey')
    }));
    startStreamingRecording();
  };
  wsVoice.onmessage = async (event) => {
    if (typeof event.data === "string") {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "gemini" && msg.text) {
          appendMessage('bot', msg.text);
        } else if (msg.type === "error") {
          appendMessage('error', msg.error);
        }
      } catch (e) {}
    } else if (event.data instanceof ArrayBuffer) {
      playStreamedAudioChunk(event.data);
    }
  };
  wsVoice.onclose = () => {
    console.log("Voice WebSocket closed");
    stopStreamingRecording();
  };
}

function stopStreamingVoiceAgent() {
  if (wsVoice) {
    wsVoice.close();
    wsVoice = null;
  }
  stopStreamingRecording();
}

function startStreamingRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0 && wsVoice && wsVoice.readyState === 1) {
        e.data.arrayBuffer().then(buf => wsVoice.send(buf));
      }
    };
    recorder.onstop = () => {
      if (wsVoice && wsVoice.readyState === 1) wsVoice.send("__END__");
    };
    recorder.start(250); // send every 250ms
    window._streamRecorder = recorder;
  });
}

function stopStreamingRecording() {
  if (window._streamRecorder) {
    window._streamRecorder.stop();
    window._streamRecorder = null;
  }
}

function playStreamedAudioChunk(arrayBuffer) {
  if (!audioStreamContext) {
    audioStreamContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  audioStreamContext.decodeAudioData(arrayBuffer.slice(0), (audioBuffer) => {
    const source = audioStreamContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioStreamContext.destination);
    source.start();
  }, (err) => {
    console.error("Audio decode error", err);
  });
}

// --- UI Hook Example ---
// To use streaming, call startStreamingVoiceAgent() instead of startRecording().
// To stop, call stopStreamingVoiceAgent().

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let sessionId = crypto.randomUUID();
let audioContext, analyser, sourceNode, silenceTimer;

const startBtn = document.getElementById("startAndstopBtn");
const chatLog = document.getElementById("chat-log");
const loading = document.getElementById("loading");
const audioPlayer = document.getElementById("tts-audio");

startBtn.addEventListener("click", async () => {
  if (!isRecording) {
    await startRecording();
  } else {
    await stopRecording();
  }
});

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  audioChunks = [];

  // Setup Web Audio API for silence detection
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  sourceNode = audioContext.createMediaStreamSource(stream);
  analyser = audioContext.createAnalyser();
  sourceNode.connect(analyser);
  analyser.fftSize = 2048;
  const dataArray = new Uint8Array(analyser.fftSize);

  function checkSilence() {
    analyser.getByteTimeDomainData(dataArray);
    // Calculate RMS (root mean square) to detect volume
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      let val = (dataArray[i] - 128) / 128;
      sum += val * val;
    }
    let rms = Math.sqrt(sum / dataArray.length);
    if (rms < 0.01) { // Even lower threshold for more tolerant detection
      if (!silenceTimer) {
        silenceTimer = setTimeout(() => {
          if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
          }
        }, 1200); // 1.2s of silence
      }
    } else {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
    }
    if (isRecording && mediaRecorder.state === "recording") {
      requestAnimationFrame(checkSilence);
    }
  }

  mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data);
  };

  mediaRecorder.onstop = async () => {
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
    const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
    await sendToBackend(audioBlob);
    // Next recording will be started after TTS playback ends (see sendToBackend)
  };

  mediaRecorder.start();
  isRecording = true;
  startBtn.textContent = "Stop Recording";
  loading.style.display = "block";
  checkSilence();
}

async function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  isRecording = false;
  startBtn.textContent = "Start Recording";
  loading.style.display = "none";
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }
}

async function sendToBackend(audioBlob) {
  // Debug: log audioBlob size and type
  console.log("audioBlob size:", audioBlob.size, "type:", audioBlob.type);
  // Optionally, provide a download link for the recorded audio
  const debugDownload = document.getElementById("debug-download");
  if (debugDownload) {
    debugDownload.href = URL.createObjectURL(audioBlob);
    debugDownload.download = "recording.wav";
    debugDownload.style.display = "inline-block";
  }
  // Check for empty/very short audio and skip sending if so
  if (audioBlob.size < 512) { // <512B is likely silence or too short
    appendMessage("error", "No speech detected. Please speak louder or check your microphone.");
    if (isRecording) {
      await startRecording();
    }
    return;
  }

  // Immediately show user message in chat
  const transcriptPlaceholder = document.createElement("div");
  transcriptPlaceholder.className = "message user";
  transcriptPlaceholder.textContent = "...";
  chatLog.appendChild(transcriptPlaceholder);
  chatLog.scrollTop = chatLog.scrollHeight;

  const formData = new FormData();
  formData.append("file", audioBlob, "recording.wav");

  try {
    const response = await fetch(`/process-audio/${sessionId}`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error("Transcription failed.");
    const data = await response.json();


    // Remove the placeholder
    chatLog.removeChild(transcriptPlaceholder);

    // Robust null/undefined check for backend response
    if (!data || typeof data !== 'object') {
      appendMessage('error', 'No response from backend.');
      if (isRecording) await startRecording();
      return;
    }

    // Show user message immediately if present
    if (data.text) {
      appendMessage('user', data.text);
    } else {
      appendMessage('error', 'No transcript received.');
    }

    // Play TTS audio from base64, then show Nick's response
    if (data.audio_base64 && typeof data.audio_base64 === 'string' && data.audio_base64.trim() !== "" && data.gemini) {
      let audioPlayer = document.getElementById("tts-audio");
      if (!audioPlayer) {
        audioPlayer = document.createElement("audio");
        audioPlayer.id = "tts-audio";
        audioPlayer.style.display = "none";
        document.querySelector(".container").appendChild(audioPlayer);
      }
      // Always use WAV for Murf TTS
      const audioSrc = `data:audio/wav;base64,${data.audio_base64}`;
      audioPlayer.src = audioSrc;
      audioPlayer.load();
      audioPlayer.onended = async () => {
        appendMessage('bot', data.gemini);
        if (isRecording) {
          await startRecording();
        }
      };
      audioPlayer.onerror = () => {
        appendMessage('error', 'Audio playback failed.');
        appendMessage('bot', data.gemini);
      };
      audioPlayer.play();
    } else if (data.gemini) {
      // If no audio or TTS failed, show Nick's response and a warning
      appendMessage('bot', data.gemini);
      if (!data.audio_base64 || data.audio_base64.trim() === "") {
        appendMessage('error', 'TTS failed or no audio generated.');
      }
      if (isRecording) {
        await startRecording();
      }
    } else {
      // If no audio or bot response, just continue
      if (isRecording) {
        await startRecording();
      }
    }

  } catch (err) {
    console.error("Error:", err);
    appendMessage("error", "Something went wrong!");
  }

}

function appendMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "role-label";
  // Always show 'Nick:' for bot/model responses
  label.textContent = role === 'user' ? "You:" : (role === 'bot' ? "Nick:" : "");
  label.style.fontWeight = "bold";
  label.style.marginRight = "6px";
  msg.appendChild(label);
  const span = document.createElement("span");
  span.textContent = text;
  msg.appendChild(span);
  chatLog.appendChild(msg);
  chatLog.scrollTop = chatLog.scrollHeight;
}    
