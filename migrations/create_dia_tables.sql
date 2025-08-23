-- DIA ERP Integration Tables Migration
-- Creates tables for DIA data synchronization

-- Create DIA Cari Kartlar table
CREATE TABLE IF NOT EXISTS dia_cari_kartlar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- DIA specific fields
    dia_key INTEGER,
    dia_level1 INTEGER, -- Firma kodu
    dia_level2 INTEGER, -- Dönem kodu
    carikartkodu VARCHAR(50) NOT NULL,
    unvan VARCHAR(250) NOT NULL,
    carikarttipi VARCHAR(10) NOT NULL, -- AL/SAT/ALSAT
    verginumarasi VARCHAR(50),
    vergidairesi VARCHAR(100),
    dia_key_sis_bolge INTEGER,
    dia_key_sis_temsilci INTEGER,
    aktif BOOLEAN DEFAULT TRUE,
    dia_cdate TIMESTAMP,
    dia_user VARCHAR(50),
    
    -- Sync metadata
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending', -- pending/synced/error
    sync_error TEXT,
    
    -- System fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    CONSTRAINT ck_dia_cari_kartlar_tipi CHECK (carikarttipi IN ('AL', 'SAT', 'ALSAT')),
    CONSTRAINT ck_dia_cari_kartlar_sync_status CHECK (sync_status IN ('pending', 'synced', 'error'))
);

-- Create indexes for DIA Cari Kartlar
CREATE INDEX IF NOT EXISTS idx_dia_cari_kartlar_tenant_id ON dia_cari_kartlar(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dia_cari_kartlar_dia_key ON dia_cari_kartlar(dia_key);
CREATE INDEX IF NOT EXISTS idx_dia_cari_kartlar_lookup ON dia_cari_kartlar(tenant_id, dia_level1, carikartkodu);
CREATE INDEX IF NOT EXISTS idx_dia_cari_kartlar_sync_status ON dia_cari_kartlar(sync_status);
CREATE INDEX IF NOT EXISTS idx_dia_cari_kartlar_last_sync ON dia_cari_kartlar(last_sync_at);

-- Create unique constraint for tenant + DIA key combination
CREATE UNIQUE INDEX IF NOT EXISTS idx_dia_cari_kartlar_unique 
ON dia_cari_kartlar(tenant_id, dia_key, dia_level1) 
WHERE dia_key IS NOT NULL;

-- Create DIA Stok Kartlar table
CREATE TABLE IF NOT EXISTS dia_stok_kartlar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- DIA specific fields
    dia_key INTEGER,
    dia_level1 INTEGER, -- Firma kodu
    dia_level2 INTEGER, -- Dönem kodu
    stokkartkodu VARCHAR(50) NOT NULL,
    stokkartadi VARCHAR(250) NOT NULL,
    stokkarttipi VARCHAR(20) NOT NULL, -- MALZEME/HIZMET/SABIT_KIYMET
    dia_key_sis_stokgrubu INTEGER,
    dia_key_sis_birim INTEGER,
    kdvorani DECIMAL(18,4) DEFAULT 0,
    satisfiyati DECIMAL(18,4) DEFAULT 0,
    aktif BOOLEAN DEFAULT TRUE,
    dia_cdate TIMESTAMP,
    dia_user VARCHAR(50),
    
    -- Sync metadata
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',
    sync_error TEXT,
    
    -- System fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    CONSTRAINT ck_dia_stok_kartlar_tipi CHECK (stokkarttipi IN ('MALZEME', 'HIZMET', 'SABIT_KIYMET')),
    CONSTRAINT ck_dia_stok_kartlar_sync_status CHECK (sync_status IN ('pending', 'synced', 'error'))
);

-- Create indexes for DIA Stok Kartlar
CREATE INDEX IF NOT EXISTS idx_dia_stok_kartlar_tenant_id ON dia_stok_kartlar(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dia_stok_kartlar_dia_key ON dia_stok_kartlar(dia_key);
CREATE INDEX IF NOT EXISTS idx_dia_stok_kartlar_lookup ON dia_stok_kartlar(tenant_id, dia_level1, stokkartkodu);
CREATE INDEX IF NOT EXISTS idx_dia_stok_kartlar_sync_status ON dia_stok_kartlar(sync_status);

-- Create unique constraint for tenant + DIA key combination
CREATE UNIQUE INDEX IF NOT EXISTS idx_dia_stok_kartlar_unique 
ON dia_stok_kartlar(tenant_id, dia_key, dia_level1) 
WHERE dia_key IS NOT NULL;

-- Create DIA Fatura Fişleri table
CREATE TABLE IF NOT EXISTS dia_fatura_fisler (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- DIA specific fields
    dia_key INTEGER,
    dia_level1 INTEGER, -- Firma kodu
    dia_level2 INTEGER, -- Dönem kodu
    faturafisnumarasi VARCHAR(50) NOT NULL,
    faturafistarihi DATE NOT NULL,
    dia_key_scf_carikart INTEGER NOT NULL,
    toplamtutar DECIMAL(18,4) NOT NULL,
    kdvtoplami DECIMAL(18,4) NOT NULL,
    faturatipi VARCHAR(10) NOT NULL, -- ALIS/SATIS
    dia_cdate TIMESTAMP,
    dia_user VARCHAR(50),
    
    -- Sync metadata
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(20) DEFAULT 'pending',
    sync_error TEXT,
    
    -- System fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    CONSTRAINT ck_dia_fatura_fisler_tipi CHECK (faturatipi IN ('ALIS', 'SATIS')),
    CONSTRAINT ck_dia_fatura_fisler_sync_status CHECK (sync_status IN ('pending', 'synced', 'error'))
);

-- Create indexes for DIA Fatura Fişleri
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_tenant_id ON dia_fatura_fisler(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_dia_key ON dia_fatura_fisler(dia_key);
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_lookup ON dia_fatura_fisler(tenant_id, dia_level1, faturafisnumarasi);
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_tarih ON dia_fatura_fisler(faturafistarihi);
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_cari ON dia_fatura_fisler(dia_key_scf_carikart);
CREATE INDEX IF NOT EXISTS idx_dia_fatura_fisler_sync_status ON dia_fatura_fisler(sync_status);

-- Create unique constraint for tenant + DIA key combination
CREATE UNIQUE INDEX IF NOT EXISTS idx_dia_fatura_fisler_unique 
ON dia_fatura_fisler(tenant_id, dia_key, dia_level1) 
WHERE dia_key IS NOT NULL;

-- Enable Row Level Security for DIA tables
ALTER TABLE dia_cari_kartlar ENABLE ROW LEVEL SECURITY;
ALTER TABLE dia_stok_kartlar ENABLE ROW LEVEL SECURITY;
ALTER TABLE dia_fatura_fisler ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for DIA tables
-- These policies ensure tenants can only access their own data

-- Cari Kartlar RLS policies
CREATE POLICY dia_cari_kartlar_tenant_isolation ON dia_cari_kartlar
    FOR ALL TO application_user
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Stok Kartlar RLS policies  
CREATE POLICY dia_stok_kartlar_tenant_isolation ON dia_stok_kartlar
    FOR ALL TO application_user
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Fatura Fişleri RLS policies
CREATE POLICY dia_fatura_fisler_tenant_isolation ON dia_fatura_fisler
    FOR ALL TO application_user
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_dia_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_dia_cari_kartlar_updated_at 
    BEFORE UPDATE ON dia_cari_kartlar 
    FOR EACH ROW EXECUTE FUNCTION update_dia_updated_at_column();

CREATE TRIGGER update_dia_stok_kartlar_updated_at 
    BEFORE UPDATE ON dia_stok_kartlar 
    FOR EACH ROW EXECUTE FUNCTION update_dia_updated_at_column();

CREATE TRIGGER update_dia_fatura_fisler_updated_at 
    BEFORE UPDATE ON dia_fatura_fisler 
    FOR EACH ROW EXECUTE FUNCTION update_dia_updated_at_column();

-- Insert migration record
INSERT INTO schema_migrations (version, applied_at) 
VALUES ('dia_tables_001', NOW()) 
ON CONFLICT (version) DO NOTHING;