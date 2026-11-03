"""Offline Text-to-Speech (TTS) component using Web Speech Synthesis API.

Provides local, air-gapped speech synthesis for technical answers and SOP steps
without any cloud dependency or remote service calls.
Features:
- Sentence-by-sentence chunking (prevents Chrome 15s speech timeout bug)
- Technical unit & acronym speech normalization (SOP, PLC, LED, °C, RPM, bar, etc.)
- Natural offline voice auto-selection (Samantha, Karen, Daniel, Google Natural)
- Full playback controls: Play, Pause, Resume, Stop, and 0.8x / 1.0x / 1.2x Speed toggles
"""

from __future__ import annotations

import json
import re
import streamlit.components.v1 as components


def clean_text_for_speech(text: str) -> str:
    """Strips citations, code blocks, and markdown markers for natural speech delivery."""
    # 1. Remove citations like [doc_id#p2#c0] or [source_id]
    cleaned = re.sub(r"\[[^\]]*#[^\]]*\]", "", text)
    # 2. Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " Code snippet omitted for audio. ", cleaned)
    # 3. Remove inline code backticks
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # 4. Remove markdown headers
    cleaned = re.sub(r"#+\s*", "", cleaned)
    # 5. Remove bold / italic symbols
    cleaned = re.sub(r"[\*_]{1,3}", "", cleaned)
    # 6. Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    # 7. Expand technical units and abbreviations for natural pronunciation
    replacements = [
        (r"\bSOPs\b", "S.O.P.s"),
        (r"\bSOP\b", "S.O.P."),
        (r"\bPLCs\b", "P.L.C.s"),
        (r"\bPLC\b", "P.L.C."),
        (r"\bCPUs\b", "C.P.U.s"),
        (r"\bCPU\b", "C.P.U."),
        (r"\bLEDs\b", "L.E.D.s"),
        (r"\bLED\b", "L.E.D."),
        (r"\bRPM\b", "R.P.M."),
        (r"\bPSI\b", "P.S.I."),
        (r"\bmax\b\.?", "maximum"),
        (r"\bmin\b\.?", "minimum"),
        (r"\bapprox\b\.?", "approximately"),
        (r"\bdept\b\.?", "department"),
        (r"\bno\b\.\s*(\d+)", r"number \1"),
        (r"°C\b", " degrees Celsius"),
        (r"°F\b", " degrees Fahrenheit"),
        (r"\bVAC\b", "volts A.C."),
        (r"\bVDC\b", "volts D.C."),
        (r"\bkHz\b", "kilohertz"),
        (r"\bMHz\b", "megahertz"),
        (r"\bHz\b", "Hertz"),
        (r"\bkW\b", "kilowatts"),
        (r"\bMW\b", "megawatts"),
        (r"\bbar\b", "bar"),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    # 8. Normalize spaces and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return cleaned.strip()


def render_tts_button(text: str, key_suffix: str = "") -> None:
    """Renders a comprehensive, high-fidelity offline TTS audio player bar."""
    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        return

    safe_text_json = json.dumps(spoken_text)
    dom_id = f"valence_tts_{re.sub(r'[^a-zA-Z0-9_]', '_', key_suffix)}"

    tts_html = f"""
    <div style="margin-top: 6px; margin-bottom: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 6px 10px; width: fit-content;">
            <!-- Main Play/Pause Button -->
            <button id="{dom_id}_play" onclick="handlePlayPause_{dom_id}()" style="
                background: rgba(59, 130, 246, 0.15);
                color: #60a5fa;
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 0.8rem;
                font-weight: 600;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 5px;
                transition: all 0.2s ease;
                user-select: none;
                outline: none;
            ">
                🔊 Listen (TTS)
            </button>

            <!-- Stop Button (hidden until active) -->
            <button id="{dom_id}_stop" onclick="handleStop_{dom_id}()" style="
                display: none;
                background: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 0.8rem;
                font-weight: 600;
                cursor: pointer;
                align-items: center;
                gap: 4px;
                user-select: none;
            ">
                ⏹️ Stop
            </button>

            <!-- Speed Controls -->
            <div style="display: flex; align-items: center; gap: 3px; border-left: 1px solid #475569; padding-left: 8px;">
                <span style="font-size: 0.72rem; color: #94a3b8; margin-right: 2px;">Speed:</span>
                <button id="{dom_id}_spd_08" onclick="setSpeed_{dom_id}(0.85)" style="background: transparent; color: #94a3b8; border: 1px solid #475569; border-radius: 4px; padding: 2px 5px; font-size: 0.72rem; cursor: pointer;">0.9x</button>
                <button id="{dom_id}_spd_10" onclick="setSpeed_{dom_id}(1.0)" style="background: rgba(59, 130, 246, 0.3); color: #93c5fd; border: 1px solid #3b82f6; border-radius: 4px; padding: 2px 5px; font-size: 0.72rem; cursor: pointer; font-weight: 600;">1.0x</button>
                <button id="{dom_id}_spd_12" onclick="setSpeed_{dom_id}(1.2)" style="background: transparent; color: #94a3b8; border: 1px solid #475569; border-radius: 4px; padding: 2px 5px; font-size: 0.72rem; cursor: pointer;">1.2x</button>
            </div>

            <!-- Status Indicator -->
            <span id="{dom_id}_status" style="font-size: 0.75rem; color: #64748b; margin-left: 4px;">Offline Native Audio</span>
        </div>
    </div>

    <script>
    (function() {{
        const rawText = {safe_text_json};
        let speechRate = 1.0;
        let isPlaying = false;
        let isPaused = false;
        let sentenceIndex = 0;
        let sentences = [];
        let chosenVoice = null;

        function getSynth() {{
            return window.speechSynthesis || (window.parent && window.parent.speechSynthesis);
        }}

        function initVoices() {{
            const synth = getSynth();
            if (!synth) return;
            const voices = synth.getVoices() || [];
            // Prioritize natural sounding English voices
            const preferred = ["Samantha", "Karen", "Daniel", "Victoria", "Google US English", "Microsoft Jenny", "Natural"];
            for (const name of preferred) {{
                const found = voices.find(v => v.name.includes(name) && v.lang.startsWith("en"));
                if (found) {{
                    chosenVoice = found;
                    break;
                }}
            }}
            if (!chosenVoice) {{
                chosenVoice = voices.find(v => v.lang.startsWith("en")) || voices[0] || null;
            }}
            if (chosenVoice) {{
                const statusEl = document.getElementById("{dom_id}_status");
                if (statusEl && !isPlaying) {{
                    statusEl.innerText = "Voice: " + chosenVoice.name.replace(/\\(.*?\\)/g, "").trim();
                }}
            }}
        }}

        initVoices();
        if (window.speechSynthesis) {{
            window.speechSynthesis.onvoiceschanged = initVoices;
        }}

        window.setSpeed_{dom_id} = function(rate) {{
            speechRate = rate;
            ["08", "10", "12"].forEach(k => {{
                const b = document.getElementById("{dom_id}_spd_" + k);
                if (b) {{
                    b.style.background = "transparent";
                    b.style.borderColor = "#475569";
                    b.style.color = "#94a3b8";
                    b.style.fontWeight = "normal";
                }}
            }});
            const activeId = rate < 0.95 ? "08" : (rate > 1.1 ? "12" : "10");
            const activeBtn = document.getElementById("{dom_id}_spd_" + activeId);
            if (activeBtn) {{
                activeBtn.style.background = "rgba(59, 130, 246, 0.3)";
                activeBtn.style.borderColor = "#3b82f6";
                activeBtn.style.color = "#93c5fd";
                activeBtn.style.fontWeight = "600";
            }}
        }};

        function splitIntoSentences(text) {{
            const matched = text.match(/[^.!?\\n]+[.!?\\n]*/g);
            return matched && matched.length > 0 ? matched.map(s => s.trim()).filter(Boolean) : [text];
        }}

        function playNextSentence() {{
            const synth = getSynth();
            if (!synth || !isPlaying || isPaused) return;

            if (sentenceIndex >= sentences.length) {{
                handleStop_{dom_id}();
                const statusEl = document.getElementById("{dom_id}_status");
                if (statusEl) statusEl.innerText = "✅ Finished playback";
                return;
            }}

            const currentText = sentences[sentenceIndex];
            const utter = new SpeechSynthesisUtterance(currentText);
            utter.rate = speechRate;
            utter.pitch = 1.0;
            utter.lang = "en-US";
            if (chosenVoice) utter.voice = chosenVoice;

            const statusEl = document.getElementById("{dom_id}_status");
            if (statusEl) {{
                statusEl.innerText = "🔊 Reading sentence " + (sentenceIndex + 1) + " of " + sentences.length;
            }}

            utter.onend = function() {{
                sentenceIndex++;
                if (isPlaying && !isPaused) {{
                    playNextSentence();
                }}
            }};

            utter.onerror = function(e) {{
                console.warn("[TTS] Utterance error:", e);
                sentenceIndex++;
                if (isPlaying && !isPaused) {{
                    playNextSentence();
                }}
            }};

            synth.speak(utter);
        }}

        window.handlePlayPause_{dom_id} = function() {{
            const synth = getSynth();
            const playBtn = document.getElementById("{dom_id}_play");
            const stopBtn = document.getElementById("{dom_id}_stop");
            const statusEl = document.getElementById("{dom_id}_status");

            if (!synth) {{
                alert("Speech Synthesis is not supported in this browser. Please use Chrome, Edge, or Safari.");
                return;
            }}

            // Case 1: Currently playing -> Pause
            if (isPlaying && !isPaused) {{
                synth.pause();
                isPaused = true;
                if (playBtn) playBtn.innerHTML = "▶️ Resume";
                if (statusEl) statusEl.innerText = "⏸️ Paused";
                return;
            }}

            // Case 2: Currently paused -> Resume
            if (isPlaying && isPaused) {{
                synth.resume();
                isPaused = false;
                if (playBtn) playBtn.innerHTML = "⏸️ Pause";
                if (statusEl) statusEl.innerText = "🔊 Reading sentence " + (sentenceIndex + 1) + " of " + sentences.length;
                return;
            }}

            // Case 3: Start fresh playback
            synth.cancel();
            sentences = splitIntoSentences(rawText);
            sentenceIndex = 0;
            isPlaying = true;
            isPaused = false;

            if (playBtn) {{
                playBtn.innerHTML = "⏸️ Pause";
                playBtn.style.background = "rgba(59, 130, 246, 0.25)";
            }}
            if (stopBtn) stopBtn.style.display = "inline-flex";

            playNextSentence();
        }};

        window.handleStop_{dom_id} = function() {{
            const synth = getSynth();
            if (synth) synth.cancel();

            isPlaying = false;
            isPaused = false;
            sentenceIndex = 0;

            const playBtn = document.getElementById("{dom_id}_play");
            const stopBtn = document.getElementById("{dom_id}_stop");
            const statusEl = document.getElementById("{dom_id}_status");

            if (playBtn) {{
                playBtn.innerHTML = "🔊 Listen (TTS)";
                playBtn.style.background = "rgba(59, 130, 246, 0.15)";
            }}
            if (stopBtn) stopBtn.style.display = "none";
            if (statusEl) {{
                statusEl.innerText = chosenVoice ? "Voice: " + chosenVoice.name.replace(/\\(.*?\\)/g, "").trim() : "Offline Native Audio";
            }}
        }};
    }})();
    </script>
    """
    components.html(tts_html, height=52)
