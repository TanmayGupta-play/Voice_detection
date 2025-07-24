import streamlit as st
from websocket import WebSocketApp
import threading
import queue
import time
from streamlit.runtime.scriptrunner import add_script_run_ctx

st.set_page_config(page_title="Cockpit Assistant", layout="centered")
st.title("Cockpit Voice Command System")
st.markdown("Press start to activate the assistant.")

WEBSOCKET_URL = "ws://localhost:8000/ws"
message_queue = queue.Queue()

# Callbacks
def on_message(ws, message):
    print("[WS Message]", message)
    message_queue.put(message)

def on_open(ws):
    print("[WS Open]")
    message_queue.put("WebSocket connection established.")

def on_error(ws, error):
    print("[WS Error]", error)
    message_queue.put(f"Error: {error}")

def on_close(ws, code, msg):
    print("[WS Closed]")
    message_queue.put("Connection closed")

def start_ws_client():
    ws = WebSocketApp(
        WEBSOCKET_URL,
        on_message=on_message,
        on_open=on_open,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# === Streamlit Session State ===
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# === Start Button ===
if st.button("Start Listening") and not st.session_state.ws_thread:
    t = threading.Thread(target=start_ws_client, daemon=True)
    add_script_run_ctx(t)  # Enables thread use in Streamlit
    t.start()
    st.session_state.ws_thread = t
    st.success("Listening started...")

# === Display Messages (Live) ===
st.markdown("System Output")
output_box = st.empty()

def speak_text(text):
    # Only speak if text matches the new plain-text prompts or is an error
    allowed_phrases = [
        "Listening started. Say trigger word.",
        "Trigger word detected. Please say your command.",
        "Command matched. Are you sure? Say confirm or cancel.",
        "No command found. Exiting. Say trigger word again.",
        "Command confirmed. Executing command."
    ]
    if text in allowed_phrases or text.startswith("Error"):
        speak_js = f"""
        <script>
        var msg = new SpeechSynthesisUtterance({repr(text)});
        window.speechSynthesis.speak(msg);
        </script>
        """
        st.components.v1.html(speak_js, height=0)

# === Update Display Every Second ===
last_spoken = None
while True:
    new_messages = []
    while not message_queue.empty():
        new_messages.append(message_queue.get())

    if new_messages:
        st.session_state.messages.extend(new_messages)
        with output_box.container():
            for msg in st.session_state.messages[-30:]:
                st.write(msg)
        # Speak only the latest message (avoid repeating)
        if st.session_state.messages:
            latest = st.session_state.messages[-1]
            if latest != last_spoken:
                speak_text(latest)
                last_spoken = latest

    time.sleep(1)