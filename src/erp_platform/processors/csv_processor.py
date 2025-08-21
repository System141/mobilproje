"""
CSV data processor
"""

import csv
import io
from typing import Any, Dict, List, Optional
import asyncio

from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class CSVProcessor:
    """
    CSV file processor
    """
    
    def __init__(self, delimiter: str = ',', quotechar: str = '"'):
        self.delimiter = delimiter
        self.quotechar = quotechar
    
    async def process(
        self,
        file_obj: io.StringIO,
        has_header: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process CSV file and return list of dictionaries
        """
        loop = asyncio.get_event_loop()
        
        def _process():
            reader = csv.DictReader(
                file_obj,
                delimiter=self.delimiter,
                quotechar=self.quotechar
            ) if has_header else csv.reader(
                file_obj,
                delimiter=self.delimiter,
                quotechar=self.quotechar
            )
            
            if has_header:
                return list(reader)
            else:
                # If no header, create generic column names
                data = list(reader)
                if data:
                    headers = [f"col_{i}" for i in range(len(data[0]))]
                    return [dict(zip(headers, row)) for row in data]
                return []
        
        result = await loop.run_in_executor(None, _process)
        
        logger.info(f"Processed CSV: {len(result)} rows")
        return result
    
    async def write(
        self,
        data: List[Dict[str, Any]],
        file_path: str,
        headers: Optional[List[str]] = None
    ):
        """
        Write data to CSV file
        """
        if not data:
            logger.warning("No data to write")
            return
        
        loop = asyncio.get_event_loop()
        
        def _write():
            # Get headers from first row if not provided
            if headers is None:
                headers = list(data[0].keys())
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=headers,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar
                )
                writer.writeheader()
                writer.writerows(data)
        
        await loop.run_in_executor(None, _write)
        
        logger.info(f"Wrote {len(data)} rows to {file_path}")
    
    async def stream_process(
        self,
        file_path: str,
        chunk_size: int = 1000,
        callback: callable = None
    ):
        """
        Stream process large CSV files
        """
        loop = asyncio.get_event_loop()
        
        def _stream():
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(
                    f,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar
                )
                
                chunk = []
                for row in reader:
                    chunk.append(row)
                    
                    if len(chunk) >= chunk_size:
                        if callback:
                            callback(chunk)
                        chunk = []
                
                # Process remaining rows
                if chunk and callback:
                    callback(chunk)
        
        await loop.run_in_executor(None, _stream)
        
        logger.info(f"Stream processed {file_path}")