import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ==========================================
# 📌 CORE LOGIC (NO CHANGES TO ALGORITHMS)
# ==========================================

def extract_pdf(file_stream):
    with pdfplumber.open(file_stream) as pdf:
        text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])

    def find(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    repayment_raw = find(r"Repayment Structure[:\s]*([^\n]+)")
    if not repayment_raw or "bullet" not in repayment_raw.lower():
        if "bullet" in text.lower():
            repayment_raw = "Bullet repayment"

    return {
        "loan_code": find(r"Loan Code[:\s]+([A-Z0-9\-]+)"),
        "issuer_id": find(r"Issuer ID[:\s]+(\d+)"),
        "payment_behaviour": find(r"Payment Behaviour[:\s]+([A-Z]+)"),
        "historical_records": find(r"(?:Historical Records|Past Records)[:\s]+([A-Z]+)"),
        "black_list": find(r"Black/?Negative List[:\s]+([A-Z]+)"),
        "sme_credit_score": find(r"SME Credit Score[:\s]+(\d+)"),
        "No of Guarantor": find(r"No of Guarantor[:\s]+(\d+)"),
        "vehicle_model": find(r"Vehicle Model[:\s]+(.+)"),
        "Year of Manufacture": find(r"Year of Manufacture[:\s]+(\d{4})"),
        "financing_margin": find(r"Financing Margin[\s\S]*?(\d+\.?\d*)"),
        "business_location": find(r"Business Location[:\s]+([A-Z]+)"),
        "entity_type": find(r"Entity Type[:\s]+(.+)"),
        "update as at": find(r"(?:Updated As At|As At|Date Updated)[\s\S]*?(\d{1,2}\s+[A-Z]+\s+\d{4})"),
        "incorporation_date": find(r"Incorporation Date[:\s]+([^\n\r]+)"),
        "paid_up_capital": find(r"Paid Up Capital[\s\S]*?([\d,\.]+|NIL)"),
        "total_moltf_facility_limit": find(r"Total MOLTF Facility[\u200B\s\S]*?([\d,\.]+\s?)?[\u200B\d,\.]+[\s\S]*?Limit"),
        "onboarded_fs_since": find(r"Onboarded with FS[\u200B\s\S]*?(\d{1,2}\s+[A-Z]+\s+\d{4})"),
        "payment_behaviour_remark": find(r"Payment Behaviour[\s\S]*?Remark[\s\S]*?([A-Z]+|NIL)"),
        "litigation": find(r"Litigation[:\s]+([A-Z]+)"),
        "security": find(r"Security[:\s]+([A-Z]+)"),
        "other_security": find(r"Other Security[:\s]+(.+)"),
        "tenure": find(r"Tenure[\s\S]*?Up to (\d+)"),
        "repayment_structure": repayment_raw
    }

def get_val(row, keys):
    for k in keys:
        for col in row.index:
            if col.lower().replace(' ', '_') == k.lower().replace(' ', '_'):
                return row[col]
    return None

def analyze_investment(row):
    payment_behavior = str(get_val(row, ['payment_behaviour', 'Payment Behaviour']) or '').strip().upper()
    black_list = str(get_val(row, ['black_list', 'Black / Negative List']) or '').strip().upper()
    sme_score = pd.to_numeric(get_val(row, ['sme_credit_score', 'SME Credit Score']), errors='coerce') or 0
    no_guarantor = pd.to_numeric(get_val(row, ['no_of_guarantor', 'No of Guarantor']), errors='coerce') or 0
    layer_a_pass = (payment_behavior == 'PROMPT' and black_list == 'NIL' and sme_score >= 320.9 and no_guarantor >= 1)
    if not layer_a_pass: return "REJECT", None
    vehicle_model = str(get_val(row, ['vehicle_model', 'Vehicle Model']) or '').strip()
    yom_val = get_val(row, ['year_of_manufacture', 'Year of Manufacture', 'Year'])
    yom = pd.to_numeric(yom_val, errors='coerce')
    yom_str = str(yom_val).strip() if yom_val else 'N/A'
    topup = 0
    if any(m.lower() in vehicle_model.lower() for m in ['Perodua Alza', 'Perodua Myvi', 'Toyota Hilux']): topup = 200
    total_inv = 100 + topup
    loan_code = get_val(row, ['loan_code', 'Loan Code'])
    issuer_id = str(get_val(row, ['issuer_id', 'Issuer ID']))
    project_info = {'issuer_id': issuer_id, 'loan_code': loan_code, 'vehicle': vehicle_model, 'yom': yom_str}
    report = f'Loan Code: {loan_code}\nDecision: INVEST\nTotal: RM{total_inv}'
    return "INVEST", report, project_info

# ==========================================
# 📌 STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Analyzer", layout="wide")
st.title("🚀 MBDF Investment Risk Control")

if 'pdf_data' not in st.session_state: st.session_state.pdf_data = None
if 'passed_db' not in st.session_state: st.session_state.passed_db = []

st.header("1. Factsheet Extraction")
pdf_files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True)
if st.button("Process PDFs"):
    if pdf_files:
        results = [extract_pdf(f) for f in pdf_files]
        st.session_state.pdf_data = pd.DataFrame(results)
        st.success("Extracted!")
        st.dataframe(st.session_state.pdf_data)

st.header("2. Portfolio Verification")
port_file = st.file_uploader("Upload Portfolio CSV", type="csv")
if port_file and st.session_state.pdf_data is not None:
    p_df = pd.read_csv(port_file)
    st.write("Verification Ready.")
    st.download_button("Download Report", "Report Content...", file_name="report.txt")
