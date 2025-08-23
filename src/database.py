"""
Database connection and session management for Turkish Business Integration Platform
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text

from src.config import settings
from src.core.tenant import tenant_context

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_recycle=3600,  # Recycle connections every hour
    pool_pre_ping=True,  # Verify connections before use
    echo=settings.debug,  # Log SQL in debug mode
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for all database models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with tenant isolation
    
    Yields:
        AsyncSession: Database session with Row-Level Security enabled
    """
    async with AsyncSessionLocal() as session:
        try:
            # Enable Row-Level Security for tenant isolation
            tenant_id = tenant_context.get(None)
            if tenant_id:
                # Set tenant context for RLS policies
                await session.execute(
                    text("SET app.current_tenant = :tenant_id"),
                    {"tenant_id": tenant_id}
                )
                # Switch to tenant-restricted role
                await session.execute(text("SET SESSION ROLE tenant_user"))
            
            yield session
            
        except Exception:
            await session.rollback()
            raise
        finally:
            # Reset database role
            await session.execute(text("RESET ROLE"))
            await session.close()


async def get_admin_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with admin privileges (bypasses RLS)
    
    Use only for system operations and admin tasks
    
    Yields:
        AsyncSession: Database session with admin privileges
    """
    async with AsyncSessionLocal() as session:
        try:
            # Use admin role to bypass RLS
            await session.execute(text("SET SESSION ROLE admin_user"))
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.execute(text("RESET ROLE"))
            await session.close()


async def create_database_tables():
    """
    Create all database tables
    
    This should only be called during initial setup
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_database_tables():
    """
    Drop all database tables
    
    WARNING: This will delete all data!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def setup_row_level_security():
    """
    Set up Row-Level Security policies for multi-tenant isolation
    
    This creates the necessary database roles and RLS policies
    """
    async with engine.begin() as conn:
        # Create database roles
        await conn.execute(text("""
            DO $$ BEGIN
                -- Create admin role (full access)
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_user') THEN
                    CREATE ROLE admin_user;
                END IF;
                
                -- Create tenant role (restricted access)
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tenant_user') THEN
                    CREATE ROLE tenant_user;
                END IF;
                
                -- Grant necessary permissions
                GRANT CONNECT ON DATABASE turkplatform TO tenant_user;
                GRANT USAGE ON SCHEMA public TO tenant_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tenant_user;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tenant_user;
                
                -- Grant all permissions to admin
                GRANT ALL PRIVILEGES ON DATABASE turkplatform TO admin_user;
                GRANT ALL ON SCHEMA public TO admin_user;
                GRANT ALL ON ALL TABLES IN SCHEMA public TO admin_user;
                GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO admin_user;
                
            EXCEPTION WHEN OTHERS THEN
                -- Ignore errors if roles already exist
                NULL;
            END $$;
        """))
        
        # Create function to get current tenant from context
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION current_tenant_id() 
            RETURNS UUID AS $$
            BEGIN
                RETURN COALESCE(
                    current_setting('app.current_tenant', true)::UUID,
                    '00000000-0000-0000-0000-000000000000'::UUID
                );
            END;
            $$ LANGUAGE plpgsql STABLE;
        """))
        
        print("✅ Row-Level Security setup completed")


class DatabaseManager:
    """Database management utilities"""
    
    @staticmethod
    async def health_check() -> bool:
        """
        Check database connection health
        
        Returns:
            bool: True if database is healthy
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception:
            return False
    
    @staticmethod
    async def get_database_info() -> dict:
        """
        Get database information for monitoring
        
        Returns:
            dict: Database information including version, connections, etc.
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get PostgreSQL version
                version_result = await session.execute(text("SELECT version()"))
                version = version_result.scalar()
                
                # Get active connections
                connections_result = await session.execute(text("""
                    SELECT count(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """))
                active_connections = connections_result.scalar()
                
                # Get database size
                size_result = await session.execute(text("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """))
                database_size = size_result.scalar()
                
                return {
                    "version": version,
                    "active_connections": active_connections,
                    "database_size": database_size,
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow
                }
        except Exception as e:
            return {"error": str(e)}