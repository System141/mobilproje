# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized CSV processor for high-performance data processing
"""

import numpy as np
cimport numpy as np
cimport cython
from libc.stdlib cimport malloc, free, realloc
from libc.string cimport strchr, strlen, strncpy, strcmp
from libc.stdio cimport FILE, fopen, fclose, fgetc, EOF
from cpython.list cimport PyList_New, PyList_SET_ITEM
from cpython.dict cimport PyDict_New, PyDict_SetItem
from cpython.ref cimport Py_INCREF

import asyncio
import io
from typing import Any, Dict, List, Optional

cdef class CSVProcessorCy:
    """
    Cython-optimized CSV file processor
    """
    
    cdef:
        char delimiter
        char quotechar
        int buffer_size
        char* line_buffer
        
    def __init__(self, str delimiter=',', str quotechar='"', int buffer_size=8192):
        self.delimiter = ord(delimiter[0])
        self.quotechar = ord(quotechar[0])
        self.buffer_size = buffer_size
        self.line_buffer = <char*>malloc(buffer_size * sizeof(char))
        
    def __dealloc__(self):
        if self.line_buffer:
            free(self.line_buffer)
    
    cdef list _parse_csv_line_fast(self, char* line, int line_length):
        """
        Fast CSV line parser using C-level operations
        """
        cdef list fields = []
        cdef int field_start = 0
        cdef int i = 0
        cdef int in_quotes = 0
        cdef char c
        cdef str field
        
        while i < line_length:
            c = line[i]
            
            if c == self.quotechar:
                in_quotes = 1 - in_quotes
            elif c == self.delimiter and not in_quotes:
                # Extract field
                field = line[field_start:i].decode('utf-8').strip()
                if field.startswith('"') and field.endswith('"'):
                    field = field[1:-1]
                fields.append(field)
                field_start = i + 1
            
            i += 1
        
        # Last field
        field = line[field_start:line_length].decode('utf-8').strip()
        if field.startswith('"') and field.endswith('"'):
            field = field[1:-1]
        fields.append(field)
        
        return fields
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    def process_fast(self, str file_content, bint has_header=True):
        """
        Fast CSV processing with Cython optimizations
        """
        cdef list lines = file_content.strip().split('\n')
        cdef list result = []
        cdef list headers = None
        cdef dict record
        cdef list fields
        cdef int i, j
        cdef str line, field_name, field_value
        
        if not lines:
            return []
        
        # Process header
        if has_header:
            headers = self._parse_csv_line_fast(
                lines[0].encode('utf-8'), 
                len(lines[0])
            )
            lines = lines[1:]
        
        # Process data lines
        for i in range(len(lines)):
            line = lines[i]
            if not line.strip():
                continue
                
            fields = self._parse_csv_line_fast(
                line.encode('utf-8'), 
                len(line)
            )
            
            if has_header and headers:
                record = {}
                for j in range(min(len(headers), len(fields))):
                    field_name = headers[j]
                    field_value = fields[j]
                    record[field_name] = field_value
                result.append(record)
            else:
                # No headers - create generic column names
                record = {}
                for j in range(len(fields)):
                    record[f"col_{j}"] = fields[j]
                result.append(record)
        
        return result
    
    async def process(self, file_obj: io.StringIO, bint has_header=True) -> List[Dict[str, Any]]:
        """
        Async wrapper for fast CSV processing
        """
        loop = asyncio.get_event_loop()
        
        def _process():
            content = file_obj.read()
            return self.process_fast(content, has_header)
        
        return await loop.run_in_executor(None, _process)
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef void _write_csv_line_fast(self, list fields, object file_handle):
        """
        Fast CSV line writer
        """
        cdef str field
        cdef str escaped_field
        cdef int i
        
        for i in range(len(fields)):
            field = str(fields[i])
            
            # Escape field if it contains delimiter or quotes
            if self.delimiter in field.encode('utf-8') or self.quotechar in field.encode('utf-8'):
                escaped_field = f'"{field.replace(chr(self.quotechar), chr(self.quotechar) + chr(self.quotechar))}"'
                file_handle.write(escaped_field)
            else:
                file_handle.write(field)
            
            if i < len(fields) - 1:
                file_handle.write(chr(self.delimiter))
        
        file_handle.write('\n')
    
    async def write_fast(self, data: List[Dict[str, Any]], str file_path, headers: Optional[List[str]] = None):
        """
        Fast CSV writer with Cython optimizations
        """
        if not data:
            return
        
        loop = asyncio.get_event_loop()
        
        def _write():
            # Get headers
            if headers is None:
                headers_list = list(data[0].keys())
            else:
                headers_list = headers
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write header
                self._write_csv_line_fast(headers_list, f)
                
                # Write data rows
                for record in data:
                    row = [record.get(header, '') for header in headers_list]
                    self._write_csv_line_fast(row, f)
        
        await loop.run_in_executor(None, _write)
    
    @cython.boundscheck(False)
    @cython.wraparound(False)  
    def process_large_file_fast(self, str file_path, int chunk_size=10000):
        """
        Process large CSV files in chunks with memory optimization
        """
        cdef list chunk = []
        cdef list headers = None
        cdef bint first_chunk = True
        cdef int line_count = 0
        
        def process_chunk(chunk_data):
            # Placeholder for chunk processing callback
            return chunk_data
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read header
                header_line = f.readline().strip()
                if header_line:
                    headers = self._parse_csv_line_fast(
                        header_line.encode('utf-8'),
                        len(header_line)
                    )
                
                # Process lines in chunks
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    fields = self._parse_csv_line_fast(
                        line.encode('utf-8'),
                        len(line)
                    )
                    
                    if headers:
                        record = {}
                        for i in range(min(len(headers), len(fields))):
                            record[headers[i]] = fields[i]
                        chunk.append(record)
                    
                    line_count += 1
                    
                    if len(chunk) >= chunk_size:
                        process_chunk(chunk)
                        chunk = []
                
                # Process remaining records
                if chunk:
                    process_chunk(chunk)
                    
        except Exception as e:
            raise Exception(f"Error processing large CSV file: {e}")
        
        return line_count
    
    async def stream_process(self, str file_path, int chunk_size=1000, callback=None):
        """
        Async stream processing with callback
        """
        loop = asyncio.get_event_loop()
        
        def _stream():
            return self.process_large_file_fast(file_path, chunk_size)
        
        return await loop.run_in_executor(None, _stream)


# Utility functions for ERP data processing
@cython.boundscheck(False)
@cython.wraparound(False)
def sap_csv_normalize(list data):
    """
    Normalize SAP CSV data with common transformations
    """
    cdef dict record
    cdef str key, value
    cdef list normalized = []
    
    for record in data:
        normalized_record = {}
        for key, value in record.items():
            # SAP-specific normalizations
            if value.startswith('0') and value.isdigit() and len(value) > 1:
                # Remove leading zeros from SAP material numbers
                value = value.lstrip('0') or '0'
            elif key.upper().endswith('_DATE') and len(value) == 8:
                # Format SAP dates
                if value != '00000000':
                    value = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
            elif key.upper().endswith('_AMOUNT') and value:
                # Clean SAP amount fields
                value = value.replace(',', '.')
            
            normalized_record[key] = value
        normalized.append(normalized_record)
    
    return normalized


@cython.boundscheck(False)
@cython.wraparound(False) 
def erp_data_validator(list data, dict schema):
    """
    Fast data validation for ERP records
    """
    cdef list errors = []
    cdef dict record
    cdef str field_name, field_value, field_type
    cdef int record_idx
    
    for record_idx in range(len(data)):
        record = data[record_idx]
        
        for field_name, field_rules in schema.items():
            if field_name not in record:
                if field_rules.get('required', False):
                    errors.append({
                        'record': record_idx,
                        'field': field_name,
                        'error': 'Required field missing'
                    })
                continue
            
            field_value = str(record[field_name])
            field_type = field_rules.get('type', 'string')
            
            # Type validation
            if field_type == 'integer':
                try:
                    int(field_value)
                except ValueError:
                    errors.append({
                        'record': record_idx,
                        'field': field_name,
                        'error': f'Invalid integer: {field_value}'
                    })
            elif field_type == 'float':
                try:
                    float(field_value)
                except ValueError:
                    errors.append({
                        'record': record_idx,
                        'field': field_name,  
                        'error': f'Invalid float: {field_value}'
                    })
            
            # Length validation
            if 'max_length' in field_rules:
                if len(field_value) > field_rules['max_length']:
                    errors.append({
                        'record': record_idx,
                        'field': field_name,
                        'error': f'Value too long: {len(field_value)} > {field_rules["max_length"]}'
                    })
    
    return errors