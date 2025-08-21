# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized JSON processor for ERP data transformations
"""

import json
import asyncio
cimport cython
from typing import Any, Dict, List, Optional
from cpython.dict cimport PyDict_New, PyDict_SetItem, PyDict_GetItem
from cpython.list cimport PyList_New, PyList_Append

cdef class JSONProcessorCy:
    """
    Cython-optimized JSON processor
    """
    
    def __init__(self):
        pass
    
    async def process(self, str data) -> Any:
        """
        Process JSON string with async support
        """
        loop = asyncio.get_event_loop()
        
        def _process():
            return json.loads(data)
        
        result = await loop.run_in_executor(None, _process)
        return result
    
    async def write(self, data: Any, str file_path, int indent=2):
        """
        Write data to JSON file
        """
        loop = asyncio.get_event_loop()
        
        def _write():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        
        await loop.run_in_executor(None, _write)
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _transform_dict_fast(self, dict obj, dict mapping):
        """
        Fast dictionary transformation using Cython
        """
        cdef dict result = {}
        cdef str old_key, new_key
        cdef object value, transformed_value
        
        for old_key, value in obj.items():
            new_key = mapping.get(old_key, old_key)
            
            if isinstance(value, dict):
                transformed_value = self._transform_dict_fast(value, mapping)
            elif isinstance(value, list):
                transformed_value = self._transform_list_fast(value, mapping)
            else:
                transformed_value = value
                
            result[new_key] = transformed_value
        
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef list _transform_list_fast(self, list obj, dict mapping):
        """
        Fast list transformation using Cython
        """
        cdef list result = []
        cdef object item, transformed_item
        
        for item in obj:
            if isinstance(item, dict):
                transformed_item = self._transform_dict_fast(item, mapping)
            elif isinstance(item, list):
                transformed_item = self._transform_list_fast(item, mapping)
            else:
                transformed_item = item
                
            result.append(transformed_item)
        
        return result
    
    async def transform(self, data: Any, dict mapping: Dict[str, str]) -> Any:
        """
        Transform JSON data based on field mapping with Cython optimization
        """
        loop = asyncio.get_event_loop()
        
        def _transform():
            if isinstance(data, dict):
                return self._transform_dict_fast(data, mapping)
            elif isinstance(data, list):
                return self._transform_list_fast(data, mapping)
            else:
                return data
        
        result = await loop.run_in_executor(None, _transform)
        return result
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cdef dict _flatten_dict_fast(self, dict obj, str parent_key, str sep):
        """
        Fast dictionary flattening using Cython
        """
        cdef dict items = {}
        cdef str k, new_key
        cdef object v
        cdef dict flattened
        cdef int i
        
        for k, v in obj.items():
            if parent_key:
                new_key = f"{parent_key}{sep}{k}"
            else:
                new_key = k
            
            if isinstance(v, dict):
                flattened = self._flatten_dict_fast(v, new_key, sep)
                items.update(flattened)
            elif isinstance(v, list):
                for i in range(len(v)):
                    item = v[i]
                    if isinstance(item, dict):
                        flattened = self._flatten_dict_fast(item, f"{new_key}{sep}{i}", sep)
                        items.update(flattened)
                    else:
                        items[f"{new_key}{sep}{i}"] = item
            else:
                items[new_key] = v
        
        return items
    
    async def flatten(self, dict data: Dict[str, Any], str sep='_') -> Dict[str, Any]:
        """
        Flatten nested JSON structure with Cython optimization
        """
        loop = asyncio.get_event_loop()
        
        def _flatten():
            return self._flatten_dict_fast(data, '', sep)
        
        result = await loop.run_in_executor(None, _flatten)
        return result


# SAP-specific JSON transformations
@cython.boundscheck(False)
@cython.wraparound(False)
def sap_odata_response_parser(dict response_data):
    """
    Fast parser for SAP OData responses
    """
    cdef dict result = {}
    cdef list items = []
    cdef dict item, normalized_item
    cdef str key, value
    
    # Extract data from SAP OData structure
    if 'd' in response_data:
        data = response_data['d']
        
        if 'results' in data:
            # Collection response
            for item in data['results']:
                normalized_item = {}
                for key, value in item.items():
                    # Skip SAP metadata fields
                    if not key.startswith('__'):
                        if isinstance(value, str) and value.startswith('/Date('):
                            # Convert SAP date format
                            timestamp = value.replace('/Date(', '').replace(')/', '')
                            if timestamp.isdigit():
                                # Convert to ISO format (simplified)
                                normalized_item[key] = timestamp
                            else:
                                normalized_item[key] = value
                        else:
                            normalized_item[key] = value
                items.append(normalized_item)
            result['items'] = items
        else:
            # Single item response
            normalized_item = {}
            for key, value in data.items():
                if not key.startswith('__'):
                    normalized_item[key] = value
            result = normalized_item
    
    return result


@cython.boundscheck(False)
@cython.wraparound(False)
def sap_bapi_response_parser(dict bapi_response):
    """
    Fast parser for SAP BAPI responses
    """
    cdef dict result = {
        'success': True,
        'messages': [],
        'data': {},
        'tables': {}
    }
    cdef dict msg
    cdef str msg_type
    
    # Parse RETURN messages
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
                'number': msg.get('NUMBER', '')
            })
            
            if msg_type == 'E':  # Error
                result['success'] = False
    
    # Extract export parameters and tables
    for key, value in bapi_response.items():
        if key == 'RETURN':
            continue
        elif isinstance(value, list) and len(value) > 0:
            # Table parameter
            result['tables'][key] = value
        else:
            # Export parameter
            result['data'][key] = value
    
    return result


@cython.boundscheck(False)
@cython.wraparound(False)
def erp_json_validator(data, dict schema):
    """
    Fast JSON schema validation for ERP data
    """
    cdef list errors = []
    
    def _validate_field(field_path, value, field_schema):
        field_type = field_schema.get('type')
        required = field_schema.get('required', False)
        
        if value is None:
            if required:
                errors.append({
                    'path': field_path,
                    'error': 'Required field is missing'
                })
            return
        
        # Type validation
        if field_type == 'string' and not isinstance(value, str):
            errors.append({
                'path': field_path,
                'error': f'Expected string, got {type(value).__name__}'
            })
        elif field_type == 'integer' and not isinstance(value, int):
            errors.append({
                'path': field_path,
                'error': f'Expected integer, got {type(value).__name__}'
            })
        elif field_type == 'number' and not isinstance(value, (int, float)):
            errors.append({
                'path': field_path,
                'error': f'Expected number, got {type(value).__name__}'
            })
        
        # Value constraints
        if 'min_length' in field_schema and isinstance(value, str):
            if len(value) < field_schema['min_length']:
                errors.append({
                    'path': field_path,
                    'error': f'String too short: {len(value)} < {field_schema["min_length"]}'
                })
        
        if 'max_length' in field_schema and isinstance(value, str):
            if len(value) > field_schema['max_length']:
                errors.append({
                    'path': field_path,
                    'error': f'String too long: {len(value)} > {field_schema["max_length"]}'
                })
    
    # Validate against schema
    if isinstance(data, dict) and isinstance(schema, dict):
        for field_name, field_schema in schema.items():
            field_value = data.get(field_name)
            _validate_field(field_name, field_value, field_schema)
    
    return errors


@cython.boundscheck(False)
@cython.wraparound(False)
def json_to_csv_converter(list json_data, list field_mapping=None):
    """
    Fast JSON to CSV conversion for ERP data export
    """
    if not json_data:
        return []
    
    cdef dict first_record = json_data[0]
    cdef list headers
    cdef list csv_rows = []
    cdef dict record
    cdef list row
    cdef str header
    cdef object value
    
    # Determine headers
    if field_mapping:
        headers = field_mapping
    else:
        headers = list(first_record.keys())
    
    # Convert records to CSV rows
    for record in json_data:
        row = []
        for header in headers:
            value = record.get(header, '')
            if isinstance(value, (dict, list)):
                # Serialize complex objects
                row.append(json.dumps(value, ensure_ascii=False))
            else:
                row.append(str(value))
        csv_rows.append(row)
    
    return {'headers': headers, 'rows': csv_rows}