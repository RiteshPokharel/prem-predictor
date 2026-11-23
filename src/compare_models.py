"""Compare different ML models using the same week-by-week walk-forward test.

Run:  python src/compare_models.py
"""
import sys, warnings, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
import train
from features import build_features, STATS_FEATURES, MARKET_FEATURES

cands = {
  "Logistic regression": lambda: make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)),
  "Random forest": lambda: make_pipeline(SimpleImputer(), RandomForestClassifier(n_estimators=300, min_samples_leaf=20, n_jobs=-1, random_state=0)),
  "Gradient boosting": lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_depth=3, min_samples_leaf=40, random_state=0),
  "K-nearest neighbours": lambda: make_pipeline(SimpleImputer(), StandardScaler(), KNeighborsClassifier(n_neighbors=75)),
  "Neural network": lambda: make_pipeline(SimpleImputer(), StandardScaler(), MLPClassifier(hidden_layer_sizes=(16,), alpha=1.0, max_iter=1000, random_state=0)),
}
df, _ = build_features()
test = df["Season"].isin(train.TEST_SEASONS).to_numpy(); y = df.loc[test, "FTR"]
feats = STATS_FEATURES + MARKET_FEATURES
for name, mk in cands.items():
    train.make_model = mk
    t = time.time()
    p = train.walk_forward(df, feats)
    s = train.score(y, p[test])
    print(f"{name:22s} acc {s['accuracy']*100:.1f}%  logloss {s['log_loss']:.4f}  ({time.time()-t:.0f}s)", flush=True)
