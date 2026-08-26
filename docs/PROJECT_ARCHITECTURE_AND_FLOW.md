# Intelligent BMS - Project Architecture & Data Flow

This document outlines the detailed flow of your system and explains the exact purpose of every file stored in the `Intelligent_BMS` folder.

---

## 🌊 The System Data Flow
Here is how the data flows through your system when you run the dashboard:

1. **Hardware / Data Ingestion:**
   - Either your simulated scripts (`generate_synthetic_faults.py`) generate data, OR real sensors send Bluetooth data which is captured by `bms_bluetooth_gateway.py`.
2. **Backend Processing (Port 5000):**
   - `bms_dashboard_backend.py` receives the telemetry data.
   - It sends the voltage, current, and temperature data to `predict_fault.py`.
3. **Machine Learning Inference:**
   - `predict_fault.py` scales the data using `bms_scaler.joblib`.
   - It then feeds the scaled data into the AI models (`battery_transformer_model.pth` or XGBoost).
   - If an Out-Of-Distribution (anomaly) is detected, `ood_detector.joblib` triggers an alert.
   - The fault classification is calculated using `risk_scoring.py` and mapped to human-readable names using `label_map.json`.
4. **Frontend Dashboard (Port 5173):**
   - The processed data, along with fault risks and predictions, are sent via API to your React/HTML frontend (`live_dashboard_v3.html`).
   - The frontend visualizes the battery health in real-time.

---

## 📂 Exact File Locations & Breakdown

### 1. `backend/` (The Brain of the System)
These files run the server and handle real-time prediction and training.
- **`bms_dashboard_backend.py`**: The main Flask API server. It listens on port 5000, receives battery data, triggers ML predictions, and serves the results to the dashboard.
- **`predict_fault.py`**: The core inference engine. It loads the ML model and processes incoming live telemetry.
- **`bms_bluetooth_gateway.py`**: A bridge script that listens for live incoming Bluetooth data from physical BMS hardware.
- **`incremental_train.py` & `train_xgboost.py`**: Scripts used to retrain your Machine Learning models on new dataset batches.
- **`generate_synthetic_faults.py` & `generate_synthetic_ood.py`**: Utility scripts used to generate fake/simulated battery faults for testing.
- **`evaluate_ood.py` & `train_ood_detector.py`**: Scripts that train and test the "Out-Of-Distribution" model.
- **`risk_scoring.py` & `fault_risk_config.py`**: Logic that calculates the final "Risk Confidence %" of a fault based on ML output.
- **`datasheet_parser.py`**: Parses battery specifications for different battery chemistries to enforce safety limits.

### 2. `models/` (The AI Weights)
Stores the "memory" and parameters of your trained artificial intelligence.
- **`battery_fault_transformer.pth` & `battery_transformer_model.pth`**: The PyTorch deep learning weights for your Transformer network.
- **`bms_scaler.joblib`**: The Scikit-Learn scaler that normalizes live voltage/current data.
- **`feature_columns.json`**: A list telling the ML model exactly which columns it should expect.
- **`label_map.json`**: Translates the model's numeric output into a readable fault.
- **`active_profile.json` & `chemistry_configs.json`**: Battery chemistry limits currently being enforced.

### 3. `frontend/` (The User Interface)
The visual part of the system that the user interacts with.
- **`live_dashboard_v3.html`**: The main HTML/JS dashboard that draws the graphs, dials, and fault alerts.
- **`battery-dashboard/`**: The complete React/Vite project containing modular UI components.

### 4. `scripts/` (The Automation Shortcuts)
Batch files to make launching the system easy.
- **`run_dashboard.bat`**: The master launcher. Automatically starts backend, ML engine, frontend, and opens your browser.
- **`run_fault_detection.bat`**: Starts the ML backend without launching the visual UI (useful for headless servers).
- **`run_entire_system.bat`**: Orchestrates the startup sequence of the various python files.

### 5. `data/` (The Historical Records)
All Excel and CSV files containing raw logs and training data.
- **`bms_data_corrected.csv` & `Converted_8S2P_Dataset.xlsx`**: Primary cleaned datasets used to train the ML models.
- **`BMS_Fault_*.xlsx`**: Highly specific isolated datasets containing only one type of fault (e.g., `BMS_Fault_Overvoltage.xlsx`).
- **`bms_telemetry_raw.csv` & `bms_telemetry_filtered.csv`**: Logs of data exactly as it was received from the sensors before and after filtering.
- **`augmented_telemetry_dataset.xlsx`**: Artificially expanded dataset combining real data with synthetic faults.
- *(And 20+ other synthetic datasets!)*

### 6. `docs/` (System Documentation)
- **`README.md`**: Technical overview of the repository.
- **`requirements.txt`**: Strict list of Python libraries (`flask`, `torch`, `pandas`) required to run the code.

### 7. `outputs/` (System Generated Artifacts)
- **`prediction_results/`**: CSV logs of historical predictions.
- **`graphs/`**: Saved charts/plots generated during model training.
- **`logs/`**: System runtime and error logs.
- *(Also contains `watchdog.log`, `backend_error.log`, `classification_report.csv`)*

---

### Main Folder Files
- **`HOW_TO_RUN.md`**: Your quick-start step-by-step guide on how to launch and retrain the project.
