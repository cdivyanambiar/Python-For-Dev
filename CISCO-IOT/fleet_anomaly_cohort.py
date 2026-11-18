"""Fleet anomaly detection with cohort baselines (the scale answer for "300M devices").

Idea: you can't fit a model per device. Compare each device with its COHORT (same hardware
model) at the same hour using a robust median/MAD z-score. Cohorts that are too small
(new hardware, cold start) fall back to the device's own history. A device is alerted only
if it stays abnormal (3 of the last 4 hours), which cuts alert noise.

Run: python fleet_anomaly_cohort.py   (needs numpy, pandas)
"""
import numpy as np
import pandas as pd

HOURS = 24
RECENT = 4          # hours examined for alerting
PERSIST = 3         # must be abnormal in this many of the RECENT hours
THRESHOLD = 3.5     # robust z threshold
MIN_COHORT = 10     # smaller cohorts use the device's own history


def make_fleet(n=300, seed=0):
    """Build fake telemetry for a fleet of devices, with a few hidden faults.

    Each device reports temperature every hour for HOURS hours. Every hardware model has its
    own normal temperature. In the last RECENT hours, 5 IR1101 devices and 1 NEW-X1 device
    overheat (+12 C). Those 6 are the "answer key" the detector must find.

    Args:
        n: number of devices.
        seed: random seed so the data is the same on every run.
    Returns:
        (telemetry table with device/model/hour/temp_c, set of truly faulty device ids)
    """
    rng = np.random.default_rng(seed)  # seeded random generator (repeatable results)
    base = {"IR1101": 55, "IR1800": 62, "IE3300": 48, "NEW-X1": 70}  # each model runs at its own normal level
    models = rng.choice(list(base), size=n, p=[0.4, 0.3, 0.28, 0.02])  # NEW-X1 is rare (2%): a tiny cohort
    devices = pd.DataFrame({"device": [f"dev{i:03d}" for i in range(n)], "model": models})  # one row per device
    tele = devices.merge(pd.DataFrame({"hour": range(HOURS)}), how="cross")  # every device x every hour
    tele["temp_c"] = tele["model"].map(base) + rng.normal(0, 1, len(tele))  # normal level + small noise

    faulty = list(devices[devices["model"] == "IR1101"]["device"].iloc[:5])  # pick 5 IR1101 devices to break
    faulty += list(devices[devices["model"] == "NEW-X1"]["device"].iloc[:1])  # and 1 new-hardware device
    m = tele["device"].isin(faulty) & (tele["hour"] >= HOURS - RECENT)  # rows: faulty devices, last RECENT hours
    tele.loc[m, "temp_c"] += 12  # inject the overheating fault
    return tele, set(faulty)


def robust_z(x: pd.Series) -> pd.Series:
    """Score how far each value is from the group's typical value, ignoring outliers.

    Uses the median and the MAD (median absolute deviation) instead of mean and standard
    deviation, so the faulty devices themselves don't distort the baseline.
    The 0.6745 factor makes the score comparable to a normal z-score.

    Args:
        x: values of one group (e.g. all devices of one model in one hour).
    Returns:
        a score per value; large positive/negative = unusually high/low.
    """
    med = x.median()  # the group's typical value
    mad = (x - med).abs().median()  # typical distance from the typical value
    if mad == 0:  # all values identical: no spread to measure against
        return pd.Series(0.0, index=x.index)
    return 0.6745 * (x - med) / mad


def score(tele: pd.DataFrame) -> pd.DataFrame:
    """Give every (device, hour) row a z score and an abnormal flag.

    Two paths:
      1. Normal: compare with the device's cohort (same model, same hour).
      2. Cold start: if the cohort has fewer than MIN_COHORT devices, a comparison with it is
         unreliable, so compare the device with its own earlier hours instead.

    Args:
        tele: telemetry table from make_fleet().
    Returns:
        a copy of the table with new columns `z` and `abnormal`.
    """
    tele = tele.copy()  # don't modify the caller's table
    cohort_size = tele.groupby(["model", "hour"])["device"].transform("nunique")  # how many peers each row has

    # path 1: compare with the cohort at the same hour
    z_cohort = tele.groupby(["model", "hour"])["temp_c"].transform(robust_z)

    # path 2 (cold start): compare with the device's own earlier hours (before the alert window)
    hist = tele[tele["hour"] < HOURS - RECENT].groupby("device")["temp_c"]  # each device's history
    med = tele["device"].map(hist.median())  # device's own typical temperature
    mad = tele["device"].map(hist.apply(lambda s: (s - s.median()).abs().median())).replace(0, np.nan)  # its own spread (0 -> NaN to avoid divide by zero)
    z_self = (0.6745 * (tele["temp_c"] - med) / mad).fillna(0)  # robust z against own history

    tele["z"] = np.where(cohort_size >= MIN_COHORT, z_cohort, z_self)  # pick the path per row
    tele["abnormal"] = tele["z"].abs() > THRESHOLD  # abnormal if far from baseline in either direction
    return tele


def alerts(scored: pd.DataFrame) -> pd.DataFrame:
    """Turn per-hour flags into device alerts, using the persistence rule.

    A device is alerted only if it was abnormal in at least PERSIST of the last RECENT hours.
    One-off blips are ignored, which reduces alert fatigue.

    Args:
        scored: output of score().
    Returns:
        one row per alerted device with its model and number of abnormal hours.
    """
    recent = scored[scored["hour"] >= HOURS - RECENT]  # only the latest hours matter for alerting
    per_dev = recent.groupby(["device", "model"])["abnormal"].sum().reset_index(name="bad_hours")  # count abnormal hours per device
    return per_dev[per_dev["bad_hours"] >= PERSIST]  # keep only persistent offenders


if __name__ == "__main__":  # runs only when this file is executed directly
    tele, truth = make_fleet()  # fake fleet + the list of truly faulty devices
    out = alerts(score(tele))  # score every row, then apply the persistence rule
    flagged = set(out["device"])  # devices the detector raised
    print(out.to_string(index=False))
    print(f"true faulty={len(truth)} flagged={len(flagged)} correct={len(flagged & truth)} false alarms={len(flagged - truth)}")
    assert flagged == truth  # note: NEW-X1 (tiny cohort) is caught by the cold-start path, and it is not flagged just for running hotter
