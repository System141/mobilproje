#!/usr/bin/env python3
"""
Cython Performance Benchmark Suite for ERP Platform
"""

import asyncio
import csv
import io
import json
import time
import statistics
import numpy as np
from typing import Dict, List, Any
import argparse
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def generate_test_csv_data(rows: int = 10000, cols: int = 10) -> str:
    """Generate test CSV data for benchmarking"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    headers = [f"field_{i}" for i in range(cols)]
    writer.writerow(headers)
    
    # Data rows
    for i in range(rows):
        row = [
            f"value_{i}_{j}" if j % 3 == 0
            else f"12345{i}{j}" if j % 3 == 1
            else f"2024-01-{(i % 28) + 1:02d}"
            for j in range(cols)
        ]
        writer.writerow(row)
    
    return output.getvalue()

def generate_test_json_data(size: int = 1000) -> Dict[str, Any]:
    """Generate test JSON data for benchmarking"""
    return {
        "metadata": {
            "version": "1.0",
            "timestamp": "2024-01-15T10:30:00Z",
            "record_count": size
        },
        "data": [
            {
                "id": f"ID_{i:06d}",
                "name": f"Item_{i}",
                "category": f"Category_{i % 10}",
                "price": round(np.random.uniform(10.0, 1000.0), 2),
                "quantity": np.random.randint(1, 100),
                "date_created": f"2024-01-{(i % 28) + 1:02d}",
                "active": i % 2 == 0,
                "metadata": {
                    "supplier": f"Supplier_{i % 20}",
                    "warehouse": f"WH_{i % 5}",
                    "tags": [f"tag_{i % 3}", f"tag_{(i + 1) % 3}"]
                }
            }
            for i in range(size)
        ]
    }

def generate_sap_bapi_response() -> Dict[str, Any]:
    """Generate mock SAP BAPI response for benchmarking"""
    return {
        "RETURN": [
            {
                "TYPE": "S",
                "MESSAGE": "Success",
                "FIELD": "",
                "NUMBER": "001"
            }
        ],
        "CUSTOMER_DATA": {
            "KUNNR": "0000001234",
            "NAME1": "ACME Corporation",
            "NAME2": "Technology Division",
            "STRAS": "123 Main Street",
            "PSTLZ": "12345",
            "ORT01": "New York",
            "LAND1": "US"
        },
        "SALES_DATA": [
            {
                "VBELN": f"000{i:07d}",
                "POSNR": "000010",
                "MATNR": f"MAT{i:015d}",
                "KWMENG": str(np.random.randint(1, 1000)),
                "NETWR": f"{np.random.uniform(100, 10000):.2f}",
                "WAERK": "USD",
                "VDATU": "20240115"
            }
            for i in range(1, 101)  # 100 sales records
        ]
    }

class BenchmarkRunner:
    """Main benchmark runner for Cython optimizations"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {}
        
        # Try to import Cython modules
        try:
            from erp_platform.cython_modules import (
                CYTHON_AVAILABLE,
                CSVProcessor,
                JSONProcessor,
                SAPTransformer,
                fast_sum, fast_mean, fast_std,
                fast_string_clean, sap_string_normalize
            )
            self.cython_available = CYTHON_AVAILABLE
            self.cython_csv = CSVProcessor()
            self.cython_json = JSONProcessor()
            self.cython_sap = SAPTransformer()
            
            if self.verbose:
                print(f"✓ Cython modules loaded successfully")
                
        except ImportError as e:
            self.cython_available = False
            if self.verbose:
                print(f"✗ Cython modules not available: {e}")
    
    def time_function(self, func, *args, **kwargs):
        """Time a function execution"""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        return result, end - start
    
    async def time_async_function(self, func, *args, **kwargs):
        """Time an async function execution"""
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        end = time.perf_counter()
        return result, end - start
    
    def benchmark_csv_processing(self, data_size: int = 10000):
        """Benchmark CSV processing performance"""
        print(f"\n📊 CSV Processing Benchmark (rows: {data_size})")
        print("-" * 50)
        
        test_data = generate_test_csv_data(data_size, 15)
        test_file = io.StringIO(test_data)
        
        # Python baseline (using built-in csv module)
        test_file.seek(0)
        start = time.perf_counter()
        reader = csv.DictReader(test_file)
        python_result = list(reader)
        python_time = time.perf_counter() - start
        
        if self.cython_available:
            # Cython optimized version
            test_file.seek(0)
            cython_result, cython_time = asyncio.run(
                self.time_async_function(self.cython_csv.process, test_file, True)
            )
            
            speedup = python_time / cython_time if cython_time > 0 else 1
            print(f"Python CSV:  {python_time:.4f}s ({len(python_result)} records)")
            print(f"Cython CSV:  {cython_time:.4f}s ({len(cython_result)} records)")
            print(f"Speedup:     {speedup:.2f}x")
            
            self.results['csv_processing'] = {
                'python_time': python_time,
                'cython_time': cython_time,
                'speedup': speedup,
                'records': len(python_result)
            }
        else:
            print(f"Python CSV:  {python_time:.4f}s ({len(python_result)} records)")
            print(f"Cython:      Not available")
    
    def benchmark_json_processing(self, data_size: int = 1000):
        """Benchmark JSON processing performance"""
        print(f"\n📊 JSON Processing Benchmark (records: {data_size})")
        print("-" * 50)
        
        test_data = generate_test_json_data(data_size)
        test_json = json.dumps(test_data)
        
        # Python baseline
        python_result, python_time = self.time_function(json.loads, test_json)
        
        if self.cython_available:
            # Cython optimized version
            cython_result, cython_time = asyncio.run(
                self.time_async_function(self.cython_json.process, test_json)
            )
            
            # Test transformation
            mapping = {"id": "item_id", "name": "item_name", "price": "cost"}
            
            python_transform_start = time.perf_counter()
            # Simple Python transformation
            transformed_python = self._transform_dict(python_result, mapping)
            python_transform_time = time.perf_counter() - python_transform_start
            
            cython_transform_result, cython_transform_time = asyncio.run(
                self.time_async_function(self.cython_json.transform, cython_result, mapping)
            )
            
            speedup_parse = python_time / cython_time if cython_time > 0 else 1
            speedup_transform = python_transform_time / cython_transform_time if cython_transform_time > 0 else 1
            
            print(f"Python Parse:      {python_time:.4f}s")
            print(f"Cython Parse:      {cython_time:.4f}s (speedup: {speedup_parse:.2f}x)")
            print(f"Python Transform:  {python_transform_time:.4f}s")
            print(f"Cython Transform:  {cython_transform_time:.4f}s (speedup: {speedup_transform:.2f}x)")
            
            self.results['json_processing'] = {
                'parse_speedup': speedup_parse,
                'transform_speedup': speedup_transform,
                'python_parse_time': python_time,
                'cython_parse_time': cython_time
            }
        else:
            print(f"Python Parse: {python_time:.4f}s")
            print(f"Cython:       Not available")
    
    def _transform_dict(self, data, mapping):
        """Simple Python dict transformation for comparison"""
        if isinstance(data, dict):
            result = {}
            for old_key, value in data.items():
                new_key = mapping.get(old_key, old_key)
                if isinstance(value, dict):
                    result[new_key] = self._transform_dict(value, mapping)
                elif isinstance(value, list):
                    result[new_key] = [self._transform_dict(item, mapping) if isinstance(item, dict) else item for item in value]
                else:
                    result[new_key] = value
            return result
        return data
    
    def benchmark_sap_processing(self):
        """Benchmark SAP data processing"""
        print(f"\n📊 SAP Data Processing Benchmark")
        print("-" * 50)
        
        test_bapi_response = generate_sap_bapi_response()
        
        if self.cython_available:
            # Cython optimized SAP transformation
            cython_result, cython_time = asyncio.run(
                self.time_async_function(self.cython_sap.transform_bapi_response, test_bapi_response)
            )
            
            print(f"Cython SAP Transform: {cython_time:.4f}s")
            print(f"Records processed:    {cython_result['metadata']['record_count']}")
            print(f"Tables found:         {cython_result['metadata']['table_count']}")
            print(f"Success:              {cython_result['success']}")
            
            self.results['sap_processing'] = {
                'cython_time': cython_time,
                'records_processed': cython_result['metadata']['record_count']
            }
        else:
            print(f"Cython SAP: Not available")
    
    def benchmark_math_operations(self, data_size: int = 100000):
        """Benchmark mathematical operations"""
        print(f"\n📊 Mathematical Operations Benchmark (size: {data_size})")
        print("-" * 50)
        
        test_data = np.random.random(data_size)
        
        # NumPy baseline
        numpy_sum, numpy_sum_time = self.time_function(np.sum, test_data)
        numpy_mean, numpy_mean_time = self.time_function(np.mean, test_data)
        numpy_std, numpy_std_time = self.time_function(np.std, test_data)
        
        if self.cython_available:
            from erp_platform.cython_modules import fast_sum, fast_mean, fast_std
            
            # Cython optimized versions
            cython_sum, cython_sum_time = self.time_function(fast_sum, test_data)
            cython_mean, cython_mean_time = self.time_function(fast_mean, test_data)
            cython_std, cython_std_time = self.time_function(fast_std, test_data)
            
            sum_speedup = numpy_sum_time / cython_sum_time if cython_sum_time > 0 else 1
            mean_speedup = numpy_mean_time / cython_mean_time if cython_mean_time > 0 else 1
            std_speedup = numpy_std_time / cython_std_time if cython_std_time > 0 else 1
            
            print(f"Sum:  NumPy {numpy_sum_time:.4f}s | Cython {cython_sum_time:.4f}s | Speedup: {sum_speedup:.2f}x")
            print(f"Mean: NumPy {numpy_mean_time:.4f}s | Cython {cython_mean_time:.4f}s | Speedup: {mean_speedup:.2f}x") 
            print(f"Std:  NumPy {numpy_std_time:.4f}s | Cython {cython_std_time:.4f}s | Speedup: {std_speedup:.2f}x")
            
            self.results['math_operations'] = {
                'sum_speedup': sum_speedup,
                'mean_speedup': mean_speedup,
                'std_speedup': std_speedup
            }
        else:
            print(f"Sum:  NumPy {numpy_sum_time:.4f}s | Cython: Not available")
            print(f"Mean: NumPy {numpy_mean_time:.4f}s | Cython: Not available")
            print(f"Std:  NumPy {numpy_std_time:.4f}s | Cython: Not available")
    
    def benchmark_string_operations(self, data_size: int = 10000):
        """Benchmark string operations"""
        print(f"\n📊 String Operations Benchmark (strings: {data_size})")
        print("-" * 50)
        
        # Generate test strings
        test_strings = [
            f"  SAP_MATERIAL_{i:06d}  " if i % 3 == 0
            else f"VENDOR/NAME-{i}_TEST  " if i % 3 == 1  
            else f'  "quoted,string,{i}"  '
            for i in range(data_size)
        ]
        
        # Python baseline
        start = time.perf_counter()
        python_cleaned = [s.strip().upper().replace('/', '_').replace('-', '_') for s in test_strings]
        python_time = time.perf_counter() - start
        
        if self.cython_available:
            from erp_platform.cython_modules import fast_string_clean, bulk_string_processing
            
            # Cython optimized version
            cython_cleaned, cython_time = self.time_function(bulk_string_processing, test_strings, 'clean')
            
            speedup = python_time / cython_time if cython_time > 0 else 1
            
            print(f"Python String Clean: {python_time:.4f}s")
            print(f"Cython String Clean: {cython_time:.4f}s")
            print(f"Speedup:             {speedup:.2f}x")
            
            self.results['string_operations'] = {
                'speedup': speedup,
                'python_time': python_time,
                'cython_time': cython_time
            }
        else:
            print(f"Python String Clean: {python_time:.4f}s")
            print(f"Cython:              Not available")
    
    def run_all_benchmarks(self):
        """Run all benchmark suites"""
        print("🚀 ERP Platform Cython Performance Benchmark Suite")
        print("=" * 60)
        
        if not self.cython_available:
            print("⚠️  Cython modules are not available. Running Python-only benchmarks.")
            print("   To build Cython modules, run: ./build_cython.sh")
        
        # Run all benchmarks
        self.benchmark_csv_processing(10000)
        self.benchmark_json_processing(1000)
        self.benchmark_sap_processing()
        self.benchmark_math_operations(100000)
        self.benchmark_string_operations(10000)
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print benchmark summary"""
        print(f"\n📈 Performance Summary")
        print("=" * 50)
        
        if not self.results:
            print("No Cython benchmarks available.")
            return
        
        total_tests = 0
        total_speedup = 0
        
        for test_name, metrics in self.results.items():
            if 'speedup' in metrics:
                speedup = metrics['speedup']
                total_speedup += speedup
                total_tests += 1
                print(f"{test_name.replace('_', ' ').title()}: {speedup:.2f}x speedup")
        
        if total_tests > 0:
            avg_speedup = total_speedup / total_tests
            print(f"\nAverage Speedup: {avg_speedup:.2f}x")
            
            if avg_speedup > 2.0:
                print("🎉 Excellent performance gains!")
            elif avg_speedup > 1.5:
                print("✅ Good performance improvements!")
            else:
                print("⚠️  Modest improvements - consider further optimization")


def main():
    parser = argparse.ArgumentParser(description="Cython Performance Benchmark Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--csv-size", type=int, default=10000, help="CSV test data size")
    parser.add_argument("--json-size", type=int, default=1000, help="JSON test data size")
    parser.add_argument("--math-size", type=int, default=100000, help="Math operations data size")
    parser.add_argument("--string-size", type=int, default=10000, help="String operations data size")
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(verbose=args.verbose)
    runner.run_all_benchmarks()


if __name__ == "__main__":
    main()