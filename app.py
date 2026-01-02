import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import time
import os
import zipfile

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(
    page_title="Tool Thắng Cầy",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    h1 {color: #D35400; font-family: 'Segoe UI', sans-serif;} 
    
    .result-card {
        background-color: #fff8e1; 
        padding: 20px; 
        border-radius: 10px;
        border-left: 5px solid #ffa000; 
        margin-bottom: 15px;
        color: #4e342e !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .stButton>button {width: 100%; border-radius: 8px; height: 3em; font-weight: bold;}
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- LOGIC XỬ LÝ ---
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

def process_custom_rule(uploaded_file, api_key, model_name, status_container):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        uploaded_file.seek(0)
        img_data = pdf_page_to_image(uploaded_file)
        if img_data is None: return "ERROR", "Lỗi đọc file."

        image_part = {"mime_type": "image/png", "data": img_data}
        
        # --- QUY TẮC CHUẨN THEO FILE TXT (YYYY.MM.DD) ---
        prompt = """
        Trích xuất thông tin đặt tên file PDF theo đúng quy tắc sau:
        
        1. CẤU TRÚC CHUẨN: 
           YYYY.MM.DD_LOAI_SoHieu_NoiDung_TrangThai.pdf
        
        2. GIẢI THÍCH CHI TIẾT:
           - YYYY.MM.DD: Năm.Tháng.Ngày (Năm đủ 4 số, dùng dấu chấm). 
             Ví dụ chuẩn: 2025.08.15
           - LOAI: Viết tắt (QD, TTr, CV, TB, GP, HD, BB, BC...).
           - SoHieu: Số hiệu (Ví dụ 125-UBND, thay / bằng -).
           - NoiDung: Tiếng Việt không dấu, nối bằng gạch dưới (_).
           - TrangThai: Mặc định là 'Signed' (nếu đã ký).
        
        3. VÍ DỤ MẪU:
           Input: Quyết định số 125/UBND ký ngày 15/08/2025.
           Output: 2025.08.15_QD_125-UBND_Giao_dat_Dot1_Signed.pdf
        
        Chỉ trả về tên file duy nhất.
        """
        
        max_retries = 5
        wait_time = 65
        
        for attempt in range(max_retries):
            try:
                result = model.generate_content([prompt, image_part])
                new_name = result.text.strip().replace("`", "")
                if not new_name.lower().endswith(".pdf"): new_name += ".pdf"
                return new_name, None
                
            except Exception as e:
                if "429" in str(e) or "Quota" in str(e) or "400" in str(e):
                    if attempt < max_retries - 1:
                        with status_container:
                            for s in range(wait_time, 0, -1):
                                st.warning(f"⏳ Google đang bận. Chờ {s}s... (Lần {attempt+1})")
                                time.sleep(1)
                            st.info("🔄 Đang thử lại...")
                            continue
                    else:
                        return None, "Google quá tải."
                else:
                    return None, str(e)
                    
    except Exception as e:
        return None, str(e)

# --- GIAO DIỆN NGƯỜI DÙNG ---
with st.sidebar:
    st.title("⚙️ CẤU HÌNH")
    st.markdown("---")
    with st.expander("🔑 Google API Key", expanded=True):
        api_key = st.text_input("Nhập Key:", type="password")
    
    st.info("ℹ️ Quy tắc: `YYYY.MM.DD`\n\nVD: `2025.08.15_QD...`")
    st.markdown("---")
    
    # --- ĐÓNG DẤU BẢN QUYỀN ---
    st.markdown("""
    <div style="text-align: center; margin-top: 20px; color: #555;">
        <b>Created by Lê Hồng Sến</b>
    </div>
    """, unsafe_allow_html=True)

# --- PHẦN CHÍNH ---
st.title("🛠️ Tool đổi tên file pdf - Thắng cầy")
st.markdown("##### 🚀 Quy chuẩn: `YYYY.MM.DD_LOAI_SoHieu_NoiDung_Signed.pdf`")

uploaded_files = st.file_uploader("", type=['pdf'], accept_multiple_files=True)

if uploaded_files:
    if st.button("✨ BẮT ĐẦU XỬ LÝ ✨", type="primary"):
        if not api_key:
            st.toast("⚠️ Nhập API Key trước đã bạn ơi!", icon="⚠️")
        else:
            active_model = get_best_model(api_key)
            if not active_model:
                st.error("❌ Key không hợp lệ!")
                st.stop()
            
            st.success(f"✅ Đã kết nối AI. Đang xử lý cho Thắng cầy...")
            progress_bar = st.progress(0)
            
            success_files = []
            
            for i, uploaded_file in enumerate(uploaded_files):
                with st.container():
                    status_box = st.empty()
                    new_name, error_msg = process_custom_rule(uploaded_file, api_key, active_model, status_box)
                    
                    if error_msg:
                        st.error(f"❌ {uploaded_file.name}: {error_msg}")
                    else:
                        status_box.empty()
                        # Lưu file để nén ZIP
                        uploaded_file.seek(0)
                        file_data = uploaded_file.read()
                        success_files.append((new_name, file_data))
                        
                        # Hiện kết quả
                        col_info, col_dl = st.columns([3, 1])
                        with col_info:
                            st.markdown(f"""
                            <div class="result-card">
                                <b>📄 Gốc:</b> {uploaded_file.name}<br>
                                <b style="color: #d84315;">✅ Mới:</b> {new_name}
                            </div>
                            """, unsafe_allow_html=True)
                        with col_dl:
                            st.write("")
                            st.download_button(
                                label="⬇️ Tải lẻ",
                                data=file_data,
                                file_name=new_name,
                                mime='application/pdf',
                                key=f"dl_{i}",
                                use_container_width=True
                            )
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            # --- NÚT TẢI ZIP ---
            if success_files:
                st.markdown("---")
                st.success("🎉 Xong hàng! Tải về tại đây:")
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for name, data in success_files:
                        zf.writestr(name, data)
                
                st.download_button(
                    label="📦 TẢI TRỌN BỘ (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="File_da_doi_ten_ThangCay.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )
