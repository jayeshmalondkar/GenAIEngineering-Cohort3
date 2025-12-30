import streamlit as st
import requests
from datetime import datetime

# ---------------------- API Detials ----------------------
# Base of Back End APIs
BackEnd_App = "http://localhost:4567"

st.set_page_config(page_title="Knowledge Assistant", layout="wide")

# -- Preserve the Chat history in Session State ----------------------
# Maintain the chat history in the front end, so that it can be managed based on user interaction
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "is_capturing" not in st.session_state:
    st.session_state.is_capturing = False

# ---------------------- SIDEBAR ----------------------
st.sidebar.header("📚 Knowledge Capture")

url = st.sidebar.text_input("Enter Knowledge Source URL")
table_name = st.sidebar.text_input("Enter Table Name")

def capture_knowledge():
    """Trigger backend knowledge capture."""
    st.session_state.is_capturing = True
    try:
        with st.spinner("Capturing knowledge..."):
            resp = requests.post(
                f"{BackEnd_App}/Capture_Knowledge",
                json={"url": url, "table_name": table_name},
                timeout=120
            )
            data = resp.json()
            if isinstance(data, dict) and "Status" in data:
                st.sidebar.success("✅ Capture completed!")
                st.sidebar.write(f"**Status:** {data.get('Status')}")
                st.sidebar.write(f"**Source:** {data.get('Source')}")
                st.sidebar.write(f"**Chunks Captured:** {data.get('Num_Chunks')}")
                # Clear chat history on new capture
                st.session_state.chat_history = []
            else:
                st.sidebar.error(f"⚠️ Unexpected response: {data}")
    except Exception as e:
        st.sidebar.error(f"❌ Connection failed: {e}")
    finally:
        st.session_state.is_capturing = False

if st.sidebar.button("Capture Knowledge", disabled=st.session_state.is_capturing):
    if not url or not table_name:
        st.sidebar.warning("⚠️ Please provide both URL and Table Name.")
    else:
        capture_knowledge()

st.sidebar.markdown("---")
st.sidebar.caption("Discuss based on Knowledge Repo")

# ---------------------- Chat window contents ----------------------
st.title("💬 Knowledge Assistant")

# chat container
chat_container = st.container()
with chat_container:
    chat_area = st.container()
    chat_area.markdown(
        """
        <style>
        [data-testid="stVerticalBlock"] div:has(> div[data-testid="stChatMessage"]) {
            max-height: 500px;
            overflow-y: auto;
            padding-right: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Display chat history with timestamps
    for role, message, ts in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(f"**{message}**")
            st.caption(f"🕒 {ts}")

# Chat input — disabled while capturing.
# when the Reference data being captured in Knowledge bsae, chat is not disabled
prompt = st.chat_input("Ask your question...", disabled=st.session_state.is_capturing)

if prompt:
    if not table_name:
        # Required as mandatory param
        st.warning("⚠️ Please specify the table name in sidebar first.")

    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Display user message in chat area
        st.session_state.chat_history.append(("user", prompt, timestamp))
        with st.chat_message("user"):
            st.markdown(f"**{prompt}**")
            st.caption(f"🕒 {timestamp}")

        # Chat History pick:
        run = 2 # how many run required
        print (len(st.session_state.chat_history))

        n = min (run, int ((len(st.session_state.chat_history) - 1) / 2))
        # n = max (n, 0)
        if (n > 0):
            
            Chat_History = st.session_state.chat_history[-((n * 2)+1) :-1]
            Chat_History = [{t[0] : t[1]}  for t in Chat_History]
        else :
            Chat_History = []

        # print (Chat_History)
        
        # Query backend
        try:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    resp = requests.get(
                        f"{BackEnd_App}/Ask_Assistant",
                        params={"Chat_Hist" : str(Chat_History),"Query": prompt, "table_name": table_name},
                        timeout=60
                    )

                    # Backend returns plain string
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, str):
                                answer = data
                            elif isinstance(data, dict) and "response" in data:
                                answer = data["response"]
                            else:
                                answer = str(data)
                        except ValueError:
                            answer = resp.text
                    else:
                        answer = f"Error {resp.status_code}: {resp.text}"

                    ts_reply = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.markdown(answer)
                    st.caption(f"🕒 {ts_reply}")
                    st.session_state.chat_history.append(("assistant", answer, ts_reply))
        except Exception as e:
            st.error(f"❌ Failed to reach backend: {e}")
