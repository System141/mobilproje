"""
JSON data processor
"""

import json
from typing import Any, Dict, List, Optional
import asyncio

from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class JSONProcessor:
    """
    JSON data processor
    """
    
    async def process(self, data: str) -> Any:
        """
        Process JSON string and return parsed data
        """
        loop = asyncio.get_event_loop()
        
        def _process():
            return json.loads(data)
        
        result = await loop.run_in_executor(None, _process)
        
        logger.info(f"Processed JSON: {type(result).__name__}")
        return result
    
    async def write(self, data: Any, file_path: str, indent: int = 2):
        """
        Write data to JSON file
        """
        loop = asyncio.get_event_loop()
        
        def _write():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        
        await loop.run_in_executor(None, _write)
        
        logger.info(f"Wrote JSON to {file_path}")
    
    async def validate(self, data: str, schema: Dict[str, Any]) -> bool:
        """
        Validate JSON against schema
        """
        try:
            import jsonschema
            
            loop = asyncio.get_event_loop()
            
            def _validate():
                json_data = json.loads(data)
                jsonschema.validate(json_data, schema)
                return True
            
            result = await loop.run_in_executor(None, _validate)
            return result
            
        except jsonschema.ValidationError as e:
            logger.error(f"JSON validation failed: {e}")
            return False
        except ImportError:
            logger.warning("jsonschema not installed, skipping validation")
            return True
    
    async def transform(
        self,
        data: Any,
        mapping: Dict[str, str]
    ) -> Any:
        """
        Transform JSON data based on field mapping
        """
        loop = asyncio.get_event_loop()
        
        def _transform(obj):
            if isinstance(obj, dict):
                result = {}
                for old_key, value in obj.items():
                    new_key = mapping.get(old_key, old_key)
                    result[new_key] = _transform(value)
                return result
            elif isinstance(obj, list):
                return [_transform(item) for item in obj]
            else:
                return obj
        
        result = await loop.run_in_executor(None, _transform, data)
        
        logger.info("Transformed JSON data")
        return result
    
    async def flatten(self, data: Dict[str, Any], sep: str = '_') -> Dict[str, Any]:
        """
        Flatten nested JSON structure
        """
        loop = asyncio.get_event_loop()
        
        def _flatten(obj, parent_key=''):
            items = []
            
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(_flatten(v, new_key).items())
                    elif isinstance(v, list):
                        for i, item in enumerate(v):
                            if isinstance(item, dict):
                                items.extend(_flatten(item, f"{new_key}{sep}{i}").items())
                            else:
                                items.append((f"{new_key}{sep}{i}", item))
                    else:
                        items.append((new_key, v))
            
            return dict(items)
        
        result = await loop.run_in_executor(None, _flatten, data)
        
        logger.info("Flattened JSON structure")
        return result