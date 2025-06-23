import math
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen, LocateControl
from streamlit_folium import st_folium
from geopy.distance import geodesic
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from datetime import datetime
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string

def safe_rating_convert(rating_value):
    """Safely convert rating value to integer, handling all edge cases."""
    try:
        if rating_value is None or rating_value == '' or (isinstance(rating_value, float) and math.isnan(rating_value)):
            return 0
        rating_str = str(rating_value).strip()
        if not rating_str or rating_str.lower() == 'nan':
            return 0
        return int(float(rating_str))
    except (ValueError, TypeError, AttributeError):
        return 0

def safe_json_loads(val):
    try:
        if not val or val == '' or val is None:
            return []
        return json.loads(val)
    except Exception:
        return []

def generate_verification_code():
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(email, code):
    """Send verification code via email"""
    try:
        # Email configuration
        sender_email = "your-app-email@gmail.com"  # Replace with your app's email
        sender_password = "your-app-email-password"  # Replace with your app's email password
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = email
        message["Subject"] = "EV Charger Station Verification Code"
        
        # Email body
        body = f"""
        Thank you for registering your EV charging station!
        
        Your verification code is: {code}
        
        Please enter this code in the app to complete your registration.
        
        If you didn't request this code, please ignore this email.
        """
        
        message.attach(MIMEText(body, "plain"))
        
        # Create SMTP session
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        return True
    except Exception as e:
        st.error(f"Error sending verification email: {str(e)}")
        return False

# Initialize session state for verification
if 'verification_code' not in st.session_state:
    st.session_state.verification_code = None
if 'email_verified' not in st.session_state:
    st.session_state.email_verified = False
if 'seller_email' not in st.session_state:
    st.session_state.seller_email = 'pending_verification'  # Temporary placeholder
if 'verification_step' not in st.session_state:
    st.session_state.verification_step = 'add_charger'  # Temporarily set to final step

# Custom CSS for better styling
st.set_page_config(
    page_title="EV Charging Station Finder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .css-1d391kg {
        padding: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 4rem;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        gap: 1rem;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4CAF50;
        color: white;
    }
    .stMarkdown {
        padding: 1rem;
    }
    .stAlert {
        border-radius: 5px;
    }
    .stSuccess {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
    }
    .stError {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
    }
    .stInfo {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
    }
    .stWarning {
        background-color: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Google Sheets connection
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# Securely get credentials from Streamlit secrets
try:
    google_creds_dict = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"].replace('\\n', '\n'),
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open('ev_chargers').sheet1
except KeyError:
    st.error("GCP credentials not found in Streamlit secrets. Please add them.")
    st.stop()
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

# Load data
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Define expected headers
    expected_headers = ['name', 'lat', 'lon', 'price', 'type', 'contact', 'status', 'rating', 'reviews', 'amenities', 'operating_hours']
    
    # Add missing columns with default values
    for col in expected_headers:
        if col not in df.columns:
            if col == 'rating':
                df[col] = 0
            elif col == 'reviews':
                df[col] = 0
            elif col == 'amenities':
                df[col] = '[]'
            elif col == 'operating_hours':
                df[col] = '24/7'
            else:
                df[col] = ''
    
    # Clean the rating column
    if 'rating' in df.columns:
        df['rating'] = df['rating'].apply(safe_rating_convert)
    
    # Convert numeric columns
    numeric_columns = ['lat', 'lon', 'price', 'rating']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    df = pd.DataFrame()

# Main app
st.title("⚡ EV Charging Station Finder")
st.markdown("Find and manage electric vehicle charging stations near you!")

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["🗺️ Map View", "📝 Add Charger", "🔍 Find Nearest"])

with tab1:
    st.markdown("### View Charging Stations")
    st.markdown("Explore charging stations on the interactive map below.")
    
    # Map view with improved styling
    if not df.empty:
        # Create map with a modern style
        m = folium.Map(
            location=[df['lat'].mean(), df['lon'].mean()],
            zoom_start=13,
            tiles='CartoDB positron'  # Modern, clean style
        )
        
        # Add marker cluster for better visualization
        marker_cluster = MarkerCluster().add_to(m)
        
        # Add markers with improved popups
        for _, row in df.iterrows():
            popup_content = f"""
            <div style='font-family: Arial, sans-serif; padding: 10px;'>
                <h3 style='color: #4CAF50; margin-bottom: 10px;'>{row['name']}</h3>
                <p style='margin: 5px 0;'><b>Type:</b> {row['type']}</p>
                <p style='margin: 5px 0;'><b>Price:</b> ${row['price']}/kWh</p>
                <p style='margin: 5px 0;'><b>Status:</b> {row['status']}</p>
                <p style='margin: 5px 0;'><b>Rating:</b> {'⭐' * safe_rating_convert(row.get('rating'))}</p>
                <p style='margin: 5px 0;'><b>Contact:</b> {row['contact']}</p>
                <p style='margin: 5px 0;'><b>Amenities:</b> {', '.join(safe_json_loads(row.get('amenities', '[]')))}</p>
            </div>
            """
            folium.Marker(
                [row['lat'], row['lon']],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=row['name']
            ).add_to(marker_cluster)
        
        # Add fullscreen and locate controls
        Fullscreen().add_to(m)
        LocateControl().add_to(m)
        
        # Display map with improved styling
        st_folium(m, width=800, height=600)
    else:
        st.warning("No charging stations found. Add some stations to see them on the map!")

with tab2:
    st.markdown("### Add New Charging Station")
    st.markdown("""
    Fill in the details below to add a new charging station.
    > Note: Email verification will be added soon for enhanced security.
    """)
    
    # Form with improved styling
    with st.form("add_charger_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Station Name")
            lat = st.number_input("Latitude", value=0.0, format="%.6f")
            price = st.number_input("Price per kWh ($)", value=0.0, format="%.2f")
            charger_type = st.selectbox("Charger Type", ["Level 1", "Level 2", "DC Fast"])
            contact = st.text_input("Contact Information")
        
        with col2:
            lon = st.number_input("Longitude", value=0.0, format="%.6f")
            status = st.selectbox("Status", ["Available", "In Use", "Out of Service"])
            amenities = st.multiselect(
                "Amenities",
                ["Restrooms", "Food", "Shopping", "WiFi", "Covered", "24/7"]
            )
            operating_hours = st.text_input("Operating Hours (e.g., '24/7' or '9 AM - 10 PM')")
        
        submit_button = st.form_submit_button("Add Charging Station")
        
        if submit_button:
            if name and lat != 0 and lon != 0:
                try:
                    # Prepare data
                    new_data = {
                        'name': name,
                        'lat': lat,
                        'lon': lon,
                        'price': price,
                        'type': charger_type,
                        'contact': contact,
                        'status': status,
                        'rating': 0,
                        'reviews': 0,
                        'amenities': json.dumps(amenities),
                        'operating_hours': operating_hours,
                        'verified_email': 'pending_verification'  # Placeholder for now
                    }
                    
                    # Add to Google Sheet
                    sheet.append_row(list(new_data.values()))
                    st.success("Charging station added successfully!")
                    time.sleep(2)
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error adding charging station: {str(e)}")
            else:
                st.error("Please fill in all required fields (name, latitude, and longitude)")

with tab3:
    st.markdown("### Find Nearest Charging Stations")
    st.markdown("Enter your location to find the nearest charging stations.")
    
    # Search with improved styling
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_query = st.text_input("Enter location (e.g., 'New York, NY')")
    
    with col2:
        max_distance = st.slider("Maximum Distance (km)", 1, 100, 10)
    
    if search_query:
        try:
            # Get coordinates for the search query
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="ev_charger_finder")
            location = geolocator.geocode(search_query)
            
            if location:
                # Calculate distances
                df['distance'] = df.apply(
                    lambda row: geodesic(
                        (location.latitude, location.longitude),
                        (row['lat'], row['lon'])
                    ).kilometers,
                    axis=1
                )
                
                # Filter by distance
                nearby_stations = df[df['distance'] <= max_distance].sort_values('distance')
                
                if not nearby_stations.empty:
                    st.success(f"Found {len(nearby_stations)} charging stations within {max_distance}km")
                    
                    # Display results in a nice format
                    for _, row in nearby_stations.iterrows():
                        with st.expander(f"{row['name']} ({row['distance']:.1f}km away)"):
                            st.markdown(f"""
                            - **Type:** {row['type']}
                            - **Price:** ${row['price']}/kWh
                            - **Status:** {row['status']}
                            - **Rating:** {'⭐' * safe_rating_convert(row.get('rating'))}
                            - **Contact:** {row['contact']}
                            - **Amenities:** {', '.join(safe_json_loads(row.get('amenities', '[]')))}
                            - **Operating Hours:** {row.get('operating_hours', 'Not specified')}
                            """)
                            
                            # Add rating functionality
                            rating = st.slider("Rate this charger", 1, 5, 3)
                            if st.button(f"Submit Rating for {row['name']}"):
                                st.success(f"Thank you for rating {row['name']} with {rating} stars!")
                else:
                    st.warning(f"No charging stations found within {max_distance}km")
            else:
                st.error("Location not found. Please try a different search query.")
        except Exception as e:
            st.error(f"Error searching for locations: {str(e)}")
