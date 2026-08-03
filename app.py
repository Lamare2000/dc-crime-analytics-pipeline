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
st.markdown("Automated ETL pipeline and interactive visualization tool built on the Open Data DC API.")

@st.cache_data(ttl=3600)
def fetch_and_clean_data():
    url = "https://services1.arcgis.com/hpR2v9JT3B373To2/arcgis/rest/services/Crime_Incidents_in_2025/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json&resultRecordCount=2000"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        records = [feature['attributes'] for feature in data['features']]
        df = pd.DataFrame(records)
        
        if 'REPORT_DAT' in df.columns:
            df['REPORT_DAT'] = pd.to_datetime(df['REPORT_DAT'], unit='ms')
            df['REPORT_DATE'] = df['REPORT_DAT'].dt.date
            df['HOUR_OF_DAY'] = df['REPORT_DAT'].dt.hour
            df['DAY_OF_WEEK'] = df['REPORT_DAT'].dt.day_name()
            
        df['OFFENSE'] = df['OFFENSE'].fillna('Unspecified').str.title()
        df['METHOD'] = df['METHOD'].fillna('Unknown').str.title()
        df['DISTRICT'] = df['DISTRICT'].fillna('Unknown').astype(str)
        df['SHIFT'] = df['SHIFT'].fillna('Unknown').str.title()
        
        df_geo = df.dropna(subset=['LATITUDE', 'LONGITUDE'])
        df_geo = df_geo[(df_geo['LATITUDE'] != 0) & (df_geo['LONGITUDE'] != 0)]
        
        return df_geo
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

with st.spinner("Connecting to Open Data DC API..."):
    df = fetch_and_clean_data()

if df.empty:
    st.warning("No data retrieved.")
    st.stop()

st.sidebar.header("Pipeline Filters")
districts = sorted(df['DISTRICT'].unique())
selected_districts = st.sidebar.multiselect("Police District", options=districts, default=districts)

offenses = sorted(df['OFFENSE'].unique())
selected_offenses = st.sidebar.multiselect("Offense Type", options=offenses, default=offenses)

shifts = df['SHIFT'].unique().tolist()
selected_shifts = st.sidebar.multiselect("Work Shift", options=shifts, default=shifts)

filtered_df = df[
    (df['DISTRICT'].isin(selected_districts)) &
    (df['OFFENSE'].isin(selected_offenses)) &
    (df['SHIFT'].isin(selected_shifts))
]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Incidents", f"{len(filtered_df):,}")
col2.metric("Top Offense", filtered_df['OFFENSE'].mode()[0] if not filtered_df.empty else "N/A")
col3.metric("Busiest District", f"District {filtered_df['DISTRICT'].mode()[0]}" if not filtered_df.empty else "N/A")
col4.metric("Peak Shift", filtered_df['SHIFT'].mode()[0] if not filtered_df.empty else "N/A")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🗺️ Incident Map", "📊 Offense Trends", "📋 Raw Data Inspector"])

with tab1:
    st.subheader("Geographic Distribution")
    if not filtered_df.empty:
        fig_map = px.scatter_mapbox(
            filtered_df, lat="LATITUDE", lon="LONGITUDE", color="OFFENSE",
            hover_data=["OFFENSE", "METHOD", "DISTRICT", "REPORT_DATE"],
            zoom=10, height=500, mapbox_style="carto-positron"
        )
        st.plotly_chart(fig_map, use_container_width=True)

with tab2:
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Offenses by Category")
        off_counts = filtered_df['OFFENSE'].value_counts().reset_index()
        off_counts.columns = ['Offense', 'Count']
        st.plotly_chart(px.bar(off_counts, x='Count', y='Offense', orientation='h', color='Count', color_continuous_scale='Reds'), use_container_width=True)
    with col_r:
        st.subheader("Incidents by Hour")
        hr_counts = filtered_df['HOUR_OF_DAY'].value_counts().sort_index().reset_index()
        hr_counts.columns = ['Hour', 'Incidents']
        st.plotly_chart(px.line(hr_counts, x='Hour', y='Incidents', markers=True), use_container_width=True)

with tab3:
    st.subheader("Data Quality Output")
    st.dataframe(filtered_df[['OBJECTID', 'REPORT_DAT', 'OFFENSE', 'METHOD', 'DISTRICT', 'SHIFT', 'WARD', 'LATITUDE', 'LONGITUDE']])
