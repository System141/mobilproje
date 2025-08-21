"""
Cython optimized modules for ERP Platform
"""

# Try to import Cython modules, fall back to Python if not available
try:
    from .csv_processor_cy import CSVProcessorCy as CSVProcessor
    from .json_processor_cy import JSONProcessorCy as JSONProcessor
    from .sap_transformer_cy import SAPTransformerCy as SAPTransformer
    from .math_utils_cy import (
        fast_sum, fast_mean, fast_std, fast_median,
        vector_operations, matrix_operations
    )
    from .string_utils_cy import (
        fast_string_clean, fast_string_split, 
        sap_string_normalize, json_string_escape
    )
    CYTHON_AVAILABLE = True
except ImportError:
    # Fallback to Python implementations
    from ..processors.csv_processor import CSVProcessor
    from ..processors.json_processor import JSONProcessor
    CYTHON_AVAILABLE = False

__all__ = [
    'CSVProcessor',
    'JSONProcessor', 
    'SAPTransformer',
    'CYTHON_AVAILABLE'
]

if CYTHON_AVAILABLE:
    __all__.extend([
        'fast_sum', 'fast_mean', 'fast_std', 'fast_median',
        'vector_operations', 'matrix_operations',
        'fast_string_clean', 'fast_string_split',
        'sap_string_normalize', 'json_string_escape'
    ])