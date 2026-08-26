# Intelligent BMS - Complete Run Procedure

This document provides the exact steps to run all parts of your Intelligent Battery Management System (Dashboard, Machine Learning, and Backend).

## Option 1: The Automated Way (Recommended)
We have a unified script that starts the ML backend, the telemetry backend, the React frontend, and the Bluetooth gateway all at once.

1. Open your File Explorer and navigate to your project folder:
   `C:\Users\Adith\Downloads\CLEANED DATA SETS\Intelligent_BMS\scripts`
2. Double-click the file named: **`run_dashboard.bat`**
3. **What happens next:**
   - Multiple black console (command prompt) windows will open. **Do NOT close them!**
   - It will automatically launch the Backend on Port 5000.
   - It will automatically start the React Dashboard on Port 5173.
   - Your web browser will open automatically to the Dashboard at `http://127.0.0.1:5173`.

---

## Option 2: The Manual Way (Step-by-Step)
If you want to run the ML backend and the dashboard separately or if the automated script fails, follow these steps:

### Step A: Run the Backend & ML System
The backend handles the Machine Learning (fault detection) and data telemetry.
1. Open your File Explorer and navigate to:
   `C:\Users\Adith\Downloads\CLEANED DATA SETS\Intelligent_BMS\scripts`
2. Double-click **`run_fault_detection.bat`**
3. A black command window will open. Leave this running in the background. It will load your transformer/XGBoost models from the `models/` folder.

### Step B: Open the Live HTML Dashboard
1. Open your File Explorer and navigate to:
   `C:\Users\Adith\Downloads\CLEANED DATA SETS\Intelligent_BMS\frontend`
2. Right-click on **`live_dashboard_v3.html`** and select **Open with > Google Chrome** (or your preferred browser).
3. The dashboard will instantly connect to the background ML system you started in Step A.

---

## How to Train / Update the ML Models
If you collect new data and need to retrain the ML model:
1. Place your new dataset into the `Intelligent_BMS\data` folder.
2. Open a Command Prompt (Terminal) inside `Intelligent_BMS\backend`.
3. Run the training script:
   ```cmd
   python incremental_train.py
   ```
   *(or `python train_xgboost.py` depending on which model you want to retrain).*
4. The newly trained models and scalers will automatically be saved into your `Intelligent_BMS\models` folder.

---

### Important Notes:
- **Never move files out of their respective folders.** The system is configured to find models in `\models`, data in `\data`, etc.
- If the dashboard shows "Disconnected" or "Offline", ensure the `run_fault_detection.bat` (Backend) is actively running in a command prompt window.
