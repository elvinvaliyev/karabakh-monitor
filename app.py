import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import datetime
import os

# --- 1. GEE Initialization ---
try:
    # Initialize GEE. It will use the default project configured in your local environment
    # or prompt for authentication.
    ee.Initialize()
except Exception as e:
    # If using Cloud Run, we might need a project ID explicitly if not using default credentials
    project_id = os.getenv('EE_PROJECT_ID')
    if project_id:
        ee.Initialize(project=project_id)
    else:
        st.error("Google Earth Engine Authentication Failed. Please run `earthengine authenticate` locally or set EE_PROJECT_ID.")
        st.stop()

# --- 2. Helper Functions ---

def get_dynamic_world_built_probability(roi, start_date, end_date):
    """
    Fetches the Dynamic World 'built' class probability.
    Dynamic World Band 6 is 'built'.
    """
    dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
        .filterDate(start_date, end_date) \
        .filterBounds(roi)
    
    # We want the probability of the 'built' class (index 6).
    # The 'built' probability is often better than the raw label for monitoring growth.
    # But for simplicity in visualization, let's use the 'label' mode or a probability threshold.
    
    # Let's use the Mode of the Class Label for visualization
    classification = dw.select('label').mode().clip(roi)
    
    # Let's create a binary mask: Built (6) = 1, Others = 0
    built_mask = classification.eq(6).rename('built')
    return built_mask

def mask_s2_clouds(image):
  qa = image.select('QA60')
  cloud_bit_mask = 1 << 10
  cirrus_bit_mask = 1 << 11
  mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
  return image.updateMask(mask).divide(10000)

def get_s2_image(roi, start_date, end_date):
    """Fetches a Sentinel-2 cloud-free median composite."""
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterDate(start_date, end_date) \
        .filterBounds(roi) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .map(mask_s2_clouds)
    
    return s2.median().clip(roi)

def calculate_built_area(built_image, roi):
    """Calculates the area of built-up pixels in km²."""
    pixel_area = ee.Image.pixelArea()
    built_area_img = pixel_area.updateMask(built_image.eq(1))
    
    stats = built_area_img.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=10,
        maxPixels=1e10,
        tileScale=4
    )
    
    area_sq_m = stats.get('area').getInfo()
    if area_sq_m:
        return area_sq_m / 1e6
    return 0.0

# --- 3. Streamlit App Layout ---

st.set_page_config(layout="wide", page_title="Karabakh Reconstruction Monitor")

st.title("🛰️ Karabakh Post-Conflict Reconstruction Monitor")
st.markdown("""
Monitor urbanization and reconstruction efforts in the Karabakh region using **Sentinel-2** satellite imagery and **Google Dynamic World** AI land cover data.
""")

# Sidebar
with st.sidebar:
    st.header("Settings")
    
    # Location Selector
    location_options = {
        "Agdam/Fuzuli (Wide)": [46.50, 39.30, 47.50, 40.50],
        "Fuzuli City": [47.11, 39.58, 47.18, 39.62],
        "Agdam City": [46.90, 39.97, 46.96, 40.01],
        "Shusha": [46.72, 39.73, 46.78, 39.78],
        "Custom (Draw on Map)": None
    }
    location_name = st.selectbox("Select Region", list(location_options.keys()))
    
    # Date Selectors
    st.subheader("Time Comparison")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Before**")
        start_date_1 = st.date_input("Start", datetime.date(2020, 6, 1))
        end_date_1 = st.date_input("End", datetime.date(2020, 9, 30))
    with col2:
        st.markdown("**After**")
        start_date_2 = st.date_input("Start", datetime.date(2024, 6, 1))
        end_date_2 = st.date_input("End", datetime.date(2024, 9, 30))

    st.info("Tip: Choose Summer months for best cloud-free images.")

# Main Content
row1_col1, row1_col2 = st.columns([3, 1])

# ROI Handling
if location_name == "Custom (Draw on Map)":
    st.warning("⚠️ Please use the drawing tool on the map to define your custom ROI.")
    roi = None
else:
    coords = location_options[location_name]
    roi = ee.Geometry.Rectangle(coords)

# Map Initialization
m = geemap.Map()

# Session State for Analysis
if 'analyzed' not in st.session_state:
    st.session_state['analyzed'] = False

# Trigger Analysis
if st.button("Analyze Change"):
    st.session_state['analyzed'] = True

# Calculate & Display (Persist if analyzed)
if st.session_state['analyzed']:
    if location_name == "Custom (Draw on Map)":
        st.error("Custom drawing is experimental. Please select a preset region for now.")
        roi = ee.Geometry.Rectangle(location_options["Agdam/Fuzuli (Wide)"])
        m.centerObject(roi, 10)
    else:
        m.centerObject(roi, 11)

    with st.spinner("Fetching Satellite Data & AI Analysis..."):
        # 1. Get Images (Visuals)
        # Cache results if possible, but GEE lazy eval handles this reasonably well
        img1 = get_s2_image(roi, str(start_date_1), str(end_date_1))
        img2 = get_s2_image(roi, str(start_date_2), str(end_date_2))
        
        # 2. Get AI Analysis (Built-up)
        built1 = get_dynamic_world_built_probability(roi, str(start_date_1), str(end_date_1))
        built2 = get_dynamic_world_built_probability(roi, str(start_date_2), str(end_date_2))
        
        # 3. Calculate Stats
        area1 = calculate_built_area(built1, roi)
        area2 = calculate_built_area(built2, roi)
        growth = area2 - area1
        
        # 4. Display Stats
        st.metric(label=f"Built Area ({start_date_1.year})", value=f"{area1:.2f} km²")
        st.metric(label=f"Built Area ({start_date_2.year})", value=f"{area2:.2f} km²", delta=f"{growth:.2f} km²")
        
        # 5. Split Map
        vis_params = {'min': 0.0, 'max': 0.3, 'bands': ['B4', 'B3', 'B2']}
        
        # Controls
        show_change = st.checkbox("Hightlight New Construction (Red)", value=True)

        if show_change:
            # Logic:
            # New Construction = Built in 2024 AND NOT Built in 2020
            # Pre-existing = Built in 2020 AND Built in 2024
            
            # 1. Create Masks
            new_construction = built2.And(built1.Not()).rename('new_construction')
            projected_old = built1 # Just show what was there in 2020
            
            # 2. Visualize
            # Pre-existing in 2020 (Yellow/Gray - subtle)
            old_vis = projected_old.updateMask(projected_old).visualize(palette=['yellow'], opacity=0.4)
            
            # New Construction (Bright Red)
            new_vis = new_construction.updateMask(new_construction).visualize(palette=['red'], opacity=0.8)
            
            # 3. Create Composites for Split Map
            
            # LEFT (2020): Satellite + Existing Buildings (Yellow)
            s1_vis = img1.visualize(**vis_params)
            left_image = ee.ImageCollection([s1_vis, old_vis]).mosaic()
            
            # RIGHT (2024): Satellite + Existing (Yellow) + NEW (Red)
            s2_vis = img2.visualize(**vis_params)
            # We add old_vis to right side too so you see context, and new_vis on top
            right_image = ee.ImageCollection([s2_vis, old_vis, new_vis]).mosaic()
            
            left_layer = geemap.ee_tile_layer(left_image, {}, f'2020 (Yellow=Existing)')
            right_layer = geemap.ee_tile_layer(right_image, {}, f'2024 (Red=New)')
        else:
            left_layer = geemap.ee_tile_layer(img1, vis_params, f'Satellite {start_date_1.year}')
            right_layer = geemap.ee_tile_layer(img2, vis_params, f'Satellite {start_date_2.year}')
        
        m.split_map(left_layer, right_layer)

# Display Map
m.to_streamlit(height=600)
