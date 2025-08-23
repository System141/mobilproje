# DIA Models - Kapsamlı Database Schema Analiz Raporu

## Executive Summary

DIA ERP sisteminin veri modeli, **34 modül** ve **2000+ tablo** içeren kapsamlı bir yapıdır. Bu analiz, hibrit Python-C++ ERP platformumuz için kritik entegrasyon bilgilerini içermektedir.

## 1. Modül Hiyerarşisi ve Öncelik Sıralaması

### 1.1. Tier 1 - Kritik Modüller (Öncelik: Yüksek)
| Modül | Tablo Sayısı* | Ana İşlev | Entegrasyon Önemi |
|-------|--------------|-----------|-------------------|
| **SCF** | 150+ | Stok-Cari-Fatura | ⭐⭐⭐⭐⭐ |
| **SIS** | 80+ | Sistem/Kullanıcı Yönetimi | ⭐⭐⭐⭐⭐ |
| **MUH** | 60+ | Muhasebe/Mali İşlemler | ⭐⭐⭐⭐ |
| **GTS** | 40+ | Görev Takip/CRM | ⭐⭐⭐⭐ |

### 1.2. Tier 2 - İkincil Modüller (Öncelik: Orta)
| Modül | Ana İşlev | Entegrasyon Senaryosu |
|-------|-----------|---------------------|
| **PER** | Personel/HR | Bordro entegrasyonu |
| **BCS** | Banka/Çek/Senet | Finansal workflow |
| **PRJ** | Proje Yönetimi | Task management |
| **WEB** | E-ticaret | B2B/B2C platformlar |

## 2. SCF Modülü - Detaylı Schema Analizi

### 2.1. Ana Veri Yapıları

#### 2.1.1. scf_carikart (Cari Kartları)
```sql
-- Ana cari kart tablosu
CREATE TABLE scf_carikart (
    _key INTEGER PRIMARY KEY,           -- Cari ID
    _level1 INTEGER,                    -- Firma kodu
    _level2 INTEGER,                    -- Dönem kodu
    carikartkodu VARCHAR(50),           -- Cari kodu (unique per firma)
    unvan VARCHAR(250),                 -- Cari unvan
    carikarttipi VARCHAR(10),           -- AL/SAT/ALSAT
    verginumarasi VARCHAR(50),          -- Vergi/TC numarası
    vergidairesi VARCHAR(100),          -- Vergi dairesi
    _key_sis_bolge INTEGER,             -- FK: sis_bolge
    _key_sis_temsilci INTEGER,          -- FK: sis_temsilci
    _cdate DATETIME,                    -- Oluşturma tarihi
    _user VARCHAR(50),                  -- Oluşturan kullanıcı
    aktif BOOLEAN DEFAULT 1             -- Aktiflik durumu
);
```

#### 2.1.2. scf_stokkart (Stok Kartları) 
```sql
CREATE TABLE scf_stokkart (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    _level2 INTEGER,
    stokkartkodu VARCHAR(50),           -- Stok kodu
    stokkartadi VARCHAR(250),           -- Stok adı
    stokkarttipi VARCHAR(10),           -- MALZEME/HIZMET/SABIT_KIYMET
    _key_sis_stokgrubu INTEGER,         -- FK: Stok grubu
    _key_sis_birim INTEGER,             -- FK: Birim
    kdvorani DECIMAL(18,4),             -- KDV oranı
    satisfiyati DECIMAL(18,4),          -- Satış fiyatı
    _cdate DATETIME,
    _user VARCHAR(50),
    aktif BOOLEAN DEFAULT 1
);
```

#### 2.1.3. scf_faturafisi (Fatura Fişleri)
```sql
CREATE TABLE scf_faturafisi (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    _level2 INTEGER,
    faturafisnumarasi VARCHAR(50),      -- Fatura numarası
    faturafistarihi DATE,               -- Fatura tarihi
    _key_scf_carikart INTEGER,          -- FK: Cari kart
    toplamtutar DECIMAL(18,4),          -- Toplam tutar
    kdvtoplami DECIMAL(18,4),           -- KDV toplamı
    faturatipi VARCHAR(10),             -- ALIS/SATIS
    _cdate DATETIME,
    _user VARCHAR(50)
);
```

### 2.2. İlişki Haritalandırması
```
scf_carikart (1) ←→ (N) scf_faturafisi
scf_stokkart (1) ←→ (N) scf_faturafisidetay  
scf_faturafisi (1) ←→ (N) scf_faturafisidetay
sis_birim (1) ←→ (N) scf_stokkart
sis_stokgrubu (1) ←→ (N) scf_stokkart
```

## 3. SIS Modülü - Sistem Altyapısı

### 3.1. Kullanıcı ve Yetkilendirme
```sql
-- Kullanıcı tablosu
CREATE TABLE sis_kullanici (
    _key INTEGER PRIMARY KEY,
    kullaniciadi VARCHAR(50) UNIQUE,
    sifre VARCHAR(255),                 -- Encrypted
    adsoyad VARCHAR(100),
    eposta VARCHAR(150),
    telefon VARCHAR(50),
    aktif BOOLEAN DEFAULT 1,
    _cdate DATETIME
);

-- Firma tanımları
CREATE TABLE sis_firma (
    _key INTEGER PRIMARY KEY,
    firmakodu INTEGER UNIQUE,
    firmaadi VARCHAR(150),
    verginumarasi VARCHAR(50),
    adres TEXT,
    aktif BOOLEAN DEFAULT 1
);
```

### 3.2. Kod Tanımları (Master Data)
```sql
-- Stok grupları
CREATE TABLE sis_stokgrubu (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,                    -- Firma
    kod VARCHAR(50),
    ad VARCHAR(150),
    aktif BOOLEAN DEFAULT 1
);

-- Birimler
CREATE TABLE sis_birim (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    kod VARCHAR(20),
    ad VARCHAR(50),
    aktif BOOLEAN DEFAULT 1
);

-- Bölgeler
CREATE TABLE sis_bolge (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    kod VARCHAR(50),
    ad VARCHAR(100),
    aktif BOOLEAN DEFAULT 1
);
```

## 4. MUH Modülü - Muhasebe Sistemi

### 4.1. Hesap Planı
```sql
CREATE TABLE muh_hesapkart (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    _level2 INTEGER,
    hesapkodu VARCHAR(50),              -- 100.01.001 formatında
    hesapadi VARCHAR(250),
    hesaptipi VARCHAR(20),              -- AKTIF/PASIF/GELIR/GIDER
    _key_parent INTEGER,                -- Self-referencing FK
    aktif BOOLEAN DEFAULT 1,
    _cdate DATETIME
);
```

### 4.2. Muhasebe Fişleri
```sql
CREATE TABLE muh_muhfis (
    _key INTEGER PRIMARY KEY,
    _level1 INTEGER,
    _level2 INTEGER,
    fisnumarasi VARCHAR(50),
    fistarih DATE,
    aciklama TEXT,
    toplamborc DECIMAL(18,4),
    toplamalacak DECIMAL(18,4),
    _cdate DATETIME,
    _user VARCHAR(50)
);

CREATE TABLE muh_muhfisdetay (
    _key INTEGER PRIMARY KEY,
    _key_muh_muhfis INTEGER,            -- FK: Ana fiş
    _key_muh_hesapkart INTEGER,         -- FK: Hesap kartı
    borc DECIMAL(18,4),
    alacak DECIMAL(18,4),
    aciklama VARCHAR(500)
);
```

## 5. Veri Standardları ve Kuralları

### 5.1. Naming Convention
- **Primary Key**: `_key` (INTEGER, Auto-increment)
- **Firma/Dönem**: `_level1`, `_level2` (INTEGER)
- **Foreign Key**: `_key_[tablo_adı]` (INTEGER)
- **Audit Fields**: `_cdate`, `_date`, `_user`, `_owner`
- **Status**: `aktif` (BOOLEAN, Default: 1)

### 5.2. Veri Tipleri Standardı
```sql
-- Temel tipler
INTEGER              -- ID'ler, kodlar
VARCHAR(50)          -- Kısa metinler, kodlar
VARCHAR(250)         -- Uzun metinler, açıklamalar
TEXT                 -- Sınırsız metin
DECIMAL(18,4)        -- Para, miktar
DATE                 -- Tarih
DATETIME             -- Zaman damgası
BOOLEAN              -- Aktiflik, flag'ler
```

### 5.3. İş Kuralları
- **Firma İzolasyonu**: Tüm veriler `_level1` ile izole
- **Dönem Yönetimi**: Mali veriler `_level2` ile ayrışır
- **Soft Delete**: `aktif=0` ile pasif hale getirilir
- **Audit Trail**: Tüm değişiklikler `_cdate`/`_user` ile izlenir

## 6. Entegrasyon Geliştirme Önerileri

### 6.1. Python ORM Modeli Önerisi
```python
# SQLAlchemy modeli örneği
from sqlalchemy import Column, Integer, String, Decimal, Boolean, ForeignKey
from sqlalchemy.orm import relationship

class SCFCariKart(Base):
    __tablename__ = 'scf_carikart'
    
    _key = Column(Integer, primary_key=True)
    _level1 = Column(Integer, nullable=False)  # Firma
    _level2 = Column(Integer, nullable=False)  # Dönem
    carikartkodu = Column(String(50), nullable=False)
    unvan = Column(String(250), nullable=False)
    carikarttipi = Column(String(10), nullable=False)  # AL/SAT/ALSAT
    verginumarasi = Column(String(50))
    aktif = Column(Boolean, default=True)
    
    # Foreign Key relationships
    _key_sis_bolge = Column(Integer, ForeignKey('sis_bolge._key'))
    
    # Relationships
    faturalar = relationship("SCFFaturaFisi", back_populates="cari")
```

### 6.2. Polars DataFrame Optimizasyonu
```python
import polars as pl

# Efficient data loading for large datasets
def load_cari_kartlar(firma_kodu: int) -> pl.DataFrame:
    query = """
    SELECT _key, carikartkodu, unvan, carikarttipi, verginumarasi
    FROM scf_carikart 
    WHERE _level1 = ? AND aktif = 1
    ORDER BY carikartkodu
    """
    
    # Lazy evaluation kullanımı
    df = pl.read_database_uri(query, connection_uri, [firma_kodu])
    return df.lazy().filter(pl.col("aktif") == True).collect()
```

### 6.3. Cython Acceleration için Hedef Alanlar
```python
# High-frequency operations için C++ acceleration
@cython.optimize.unpack_method_calls(False)
def calculate_fatura_total(
    detaylar: List[FaturaDetay]
) -> Tuple[Decimal, Decimal]:
    """
    Fatura detaylarından toplam ve KDV hesabı
    C++ optimizasyon için ideal
    """
    toplam_tutar = Decimal('0.00')
    kdv_toplami = Decimal('0.00')
    
    for detay in detaylar:
        birim_fiyat = detay.birimfiyat
        miktar = detay.miktar
        kdv_oran = detay.kdvorani
        
        satir_tutari = birim_fiyat * miktar
        kdv_tutari = satir_tutari * kdv_oran / 100
        
        toplam_tutar += satir_tutari + kdv_tutari
        kdv_toplami += kdv_tutari
    
    return toplam_tutar, kdv_toplami
```

## 7. Database Migration Stratejisi

### 7.1. Schema Validation
```python
def validate_dia_schema(connection_string: str) -> bool:
    """DIA database schema validation"""
    required_tables = [
        'scf_carikart', 'scf_stokkart', 'scf_faturafisi',
        'sis_kullanici', 'sis_firma', 'muh_hesapkart'
    ]
    
    # Validation logic
    return all(table_exists(table) for table in required_tables)
```

### 7.2. Data Synchronization
- **Incremental Sync**: `_cdate` / `_date` fields kullanımı
- **Delta Detection**: Timestamp-based change tracking
- **Conflict Resolution**: Last-write-wins stratejisi

## 8. Performance Optimization Stratejisi

### 8.1. Indexing Recommendations
```sql
-- SCF modülü için kritik index'ler
CREATE INDEX idx_scf_carikart_lookup ON scf_carikart(_level1, carikartkodu);
CREATE INDEX idx_scf_carikart_type ON scf_carikart(_level1, carikarttipi);
CREATE INDEX idx_scf_stokkart_lookup ON scf_stokkart(_level1, stokkartkodu);
CREATE INDEX idx_scf_faturafisi_tarih ON scf_faturafisi(_level1, faturafistarihi);
CREATE INDEX idx_scf_faturafisi_cari ON scf_faturafisi(_key_scf_carikart);
```

### 8.2. Query Optimization Patterns
```python
# Efficient multi-table queries
OPTIMIZED_CARI_FATURA_QUERY = """
SELECT 
    c.carikartkodu,
    c.unvan,
    f.faturafisnumarasi,
    f.faturafistarihi,
    f.toplamtutar
FROM scf_carikart c
INNER JOIN scf_faturafisi f ON c._key = f._key_scf_carikart
WHERE c._level1 = :firma_kodu 
    AND c.aktif = 1
    AND f.faturafistarihi >= :baslangic_tarih
ORDER BY f.faturafistarihi DESC
LIMIT :limit_count
"""
```

## 9. Entegrasyon Implementasyon Roadmap

### 9.1. Phase 1 - Foundation (4-6 hafta)
1. **Database Schema Mapping** (1 hafta)
   - Core table mappings (SCF, SIS)
   - SQLAlchemy model oluşturma
   - Relationship tanımları

2. **Basic CRUD Operations** (2 hafta)
   - SCF_CariKart CRUD
   - SCF_StokKart CRUD  
   - Basic validation logic

3. **Connection Pool & Session Management** (1 hafta)
   - AsyncIO database pool
   - Session lifecycle management
   - Error handling patterns

4. **Unit Testing Framework** (1-2 hafta)
   - SQLAlchemy test fixtures
   - Mock data generation
   - Integration test setup

### 9.2. Phase 2 - Advanced Features (6-8 hafta)
1. **Complex Business Logic** (3 hafta)
   - Fatura calculation engine
   - Stok hareket tracking
   - Mali rapor generators

2. **Performance Optimization** (2 hafta)
   - Polars DataFrame integration
   - Bulk operation optimizations
   - Query performance tuning

3. **Cython Acceleration** (2-3 hafta)
   - Mathematical calculation modules
   - High-frequency data processing
   - Performance benchmarking

### 9.3. Phase 3 - Production (4-6 hafta)
1. **Advanced Features** (2-3 hafta)
   - Multi-company support
   - Real-time data sync
   - Advanced reporting

2. **Production Hardening** (2-3 hafta)
   - Security audit
   - Performance testing
   - Monitoring integration

## 10. Risk Assessment ve Mitigation

### 10.1. Yüksek Risk Alanları
1. **Performance**: 2000+ tablo ile query complexity
   - **Mitigation**: Index optimization, query caching
   
2. **Data Consistency**: Multi-company data isolation
   - **Mitigation**: Row-level security, strict validation

3. **API Compatibility**: DIA version updates
   - **Mitigation**: Versioning strategy, backward compatibility

### 10.2. Monitoring Requirements
- Query performance metrics
- Data sync success rates
- Error rate tracking
- Resource utilization monitoring

## Sonuç

DIA Models analizi, hibrit Python-C++ ERP platformumuz için solid foundation sağlamaktadır. **34 modül** ve **2000+ tablo** içeren kapsamlı yapı, **SCF modülü** öncelikli olmak üzere aşamalı entegrasyon stratejisi gerektirmektedir.

**Tavsiye Edilen Yaklaşım**: 
1. **SCF + SIS** modülleri ile başlangıç (Tier 1)
2. **Polars** ile high-performance data processing 
3. **Cython** ile mathematical operations acceleration
4. **FastAPI** ile modern REST API exposure

Bu strateji ile **6 aylık implementasyon** süreci içinde production-ready DIA entegrasyonu sağlanabilecektir.