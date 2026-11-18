# ML Basics – Interview Prep

Run each file in order with `py <file>.py`. Every file prints what it does, so read the code and the output together.

Each `.py` file has plain-language comments explaining every step.

| File | Topic | Needs |
|------|-------|-------|
| `01_ml_basics.py` | Core ML ideas from scratch with NumPy: data split, loss, gradient descent, overfitting, decision tree | numpy |
| `02_regression.py` | Regression: Linear, Ridge/Lasso, Polynomial, Random Forest, metrics | numpy, scikit-learn |
| `03_classification.py` | Classification: Logistic Regression, Decision Tree, KNN, metrics, thresholds | numpy, scikit-learn |
| `04_pytorch_basics.py` | PyTorch: tensors, autograd, `nn.Module`, training loop (regression + classification) | torch |
| `05_rag_basics.py` | RAG: chunking, embeddings, vector search, prompt building, generation, per-customer filtering (reads `rag_docs/*.md`) | numpy, scikit-learn |
| `06_text_to_sql_basics.py` | Text-to-SQL: schema prompt, generated SQL, SQL validation, tenant isolation, self-correction, device telemetry questions | standard library only |
| `07_interview_quick_templates.py` | **What to type in a 1-hour interview**: scikit-learn templates for classification, pandas pipelines, regression, tuning, imbalanced data, clustering and saving a model, plus a cheat sheet | numpy, pandas, scikit-learn |

Install: `py -m pip install numpy scikit-learn` and `py -m pip install torch --index-url https://download.pytorch.org/whl/cpu`

---

## 1. What is Machine Learning?

Instead of writing rules by hand, we give the computer **examples** (data) and it **learns a function** `f(X) -> y`.

- **X (features)**: input columns, e.g. CPU %, memory, temperature.
- **y (label/target)**: what we want to predict, e.g. "will fail" or "latency in ms".
- **Model**: a function with parameters (weights) like `y = w*x + b`.
- **Training**: adjusting weights so predictions are close to the true labels.
- **Inference**: using the trained model on new data.

### Types of ML

| Type | Has labels? | Examples |
|------|-------------|----------|
| Supervised | Yes | Regression (predict a number), Classification (predict a class) |
| Unsupervised | No | Clustering (K-Means), dimensionality reduction (PCA), anomaly detection |
| Reinforcement | Reward signal | Game playing, robotics |
| Self-supervised | Labels made from data | LLM pre-training (predict next word) |

### Regression vs Classification

| | Regression | Classification |
|---|---|---|
| Output | Continuous number (price, latency) | Category (spam / not spam) |
| Typical loss | MSE (mean squared error) | Cross-entropy (log loss) |
| Metrics | MAE, RMSE, R² | Accuracy, Precision, Recall, F1, ROC-AUC |
| Examples | Linear Regression, Random Forest Regressor | Logistic Regression, Decision Tree, SVM |

## 2. The ML workflow

1. **Define the problem** – regression or classification? What metric matters?
2. **Collect & clean data** – handle missing values, duplicates, outliers.
3. **Feature engineering** – scaling, encoding categories (one-hot), new features.
4. **Split data** – train / validation / test (e.g. 70/15/15). Never tune on the test set.
5. **Train** – fit the model on training data.
6. **Evaluate** – on validation data; tune hyperparameters (cross-validation).
7. **Test** – final, one-time check on the test set.
8. **Deploy & monitor** – watch for **data drift** and retrain when needed.

## 3. How a model learns (gradient descent)

1. Start with random weights.
2. **Forward pass**: predict `ŷ = model(X)`.
3. **Loss**: measure the error, e.g. `MSE = mean((ŷ - y)²)`.
4. **Gradient**: compute how the loss changes with each weight (`∂loss/∂w`).
5. **Update**: `w = w - learning_rate * gradient`.
6. Repeat for many **epochs** (one epoch = one pass over the training data).

- **Learning rate too high** → loss jumps around or blows up. **Too low** → very slow training.
- **Batch GD** uses all data per step; **SGD** uses 1 sample; **mini-batch** (most common) uses e.g. 32 samples.

## 4. Key concepts interviewers ask about

- **Overfitting**: great on training data, poor on new data (model memorised noise). Fix: more data, regularization (L1/L2), dropout, simpler model, early stopping, cross-validation.
- **Underfitting**: poor on both training and test data. Fix: more complex model, better features, train longer.
- **Bias–variance tradeoff**: high bias = too simple (underfit); high variance = too sensitive to training data (overfit).
- **Regularization**: add a penalty for large weights. L1 (Lasso) can push weights to exactly 0 (feature selection). L2 (Ridge) shrinks all weights.
- **Feature scaling**: StandardScaler (mean 0, std 1) or MinMaxScaler (0–1). Important for gradient descent, KNN, SVM; not needed for trees.
- **Data leakage**: information from test data leaks into training (e.g. fitting the scaler on all data). Always fit preprocessing on train only (use a `Pipeline`).
- **Cross-validation**: split training data into k folds, train on k-1, validate on 1, rotate, then average.
- **Class imbalance**: e.g. 99% normal, 1% fraud. Accuracy is misleading; use precision/recall/F1, PR-AUC, class weights, resampling (SMOTE).

## 5. Classification metrics

```
                 Predicted +    Predicted -
Actual +            TP             FN
Actual -            FP             TN
```

- **Accuracy** = (TP+TN) / all
- **Precision** = TP / (TP+FP) → "Of the items I flagged, how many were correct?" (important when false alarms are costly)
- **Recall** = TP / (TP+FN) → "Of all real positives, how many did I catch?" (important when missing a case is costly, e.g. disease, fraud)
- **F1** = 2·P·R / (P+R), the harmonic mean of precision and recall
- **ROC-AUC**: how well the model ranks positives above negatives across all thresholds (0.5 = random, 1.0 = perfect)

## 6. Regression metrics

- **MAE** = mean(|y − ŷ|), easy to interpret and robust to outliers
- **MSE** = mean((y − ŷ)²), penalises large errors more
- **RMSE** = √MSE, in the same units as y
- **R²** = 1 − SS_res/SS_tot, the fraction of variance explained (1 = perfect, 0 = same as predicting the mean)

## 7. Common algorithms – one-liners

| Algorithm | Idea | Use for |
|-----------|------|---------|
| Linear Regression | Best straight line/plane (minimise MSE) | Regression |
| Logistic Regression | Linear score → sigmoid → probability | Binary classification |
| Decision Tree | if/else splits that reduce impurity (Gini/entropy) or variance | Both |
| Random Forest | Many trees on bootstrap samples + random features, then vote/average (**bagging**) | Both |
| Gradient Boosting (XGBoost/LightGBM) | Trees added one by one, each fixing the previous errors (**boosting**) | Both, often best on tables |
| KNN | Look at the k nearest neighbours and vote/average | Both |
| SVM | Find the boundary with the widest margin; kernels allow non-linear boundaries | Mostly classification |
| K-Means | Group points around k centroids | Clustering |
| Neural Networks | Layers of linear + non-linear activations, trained with backprop | Images, text, complex patterns |

## 8. Deep learning / PyTorch essentials

- **Tensor**: an n-dimensional array (like NumPy) that can run on a GPU and track gradients.
- **Autograd**: `loss.backward()` computes all gradients automatically.
- **nn.Module**: base class for models; define layers in `__init__` and the computation in `forward`.
- **Training loop**: `zero_grad → forward → loss → backward → step`.
- **Activation functions**: ReLU (hidden layers), Sigmoid (binary output), Softmax (multi-class output).
- **Loss functions**: `MSELoss` (regression), `BCEWithLogitsLoss` (binary), `CrossEntropyLoss` (multi-class, takes raw logits).
- **Optimizers**: SGD, Adam (adaptive learning rate per parameter, a good default).
- `model.train()` / `model.eval()` turn dropout/batch-norm on or off; use `torch.no_grad()` for inference.

## 9. RAG (Retrieval-Augmented Generation)

**Problem:** LLMs don't know your private or recent data and can hallucinate.
**Solution:** retrieve relevant documents first, then give them to the LLM as context.

```
INDEXING (offline):  documents → chunk → embed → store in vector DB
QUERY (online):      question → embed → similarity search (top-k) → build prompt (context + question) → LLM → answer (+ sources)
```

- **Chunking**: split docs into pieces of about 200–1000 tokens with some overlap so context isn't cut mid-thought.
- **Embeddings**: vectors that capture meaning (e.g. OpenAI `text-embedding-3-small`, `sentence-transformers`). Similar text → nearby vectors.
- **Vector DB**: FAISS, Chroma, Pinecone, pgvector, Milvus, Weaviate. Uses ANN (approximate nearest neighbour) search such as HNSW.
- **Similarity**: cosine similarity = (a·b) / (|a||b|).
- **Improvements**: hybrid search (BM25 keywords + vectors), re-ranking with a cross-encoder, metadata filters, query rewriting, citing sources.
- **Evaluation**: retrieval quality (recall@k, MRR) and answer quality (faithfulness/groundedness, relevance), e.g. with RAGAS.
- **RAG vs fine-tuning**: RAG adds *knowledge* (easy to update, cites sources). Fine-tuning changes *behaviour/style/format*.
