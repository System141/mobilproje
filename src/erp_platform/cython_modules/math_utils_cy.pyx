# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized mathematical utilities for ERP calculations
"""

import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport sqrt, fabs, floor, ceil
from libc.stdlib cimport malloc, free
import asyncio

# Initialize NumPy
np.import_array()

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_sum(double[:] arr):
    """
    Fast sum calculation using Cython
    """
    cdef double result = 0.0
    cdef int i, n = arr.shape[0]
    
    for i in range(n):
        result += arr[i]
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_mean(double[:] arr):
    """
    Fast mean calculation using Cython
    """
    cdef double total = 0.0
    cdef int i, n = arr.shape[0]
    
    if n == 0:
        return 0.0
    
    for i in range(n):
        total += arr[i]
    
    return total / n

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_std(double[:] arr):
    """
    Fast standard deviation calculation using Cython
    """
    cdef double mean_val = fast_mean(arr)
    cdef double variance = 0.0
    cdef double diff
    cdef int i, n = arr.shape[0]
    
    if n <= 1:
        return 0.0
    
    for i in range(n):
        diff = arr[i] - mean_val
        variance += diff * diff
    
    variance /= (n - 1)
    return sqrt(variance)

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_median(double[:] arr):
    """
    Fast median calculation (note: modifies input array)
    """
    cdef int n = arr.shape[0]
    cdef double[:] sorted_arr = np.sort(arr)
    
    if n == 0:
        return 0.0
    elif n % 2 == 1:
        return sorted_arr[n // 2]
    else:
        return (sorted_arr[n // 2 - 1] + sorted_arr[n // 2]) / 2.0

@cython.boundscheck(False)
@cython.wraparound(False)
def vector_operations(double[:] a, double[:] b, str operation):
    """
    Fast vector operations for ERP calculations
    """
    cdef int n = a.shape[0]
    cdef double[:] result = np.zeros(n)
    cdef int i
    
    if operation == 'add':
        for i in range(n):
            result[i] = a[i] + b[i]
    elif operation == 'subtract':
        for i in range(n):
            result[i] = a[i] - b[i]
    elif operation == 'multiply':
        for i in range(n):
            result[i] = a[i] * b[i]
    elif operation == 'divide':
        for i in range(n):
            if b[i] != 0:
                result[i] = a[i] / b[i]
            else:
                result[i] = 0.0  # Handle division by zero
    
    return np.asarray(result)

@cython.boundscheck(False)
@cython.wraparound(False)
def matrix_operations(double[:, :] matrix_a, double[:, :] matrix_b, str operation):
    """
    Fast matrix operations for ERP data transformations
    """
    cdef int rows_a = matrix_a.shape[0]
    cdef int cols_a = matrix_a.shape[1]
    cdef int rows_b = matrix_b.shape[0]
    cdef int cols_b = matrix_b.shape[1]
    cdef int i, j, k
    cdef double temp
    
    if operation == 'multiply':
        if cols_a != rows_b:
            raise ValueError("Matrix dimensions don't match for multiplication")
        
        cdef double[:, :] result = np.zeros((rows_a, cols_b))
        
        for i in range(rows_a):
            for j in range(cols_b):
                temp = 0.0
                for k in range(cols_a):
                    temp += matrix_a[i, k] * matrix_b[k, j]
                result[i, j] = temp
        
        return np.asarray(result)
    
    elif operation == 'add':
        if rows_a != rows_b or cols_a != cols_b:
            raise ValueError("Matrix dimensions don't match for addition")
        
        cdef double[:, :] result = np.zeros((rows_a, cols_a))
        
        for i in range(rows_a):
            for j in range(cols_a):
                result[i, j] = matrix_a[i, j] + matrix_b[i, j]
        
        return np.asarray(result)

# SAP-specific financial calculations
@cython.boundscheck(False)
@cython.wraparound(False)
def sap_currency_conversion(double[:] amounts, double exchange_rate, int decimal_places=2):
    """
    Fast currency conversion for SAP financial data
    """
    cdef int n = amounts.shape[0]
    cdef double[:] result = np.zeros(n)
    cdef int i
    cdef double multiplier = 10.0 ** decimal_places
    
    for i in range(n):
        # Convert and round to specified decimal places
        result[i] = floor((amounts[i] * exchange_rate * multiplier) + 0.5) / multiplier
    
    return np.asarray(result)

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_percentage_calculation(double[:] values, double[:] totals):
    """
    Fast percentage calculation for SAP reporting
    """
    cdef int n = values.shape[0]
    cdef double[:] percentages = np.zeros(n)
    cdef int i
    
    for i in range(n):
        if totals[i] != 0:
            percentages[i] = (values[i] / totals[i]) * 100.0
        else:
            percentages[i] = 0.0
    
    return np.asarray(percentages)

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_tax_calculation(double[:] net_amounts, double tax_rate):
    """
    Fast tax calculation for SAP financial processing
    """
    cdef int n = net_amounts.shape[0]
    cdef double[:] tax_amounts = np.zeros(n)
    cdef double[:] gross_amounts = np.zeros(n)
    cdef int i
    cdef double tax_multiplier = tax_rate / 100.0
    
    for i in range(n):
        tax_amounts[i] = net_amounts[i] * tax_multiplier
        gross_amounts[i] = net_amounts[i] + tax_amounts[i]
    
    return np.asarray(tax_amounts), np.asarray(gross_amounts)

# Oracle-specific calculations
@cython.boundscheck(False)
@cython.wraparound(False)
def oracle_number_precision_fix(double[:] values, int precision, int scale):
    """
    Fix numeric precision for Oracle NUMBER columns
    """
    cdef int n = values.shape[0]
    cdef double[:] result = np.zeros(n)
    cdef int i
    cdef double multiplier = 10.0 ** scale
    
    for i in range(n):
        # Apply Oracle NUMBER precision/scale rules
        result[i] = floor(values[i] * multiplier + 0.5) / multiplier
    
    return np.asarray(result)

# ERP aggregation functions
@cython.boundscheck(False)
@cython.wraparound(False)
def erp_group_aggregation(long[:] group_ids, double[:] values, str agg_func):
    """
    Fast group-by aggregation for ERP data
    """
    cdef dict groups = {}
    cdef int i, n = values.shape[0]
    cdef long group_id
    cdef double value
    cdef list group_values
    
    # Group values by group_id
    for i in range(n):
        group_id = group_ids[i]
        value = values[i]
        
        if group_id not in groups:
            groups[group_id] = []
        groups[group_id].append(value)
    
    # Calculate aggregation for each group
    cdef dict results = {}
    
    for group_id, group_values in groups.items():
        values_array = np.array(group_values, dtype=np.float64)
        
        if agg_func == 'sum':
            results[group_id] = fast_sum(values_array)
        elif agg_func == 'mean':
            results[group_id] = fast_mean(values_array)
        elif agg_func == 'std':
            results[group_id] = fast_std(values_array)
        elif agg_func == 'median':
            results[group_id] = fast_median(values_array)
        elif agg_func == 'count':
            results[group_id] = len(group_values)
        elif agg_func == 'min':
            results[group_id] = min(group_values)
        elif agg_func == 'max':
            results[group_id] = max(group_values)
    
    return results

@cython.boundscheck(False)
@cython.wraparound(False)
def moving_average(double[:] values, int window_size):
    """
    Fast moving average calculation for time series ERP data
    """
    cdef int n = values.shape[0]
    cdef double[:] result = np.zeros(n)
    cdef int i, j, start_idx
    cdef double window_sum
    
    for i in range(n):
        start_idx = max(0, i - window_size + 1)
        window_sum = 0.0
        
        for j in range(start_idx, i + 1):
            window_sum += values[j]
        
        result[i] = window_sum / (i - start_idx + 1)
    
    return np.asarray(result)