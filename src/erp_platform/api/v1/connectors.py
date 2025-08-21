"""
ERP Connector API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from erp_platform.connectors.pool import ConnectionPoolManager
from erp_platform.core.logging import get_logger
from erp_platform.core.telemetry import track_request

router = APIRouter()
logger = get_logger(__name__)


class ConnectorRequest(BaseModel):
    """Request model for connector operations"""
    connector: str
    operation: str
    parameters: Dict[str, Any] = {}


class SAPRequest(BaseModel):
    """SAP-specific request model"""
    function_name: str
    parameters: Dict[str, Any] = {}
    tables: Optional[Dict[str, List]] = None


class SQLRequest(BaseModel):
    """SQL query request model"""
    query: str
    parameters: Optional[Dict[str, Any]] = None


async def get_pool_manager(request: Request) -> ConnectionPoolManager:
    """Dependency to get connection pool manager"""
    return request.app.state.pool_manager


@router.get("/status")
async def get_connectors_status(
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Get status of all configured connectors
    """
    return pool_manager.get_all_stats()


@router.post("/sap/execute")
@track_request("sap", "execute")
async def execute_sap_function(
    request: SAPRequest,
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Execute SAP RFC function or BAPI
    """
    try:
        async with pool_manager.get_connection("sap") as connector:
            result = await connector.execute(
                request.function_name,
                request.parameters
            )
            return {"success": True, "data": result}
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SAP execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sap/read-table")
@track_request("sap", "read_table")
async def read_sap_table(
    table_name: str,
    fields: Optional[List[str]] = None,
    where_clause: Optional[str] = None,
    max_rows: int = 100,
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Read data from SAP table
    """
    try:
        async with pool_manager.get_connection("sap") as connector:
            result = await connector.read_table(
                table_name=table_name,
                fields=fields,
                where_clause=where_clause,
                max_rows=max_rows
            )
            return {
                "success": True,
                "table": table_name,
                "row_count": len(result),
                "data": result
            }
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SAP table read failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/oracle/execute")
@track_request("oracle", "execute")
async def execute_oracle_query(
    request: SQLRequest,
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Execute Oracle SQL query
    """
    try:
        async with pool_manager.get_connection("oracle") as connector:
            result = await connector.execute(
                request.query,
                request.parameters
            )
            return {"success": True, "data": result}
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Oracle execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sqlserver/execute")
@track_request("sqlserver", "execute")
async def execute_sqlserver_query(
    request: SQLRequest,
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Execute SQL Server query
    """
    try:
        async with pool_manager.get_connection("sqlserver") as connector:
            result = await connector.execute(
                request.query,
                request.parameters
            )
            return {"success": True, "data": result}
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SQL Server execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generic/execute")
async def execute_generic(
    request: ConnectorRequest,
    pool_manager: ConnectionPoolManager = Depends(get_pool_manager)
) -> Dict[str, Any]:
    """
    Execute operation on any configured connector
    """
    try:
        async with pool_manager.get_connection(request.connector) as connector:
            # Dynamic method invocation
            method = getattr(connector, request.operation, None)
            if method is None:
                raise ValueError(f"Operation '{request.operation}' not supported")
            
            result = await method(**request.parameters)
            return {"success": True, "data": result}
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generic execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))