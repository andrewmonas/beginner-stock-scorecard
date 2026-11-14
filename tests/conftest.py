import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def series(values, end="2025-06-30") -> pd.Series:
    values = np.asarray(values, dtype=float)
    return pd.Series(values, index=pd.bdate_range(end=end, periods=len(values)))


def flat(n=300, price=100.0) -> pd.Series:
    return series([price] * n)


def steady_rise(n=300, daily=0.001, start=100.0) -> pd.Series:
    return series(start * (1 + daily) ** np.arange(n))
