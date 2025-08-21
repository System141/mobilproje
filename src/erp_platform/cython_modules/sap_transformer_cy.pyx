# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized SAP data transformer for high-performance ERP operations
"""

import asyncio
import numpy as np
cimport numpy as np
cimport cython
from typing import Any, Dict, List, Optional
from cpython.dict cimport PyDict_New, PyDict_SetItem
from cpython.list cimport PyList_New, PyList_Append

np.import_array()

cdef class SAPTransformerCy:
    """
    Cython-optimized SAP data transformer
    """
    
    def __init__(self):
        pass
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_bapi_result(self, dict bapi_response):
        """
        Fast transformation of SAP BAPI results
        """
        cdef dict result = {
            'success': True,
            'messages': [],
            'data': {},
            'tables': {},
            'metadata': {}
        }
        
        cdef dict msg
        cdef str msg_type, key
        cdef object value
        
        # Process RETURN messages
        if 'RETURN' in bapi_response:
            return_data = bapi_response['RETURN']
            if isinstance(return_data, dict):
                return_data = [return_data]
            
            for msg in return_data:
                msg_type = msg.get('TYPE', '')
                result['messages'].append({
                    'type': msg_type,
                    'message': msg.get('MESSAGE', ''),
                    'field': msg.get('FIELD', ''),
                    'number': msg.get('NUMBER', ''),
                    'severity': self._get_message_severity(msg_type)
                })
                
                if msg_type in ['E', 'A']:  # Error or Abort
                    result['success'] = False
        
        # Process other fields
        for key, value in bapi_response.items():
            if key == 'RETURN':
                continue
            elif isinstance(value, list) and len(value) > 0:
                # Table parameter
                result['tables'][key] = self._transform_sap_table(value)
            else:
                # Export parameter
                result['data'][key] = self._transform_sap_field(value)
        
        # Add metadata
        result['metadata'] = {
            'record_count': sum(len(table['rows']) for table in result['tables'].values()),
            'table_count': len(result['tables']),
            'has_errors': not result['success'],
            'message_count': len(result['messages'])
        }
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef str _get_message_severity(self, str msg_type):
        """
        Get message severity level
        """
        if msg_type == 'S':
            return 'success'
        elif msg_type == 'I':
            return 'info'
        elif msg_type == 'W':
            return 'warning'
        elif msg_type == 'E':
            return 'error'
        elif msg_type == 'A':
            return 'abort'
        else:
            return 'unknown'
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_sap_table(self, list table_data):
        """
        Transform SAP table data with optimizations
        """
        if not table_data:
            return {'headers': [], 'rows': [], 'row_count': 0}
        
        cdef dict first_row = table_data[0]
        cdef list headers = list(first_row.keys())
        cdef list rows = []
        cdef dict row
        cdef list row_values
        cdef str header
        
        for row in table_data:
            row_values = []
            for header in headers:
                value = row.get(header, '')
                # Transform SAP-specific field values
                transformed_value = self._transform_sap_field(value)
                row_values.append(transformed_value)
            rows.append(row_values)
        
        return {
            'headers': headers,
            'rows': rows,
            'row_count': len(rows)
        }
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef object _transform_sap_field(self, object value):
        """
        Transform individual SAP field values
        """
        if not isinstance(value, str):
            return value
        
        cdef str string_value = value.strip()
        
        # Handle empty values
        if not string_value:
            return ""
        
        # Date field transformation (YYYYMMDD -> YYYY-MM-DD)
        if len(string_value) == 8 and string_value.isdigit():
            if string_value != '00000000':
                return f"{string_value[0:4]}-{string_value[4:6]}-{string_value[6:8]}"
            else:
                return ""
        
        # Time field transformation (HHMMSS -> HH:MM:SS)
        if len(string_value) == 6 and string_value.isdigit():
            return f"{string_value[0:2]}:{string_value[2:4]}:{string_value[4:6]}"
        
        # Amount field cleaning
        if string_value.replace('.', '').replace(',', '').replace('-', '').isdigit():
            # Convert German decimal format to standard
            if ',' in string_value and '.' not in string_value:
                string_value = string_value.replace(',', '.')
            return string_value
        
        # Material number normalization
        if string_value.isdigit() and len(string_value) >= 8:
            return string_value.lstrip('0') or '0'
        
        return string_value
    
    async def transform_bapi_response(self, dict bapi_response) -> Dict[str, Any]:
        """
        Async wrapper for BAPI response transformation
        """
        loop = asyncio.get_event_loop()
        
        def _transform():
            return self._transform_bapi_result(bapi_response)
        
        return await loop.run_in_executor(None, _transform)
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef list _transform_rfc_table_data(self, list rfc_data):
        """
        Transform RFC_READ_TABLE data format
        """
        if not rfc_data:
            return []
        
        cdef dict rfc_response = rfc_data[0] if isinstance(rfc_data, list) else rfc_data
        cdef list data_rows = rfc_response.get('DATA', [])
        cdef list field_info = rfc_response.get('FIELDS', [])
        cdef str delimiter = '|'  # Default SAP delimiter
        
        # Extract field names and positions
        cdef list field_names = []
        cdef dict field
        for field in field_info:
            field_names.append(field.get('FIELDNAME', ''))
        
        # Parse data rows
        cdef list records = []
        cdef dict row_dict
        cdef dict data_row
        cdef str row_data
        cdef list values
        cdef int i
        
        for data_row in data_rows:
            row_data = data_row.get('WA', '')
            values = row_data.split(delimiter)
            
            row_dict = {}
            for i in range(min(len(field_names), len(values))):
                field_name = field_names[i]
                field_value = values[i].strip()
                # Apply field transformation
                row_dict[field_name] = self._transform_sap_field(field_value)
            
            records.append(row_dict)
        
        return records
    
    async def transform_rfc_table_response(self, dict rfc_response) -> List[Dict[str, Any]]:
        """
        Transform RFC table read response
        """
        loop = asyncio.get_event_loop()
        
        def _transform():
            return self._transform_rfc_table_data([rfc_response])
        
        return await loop.run_in_executor(None, _transform)
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    def batch_transform_records(self, list records, str record_type='generic'):
        """
        Batch transform multiple records with type-specific optimizations
        """
        cdef list transformed = []
        cdef dict record
        cdef dict transformed_record
        
        for record in records:
            if record_type == 'material_master':
                transformed_record = self._transform_material_master(record)
            elif record_type == 'vendor_master':
                transformed_record = self._transform_vendor_master(record)
            elif record_type == 'customer_master':
                transformed_record = self._transform_customer_master(record)
            elif record_type == 'financial_document':
                transformed_record = self._transform_financial_document(record)
            else:
                # Generic transformation
                transformed_record = {}
                for key, value in record.items():
                    transformed_record[key] = self._transform_sap_field(value)
            
            transformed.append(transformed_record)
        
        return transformed
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_material_master(self, dict record):
        """
        SAP Material Master specific transformations
        """
        cdef dict result = {}
        cdef str key, value
        
        for key, value in record.items():
            if key == 'MATNR':  # Material Number
                result[key] = self._transform_sap_field(value).lstrip('0') or '0'
            elif key in ['ERSDA', 'LAEDA']:  # Creation/Change Date
                result[key] = self._transform_sap_field(value)
            elif key == 'MTART':  # Material Type
                result[key] = value.strip().upper()
            elif key in ['BRGEW', 'NTGEW']:  # Weights
                result[key] = self._normalize_numeric_field(value)
            else:
                result[key] = self._transform_sap_field(value)
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_vendor_master(self, dict record):
        """
        SAP Vendor Master specific transformations
        """
        cdef dict result = {}
        cdef str key, value
        
        for key, value in record.items():
            if key == 'LIFNR':  # Vendor Number
                result[key] = self._transform_sap_field(value).lstrip('0') or '0'
            elif key == 'NAME1':  # Vendor Name
                result[key] = value.strip().title()
            elif key in ['STRAS', 'PFACH']:  # Address fields
                result[key] = value.strip()
            elif key == 'LAND1':  # Country
                result[key] = value.strip().upper()
            else:
                result[key] = self._transform_sap_field(value)
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_customer_master(self, dict record):
        """
        SAP Customer Master specific transformations
        """
        cdef dict result = {}
        cdef str key, value
        
        for key, value in record.items():
            if key == 'KUNNR':  # Customer Number
                result[key] = self._transform_sap_field(value).lstrip('0') or '0'
            elif key in ['NAME1', 'NAME2']:  # Customer Names
                result[key] = value.strip().title()
            elif key == 'KTOKD':  # Customer Account Group
                result[key] = value.strip().upper()
            else:
                result[key] = self._transform_sap_field(value)
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_financial_document(self, dict record):
        """
        SAP Financial Document specific transformations
        """
        cdef dict result = {}
        cdef str key, value
        
        for key, value in record.items():
            if key == 'BELNR':  # Document Number
                result[key] = self._transform_sap_field(value).lstrip('0') or '0'
            elif key in ['DMBTR', 'WRBTR']:  # Amount fields
                result[key] = self._normalize_numeric_field(value)
            elif key == 'WAERS':  # Currency
                result[key] = value.strip().upper()
            elif key in ['BUDAT', 'BLDAT']:  # Date fields
                result[key] = self._transform_sap_field(value)
            else:
                result[key] = self._transform_sap_field(value)
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef str _normalize_numeric_field(self, str value):
        """
        Normalize numeric fields for consistency
        """
        if not value or value.strip() == '':
            return "0"
        
        cdef str cleaned = value.strip()
        
        # Remove thousand separators and normalize decimal
        cleaned = cleaned.replace(',', '.')
        
        # Handle negative values in SAP format (trailing minus)
        cdef bint is_negative = cleaned.endswith('-')
        if is_negative:
            cleaned = cleaned[:-1]
        
        try:
            float(cleaned)
            return f"-{cleaned}" if is_negative else cleaned
        except ValueError:
            return "0"


# Utility functions for SAP data processing
@cython.boundscheck(False)
@cython.wraparound(False)
def sap_table_to_polars_format(list sap_table_data):
    """
    Convert SAP table data to Polars-compatible format
    """
    if not sap_table_data:
        return {'columns': [], 'data': []}
    
    # Extract column names from first record
    cdef list columns = list(sap_table_data[0].keys())
    cdef list rows = []
    cdef dict record
    cdef list row_values
    cdef str col
    
    for record in sap_table_data:
        row_values = []
        for col in columns:
            row_values.append(record.get(col, ''))
        rows.append(row_values)
    
    return {
        'columns': columns,
        'data': rows
    }

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_bapi_parameter_builder(dict params, dict param_definitions):
    """
    Build SAP BAPI parameters with proper formatting
    """
    cdef dict formatted_params = {}
    cdef str param_name, param_value, param_type
    cdef dict param_def
    
    for param_name, param_value in params.items():
        if param_name in param_definitions:
            param_def = param_definitions[param_name]
            param_type = param_def.get('type', 'string')
            
            if param_type == 'date' and param_value:
                # Convert to SAP date format
                if '-' in param_value:
                    param_value = param_value.replace('-', '')
            elif param_type == 'material_number' and param_value:
                # Pad material number to 18 digits
                param_value = param_value.zfill(18)
            elif param_type == 'numeric' and param_value:
                # Ensure proper numeric format
                param_value = str(float(param_value))
            
            formatted_params[param_name] = param_value
        else:
            formatted_params[param_name] = param_value
    
    return formatted_params