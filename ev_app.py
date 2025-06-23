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
import streamlit.components.v1 as components


# Custom CSS for blue/black electric theme
st.markdown("""
    <style>
    body, .stApp {
        background: linear-gradient(135deg, #0f2027 0%, #2c5364 100%) !important;
        color: #e0e6f7 !important;
    }
    .stButton>button {
        background-color: #00c6ff !important;
        color: #fff !important;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        box-shadow: 0 0 10px #00c6ff44;
        transition: background 0.3s;
    }
    .stButton>button:hover {
        background-color: #0072ff !important;
        box-shadow: 0 0 20px #00c6ff99;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: #101820;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #00c6ff;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background: #00c6ff;
        color: #fff;
    }
    .stMarkdown, .stTextInput, .stNumberInput, .stSelectbox, .stMultiselect {
        background: #181f2a !important;
        color: #e0e6f7 !important;
        border-radius: 8px;
    }
    .stAlert, .stSuccess, .stError, .stWarning, .stInfo {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Splash screen with sound and animation ---
splash_html = '''
<div id="splash" style="position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:9999;background:#0f2027;display:flex;flex-direction:column;align-items:center;justify-content:center;">
    <audio id="splash-audio" src="https://cdn.pixabay.com/audio/2022/07/26/audio_124bfa4c3b.mp3"></audio>
    <img id="car-img" src="https://cdn.pixabay.com/animation/2023/03/01/10/09/10-09-44-401_512.gif" style="width:120px;filter:drop-shadow(0 0 40px #00c6ff);margin-bottom:10px;" />
    <h1 style="color:#00c6ff;font-size:1.3rem;font-family:sans-serif;letter-spacing:2px;margin:0 0 8px 0;padding:0;line-height:1.1;">EV CHARGER FINDER</h1>
    <button id="play-btn" style="display:none;margin-top:10px;padding:6px 18px;background:#00c6ff;color:#fff;border:none;border-radius:6px;font-size:1rem;cursor:pointer;">Play Sound</button>
</div>
<script>
window.onload = function() {
    var audio = document.getElementById('splash-audio');
        var playBtn = document.getElementById('play-btn');
    var played = false;
    function playSplash() {
        if (!played) {
            audio.volume = 1.0;
            audio.play().then(()=>{
                played = true;
                playBtn.style.display = 'none';
                setTimeout(function() {
                    var car = document.getElementById('car-img');
                    car.style.transition = 'transform 1.2s cubic-bezier(0.4,2,0.6,1), opacity 1.2s';
                    car.style.transform = 'translateX(600px) scale(1.2)';
                    car.style.opacity = '0.2';
                }, 1200);
                setTimeout(function() {
                    var splash = document.getElementById('splash');
                    splash.style.transition = 'opacity 1s';
                    splash.style.opacity = 0;
                    setTimeout(function(){ splash.style.display = 'none'; }, 1000);
                }, 2200);
            }).catch(()=>{
                playBtn.style.display = 'block';
            });
        }
    }
    playSplash();
    playBtn.onclick = playSplash;

}
</script>
'''
components.html(splash_html, height=350)




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

# Main app
st.set_page_config(
    page_title="Freddie - your EV Charger Finder Buddy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("⚡ Freddie - your EV Charger Finder Buddy")
st.markdown("Find and manage electric vehicle charging stations near you!")

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["🗺️ Map View", "📝 Add Charger", "🔍 Find Nearest"])

# Default Karachi coordinates
KARACHI_LAT = 24.8607
KARACHI_LON = 67.0011

# Google Sheets connection
try:
    # ... your credentials and gspread logic ...
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
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
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

# Load data
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # ... your header and cleaning logic ...
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    df = pd.DataFrame()  # Always define df, even if empty

with tab1:
    st.markdown("### View Charging Stations")
    st.markdown("Explore charging stations on the interactive map below.")
    map_center = [st.session_state.add_lat if 'add_lat' in st.session_state else KARACHI_LAT,
                  st.session_state.add_lon if 'add_lon' in st.session_state else KARACHI_LON]
    m = folium.Map(location=map_center, zoom_start=12, tiles='CartoDB positron')
    marker_cluster = MarkerCluster().add_to(m)
    if not df.empty:
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
    Fullscreen().add_to(m)
    LocateControl().add_to(m)
    st_folium(m, use_container_width=True, height=600)

with tab2:
    st.markdown("### Add New Charging Station")
    st.markdown("""
    Fill in the details below to add a new charging station.
    > Note: Email verification will be added soon for enhanced security.
    """)

    # Session state for map picker
    if 'add_lat' not in st.session_state:
        st.session_state.add_lat = KARACHI_LAT
    if 'add_lon' not in st.session_state:
        st.session_state.add_lon = KARACHI_LON

    # Use My Location button (browser geolocation)
    st.markdown('''
    <script>
    function getLocation() {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                window.parent.postMessage({type: 'set_location', lat: lat, lon: lon}, '*');
            }
        );
    }
    </script>
    <button onclick='getLocation(); return false;' style='margin-bottom:10px;'>📍 Use My Location</button>
    ''', unsafe_allow_html=True)

    # Listen for location from browser
    st_folium_js = '''
    <script>
    window.addEventListener("message", (event) => {
        if (event.data.type === "set_location") {
            const latInput = window.parent.document.querySelector('input[data-testid="stNumberInput"][aria-label="Latitude"]');
            const lonInput = window.parent.document.querySelector('input[data-testid="stNumberInput"][aria-label="Longitude"]');
            if (latInput && lonInput) {
                latInput.value = event.data.lat;
                lonInput.value = event.data.lon;
                latInput.dispatchEvent(new Event('input', { bubbles: true }));
                lonInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    });
    </script>
    '''
    st.markdown(st_folium_js, unsafe_allow_html=True)

    # Map picker
    st.write("**Pick location on map:** (drag the marker)")
    m_picker = folium.Map(location=[st.session_state.add_lat, st.session_state.add_lon], zoom_start=12)
    marker = folium.Marker([st.session_state.add_lat, st.session_state.add_lon], draggable=True)
    marker.add_to(m_picker)
    map_picker_data = st_folium(m_picker, width=500, height=350, returned_objects=["last_clicked", "last_object_clicked_tooltip"] )
    if map_picker_data and map_picker_data.get("last_clicked"):
        st.session_state.add_lat = map_picker_data["last_clicked"]["lat"]
        st.session_state.add_lon = map_picker_data["last_clicked"]["lng"]

    # Sanity check for land (simple bounding box for Karachi)
    def is_on_land(lat, lon):
        # Karachi bounding box (approximate)
        return 24.7 <= lat <= 25.1 and 66.8 <= lon <= 67.4

    # --- All form fields and submit button must be inside the form ---
    with st.form("add_charger_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Station Name")
            lat = st.number_input("Latitude", format="%.6f", value=st.session_state.add_lat, key="lat_input")
            price = st.number_input("Price per kWh ($)", value=0.0, format="%.2f")
            charger_type = st.selectbox("Charger Type", ["2kWh", "7kWh", "50kWh", "Other"])
            charger_desc = ""
            if charger_type == "Other":
                charger_desc = st.text_input("Describe the charger type (required)")
            contact = st.text_input("Contact Information")
        with col2:
            lon = st.number_input("Longitude", format="%.6f", value=st.session_state.add_lon, key="lon_input")
            status = st.selectbox("Status", ["Available", "In Use", "Out of Service"])
            amenities = st.multiselect(
                "Amenities",
                ["Restrooms", "Food", "Shopping", "WiFi", "Covered", "24/7"]
            )
            operating_hours = st.text_input("Operating Hours (e.g., '24/7' or '9 AM - 10 PM')")

        # Keep map and fields in sync
        st.session_state.add_lat = lat
        st.session_state.add_lon = lon

        submit_button = st.form_submit_button("Add Charging Station")
        if submit_button:
            if not is_on_land(lat, lon):
                st.error("The selected location appears to be in the sea or outside Karachi. Please pick a valid land location in Karachi.")
            elif name and lat != 0 and lon != 0 and (charger_type != "Other" or (charger_type == "Other" and charger_desc.strip() != "")):
                try:
                    # Prepare data
                    new_data = {
                        'name': name,
                        'lat': lat,
                        'lon': lon,
                        'price': price,
                        'type': charger_type if charger_type != "Other" else charger_desc,
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
                    # Reset form fields to defaults (refresh form)
                    st.session_state.add_lat = KARACHI_LAT
                    st.session_state.add_lon = KARACHI_LON
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error adding charging station: {str(e)}")
            else:
                st.error("Please fill in all required fields (name, latitude, longitude, and charger description if 'Other' is selected)")

with tab3:
    st.markdown("### Find Nearest Charging Stations")
    st.markdown("Enter your location to find the nearest charging stations.")
    if 'user_lat' not in st.session_state:
        st.session_state.user_lat = KARACHI_LAT
    if 'user_lon' not in st.session_state:
        st.session_state.user_lon = KARACHI_LON
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("Enter location (e.g., 'New York, NY')")
        user_lat = st.number_input("Or enter your Latitude", format="%.6f", value=st.session_state.user_lat, key="user_lat_input")
        user_lon = st.number_input("Or enter your Longitude", format="%.6f", value=st.session_state.user_lon, key="user_lon_input")
        st.markdown('''
        <script>
        function getUserLocation() {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    window.parent.postMessage({type: 'set_user_location', lat: lat, lon: lon}, '*');
                }
            );
        }
        </script>
        <button onclick='getUserLocation(); return false;' style='margin-bottom:10px;'>📍 Use My Own Location</button>
        ''', unsafe_allow_html=True)
        st.markdown('''
        <script>
        window.addEventListener("message", (event) => {
            if (event.data.type === "set_user_location") {
                const latInput = window.parent.document.querySelector('input[data-testid="stNumberInput"][aria-label="Or enter your Latitude"]');
                const lonInput = window.parent.document.querySelector('input[data-testid="stNumberInput"][aria-label="Or enter your Longitude"]');
                if (latInput && lonInput) {
                    latInput.value = event.data.lat;
                    lonInput.value = event.data.lon;
                    latInput.dispatchEvent(new Event('input', { bubbles: true }));
                    lonInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        });
        </script>
        ''', unsafe_allow_html=True)
    with col2:
        max_distance = st.slider("Maximum Distance (km)", 1, 100, 10)
    if search_query:
        if not df.empty:
            try:
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="ev_charger_finder")
                location = geolocator.geocode(search_query)
                if location:
                    df['distance'] = df.apply(
                        lambda row: geodesic(
                            (location.latitude, location.longitude),
                            (row['lat'], row['lon'])
                        ).kilometers,
                        axis=1
                    )
                    nearby_stations = df[df['distance'] <= max_distance].sort_values('distance')
                    if not nearby_stations.empty:
                        st.success(f"Found {len(nearby_stations)} charging stations within {max_distance}km")
                        for idx, row in nearby_stations.iterrows():
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
                                rating = st.slider("Rate this charger", 1, 5, 3, key=f"rating_slider_{idx}")
                                if st.button(f"Submit Rating for {row['name']}", key=f"rate_btn_{idx}"):
                                    st.success(f"Thank you for rating {row['name']} with {rating} stars!")
                    else:
                        st.warning(f"No charging stations found within {max_distance}km")
                else:
                    st.error("Location not found. Please try a different search query.")
            except Exception as e:
                st.error(f"Error searching for locations: {str(e)}")
        else:
            st.warning("No data available to search.")
    elif user_lat and user_lon:
        if not df.empty:
            try:
                df['distance'] = df.apply(
                    lambda row: geodesic(
                        (user_lat, user_lon),
                        (row['lat'], row['lon'])
                    ).kilometers,
                    axis=1
                )
                nearby_stations = df[df['distance'] <= max_distance].sort_values('distance')
                if not nearby_stations.empty:
                    st.success(f"Found {len(nearby_stations)} charging stations within {max_distance}km")
                    for idx, row in nearby_stations.iterrows():
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
                            rating = st.slider("Rate this charger", 1, 5, 3, key=f"rating_slider_{idx}")
                            if st.button(f"Submit Rating for {row['name']}", key=f"rate_btn_{idx}"):
                                st.success(f"Thank you for rating {row['name']} with {rating} stars!")
                else:
                    st.warning(f"No charging stations found within {max_distance}km")
            except Exception as e:
                st.error(f"Error searching for locations: {str(e)}")
        else:
            st.warning("No data available to search.")
