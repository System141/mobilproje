"""
Data processor API endpoints
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict, Any, Optional
from pydantic import BaseModel
import io

from erp_platform.processors.csv_processor import CSVProcessor
from erp_platform.processors.json_processor import JSONProcessor
from erp_platform.processors.polars_processor import PolarsProcessor
from erp_platform.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ProcessRequest(BaseModel):
    """Data processing request model"""
    data: str
    format: str = "csv"
    options: Dict[str, Any] = {}


@router.post("/process/csv")
async def process_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Process CSV file
    """
    try:
        content = await file.read()
        processor = CSVProcessor()
        
        result = await processor.process(io.StringIO(content.decode()))
        
        return {
            "success": True,
            "filename": file.filename,
            "rows_processed": len(result),
            "columns": result[0].keys() if result else [],
            "sample": result[:5] if len(result) > 5 else result
        }
        
    except Exception as e:
        logger.error(f"CSV processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/json")
async def process_json(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Process JSON file
    """
    try:
        content = await file.read()
        processor = JSONProcessor()
        
        result = await processor.process(content.decode())
        
        return {
            "success": True,
            "filename": file.filename,
            "data_type": type(result).__name__,
            "sample": result[:5] if isinstance(result, list) else result
        }
        
    except Exception as e:
        logger.error(f"JSON processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transform/polars")
async def transform_with_polars(
    file: UploadFile = File(...),
    operations: str = None
) -> Dict[str, Any]:
    """
    Transform data using Polars
    
    Args:
        file: Data file to process
        operations: JSON string of operations to apply
    """
    try:
        content = await file.read()
        processor = PolarsProcessor()
        
        # Process file
        df = await processor.read_csv(io.BytesIO(content))
        
        # Apply operations if provided
        if operations:
            import json
            ops = json.loads(operations)
            for op in ops:
                df = await processor.apply_operation(df, op)
        
        # Convert to dict for response
        result = df.to_dicts()
        
        return {
            "success": True,
            "filename": file.filename,
            "shape": {"rows": df.height, "columns": df.width},
            "columns": df.columns,
            "sample": result[:5] if len(result) > 5 else result
        }
        
    except Exception as e:
        logger.error(f"Polars transformation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert")
async def convert_format(
    file: UploadFile = File(...),
    target_format: str = "json"
) -> Dict[str, Any]:
    """
    Convert between data formats
    """
    try:
        content = await file.read()
        
        # Detect source format
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            source_format = "csv"
        elif filename.endswith('.json'):
            source_format = "json"
        else:
            raise ValueError("Unsupported file format")
        
        # Process based on source format
        if source_format == "csv":
            processor = CSVProcessor()
            data = await processor.process(io.StringIO(content.decode()))
        else:
            processor = JSONProcessor()
            data = await processor.process(content.decode())
        
        # Convert to target format
        if target_format == "json":
            import json
            output = json.dumps(data, indent=2)
        elif target_format == "csv":
            import csv
            output_io = io.StringIO()
            if data and isinstance(data, list):
                writer = csv.DictWriter(output_io, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            output = output_io.getvalue()
        else:
            raise ValueError(f"Unsupported target format: {target_format}")
        
        return {
            "success": True,
            "source_format": source_format,
            "target_format": target_format,
            "output": output
        }
        
    except Exception as e:
        logger.error(f"Format conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))