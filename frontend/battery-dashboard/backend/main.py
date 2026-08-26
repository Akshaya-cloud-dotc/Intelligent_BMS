from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from schemas import CellParameters, CalculateRequest, CalculationResponse
from parser import extract_parameters_from_pdf
from calculator import calculate_pack_data

app = FastAPI(title="Battery Parameter Dashboard API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/upload", response_model=CellParameters)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        contents = await file.read()
        extracted_params = extract_parameters_from_pdf(contents)
        return extracted_params
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys
import json
import pandas as pd
import subprocess
FLASK_APP_DIR = r"C:\Users\Adith\Downloads\CLEANED DATA SETS"
@app.post("/calculate", response_model=CalculationResponse)
def calculate(request: CalculateRequest):
    if request.series_cells <= 0 or request.parallel_cells <= 0:
         raise HTTPException(status_code=400, detail="Series and Parallel cells must be positive integers")
         
    try:
        response = calculate_pack_data(request.cell_parameters, request.series_cells, request.parallel_cells)
        return response
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")

@app.post("/save_active_profile")
def save_active_profile(payload: dict):
    profile_path = os.path.join(FLASK_APP_DIR, "active_profile.json")
    try:
        with open(profile_path, "w") as f:
            json.dump(payload, f, indent=4)
        return {"status": "success", "message": "Active profile saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/train_model")
async def train_model(file: UploadFile = File(...), upload_mode: str = Form("replace")):
    try:
        contents = await file.read()
        target_excel_path = os.path.join(FLASK_APP_DIR, "master_dataset.xlsx")
        backup_excel_path = os.path.join(FLASK_APP_DIR, "master_dataset_backup.xlsx")
        
        import io
        if file.filename.lower().endswith(".csv"):
            df_new = pd.read_csv(io.BytesIO(contents))
        else:
            df_new = pd.read_excel(io.BytesIO(contents))
            
        new_row_count = len(df_new)
        if new_row_count < 100:
            raise HTTPException(status_code=400, detail="Uploaded dataset is too small for reliable ML learning. Please upload at least 100 rows.")
            
        import sys
        if FLASK_APP_DIR not in sys.path:
            sys.path.append(FLASK_APP_DIR)
        try:
            from mode_classifier import classify_operating_modes
        except ImportError:
            raise Exception("mode_classifier module not found")
            
        recompute = (upload_mode == "replace") or not os.path.exists(target_excel_path)
        threshold_path = os.path.join(FLASK_APP_DIR, "mode_thresholds.json")
        df_new = classify_operating_modes(df_new, recompute_thresholds=recompute, threshold_path=threshold_path)
        
        mode_counts = df_new['Operating_Mode'].value_counts().to_dict()
        
        existing_row_count = 0
        if upload_mode == "append" and os.path.exists(target_excel_path):
            df_master = pd.read_excel(target_excel_path)
            existing_row_count = len(df_master)
            
            missing_cols = set(df_master.columns) - set(df_new.columns)
            if missing_cols:
                raise HTTPException(status_code=400, detail=f"Incompatible dataset. Missing columns: {missing_cols}")
                
            df_new = df_new[df_master.columns]
            
            df_combined = pd.concat([df_master, df_new], ignore_index=True)
            telemetry_cols = ['voltage', 'current', 'temperature', 'soc'] + [f'cell_v{i}' for i in range(1, 9)]
            cols_to_check = [c for c in telemetry_cols if c in df_combined.columns]
            if cols_to_check:
                df_combined.drop_duplicates(subset=cols_to_check, keep='last', inplace=True)
        else:
            df_combined = df_new
            if os.path.exists(target_excel_path):
                import shutil
                shutil.copy2(target_excel_path, backup_excel_path)
                
        final_row_count = len(df_combined)
        df_combined.to_excel(target_excel_path, index=False)
        
        # Copy to uploaded_baseline for compatibility with the synthetic generator
        uploaded_baseline_path = os.path.join(FLASK_APP_DIR, "uploaded_baseline.xlsx")
        df_combined.to_excel(uploaded_baseline_path, index=False)
                
        gen_script = os.path.join(FLASK_APP_DIR, "generate_synthetic_faults.py")
        gen_result = subprocess.run([sys.executable, gen_script], cwd=FLASK_APP_DIR, capture_output=True, text=True)
        if gen_result.returncode != 0:
            raise Exception(f"Fault augmentation failed: {gen_result.stderr}")
            
        train_script = os.path.join(FLASK_APP_DIR, "train_xgboost.py")
        result = subprocess.run([sys.executable, train_script], cwd=FLASK_APP_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Training failed: {result.stderr}")
            
        status = "warning" if final_row_count <= 500 else "success"
        message = "Dataset is small. Prediction is for demonstration only." if final_row_count <= 500 else "Dataset augmented and model trained successfully"
            
        return {
            "status": status, 
            "message": message,
            "stats": {
                "existing_rows": existing_row_count,
                "new_rows": new_row_count,
                "final_rows": final_row_count,
                "mode_counts": mode_counts
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve frontend build if it exists
frontend_build_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_build_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build_path, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for React Router / SPA routing
        requested_file = os.path.join(frontend_build_path, full_path)
        if os.path.isfile(requested_file):
            return FileResponse(requested_file)
        return FileResponse(os.path.join(frontend_build_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
