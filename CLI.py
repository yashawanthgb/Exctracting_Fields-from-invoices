import os
import re
import csv
import json
import argparse
import pytesseract
import pdfplumber
import google.generativeai as genai
from pdf2image import convert_from_path
import pandas as pd
from dotenv import load_dotenv
from PIL import Image
import io
import pymupdf

# Load environment variables
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in your environment variables")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

def is_image_file(file_path):
    """Check if the file is an image file."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    return os.path.splitext(file_path.lower())[1] in image_extensions

def extract_text_from_image(image_path):
    """Extract text from an image file using OCR."""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

def is_digital_pdf(pdf_path):
    """Check if PDF is digital (has extractable text)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return True
    except:
        pass
    return False

def extract_text_digital(pdf_path):
    """Extract text from digital PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        return text.strip()
    except Exception as e:
        print(f"Error extracting digital PDF: {e}")
        return ""

def extract_text_scanned(pdf_path):
    """Extract text from scanned PDF using OCR."""
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
    """Clean extracted text."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,/-]', ' ', text)
    return text.strip()

def extract_fields_with_gemini(text):
    """Extract structured fields from invoice text using Gemini."""
    prompt = f"""
    Extract the following fields from this invoice text. Return only a JSON object with these fields:
    - invoice_number
    - date (invoice date, in YYYY-MM-DD or DD-MM-YYYY format)
    - due_date (if available)
    - vendor_name
    - vendor_address (if available)
    - customer_name
    - customer_address
    - customer_email (if available)
    - customer_phone (if available)
    - customer_tax_id (if available)
    - invoice_total (numeric value only)
    - tax_amount (if available)
    - shipping_amount (if available)
    - payment_terms (if available)
    - payment_method (if available)
    - items: a list of objects, each with:
        - description
        - quantity
        - unit_price
        - total
        - tax_rate (if available)
        - discount (if available)

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
        "customer_name": "XYZ Company",
        "customer_address": "456 Business Ave, Town, Country",
        "customer_email": "contact@xyzcompany.com",
        "customer_phone": "+1-234-567-8900",
        "customer_tax_id": "TAX123456",
        "invoice_total": "1250.50",
        "tax_amount": "125.05",
        "shipping_amount": "25.00",
        "payment_terms": "Net 30",
        "payment_method": "Bank Transfer",
        "items": [
            {{
                "description": "Widget A",
                "quantity": "2",
                "unit_price": "500.00",
                "total": "1000.00",
                "tax_rate": "10%",
                "discount": "0.00"
            }},
            {{
                "description": "Widget B",
                "quantity": "1",
                "unit_price": "250.50",
                "total": "250.50",
                "tax_rate": "10%",
                "discount": "0.00"
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
    """Fallback pattern matching extraction."""
    text = clean_text(text)
    lines = text.split('\n')
    fields = {
        "invoice_number": "",
        "date": "",
        "due_date": "",
        "vendor_name": "",
        "vendor_address": "",
        "customer_name": "",
        "customer_address": "",
        "customer_email": "",
        "customer_phone": "",
        "customer_tax_id": "",
        "invoice_total": "",
        "tax_amount": "",
        "shipping_amount": "",
        "payment_terms": "",
        "payment_method": "",
        "items": []
    }
    return fields

def process_invoices(input_files, csv_out, json_out):
    """Process invoices and save results to CSV and JSON."""
    results = []
    
    for input_file in input_files:
        print(f"\nProcessing: {input_file}")
        
        # Handle different file types
        if is_image_file(input_file):
            text = extract_text_from_image(input_file)
        else:  # PDF file
            is_digital = is_digital_pdf(input_file)
            text = extract_text_digital(input_file) if is_digital else extract_text_scanned(input_file)
        
        extracted_fields = extract_fields_with_gemini(text)
        source_file = os.path.basename(input_file)
        
        # Flatten line items for CSV
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
                'Customer Name': extracted_fields.get('customer_name', ''),
                'Customer Address': extracted_fields.get('customer_address', ''),
                'Customer Email': extracted_fields.get('customer_email', ''),
                'Customer Phone': extracted_fields.get('customer_phone', ''),
                'Customer Tax ID': extracted_fields.get('customer_tax_id', ''),
                'Tax Amount': extracted_fields.get('tax_amount', ''),
                'Shipping Amount': extracted_fields.get('shipping_amount', ''),
                'Payment Terms': extracted_fields.get('payment_terms', ''),
                'Payment Method': extracted_fields.get('payment_method', ''),
                'Item Description': item.get('description', ''),
                'Quantity': item.get('quantity', ''),
                'Unit Price': item.get('unit_price', ''),
                'Item Total': item.get('total', ''),
                'Item Tax Rate': item.get('tax_rate', ''),
                'Item Discount': item.get('discount', ''),
                'Invoice Total': extracted_fields.get('invoice_total', ''),
                'Source File': source_file
            }
            results.append(row)
        
        # Save extracted text to .txt for reference
        with open(os.path.splitext(input_file)[0] + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
    
    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(csv_out, index=False)
    print(f"\nSaved structured data to: {csv_out}")
    
    # Save to JSON
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"Saved structured data to: {json_out}")


def main():
    parser = argparse.ArgumentParser(description='Process invoices and extract structured data.')
    parser.add_argument('input_files', nargs='+', help='Input invoice files (PDF or image)')
    parser.add_argument('--csv', default='extracted_invoices.csv', help='Output CSV filename')
    parser.add_argument('--json', default='extracted_invoices.json', help='Output JSON filename')
    
    args = parser.parse_args()
    
    # Verify input files exist
    for file in args.input_files:
        if not os.path.exists(file):
            print(f"Error: File not found - {file}")
            return
    
    process_invoices(args.input_files, args.csv, args.json)

if __name__ == "__main__":
    main()


# python cli.py invoice.pdf --csv extracted_invoices.csv --json extracted_invoices.json
#python cli.py Document2.pdf
