# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized string utilities for ERP data processing
"""

cimport cython
from libc.string cimport strlen, strchr, strstr, strcpy, strncpy
from libc.stdlib cimport malloc, free, realloc
from libc.ctype cimport isspace, isalnum, isdigit
from cpython.unicode cimport PyUnicode_FromString

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_string_clean(str input_string):
    """
    Fast string cleaning for ERP data
    """
    if not input_string:
        return ""
    
    cdef bytes input_bytes = input_string.encode('utf-8')
    cdef char* input_ptr = input_bytes
    cdef int length = len(input_bytes)
    cdef char* cleaned = <char*>malloc((length + 1) * sizeof(char))
    cdef int i, j = 0
    cdef char c
    
    try:
        for i in range(length):
            c = input_ptr[i]
            
            # Remove control characters and excessive whitespace
            if c >= 32 and c <= 126:  # Printable ASCII
                if isspace(c):
                    # Only add space if previous char wasn't space
                    if j > 0 and cleaned[j-1] != 32:  # 32 = space
                        cleaned[j] = 32
                        j += 1
                else:
                    cleaned[j] = c
                    j += 1
        
        # Remove trailing space
        if j > 0 and cleaned[j-1] == 32:
            j -= 1
        
        cleaned[j] = 0  # Null terminate
        
        return PyUnicode_FromString(cleaned).decode('utf-8', errors='ignore')
    
    finally:
        free(cleaned)

@cython.boundscheck(False)
@cython.wraparound(False)
def fast_string_split(str input_string, str delimiter, int max_splits=-1):
    """
    Fast string splitting for ERP field parsing
    """
    if not input_string or not delimiter:
        return [input_string] if input_string else []
    
    cdef list result = []
    cdef bytes input_bytes = input_string.encode('utf-8')
    cdef bytes delim_bytes = delimiter.encode('utf-8')
    cdef char* input_ptr = input_bytes
    cdef char* delim_ptr = delim_bytes
    cdef int input_len = len(input_bytes)
    cdef int delim_len = len(delim_bytes)
    cdef int start = 0
    cdef int i = 0
    cdef int splits_made = 0
    cdef char* found_pos
    
    while i <= input_len - delim_len:
        found_pos = strstr(input_ptr + i, delim_ptr)
        
        if found_pos == NULL:
            break
        
        # Extract substring
        segment_len = found_pos - (input_ptr + start)
        if segment_len > 0:
            segment = input_string[start:start + segment_len]
            result.append(segment)
        else:
            result.append("")
        
        start = (found_pos - input_ptr) + delim_len
        i = start
        splits_made += 1
        
        if max_splits > 0 and splits_made >= max_splits:
            break
    
    # Add remaining string
    if start < input_len:
        result.append(input_string[start:])
    elif start == input_len:
        result.append("")
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_string_normalize(str sap_field):
    """
    SAP-specific string normalization
    """
    if not sap_field:
        return ""
    
    cdef str result = sap_field.strip()
    
    # Remove SAP-specific prefixes/suffixes
    if result.startswith('SAP_'):
        result = result[4:]
    
    # Convert to uppercase for SAP field consistency
    result = result.upper()
    
    # Handle SAP special characters
    result = result.replace('/', '_')
    result = result.replace('-', '_')
    result = result.replace(' ', '_')
    
    # Remove double underscores
    while '__' in result:
        result = result.replace('__', '_')
    
    # Remove leading/trailing underscores
    result = result.strip('_')
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_material_number_normalize(str material_number):
    """
    Normalize SAP material numbers (remove leading zeros, validate format)
    """
    if not material_number:
        return ""
    
    cdef str cleaned = material_number.strip().upper()
    
    # Remove leading zeros but keep at least one digit
    cdef str result = cleaned.lstrip('0') or '0'
    
    # Validate that it's numeric for material numbers
    if result.isdigit():
        # Pad to standard SAP material number length (18 digits)
        result = result.zfill(18)
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def sap_date_normalize(str sap_date):
    """
    Normalize SAP date formats (YYYYMMDD -> YYYY-MM-DD)
    """
    if not sap_date or sap_date == '00000000':
        return ""
    
    cdef str cleaned = sap_date.strip()
    
    # Handle YYYYMMDD format
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[0:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    
    return cleaned

@cython.boundscheck(False)
@cython.wraparound(False)
def json_string_escape(str input_string):
    """
    Fast JSON string escaping for API responses
    """
    if not input_string:
        return ""
    
    cdef str result = input_string
    
    # Escape special JSON characters
    result = result.replace('\\', '\\\\')
    result = result.replace('"', '\\"')
    result = result.replace('\n', '\\n')
    result = result.replace('\r', '\\r')
    result = result.replace('\t', '\\t')
    result = result.replace('\b', '\\b')
    result = result.replace('\f', '\\f')
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def csv_field_escape(str field_value, str delimiter=',', str quote_char='"'):
    """
    Fast CSV field escaping
    """
    if not field_value:
        return ""
    
    cdef str result = field_value
    cdef bint needs_quoting = False
    
    # Check if quoting is needed
    if delimiter in result or quote_char in result or '\n' in result or '\r' in result:
        needs_quoting = True
    
    if needs_quoting:
        # Escape quote characters by doubling them
        result = result.replace(quote_char, quote_char + quote_char)
        result = f"{quote_char}{result}{quote_char}"
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def erp_field_validator(str field_value, str field_type, dict constraints=None):
    """
    Fast field validation for ERP data
    """
    cdef list errors = []
    
    if not field_value and constraints and constraints.get('required', False):
        errors.append("Field is required")
        return errors
    
    if not field_value:
        return errors
    
    # Type-specific validations
    if field_type == 'numeric':
        if not field_value.replace('.', '').replace('-', '').isdigit():
            errors.append(f"Invalid numeric value: {field_value}")
    
    elif field_type == 'date':
        if len(field_value) == 8 and field_value.isdigit():
            # YYYYMMDD format validation
            year = int(field_value[0:4])
            month = int(field_value[4:6])
            day = int(field_value[6:8])
            
            if year < 1900 or year > 2100:
                errors.append(f"Invalid year: {year}")
            if month < 1 or month > 12:
                errors.append(f"Invalid month: {month}")
            if day < 1 or day > 31:
                errors.append(f"Invalid day: {day}")
        else:
            errors.append(f"Invalid date format: {field_value}")
    
    elif field_type == 'material_number':
        if not field_value.replace('-', '').isalnum():
            errors.append(f"Invalid material number format: {field_value}")
    
    # Constraint validations
    if constraints:
        if 'min_length' in constraints and len(field_value) < constraints['min_length']:
            errors.append(f"Value too short: {len(field_value)} < {constraints['min_length']}")
        
        if 'max_length' in constraints and len(field_value) > constraints['max_length']:
            errors.append(f"Value too long: {len(field_value)} > {constraints['max_length']}")
        
        if 'pattern' in constraints:
            import re
            if not re.match(constraints['pattern'], field_value):
                errors.append(f"Value doesn't match pattern: {constraints['pattern']}")
    
    return errors

@cython.boundscheck(False)
@cython.wraparound(False)
def bulk_string_processing(list string_list, str operation):
    """
    Bulk string processing for large ERP datasets
    """
    cdef list results = []
    cdef str string_item
    cdef str processed
    
    for string_item in string_list:
        if operation == 'clean':
            processed = fast_string_clean(string_item)
        elif operation == 'sap_normalize':
            processed = sap_string_normalize(string_item)
        elif operation == 'material_normalize':
            processed = sap_material_number_normalize(string_item)
        elif operation == 'date_normalize':
            processed = sap_date_normalize(string_item)
        elif operation == 'json_escape':
            processed = json_string_escape(string_item)
        else:
            processed = string_item
        
        results.append(processed)
    
    return results

@cython.boundscheck(False)
@cython.wraparound(False)
def oracle_varchar_truncate(str input_string, int max_length):
    """
    Safe truncation for Oracle VARCHAR2 fields
    """
    if not input_string:
        return ""
    
    if len(input_string) <= max_length:
        return input_string
    
    # Truncate and add ellipsis if possible
    if max_length > 3:
        return input_string[:max_length-3] + "..."
    else:
        return input_string[:max_length]