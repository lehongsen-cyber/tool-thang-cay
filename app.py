import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import json
import zipfile
import base64
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Magic Renamer Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS CAO CẤP (DASHBOARD 3 CỘT) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    body {
        font-family: 'Inter', sans-serif;
        background-color: #f3f4f6;
    }
    
    /* Ẩn Header mặc định */
    header[data-testid="stHeader"] {display: none;}
    
    /* HEADER CHÍNH */
    .top-bar {
        background: white;
        padding: 15px 30px;
        border-bottom: 1px solid #e5e7eb;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .app-logo {
        font-size: 1.5em;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* CỘT 1: LIST FILE */
    .list-header {
        font-weight: 700;
        color: #6b7280;
        margin-bottom: 10px;
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    div.stButton > button {
        width: 100%;
        text-align: left;
        border: 1px solid #e5e7eb;
        background: white;
        color: #374151;
        padding: 10px 15px;
        border-radius: 8px;
        transition: all 0.2s;
        margin-bottom: 5px;
        font-size: 0.9em;
    }
    div.stButton > button:hover {
        border-color: #6366f1;
        color: #6366f1;
        background: #eef2ff;
    }
    div.stButton > button:focus {
        background: #4f46e5;
        color: white;
        border-color: #4f46e5;
    }
    
    /* CỘT 2: PREVIEW */
    .preview-box {
        background: white;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        height: 600px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px solid #e5e7eb;
        overflow: hidden;
    }
    .preview-img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* CỘT 3: RESULT */
    .result-panel {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        height: 100%;
    }
    .dark-box {
        background-color: #111827;
        color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        margin-top: 10px;
        margin-bottom: 20px;
        font-family: 'Consolas', monospace;
        font-size: 1em;
        line-height: 1.4;
        border-left: 5px solid #8b5cf6;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        word-break: break-all;
    }
    
    /* INFO GRID */
    .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        margin-bottom: 15px;
    }
    .info-item {
        background: #f9fafb;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #f3f4f6;
    }
    .info-label {
        font-size: 0.7em;
        text-transform: uppercase;
        color: #9ca3af;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .info-value {
        font-size: 0.95em;
        color: #111827;
        font-weight: 600;
    }
    
    /* FOOTER */
    .footer-credit {
        position: fixed;
        bottom: 10px;
        right: 20px;
        font-size: 0.8em;
        color: #9ca3af;
        z-index: 999;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC BACKEND ---
if 'data' not in st.session_state:
    st.session_state.data = []
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = 0

def get_gemini_response(uploaded_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        
        # Đọc trang đầu PDF thành ảnh
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        uploaded_file.seek(0)
        
        # Prompt lấy JSON
        prompt = """
        Phân tích ảnh văn bản và trả về JSON.
        
        1. QUY TẮC TÊN FILE (new_name):
           Cấu trúc: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
           - YYYY.MM.DD: Năm.Tháng.Ngày (Ví dụ 2025.12.31). Dấu CHẤM.
           - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
           - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
           - NoiDung: Tiếng Việt không dấu, nối gạch dưới (_).
           - TrangThai: 'Signed'.
           
        2. TRƯỜNG HIỂN THỊ (Tiếng Việt có dấu):
           - date: Ngày ký (DD/MM/YYYY).
           - number: Số hiệu.
           - authority: Cơ quan ban hành.
           - summary: Trích yếu ngắn gọn.
           
        OUTPUT JSON:
        { "new_name": "...", "date": "...", "number": "...", "authority": "...", "summary": "..." }
        """
        
        image_part = {"mime_type": "image/png", "data": img_data}
        
        for _ in range(3): # Retry 3 lần
            try:
                response = model.generate_content([prompt, image_part])
                txt = response.text.strip()
                if txt.startswith("```json"): txt = txt[7:]
                if txt.endswith("```"): txt = txt[:-3]
                data = json.loads(txt)
                if not data['new_name'].lower().endswith(".pdf"):
                    data['new_name'] += ".pdf"
                return data, img_base64
            except:
                time.sleep(1)
        return None, None
    except:
        return None, None

# --- 4. GIAO DIỆN CHÍNH ---

# Top Bar
st.markdown("""
<div class="top-bar">
    <div class="app-logo">✨ Magic Renamer <span style="font-size:0.5em; color:#9ca3af; font-weight:normal;">| Thắng Cầy Edition</span></div>
    <div>
        <span style="color:#6b7280; font-size:0.9em; margin-right:5px;">Created by</span>
        <span style="color:#ec4899; font-weight:bold;">Lê Hồng Sến</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Input Area
with st.container():
    c1, c2, c3 = st.columns([1, 2, 0.5])
    with c1:
        api_key = st.text_input("🔑 API Key:", type="password")
    with c2:
        uploaded_files = st.file_uploader("Chọn file PDF", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
    with c3:
        st.write("")
        if st.button("🚀 BẮT ĐẦU", type="primary"):
            if not api_key:
                st.toast("⚠️ Thiếu API Key!")
            elif not uploaded_files:
                st.toast("⚠️ Chưa chọn file!")
            else:
                st.session_state.data = []
                st.session_state.selected_idx = 0
                
                bar = st.progress(0, text="Đang khởi động...")
                for i, f in enumerate(uploaded_files):
                    meta, img = get_gemini_response(f, api_key)
                    if meta:
                        st.session_state.data.append({
                            "original_name": f.name,
                            "file_obj": f,
                            "meta": meta,
                            "img": img
                        })
                    bar.progress((i + 1) / len(uploaded_files), text=f"Đang xử lý: {f.name}")
                bar.empty()
                st.success("✅ Hoàn tất!")

# --- 5. DASHBOARD ---
if st.session_state.data:
    st.divider()
    col_list, col_preview, col_detail = st.columns([1, 1.5, 1.5])
    
    # Cột 1: List
    with col_list:
        st.markdown(f"<div class='list-header'>📂 FILE ({len(st.session_state.data)})</div>", unsafe_allow_html=True)
        for i, item in enumerate(st.session_state.data):
            label = f"{i+1}. {item['original_name']}"
            if len(label) > 30: label = label[:27] + "..."
            if st.button(label, key=f"sel_{i}", use_container_width=True):
                st.session_state.selected_idx = i
                
    # Lấy data hiện tại
    idx = st.session_state.selected_idx
    if idx >= len(st.session_state.data): idx = 0
    curr = st.session_state.data[idx]
    meta = curr['meta']
    
    # Cột 2: Preview
    with col_preview:
        st.markdown("<div class='list-header'>👁️ BẢN XEM TRƯỚC</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="preview-box">
            <img src="data:image/png;base64,{curr['img']}" class="preview-img">
        </div>
        """, unsafe_allow_html=True)
        
    # Cột 3: Result
    with col_detail:
        st.markdown("<div class='list-header'>✨ KẾT QUẢ AI</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="result-panel">
            <div class="info-label" style="color:#6366f1;">TÊN FILE MỚI</div>
            <div class="dark-box">{meta['new_name']}</div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">NGÀY BAN HÀNH</div>
                    <div class="info-value">{meta.get('date','...')}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">SỐ HIỆU</div>
                    <div class="info-value">{meta.get('number','...')}</div>
                </div>
            </div>
            
            <div class="info-item" style="margin-bottom:15px;">
                <div class="info-label">CƠ QUAN</div>
                <div class="info-value">{meta.get('authority','...')}</div>
            </div>
            <div class="info-item" style="margin-bottom:20px;">
                <div class="info-label">TRÍCH YẾU</div>
                <div class="info-value" style="font-weight:400;">{meta.get('summary','...')}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        curr['file_obj'].seek(0)
        st.download_button(
            label="⬇️ TẢI FILE NÀY",
            data=curr['file_obj'],
            file_name=meta['new_name'],
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

    # ZIP Download
    st.divider()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for item in st.session_state.data:
            item['file_obj'].seek(0)
            zf.writestr(item['meta']['new_name'], item['file_obj'].read())
            
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.download_button(
            label="📦 TẢI TRỌN BỘ (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="Magic_Renamed_Full.zip",
            mime="application/zip",
            type="secondary",
            use_container_width=True
        )

else:
    st.markdown("""
    <div style="text-align: center; margin-top: 100px; color: #9ca3af;">
        <h3>👋 Sẵn sàng làm việc!</h3>
        <p>Vui lòng nhập Key và chọn file để bắt đầu.</p>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown('<div class="footer-credit">Created by Lê Hồng Sến</div>', unsafe_allow_html=True)
