import ee
import geemap
import pandas as pd
import matplotlib.pyplot as plt
import os

# 1. Initialize Google Earth Engine
# 1. Initialize Google Earth Engine
try:
    ee.Initialize()
    print("Google Earth Engine initialized successfully.")
except Exception as e:
    print("Authentication required. Please authenticate in the browser window that opens.")
    ee.Authenticate()
    ee.Initialize()

# 2. Define Region of Interest (ROI)
# Agdam/Fuzuli area: [46.50, 39.30, 47.50, 40.50] (min_lon, min_lat, max_lon, max_lat)
roi = ee.Geometry.Rectangle([46.50, 39.30, 47.50, 40.50])

print("ROI defined.")

# --- Helper Functions ---

def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 images."""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)

def get_summer_composite(year, roi):
    """Generates a cloud-free summer median composite for a given year."""
    start_date = f'{year}-06-01'
    end_date = f'{year}-09-30'
    
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterDate(start_date, end_date)
                  .filterBounds(roi)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                  .map(mask_s2_clouds))
    
    composite = collection.median().clip(roi)
    return composite

# 3. AUTOMATED TRAINING DATA GENERATION
print("Preparing training data...")

# Load Sentinel-2 2020 composite for training
s2_2020 = get_summer_composite(2020, roi)

# Load ESA WorldCover 2020
worldcover = ee.Image('ESA/WorldCover/v100/2020').clip(roi)

# Remap WorldCover: Class 50 (Built-up) -> 1, Others -> 0
# WorldCover classes: 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100
# We remap 50 to 1, and everything else to 0. Use remap for simplicity on known classes or expression.
# To be robust, let's create a binary image.
built_up = worldcover.eq(50)

# Create training points
# Use stratified sample to get points for class 0 (non-built-up) and class 1 (built-up)
training_image = s2_2020.addBands(built_up.rename('class'))
bands = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']

points = training_image.select(bands + ['class']).stratifiedSample(
    numPoints=1000,
    classBand='class',
    region=roi,
    scale=30,  # Increased scale for training sampling speed
    geometries=True
)

# Train Random Forest
print("Training Random Forest Classifier...")
classifier = ee.Classifier.smileRandomForest(50).train(
    features=points,
    classProperty='class',
    inputProperties=bands
)

# 4. TIME-SERIES ANALYSIS
years = [2020, 2021, 2022, 2023, 2024]
results = []
urban_growth_data = {}

print("Starting Time-Series Analysis...")

for year in years:
    print(f"Processing year {year}...")
    
    # Get image
    image = get_summer_composite(year, roi)
    
    # Classify
    classified = image.select(bands).classify(classifier)
    
    # Calculate Area
    # Create an image where each pixel is the area in square meters
    pixel_area = ee.Image.pixelArea()
    
    # Mask non-urban pixels (value 0)
    urban_area_img = pixel_area.updateMask(classified.eq(1))
    
    # Sum area over ROI
    stats = urban_area_img.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=30,       # Optimization: 30m scale to reduce pixel count
        maxPixels=1e10, # Increased maxPixels limit
        tileScale=4     # Optimization: tileScale to split computation
    )
    
    area_sq_m = stats.get('area').getInfo()
    
    if area_sq_m is None:
         area_sq_km = 0
    else:
         area_sq_km = area_sq_m / 1e6 # Convert to km^2
    
    print(f"Year {year}: {area_sq_km:.2f} km²")
    
    results.append({'Year': year, 'Urban Area (km²)': area_sq_km})
    urban_growth_data[year] = area_sq_km
    
    # Keep 2024 classification for visualization
    if year == 2024:
        classified_2024 = classified

# 5. VISUALIZATION

# DataFrame
df = pd.DataFrame(results)

# Line Chart
plt.figure(figsize=(10, 6))
plt.plot(df['Year'], df['Urban Area (km²)'], marker='o', linestyle='-', color='b')
plt.title('Urban Growth in Agdam/Fuzuli (2020-2024)')
plt.xlabel('Year')
plt.ylabel('Built-Up Area (km²)')
plt.grid(True)
plt.xticks(years)
plt.savefig('growth_chart.png')
print("Chart saved to growth_chart.png")

# Interactive Map
print("Generating Map...")
m = geemap.Map()
m.centerObject(roi, 10)

# Add Satellite Imagery (2024)
s2_2024 = get_summer_composite(2024, roi)
vis_params = {'min': 0.0, 'max': 0.3, 'bands': ['B4', 'B3', 'B2']}
m.addLayer(s2_2024, vis_params, 'Sentinel-2 2024')

# Add Urban Detection Layer (Red)
urban_vis = {'min': 1, 'max': 1, 'palette': ['red']}
# We mask 0 values to be transparent, so only value 1 is shown
m.addLayer(classified_2024.updateMask(classified_2024.eq(1)), urban_vis, 'Urban Growth 2024')

m.save('map.html')
print("Map saved to map.html")

print("Processing complete.")
