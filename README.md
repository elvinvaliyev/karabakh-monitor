# 🛰️ Karabakh Post-Conflict Reconstruction Monitor

A geospatial data science tool to quantify and visualize urban growth in the Karabakh region (Agdam/Fuzuli) from 2020 to 2024 using **Sentinel-2** satellite imagery and **Google Dynamic World** AI.

![Project Screenshot](image.png)

## 📊 Project Overview
This tool automates the monitoring of post-conflict reconstruction by:
1.  **Ingesting Sentinel-2 Imagery**: Filtering for cloud-free summer composites.
2.  **AI Land Cover Analysis**: Using Google's "Dynamic World" model (~10m resolution) to detect built-up areas.
3.  **Time-Series Tracking**: Calculating total urban area (km²) for each year since 2020.
4.  **Interactive Dashboard**: A Streamlit app with Split-Map comparison (Before/After) and change detection.

## 🛠️ Tech Stack
*   **Python 3.9+**
*   **Google Earth Engine (GEE)**: Cloud-based geospatial processing.
*   **Streamlit**: Interactive web dashboard.
*   **Geemap**: Interactive mapping integration.
*   **Pandas/Matplotlib**: Data analysis and charting.

## 🚀 How to Run Locally

### 1. Prerequisites
*   Python installed.
*   A Google Earth Engine account (free for research).

### 2. Installation
```bash
git clone https://github.com/YOUR_USERNAME/karabakh-monitor.git
cd karabakh-monitor
pip install -r requirements.txt
```

### 3. Authentication
The first time you run the app, you need to authenticate with Google:
```bash
earthengine authenticate
```

### 4. Run the App
**Web Interface (Recommended):**
```bash
streamlit run app.py
```

**Command Line Mode (Headless):**
```bash
python cli_analysis.py
```

## ☁️ Deployment (Google Cloud)
This project includes a `Dockerfile` for deployment to Google Cloud Run.

1.  **Build**: `gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/karabakh-monitor .`
2.  **Deploy**: `gcloud run deploy --image gcr.io/YOUR_PROJECT_ID/karabakh-monitor --platform managed`

## 📈 Results (Example)
*   **Agdam/Fuzuli Area**:
    *   2020 (Baseline): ~1440 km²
    *   2023 (Peak Construction): ~1770 km²
    *   *Growth detected in road networks and new settlements.*

## 📜 License
MIT
