import os
import re
import csv
import json
import pytesseract
import pdfplumber
import google.generativeai as genai
from pdf2image import convert_from_path
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in your environment variables")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')


# Check if PDF is digital (has extractable text)
def is_digital_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return True
    except:
        pass
    return False

# Extract text from digital PDF
def extract_text_digital(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        return text.strip()
    except Exception as e:
        print(f"Error extracting digital PDF: {e}")
        return ""

# Extract text from scanned PDF using OCR
def extract_text_scanned(pdf_path):
    try:
        images = convert_from_path(pdf_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Error with OCR: {e}")
        return ""

def clean_text(text):
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    # Remove common OCR artifacts
    text = re.sub(r'[^\w\s.,/-]', ' ', text)
    return text.strip()

def extract_fields_with_gemini(text):
    prompt = f"""
    Extract the following fields from this invoice text. Return only a JSON object with these fields:
    - invoice_number
    - date (invoice date, in YYYY-MM-DD or DD-MM-YYYY format)
    - due_date (if available)
    - vendor_name
    - vendor_address (if available)
    - invoice_total (numeric value only)
    - items: a list of objects, each with:
        - description
        - quantity
        - unit_price
        - total

    If any field is not found, return an empty string for that field. For items, return an empty list if not found.

    Invoice Text:
    {text}

    Return ONLY the JSON object, nothing else. Example format:
    {{
        "invoice_number": "INV-12345",
        "date": "15-05-2023",
        "due_date": "20-05-2023",
        "vendor_name": "ABC Corporation",
        "vendor_address": "123 Main St, City, Country",
        "invoice_total": "1250.50",
        "items": [
            {{
                "description": "Widget A",
                "quantity": "2",
                "unit_price": "500.00",
                "total": "1000.00"
            }},
            {{
                "description": "Widget B",
                "quantity": "1",
                "unit_price": "250.50",
                "total": "250.50"
            }}
        ]
    }}
    """
    try:
        response = model.generate_content(prompt)
        json_str = response.text.strip()
        if json_str.startswith('```json'):
            json_str = json_str[7:-3]
        elif json_str.startswith('```'):
            json_str = json_str[3:-3]
        fields = json.loads(json_str)
        return fields
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return extract_fields_with_patterns(text)

def extract_fields_with_patterns(text):
    """Fallback pattern matching extraction for all required fields and items."""
    text = clean_text(text)
    lines = text.split('\n')
    fields = {
        "invoice_number": "",
        "date": "",
        "due_date": "",
        "vendor_name": "",
        "vendor_address": "",
        "invoice_total": "",
        "items": []
    }
    # You can add regex extraction here for each field as needed
    # For now, return mostly empty fields for fallback
    return fields

# Main processor
def process_invoices(pdf_files, csv_out, json_out):
    results = []
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file}")
        is_digital = is_digital_pdf(pdf_file)
        text = extract_text_digital(pdf_file) if is_digital else extract_text_scanned(pdf_file)
        extracted_fields = extract_fields_with_gemini(text)
        source_pdf = os.path.basename(pdf_file)
        # Flatten line items for CSV: one row per item, with invoice-level fields repeated
        items = extracted_fields.get("items", [])
        if not items:
            items = [{}]  # At least one row per invoice
        for item in items:
            row = {
                'Invoice Number': extracted_fields.get('invoice_number', ''),
                'Date': extracted_fields.get('date', ''),
                'Due Date': extracted_fields.get('due_date', ''),
                'Vendor Name': extracted_fields.get('vendor_name', ''),
                'Vendor Address': extracted_fields.get('vendor_address', ''),
                'Item Description': item.get('description', ''),
                'Quantity': item.get('quantity', ''),
                'Unit Price': item.get('unit_price', ''),
                'Item Total': item.get('total', ''),
                'Invoice Total': extracted_fields.get('invoice_total', ''),
                'Source PDF': source_pdf
            }
            results.append(row)
        # Save extracted text to .txt for reference
        with open(os.path.splitext(pdf_file)[0] + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(csv_out, index=False)
    print(f"\nSaved structured data to: {csv_out}")
    # Save to JSON
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"Saved structured data to: {json_out}")

# Example usage
if __name__ == "__main__":
    pdf_files = [
        'Document2.pdf'
        # Add more PDF files as needed
    ]
    process_invoices(pdf_files, "extracted_invoices.csv", "extracted_invoices.json")