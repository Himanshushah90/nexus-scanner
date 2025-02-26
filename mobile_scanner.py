import streamlit as st
import cv2
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
from supabase import create_client
import datetime
import logging
import pandas as pd

# Initialize Supabase client
supabase_url = "https://hktzqljpougkmfdlwpix.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhrdHpxbGpwb3Vna21mZGx3cGl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg1MDczNDgsImV4cCI6MjA1NDA4MzM0OH0.IN9WGdv9kTCLakcE_sy_FVRfKunXO7rFSdIZ4tn2Jg0"
supabase = create_client(supabase_url, supabase_key)

GATE_DEFINITIONS = {
    "GATE1": "Main Gate (Deepanshu)",
    "GATE2": "Main Gate (Person 2)",
    "GATE3": "Main Gate (Person 3)",
    "GATE4": "Main Gate (Person 4)",
}

def process_qr(qr_data, gate_id):
    try:
        # Clean and normalize QR data
        qr_data = qr_data.strip().upper()
        if not qr_data.startswith("NEXUS2025-"):
            qr_data = f"NEXUS2025-{qr_data.replace('NEXUS2025', '')}"
        
        # Query attendee with normalized data
        response = supabase.table("attendees").select("*").eq("qr_code_data", qr_data).execute()
        
        if not response.data:
            # Try alternative format (without prefix)
            alt_qr_data = qr_data.replace("NEXUS2025-", "")
            response = supabase.table("attendees").select("*").eq("qr_code_data", alt_qr_data).execute()
            
            if not response.data:
                return "error", "Invalid QR Code"
        
        attendee = response.data[0]
        if attendee.get("entry_status"):
            return "warning", f"Already scanned at {attendee['entry_time']}"
            
        # Update entry status
        current_time = datetime.datetime.now().isoformat()
        supabase.table("attendees").update({
            "entry_status": True,
            "entry_time": current_time
        }).eq("id", attendee["id"]).execute()
        
        # Log scan
        supabase.table("scan_log").insert({
            "reference_number": attendee["reference_number"],
            "scan_time": current_time,
            "scan_status": "SUCCESS",
            "scanner_id": gate_id,
            "notes": "Mobile scan"
        }).execute()
        
        return "success", f"Welcome {attendee['name']}!"
        
    except Exception as e:
        return "error", f"Error: {str(e)}"

def process_manual_entry(ref_number, gate_id):
    try:
        if not ref_number:
            return "warning", "Please enter a reference number"
        
        # Clean and normalize reference number
        ref_number = ref_number.strip().upper()
        if not ref_number.startswith("NEXUS2025-"):
            ref_number = f"NEXUS2025-{ref_number.replace('NEXUS2025', '')}"
        
        # Process as QR code
        return process_qr(ref_number, gate_id)
    except Exception as e:
        return "error", f"Error: {str(e)}"

def main():
    st.set_page_config(
        page_title="Nexus Scanner",
        page_icon="🎫",
        layout="wide"
    )

    st.title("Nexus 2025 QR Scanner")

    # Gate selection at the top
    gate_id = st.selectbox(
        "Select Gate",
        options=list(GATE_DEFINITIONS.keys()),
        format_func=lambda x: f"{x}: {GATE_DEFINITIONS.get(x, 'Unknown')}"
    )

    st.markdown(f"**Active Gate:** {GATE_DEFINITIONS[gate_id]}")

    # Create columns for scanner and manual entry
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Scan QR Code")
        img_file = st.camera_input(
            "Take a photo of QR code",
            help="Place QR code in view and take a photo",
            key="camera"
        )
        
        if img_file is not None:
            # Process image
            image = Image.open(img_file)
            img_array = np.array(image)
            
            # Decode QR code
            qr_codes = decode(img_array)
            
            if qr_codes:
                qr_data = qr_codes[0].data.decode('utf-8')
                status, message = process_qr(qr_data, gate_id)
                show_result(status, message)
            else:
                st.error("No QR code found in image")

    with col2:
        st.subheader("Manual Entry")
        ref_number = st.text_input("Enter Reference Number").strip().upper()
        if st.button("Process Entry", type="primary"):
            status, message = process_manual_entry(ref_number, gate_id)
            show_result(status, message)

    # Display recent scans
    st.markdown("---")
    st.subheader("Recent Scans")
    display_recent_scans(gate_id)

def show_result(status, message):
    """Display scan result with appropriate styling"""
    if status == "success":
        st.success(f"✅ {message}")
        st.balloons()
    elif status == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.error(f"❌ {message}")

def display_recent_scans(gate_id):
    """Display recent scans in a more mobile-friendly format"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    scans = supabase.table("scan_log").select("*").eq("scanner_id", gate_id).execute()
    
    today_scans = [
        scan for scan in scans.data 
        if scan.get("scan_time", "").startswith(today)
    ]
    
    if today_scans:
        st.metric("Total Scans Today", len(today_scans))
        
        # Show last 5 scans in cards
        for scan in list(reversed(today_scans))[:5]:
            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**Ref:** {scan['reference_number']}")
                with col2:
                    scan_time = datetime.datetime.fromisoformat(scan['scan_time']).strftime('%H:%M:%S')
                    st.markdown(f"*{scan_time}*")
                st.markdown("---")
    else:
        st.info("📝 No scans yet today")

if __name__ == "__main__":
    main()
