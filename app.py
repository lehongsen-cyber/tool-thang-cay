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

# --- 2. CSS CAO CẤP (GIAO DIỆN DASHBOARD 3 CỘT) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    body {
        font-family: 'Inter', sans-serif;
        background-color: #f3f4f6;
    }
    
    /* Ẩn Header mặc định của Streamlit cho gọn */
    header[data-testid="stHeader"] {display: none;}
    
    /* --- HEADER CHÍNH --- */
    .top-bar {
        background: white;
        padding: 20px 40px;
        border-bottom: 1px solid #e5e7eb;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    .app-logo {
        font-size: 1.8em;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* --- CỘT 1: DANH SÁCH HÀNG CHỜ --- */
    .list-header {
        font-weight: 700;
        color: #6b7280;
        margin-bottom: 10px;
        font-size: 0.9em;
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
    
    /* --- CỘT 2: KHUNG PREVIEW --- */
    .preview-box {
        background: white;
        border-radius: 16px;
        padding: 20px;
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
        border-radius: 4px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
    }
    
    /* --- CỘT 3: KẾT QUẢ AI --- */
    .result-panel {
        background: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        height: 100%;
    }
    
    /* HỘP ĐEN CHỨA TÊN FILE */
    .dark-box {
        background-color: #111827;
        color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        margin-top: 10px;
        margin-bottom: 25px;
        font-family: 'Consolas', monospace;
        font-size: 1.1em;
        line-height: 1.5;
        border-left: 6px solid #8b5cf6; /* Viền tím */
        box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.3);
    }
    
    /* Grid thông tin chi tiết */
    .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-bottom: 20px;
    }
    .info-item {
        background: #f9fafb;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #f3f4f6;
    }
    .info-label {
        font-size: 0.75em;
        text-transform: uppercase;
        color: #9ca3af;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .info-value {
        font-size: 1.05em;
        color: #111827;
        font-weight: 600;
    }
    
    /* Footer */
    .footer-credit {
        position: fixed;
        bottom: 10px;
        right: 20px;
        font-size: 0.8em;
        color: #d1d5db;
        z-index: 999;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC XỬ LÝ (BACKEND) ---
if 'data' not in st.session_state:
    st.session_state.data = [] 
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = 0 

def get_gemini_response(uploaded_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        
        # Chuyển PDF trang đầu thành ảnh
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        uploaded_file.seek(0)
        
        # Prompt ép AI trả về JSON để lấy từng trường thông tin
        prompt = """
        Phân tích hình ảnh văn bản này và trả về JSON (Không Markdown).
        
        1. QUY TẮC TÊN FILE (new_name):
           Cấu trúc: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
           - YYYY.MM.DD: Năm.Tháng.Ngày (Ví dụ 2025.12.31). Dùng dấu CHẤM.
           - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
           - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
           - NoiDung: Tiếng Việt không dấu, nối gạch dưới (_).
           - TrangThai: 'Signed'
           
        2. CÁC TRƯỜNG HIỂN THỊ (Tiếng Việt có dấu):
           - date: Ngày ký (DD/MM/YYYY).
           - number: Số hiệu văn bản.
           - authority: Cơ quan ban hành.
           - summary: Trích yếu nội dung ngắn gọn.
           
        OUTPUT JSON:
        {
            "new_name": "...",
            "date": "...",
            "number": "...",
            "authority": "...",
            "summary": "..."
        }
        """
        
        image_part = {"mime_type": "image/png", "data": img_data}
        
        # Thử 3 lần nếu lỗi mạng
        for _ in range(3):
            try:
                response = model.generate_content([prompt, image_part])
                json_str = response.text.strip()
                # Lọc bỏ markdown nếu AI lỡ thêm vào
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                    
                data = json.loads(json_str)
                # Đảm bảo tên file có đuôi .pdf
                if not data['new_name'].lower().endswith(".pdf"):
                    data['new_name'] += ".pdf"
                    
                return data, img_base64
            except:
                time.sleep(1)
        return None, None
    except Exception:
        return None, None

# --- 4. GIAO DIỆN CHÍNH ---

# Top Bar
st.markdown("""
<div class="top-bar">
    <div class="app-logo">✨ Magic Renamer <span style="font-size:0.5em; color:#9ca3af; font-weight:normal;">| Thắng Cầy Edition</span></div>
    <div>
        <span style="color:#6b7280; font-size:0.9em; margin-right:10px;">Created by</span>
        <span style="color:#ec4899; font-weight:bold;">Lê Hồng Sến</span>
    </div>
</div>
""", unsafe_
