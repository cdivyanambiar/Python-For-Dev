"""07 - Interview quick templates: what to actually TYPE in a 1-hour ML coding round.

Run: py 07_interview_quick_templates.py

WHY THIS FILE EXISTS
  In an interview you do NOT build models from scratch (01_ml_basics.py is for UNDERSTANDING).
  You use scikit-learn: every model has the same 3 calls -> fit / predict / score.
  Memorise these templates; swap the model line and the metric, and you can handle most tasks.

HOW TO SPEND A 1-HOUR ROUND (say this structure out loud - interviewers love it)
  1. Clarify   (5 min) : regression or classification? which metric matters? is the data imbalanced?
  2. Explore   (10 min): df.shape, df.info(), df.describe(), missing values, label balance.
  3. Baseline  (10 min): a dummy model + a simple model (Logistic/Linear Regression).
  4. Improve   (10 min): a stronger model (Random Forest / Gradient Boosting), quick tuning.
  5. Evaluate  (10 min): the right metric, confusion matrix, threshold, feature importance.
  6. Discuss   (rest)  : more features, class weights, deployment, monitoring, data drift.

TEMPLATES IN THIS FILE
  T1. Classification (numbers only)          -> the 10-line core template
  T2. Real-world table with pandas            -> missing values + text categories (ColumnTransformer)
  T3. Regression                              -> predict a number
  T4. Hyperparameter tuning                   -> GridSearchCV
  T5. Imbalanced data + threshold             -> class_weight, precision/recall trade-off
  T6. Clustering (no labels)                  -> KMeans + elbow / silhouette
  T7. Save / load a model                     -> joblib
At the bottom: a cheat sheet of "which model / which metric" one-liners.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.datasets import load_breast_cancer, load_diabetes, make_blobs, make_classification
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (classification_report, confusion_matrix, f1_score, mean_absolute_error,
                             precision_score, r2_score, recall_score, roc_auc_score, silhouette_score)
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42       # one seed everywhere -> same results every run (say "for reproducibility")


# ---------------------------------------------------------------------------
# T1. CLASSIFICATION - the core template (memorise this one first)
# ---------------------------------------------------------------------------
def t1_classification() -> None:
    """Predict a category. Dataset: breast cancer (malignant vs benign), 30 numeric features."""
    print("=== T1. Classification core template ===")
    # load_* returns ready-made X (features table) and y (labels). In an interview you'd get a CSV instead.
    X, y = load_breast_cancer(return_X_y=True)

    # SPLIT: 80% train / 20% test.
    #   stratify=y        -> keep the same class ratio in both parts (important for imbalanced data)
    #   random_state      -> same split every run
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)

    # BASELINE FIRST: "always predict the most common class". Any real model must beat this.
    # Saying "let me start with a baseline" shows maturity.
    dummy = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    print(f"baseline accuracy (always majority class): {dummy.score(X_te, y_te):.3f}")

    # MODELS: same fit/predict API, so comparing them is a simple loop.
    #   make_pipeline(StandardScaler(), model) -> scaling is learned on TRAIN only (no data leakage).
    #   Linear models / KNN / SVM need scaling. Tree models (RandomForest) don't, but it doesn't hurt.
    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE),
    }
    for name, model in models.items():
        model.fit(X_tr, y_tr)                       # LEARN from training data
        pred = model.predict(X_te)                  # PREDICT classes (0/1) for unseen data
        proba = model.predict_proba(X_te)[:, 1]     # PROBABILITY of class 1 (needed for ROC-AUC)
        print(f"{name:20s} acc={model.score(X_te, y_te):.3f}  f1={f1_score(y_te, pred):.3f}  "
              f"roc_auc={roc_auc_score(y_te, proba):.3f}")

    # CROSS-VALIDATION: one split can be lucky. 5 different splits of the TRAIN data -> mean +- std.
    # Say: "I'd use cross-validation to get a more reliable estimate before touching the test set."
    scores = cross_val_score(models["LogisticRegression"], X_tr, y_tr, cv=5, scoring="f1")
    print(f"LogReg 5-fold CV f1 = {scores.mean():.3f} +- {scores.std():.3f}")

    # FULL REPORT: precision / recall / f1 per class + confusion matrix (rows = actual, cols = predicted).
    best = models["LogisticRegression"]
    print(classification_report(y_te, best.predict(X_te), target_names=["malignant", "benign"]))
    print("confusion matrix [[TN FP] [FN TP]]:\n", confusion_matrix(y_te, best.predict(X_te)), "\n")


# ---------------------------------------------------------------------------
# T2. REAL-WORLD TABLE: pandas + missing values + text categories
# ---------------------------------------------------------------------------
def make_device_dataframe(n: int = 600) -> pd.DataFrame:
    """Fake device table like an interview CSV: numbers, text columns, missing values and a label."""
    rng = np.random.default_rng(RANDOM_STATE)
    df = pd.DataFrame({
        "temp_c": rng.normal(60, 10, n),
        "cpu_pct": rng.normal(50, 20, n),
        "uptime_days": rng.integers(1, 400, n),
        "uplink": rng.choice(["cellular", "ethernet", "wifi"], n),       # TEXT category
        "model": rng.choice(["IR1101", "IR1800", "IE3400"], n),          # TEXT category
    })
    risk = 0.08 * (df.temp_c - 60) + 0.03 * (df.cpu_pct - 50) + 0.8 * (df.uplink == "cellular")
    df["failed"] = (risk + rng.normal(0, 0.7, n) > 0.6).astype(int)       # the LABEL column
    # Real data has holes: blank out ~5% of temperatures and some uplinks
    df.loc[rng.random(n) < 0.05, "temp_c"] = np.nan
    df.loc[rng.random(n) < 0.03, "uplink"] = np.nan
    return df


def t2_pandas_pipeline() -> None:
    """The template for a REAL CSV: different preprocessing for numeric vs text columns, all in one pipeline."""
    print("=== T2. pandas + ColumnTransformer (missing values + categories) ===")
    df = make_device_dataframe()                    # in an interview: df = pd.read_csv("devices.csv")

    # QUICK EDA (exploratory data analysis) - always do these 4 and comment on what you see:
    print("shape:", df.shape)                                        # rows, columns
    print("missing values per column:", df.isna().sum().to_dict())   # where are the holes?
    print("label balance:", df["failed"].value_counts(normalize=True).round(2).to_dict())  # imbalanced?
    # (also useful: df.info() for types, df.describe() for min/max/mean of numeric columns)

    X = df.drop(columns=["failed"])                 # features = everything except the label
    y = df["failed"]
    numeric = ["temp_c", "cpu_pct", "uptime_days"]
    categorical = ["uplink", "model"]

    # COLUMNTRANSFORMER = apply different steps to different columns, then glue the results together.
    #   numeric     : fill missing with the MEDIAN (robust to outliers) -> scale
    #   categorical : fill missing with the most frequent value -> ONE-HOT encode
    #                 (one-hot: "uplink=wifi" becomes 3 columns cellular/ethernet/wifi with a single 1)
    #                 handle_unknown="ignore" -> a category never seen in training won't crash prediction
    preprocess = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric),
        ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"),
                              OneHotEncoder(handle_unknown="ignore")), categorical),
    ])

    # PIPELINE = preprocessing + model as ONE object. Why it matters (say this!):
    #   - imputer/scaler/encoder are fit on TRAIN only -> no data leakage
    #   - the same steps run automatically at prediction time -> no train/serve mismatch
    #   - you can save ONE file and deploy it
    clf = Pipeline([("prep", preprocess),
                    ("model", RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE))])

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    clf.fit(X_tr, y_tr)
    pred = clf.predict(X_te)
    print(f"accuracy={clf.score(X_te, y_te):.3f}  precision={precision_score(y_te, pred):.3f}  "
          f"recall={recall_score(y_te, pred):.3f}")

    # FEATURE IMPORTANCE: which inputs mattered most. get_feature_names_out() gives the names
    # AFTER one-hot encoding (e.g. "cat__uplink_cellular").
    names = clf.named_steps["prep"].get_feature_names_out()
    importances = clf.named_steps["model"].feature_importances_
    top = sorted(zip(names, importances), key=lambda t: -t[1])[:4]
    print("top features:", [(n, round(float(i), 3)) for n, i in top])

    # PREDICT ONE NEW ROW: must be a DataFrame with the SAME column names (missing values are fine).
    new = pd.DataFrame([{"temp_c": 78, "cpu_pct": 85, "uptime_days": 30, "uplink": "cellular", "model": "IR1101"}])
    print(f"new device failure probability: {clf.predict_proba(new)[0, 1]:.2f}\n")


# ---------------------------------------------------------------------------
# T3. REGRESSION - predict a number
# ---------------------------------------------------------------------------
def t3_regression() -> None:
    """Same pattern as T1; only the model class and the metrics change."""
    print("=== T3. Regression template ===")
    # diabetes dataset: 10 numeric features -> disease progression score after 1 year (a NUMBER)
    X, y = load_diabetes(return_X_y=True)
    # no stratify for regression (y is continuous, there are no classes to balance)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

    models = {
        "Baseline (mean)": DummyRegressor(strategy="mean"),     # always predicts the training average
        "LinearRegression": make_pipeline(StandardScaler(), LinearRegression()),
        "RandomForest": RandomForestRegressor(n_estimators=300, random_state=RANDOM_STATE),
    }
    for name, model in models.items():
        pred = model.fit(X_tr, y_tr).predict(X_te)              # fit() returns the model, so calls chain
        # MAE = average error in the target's own units (easy to explain to business people)
        # R2  = share of variation explained: 1 = perfect, 0 = same as predicting the mean, <0 = worse
        print(f"{name:18s} MAE={mean_absolute_error(y_te, pred):6.1f}  R2={r2_score(y_te, pred):6.3f}")
    print("(Linear beats the forest here: small dataset + mostly linear relationships."
          " Always compare - don't assume the fancy model wins.)\n")


# ---------------------------------------------------------------------------
# T4. HYPERPARAMETER TUNING
# ---------------------------------------------------------------------------
def t4_tuning() -> None:
    """GridSearchCV = try every combination of settings with cross-validation, keep the best."""
    print("=== T4. Hyperparameter tuning (GridSearchCV) ===")
    X, y = load_breast_cancer(return_X_y=True)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)

    # HYPERPARAMETERS = settings YOU choose (number of trees, depth). PARAMETERS = what the model learns.
    # Keep the grid SMALL in an interview (2 x 3 = 6 combos x 5 folds = 30 fits). For big grids use
    # RandomizedSearchCV (tries N random combos instead of all).
    grid = GridSearchCV(
        RandomForestClassifier(random_state=RANDOM_STATE),
        param_grid={"n_estimators": [100, 300], "max_depth": [3, 6, None]},   # None = grow until pure
        cv=5,                       # 5-fold cross-validation on TRAIN only
        scoring="f1",               # optimise the metric that matters for the business
        n_jobs=-1,                  # use all CPU cores
    )
    grid.fit(X_tr, y_tr)
    print("best params:", grid.best_params_, f" best CV f1={grid.best_score_:.3f}")
    # grid itself now behaves like the best model, re-trained on all of the training data
    print(f"test f1 with best model: {f1_score(y_te, grid.predict(X_te)):.3f}")
    print("Rule: tune on train (CV), touch the TEST set only ONCE at the very end.\n")


# ---------------------------------------------------------------------------
# T5. IMBALANCED DATA + THRESHOLD
# ---------------------------------------------------------------------------
def t5_imbalanced() -> None:
    """When positives are rare (fraud, failures), accuracy lies. Fix with class_weight and a tuned threshold."""
    print("=== T5. Imbalanced data (5% positives) ===")
    X, y = make_classification(n_samples=4000, n_features=10, n_informative=5, weights=[0.95, 0.05],
                               random_state=RANDOM_STATE)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=RANDOM_STATE)

    for name, model in {
        "plain": make_pipeline(StandardScaler(), LogisticRegression()),
        # class_weight="balanced" -> errors on the rare class cost ~19x more (95/5), so the model tries
        # much harder to catch them. Simple, often enough; alternatives: SMOTE oversampling, undersampling.
        "balanced": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced")),
        "GradBoost": GradientBoostingClassifier(random_state=RANDOM_STATE),
    }.items():
        pred = model.fit(X_tr, y_tr).predict(X_te)
        print(f"{name:9s} acc={np.mean(pred == y_te):.3f}  precision={precision_score(y_te, pred):.3f}  "
              f"recall={recall_score(y_te, pred):.3f}  f1={f1_score(y_te, pred):.3f}")

    # THRESHOLD: predict() uses probability >= 0.5. Choose your own based on the cost of mistakes.
    #   missing a failure is expensive -> LOWER threshold (more recall, more false alarms)
    #   false alarms are expensive    -> HIGHER threshold (more precision, more misses)
    proba = model.predict_proba(X_te)[:, 1]         # `model` = the last one in the loop (GradBoost)
    for t in (0.2, 0.5, 0.8):
        p = (proba >= t).astype(int)
        print(f"GradBoost threshold={t}: precision={precision_score(y_te, p, zero_division=0):.3f}  "
              f"recall={recall_score(y_te, p):.3f}")
    print("Say: 'accuracy is misleading here; I'd report precision/recall/F1 or PR-AUC'.\n")


# ---------------------------------------------------------------------------
# T6. CLUSTERING (unsupervised - no labels)
# ---------------------------------------------------------------------------
def t6_clustering() -> None:
    """Group similar rows without labels, e.g. device usage profiles or customer segments."""
    print("=== T6. Clustering (KMeans) ===")
    X, _ = make_blobs(n_samples=500, centers=4, cluster_std=1.2, random_state=RANDOM_STATE)  # labels ignored
    X = StandardScaler().fit_transform(X)           # KMeans uses distance -> ALWAYS scale first

    # HOW TO PICK k (number of clusters):
    #   inertia    = total distance of points to their cluster centre (always drops as k grows;
    #                look for the "ELBOW" where it stops dropping fast)
    #   silhouette = how well each point fits its own cluster vs the next one (-1..1, higher = better)
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(X)  # n_init = 10 random restarts
        print(f"k={k}: inertia={km.inertia_:7.1f}  silhouette={silhouette_score(X, km.labels_):.3f}")

    km = KMeans(n_clusters=4, n_init=10, random_state=RANDOM_STATE).fit(X)
    print("cluster sizes:", np.bincount(km.labels_).tolist(), "-> k=4 has the best silhouette (the true number)")
    # km.predict(new_points) assigns new rows to the nearest cluster centre (km.cluster_centers_).
    print("Anomaly idea: points far from every centre are outliers (or use IsolationForest).\n")


# ---------------------------------------------------------------------------
# T7. SAVE / LOAD (deployment talk)
# ---------------------------------------------------------------------------
def t7_save_load() -> None:
    """Save the WHOLE pipeline (preprocessing + model) so serving uses exactly the training steps."""
    import os
    import joblib                                   # installed with scikit-learn; efficient for NumPy arrays

    print("=== T7. Save / load ===")
    X, y = load_breast_cancer(return_X_y=True)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X, y)
    joblib.dump(model, "model.joblib")              # save
    loaded = joblib.load("model.joblib")            # load (only load files you trust: it can run code)
    print("loaded model predicts same as original:", bool((loaded.predict(X) == model.predict(X)).all()))
    os.remove("model.joblib")
    print("Deployment talk: wrap in FastAPI, version the model, log inputs/outputs, monitor drift, retrain.\n")


# ---------------------------------------------------------------------------
# CHEAT SHEET (one-liners to say or type)
# ---------------------------------------------------------------------------
# WHICH MODEL?
#   start simple       -> LogisticRegression (classification) / LinearRegression or Ridge (regression)
#   tabular, strong    -> RandomForest*, GradientBoosting*, XGBoost / LightGBM (best on tables usually)
#   need explanation   -> DecisionTreeClassifier(max_depth=3) or logistic regression coefficients
#   few rows           -> simple linear models (less overfitting)
#   images / text      -> neural networks / pretrained models (see 04_pytorch_basics.py)
#   no labels          -> KMeans (groups), IsolationForest (anomalies), PCA (reduce columns)
#
# WHICH METRIC?
#   regression                 -> MAE (easy to explain), RMSE (punishes big errors), R2
#   balanced classification    -> accuracy, F1
#   imbalanced classification  -> precision / recall / F1, PR-AUC, ROC-AUC (NOT accuracy)
#   missing a positive is bad  -> recall;   false alarms are bad -> precision
#
# ONE-LINE MODEL SWAPS (same fit/predict everywhere):
#   from sklearn.tree import DecisionTreeClassifier      -> DecisionTreeClassifier(max_depth=4)
#   from sklearn.neighbors import KNeighborsClassifier   -> make_pipeline(StandardScaler(), KNeighborsClassifier(5))
#   from sklearn.svm import SVC                          -> make_pipeline(StandardScaler(), SVC(probability=True))
#   from sklearn.ensemble import IsolationForest         -> IsolationForest(contamination=0.05).fit_predict(X)
#   from sklearn.decomposition import PCA                -> PCA(n_components=2).fit_transform(X)
#
# PANDAS ONE-LINERS FOR EDA:
#   df.head(), df.info(), df.describe(), df.isna().sum(), df["label"].value_counts(normalize=True)
#   df.groupby("uplink")["failed"].mean()      -> failure rate per category (quick insight!)
#   df.corr(numeric_only=True)["failed"]       -> which numeric columns move with the label
#
# PHRASES THAT SCORE POINTS:
#   "Let me start with a baseline."    "I'll stratify because the classes are imbalanced."
#   "I'll put preprocessing in a Pipeline to avoid data leakage."
#   "I'll tune with cross-validation and use the test set only once."
#   "Given the cost of missing a failure, I'd optimise recall and tune the threshold."


if __name__ == "__main__":
    t1_classification()
    t2_pandas_pipeline()
    t3_regression()
    t4_tuning()
    t5_imbalanced()
    t6_clustering()
    t7_save_load()
