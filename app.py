import streamlit as st
import pandas as pd
import os
import tempfile
from extract_invoices import process_invoices

def main():
    st.title("Invoice Extraction Website")
    st.write("Upload PDF invoices or images (JPG, PNG) to extract data. Download results as CSV or JSON.")

    # File uploader for both PDF and image files
    uploaded_files = st.file_uploader(
        "Upload invoices (PDF, JPG, PNG)",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
    
    extract_btn = st.button("Extract Data")

    if extract_btn and uploaded_files:
        # Save uploaded files to temp files
        temp_dir = tempfile.mkdtemp()
        input_paths = []
        
        for uploaded in uploaded_files:
            path = os.path.join(temp_dir, uploaded.name)
            with open(path, "wb") as f:
                f.write(uploaded.read())
            input_paths.append(path)

        csv_out = os.path.join(temp_dir, "results.csv")
        json_out = os.path.join(temp_dir, "results.json")
        
        with st.spinner("Processing files..."):
            process_invoices(input_paths, csv_out, json_out)

            # Show table preview
            df = pd.read_csv(csv_out)
            st.success(f"Extraction complete! {len(df)} rows extracted.")
            
            # Display preview with all columns
            st.dataframe(df)
            
            # Download buttons
            with open(csv_out, "rb") as f:
                st.download_button(
                    "Download CSV",
                    f,
                    file_name="extracted_invoices.csv",
                    mime="text/csv"
                )
            with open(json_out, "rb") as f:
                st.download_button(
                    "Download JSON",
                    f,
                    file_name="extracted_invoices.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main()
