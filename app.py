import json
from datetime import datetime
import requests
import streamlit as st

st.set_page_config(page_title="AI Robustness Lab - Attack Testing", layout="centered")

st.title("AI Robustness Lab - Attack Testing")

# Initialize session state for conversation history
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "attack_log" not in st.session_state:
    st.session_state.attack_log = []

# Local llama.cpp server configuration
LLAMACPP_URL = "http://localhost:8080/v1/chat/completions"

with st.sidebar:
    st.header("Settings")

    # Server URL input
    server_url = st.text_input(
        "llama.cpp Server URL",
        value=LLAMACPP_URL,
        help="URL of your local llama.cpp server (default: http://localhost:8080/v1/chat/completions)",
    )

    # Connection status indicator
    st.info("Using local llama.cpp server (Qwen 2.5 7B Q4)")

    st.divider()

    model_label = "Qwen 2.5 7B Instruct (local)"
    model = "qwen2.5-7b-instruct"  # Not used by llama.cpp but kept for logging

    temperature = st.slider("Temperature", 0.0, 1.5, 0.7, 0.05)
    max_tokens = st.slider("Max tokens", 32, 2048, 512, 32)
    top_p = st.slider("Top P", 0.1, 1.0, 0.9, 0.05)

    system_prompt = st.text_area(
        "System prompt",
        value="You are a helpful assistant.",
        height=80,
    )

    st.divider()

    # Conversation controls
    st.subheader("Conversation")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Clear", use_container_width=True):
            st.session_state.conversation_history = []
            st.session_state.attack_log = []
            st.rerun()

    with col_b:
        if st.session_state.attack_log:
            # Create export data
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "model": model_label,
                "system_prompt": system_prompt,
                "attacks": st.session_state.attack_log
            }
            export_json = json.dumps(export_data, indent=2)

            st.download_button(
                label="Export",
                data=export_json,
                file_name=f"attack_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

    # Show request counter
    if st.session_state.attack_log:
        st.metric("Requests sent", len(st.session_state.attack_log))

st.subheader("Chat")

# Display conversation history
if st.session_state.conversation_history:
    st.markdown("### Conversation History")
    for i, msg in enumerate(st.session_state.conversation_history):
        if msg["role"] == "user":
            st.markdown(f"**You ({i//2 + 1}):**")
            st.info(msg["content"])
        elif msg["role"] == "assistant":
            st.markdown(f"**Assistant ({i//2 + 1}):**")
            st.success(msg["content"])
    st.divider()

user_prompt = st.text_area(
    "Your message",
    value="",
    height=150,
    placeholder="Enter your attack prompt here...",
)

col1, col2 = st.columns([1, 1])
with col1:
    send_btn = st.button("Send", use_container_width=True, type="primary")

with col2:
    mark_success = st.checkbox("Mark as successful attack", value=False)

if send_btn:
    if not user_prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        headers = {
            "Content-Type": "application/json",
        }

        # Build messages with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(st.session_state.conversation_history)
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "messages": messages,
        }

        with st.spinner("Calling local llama.cpp server..."):
            try:
                resp = requests.post(server_url, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to llama.cpp server. Make sure llama-server is running at " + server_url)
            except requests.exceptions.Timeout:
                st.error("Request timed out. The model might be processing a long response.")
            except requests.exceptions.RequestException as e:
                st.error(f"Request error: {e}")
            except ValueError:
                st.error("Failed to parse JSON response from server.")
            else:
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError):
                    st.error("Unexpected response format.")
                    st.json(data)
                else:
                    # Add to conversation history
                    st.session_state.conversation_history.append(
                        {"role": "user", "content": user_prompt}
                    )
                    st.session_state.conversation_history.append(
                        {"role": "assistant", "content": content}
                    )

                    # Add to attack log
                    attack_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "attempt_number": len(st.session_state.attack_log) + 1,
                        "user_prompt": user_prompt,
                        "assistant_response": content,
                        "success": mark_success,
                        "model": model_label,
                        "temperature": temperature,
                    }
                    st.session_state.attack_log.append(attack_entry)

                    # Display latest response
                    st.markdown("### Model Response")
                    st.success(content)

                    if mark_success:
                        st.balloons()
                        st.success("Marked as successful attack!")

                    with st.expander("Raw response (debug)"):
                        st.json(data)

                    # Rerun to update conversation display
                    st.rerun()

