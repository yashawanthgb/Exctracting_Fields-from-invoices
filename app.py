import streamlit as st
import pandas as pd
import os
import tempfile
from extract_invoices import process_invoices

def main():
    st.title("Invoice Extraction App")
    st.write("Upload one or more PDF invoices, extract data, and download as CSV or JSON.")

    uploaded_files = st.file_uploader("Upload PDF invoices", type=["pdf"], accept_multiple_files=True)
    extract_btn = st.button("Extract Data")

    if extract_btn and uploaded_files:
        # Save uploaded PDFs to temp files
        temp_dir = tempfile.mkdtemp()
        pdf_paths = []
        for uploaded in uploaded_files:
            path = os.path.join(temp_dir, uploaded.name)
            with open(path, "wb") as f:
                f.write(uploaded.read())
            pdf_paths.append(path)

        csv_out = os.path.join(temp_dir, "results.csv")
        json_out = os.path.join(temp_dir, "results.json")
        process_invoices(pdf_paths, csv_out, json_out)

        # Show table preview
        df = pd.read_csv(csv_out)
        st.success(f"Extraction complete! {len(df)} rows extracted.")
        st.dataframe(df)
        # Download buttons
        with open(csv_out, "rb") as f:
            st.download_button("Download CSV", f, file_name="extracted_invoices.csv")
        with open(json_out, "rb") as f:
            st.download_button("Download JSON", f, file_name="extracted_invoices.json")

if __name__ == "__main__":
    main()
