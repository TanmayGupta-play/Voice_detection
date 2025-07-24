import streamlit as st
from websocket import WebSocketApp
import threading
import queue
import time
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit_autorefresh import st_autorefresh
import requests

st.set_page_config(page_title="Cockpit Assistant", layout="wide")
st.title("Cockpit Voice Command System")
st.markdown("Press start to activate the assistant.")

# Add a Back button to the top left corner
st.markdown(
    """
    <style>
    .back-btn-container {
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 2147483647 !important;  /* Maximum z-index with !important */
    }
    </style>
    <div class="back-btn-container">
        <form action="/" method="get">
            <button style="padding:8px 16px; font-size:16px; border-radius:5px; border:none; background:#eee; cursor:pointer;">⬅ Back</button>
        </form>
    </div>
    """,
    unsafe_allow_html=True
)

WEBSOCKET_URL = "ws://localhost:8000/ws"

# === Streamlit Session State ===
if "message_queue" not in st.session_state:
    st.session_state.message_queue = queue.Queue()
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "message_history" not in st.session_state:
    st.session_state.message_history = []
if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False

def on_message(ws, message):
    print("[WS Message]", message)
    st.session_state.message_queue.put(message)

def on_open(ws):
    print("[WS Open]")
    st.session_state.message_queue.put("WebSocket connection established.")
    st.session_state.ws_connected = True

def on_error(ws, error):
    print("[WS Error]", error)
    st.session_state.message_queue.put(f"Error: {error}")
    st.session_state.ws_connected = False

def on_close(ws, code, msg):
    print("[WS Closed]")
    st.session_state.message_queue.put("Connection closed")
    st.session_state.ws_connected = False

def start_ws_client():
    ws = WebSocketApp(
        WEBSOCKET_URL,
        on_message=on_message,
        on_open=on_open,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# === Start/Restart Button ===
if "listening" not in st.session_state:
    st.session_state.listening = False

# Only show Start Listening button if not already listening
if not st.session_state.listening:
    if st.button("Start Listening"):
        st.session_state.listening = True
else:
    st.info("Listening is active.")

# Only start the thread if listening is True and thread is not running
if st.session_state.listening:
    if not st.session_state.ws_thread or not st.session_state.ws_thread.is_alive():
        print("[DEBUG] Starting new WebSocket thread")
        t = threading.Thread(target=start_ws_client, daemon=True)
        add_script_run_ctx(t)
        t.start()
        st.session_state.ws_thread = t
        st.success("Listening started...")

# === Display Messages (Live) ===
st.markdown("System Output")
output_box = st.empty()

def speak_text(text):
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

# === Poll for New Messages (Streamlit Timer) ===
last_spoken = st.session_state.get("last_spoken", None)

def poll_messages():
    new_messages = []
    while not st.session_state.message_queue.empty():
        new_messages.append(st.session_state.message_queue.get())
    if new_messages:
        st.session_state.messages.extend(new_messages)
        st.session_state.message_history.extend(new_messages)
        print(f"[DEBUG] New messages: {new_messages}")
    with output_box.container():
        for msg in st.session_state.message_history[-30:]:
            st.write(msg)
    # Speak only the latest message (avoid repeating)
    if st.session_state.message_history:
        latest = st.session_state.message_history[-1]
        if latest != st.session_state.get("last_spoken", None):
            speak_text(latest)
            st.session_state.last_spoken = latest

# This will refresh the app every 1000 ms (1 second)
st_autorefresh(interval=1000, key="message_poll")

def backend_is_up():
    try:
        # Use the correct URL for your backend (change if not localhost)
        r = requests.get("http://localhost:8000/docs", timeout=1)
        return r.status_code == 200
    except Exception:
        return False

if not backend_is_up():
    st.error("Backend is not running! Please restart the backend server (e.g., run 'uvicorn backend.app:app --reload').")
    st.stop()