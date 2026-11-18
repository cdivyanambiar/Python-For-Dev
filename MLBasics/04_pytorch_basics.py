"""04 - PyTorch basics: tensors, autograd, nn.Module, Dataset/DataLoader and the training loop.

Run: py 04_pytorch_basics.py
Install (CPU): py -m pip install torch --index-url https://download.pytorch.org/whl/cpu

PyTorch = a library for deep learning (neural networks). Think: NumPy + GPU support + automatic gradients.

The 5-step training loop to remember for interviews:
    optimizer.zero_grad()      # 1. clear old gradients (PyTorch ADDS them up by default)
    pred = model(xb)           # 2. forward pass: make predictions
    loss = loss_fn(pred, yb)   # 3. measure how wrong
    loss.backward()            # 4. backprop: compute d(loss)/d(every parameter)
    optimizer.step()           # 5. nudge the weights
It's exactly what 01_ml_basics.py did by hand, now done by PyTorch.
"""
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

torch.manual_seed(0)                                # repeatable randomness (same idea as a NumPy seed)
# A GPU does thousands of small calculations at once, which is why deep learning loves it.
device = "cuda" if torch.cuda.is_available() else "cpu"    # same code runs on GPU when available


def tensor_basics() -> None:
    """Tensors are NumPy-like arrays that can live on a GPU and track gradients."""
    print("=== 1. Tensors ===")
    a = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
    b = torch.ones(2, 2)
    print("a + b =\n", a + b)                       # element by element
    print("a @ b (matrix multiply) =\n", a @ b)
    # shape = size, dtype = number type (float32 = decimal), device = CPU or GPU
    print("shape:", a.shape, "dtype:", a.dtype, "device:", a.device)
    print("reshape to (4,):", a.reshape(4))         # same data, new shape (2x2 -> line of 4)
    print("mean over rows (dim=0):", a.mean(dim=0)) # dim = PyTorch's name for NumPy's axis
    print("to numpy:", a.numpy().tolist(), "| from numpy: torch.from_numpy(arr)\n")


def autograd_basics() -> None:
    """Autograd records operations and computes derivatives for us."""
    # In 01_ml_basics.py we wrote the gradient formula (dw = ...) BY HAND. PyTorch records every
    # operation on a tracked tensor and computes gradients AUTOMATICALLY with .backward().
    # This is what makes training networks with millions of weights possible.
    print("=== 2. Autograd ===")
    x = torch.tensor(3.0, requires_grad=True)       # "track everything done with x"
    y = x ** 2 + 2 * x + 1                          # dy/dx = 2x + 2 = 8 at x=3
    y.backward()                                    # work out the slope
    print(f"y = x^2 + 2x + 1 at x=3 -> y={y.item()}, dy/dx={x.grad.item()} (expected 8)\n")


def regression_with_nn() -> None:
    """Simplest model: nn.Linear learns y = 2x + 1 (same as linear regression)."""
    print("=== 3. Linear regression with nn.Linear ===")
    # linspace = 100 evenly spaced numbers 0..10; unsqueeze(1) makes it a column of shape (100, 1)
    # because models expect "rows x features": 100 samples, 1 feature.
    X = torch.linspace(0, 10, 100).unsqueeze(1)
    y = 2 * X + 1 + 0.5 * torch.randn_like(X)       # true rule + noise

    model = nn.Linear(in_features=1, out_features=1)   # a layer computing w*x + b
    loss_fn = nn.MSELoss()                              # mean squared error, same as before
    # OPTIMIZER = the thing that updates weights. SGD = plain gradient descent, lr = step size.
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

    for epoch in range(500):
        optimizer.zero_grad()
        loss = loss_fn(model(X), y)
        loss.backward()
        optimizer.step()
        if epoch % 100 == 0:
            print(f"epoch {epoch:3d} loss={loss.item():.4f}")   # .item() -> plain Python number
    print(f"learned w={model.weight.item():.2f} (true 2), b={model.bias.item():.2f} (true 1)\n")


class Classifier(nn.Module):
    """A small feed-forward neural network (MLP). Layers go in __init__, the data flow in forward()."""
    # nn.Module = base class for every PyTorch model. You call model(x); PyTorch calls forward(x) for you.

    def __init__(self, n_features: int, n_classes: int):
        """Two hidden layers with ReLU non-linearity and dropout for regularization."""
        super().__init__()
        # nn.Sequential = layers run IN ORDER, like a pipeline: 2 inputs -> 32 -> 16 -> 3 outputs.
        # Each Linear layer is a set of weighted sums; the 32 and 16 "hidden" neurons learn useful
        # in-between patterns.
        self.net = nn.Sequential(
            nn.Linear(n_features, 32),
            # ReLU: "if negative make it 0, else keep it". Without it, stacked linear layers are still
            # just one straight line. ReLU lets the network learn CURVES and shapes.
            nn.ReLU(),
            # Dropout: during training, randomly switch off 10% of neurons each step so the network can't
            # rely on any single one -> less overfitting (like a team where anyone might be absent).
            nn.Dropout(0.1),
            nn.Linear(32, 16),
            nn.ReLU(),
            # Output = LOGITS: 3 raw scores, one per class (not probabilities yet).
            nn.Linear(16, n_classes),               # CrossEntropyLoss applies softmax itself
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return logits of shape (batch, n_classes)."""
        return self.net(x)


def classification_with_mlp() -> None:
    """3-class problem: points in 2-D split by distance from the origin into rings (not linearly separable)."""
    # Inner circle = class 0, middle ring = 1, outer = 2. A straight line CAN'T separate rings,
    # so we need a neural network with ReLU.
    print("=== 4. Multi-class classification with an MLP + DataLoader ===")
    n = 1500
    X = torch.randn(n, 2) * 2                       # random 2-D points
    r = X.norm(dim=1)                               # distance of each point from the centre
    # torch.where(cond, a, b) = "if cond then a else b" for every element
    y = torch.where(r < 1.5, 0, torch.where(r < 3.0, 1, 2))     # class labels must be int64 (long)

    dataset = TensorDataset(X, y)                   # pairs each input row with its label
    train_ds, test_ds = random_split(dataset, [1200, 300])     # train / test split
    # DataLoader feeds data in MINI-BATCHES of 64 rows, reshuffled every epoch.
    # Batches use less memory and the small randomness actually helps learning.
    train_dl = DataLoader(train_ds, batch_size=64, shuffle=True)
    test_dl = DataLoader(test_ds, batch_size=256)

    model = Classifier(n_features=2, n_classes=3).to(device)
    # CrossEntropyLoss = loss for multi-class: turns logits into probabilities (softmax) internally
    # and punishes a low probability on the correct class.
    loss_fn = nn.CrossEntropyLoss()
    # Adam = smarter optimizer that adapts the step size for each weight automatically; a good default.
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    for epoch in range(30):
        model.train()                               # "training mode": dropout ON
        total = 0.0
        for xb, yb in train_dl:                     # one mini-batch at a time
            xb, yb = xb.to(device), yb.to(device)   # data must be on the same device as the model
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(xb)
        if epoch % 10 == 0 or epoch == 29:
            print(f"epoch {epoch:2d} train loss={total / len(train_ds):.4f}  test acc={evaluate(model, test_dl):.3f}")

    # SAVE / LOAD: state_dict = dictionary of all learned numbers. Save that (not the whole object).
    # To load: build an empty model of the same shape, then pour the weights in.
    # weights_only=True = safe loading; refuses to run arbitrary code hidden in the file.
    torch.save(model.state_dict(), "mlp.pt")
    loaded = Classifier(2, 3)
    loaded.load_state_dict(torch.load("mlp.pt", weights_only=True))
    loaded.eval()
    with torch.no_grad():
        # softmax turns logits into probabilities that add up to 1, e.g. [0.99, 0.01, 0.00] = 99% inner circle
        probs = torch.softmax(loaded(torch.tensor([[0.5, 0.5], [2.0, 1.0], [3.5, 2.0]])), dim=1)
    print("predictions for 3 new points (inner, middle, outer ring):", probs.argmax(dim=1).tolist())
    print("probabilities:\n", probs.round(decimals=2))

    import os
    os.remove("mlp.pt")


def evaluate(model: nn.Module, loader: DataLoader) -> float:
    """Accuracy on a dataset. eval() disables dropout; no_grad() skips gradient tracking (faster, less memory)."""
    model.eval()                                    # "test mode": dropout OFF, use the full network
    correct = 0
    with torch.no_grad():                           # not learning here, so don't record for gradients
        for xb, yb in loader:
            pred = model(xb.to(device)).argmax(dim=1)   # pick the class with the highest logit
            correct += (pred == yb.to(device)).sum().item()
    return correct / len(loader.dataset)


if __name__ == "__main__":
    tensor_basics()
    autograd_basics()
    regression_with_nn()
    classification_with_mlp()
