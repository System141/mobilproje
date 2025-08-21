"""
High-performance data processing using Polars
"""

import polars as pl
from typing import Any, Dict, List, Optional, Union
import io
import asyncio

from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class PolarsProcessor:
    """
    Data processor using Polars for high-performance operations
    """
    
    async def read_csv(
        self,
        file_path: Union[str, io.BytesIO],
        **kwargs
    ) -> pl.DataFrame:
        """
        Read CSV file using Polars lazy evaluation
        """
        loop = asyncio.get_event_loop()
        
        def _read():
            if isinstance(file_path, str):
                return pl.scan_csv(file_path, **kwargs).collect()
            else:
                return pl.read_csv(file_path, **kwargs)
        
        df = await loop.run_in_executor(None, _read)
        
        logger.info(f"Read CSV: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    async def read_parquet(
        self,
        file_path: str,
        **kwargs
    ) -> pl.DataFrame:
        """
        Read Parquet file
        """
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            pl.scan_parquet,
            file_path,
            **kwargs
        )
        df = await loop.run_in_executor(None, df.collect)
        
        logger.info(f"Read Parquet: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    async def process_large_file(
        self,
        file_path: str,
        chunk_size: int = 10000,
        operations: List[Dict[str, Any]] = None
    ) -> pl.DataFrame:
        """
        Process large file with streaming and lazy evaluation
        """
        loop = asyncio.get_event_loop()
        
        # Create lazy frame
        lazy_df = await loop.run_in_executor(
            None,
            pl.scan_csv,
            file_path
        )
        
        # Apply operations
        if operations:
            for op in operations:
                lazy_df = await self._apply_lazy_operation(lazy_df, op)
        
        # Collect results
        result = await loop.run_in_executor(None, lazy_df.collect)
        
        logger.info(f"Processed large file: {result.shape}")
        return result
    
    async def _apply_lazy_operation(
        self,
        lazy_df: pl.LazyFrame,
        operation: Dict[str, Any]
    ) -> pl.LazyFrame:
        """
        Apply operation to lazy dataframe
        """
        op_type = operation.get("type")
        
        if op_type == "filter":
            condition = operation.get("condition")
            lazy_df = lazy_df.filter(pl.col(condition["column"]) == condition["value"])
            
        elif op_type == "select":
            columns = operation.get("columns")
            lazy_df = lazy_df.select(columns)
            
        elif op_type == "group_by":
            group_cols = operation.get("columns")
            agg_ops = operation.get("aggregations", {})
            
            agg_exprs = []
            for col, func in agg_ops.items():
                if func == "sum":
                    agg_exprs.append(pl.col(col).sum().alias(f"{col}_sum"))
                elif func == "mean":
                    agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
                elif func == "count":
                    agg_exprs.append(pl.col(col).count().alias(f"{col}_count"))
            
            lazy_df = lazy_df.group_by(group_cols).agg(agg_exprs)
            
        elif op_type == "sort":
            columns = operation.get("columns")
            descending = operation.get("descending", False)
            lazy_df = lazy_df.sort(columns, descending=descending)
            
        elif op_type == "join":
            other_path = operation.get("other_file")
            join_on = operation.get("on")
            how = operation.get("how", "inner")
            
            other_lazy = pl.scan_csv(other_path)
            lazy_df = lazy_df.join(other_lazy, on=join_on, how=how)
        
        return lazy_df
    
    async def apply_operation(
        self,
        df: pl.DataFrame,
        operation: Dict[str, Any]
    ) -> pl.DataFrame:
        """
        Apply operation to dataframe
        """
        loop = asyncio.get_event_loop()
        
        def _apply():
            op_type = operation.get("type")
            
            if op_type == "filter":
                condition = operation.get("condition")
                return df.filter(pl.col(condition["column"]) == condition["value"])
                
            elif op_type == "select":
                columns = operation.get("columns")
                return df.select(columns)
                
            elif op_type == "transform":
                transformations = operation.get("transformations", {})
                for col, expr in transformations.items():
                    df = df.with_columns(eval(expr).alias(col))
                return df
                
            elif op_type == "pivot":
                return df.pivot(
                    values=operation.get("values"),
                    index=operation.get("index"),
                    columns=operation.get("columns")
                )
                
            return df
        
        result = await loop.run_in_executor(None, _apply)
        return result
    
    async def aggregate(
        self,
        df: pl.DataFrame,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> pl.DataFrame:
        """
        Perform aggregations on dataframe
        """
        loop = asyncio.get_event_loop()
        
        def _aggregate():
            agg_exprs = []
            
            for col, func in aggregations.items():
                if func == "sum":
                    agg_exprs.append(pl.col(col).sum().alias(f"{col}_sum"))
                elif func == "mean":
                    agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
                elif func == "median":
                    agg_exprs.append(pl.col(col).median().alias(f"{col}_median"))
                elif func == "min":
                    agg_exprs.append(pl.col(col).min().alias(f"{col}_min"))
                elif func == "max":
                    agg_exprs.append(pl.col(col).max().alias(f"{col}_max"))
                elif func == "count":
                    agg_exprs.append(pl.col(col).count().alias(f"{col}_count"))
                elif func == "std":
                    agg_exprs.append(pl.col(col).std().alias(f"{col}_std"))
            
            return df.group_by(group_by).agg(agg_exprs)
        
        result = await loop.run_in_executor(None, _aggregate)
        
        logger.info(f"Aggregated data: {result.shape}")
        return result
    
    async def join_dataframes(
        self,
        left: pl.DataFrame,
        right: pl.DataFrame,
        on: Union[str, List[str]],
        how: str = "inner"
    ) -> pl.DataFrame:
        """
        Join two dataframes
        """
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            left.join,
            right,
            on,
            how
        )
        
        logger.info(f"Joined dataframes: {result.shape}")
        return result
    
    async def optimize_memory(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Optimize dataframe memory usage
        """
        loop = asyncio.get_event_loop()
        
        def _optimize():
            # Downcast numeric types
            for col in df.columns:
                dtype = df[col].dtype
                
                if dtype == pl.Int64:
                    min_val = df[col].min()
                    max_val = df[col].max()
                    
                    if min_val >= -128 and max_val <= 127:
                        df = df.with_columns(pl.col(col).cast(pl.Int8))
                    elif min_val >= -32768 and max_val <= 32767:
                        df = df.with_columns(pl.col(col).cast(pl.Int16))
                    elif min_val >= -2147483648 and max_val <= 2147483647:
                        df = df.with_columns(pl.col(col).cast(pl.Int32))
                
                elif dtype == pl.Float64:
                    df = df.with_columns(pl.col(col).cast(pl.Float32))
            
            return df
        
        optimized = await loop.run_in_executor(None, _optimize)
        
        logger.info("Optimized dataframe memory usage")
        return optimized
    
    async def to_parquet(
        self,
        df: pl.DataFrame,
        file_path: str,
        compression: str = "snappy"
    ):
        """
        Save dataframe to Parquet format
        """
        loop = asyncio.get_event_loop()
        
        await loop.run_in_executor(
            None,
            df.write_parquet,
            file_path,
            compression
        )
        
        logger.info(f"Saved to Parquet: {file_path}")
    
    async def profile_data(self, df: pl.DataFrame) -> Dict[str, Any]:
        """
        Generate data profile statistics
        """
        loop = asyncio.get_event_loop()
        
        def _profile():
            profile = {
                "shape": df.shape,
                "columns": df.columns,
                "dtypes": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
                "null_counts": {col: df[col].null_count() for col in df.columns},
                "memory_usage": df.estimated_size(),
                "statistics": {}
            }
            
            for col in df.columns:
                if df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64, 
                                     pl.Float32, pl.Float64]:
                    profile["statistics"][col] = {
                        "mean": df[col].mean(),
                        "std": df[col].std(),
                        "min": df[col].min(),
                        "max": df[col].max(),
                        "median": df[col].median(),
                    }
            
            return profile
        
        profile = await loop.run_in_executor(None, _profile)
        
        logger.info("Generated data profile")
        return profile