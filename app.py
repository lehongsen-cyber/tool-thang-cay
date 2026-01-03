import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import json
import zipfile
import base64

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Magic Renamer Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS CAO CẤP (DASHBOARD STYLE) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    body {
        font-family: 'Inter', sans-serif;
        background-color: #f3f4f6;
    }
    
    /* Ẩn Header mặc định */
    header[data-testid="stHeader"] {display: none;}
    
    /* --- HEADER CHÍNH --- */
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
    
    /* --- CỘT TRÁI: DANH SÁCH --- */
    .list-item {
        background: white;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 8px;
        border: 1px solid #e5e7eb;
        cursor: pointer;
        transition: all 0.2s;
        font-size: 0.9em;
        color: #374151;
    }
    .list-item:hover {
        border-color: #6366f1;
        box-shadow: 0 2px 5px rgba(99, 102, 241, 0.1);
    }
    .list-item.active {
        background-color: #eef2ff;
        border-left: 4px solid #6366f1;
        font-weight: 600;
        color: #4338ca;
    }
    
    /* --- CỘT GIỮA: PREVIEW --- */
    .preview-container {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
        height: 100%;
        min-height: 500px;
    }
    .preview-img {
        max-width: 100%;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* --- CỘT PHẢI: KẾT QUẢ (GIỐNG ẢNH MẪU) --- */
    .result-panel {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Hộp đen chứa tên file */
    .dark-box {
        background-color: #111827;
        color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-family: 'Consolas', monospace;
        font-size: 1.1em;
        line-height: 1.4;
        border-left: 5px solid #8b5cf6;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    
    /* Grid thông tin */
    .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        margin-bottom: 15px;
    }
    .info-item {
        background: #f9fafb;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #f3f4f6;
    }
    .info-label {
        font-size: 0.75em;
        text-transform: uppercase;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .info-value {
        font-size: 1em;
        color: #1f2937;
        font-weight: 600;
    }
    
    /* Footer */
    .footer-credit {
        text-align: center;
        margin-top: 40px;
        color: #9ca3af;
        font-size: 0.9em;
    }
    .author-highlight {
        color: #ec4899;
        font-weight: bold;
    }
    
    /* Nút bấm Custom */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC BACKEND ---

if 'data' not in st.session_state:
    st.session_state.data = [] # Lưu danh sách file đã xử lý
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = 0 # Lưu chỉ số file đang chọn xem

def get_gemini_response(uploaded_file, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        
        # Chuyển PDF sang ảnh để AI đọc
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Prompt trả về JSON
        prompt = """
        Phân tích hình ảnh văn bản hành chính này và trả về kết quả định dạng JSON.
        
        1. QUY TẮC ĐẶT TÊN FILE (new_name):
           Cấu trúc: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
           - YYYY.MM.DD: Năm.Tháng.Ngày (Ví dụ: 2025.12.31).
           - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
           - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
           - NoiDung: Tiếng Việt không dấu, nối gạch dưới (_).
           - TrangThai: 'Signed'
           
        2. CÁC TRƯỜNG KHÁC (để hiển thị giao diện):
           - date: Ngày ban hành (DD/MM/YYYY).
           - number: Số hiệu văn bản.
           - authority: Cơ quan ban hành (UBND..., Sở...).
           - summary: Trích yếu nội dung ngắn gọn (Tiếng Việt có dấu).
           
        OUTPUT JSON FORMAT:
        {
            "new_name": "...",
            "date": "...",
            "number": "...",
            "authority": "...",
            "summary": "..."
        }
        """
        
        image_part = {"mime_type": "image/png", "data": img_data}
        
        response = model.generate_content([prompt, image_part])
        json_str = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(json_str)
        
        return data, img_base64
    except Exception as e:
        return None, None

# --- 4. GIAO DIỆN CHÍNH ---

# Top Bar
st.markdown("""
<div class="top-bar">
    <div class="app-logo">✨ Magic Renamer <span style="font-size:0.6em; color: #6b7280;">| Thắng Cầy Edition</span></div>
    <div style="font-size: 0.9em; font-weight: bold; color: #ec4899;">Created by Lê Hồng Sến</div>
</div>
""", unsafe_allow_html=True)

# Input Section (Ẩn gọn trong Expander nếu muốn, hoặc để trần)
with st.container():
    c1, c2, c3 = st.columns([1, 2, 0.5])
    with c1:
        api_key = st.text_input("🔑 API Key:", type="password")
    with c2:
        uploaded_files = st.file_uploader("Tải file PDF vào đây:", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")
    with c3:
        st.write("") # Spacer
        if st.button("🚀 XỬ LÝ", type="primary"):
            if not api_key:
                st.toast("⚠️ Thiếu API Key!")
            elif not uploaded_files:
                st.toast("⚠️ Chưa chọn file!")
            else:
                st.session_state.data = [] # Reset
                st.session_state.selected_idx = 0
                
                bar = st.progress(0)
                for i, f in enumerate(uploaded_files):
                    meta, img = get_gemini_response(f, api_key)
                    if meta:
                        st.session_state.data.append({
                            "original_name": f.name,
                            "file_obj": f,
                            "meta": meta,
                            "img": img
                        })
                    bar.progress((i+1)/len(uploaded_files))
                bar.empty()
                st.success("Đã xử lý xong!")

# --- 5. DASHBOARD VIEW (CHỈ HIỆN KHI CÓ DỮ LIỆU) ---
if st.session_state.data:
    st.markdown("---")
    
    # Chia 3 cột: List (1) | Preview (1.5) | Detail (1.5)
    col_list, col_preview, col_detail = st.columns([1, 1.5, 1.5])
    
    # === CỘT 1: DANH SÁCH FILE ===
    with col_list:
        st.markdown(f"##### 📂 HÀNG CHỜ ({len(st.session_state.data)})")
        for i, item in enumerate(st.session_state.data):
            # Logic đổi màu nút khi được chọn
            btn_label = f"{i+1}. {item['original_name']}"
            if st.button(btn_label, key=f"btn_{i}", use_container_width=True):
                st.session_state.selected_idx = i
                
    # Lấy dữ liệu file đang chọn
    current_item = st.session_state.data[st.session_state.selected_idx]
    meta = current_item['meta']
    
    # === CỘT 2: PREVIEW ẢNH ===
    with col_preview:
        st.markdown("##### 👁️ XEM CHI TIẾT")
        st.markdown(f"""
        <div class="preview-container">
            <img src="data:image/png;base64,{current_item['img']}" class="preview-img">
        </div>
        """, unsafe_allow_html=True)
        
    # === CỘT 3: KẾT QUẢ CHI TIẾT ===
    with col_detail:
        st.markdown("##### ✨ TÊN FILE ĐỀ XUẤT")
        
        # Hộp đen chứa tên file mới (Giống ảnh mẫu)
        st.markdown(f"""
        <div class="result-panel">
            <div class="info-label" style="color:#6366f1;">TÊN FILE MỚI (COPY NẾU CẦN)</div>
            <div class="dark-box">
                {meta['new_name']}
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">NGÀY BAN HÀNH</div>
                    <div class="info-value">{meta.get('date', 'N/A')}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">SỐ HIỆU</div>
                    <div class="info-value">{meta.get('number', 'N/A')}</div>
                </div>
            </div>
            
            <div class="info-item" style="margin-bottom: 15px;">
                <div class="info-label">CƠ QUAN BAN HÀNH</div>
                <div class="info-value">{meta.get('authority', 'N/A')}</div>
            </div>
             <div class="info-item" style="margin-bottom: 20px;">
                <div class="info-label">TRÍCH YẾU NỘI DUNG</div>
                <div class="info-value" style="font-weight: normal;">{meta.get('summary', 'N/A')}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        # Nút tải file
        current_item['file_obj'].seek(0)
        st.download_button(
            label="⬇️ TẢI FILE NÀY VỀ",
            data=current_item['file_obj'],
            file_name=meta['new_name'],
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

    # --- KHU VỰC TẢI TẤT CẢ (ZIP) ---
    st.markdown("---")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip
