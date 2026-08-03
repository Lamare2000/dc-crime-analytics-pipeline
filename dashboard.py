import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(
    page_title="USAO-DC Crime Analytics Pipeline",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ D.C. Public Safety & Incident Analytics Dashboard")
st.markdown("Automated ETL pipeline and interactive visualization tool built on Open Data DC.")

@st.cache_data(ttl=1800)
def fetch_and_clean_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Official Open Data DC Feature Server 2026 Endpoint
    url = "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/MPD/FeatureServer/41/query"
    params = {
        'where': '1=1',
        'outFields': '*',
        'outSR': '4326',
        'orderByFields': 'REPORT_DAT DESC',
        'f': 'json',
        'resultRecordCount': 2000
    }
    
    records = []
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'features' in data:
            records = [f.get('attributes', f) for f in data['features']]
        elif isinstance(data, list):
            records = data
    except Exception as e:
        print(f"\n[ETL LOG] Primary API Fetch Failed: {e}\n")

    # Secondary Fallback Stream
    if not records:
        try:
            csv_url = "https://opendata.dc.gov/datasets/DCGIS::crime-incidents-in-2026.csv"
            df = pd.read_csv(csv_url, nrows=2000, storage_options=headers)
        except Exception as e:
            print(f"\n[ETL LOG] CSV Fallback Failed: {e}\n")
            st.warning("⚠️ Live API/DNS unreachable. Loading cached offline sample dataset...")
            df = pd.DataFrame({
                'OBJECTID': range(1, 101),
                'REPORT_DAT': pd.date_range(start='2026-01-01', periods=100, freq='h'),
                'OFFENSE': ['Theft/Auto', 'Theft/Other', 'Robbery', 'Burglary', 'Assault W/Dangerous Weapon'] * 20,
                'METHOD': ['Others', 'Others', 'Gun', 'Others', 'Knife'] * 20,
                'DISTRICT': ['1st', '2nd', '3rd', '4th', '5th'] * 20,
                'SHIFT': ['Day', 'Evening', 'Midnight'] * 33 + ['Day'],
                'WARD': [1, 2, 3, 4, 5] * 20,
                'LATITUDE': [38.9072 + (i * 0.001) for i in range(100)],
                'LONGITUDE': [-77.0369 + (i * 0.001) for i in range(100)]
            })
    else:
        df = pd.DataFrame(records)

    # Clean & Transform
    if 'REPORT_DAT' in df.columns:
        df['REPORT_DAT'] = pd.to_datetime(df['REPORT_DAT'], unit='ms', errors='coerce').fillna(
            pd.to_datetime(df['REPORT_DAT'], errors='coerce')
        )
        df['REPORT_DATE'] = df['REPORT_DAT'].dt.date
        df['HOUR_OF_DAY'] = df['REPORT_DAT'].dt.hour
        df['DAY_OF_WEEK'] = df['REPORT_DAT'].dt.day_name()
        
    for col in ['OFFENSE', 'METHOD', 'SHIFT']:
        if col in df.columns:
            df[col] = df[col].fillna('Unspecified').astype(str).str.title()
            
    if 'DISTRICT' in df.columns:
        df['DISTRICT'] = df['DISTRICT'].fillna('Unknown').astype(str)

    if 'LATITUDE' in df.columns and 'LONGITUDE' in df.columns:
        df = df.dropna(subset=['LATITUDE', 'LONGITUDE'])
        df = df[(df['LATITUDE'] != 0) & (df['LONGITUDE'] != 0)]
    
    return df

with st.spinner("Executing ETL pipeline & loading incident records..."):
    df = fetch_and_clean_data()

if df.empty:
    st.error("No data available.")
    st.stop()

# Sidebar Filters
st.sidebar.header("Filter Pipeline Data")

districts = sorted(df['DISTRICT'].unique()) if 'DISTRICT' in df.columns else []
selected_districts = st.sidebar.multiselect("Police District", options=districts, default=districts)

offenses = sorted(df['OFFENSE'].unique()) if 'OFFENSE' in df.columns else []
selected_offenses = st.sidebar.multiselect("Offense Type", options=offenses, default=offenses)

shifts = df['SHIFT'].unique().tolist() if 'SHIFT' in df.columns else []
selected_shifts = st.sidebar.multiselect("Shift", options=shifts, default=shifts)

filtered_df = df[
    (df['DISTRICT'].isin(selected_districts)) &
    (df['OFFENSE'].isin(selected_offenses)) &
    (df['SHIFT'].isin(selected_shifts))
]

# Summary Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Incidents Loaded", f"{len(filtered_df):,}")
col2.metric("Top Offense", filtered_df['OFFENSE'].mode()[0] if not filtered_df.empty else "N/A")
col3.metric("Busiest District", f"District {filtered_df['DISTRICT'].mode()[0]}" if not filtered_df.empty else "N/A")
col4.metric("Peak Shift", filtered_df['SHIFT'].mode()[0] if not filtered_df.empty else "N/A")

st.markdown("---")

# Visualizations
tab1, tab2, tab3 = st.tabs(["🗺️ Geospatial Map", "📊 Temporal Analysis", "📋 Raw Data Inspector"])

with tab1:
    st.subheader("Incident Map Visualization")
    if not filtered_df.empty and 'LATITUDE' in filtered_df.columns:
        fig_map = px.scatter_mapbox(
            filtered_df, lat="LATITUDE", lon="LONGITUDE", color="OFFENSE",
            hover_data=["OFFENSE", "METHOD", "DISTRICT", "REPORT_DATE"],
            zoom=10, height=500, mapbox_style="carto-positron"
        )
        st.plotly_chart(fig_map, width='stretch')

with tab2:
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Offense Breakdown")
        if not filtered_df.empty and 'OFFENSE' in filtered_df.columns:
            off_counts = filtered_df['OFFENSE'].value_counts().reset_index()
            off_counts.columns = ['Offense', 'Count']
            st.plotly_chart(px.bar(off_counts, x='Count', y='Offense', orientation='h', color='Count', color_continuous_scale='Reds'), width='stretch')
    with col_r:
        st.subheader("Hourly Distribution")
        if not filtered_df.empty and 'HOUR_OF_DAY' in filtered_df.columns:
            hr_counts = filtered_df['HOUR_OF_DAY'].value_counts().sort_index().reset_index()
            hr_counts.columns = ['Hour', 'Incidents']
            st.plotly_chart(px.line(hr_counts, x='Hour', y='Incidents', markers=True), width='stretch')

with tab3:
    st.subheader("Data Pipeline Inspection")
    cols_to_show = [c for c in ['OBJECTID', 'REPORT_DAT', 'OFFENSE', 'METHOD', 'DISTRICT', 'SHIFT', 'WARD', 'LATITUDE', 'LONGITUDE'] if c in filtered_df.columns]
    st.dataframe(filtered_df[cols_to_show])
