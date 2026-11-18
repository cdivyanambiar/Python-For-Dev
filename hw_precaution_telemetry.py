"""Hardware precaution log + telemetry: does a warning really lead to a failure?

Story: servers write hardware log lines. Some are PRECAUTION (an early warning, e.g.
"fan degraded"), some are CRITICAL (the part really failed). Telemetry (temperature, fan
speed, ECC memory errors, power) is recorded every 5 minutes.

Plan:
  1. Find the PRECAUTION lines in the log.
  2. For each one, look at the telemetry of the hour BEFORE it.
  3. Check whether a CRITICAL error followed within 24h (this is our answer key).
  4. Train a model: "telemetry before a precaution -> will it become critical?"

Run: python hw_precaution_telemetry.py   (needs numpy, pandas, scikit-learn)
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

LOOKBACK = pd.Timedelta("1h")  # how much telemetry we study before a precaution
HORIZON = pd.Timedelta("24h")  # how long we wait to see if it turns critical


def make_data(n_servers=20, days=14, seed=0):
    """Builds fake telemetry and a fake hardware log (same shape as real data)."""
    rng = np.random.default_rng(seed)
    times = pd.date_range("2026-03-01", periods=days * 288, freq="5min")  # 288 readings/day
    frames = []
    for s in range(n_servers):
        hour = times.hour.values
        frames.append(pd.DataFrame({
            "server": f"srv{s:02d}", "ts": times,
            "temp_c": 55 + 3 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 1, len(times)),
            "fan_rpm": 6000 + rng.normal(0, 80, len(times)),
            "ecc_errors": rng.poisson(0.05, len(times)),
            "power_w": 300 + rng.normal(0, 10, len(times)),
        }))
    tele = pd.concat(frames, ignore_index=True)

    logs = []
    for s in range(n_servers):
        server = f"srv{s:02d}"
        for day in (1, 3, 5, 7, 9):  # one precaution on each of these days
            ts = times[0] + pd.Timedelta(days=day, hours=int(rng.integers(2, 20)))
            logs.append((ts, server, "PRECAUTION", "hw component degraded (early warning)"))
            if rng.random() < 0.3:  # 30% of warnings are real: the machine degrades, then fails
                m = (tele["server"] == server) & (tele["ts"] >= ts - pd.Timedelta("2h")) & (tele["ts"] < ts)
                n = int(m.sum())
                tele.loc[m, "temp_c"] += np.linspace(0, 15, n)       # heating up
                tele.loc[m, "fan_rpm"] -= np.linspace(0, 1500, n)    # fan slowing down
                tele.loc[m, "ecc_errors"] += rng.poisson(1.0, n)     # memory errors rising
                logs.append((ts + pd.Timedelta(hours=int(rng.integers(1, 20))), server, "CRITICAL", "hw component failed"))
        logs.append((times[0] + pd.Timedelta(days=2), server, "INFO", "routine health check ok"))  # noise
    log = pd.DataFrame(logs, columns=["ts", "server", "severity", "message"]).sort_values("ts").reset_index(drop=True)
    return tele, log


def build_dataset(tele: pd.DataFrame, log: pd.DataFrame) -> pd.DataFrame:
    """One row per PRECAUTION event: features from telemetry before it + the real outcome."""
    precautions = log[log["severity"] == "PRECAUTION"]  # step 1: only the early warnings
    criticals = log[log["severity"] == "CRITICAL"]
    by_server = {k: g.set_index("ts").sort_index() for k, g in tele.groupby("server")}

    rows = []
    for _, ev in precautions.iterrows():
        # step 2: telemetry of the hour BEFORE the warning (never after: that would leak the future)
        w = by_server[ev["server"]].loc[ev["ts"] - LOOKBACK: ev["ts"] - pd.Timedelta("1s")]
        if len(w) < 6:
            continue  # not enough telemetry to judge
        # step 3: did a CRITICAL follow on the same server within 24h?
        later = criticals[(criticals["server"] == ev["server"]) &
                          (criticals["ts"] > ev["ts"]) & (criticals["ts"] <= ev["ts"] + HORIZON)]
        rows.append({
            "server": ev["server"], "ts": ev["ts"],
            "temp_mean": w["temp_c"].mean(),
            "temp_rise": w["temp_c"].iloc[-3:].mean() - w["temp_c"].iloc[:3].mean(),  # end minus start
            "fan_min": w["fan_rpm"].min(),
            "fan_drop": w["fan_rpm"].iloc[:3].mean() - w["fan_rpm"].iloc[-3:].mean(),
            "ecc_sum": w["ecc_errors"].sum(),
            "power_mean": w["power_w"].mean(),
            "became_critical": int(len(later) > 0),
        })
    return pd.DataFrame(rows)


FEATURES = ["temp_mean", "temp_rise", "fan_min", "fan_drop", "ecc_sum", "power_mean"]

if __name__ == "__main__":
    tele, log = make_data()
    print(log["severity"].value_counts().to_dict(), "| telemetry rows:", len(tele))

    ds = build_dataset(tele, log)
    print("precaution events:", len(ds), "| became critical:", round(ds["became_critical"].mean(), 2))
    print(ds.groupby("became_critical")[FEATURES].mean().round(1))  # real vs false alarms: look at the gap

    # split by TIME (train on earlier warnings, test on later ones): that is how it will be used in real life
    ds = ds.sort_values("ts")
    cut = int(len(ds) * 0.7)
    train, test = ds.iloc[:cut], ds.iloc[cut:]

    model = RandomForestClassifier(n_estimators=200, max_depth=4, class_weight="balanced", random_state=0)
    model.fit(train[FEATURES], train["became_critical"])
    print(classification_report(test["became_critical"], model.predict(test[FEATURES]),
                                target_names=["false alarm", "became critical"], zero_division=0))
    print(pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False).round(2))

    # score a brand-new precaution: hot, fan slowing, ECC errors rising -> should be high risk
    hot = pd.DataFrame([[68, 14, 4600, 1400, 12, 300]], columns=FEATURES)
    calm = pd.DataFrame([[55, 0, 5950, 20, 0, 300]], columns=FEATURES)
    p_hot, p_calm = model.predict_proba(hot)[0, 1], model.predict_proba(calm)[0, 1]
    print(f"risk if hot/fan slowing: {p_hot:.2f} | risk if normal telemetry: {p_calm:.2f}")
    assert p_hot > 0.8 > 0.2 > p_calm
