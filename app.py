import streamlit as st
import os
import google.generativeai as genai
import pandas as pd
import requests
from dotenv import load_dotenv
from fpdf import FPDF
from duckduckgo_search import DDGS
from datetime import date, datetime
from PIL import Image
from pypdf import PdfReader

# Load environment variables
load_dotenv()

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Super Agent - Listings", layout="wide", page_icon="🏢")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
        @media print {
            [data-testid="stSidebar"] {display: none;}
            .stChatInput {display: none;}
            .stMarkdown {font-size: 12pt;}
        }
        .reportview-container .main .block-container{
            padding-top: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- API KEY CONFIGURATION ---
api_key = os.environ.get("GOOGLE_API_KEY")
maps_key = os.environ.get("MAPS_API_KEY") 

if not api_key:
    st.error("⚠️ GOOGLE_API_KEY missing in environment variables.")
    st.stop()

genai.configure(api_key=api_key)

# ==========================================
#        BACKEND HELPER FUNCTIONS
# ==========================================

def load_knowledge_base():
    knowledge_text = ""
    if os.path.exists("knowledge"):
        for filename in os.listdir("knowledge"):
            if filename.endswith(".txt") or filename.endswith(".md"):
                try:
                    with open(os.path.join("knowledge", filename), "r", encoding="utf-8") as f:
                        knowledge_text += f"\n--- INFO FROM {filename} ---\n"
                        knowledge_text += f.read()
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    return knowledge_text

def search_web_general(query, max_results=4):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, backend='api'))
            formatted_results = ""
            if results:
                for r in results:
                    formatted_results += f"- {r['title']}: {r['body']} (Link: {r['href']})\n"
            return formatted_results if formatted_results else "No relevant data found."
    except Exception as e:
        return f"Search error: {str(e)}"

def get_street_view_image(address, key):
    if not key: return None
    base_url = "https://maps.googleapis.com/maps/api/streetview"
    params = {'size': '600x400', 'location': address, 'key': key}
    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            file_path = "temp_house.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
    except: return None
    return None

def get_web_estimates(address):
    return search_web_general(f"{address} price estimate zillow redfin", max_results=4)

def calculate_metrics(df, months=6, address_query=""):
    try:
        df.columns = [c.lower().strip() for c in df.columns]
        status_col = next((c for c in df.columns if 'status' in c), None)
        price_col = next((c for c in df.columns if 'list' in c and 'price' in c), None)
        num_col = next((c for c in df.columns if 'street' in c and 'number' in c), None)
        name_col = next((c for c in df.columns if 'street' in c and 'name' in c), None)
        
        subject_price_found = "N/A"
        if address_query and num_col and name_col and price_col:
            df['temp_addr'] = df[num_col].astype(str) + " " + df[name_col].astype(str)
            query_simple = " ".join(address_query.split()[:2])
            match = df[df['temp_addr'].str.contains(query_simple, case=False, na=False)]
            if not match.empty:
                subject_price_found = str(match.iloc[0][price_col])

        if not status_col: return {"error": "No 'Status' column found in CSV"}

        status = df[status_col].astype(str)
        sold = df[status.str.contains('sold|closed', case=False, na=False)].shape[0]
        active = df[status.str.contains('active', case=False, na=False)].shape[0]
        failed = df[status.str.contains('exp|with|canc', case=False, na=False)].shape[0]
        
        total_attempts = sold + failed
        success_ratio = (sold / total_attempts * 100) if total_attempts > 0 else 0
        ar = sold / months
        moi = (active / ar) if ar > 0 else 99
        avg_price = df[status.str.contains('sold|closed', case=False, na=False)][price_col].astype(str).str.replace(r'[$,]', '', regex=True).pipe(pd.to_numeric, errors='coerce').mean() if price_col else 0

        return {
            "months_inventory": round(moi, 2),
            "absorption_rate": round(ar, 2),
            "success_ratio": round(success_ratio, 1),
            "subject_price_found": subject_price_found,
            "avg_sold_price": f"${avg_price:,.0f}" if avg_price > 0 else "N/A"
        }
    except Exception as e: return {"error": str(e)}

# --- PDF REPORTING ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'CONFIDENTIAL ANALYSIS | Powered by Agent Coach AI', 0, 1, 'R')
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Powered by Agent Coach AI | Generated: {date.today()}', 0, 0, 'C')

def create_rick_pdf(content, agent_name, address, metrics, web_summary, ai_price, image_path):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 26)
    pdf.ln(10)
    pdf.cell(0, 15, "STRATEGIC GAME PLAN", 0, 1, 'C')
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, f"PROPERTY: {address}", 0, 1, 'C')
    if image_path:
        try:
            pdf.image(image_path, x=25, y=55, w=160)
            pdf.ln(115)
        except: pdf.ln(30)
    else: pdf.ln(30)
    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, f"Prepared by: {agent_name}", 0, 1, 'C')
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_fill_color(33, 47, 61)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "  1. Market Diagnostics", 0, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    pdf.set_font('Arial', '', 11)
    if "error" not in metrics:
        pdf.cell(0, 10, f"MOI: {metrics.get('months_inventory', 'N/A')} | Success Ratio: {metrics.get('success_ratio', 'N/A')}%", 0, 1)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_fill_color(33, 47, 61)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "  2. Analysis & Strategy", 0, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    pdf.set_font('Arial', '', 11)
    lines = content.split('\n')
    for line in lines:
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, clean_line.replace('*', ''))
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
#           FRONTEND INTERFACE
# ==========================================

st.sidebar.title("🏢 Listings Department")
st.sidebar.markdown("---")
selected_agent = st.sidebar.radio("Select Agent:", ["Rick", "Sherlock", "Ava"])
st.sidebar.markdown("---")
st.sidebar.info("System Status: Online")

st.title(f"Active Agent: {selected_agent}")

# ==========================================
#           AGENT LOGIC
# ==========================================

if selected_agent == "Rick":
    st.markdown("### 🏘️ The Property Analyzer")
    st.info("Upload your MLS (CSV) file to generate a winning strategic plan. Fill in the spaces below to make the magic happen.")
    col1, col2 = st.columns([1, 2])
    with col1:
        uploaded_file = st.file_uploader("1. Upload MLS CSV", type=["csv"])
        months_analyzed = st.number_input("Months to Analyze", value=6)
        agent_name = st.text_input("Agent Name", value="Fernando Herboso")
    with col2:
        address = st.text_input("2. Property Address", placeholder="Ex: 123 Main St...")
        if st.button("🚀 Run Strategic Analysis"):
            if not address or not uploaded_file:
                st.error("Please enter the address and upload the CSV file.")
            else:
                final_img = None
                if maps_key:
                    with st.spinner('📸 Fetching satellite image...'):
                        final_img = get_street_view_image(address, maps_key)
                df = pd.read_csv(uploaded_file)
                metrics = calculate_metrics(df, months_analyzed, address)
                if "error" in metrics:
                    st.error(f"CSV Error: {metrics['error']}")
                else:
                    with st.spinner('🌍 Analyzing online market...'):
                        web_data = get_web_estimates(address)
                    prompt = f"""
                    YOU ARE: The Listing Powerhouse AI. 
                    ROLE: Senior Strategic Analyst for {agent_name}.
                    MISSION: Win the listing using authoritative, analytical data. 
                    TONE: Executive, Authoritative, Proactive. NO JOKES.
                    TARGET: {address}
                    === DATA INTELLIGENCE ===
                    - ANCHOR PRICE: {metrics['subject_price_found']}
                    - MOI: {metrics['months_inventory']}
                    - Success Ratio: {metrics['success_ratio']}%
                    - FAILURE RATE: {100 - metrics['success_ratio']:.1f}%
                    === WEB INTEL ===
                    {web_data}
                    === INSTRUCTIONS ===
                    1. STRATEGIC PRICE: Propose a strategy based on the data.
                    2. AVM SHIELD: Compare with online estimates.
                    3. PREDICTIVE SCENARIOS: Create 3 scenarios (Stable, Rates Drop, Rates Spike).
                    """
                    with st.spinner('🧠 Generating Strategy...'):
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        response = model.generate_content(prompt)
                        report_text = response.text
                        st.markdown("---")
                        if final_img:
                            st.image(final_img, caption="Property View", width=400)
                        st.markdown(report_text)
                        ai_price = metrics['subject_price_found']
                        pdf_bytes = create_rick_pdf(report_text, agent_name, address, metrics, str(web_data)[:300], ai_price, final_img)
                        st.download_button("📥 Download Plan (PDF)", pdf_bytes, f"Strategy_{address}.pdf", "application/pdf")

elif selected_agent == "Sherlock":
    st.markdown("### 🕵️‍♂️ Sherlock: The Ultimate Real Estate Analyst")
    st.caption("I'm Sherlock, the best real estate analyst. I provide actionable cost estimates, identify red flags, and generate negotiation scripts for real estate agents. Please upload your photo for analysis, tell me what I should analyze, and in the spaces below, indicate the city where the property is located.")
    knowledge_base = load_knowledge_base()
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_img = st.file_uploader("📸 Upload a photo", type=["jpg", "jpeg", "png"])
        location = st.text_input("📍 Location (City/Zip Code)", placeholder="Ex: Bethesda, MD 20814")
    with col2:
        user_question = st.text_area("❓ What should I analyze?", placeholder="Ex: Red flags?", height=130)
    if st.button("🔍 Analyze with Sherlock Lens"):
        if not location:
            st.warning("⚠️ Sherlock needs the location to calculate local labor costs.")
        else:
            with st.spinner("Sherlock is inspecting..."):
                sherlock_system_prompt = f"""
                You are Sherlock — The Ultimate Real Estate Analyst. 
                Roles: General Contractor, Home Inspector, Valuation Expert.
                Objective: "See what others miss". Provide actionable cost estimates, red flags, and scripts.
                GLOBAL SETTINGS:
                - Location Provided: {location}
                - Tone: Direct, professional, data-driven. NO FLUFF.
                MANDATORY OUTPUT FORMAT:
                **📍 LOCATION & CONTEXT**
                **🛠️ THE ANALYSIS (Visual Observations)**
                **💵 THE NUMBERS (Est. Cost Range)**
                **🗣️ STRATEGIC SCRIPTS (Buyer & Seller versions)**
                🛡️ BROKERAGE DISCLAIMER
                EXTERNAL KNOWLEDGE BASE:
                {knowledge_base}
                """
                model = genai.GenerativeModel('gemini-2.0-flash')
                content_payload = [sherlock_system_prompt, f"USER QUESTION: {user_question}"]
                if uploaded_img:
                    img = Image.open(uploaded_img)
                    content_payload.append(img)
                response = model.generate_content(content_payload)
                st.markdown("---")
                st.markdown(response.text)

elif selected_agent == "Ava":
    st.markdown("### ✍️ Ava: Senior Real Estate Copywriter")
    st.caption("I am Ava, a senior real-estate copywriter I write persuasive, cinematic, and Fair-Housing-compliant property descriptions. Fill in the spaces below to make the magic happen.")
    with st.form("ava_form"):
        col1, col2 = st.columns(2)
        with col1:
            ava_address = st.text_input("📍 Property Address")
            ava_specs = st.text_input("🛏️ Specs (Beds, Baths, SqFt)")
            ava_style = st.text_input("🏠 Home Style")
        with col2:
            ava_features = st.text_area("✨ Key Features", height=100)
            ava_neighborhood = st.text_area("🌳 Neighborhood Highlights", height=100)
        submit_ava = st.form_submit_button("✨ Write Magic Description")

    if submit_ava:
        with st.spinner("Ava is drafting..."):
            ava_prompt = f"""
            You are **Ava**, a senior real-estate copywriter created by **AgentCoachAI**. 
            Objective: Turn raw details into market-ready stories.
            PROPERTY: {ava_address} | {ava_specs} | {ava_style} | {ava_features} | {ava_neighborhood}
            Produce THREE unique versions: Cinematic, Professional, and Short Summary.
            FAIR HOUSING COMPLIANT. End with: "Description generated by Ava — AgentCoachAI."
            """
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(ava_prompt)
            st.markdown("---")
            st.markdown(response.text)
            st.code(response.text)



