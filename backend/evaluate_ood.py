import os
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")

IN_DIST_FILE = os.path.join(DATA_DIR, "augmented_telemetry_dataset.xlsx")
OOD_FILE = os.path.join(DATA_DIR, "synthetic_ood_dataset.csv")
REPORT_FILE = os.path.join(OUTPUTS_DIR, "ood_evaluation_report.txt")

# We will import the inference pipeline directly
from predict_fault import init_ml_model, run_inference

def evaluate():
    print("Initializing ML Models...")
    init_ml_model(os.path.join(PROJECT_ROOT, "models"))
    
    print("Loading test data...")
    df_in = pd.read_excel(IN_DIST_FILE).sample(n=3000, random_state=1)
    df_ood = pd.read_csv(OOD_FILE).sample(n=3000, random_state=1)
    
    # We must feed sequences of length 60
    # Let's write a helper to batch
    def get_predictions(df, is_true_ood):
        preds = []
        scores = []
        is_oods = []
        for i in range(0, len(df) - 60, 60):
            window = df.iloc[i:i+60].copy()
            window = window.reset_index(drop=True)
            res = run_inference(window, os.path.join(PROJECT_ROOT, "models"))
            preds.append(res["predicted_class"])
            scores.append(res["ood_score"])
            is_oods.append(1 if res["is_ood"] else 0)
        return is_oods, scores, preds
        
    print("Evaluating In-Distribution (Normal/Known Faults)...")
    in_ood_preds, in_scores, in_classes = get_predictions(df_in, False)
    
    print("Evaluating Out-of-Distribution (Unknown Anomalies)...")
    ood_ood_preds, ood_scores, ood_classes = get_predictions(df_ood, True)
    
    y_true = [0]*len(in_ood_preds) + [1]*len(ood_ood_preds)
    y_pred = in_ood_preds + ood_ood_preds
    y_scores = in_scores + ood_scores # Note: here higher score = more anomalous
    
    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    auroc = roc_auc_score(y_true, y_scores)
    
    # False Positive Rate on normal data
    fpr = np.mean(in_ood_preds)
    
    report = []
    report.append("=== Out-of-Distribution (OOD) Evaluation Report ===")
    report.append(f"Tested on {len(in_ood_preds)} In-Dist windows and {len(ood_ood_preds)} OOD windows.")
    report.append("")
    report.append("--- OOD Detection Performance ---")
    report.append(f"AUROC (Separation Power):     {auroc:.4f}")
    report.append(f"OOD Recall (Sensitivity):     {recall*100:.2f}%")
    report.append(f"OOD Precision:                {precision*100:.2f}%")
    report.append(f"OOD F1-Score:                 {f1:.4f}")
    report.append(f"False Positive Rate (FPR):    {fpr*100:.2f}% (Normal cycles incorrectly flagged as OOD)")
    report.append("")
    report.append("--- Known Samples Incorrectly Rejected as OOD ---")
    incorrect_in = [i for i, p in enumerate(in_ood_preds) if p == 1]
    report.append(f"Count: {len(incorrect_in)} out of {len(in_ood_preds)}")
    if incorrect_in:
        report.append(f"Example original known class predicted as OOD: {in_classes[incorrect_in[0]]}")
        
    report.append("")
    report.append("--- Examples of Detected Synthetic Unknown Patterns ---")
    correct_ood = [i for i, p in enumerate(ood_ood_preds) if p == 1]
    if correct_ood:
        report.append(f"Successfully caught anomaly with score {ood_scores[correct_ood[0]]:.4f}")
        
    report_text = "\n".join(report)
    print(report_text)
    
    with open(REPORT_FILE, 'w') as f:
        f.write(report_text)
        
if __name__ == "__main__":
    evaluate()
