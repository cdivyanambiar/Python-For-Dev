"""02 - Regression models with scikit-learn: how they work and how to evaluate them.

Run: py 02_regression.py

Regression = predict a continuous NUMBER (latency, price, temperature).

How each model works (plain language):
  - LinearRegression : gives each feature a weight, multiplies and adds: y = w1*x1 + ... + b.
                       Picks the weights with the smallest squared error (least squares).
  - Ridge (L2)       : linear + penalty alpha*sum(w^2) -> keeps weights small and calm, reduces overfitting.
                       alpha = penalty strength.
  - Lasso (L1)       : linear + penalty alpha*sum(|w|) -> can push useless weights to EXACTLY 0
                       (it picks features for you).
  - Polynomial       : creates extra features like x^2, x1*x2, so a linear model can fit CURVES.
  - DecisionTree     : a flowchart of yes/no questions ("rps > 300?" -> "cache_hit < 0.4?" -> ...).
                       Each leaf box predicts the average of the training rows that end up there.
  - RandomForest     : 200 different trees, each trained on a random sample of rows/features;
                       final answer = their AVERAGE (bagging). Like asking 200 people and averaging:
                       more stable than one person.

scikit-learn pattern (same for EVERY model):
    model.fit(X_train, y_train)     # learn
    pred = model.predict(X_test)    # use
"""
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.tree import DecisionTreeRegressor

rng = np.random.default_rng(0)                      # seeded random generator -> same data every run


def make_data(n: int = 500):
    """Synthetic API latency (ms) from requests/sec, payload KB, cache hit rate, plus 2 useless noise features."""
    rps = rng.uniform(10, 500, n)                   # requests per second: more load -> slower
    payload = rng.uniform(1, 100, n)                # request size in KB: bigger -> slower
    cache_hit = rng.uniform(0, 1, n)                # 0..1 share served from cache: more cache -> FASTER
    noise_feats = rng.normal(0, 1, (n, 2))          # random junk with NO effect; tests if models ignore it
    # Non-linear: latency grows with the SQUARE of load (faster than a straight line).
    # rng.normal(0, 5, n) adds noise because real data is never perfect.
    latency = 20 + 0.0004 * rps ** 2 + 0.8 * payload - 40 * cache_hit + rng.normal(0, 5, n)
    X = np.column_stack([rps, payload, cache_hit, noise_feats])
    return X, latency


def evaluate(name: str, model, X_tr, X_te, y_tr, y_te) -> None:
    """Fit on train, score on test with the standard regression metrics."""
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    mae = mean_absolute_error(y_te, pred)           # "on average we're off by X ms" - easiest to explain
    rmse = np.sqrt(mean_squared_error(y_te, pred))  # also in ms, but punishes big misses more
    r2 = r2_score(y_te, pred)                       # share of variation explained (1 = perfect, 0 = guess avg)
    print(f"{name:22s} MAE={mae:7.2f}  RMSE={rmse:7.2f}  R2={r2:.3f}")


def main() -> None:
    X, y = make_data()
    # 80% train / 20% test; random_state fixes the shuffle so the split is the same every run
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    # PIPELINE = a chain of steps that acts like ONE model. On .fit(), the scaler learns mean/std from
    # TRAIN data only, then the model trains -> prevents data leakage automatically.
    models = {
        "LinearRegression": make_pipeline(StandardScaler(), LinearRegression()),
        "Ridge (L2)": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Lasso (L1)": make_pipeline(StandardScaler(), Lasso(alpha=0.5)),
        "Polynomial deg2": make_pipeline(PolynomialFeatures(2), StandardScaler(), Ridge(alpha=1.0)),
        "DecisionTree": DecisionTreeRegressor(max_depth=6, random_state=0),     # max 6 questions deep
        "RandomForest": RandomForestRegressor(n_estimators=200, random_state=0),  # 200 trees
    }

    # Reading the result: Polynomial wins (can represent rps^2). A single tree is worst - its predictions
    # are "steppy" and it is sensitive to the exact data (HIGH VARIANCE). The forest fixes that by averaging.
    print("=== Test-set results (lower MAE/RMSE, higher R2 is better) ===")
    for name, model in models.items():
        evaluate(name, model, X_tr, X_te, y_tr, y_te)
    print("Polynomial features capture the rps^2 curve best. A single tree is high-variance (step-shaped);")
    print("averaging many trees (RandomForest) reduces that variance and beats the plain linear model.\n")

    # WEIGHTS: bigger number = bigger effect. NEGATIVE weight = feature REDUCES latency (cache).
    # Lasso sets the noise features to 0 = "these don't matter".
    print("=== Inside the linear model: learned weights (scaled features) ===")
    names = ["rps", "payload", "cache_hit", "noise1", "noise2"]
    lin = models["LinearRegression"][-1]            # [-1] = last step of the pipeline = the model itself
    lasso = models["Lasso (L1)"][-1]
    for n, wl, wla in zip(names, lin.coef_, lasso.coef_):   # coef_ = learned weights
        print(f"{n:10s} linear={wl:8.2f}  lasso={wla:8.2f}")
    print("Lasso pushes useless noise features to (near) 0. Negative weight = feature lowers latency.\n")

    # FEATURE IMPORTANCE: how much each feature helped the trees make good splits (they add up to 1).
    print("=== Random forest feature importance ===")
    for n, imp in sorted(zip(names, models["RandomForest"].feature_importances_), key=lambda t: -t[1]):
        print(f"{n:10s} {imp:.3f}")

    # CROSS-VALIDATION: one split can be lucky/unlucky. cv=5 cuts the TRAIN data into 5 pieces,
    # trains on 4 and tests on the 5th, repeats 5 times (each piece is the test once), then averages.
    print("\n=== 5-fold cross-validation (more reliable than a single split) ===")
    scores = cross_val_score(RandomForestRegressor(n_estimators=100, random_state=0), X_tr, y_tr, cv=5, scoring="r2")
    print(f"RandomForest R2 per fold={np.round(scores, 3)}  mean={scores.mean():.3f}")

    print("\n=== Predict for a new request ===")
    new = np.array([[400, 50, 0.2, 0, 0]])          # double brackets = a TABLE with 1 row (models need tables)
    print(f"rps=400, payload=50KB, cache_hit=0.2 -> predicted latency {models['RandomForest'].predict(new)[0]:.1f} ms")


if __name__ == "__main__":
    main()
