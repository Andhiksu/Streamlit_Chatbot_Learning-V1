import os
import json
import time
import tempfile
from typing import List, Dict, Any

import streamlit as st
from google import genai
from google.genai import types as gx

# ==== Guard versi SDK (tempel setelah imports) ====
try:
    import google.genai as _genai_pkg
    _genai_ver = getattr(_genai_pkg, "__version__", "0.0.0")
except Exception:
    _genai_ver = "0.0.0"

def _parse_ver(v):
    # parsing sederhana "major.minor.patch"
    try:
        parts = v.split(".")
        major = int(parts[0]); minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor)
    except Exception:
        return (0, 0)

if _parse_ver(_genai_ver) < (1, 0):
    import streamlit as st
    st.error(
        f"google-genai {_genai_ver} terdeteksi (butuh >= 1.0.0). "
        "Jalankan di terminal:\n"
        "pip uninstall -y google-generativeai\n"
        "pip install -U \"google-genai>=1.0.0\"\n"
        "Lalu restart aplikasi."
    )
    st.stop()
# ================================================

# =====================
# Konstanta App
# =====================
APP_TITLE = "🚀StudyBuddy AI — Chatbot Teman Belajar"
MODEL_NAME = "gemini-2.5-pro"
PROMPT_FILE = "prompts_chatbot_learning.txt"


# =====================
# Util & Helpers
# =====================
def load_prompts(path: str) -> Dict[str, str]:
    """Membaca prompts dari .txt menjadi dict per section header [SECTION]."""
    if not os.path.exists(path):
        return {"SYSTEM_ROLE": "", "QUIZ_INSTRUCTION_JSON": "", "REPHRASE_INSTRUCTION": "", "REVIEW_TIPS": ""}
    raw = open(path, "r", encoding="utf-8").read()
    sections = {}
    current = None
    buf = []
    for line in raw.splitlines():
        if line.strip().startswith("[") and line.strip().endswith("]"):
            if current:
                sections[current] = "\n".join(buf).strip()
            current = line.strip().strip("[]")
            buf = []
        else:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


def ensure_state():
    defaults = {
        "api_key": "",
        "client": None,
        "context_files": [],      # list of {name, uri, mime_type, display_name}
        "context_text": "",
        "mode": "Belajar",        # Belajar | Kuis | Review
        "difficulty": "easy",     # easy | medium | hard
        "quiz": None,
        "quiz_idx": 0,
        "answers": {},
        "current_answered": False,
        "progress": {
            "total_attempts": 0,
            "total_correct": 0,
            "history": []         # [{id, correct, level, ts}]
        },
        "messages": []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def make_client(api_key: str):
    if not api_key:
        st.warning("Masukkan API Key lalu klik **Run API Key**.", icon="🔑")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Gagal membuat client: {e}")
        return None


def upload_to_gemini(client, file_name: str, file_bytes: bytes, mime_guess: str) -> dict:
    """
    Upload file ke Gemini File API.
    - Simpan tmp file dengan suffix ekstensi agar SDK bisa menebak MIME.
    - Coba kirim mime_type jika versi SDK mendukung; jika tidak, fallback tanpa argumen.
    - Kembalikan {name, uri, mime_type, display_name}.
    """
    import mimetypes

    ext = os.path.splitext(file_name)[1] or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        tmp_path = tmp.name

    try:
        try:
            uploaded = client.files.upload(file=tmp_path, mime_type=mime_guess)
        except TypeError:
            uploaded = client.files.upload(file=tmp_path)

        # (opsional) tunggu ACTIVE untuk tipe tertentu
        try:
            while getattr(uploaded, "state", None) and getattr(uploaded.state, "name", None) == "PROCESSING":
                time.sleep(1.5)
                uploaded = client.files.get(name=uploaded.name)
        except Exception:
            pass

        uri = getattr(uploaded, "uri", None) or getattr(uploaded, "name", None)
        mime = (
            getattr(uploaded, "mime_type", None)
            or mime_guess
            or (mimetypes.guess_type(file_name)[0] if file_name else None)
            or "application/octet-stream"
        )
        return {
            "name": uploaded.name,
            "uri": uri,
            "mime_type": mime,
            "display_name": file_name,
        }
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def gen_chat_response(client, messages: List[Dict[str, str]], files: List[Dict], system_role: str) -> str:
    """Panggil Gemini dengan riwayat chat + file kontekstual."""
    contents = []
    # Add context files as initial user content
    initial_parts = []
    for file_ref in files or []:
        initial_parts.append(gx.Part.from_uri(file_uri=file_ref["uri"], mime_type=file_ref["mime_type"]))
    if initial_parts:
        contents.append(gx.Content(role="user", parts=initial_parts))

    # Add history
    for msg in (messages or [])[-12:]:
        role = "user" if msg["role"] == "user" else "model"
        prefix = "Siswa: " if role == "user" else "StudyBuddy AI: "
        contents.append(gx.Content(role=role, parts=[gx.Part(text=prefix + msg["content"])]))
    
    config = gx.GenerateContentConfig(
        temperature=0.6,
        system_instruction=system_role if system_role else None
    )
    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config,
    )
    return resp.text or ""


def gen_quiz(client, difficulty: str, topic_text: str, files: List[Dict],
             sys_role: str, quiz_instr: str, n_items: int = 5):
    """Minta Gemini membuat kuis JSON terstruktur."""
    prompt = f"""{sys_role}

Konsep/topik pembelajaran:
---
{topic_text.strip() if topic_text else "(lihat file terlampir)"}
---

Petunjuk kuis:
{quiz_instr}

Jumlah soal: {n_items}
Level: {difficulty}

KELUARKAN **HANYA** JSON VALID sesuai skema (tanpa penjelasan tambahan).
"""
    initial_parts = [gx.Part(text=prompt)]
    for file_ref in files or []:
        initial_parts.append(gx.Part.from_uri(file_uri=file_ref["uri"], mime_type=file_ref["mime_type"]))
    contents = [gx.Content(role="user", parts=initial_parts)]
    
    config = gx.GenerateContentConfig(
        temperature=0.7,
        response_mime_type="application/json"
    )
    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config,
    )
    text = resp.text
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise ValueError("Gagal parse JSON kuis dari model.")


def show_progress():
    prog = st.session_state["progress"]
    attempts = prog["total_attempts"]
    correct = prog["total_correct"]
    acc = (correct / attempts) * 100 if attempts else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Percobaan", attempts)
    col2.metric("Benar", correct)
    col3.metric("Akurasi", f"{acc:.1f}%")

    if prog["history"]:
        last5 = prog["history"][-5:]
        st.caption("Ringkasan 5 jawaban terakhir:")
        st.write([("✅" if h["correct"] else "❌") + f" ({h['level']})" for h in last5])


def update_progress(qid: str, correct: bool, level: str):
    prog = st.session_state["progress"]
    prog["total_attempts"] += 1
    if correct:
        prog["total_correct"] += 1
    prog["history"].append({"id": qid, "correct": correct, "level": level, "ts": time.time()})


def render_chat_area(client, prompts):
    st.subheader("💬 Chat Belajar")
    for m in st.session_state["messages"]:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.write(m["content"])

    user_msg = st.chat_input("Tanyakan apa saja tentang materi …")
    if user_msg:
        st.session_state["messages"].append({"role": "user", "content": user_msg})
        try:
            reply = gen_chat_response(
                client,
                st.session_state["messages"],
                st.session_state["context_files"],
                prompts.get("SYSTEM_ROLE", ""),
            )
        except Exception as e:
            reply = f"Terjadi error saat memanggil model: {e}"
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)
        st.rerun()


def render_quiz_area(client, prompts):
    st.subheader("📝 Mode Kuis")
    left, right = st.columns([2, 1])
    with right:
        show_progress()
    with left:
        if st.session_state["quiz"] is None:
            n = st.number_input("Jumlah soal", min_value=3, max_value=15, value=5, step=1)
            if st.button("🎯 Buat Kuis"):
                with st.spinner("Menyusun kuis dari materi…"):
                    try:
                        topic_text = st.session_state["context_text"]
                        data = gen_quiz(
                            client,
                            st.session_state["difficulty"],
                            topic_text,
                            st.session_state["context_files"],
                            prompts.get("SYSTEM_ROLE", ""),
                            prompts.get("QUIZ_INSTRUCTION_JSON", ""),
                            n_items=int(n),
                        )
                        st.session_state["quiz"] = data
                        st.session_state["quiz_idx"] = 0
                        st.session_state["answers"] = {}
                        st.session_state["current_answered"] = False
                        st.success("Kuis siap!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal membuat kuis: {e}")
        else:
            qdata = st.session_state["quiz"]["items"]
            idx = st.session_state["quiz_idx"]
            if idx >= len(qdata):
                st.success("Kuis selesai! 🎉")
                show_progress()
                if st.button("Ulangi Kuis"):
                    st.session_state["quiz"] = None
                    st.session_state["quiz_idx"] = 0
                    st.session_state["answers"] = {}
                    st.session_state["current_answered"] = False
                    st.rerun()
                return

            item = qdata[idx]
            st.markdown(f"**Soal {idx + 1} / {len(qdata)}**")
            st.write(item["question"])
            answered = st.session_state.get("current_answered", False)
            if not answered:
                choice = st.radio(
                    "Pilih jawaban:",
                    options=list(range(4)),
                    format_func=lambda i: f"{['A','B','C','D'][i]}. {item['options'][i]}",
                    key=f"q_{item['id']}_{idx}",
                )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Kunci Jawaban", use_container_width=True):
                        if choice is None:
                            st.warning("Pilih satu jawaban dulu!")
                        else:
                            st.session_state["answers"][item["id"]] = choice
                            st.session_state["current_answered"] = True
                            st.rerun()
            else:
                selected = st.session_state["answers"].get(item["id"], None)
                if selected is not None:
                    st.write(f"**Jawaban Anda:** {['A','B','C','D'][selected]}. {item['options'][selected]}")
                correct = (selected == item["answer_index"])
                update_progress(item["id"], correct, st.session_state["difficulty"])
                if correct:
                    st.success("Benar! ✅")
                else:
                    st.error(f"Salah. ❌ **Jawaban benar:** {['A','B','C','D'][item['answer_index']]} . {item['options'][item['answer_index']]}")
                with st.expander("Penjelasan"):
                    st.write(item.get("explanation", ""))
                if st.button("Lanjut ➡️", use_container_width=True):
                    st.session_state["quiz_idx"] += 1
                    st.session_state["current_answered"] = False
                    st.rerun()


def render_review_area(client, prompts):
    st.subheader("🔁 Mode Review")
    wrong_ids = [h["id"] for h in st.session_state["progress"]["history"] if not h["correct"]]
    if not wrong_ids:
        st.info("Belum ada jawaban salah. Selesaikan kuis dulu ya!")
        return

    ctx_text = st.session_state["context_text"]
    prompt = f"""{prompts.get('SYSTEM_ROLE','')}

{prompts.get('REVIEW_TIPS','')}

Ringkas ulang materi terkait ID soal berikut (anggap itu mewakili area sulit):
{wrong_ids}

Jika ada file, gunakan juga sebagai rujukan."""
    initial_parts = [gx.Part(text=prompt)]
    for file_ref in st.session_state["context_files"]:
        initial_parts.append(gx.Part.from_uri(file_uri=file_ref["uri"], mime_type=file_ref["mime_type"]))
    if ctx_text:
        initial_parts.append(gx.Part(text="Ringkasan/topik:\n" + ctx_text[:3000]))
    contents = [gx.Content(role="user", parts=initial_parts)]
    
    config = gx.GenerateContentConfig(
        temperature=0.5,
    )

    if st.button("Buat Kartu Review"):
        with st.spinner("Menyusun kartu review…"):
            try:
                resp = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contents,
                    config=config,
                )
                st.markdown(resp.text or "_(tidak ada output)_")
            except Exception as e:
                st.error(f"Gagal membuat review: {e}")


def reset_all():
    """Reset semua state untuk belajar dari awal."""
    st.session_state["context_files"] = []
    st.session_state["context_text"] = ""
    st.session_state["messages"] = []
    st.session_state["quiz"] = None
    st.session_state["quiz_idx"] = 0
    st.session_state["answers"] = {}
    st.session_state["current_answered"] = False
    st.session_state["progress"] = {
        "total_attempts": 0,
        "total_correct": 0,
        "history": []
    }
    st.session_state["mode"] = "Belajar"
    st.session_state["difficulty"] = "easy"
    st.success("Semua data telah direset! Siap belajar dari awal.")
    st.rerun()


# =====================
# MAIN (semua UI di sini)
# =====================
def main():
    st.set_page_config(page_title="StudyBuddy AI", page_icon="🚀", layout="wide")
    ensure_state()
    prompts = load_prompts(PROMPT_FILE)

    st.title(APP_TITLE)
    st.caption("Teman belajar yang membantu kamu memahami materi dengan cara interaktif — unggah materi atau masukkan topik yang ingin kamu pelajari, lakukan tanya-jawab, ikuti kuis, dan tinjau kembali konsep yang belum dikuasai.")

    # ---- Sidebar: Pengaturan & Upload ----
    with st.sidebar:
        # Bagian Pengaturan Utama (selalu terlihat)
        st.header("⚙️ Pengaturan")
        api = st.text_input("Google AI API Key", type="password", placeholder="AI...", help="Masukkan API Key dari Google AI Studio")
        if st.button("🔑 Set API Key", use_container_width=True):
            st.session_state["api_key"] = api
            st.session_state["client"] = make_client(api)
            if st.session_state["client"]:
                st.success("✅ API Key berhasil diset!")
            else:
                st.error("❌ Gagal set API Key. Periksa kembali.")

        # Button Reset (selalu terlihat)
        if st.button("🔄 Reset Semua", use_container_width=True, help="Hapus semua data dan mulai dari awal"):
            reset_all()

        # Expander untuk Materi Belajar (untuk menghemat ruang)
        with st.expander("📄 Materi Belajar", expanded=True):
            uploaded_file = st.file_uploader("Upload File", type=["pdf", "txt", "md"], help="Unggah PDF, TXT, atau MD untuk konteks belajar")
            if st.button("📂 Buka File", use_container_width=True):
                if st.session_state["client"] is None:
                    st.warning("⚠️ Set API Key dulu!")
                elif uploaded_file is None:
                    st.warning("⚠️ Pilih file terlebih dahulu!")
                else:
                    name_lower = uploaded_file.name.lower()
                    mime = uploaded_file.type or "application/octet-stream"
                    if name_lower.endswith(".md") and mime == "text/plain":
                        mime = "text/markdown"
                    elif name_lower.endswith(".txt"):
                        mime = "text/plain"
                    elif name_lower.endswith(".pdf"):
                        mime = "application/pdf"

                    file_bytes = uploaded_file.read()
                    meta = upload_to_gemini(st.session_state["client"], uploaded_file.name, file_bytes, mime)
                    st.session_state["context_files"].append(meta)
                    st.success(f"✅ File '{uploaded_file.name}' diunggah!")

            # Input Topik dan Explore
            context_input = st.text_input(
                "Tidak ada file? Masukkan topik yang ingin dipelajari:",
                key="context_text",
                placeholder="Contoh: Matematika, fisika, kimia...",
                help="Deskripsikan topik yang ingin dipelajari"
            )

            # Button Explore (kondisional)
            if st.session_state["client"] and st.session_state["context_text"].strip():
                if st.button("🔍 Explore Topik", use_container_width=True):
                    with st.spinner("Sedang mengeksplorasi topik..."):
                        explore_prompt = f"Jelaskan secara singkat tentang {st.session_state['context_text']}"
                        try:
                            reply = gen_chat_response(
                                st.session_state["client"],
                                [{"role": "user", "content": explore_prompt}],
                                st.session_state["context_files"],
                                prompts.get("SYSTEM_ROLE", ""),
                            )
                            st.session_state["messages"].append({"role": "user", "content": explore_prompt})
                            st.session_state["messages"].append({"role": "assistant", "content": reply})
                            st.session_state["mode"] = "Belajar"
                            st.success("✅ Topik dieksplorasi! Beralih ke mode Belajar.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal mengeksplorasi: {e}")
            elif st.session_state["client"] and st.button("🔍 Explore Topik", use_container_width=True, disabled=True):
                st.info("📝 Masukkan topik terlebih dahulu!")

        # Pengaturan Mode (di bagian bawah, ringkas)
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Level Kuis", options=["easy", "medium", "hard"], key="difficulty", help="Pilih tingkat kesulitan kuis")
        with col2:
            st.radio("Mode", options=["Belajar", "Kuis", "Review"], key="mode", horizontal=True, help="Pilih mode interaksi")

    # ---- Main Area ----
    if st.session_state["client"] is None:
        st.info("🔑 Masukkan API Key di sidebar untuk memulai.")
        return

    if st.session_state["mode"] == "Belajar":
        render_chat_area(st.session_state["client"], prompts)
    elif st.session_state["mode"] == "Kuis":
        render_quiz_area(st.session_state["client"], prompts)
    else:
        render_review_area(st.session_state["client"], prompts)


if __name__ == "__main__":
    main()