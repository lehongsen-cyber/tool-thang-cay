import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import time
import zipfile
import base64

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Magic Renamer - Thắng Cầy",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed" # Ẩn sidebar cho rộng chỗ giống App
)

# --- 2. CSS "MAKEUP" CHO GIAO DIỆN (MAGIC UI) ---
st.markdown("""
<style>
    /* Import Font hiện đại */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f3f4f6; /* Màu nền xám nhạt sang trọng */
    }

    /* HEADER */
    .magic-header {
        background: linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(37, 117, 252, 0.3);
    }
    .magic-title {
        font-size: 2.5em;
        font-weight: 800;
        margin: 0;
    }
    .magic-subtitle {
        font-size: 1.1em;
        opacity: 0.9;
        margin-top: 5px;
    }

    /* CARD FILE (Khung chứa từng file) */
    .file-card {
        background-color: white;
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
    }

    /* PREVIEW IMAGE (Ảnh PDF) */
    .pdf-preview {
        border-radius: 10px;
        border: 1px solid #ddd;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        width: 100%;
        object-fit: cover;
    }

    /* INFO BOXES (Các ô thông tin nhỏ) */
    .info-label {
        font-size: 0.8em;
        text-transform: uppercase;
        color: #6b7280;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .info-value {
        font-size: 1.1em;
        color: #111827;
        font-weight: 600;
        word-wrap: break-word;
    }
    .meta-box {
        background-color: #f9fafb;
        padding: 10px;
        border-radius: 8px;
        margin-top: 10px;
    }

    /* RESULT BOX (Khung kết quả màu tối) */
    .result-box {
        background-color: #1e1b4b; /* Màu chàm tối */
        color: #e0e7ff;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border-left: 5px solid #818cf8;
    }
    .new-name-text {
        font-size: 1.2em;
        font-weight: 700;
        color: white;
        word-break: break-all;
    }

    /* BUTTONS */
    .stButton>button {
        border-radius: 50px;
        font-weight: bold;
        padding: 0.5rem 2rem;
        transition: all 0.3s ease;
    }
    /* Nút chính (Úm ba la) */
    .primary-btn button {
        background: linear-gradient(45deg, #8b5cf6, #d946ef);
        color: white;
        border: none;
        height: 3.5em;
        font-size: 1.2em;
        width: 100%;
    }
    .primary-btn button:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 20px rgba(139, 92, 246, 0.3);
    }
    
    /* FOOTER */
    .footer-credits {
        text-align: center;
        margin-top: 50px;
        font-size: 1.2em;
        color: #9ca3af;
    }
    .author-name {
        background: -webkit-linear-gradient(45deg, #FF512F, #DD2476);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 1.5em;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. HEADER MAGIC ---
st.markdown("""
<div class="magic-header">
    <div class="magic-title">✨ Magic Renamer</div>
    <div class="magic-subtitle">Công cụ thần kỳ hệ thống hóa văn bản pháp lý - Dành riêng cho Thắng cầy</div>
</div>
""", unsafe_allow_html=True)

# --- 4. LOGIC XỬ LÝ (BACKEND) ---
def get_best_model(api_key):
    genai.configure(api_key=api_key)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                return m.name
    except:
        return None
    return "models/gemini-1.5-flash"

def pdf_page_to_image(uploaded_file):
    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0) 
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        return img_data
    except Exception:
        return None

def process_file(uploaded_file, api_key, model_name):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        uploaded_file.seek(0)
        img_data = pdf_page_to_image(uploaded_file)
        if img_data is None: return None, "Lỗi đọc file", None

        # Chuyển ảnh sang base64 để hiển thị lên giao diện
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        image_part = {"mime_type": "image/png", "data": img_data}
        
        # PROMPT CHUẨN YYYY.MM.DD
        prompt = """
        Trích xuất thông tin đặt tên file PDF theo quy tắc sau.
        Cấu trúc: YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
        
        Quy tắc:
        - YYYY.MM.DD: Năm.Tháng.Ngày (Ví dụ: 2025.12.31). Dùng dấu CHẤM.
        - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
        - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
        - NoiDung: Tiếng Việt không dấu, nối bằng gạch dưới (_).
        - TrangThai: Mặc định 'Signed'.
        
        Chỉ trả về tên file.
        """
        
        # Retry Logic
        for attempt in range(3):
            try:
                result = model.generate_content([prompt, image_part])
                new_name = result.text.strip().replace("`", "")
                if not new_name.lower().endswith(".pdf"): new_name += ".pdf"
                return new_name, None, img_base64
            except Exception as e:
                time.sleep(2)
                continue
        
        return None, "Server bận", img_base64
        
    except Exception as e:
        return None, str(e), None

# --- 5. GIAO DIỆN CHÍNH (LAYOUT 3 CỘT) ---

# Khu vực nhập Key và Upload (Gọn gàng)
with st.container():
    col_key, col_up = st.columns([1, 2])
    with col_key:
        api_key = st.text_input("🔑 Nhập API Key:", type="password", placeholder="Dán key vào đây...")
    with col_up:
        uploaded_files = st.file_uploader("📂 Chọn hồ sơ cần đổi tên (PDF)", type=['pdf'], accept_multiple_files=True)

# Nút Action to đùng
if uploaded_files:
    st.write("")
    col_btn_1, col_btn_2, col_btn_3 = st.columns([1, 2, 1])
    with col_btn_2:
        # Hack CSS để class primary-btn tác động vào nút này
        st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
        run_btn = st.button("⚡ ÚM BA LA ĐỔI TÊN ⚡")
        st.markdown('</div>', unsafe_allow_html=True)

    if run_btn:
        if not api_key:
            st.warning("⚠️ Chưa có chìa khóa (API Key) thì sao mở cửa thần kỳ được!")
        else:
            active_model = get_best_model(api_key)
            if not active_model:
                st.error("❌ Chìa khóa bị gãy rồi (Key lỗi).")
                st.stop()
            
            # Khởi tạo thanh tiến trình
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_files = [] # Để dành nén ZIP

            st.write("---")
            
            # VÒNG LẶP XỬ LÝ TỪNG FILE VÀ HIỆN CARD
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"⏳ Đang phù phép: {uploaded_file.name}...")
                
                # Gọi hàm xử lý
                new_name, error, img_base64 = process_file(uploaded_file, api_key, active_model)
                
                # --- RENDER GIAO DIỆN CARD ---
                with st.container():
                    # Mở thẻ Card HTML
                    st.markdown('<div class="file-card">', unsafe_allow_html=True)
                    
                    # Chia layout card thành 3 cột: Ảnh | Thông tin Gốc | Kết quả
                    c1, c2, c3 = st.columns([1, 1.5, 2])
                    
                    # Cột 1: Ảnh Preview
                    with c1:
                        if img_base64:
                            st.markdown(f'<img src="data:image/png;base64,{img_base64}" class="pdf-preview">', unsafe_allow_html=True)
                        else:
                            st.image("https://cdn-icons-png.flaticon.com/512/337/337946.png", width=100)
                    
                    # Cột 2: Thông tin gốc
                    with c2:
                        st.markdown(f"""
                        <div class="info-label">TÊN FILE GỐC</div>
                        <div class="info-value" style="color: #6b7280;">{uploaded_file.name}</div>
                        <div class="meta-box">
                            <div class="info-label">KÍCH THƯỚC</div>
                            <div class="info-value">{round(uploaded_file.size/1024, 1)} KB</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Cột 3: Kết quả AI
                    with c3:
                        if error:
                            st.error(f"Lỗi: {error}")
                        else:
                            # Tách lấy ngày tháng để hiển thị cho đẹp (nếu format đúng)
                            try:
                                date_part = new_name.split('_')[0]
                            except:
                                date_part = "..."

                            st.markdown(f"""
                            <div class="info-label" style="color: #818cf8;">TÊN FILE ĐƯỢC AI ĐỀ XUẤT</div>
                            <div class="result-box">
                                <div class="new-name-text">📄 {new_name}</div>
                            </div>
                            <div style="display: flex; gap: 10px;">
                                <div class="meta-box" style="flex: 1;">
                                    <div class="info-label">NGÀY BAN HÀNH</div>
                                    <div class="info-value">{date_part}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.write("")
                            # Lưu vào list để tạo ZIP
                            uploaded_file.seek(0)
                            success_files.append((new_name, uploaded_file.read()))
                            
                            # Nút tải lẻ
                            st.download_button(
                                label="⬇️ Tải file này",
                                data=success_files[-1][1],
                                file_name=new_name,
                                mime='application/pdf',
                                key=f"btn_{i}"
                            )
                    
                    st.markdown('</div>', unsafe_allow_html=True) # Đóng thẻ Card

                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.empty()
            
            # --- KHU VỰC TẢI ZIP (CUỐI CÙNG) ---
            if success_files:
                st.balloons()
                st.markdown("""
                <div style="text-align: center; margin-top: 20px;">
                    <h3 style="color: #4b5563;">🎉 Đã đổi tên xong tất cả!</h3>
                </div>
                """, unsafe_allow_html=True)
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for name, data in success_files:
                        zf.writestr(name, data)
                
                c_zip_1, c_zip_2, c_zip_3 = st.columns([1, 2, 1])
                with c_zip_2:
                     st.download_button(
                        label="📦 TẢI TRỌN BỘ (ZIP) - KHÔNG RELOAD",
                        data=zip_buffer.getvalue(),
                        file_name="Magic_Renamed_Files.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True
                    )

# --- 6. FOOTER (TÁC GIẢ) ---
st.markdown("""
<div class="footer-credits">
    Created with ❤️ by <span class="author-name">Lê Hồng Sến</span>
</div>
""", unsafe_allow_html=True)
