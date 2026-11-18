"""03 - Classification models with scikit-learn: how they work and how to evaluate them.

Run: py 03_classification.py

Classification = predict a CATEGORY (fail / ok, spam / not spam, cat / dog / bird).

How each model works (plain language):
  - LogisticRegression : weighted sum of features z = w.x + b -> sigmoid(z) = probability -> threshold (0.5).
                         Draws a straight-line boundary between classes.
  - DecisionTree       : yes/no flowchart; each question is chosen to make groups as "pure" as possible
                         (mostly one class), measured by Gini impurity.
  - RandomForest       : many different trees each VOTE; majority wins.
  - KNN                : "tell me who your neighbours are" - find the k most similar training rows and
                         take a majority vote. Needs scaling, else "distance" is dominated by big features.
  - GradientBoosting   : builds trees ONE AFTER ANOTHER, each focusing on the previous trees' mistakes
                         (like revising only the questions you got wrong). Often the best on tables;
                         XGBoost / LightGBM are faster versions.

Metrics (plain language):
  accuracy  = % of all predictions correct (MISLEADING when one class is rare)
  precision = when it says "failure", how often it's right (high = few false alarms)
  recall    = of all real failures, how many it caught (high = few misses)
  f1        = one balance score of precision and recall
  roc-auc   = how well it RANKS failures above normal ones, regardless of threshold (0.5 = coin flip, 1 = perfect)
"""
import numpy as np
from sklearn.datasets import load_iris, make_classification
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text


def binary_imbalanced_demo() -> None:
    """Device-failure style problem: only ~10% positives, so accuracy alone is misleading."""
    print("=== Binary classification on IMBALANCED data (10% positive) ===")
    # Fake data: 2000 rows, 8 features (only 5 actually useful).
    # weights=[0.9, 0.1] -> 90% class 0 (normal), 10% class 1 (failure) = IMBALANCED, like real life
    # (fraud, failures, diseases are rare).
    X, y = make_classification(n_samples=2000, n_features=8, n_informative=5,
                               weights=[0.9, 0.1], random_state=1)
    # stratify keeps the same 90/10 ratio in train and test (otherwise test might get very few failures)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=1)

    # THE DUMMY TRAP: always saying "no failure" gets ~90% accuracy but NEVER catches a failure.
    # Lesson: with imbalanced data, accuracy lies -> look at precision / recall / F1.
    baseline = np.zeros_like(y_te)                  # "always predict 0" dummy model
    print(f"Dummy 'always 0' accuracy = {accuracy_score(y_te, baseline):.3f}  <- high accuracy, useless model!\n")

    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression()),
        # class_weight="balanced": mistakes on the rare class count ~9x more -> model tries harder to catch them
        "LogReg balanced": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced")),
        "DecisionTree": DecisionTreeClassifier(max_depth=5, random_state=0),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=0),
        "KNN (k=7)": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=7)),
        "GradientBoosting": GradientBoostingClassifier(random_state=0),
    }
    print(f"{'model':20s} {'acc':>6s} {'prec':>6s} {'recall':>6s} {'f1':>6s} {'rocauc':>6s}")
    for name, m in models.items():
        m.fit(X_tr, y_tr)
        pred = m.predict(X_te)                      # predict       -> final answer 0 or 1
        # predict_proba -> probabilities per class, e.g. [0.8, 0.2]; [:, 1] takes the "class 1" column
        proba = m.predict_proba(X_te)[:, 1]         # probability of class 1, used for ROC-AUC
        print(f"{name:20s} {accuracy_score(y_te, pred):6.3f} {precision_score(y_te, pred):6.3f} "
              f"{recall_score(y_te, pred):6.3f} {f1_score(y_te, pred):6.3f} {roc_auc_score(y_te, proba):6.3f}")
    print("class_weight='balanced' trades precision for much better recall on the rare class.\n")

    # CONFUSION MATRIX: a 2x2 count of right/wrong answers by type.
    # Every other metric (precision, recall, ...) is calculated from these 4 numbers.
    #   TN = said normal, was normal    FP = said fail, was normal (false alarm)
    #   FN = said normal, was fail (missed)   TP = said fail, was fail
    print("=== Confusion matrix (LogisticRegression) ===")
    cm = confusion_matrix(y_te, models["LogisticRegression"].predict(X_te))
    print("            pred 0  pred 1")
    print(f"actual 0   TN={cm[0,0]:4d} FP={cm[0,1]:4d}")
    print(f"actual 1   FN={cm[1,0]:4d} TP={cm[1,1]:4d}\n")

    # THRESHOLD TUNING: default rule is "probability >= 0.5 -> failure"; you can move that line.
    #   Lower (0.2)  -> flag more -> catch more failures (recall up), more false alarms (precision down).
    #                   Good for disease screening / fraud, where missing a case is costly.
    #   Higher (0.7) -> flag only when very sure -> few false alarms, more misses.
    #                   Good for spam filtering, where losing a real email is costly.
    print("=== Threshold tuning: precision vs recall tradeoff ===")
    proba = models["LogisticRegression"].predict_proba(X_te)[:, 1]
    for t in (0.2, 0.35, 0.5, 0.7):
        pred = (proba >= t).astype(int)
        print(f"threshold={t:.2f}  precision={precision_score(y_te, pred, zero_division=0):.3f}  "
              f"recall={recall_score(y_te, pred):.3f}")
    print("Lower threshold -> catch more failures (recall up) but more false alarms (precision down).\n")


def multiclass_demo() -> None:
    """Iris flowers: 3 classes, 4 features. Shows a readable decision tree and hyperparameter tuning."""
    # Iris = famous small dataset: 150 flowers, 3 species, 4 measurements (petal/sepal length & width).
    print("=== Multi-class classification (Iris, 3 classes) ===")
    data = load_iris()
    X_tr, X_te, y_tr, y_te = train_test_split(data.data, data.target, test_size=0.3,
                                              stratify=data.target, random_state=0)

    # export_text prints the tree's actual if/else rules - you can read the model like a program.
    tree = DecisionTreeClassifier(max_depth=3, random_state=0).fit(X_tr, y_tr)
    print("Learned decision tree rules (this IS the model):")
    print(export_text(tree, feature_names=list(data.feature_names)))

    # GridSearchCV tries EVERY combination of settings, scores each with 5-fold cross-validation,
    # and keeps the best.
    #   HYPERPARAMETERS = settings YOU choose before training (n_estimators = number of trees,
    #                     max_depth = how deep each tree is).
    #   PARAMETERS      = values the model LEARNS during training (weights, split points).
    print("Hyperparameter tuning with GridSearchCV (5-fold CV on train set only):")
    grid = GridSearchCV(RandomForestClassifier(random_state=0),
                        {"n_estimators": [50, 200], "max_depth": [2, 4, None]}, cv=5)
    grid.fit(X_tr, y_tr)
    print(f"best params={grid.best_params_}  CV accuracy={grid.best_score_:.3f}")
    # classification_report = precision / recall / F1 for each class
    print(classification_report(y_te, grid.predict(X_te), target_names=data.target_names))

    sample = [[6.0, 2.9, 4.5, 1.5]]
    probs = grid.predict_proba(sample)[0]
    # np.argmax(probs) = position of the highest probability = predicted class
    print("New flower", sample[0], "->", data.target_names[int(np.argmax(probs))], "probs:", np.round(probs, 2))


if __name__ == "__main__":
    binary_imbalanced_demo()
    multiclass_demo()
