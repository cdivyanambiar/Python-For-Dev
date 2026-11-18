"""08 - MLOps basics: what happens to a model AFTER the notebook (train -> ship -> watch -> retrain).

Run: py 08_mlops_basics.py      (only numpy + scikit-learn; writes to a temp folder that is deleted at the end)

WHAT IS MLOPS? (plain language)
  DevOps = reliably ship and run CODE.  MLOps = reliably ship and run MODELS.
  A model is code + DATA + training settings, and it silently gets worse as the world changes
  (new device models, summer heat, new customers). MLOps is the process + tooling that keeps it healthy.

THE LIFECYCLE THIS FILE WALKS THROUGH (one function per step)
  1. Data validation    : check the data before training (schema, ranges, missing values).
  2. Experiment tracking: record every training run (params, metrics, data version) so it's reproducible.
  3. Model registry     : store versioned models + metadata; promote to "production" only if it's better.
  4. Serving            : load the production model and answer prediction requests (validate inputs, log).
  5. Monitoring         : compare live data with training data (DATA DRIFT) and track live accuracy.
  6. Retraining         : drift detected -> retrain on fresh data -> same quality gate -> new version.

REAL TOOLS FOR EACH STEP (name-drop these in interviews)
  data validation    -> Great Expectations, pandera, TFX Data Validation
  data versioning    -> DVC, lakeFS, Delta Lake time travel
  experiment tracking-> MLflow Tracking, Weights & Biases, Neptune
  model registry     -> MLflow Model Registry, SageMaker / Vertex AI / Azure ML registries
  pipelines / CI-CD  -> Airflow, Kubeflow Pipelines, GitHub Actions, Argo
  serving            -> FastAPI + Docker + Kubernetes, BentoML, KServe, SageMaker endpoints
  monitoring         -> Evidently, WhyLabs, Arize, Prometheus + Grafana
  feature store      -> Feast, Tecton (same feature logic for training AND serving)

Here each tool is replaced by ~20 lines of plain Python so you can SEE what it does inside.
"""
import hashlib
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["temp_c", "cpu_pct", "mem_pct"]
rng = np.random.default_rng(42)


def make_device_data(n: int, temp_shift: float = 0.0, rule_shift: float = 0.0):
    """Fake device telemetry + label 'failed within 24h'.

    temp_shift : SUMMER - every device runs hotter          -> input data changes  (DATA drift)
    rule_shift : NEW FIRMWARE - devices now fail at lower temps -> the relationship changes (CONCEPT drift)
    """
    temp = rng.normal(60 + temp_shift, 8, n)
    cpu = rng.normal(50, 15, n)
    mem = rng.normal(55, 12, n)
    risk = 0.4 * (temp - (72 - rule_shift)) + 0.1 * (cpu - 60) + rng.normal(0, 1, n)
    y = (risk > 0).astype(int)
    return np.column_stack([temp, cpu, mem]), y


# ---------------------------------------------------------------------------
# 1. DATA VALIDATION - garbage in, garbage out
# ---------------------------------------------------------------------------
def validate_data(X: np.ndarray, y: np.ndarray) -> list[str]:
    """Return a list of problems (empty list = data is OK). Run this BEFORE every training job.

    Typical checks: right columns, no/limited missing values, values in a physically possible range,
    enough rows, both classes present. A failed check should STOP the pipeline, not train a bad model.
    """
    problems = []
    if X.shape[1] != len(FEATURES):
        problems.append(f"expected {len(FEATURES)} columns, got {X.shape[1]}")
    if np.isnan(X).mean() > 0.01:
        problems.append("more than 1% missing values")
    ranges = {"temp_c": (-40, 125), "cpu_pct": (0, 100), "mem_pct": (0, 100)}   # physically possible values
    for i, name in enumerate(FEATURES):
        lo, hi = ranges[name]
        bad = np.mean((X[:, i] < lo) | (X[:, i] > hi))
        if bad > 0.02:                              # allow a few sensor glitches, not many
            problems.append(f"{name}: {bad:.0%} of values outside [{lo}, {hi}]")
    if len(y) < 200:
        problems.append("too few rows to train reliably")
    if len(np.unique(y)) < 2:
        problems.append("only one class present in the labels")
    return problems


def data_fingerprint(X: np.ndarray) -> str:
    """Short hash of the training data = its VERSION. Same data -> same hash (what DVC does, simplified).

    Saved with each run so you can always answer "which data was this model trained on?"
    """
    return hashlib.sha256(np.ascontiguousarray(X).tobytes()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# 2. EXPERIMENT TRACKING - never lose "what did I try and what did it score?"
# ---------------------------------------------------------------------------
class ExperimentTracker:
    """Mini MLflow: appends one JSON line per training run to runs.jsonl.

    Real MLflow equivalent:
        with mlflow.start_run():
            mlflow.log_params({"model": "rf", "n_estimators": 200})
            mlflow.log_metric("f1", 0.91)
            mlflow.sklearn.log_model(model, "model")
    """

    def __init__(self, folder: Path):
        """Runs are stored in <folder>/runs.jsonl (JSON Lines = one JSON object per line, easy to append)."""
        self.file = folder / "runs.jsonl"

    def log_run(self, params: dict, metrics: dict, data_version: str) -> dict:
        """Record everything needed to REPRODUCE and COMPARE the run."""
        previous_runs = len(self.file.read_text().splitlines()) if self.file.exists() else 0
        run = {
            "run_id": f"run-{previous_runs + 1:03d}",    # MLflow uses random UUIDs; sequential is easier to read
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "params": params,                       # what we chose (model type, hyperparameters)
            "metrics": metrics,                     # how well it did
            "data_version": data_version,           # which data it saw
            # in real life also: git commit, library versions, random seed, who ran it
        }
        with self.file.open("a") as f:
            f.write(json.dumps(run) + "\n")
        return run

    def best_run(self, metric: str) -> dict:
        """Read all runs back and return the one with the highest metric (like sorting in the MLflow UI)."""
        runs = [json.loads(line) for line in self.file.read_text().splitlines()]
        return max(runs, key=lambda r: r["metrics"][metric])


CANDIDATES = {   # the "experiments": different models / settings to try
    "logreg": lambda: make_pipeline(StandardScaler(), LogisticRegression()),
    "rf_shallow": lambda: RandomForestClassifier(n_estimators=100, max_depth=4, random_state=0),
    "rf_deep": lambda: RandomForestClassifier(n_estimators=200, max_depth=None, random_state=0),
}


def train_and_track(X, y, tracker: ExperimentTracker):
    """Train every candidate, log each run, return the best model and its run record."""
    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)
    version = data_fingerprint(X)
    models = {}
    for name, build in CANDIDATES.items():
        model = build().fit(X_tr, y_tr)
        f1 = f1_score(y_val, model.predict(X_val))
        run = tracker.log_run({"candidate": name}, {"f1": round(f1, 4)}, version)
        models[run["run_id"]] = model
        print(f"   tracked {run['run_id']}  {name:10s} f1={f1:.3f}  data={version}")
    best = tracker.best_run("f1")
    return models[best["run_id"]], best


# ---------------------------------------------------------------------------
# 3. MODEL REGISTRY - versioned models + a quality gate before production
# ---------------------------------------------------------------------------
class ModelRegistry:
    """Mini model registry: registry/v1/, registry/v2/ ... each with model.joblib + metadata.json.

    'production.json' points at the version currently serving traffic. Rolling BACK = point it at an
    older version (no retraining needed) - a key reason registries exist.
    """

    def __init__(self, folder: Path):
        """Create the registry folder if needed."""
        self.root = folder / "registry"
        self.root.mkdir(exist_ok=True)
        self.prod_pointer = self.root / "production.json"

    def register(self, model, run: dict) -> str:
        """Save a new immutable version (never overwrite old versions - you may need to roll back)."""
        version = f"v{len([p for p in self.root.iterdir() if p.is_dir()]) + 1}"
        folder = self.root / version
        folder.mkdir()
        joblib.dump(model, folder / "model.joblib")
        (folder / "metadata.json").write_text(json.dumps({"version": version, **run}, indent=2))
        return version

    def production(self) -> dict | None:
        """Metadata of the current production model (None before the first deployment)."""
        if not self.prod_pointer.exists():
            return None
        version = json.loads(self.prod_pointer.read_text())["version"]
        return json.loads((self.root / version / "metadata.json").read_text())

    def promote_if_better(self, version: str, new_f1: float, current_f1_on_new_data: float | None,
                          min_f1: float = 0.6) -> bool:
        """QUALITY GATE: promote only if the candidate passes a minimum bar AND beats production.

        Comparing on the SAME (latest) validation data is important - an old score measured on old data
        is not a fair comparison after drift. Real pipelines add more gates: latency, model size,
        fairness checks, a shadow / canary period with a small % of live traffic.
        """
        if new_f1 < min_f1:
            print(f"   gate: {version} REJECTED (f1 {new_f1:.3f} < minimum {min_f1})")
            return False
        if current_f1_on_new_data is not None and new_f1 <= current_f1_on_new_data:
            print(f"   gate: {version} REJECTED (f1 {new_f1:.3f} not better than production {current_f1_on_new_data:.3f})")
            return False
        self.prod_pointer.write_text(json.dumps({"version": version}))
        print(f"   gate: {version} PROMOTED to production")
        return True

    def load_production(self):
        """What the serving layer calls at start-up."""
        version = json.loads(self.prod_pointer.read_text())["version"]
        return joblib.load(self.root / version / "model.joblib"), version


# ---------------------------------------------------------------------------
# 4. SERVING - turn the model into a prediction service
# ---------------------------------------------------------------------------
class PredictionService:
    """What would sit behind an HTTP endpoint. A real FastAPI version:

        app = FastAPI()
        service = PredictionService(registry)            # load the model ONCE at start-up, not per request

        class Reading(BaseModel):                         # pydantic validates types automatically
            temp_c: float; cpu_pct: float; mem_pct: float

        @app.post("/predict")
        def predict(r: Reading):
            return service.predict([r.temp_c, r.cpu_pct, r.mem_pct])

    Packaged with Docker, run on Kubernetes with several replicas + autoscaling, /health endpoint for probes.
    """

    def __init__(self, registry: ModelRegistry):
        """Load the production model once; keep a log of inputs for monitoring."""
        self.model, self.version = registry.load_production()
        self.request_log: list[list[float]] = []    # in real life: Kafka / a database / log files

    def predict(self, features: list[float]) -> dict:
        """Validate input -> predict -> log. Always return the model version (helps debugging later)."""
        if len(features) != len(FEATURES) or any(not np.isfinite(v) for v in features):
            return {"error": f"expected {len(FEATURES)} finite numbers: {FEATURES}"}
        start = time.perf_counter()
        proba = float(self.model.predict_proba([features])[0, 1])
        latency_ms = (time.perf_counter() - start) * 1000
        self.request_log.append(features)           # inputs are saved so monitoring can check for drift
        return {"fail_probability": round(proba, 3), "model_version": self.version,
                "latency_ms": round(latency_ms, 2)}


# ---------------------------------------------------------------------------
# 5. MONITORING - is the world still like the training data?
# ---------------------------------------------------------------------------
def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index: how much a feature's distribution moved between training and live data.

    How it works: cut the TRAINING values into 10 buckets (deciles), then compare what share of rows
    falls in each bucket for train vs live. Same shares -> PSI ~ 0.
    Rule of thumb:  < 0.1 no drift   |   0.1 - 0.2 moderate, watch it   |   > 0.2 significant drift, act
    (Other drift tests: Kolmogorov-Smirnov test, Jensen-Shannon distance - Evidently computes all of them.)
    """
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf           # catch live values outside the training range
    e_share = np.histogram(expected, edges)[0] / len(expected)
    a_share = np.histogram(actual, edges)[0] / len(actual)
    e_share, a_share = np.clip(e_share, 1e-6, None), np.clip(a_share, 1e-6, None)   # avoid log(0)
    return float(np.sum((a_share - e_share) * np.log(a_share / e_share)))


def monitor(train_X: np.ndarray, live_X: np.ndarray, live_y_true: np.ndarray, live_y_pred: np.ndarray,
            psi_alert: float = 0.2, f1_alert: float = 0.6) -> bool:
    """Two kinds of checks. Returns True if retraining should be triggered.

    DATA DRIFT   : inputs changed (no labels needed -> you can check it immediately, every hour).
    PERFORMANCE  : accuracy/F1 on live data. Needs the TRUE labels, which arrive LATER
                   (we only know a device failed after 24h) - so you watch drift as an early warning.
    Also watch in real life: latency, error rate, prediction distribution (e.g. suddenly 40% "fail").
    """
    drift = False
    for i, name in enumerate(FEATURES):
        score = psi(train_X[:, i], live_X[:, i])
        status = "DRIFT" if score > psi_alert else ("watch" if score > 0.1 else "ok")
        drift |= score > psi_alert
        print(f"   PSI {name:8s} = {score:5.3f}  {status}")
    live_f1 = f1_score(live_y_true, live_y_pred)
    print(f"   live F1 = {live_f1:.3f}  ({'ALERT' if live_f1 < f1_alert else 'ok'}; alert below {f1_alert})")
    return drift or live_f1 < f1_alert


# ---------------------------------------------------------------------------
# 6. THE WHOLE LOOP
# ---------------------------------------------------------------------------
def training_pipeline(X, y, tracker, registry) -> None:
    """validate -> train + track -> register -> gate. In production this is an Airflow/Kubeflow DAG,
    started on a schedule (e.g. weekly) or by a monitoring alert."""
    problems = validate_data(X, y)
    if problems:
        print("   data validation FAILED -> pipeline stopped:", problems)
        return
    print("   data validation passed")
    model, run = train_and_track(X, y, tracker)
    version = registry.register(model, run)
    print(f"   registered best run {run['run_id']} ({run['params']['candidate']}) as {version}")

    # Fair comparison: score the CURRENT production model on the SAME new validation split
    current_f1 = None
    if registry.production() is not None:
        prod_model, _ = registry.load_production()
        _, X_val, _, y_val = train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)
        current_f1 = f1_score(y_val, prod_model.predict(X_val))
    registry.promote_if_better(version, run["metrics"]["f1"], current_f1)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:      # all artifacts go here and are deleted at the end
        folder = Path(tmp)
        tracker, registry = ExperimentTracker(folder), ModelRegistry(folder)

        print("=== Step 0: a broken data delivery (sensor bug: temperatures in Fahrenheit*10) ===")
        X_bad, y_bad = make_device_data(1000)
        X_bad[:, 0] = X_bad[:, 0] * 10
        training_pipeline(X_bad, y_bad, tracker, registry)

        print("\n=== Step 1-3: first real training (spring data) ===")
        X_train, y_train = make_device_data(3000)
        training_pipeline(X_train, y_train, tracker, registry)
        if registry.production() is None:           # the gate rejected everything -> nothing to serve
            print("No production model yet - stopping. (In real life: keep serving the old model, alert the team.)")
            return

        print("\n=== Step 4: serving ===")
        service = PredictionService(registry)
        print("   normal device :", service.predict([58.0, 40.0, 50.0]))
        print("   hot + busy    :", service.predict([85.0, 92.0, 70.0]))
        print("   bad input     :", service.predict([85.0, float("nan")]))

        print("\n=== Step 5a: monitoring a normal week (no drift) ===")
        X_live, y_live = make_device_data(1500)
        for row in X_live:
            service.predict(row.tolist())           # live traffic goes through the service and gets logged
        logged = np.array(service.request_log[-1500:])
        monitor(X_train, logged, y_live, service.model.predict(logged))

        print("\n=== Step 5b: summer + new firmware (data drift AND concept drift) ===")
        X_summer, y_summer = make_device_data(1500, temp_shift=10, rule_shift=6)
        retrain = monitor(X_train, X_summer, y_summer, service.model.predict(X_summer))

        if retrain:
            print("\n=== Step 6: alert -> retrain on recent data -> same gate ===")
            X_recent, y_recent = make_device_data(3000, temp_shift=10, rule_shift=6)
            training_pipeline(X_recent, y_recent, tracker, registry)
            service = PredictionService(registry)   # in K8s: rolling update / canary to the new version
            print(f"   now serving {service.version}")
            monitor(X_recent, X_summer, y_summer, service.model.predict(X_summer))

        print("\n=== Experiment history (runs.jsonl) ===")
        for line in (folder / "runs.jsonl").read_text().splitlines():
            r = json.loads(line)
            print(f"   {r['run_id']}  {r['params']['candidate']:10s} f1={r['metrics']['f1']:.3f}  data={r['data_version']}")
        print("\nRegistry folders:", sorted(p.name for p in registry.root.iterdir()))
        print("Rollback = write an older version into production.json and restart serving.")


if __name__ == "__main__":
    main()
