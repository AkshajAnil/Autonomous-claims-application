import os
import re
import pickle
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import requests
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, precision_recall_curve, auc, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from typing import Any

# Global model details cache
_MODEL_DATA = None

UNIFIED_FEATURES = [
    "months_as_customer",
    "age",
    "policy_csl",
    "policy_deductable",
    "policy_annual_premium",
    "umbrella_limit",
    "insured_sex",
    "insured_education_level",
    "insured_occupation",
    "insured_hobbies",
    "insured_relationship",
    "capital_gains",
    "capital_loss",
    "incident_type",
    "collision_type",
    "incident_severity",
    "authorities_contacted",
    "incident_hour_of_the_day",
    "number_of_vehicles_involved",
    "property_damage",
    "bodily_injuries",
    "witnesses",
    "police_report_available",
    "total_claim_amount",
    "injury_claim",
    "property_claim",
    "vehicle_claim",
    "auto_make",
    "auto_model",
    "auto_year"
]


def download_public_dataset() -> pd.DataFrame:
    url = "https://raw.githubusercontent.com/mwitiderrick/insurancedata/master/insurance_claims.csv"
    local_path = "app/artifacts/insurance_claims_raw.csv"
    os.makedirs("app/artifacts", exist_ok=True)
    
    if os.path.exists(local_path):
        # Remove old cached incorrect file if exists
        try:
            raw_df = pd.read_csv(local_path)
            if "months_as_customer" not in raw_df.columns:
                os.remove(local_path)
        except Exception:
            os.remove(local_path)
            
    if not os.path.exists(local_path):
        print(f"Downloading public insurance dataset from {url}...")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
            
    df = pd.read_csv(local_path)
    # Clean '? ' or '?' values
    df = df.replace('?', np.nan)
    return df


def train_model() -> None:
    df_raw = download_public_dataset()
    
    # 1. Map real dataset features directly without synthetic generation
    df = pd.DataFrame()
    df["months_as_customer"] = df_raw["months_as_customer"].fillna(0).astype(float)
    df["age"] = df_raw["age"].fillna(30).astype(float)
    df["policy_csl"] = df_raw["policy_csl"].fillna("250/500").astype(str)
    df["policy_deductable"] = df_raw["policy_deductable"].fillna(1000).astype(float)
    df["policy_annual_premium"] = df_raw["policy_annual_premium"].fillna(1200).astype(float)
    df["umbrella_limit"] = df_raw["umbrella_limit"].fillna(0).astype(float)
    df["insured_sex"] = df_raw["insured_sex"].fillna("FEMALE").astype(str)
    df["insured_education_level"] = df_raw["insured_education_level"].fillna("High School").astype(str)
    df["insured_occupation"] = df_raw["insured_occupation"].fillna("other").astype(str)
    df["insured_hobbies"] = df_raw["insured_hobbies"].fillna("reading").astype(str)
    df["insured_relationship"] = df_raw["insured_relationship"].fillna("husband").astype(str)
    df["capital_gains"] = df_raw["capital-gains"].fillna(0).astype(float)
    df["capital_loss"] = df_raw["capital-loss"].fillna(0).astype(float)
    df["incident_type"] = df_raw["incident_type"].fillna("Single Vehicle Collision").astype(str)
    df["collision_type"] = df_raw["collision_type"].fillna("Side Collision").astype(str)
    df["incident_severity"] = df_raw["incident_severity"].fillna("Minor Damage").astype(str)
    df["authorities_contacted"] = df_raw["authorities_contacted"].fillna("Police").astype(str)
    df["incident_hour_of_the_day"] = df_raw["incident_hour_of_the_day"].fillna(12).astype(float)
    df["number_of_vehicles_involved"] = df_raw["number_of_vehicles_involved"].fillna(1).astype(float)
    df["property_damage"] = df_raw["property_damage"].fillna("NO").astype(str)
    df["bodily_injuries"] = df_raw["bodily_injuries"].fillna(0).astype(float)
    df["witnesses"] = df_raw["witnesses"].fillna(0).astype(float)
    df["police_report_available"] = df_raw["police_report_available"].fillna("NO").astype(str)
    df["total_claim_amount"] = df_raw["total_claim_amount"].fillna(0).astype(float)
    df["injury_claim"] = df_raw["injury_claim"].fillna(0).astype(float)
    df["property_claim"] = df_raw["property_claim"].fillna(0).astype(float)
    df["vehicle_claim"] = df_raw["vehicle_claim"].fillna(0).astype(float)
    df["auto_make"] = df_raw["auto_make"].fillna("Toyota").astype(str)
    df["auto_model"] = df_raw["auto_model"].fillna("Camry").astype(str)
    df["auto_year"] = df_raw["auto_year"].fillna(2010).astype(float)

    # Real Label
    df["fraud_label"] = (df_raw["fraud_reported"] == "Y").astype(int)
    
    # Clean duplicates
    df = df.drop_duplicates()
    
    # Preprocessing: Encoding categoricals
    encoders = {}
    for cat_col in UNIFIED_FEATURES:
        if df[cat_col].dtype == 'object':
            le = LabelEncoder()
            df[cat_col] = le.fit_transform(df[cat_col].astype(str))
            encoders[cat_col] = le
        
    X = df[UNIFIED_FEATURES]
    y = df["fraud_label"]
    
    # 70/15/15 Split
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)
    
    # Random Oversampling to balance minority class
    train_df = pd.concat([X_train, y_train], axis=1)
    df_majority = train_df[train_df["fraud_label"] == 0]
    df_minority = train_df[train_df["fraud_label"] == 1]
    df_minority_oversampled = df_minority.sample(len(df_majority), replace=True, random_state=42)
    train_balanced = pd.concat([df_majority, df_minority_oversampled])
    
    X_train_bal = train_balanced[UNIFIED_FEATURES]
    y_train_bal = train_balanced["fraud_label"]
    
    # scale_pos_weight
    neg_count = sum(y_train_bal == 0)
    pos_count = sum(y_train_bal == 1)
    scale_weight = neg_count / max(pos_count, 1)
    
    # Hyperparameter Grid Search CV
    param_grid = {
        "max_depth": [3, 5],
        "learning_rate": [0.05, 0.1],
        "n_estimators": [50, 100],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
        "min_child_weight": [1, 3]
    }
    
    grid = GridSearchCV(
        estimator=xgb.XGBClassifier(eval_metric="logloss", random_state=42, scale_pos_weight=scale_weight),
        param_grid=param_grid,
        scoring="f1",
        cv=3,
        n_jobs=-1
    )
    grid.fit(X_train_bal, y_train_bal)
    best_model = grid.best_estimator_
    best_params = grid.best_params_
    
    # Optimal Threshold Tuning on Validation set
    val_probs = best_model.predict_proba(X_val)[:, 1]
    best_threshold = 0.5
    best_f1 = 0.0
    for th in np.linspace(0.1, 0.9, 17):
        f1 = f1_score(y_val, (val_probs >= th).astype(int))
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = th
            
    # Evaluation on Test set
    test_probs = best_model.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= best_threshold).astype(int)
    
    precision = float(precision_score(y_test, test_preds, zero_division=0))
    recall = float(recall_score(y_test, test_preds, zero_division=0))
    f1 = float(f1_score(y_test, test_preds, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, test_probs))
    
    prec_curve, rec_curve, _ = precision_recall_curve(y_test, test_probs)
    pr_auc = float(auc(rec_curve, prec_curve))
    
    cm = confusion_matrix(y_test, test_preds).tolist()
    
    metrics = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "confusion_matrix": cm,
        "best_threshold": float(best_threshold)
    }
    
    # Save Model artifacts
    max_ver = 0
    for filename in os.listdir("app/artifacts"):
        match = re.match(r"fraud_model_v(\d+)\.pkl", filename)
        if match:
            max_ver = max(max_ver, int(match.group(1)))
            
    next_ver = max_ver + 1
    model_path = f"app/artifacts/fraud_model_v{next_ver}.pkl"
    metrics_path = f"app/artifacts/fraud_model_v{next_ver}_metrics.json"
    
    model_data = {
        "model": best_model,
        "threshold": float(best_threshold),
        "best_params": best_params,
        "encoders": encoders,
        "version": next_ver,
        "feature_names": UNIFIED_FEATURES
    }
    
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)
        
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
        
    print(f"Unified XGBoost Model v{next_ver} trained on public claims dataset successfully.")


def load_model() -> dict[str, Any]:
    global _MODEL_DATA
    if _MODEL_DATA is None:
        os.makedirs("app/artifacts", exist_ok=True)
        max_ver = 0
        latest_file = None
        for filename in os.listdir("app/artifacts"):
            match = re.match(r"fraud_model_v(\d+)\.pkl", filename)
            if match:
                ver = int(match.group(1))
                if ver > max_ver:
                    max_ver = ver
                    latest_file = filename
                    
        if latest_file is None:
            train_model()
            # Scan again
            for filename in os.listdir("app/artifacts"):
                match = re.match(r"fraud_model_v(\d+)\.pkl", filename)
                if match:
                    ver = int(match.group(1))
                    if ver > max_ver:
                        max_ver = ver
                        latest_file = filename
                        
        model_path = os.path.join("app/artifacts", latest_file)
        with open(model_path, "rb") as f:
            _MODEL_DATA = pickle.load(f)
            
    return _MODEL_DATA


def calculate_shap_contributions(model: xgb.XGBClassifier, df: pd.DataFrame) -> list[dict]:
    try:
        booster = model.get_booster()
        dmat = xgb.DMatrix(df)
        contribs = booster.predict(dmat, pred_contribs=True)[0]
        # Skip bias contribution term at the end
        shap_values = contribs[:-1]
        shap_exps = []
        for feat, val in zip(UNIFIED_FEATURES, shap_values):
            shap_exps.append({
                "feature": feat,
                "impact": round(float(val), 4)
            })
        # Sort by absolute impact
        shap_exps = sorted(shap_exps, key=lambda x: abs(x["impact"]), reverse=True)
        return shap_exps
    except Exception as exc:
        print("Failed to compute SHAP values natively:", exc)
        # Fallback to feature importance if SHAP fails
        importances = model.feature_importances_
        shap_exps = []
        for feat, val in zip(UNIFIED_FEATURES, importances):
            shap_exps.append({
                "feature": feat,
                "impact": round(float(val), 4)
            })
        shap_exps = sorted(shap_exps, key=lambda x: abs(x["impact"]), reverse=True)
        return shap_exps


def predict_fraud_probability(features: dict[str, Any]) -> dict[str, Any]:
    model_data = load_model()
    model = model_data["model"]
    threshold = model_data.get("threshold", 0.5)
    encoders = model_data.get("encoders", {})
    
    # Process features input
    row = {}
    for col in UNIFIED_FEATURES:
        val = features.get(col)
        # Handle default value fallback if key is missing
        if val is None:
            if col in ["weather_verified", "location_verified", "disaster_verified"]:
                row[col] = 1
            elif col == "ocr_consistency_score":
                row[col] = 0.90
            elif col == "policy_type":
                row[col] = "IL"
            elif col == "insurance_type":
                row[col] = "Auto"
            else:
                row[col] = 0.0
        else:
            if isinstance(val, bool):
                row[col] = 1 if val else 0
            else:
                row[col] = val

    # Encode categories
    for cat_col in ["policy_type", "insurance_type"]:
        le = encoders.get(cat_col)
        if le:
            try:
                # Check classes to prevent out-of-vocabulary exceptions
                val_str = str(row[cat_col])
                if val_str in le.classes_:
                    row[cat_col] = int(le.transform([val_str])[0])
                else:
                    # Fallback to first class
                    row[cat_col] = 0
            except Exception:
                row[cat_col] = 0
                
    # Format to Pandas DataFrame
    df = pd.DataFrame([row])[UNIFIED_FEATURES]
    
    # Predict Probability
    prob = float(model.predict_proba(df)[0][1])
    
    # Map to non-technical risk score (0-100)
    risk_score = int(round(prob * 100))
    
    # Recommendation mapping based on risk score thresholds
    if risk_score < 30:
        recommendation = "AUTO_APPROVE"
    elif risk_score <= 70:
        recommendation = "ASSIGN_TO_ADJUSTER"
    else:
        recommendation = "FLAG_FOR_FRAUD_INVESTIGATION"
        
    # Calculate SHAP Impact values
    shap_explanations = calculate_shap_contributions(model, df)
    
    return {
        "fraud_probability": round(prob, 2),
        "risk_score": risk_score,
        "recommendation": recommendation,
        "shap_explanations": shap_explanations
    }
