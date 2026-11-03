/**
 * VALENCE Voice Dictation Engine for Streamlit Chat Input.
 *
 * Places an integrated microphone toggle directly inside the query box (stChatInput).
 * Uses native Web Speech API (Chrome / Edge / Safari) to transcribe technical queries
 * in real-time into the input textarea with full React / Streamlit event synchronization.
 */

(function () {
    let isRecording = false;
    let activeRecognizer = null;

    function getSpeechRec() {
        return window.SpeechRecognition || window.webkitSpeechRecognition ||
               (window.parent && (window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition));
    }

    function updateMicUi(recording, btn, container) {
        if (!btn) return;
        if (recording) {
            btn.innerHTML = '🔴';
            btn.style.borderColor = '#ef4444';
            btn.style.boxShadow = '0 0 12px rgba(239, 68, 68, 0.8)';
            btn.style.background = 'rgba(239, 68, 68, 0.2)';
            btn.title = 'Listening... Click to stop';
            const ta = container ? container.querySelector('textarea') : null;
            if (ta) ta.placeholder = '🔴 Listening... Speak clearly now.';
        } else {
            btn.innerHTML = '🎙️';
            btn.style.borderColor = 'rgba(56, 189, 248, 0.4)';
            btn.style.boxShadow = 'none';
            btn.style.background = 'transparent';
            btn.title = 'Speak query (Voice Dictation)';
            const ta = container ? container.querySelector('textarea') : null;
            if (ta) ta.placeholder = 'Ask a question or click 🎙️ to dictate query...';
        }
    }

    function toggleVoice(btn, container) {
        const ta = container ? container.querySelector('textarea') : null;

        if (isRecording) {
            if (activeRecognizer) {
                try { activeRecognizer.stop(); } catch(e) {}
            }
            isRecording = false;
            updateMicUi(false, btn, container);
            if (ta) ta.focus();
            return;
        }

        const SpeechRec = getSpeechRec();
        if (!SpeechRec) {
            alert(
                "Voice Dictation:\n\n" +
                "Web Speech is natively supported in Google Chrome, Edge, and Safari.\n" +
                "On other browsers, press your OS dictation shortcut directly into this box:\n" +
                "- Mac: Press Fn twice (Fn + Fn)\n" +
                "- Windows: Press Win + H"
            );
            if (ta) ta.focus();
            return;
        }

        try {
            const rec = new SpeechRec();
            rec.continuous = false;
            rec.interimResults = true;
            rec.lang = 'en-US';

            rec.onstart = function() {
                isRecording = true;
                updateMicUi(true, btn, container);
            };

            rec.onresult = function(event) {
                let transcript = '';
                for (let i = 0; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                if (ta) {
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set ||
                                         (window.parent && Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value')?.set);
                    if (nativeSetter) {
                        nativeSetter.call(ta, transcript);
                    } else {
                        ta.value = transcript;
                    }
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                    ta.dispatchEvent(new Event('change', { bubbles: true }));
                }
            };

            rec.onerror = function(err) {
                console.warn('[VALENCE Voice] Recognition error:', err);
                isRecording = false;
                updateMicUi(false, btn, container);
                if (err.error === 'not-allowed') {
                    alert(
                        "Microphone access blocked by browser.\n\n" +
                        "To enable:\n" +
                        "1. Click the site settings / lock icon 🔒 next to 'localhost:8501' in your Chrome address bar.\n" +
                        "2. Set 'Microphone' to 'Allow'.\n" +
                        "3. Refresh the page."
                    );
                }
            };

            rec.onend = function() {
                isRecording = false;
                updateMicUi(false, btn, container);
                if (ta) ta.focus();
            };

            activeRecognizer = rec;
            rec.start();
        } catch(err) {
            console.warn('[VALENCE Voice] Start failed:', err);
            isRecording = false;
            updateMicUi(false, btn, container);
        }
    }

    function setupMicInDoc(doc) {
        if (!doc) return;
        const container = doc.querySelector('div[data-testid="stChatInput"]');
        if (!container) return;

        let micBtn = container.querySelector('#valence-voice-mic-btn');
        if (!micBtn) {
            micBtn = doc.createElement('button');
            micBtn.id = 'valence-voice-mic-btn';
            micBtn.type = 'button';
            micBtn.title = 'Speak query (Voice Dictation)';
            micBtn.innerHTML = '🎙️';
            micBtn.setAttribute('style', [
                'position: absolute',
                'right: 48px',
                'bottom: 7px',
                'width: 32px',
                'height: 32px',
                'border-radius: 8px',
                'background: transparent',
                'border: 1px solid rgba(56, 189, 248, 0.4)',
                'cursor: pointer',
                'font-size: 1.15rem',
                'display: inline-flex',
                'align-items: center',
                'justify-content: center',
                'z-index: 99999',
                'pointer-events: auto',
                'padding: 0',
                'transition: all 0.2s ease',
                'user-select: none'
            ].join(' !important;') + ' !important;');

            micBtn.onmouseenter = function() {
                if (!isRecording) {
                    micBtn.style.borderColor = '#38bdf8';
                    micBtn.style.background = 'rgba(56, 189, 248, 0.1)';
                }
            };

            micBtn.onmouseleave = function() {
                if (!isRecording) {
                    micBtn.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                    micBtn.style.background = 'transparent';
                }
            };

            micBtn.onmousedown = function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleVoice(micBtn, container);
            };

            micBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
            };

            container.appendChild(micBtn);

            const ta = container.querySelector('textarea');
            if (ta) {
                ta.style.paddingRight = '84px';
            }
        }
    }

    function checkAll() {
        setupMicInDoc(document);
        if (window.parent && window.parent.document) {
            setupMicInDoc(window.parent.document);
        }
    }

    setInterval(checkAll, 400);
    checkAll();
})();
