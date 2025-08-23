# DIA Web Servis API - Kapsamlı Entegrasyon Analiz Raporu

## Executive Summary

DIA Web Servis API, Türkiye'nin önde gelen ERP sistemlerinden DIA'nın web servis tabanlı entegrasyon çözümüdür. **JSON REST Web Service** mimarisini kullanan bu API, kapsamlı CRUD operasyonları, güçlü güvenlik özellikleri ve geniş modül desteği sunmaktadır.

## 1. Teknik Mimari ve Protokoller

### 1.1. Temel Protokol Bilgileri
- **Protokol**: JSON REST Web Service  
- **Güvenlik**: SSL/TLS 1.2+ (30 Ekim 2022'den itibaren zorunlu)
- **Authentication**: Session-based authentication + API Key
- **Base URL Format**: `https://SUNUCUKODU.ws.dia.com.tr/api/v3/{MODULE}/json`

### 1.2. Session ve Güvenlik Yönetimi
```json
// Login Request
{
  "login": {
    "username": "kullanici_adi",
    "password": "sifre",  
    "disconnect_same_user": "True",
    "params": {"apikey": "YOUR_API_KEY"}
  }
}

// Response
{
  "code": "200",
  "msg": "b2d4820cc43f4d98a8c6698686b6d386"  // session_id
}
```

**Kritik Güvenlik Özellikleri**:
- Session timeout: 1 saat (her çağrıda reset)
- IP kısıtlaması (opsiyonel)
- Kullanıcı yetki kontrolü (masaüstü yetkilerine bağlı)
- API Key zorunluluğu

## 2. CRUD Operasyon Detayları

### 2.1. Servis Naming Convention
- **Listeleme**: `{model}_listele` (örn: `scf_carikart_listele`)
- **Getirme**: `{model}_getir` (örn: `scf_carikart_getir`)  
- **Ekleme**: `{model}_ekle` (örn: `scf_carikart_ekle`)
- **Güncelleme**: `{model}_guncelle` (örn: `scf_carikart_guncelle`)
- **Silme**: `{model}_sil` (örn: `scf_carikart_sil`)

### 2.2. Listeleme Servisleri - Gelişmiş Filtreleme
```json
{
  "scf_carikart_listele": {
    "session_id": "SESSION_ID",
    "firma_kodu": 34,
    "donem_kodu": 1,
    "filters": [
      {"field": "carikarttipi", "operator": "=", "value": "AL"},
      {"field": "_date", "operator": ">=", "value": "2023-01-01"}
    ],
    "sorts": [{"field": "carikartkodu", "sorttype": "DESC"}],
    "limit": 100,
    "offset": 0,
    "params": {"selectedcolumns": ["carikartkodu", "unvan"]}
  }
}
```

**Desteklenen Operatörler**: `<`, `>`, `<=`, `>=`, `!`, `=`, `IN`, `NOT IN`

### 2.3. Ekleme/Güncelleme - Smart Foreign Key Resolution
```json
// Otomatik foreign key çözümleme
"_key_sis_vergidairesi": {"kod": "ÇANKAYA VERGİ DAİRESİ"}
// Çoklu filtreleme
"_key_sis_ozelkod2": {"turkodu": "M2", "kod": "WS003"}
```

## 3. Modül Yapısı ve Servis Kapsamı

### 3.1. Ana Modüller
| Modül | Açıklama | Ana Servisler |
|-------|----------|---------------|
| **SCF** | Stok-Cari-Fatura | Cari kartlar, stok yönetimi, fatura operasyonları |
| **MUH** | Muhasebe | Genel muhasebe, mali tablolar |
| **PER** | Personel | HR yönetimi, bordro |
| **GTS** | Görev Takip | CRM, task management |
| **BCS** | Banka-Çek-Senet | Finansal araçlar |
| **SIS** | Sistem | Kod tanımları, yetkilendirme |

### 3.2. SCF Modülü Alt Bileşenleri
- **Cari Yönetimi**: Müşteri/tedarikçi kartları, adres yönetimi
- **Stok-Hizmet**: Ürün kartları, fiyat yönetimi, stok hareketleri  
- **TSIF**: Teklif-Sipariş-İrsaliye-Fatura döngüsü
- **Kasa**: Nakit akış yönetimi
- **DYS**: Depo Yönetim Sistemi

## 4. Firma ve Dönem Yönetimi

### 4.1. Firma/Dönem Bilgilerinin Alınması
```json
{
  "sis_yetkili_firma_donem_sube_depo": {
    "session_id": "SESSION_ID"
  }
}
```

**Response yapısı**:
- `firmakodu`: Numeric firma kodu (servis çağrılarında kullanılacak)
- `donemler[]`: Aktif dönemler listesi
- `subeler[]`: Şube bilgileri
- `ontanimli__*`: Kullanıcıya öntanımlı değerler

## 5. Hata Yönetimi ve HTTP Durum Kodları

| Code | Type | Açıklama |
|------|------|----------|
| 200 | SUCCESS | İşlem başarılı |
| 400 | INVALID | Parametre hatası |
| 401 | UNAUTHORIZED | Yetki/login hatası |
| 402 | LICENSE_ERROR | Lisans sorunu |
| 406 | CREDIT_ERROR | Kontör yetersiz |
| 419 | LOGIN_TIMEOUT | Session timeout |
| 500 | FAILURE | Geçersiz işlem |
| 501 | ERROR | Sunucu hatası |

## 6. Kontör Sistemi ve Maliyet Yönetimi

- **Kontör Maliyeti**: Her servis çağrısı 0.0125 kontör
- **İstisna Servisler**: login, logout (kontör düşmez)
- **Takip**: `sis_kontor_sorgula` servisi ile kalan kontör sorgulanabilir
- **Yönetim**: Masaüstü `Kontör Hareketleri (msj1900)` ekranından

## 7. Entegrasyon için Öneriler

### 7.1. Projeye Uygun Mimari Yaklaşım
ERP platform projesinin **hybrid Python-C++ yaklaşımı** ile DIA entegrasyonu için:

```python
# Connector sınıfı örneği
class DIAConnector(BaseConnector):
    def __init__(self, server_code: str, api_key: str):
        self.base_url = f"https://{server_code}.ws.dia.com.tr/api/v3"
        self.api_key = api_key
        self.session_id = None
        
    async def authenticate(self, username: str, password: str) -> bool:
        login_data = {
            "login": {
                "username": username,
                "password": password,
                "disconnect_same_user": "True", 
                "params": {"apikey": self.api_key}
            }
        }
        # Implementation...
```

### 7.2. Connection Pool Yönetimi
- Session yönetimi için connection pooling
- 1 saatlik timeout göz önünde bulundurulmalı
- Otomatik yeniden bağlanma mekanizması

### 7.3. Performans Optimizasyonu
- Batch operasyonlar için limit/offset kullanımı
- `selectedcolumns` ile sadece gerekli alanları çekme
- Polars DataFrame entegrasyonu için efficient data mapping

## 8. Test ve Geliştirme Araçları

### 8.1. DIA Web Service Tester
**İndirme Linkleri**:
- Windows: `https://dia-dl.s3.amazonaws.com/win/dia_ws_tester_32bit/DiaWSTester-installer.exe`
- Linux: `https://dia-dl.s3.amazonaws.com/linux/dia_ws_tester/diawstester_1.3.0-2021101407_amd64.deb`  
- macOS: `https://dia-dl.s3.amazonaws.com/mac/dia_ws_tester/DiaWSTester.dmg`

**Özellikler**:
- Canlı servis test ortamı
- Otomatik Python/C#/PHP kod üretimi
- JSON request/response inspector

## 9. API Key ve Lisanslama

### 9.1. API Key Başvuru Süreci
- **İletişim**: satis@dia.com.tr
- **Gerekli Bilgiler**: Uygulama detayları, kullanım amacı
- **Süreç**: Ticari değerlendirme sonrası key tahsisi

### 9.2. Demo Sunucu
Test ve geliştirme için demo sunucu erişimi mevcut.

## 10. Entegrasyon Implementasyon Roadmap

### 10.1. Faz 1: Temel Bağlantı (1-2 hafta)
1. DIAConnector sınıfı implementasyonu
2. Session yönetimi ve authentication
3. Temel CRUD operasyonları (SCF modülü)
4. Connection pooling

### 10.2. Faz 2: Gelişmiş Özellikler (2-3 hafta)  
1. Gelişmiş filtreleme ve sorgulama
2. Batch processing optimizasyonları
3. Error handling ve retry logic
4. Logging ve monitoring entegrasyonu

### 10.3. Faz 3: Üretim Hazırlığı (1-2 hafta)
1. Performance testing ve optimization
2. Security audit ve API key management
3. Documentation ve deployment guides

## 11. Kritik Dikkat Edilmesi Gerekenler

1. **TLS Versiyonu**: Mutlaka TLS 1.2+ kullanımı
2. **Session Timeout**: 1 saatlik timeout planlanması
3. **Yetki Kontrolü**: Masaüstü yetkileri ile senkronizasyon
4. **Kontör Yönetimi**: Maliyetli servis çağrıları için optimizasyon
5. **Foreign Key Resolution**: Smart key resolution kullanımı

## Sonuç

DIA Web Servis API, kapsamlı ERP entegrasyonu için güçlü bir altyapı sunmaktadır. Projenin mevcut **hybrid Python-C++ mimarisi** ile mükemmel uyum sağlayacak, özellikle **FastAPI** ve **Polars** entegrasyonu ile yüksek performanslı data processing imkanı sunacaktır.

**Tavsiye Edilen Yaklaşım**: İlk etapta Python ile rapid prototyping, sonrasında kritik performans bölümlerinde C++ optimizasyonu stratejisi, DIA API'sının sunduğu esneklik ile mükemmel uyum içinde çalışacaktır.