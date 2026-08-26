# Intelligent BMS Project

This is the single master project folder containing every latest working file required for the Battery Management System (BMS) project.

## 1. How to install requirements
To install all required packages, run:
```bash
pip install -r docs/requirements.txt
```

## 2. How to train the ML model
Run the training scripts (if available) from the `backend/` directory. For example, if you have `train_transformer.py` or `incremental_train.py`:
```bash
cd backend
python incremental_train.py
```
*(Note: some training scripts might be external depending on the dataset update).*

## 3. How to run prediction
Real-time prediction and fault detection can be run via:
```bash
cd scripts
run_fault_detection.bat
```
Alternatively, run the prediction scripts directly from the backend folder:
```bash
cd backend
python predict_fault.py
```

## 4. How to start the Flask backend
To start the server handling the ML models and data endpoints:
```bash
cd backend
python bms_dashboard_backend.py
```
Alternatively, use the startup script:
```bash
cd scripts
run_dashboard.bat
```

## 5. How to open the dashboard
Once the Flask backend is running, open the HTML dashboard file in your web browser:
- `frontend/live_dashboard_v3.html` (or your preferred latest dashboard file)

## 6. Which files are model files
Model weights and configurations are located in the `models/` directory:
- `battery_fault_transformer.pth` (PyTorch model weights)
- `battery_transformer_model.pth` (PyTorch model weights)
- `bms_scaler.joblib` (Scikit-Learn feature scaler)
- `feature_columns.json` (List of features expected by the model)
- `label_map.json` (Mapping of numeric classes to fault types)

## 7. Which files are dataset files
Datasets are stored in the `data/` directory:
- `bms_data_corrected.csv` (and any other `.csv` / `.xlsx` files used for training, testing, or telemetry).

## 8. Which files are dashboard files
Dashboard and UI files are stored in the `frontend/` directory:
- `live_dashboard_v3.html` (Primary Dashboard UI)
- `live_dashboard_v2.html`
- Any React/Vite project directories if applicable.

---
**Project Structure:**
- `backend/`: Flask server and prediction scripts
- `frontend/`: UI files
- `models/`: ML weights, scalers, and mappings
- `data/`: Datasets and live logs
- `scripts/`: Batch / Shell startup scripts
- `docs/`: Documentation and requirements
- `outputs/`: Prediction results, logs, and generated graphs
