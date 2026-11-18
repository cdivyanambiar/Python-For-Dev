"""01 - ML basics from scratch with NumPy (no ML library), so you can see what libraries do inside.

Run: py 01_ml_basics.py

Covers:
  1. Data -> features X and label y, then a train/test split
  2. Linear regression trained with gradient descent (forward, loss, gradient, update)
  3. Logistic regression (classification) with sigmoid + cross-entropy
  4. Feature scaling
  5. Overfitting vs underfitting (polynomial degree)
  6. Decision tree classifier: Gini impurity, best split, recursion, depth vs overfitting

COMMON TERMS USED IN ALL FILES (plain language)
  X (capital) = the INPUTS / features: a table with one row per example and one column per feature.
  y (small)   = the ANSWER / label we want to predict, one per row.
                (Capital X because it is a table/matrix; small y because it is a single column/vector.)
  NumPy array = like a Python list but much faster for maths; works on all values at once (no for loop).
  shape       = size of an array, e.g. (200, 1) = 200 rows, 1 column.
  X[:, 0]     = "all rows (:), column 0".
  axis=0      = work DOWN the columns (e.g. mean of each column); axis=1 = work ACROSS each row.
  a @ b       = matrix multiplication (multiply row-by-column and add up).
  1e-8 / 1e-9 = a tiny number (0.00000001) added so we never divide by zero or take log(0).
"""
import numpy as np

# RANDOM NUMBER GENERATOR WITH A SEED
# Computers don't make truly random numbers; they use a formula that produces numbers that LOOK random.
# The formula needs a starting number called the SEED (here 42). Same seed -> exactly the same "random"
# numbers on every run, so results are repeatable (easy to debug, compare and explain).
# 42 has no special meaning; any number works.
#   rng.uniform(0, 10, size=3) -> 3 decimals between 0 and 10, e.g. [7.74, 4.39, 8.59]
#   rng.normal(60, 10, size=3) -> 3 numbers around 60, mostly within +-10 (bell curve)
#   rng.permutation(5)         -> the numbers 0..4 in shuffled order, e.g. [2, 4, 0, 3, 1]
# Same idea elsewhere: random_state=0 in scikit-learn, torch.manual_seed(0) in PyTorch.
# Old style np.random.seed(42) also works but changes one hidden global generator for the whole program.
rng = np.random.default_rng(42)


def train_test_split(X: np.ndarray, y: np.ndarray, test_ratio: float = 0.2):
    """Shuffle the rows, then hold out a test set the model never sees during training."""
    # Think of an exam: you STUDY with some questions (train) and are TESTED on unseen ones (test).
    # If test questions were in your study material, a high score would mean nothing.
    # We shuffle first so the split isn't biased (e.g. all small values ending up in train).
    idx = rng.permutation(len(X))                   # shuffled row numbers
    n_test = int(len(X) * test_ratio)               # e.g. 20% of 200 = 40 rows for test
    test, train = idx[:n_test], idx[n_test:]
    return X[train], X[test], y[train], y[test]


def standardize(train: np.ndarray, test: np.ndarray):
    """Scale features to mean 0 and std 1. Fit on TRAIN only, otherwise test data leaks into training."""
    # Features have different scales (temperature ~60, CPU ~50, others could be 0.001 or 50,000).
    # Big-number features would dominate learning, so we put all of them on the same scale:
    # average 0, typical spread 1.
    # DATA LEAKAGE: computing mean/std using test data = peeking at the exam. Always use train only.
    mean, std = train.mean(axis=0), train.std(axis=0) + 1e-8
    return (train - mean) / std, (test - mean) / std


# ---------------------------------------------------------------------------
# 1 + 2. LINEAR REGRESSION with gradient descent
# ---------------------------------------------------------------------------
def linear_regression_demo() -> None:
    """Learn y = w*x + b. The true relation is y = 3x + 5 + noise."""
    # The model does NOT know w=3, b=5. It must discover them from data.
    #
    # GRADIENT DESCENT ANALOGY: you are blindfolded on a hill and want to reach the lowest point.
    #   loss          = your height on the hill (how wrong the model is)
    #   gradient      = which direction is uphill; we step the OPPOSITE way (hence  -= )
    #   learning rate = step size. Too big -> you jump past the bottom. Too small -> takes forever.
    #   epoch         = one full pass over the training data (we do 1000).
    print("=== Linear regression (gradient descent) ===")
    X = rng.uniform(0, 10, size=(200, 1))           # 200 rows, 1 feature, values 0..10
    y = 3 * X[:, 0] + 5 + rng.normal(0, 1, size=200)   # true rule + random noise (real data is never perfect)

    X_tr, X_te, y_tr, y_te = train_test_split(X, y)

    w, b, lr = 0.0, 0.0, 0.01                       # start from zero; lr = learning rate
    for epoch in range(1000):
        y_hat = w * X_tr[:, 0] + b                  # 1. forward pass: make a guess (y_hat = prediction)
        error = y_hat - y_tr                        # 2. how wrong each guess is
        # 3. MSE loss: one "wrongness" score. Squaring makes negatives positive (-3 and +3 count equally)
        #    and punishes big mistakes much more than small ones.
        loss = np.mean(error ** 2)
        dw = 2 * np.mean(error * X_tr[:, 0])        # 4. d(loss)/dw: which way to move w (calculus of MSE)
        db = 2 * np.mean(error)                     #    d(loss)/db: which way to move b
        w -= lr * dw                                # 5. take a small step against the gradient
        b -= lr * db
        if epoch % 200 == 0:
            print(f"epoch {epoch:4d}  loss={loss:8.3f}  w={w:.3f}  b={b:.3f}")

    pred = w * X_te[:, 0] + b                       # use the learned line on unseen test data
    mse = np.mean((pred - y_te) ** 2)
    # R2 in plain words: "how much better is my model than always guessing the average?"
    # 1 = perfect, 0 = no better than the average. 0.99 = explains 99% of the ups and downs.
    r2 = 1 - np.sum((y_te - pred) ** 2) / np.sum((y_te - y_te.mean()) ** 2)
    print(f"learned w={w:.2f} (true 3), b={b:.2f} (true 5)  test MSE={mse:.3f}  R2={r2:.3f}\n")


# ---------------------------------------------------------------------------
# 3 + 4. LOGISTIC REGRESSION (binary classification)
# ---------------------------------------------------------------------------
def sigmoid(z: np.ndarray) -> np.ndarray:
    """Squash any number into (0, 1) so it can be read as a probability."""
    # Big positive -> ~1 ("very likely yes"), big negative -> ~0, exactly 0 -> 0.5.
    return 1 / (1 + np.exp(-z))


def logistic_regression_demo() -> None:
    """Predict 'device fails' (1) from temperature and CPU load."""
    # Question: "Will this device fail?" (1 = fail, 0 = ok). Despite the name, logistic REGRESSION
    # is a CLASSIFICATION model: weighted sum -> sigmoid -> probability -> threshold -> yes/no.
    print("=== Logistic regression (classification) ===")
    n = 400
    temp = rng.normal(60, 10, n)                    # temperatures around 60
    cpu = rng.normal(50, 20, n)                     # CPU % around 50
    # Hidden rule: hot AND busy devices tend to fail (noise added so it's not perfect)
    y = ((0.08 * (temp - 60) + 0.04 * (cpu - 50) + rng.normal(0, 0.5, n)) > 0).astype(float)
    X = np.column_stack([temp, cpu])                # put temp and cpu side by side as 2 columns

    X_tr, X_te, y_tr, y_te = train_test_split(X, y)
    X_tr, X_te = standardize(X_tr, X_te)            # features on very different scales -> scale them

    w, b, lr = np.zeros(X.shape[1]), 0.0, 0.1       # one weight per feature (2), all start at 0
    for epoch in range(500):
        # X_tr @ w = temp*w1 + cpu*w2 for every row at once; sigmoid turns it into a probability
        p = sigmoid(X_tr @ w + b)                   # predicted probability of class 1 (fail)
        # Binary cross-entropy (log-loss): the wrongness score for probabilities.
        # Truth = fail and you said 0.99 -> tiny penalty. You said 0.01 -> huge penalty.
        # Confident AND wrong is punished the hardest.
        loss = -np.mean(y_tr * np.log(p + 1e-9) + (1 - y_tr) * np.log(1 - p + 1e-9))
        grad_w = X_tr.T @ (p - y_tr) / len(y_tr)    # same simple gradient form as linear regression
        grad_b = np.mean(p - y_tr)
        w -= lr * grad_w
        b -= lr * grad_b
        if epoch % 100 == 0:
            print(f"epoch {epoch:3d}  log-loss={loss:.4f}")

    # 0.5 is the THRESHOLD: probability >= 0.5 -> predict "fail". You can move it (see 03_classification.py).
    pred = (sigmoid(X_te @ w + b) >= 0.5).astype(float)   # threshold probability -> class
    # Counting right/wrong answers:
    #   TP (true positive)  = predicted fail and it really failed        (good)
    #   FP (false positive) = predicted fail but it was fine             (false alarm)
    #   FN (false negative) = predicted ok but it failed                 (missed it)
    tp = np.sum((pred == 1) & (y_te == 1))
    fp = np.sum((pred == 1) & (y_te == 0))
    fn = np.sum((pred == 0) & (y_te == 1))
    acc = np.mean(pred == y_te)                     # accuracy  = fraction of all predictions that were right
    precision = tp / (tp + fp + 1e-9)               # precision = "when I shout FAIL, how often am I right?"
    recall = tp / (tp + fn + 1e-9)                  # recall    = "of all real failures, how many did I catch?"
    # Both weights positive -> higher temperature AND higher CPU both push toward "fail".
    print(f"weights={np.round(w, 2)}  accuracy={acc:.3f}  precision={precision:.3f}  recall={recall:.3f}\n")


# ---------------------------------------------------------------------------
# 5. OVERFITTING vs UNDERFITTING
# ---------------------------------------------------------------------------
def overfitting_demo() -> None:
    """Fit polynomials of increasing degree to a few noisy points from a sine curve."""
    # Degree = how flexible/bendy the curve is.
    #   degree 1  (straight line) -> too stiff for a wave. Train AND test error high  = UNDERFIT
    #             (a student who didn't study enough)
    #   degree 3  -> follows the wave nicely. Both errors low                         = GOOD FIT
    #             (a student who understood the topic)
    #   degree 15 -> bends through every noisy point. Train error tiny, test error HUGE = OVERFIT
    #             (a student who memorised answers, then failed new questions)
    print("=== Overfitting vs underfitting (polynomial degree) ===")
    x = np.sort(rng.uniform(0, 1, 20))              # only 20 training points
    y = np.sin(2 * np.pi * x) + rng.normal(0, 0.2, 20)   # a wave + noise
    x_test = np.linspace(0, 1, 100)                 # 100 evenly spaced test points
    y_test = np.sin(2 * np.pi * x_test)             # the true wave (no noise)

    for degree in (1, 3, 15):
        coeffs = np.polyfit(x, y, degree)           # find the best curve of this degree
        train_err = np.mean((np.polyval(coeffs, x) - y) ** 2)        # polyval = use the curve to predict
        test_err = np.mean((np.polyval(coeffs, x_test) - y_test) ** 2)
        verdict = {1: "underfit (too simple)", 3: "good fit", 15: "overfit (memorised noise)"}[degree]
        print(f"degree {degree:2d}: train MSE={train_err:.4f}  test MSE={test_err:.4f}  -> {verdict}")
    print("Overfit = low train error but high test error. Underfit = both errors high.\n")


# ---------------------------------------------------------------------------
# 6. DECISION TREE (classification) from scratch
# ---------------------------------------------------------------------------
# A decision tree is a flowchart of yes/no questions learned from data, e.g.
#     is temp <= 70?  -- no  --> FAIL
#          | yes
#     is cpu <= 85?   -- no  --> FAIL
#          | yes
#          OK
# HOW IT LEARNS (greedy, top-down):
#   1. Try every feature and every possible cut-off value ("threshold").
#   2. Pick the question that splits the rows into the two PUREST groups (mostly one class each).
#   3. Repeat the same thing inside each group (recursion) until a stop rule is hit.
#   4. A LEAF (end box) predicts the majority class of the training rows that landed there.
# Stop rules (= regularization for trees): max_depth, min_samples, or the group is already pure.
# Trees need NO feature scaling: they only ask "is x <= t?", so units don't matter.


def gini(y: np.ndarray) -> float:
    """Gini impurity: chance of mislabelling a random row if you guess using the group's class mix.

    0.0 = pure (all one class). 0.5 = worst possible for 2 classes (50/50 mix).
    """
    if len(y) == 0:
        return 0.0
    _, counts = np.unique(y, return_counts=True)
    p = counts / len(y)                             # share of each class in this group
    return 1.0 - np.sum(p ** 2)


def best_split(X: np.ndarray, y: np.ndarray, min_leaf: int = 1):
    """Try every (feature, threshold) and return the one with the lowest weighted Gini of the two children.

    min_leaf = smallest allowed child; stops the tree carving out a 1-row group just to fit one noisy label.
    """
    best_feature, best_threshold, best_impurity = None, None, gini(y)   # must beat "no split"
    for f in range(X.shape[1]):
        values = np.unique(X[:, f])                 # sorted distinct values of this feature
        thresholds = (values[:-1] + values[1:]) / 2 # cut-offs halfway between neighbouring values
        for t in thresholds:
            left = X[:, f] <= t                     # True/False mask: which rows answer "yes"
            right = ~left                           # ~ flips the mask
            if left.sum() < min_leaf or right.sum() < min_leaf:
                continue                            # one side too small -> skip this question
            # weighted average: a big child counts more than a tiny one
            impurity = (left.sum() * gini(y[left]) + right.sum() * gini(y[right])) / len(y)
            if impurity < best_impurity:
                best_feature, best_threshold, best_impurity = f, t, impurity
    return best_feature, best_threshold


def build_tree(X: np.ndarray, y: np.ndarray, depth: int = 0, max_depth: int = 3, min_samples: int = 5) -> dict:
    """Recursively grow the tree. A node is a dict: either a leaf or a question with left/right children."""
    majority = int(np.bincount(y.astype(int)).argmax())    # most common class in this group
    # STOP: too deep, too few rows, or already pure -> make a leaf
    if depth >= max_depth or len(y) < min_samples or gini(y) == 0:
        return {"leaf": True, "pred": majority, "n": len(y)}
    f, t = best_split(X, y, min_leaf=max(1, min_samples // 4))   # e.g. min_samples=20 -> leaves of >= 5 rows
    if f is None:                                   # no question improves purity -> leaf
        return {"leaf": True, "pred": majority, "n": len(y)}
    left = X[:, f] <= t
    return {
        "leaf": False, "feature": f, "threshold": t,
        "left": build_tree(X[left], y[left], depth + 1, max_depth, min_samples),    # "yes" branch
        "right": build_tree(X[~left], y[~left], depth + 1, max_depth, min_samples), # "no" branch
    }


def predict_tree(node: dict, x: np.ndarray) -> int:
    """Walk from the root, answering each question, until reaching a leaf."""
    while not node["leaf"]:
        node = node["left"] if x[node["feature"]] <= node["threshold"] else node["right"]
    return node["pred"]


def print_tree(node: dict, names: list[str], indent: str = "") -> None:
    """Print the learned rules. The tree IS readable if/else code - a big plus for explaining decisions."""
    if node["leaf"]:
        print(f"{indent}-> predict {'FAIL' if node['pred'] else 'ok'}  ({node['n']} training rows)")
        return
    print(f"{indent}if {names[node['feature']]} <= {node['threshold']:.1f}:")
    print_tree(node["left"], names, indent + "    ")
    print(f"{indent}else:")
    print_tree(node["right"], names, indent + "    ")


def decision_tree_demo() -> None:
    """Device failure again, but with a rule a straight line can't draw well: fail if VERY hot OR VERY busy."""
    print("=== Decision tree (classification, from scratch) ===")
    n = 400
    temp = rng.normal(60, 10, n)
    cpu = rng.normal(50, 20, n)
    # Hidden rule (the tree must discover the 70 and 85 cut-offs by itself)
    y = ((temp > 70) | (cpu > 85)).astype(int)      # | = OR, element by element
    flip = rng.random(n) < 0.15                     # 15% of labels flipped = real-world noise / mistakes
    y[flip] = 1 - y[flip]
    X = np.column_stack([temp, cpu])
    X_tr, X_te, y_tr, y_te = train_test_split(X, y)  # note: NO scaling needed for trees

    tree = build_tree(X_tr, y_tr, max_depth=2, min_samples=20)   # min_samples=20: don't split tiny groups
    print("Learned rules (max_depth=2, min_samples=20):")
    print_tree(tree, ["temp", "cpu"])

    # Depth controls complexity, just like polynomial degree above:
    # too shallow = underfit, too deep = memorises the 15% noisy labels = overfit.
    print("\nEffect of max_depth (min_samples=1 so deep trees can memorise):")
    for depth in (1, 2, 4, 12):
        t = build_tree(X_tr, y_tr, max_depth=depth, min_samples=1)
        train_acc = np.mean([predict_tree(t, x) == label for x, label in zip(X_tr, y_tr)])
        test_acc = np.mean([predict_tree(t, x) == label for x, label in zip(X_te, y_te)])
        print(f"max_depth={depth:2d}: train acc={train_acc:.3f}  test acc={test_acc:.3f}")
    print("Deeper trees keep raising TRAIN accuracy by memorising noisy labels, but TEST accuracy drops = overfit.")
    print("Random Forest (many trees, averaged) and Gradient Boosting fix this - see 02/03 files.\n")


# Runs only when you execute this file directly (py 01_ml_basics.py), not when it is imported.
if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")               # polyfit warns at degree 15; that's the point of the demo
    linear_regression_demo()
    logistic_regression_demo()
    overfitting_demo()
    decision_tree_demo()
