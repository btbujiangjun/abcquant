import json
import numpy as np
import pandas as pd 
from typing import Dict, Any

def numpy_to_python(obj):
    """递归将 numpy 类型转换为原生 python 类型"""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [numpy_to_python(v) for v in obj]
    elif isinstance(obj, (np.int64, np.int32, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, float)):
        return 0.0 if np.isnan(obj) or np.isinf(obj) else float(obj)
    elif isinstance(obj, (np.int64, np.int32, int)):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

def str_to_dict(raw_data: Any) -> Dict:
    """安全解析参数配置，支持处理转义字符串"""
    if isinstance(raw_data, dict):
        return raw_data
    if not isinstance(raw_data, str) or not raw_data.strip():
        return {}
    
    try:
        parsed = json.loads(raw_data)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        raise e


