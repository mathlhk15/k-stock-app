import os
from typing import Any, Dict
import numpy as np
import pandas as pd

try:
    import OpenDartReader
except Exception:
    OpenDartReader = None


def is_valid_number(v: Any) -> bool:
    return v is not None and not pd.isna(v) and np.isfinite(v)


def get_dart_reader():
    api_key = os.environ.get("DART_API_KEY")
    if api_key and OpenDartReader is not None:
        try:
            return OpenDartReader(api_key)
        except Exception:
            return None
    return None


def build_pbr_statistics(symbol: str, price_df: pd.DataFrame) -> Dict[str, Any]:
    """
    임시 안정화 버전:
    진짜 PBR이 계산되지 않으면 가격을 PBR처럼 쓰지 않고 N/A 처리.
    """
    return {
        "available": False,
        "reason": "PBR 계산 모듈 미연결",
        "current_pbr": None,
        "mean_pbr": None,
        "std_pbr": None,
        "zscore": None,
        "sample_months": 0,
    }
