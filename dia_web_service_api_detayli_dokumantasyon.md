# DİA Web Servis API - Detaylı Dokümantasyon

Bu dokümantasyon, DİA Web Servis API'nin ana sayfasından (https://doc.dia.com.tr/doku.php?id=gelistirici:wsapi:anasayfa) taranan tüm bağlantıların detaylı içeriklerini kapsamaktadır.

## 📋 İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Test Aracı (DİA Web Service Tester)](#2-test-aracı)
3. [Session (Oturum) & API Key](#3-session-oturum--api-key)
4. [Yetkili Firma, Dönem Bilgilerinin Alınması](#4-yetkili-firma-dönem-bilgilerinin-alınması)
5. [Servis Türleri](#5-servis-türleri)
6. [Hata Takibi](#6-hata-takibi)
7. [Rapor Alınması](#7-rapor-alınması)
8. [Servis İndex](#8-servis-i̇ndex)
9. [Eğitim Videoları](#9-eğitim-videoları)
10. [Örnekler](#10-örnekler)

---

## 1. Genel Bakış

### Tanım
Yazılım geliştiricilerin API sayesinde entegrasyonlar gerçekleştirebilmeleri amaçlanmaktadır. **JSON REST Web Service** çağrıları ile:
- Veri okuma
- Veri ekleme, değiştirme, silme işlemleri
- Rapor çağırıp sonucunu çeşitli formatlarda alabilme

### ⚠️ Önemli Güvenlik Uyarısı
**30 Ekim 2022 tarihi itibariyle, DİA Web Servislerini kullanmak için güvenli iletişim protokolü olarak TLS 1.2 ve üzeri sürümlerin kullanımı zorunlu hale gelecektir.**

### 1.1. Nereden Başlamalıyız?

1. **Test Aracı Kurulumu**
   - [DİA WS v3 Test Aracı [Windows]](https://dia-dl.s3.amazonaws.com/win/dia_ws_tester_32bit/DiaWSTester-installer.exe)
   - [DİA WS v3 Test Aracı [Linux/Ubuntu]](https://dia-dl.s3.amazonaws.com/linux/dia_ws_tester/diawstester_1.3.0-2021101407_amd64.deb)
   - [DİA WS v3 Test Aracı [Mac OS X]](https://dia-dl.s3.amazonaws.com/mac/dia_ws_tester/DiaWSTester.dmg)

2. **Öğrenilmesi Gerekenler**
   - Kontör düşme mantığı ve takibi
   - Login işlemi ve session_id alma
   - Firma, dönem mantığı

### 1.2. Kontör Takibi

- Her web servis çağrısı için **0.0125 kontör** düşmektedir
- Bazı özel servislerden kontör düşülmez (login, logout gibi)
- Kontör takip: Masaüstü istemciden **Kontör Hareketleri (msj1900)** ekranı
- Kalan kontör sorgulama: `sis_kontor_sorgula` servisi

### 1.3. Güvenlik

- **Oturum (session) açılması zorunlu**
- DİA sisteminde tanımlı kullanıcı bilgileriyle oturum oluşturma
- Yetkilendirme: Kullanıcı masaüstünde yapabildiği işlemleri web servisle yapabilir
- **"İzin Verilen IP'ler"** tanımlaması mümkün
- **SSL ile şifreli haberleşme**

### 1.4. Servis İsimlendirmesi

**Model tabanlı isimlendirme:**
- Model: `scf_carikart`
- Servisler: 
  - `scf_carikart_ekle`
  - `scf_carikart_getir`
  - `scf_carikart_guncelle`
  - `scf_carikart_listele`
  - `scf_carikart_sil`

### 1.5. Input/Response Genel Özellikleri

**Tüm servislerde zorunlu parametreler:**
- `session_id`
- `firma_kodu`
- `donem_kodu`

**Ek gereksinimler:**
- **Ekleme/Güncelleme:** `kart` bilgisi zorunlu
- **Getirme/Silme:** `key` bilgisi zorunlu

---

## 2. Test Aracı (DİA Web Service Tester)

### Tanım
Kod yazmadan servislerin hızlı test edilmesini sağlayan araçtır.

### 2.1. Ekran Kullanımı

1. **Kaynak WS Girişi:**
   ```
   https://SUNUCUKODU.ws.dia.com.tr/api/v3/
   ```

2. **Login İşlemi:**
   - Kullanıcı adı ve şifre girme
   - [F5] Login butonu

3. **Firma/Dönem:**
   - Bilinen değerleri girme
   - [F7] Yetkili Firma Dönemler ile öğrenme

4. **Servis Çalıştırma:**
   - Sol taraftan servis seçimi
   - İnput kısmında değişiklik
   - [F2] Çalıştır

### Kısayol Tuşları
- **[F8] Parametre Kaydet:** Üst kısım bilgilerini kaydet
- **[F9] Jsonları Güncelle:** Öntanımlı json dosyalarını güncelle
- **[F4] İnput Kaydet:** İnput değişikliklerini kaydet
- **Örnek Kodlar:** Python, C#, PHP kod örnekleri

---

## 3. Session (Oturum) & API Key

### Session Timeout
- **Timeout süresi:** 1 saat
- Her çağrı timeout süresini sıfırlar

### 3.1. API Key

**Tanım:** DİA tarafından verilen tekil anahtar değeri

**Nasıl Alınır:**
- `satis@dia.com.tr` adresine mail
- Kullanım amacı ve uygulama detayları belirtilmeli
- Sadece login servisinde kullanılır

### 3.2. Login

**Parametreler:**
- `username`: DİA'da tanımlı kullanıcı adı
- `password`: DİA'da tanımlı şifre
- `disconnect_same_user`: Kullanıcı bağlıysa koparılsın mı? ("True"/"False")

**Örnek İnput:**
```json
{
  "login": {
    "username": "ws",
    "password": "ws",
    "disconnect_same_user": "True",
    "params": {"apikey": "xxx"}
  }
}
```

**Başarılı Response:**
```json
{'code': '200', 'msg': 'b2d4820cc43f4d98a8c6698686b6d386'}
```

**Başarısız Response:**
```json
{'code': '401', 'msg': 'NOUSER'}
```

### 3.3. Logout

**Örnek İnput:**
```json
{
  "logout": {
    "session_id": "b2d4820cc43f4d98a8c6698686b6d386"
  }
}
```

---

## 4. Yetkili Firma, Dönem Bilgilerinin Alınması

### Servis Yoluyla Alma

**Servis:** `sis_yetkili_firma_donem_sube_depo`

**Dönen Bilgiler:**
- `firmakodu`: Servislerde kullanılacak gerçek kod
- `firmaadi`: Firma adı
- `donemler`: Dönem listesi
  - `donemkodu`: Servislerde kullanılacak değer
- `subeler`: Şube listesi
- `ontanimli__`: Öntanımlı değerler

**Örnek Çağrı:**
```json
{
  "sis_yetkili_firma_donem_sube_depo": {
    "session_id": "b2d4820cc43f4d98a8c6698686b6d386"
  }
}
```

---

## 5. Servis Türleri

### 5.1. Listeleme (_listele) Servisleri

**Parametreler:**
- `session_id`, `firma_kodu`, `donem_kodu`
- `filters`: Filtre uygulama
- `sorts`: Sıralama
- `params`: Ekstra parametreler
- `limit`: Kayıt sayısı limiti
- `offset`: Sayfalama için başlangıç

#### 5.1.1. Filtreleme (filters)

**Operatörler:** "<", ">", "<=", ">=", "!", "=", "IN", "NOT IN"

**Örnekler:**
```json
// Cari kart tipi "AL" olanlar
"filters": [{"field": "carikarttipi", "operator": "=", "value": "AL"}]

// Kodu "001" veya "002" olanlar
"filters": [{"field": "carikartkodu", "operator": "IN", "value": "001,002"}]

// Tarih aralığı
"filters": [
  {"field": "_date", "operator": ">=", "value": "2016-07-01"},
  {"field": "_date", "operator": "<", "value": "2016-08-01"}
]
```

#### 5.1.2. Sıralama (sorts)

```json
"sorts": [{"field": "carikartkodu", "sorttype": "DESC"}]
```

#### 5.1.3. Sadece İstenen Kolonları Getirme

```json
"params": {"selectedcolumns": ["stokkartkodu", "aciklama"]}
```

### 5.2. Getirme (_getir) Servisleri

**Özellikler:**
- Tek kayda ait detaylı bilgi
- Alt modellerin bilgileri dahil
- Bağlantılı alanların detayları otomatik

**Parametreler:**
- `session_id`, `firma_kodu`, `donem_kodu`
- `key`: İstenen kayda ait _key bilgisi

### 5.3. Ekleme (_ekle) Servisleri

**Parametreler:**
- `session_id`, `firma_kodu`, `donem_kodu`
- `kart`: Eklenecek veri bilgisi

#### 5.3.1. Önemli Notlar
- Tüm alanları göndermek zorunlu değil
- Default değerler otomatik yazılır
- Bazı alanlar zorunlu (örn: `carikartkodu`)

#### 5.3.2. Bağlantılı (_key ile başlayan) Alanlar

**Numeric değer gönderme:**
```json
"_key_sis_vergidairesi": 123
```

**Otomatik bulma:**
```json
"_key_sis_vergidairesi": {"kod": "ÇANKAYA VERGİ DAİRESİ"}
```

#### 5.3.3. Combo (Seçimli) Alanlar

Model dokümantasyonundan kısa kodlar kullanılmalı:
```json
"stokkartturu": "TCR"  // 'Ticari Mal' için
```

### 5.4. Güncelleme (_guncelle) Servisleri

**Ekleme servisinden farklar:**
- `kart` içinde `_key` bilgisi zorunlu
- Alt modellerde _key varsa güncelleme, yoksa yeni kayıt

**Silme:**
```json
"m_silinecek_kalemler": ["key1", "key2"]
```

### 5.5. Silme (_sil) Servisleri

**Parametreler:**
- `session_id`, `firma_kodu`, `donem_kodu`
- `key`: Silinecek kayda ait key bilgisi

---

## 6. Hata Takibi

### HTTP Status Kodları

| Code | Type | Açıklama |
|------|------|----------|
| 200 | SUCCESS | İşlem Başarılı |
| 400 | INVALID | İşlem parametrelerinde hata |
| 401 | UNAUTHORIZED | Yetki sorunu veya kullanıcı adı/şifre hatalı |
| 402 | UNAUTHORIZED_LICENSE_ERROR | Lisans sorunu |
| 405 | LICENSE_ERROR | Lisans hatası |
| 406 | CREDIT_ERROR | Yeterli kontör bulunamadı |
| 419 | LOGIN_TIMEOUT | Session timeout |
| 500 | FAILURE | Geçersiz işlem yada parametre |
| 501 | ERROR | Sunucuda öngörülmeyen hata |

---

## 7. Rapor Alınması

### Ana Servis
**`rpr_raporsonuc_getir`** servisi ile rapor sonuçları alınır.

### Parametreler
- `session_id`, `firma_kodu`, `donem_kodu`
- `report_code`: Rapor kodu (scf1110a, scf2201c, ...)
- `tasarim_key`: Tasarım anahtarı
- `param`: Rapor parametreleri
- `format_type`: Çıktı formatı (dia, html, excel, pdf, json)

### Tasarım Bilgisi Alma
**`rpr_tasarimlar_listele`** servisi ile tasarımlar listelenir.

### Rapor Parametreleri
**`rpr_dinamik_raporparametreleri_getir`** servisi ile rapor parametreleri öğrenilir.

**Parametre Yapısı:**
```json
{
  "_key": "178717",
  "tarihbaslangic": "2016-01-01",
  "tarihbitis": "2016-12-31",
  "filtreler": [...],
  "siralama": [...],
  "gruplama": [...]
}
```

---

## 8. Servis İndex

### Ana Modüller

- **BCS (Banka Çek-Senet)**: Banka, çek, senet işlemleri
- **DAG (Dağıtım)**: Dağıtım yönetimi
- **DMR (Demirbaş)**: Demirbaş takip
- **GTS (Görev Takip)**: Görev ve takip sistemi
- **ITH (İthalat-İhracat)**: Dış ticaret işlemleri
- **KRG (Kargo Takip)**: Kargo takip sistemi
- **MIY (Müşteri İlişkileri Yönetimi)**: CRM işlemleri
- **MUH (Muhasebe)**: Muhasebe işlemleri
- **OTE (Otel Yönetimi)**: Otel operasyon sistemi
- **PER (Personel)**: İnsan kaynakları
- **PRJ (Proje)**: Proje yönetimi
- **RPR (Rapor)**: Raporlama sistemi
- **RST (Restoran)**: Restoran yönetimi
- **SCF (Stok-Cari-Fatura)**: Temel ticari işlemler
  - SCF - Cari: Cari kart işlemleri
  - SCF - Stok-Hizmet: Stok ve hizmet yönetimi
  - SCF - Teklif-Sipariş-İrsaliye-Fatura: Satış süreçleri
  - SCF - Kasa: Kasa işlemleri
- **SHY (Servis Hizmet Yönetimi)**: Servis takip
- **SIS (Sistem)**: Sistem ayarları
- **URE (Üretim)**: Üretim planlama

---

## 9. Eğitim Videoları

### Video Konuları
- DİA Web Service Tester aracı nedir ve nasıl kullanılır?
- Web service ile sisteme nasıl giriş yapılır?
- Firma ve dönem bilgilerine nasıl ulaşılır?
- Lisans ve kontör işleyişi nasıldır?
- İsimlendirme standardı nasıldır?
- Listeleme servisleri nasıl çalışır?
- Getir servislerinin işleyişi nasıldır?
- Ekle servislerinin çalışma mantığı nasıldır?
- Güncelle servisleri nasıl çalışır?
- Sil servisleri nasıl çalışır?
- Web service ile raporlar nasıl alınır?

---

## 10. Örnekler

### Pratik Örnekler
1. **Örnek 1**: Belirli Bir Grup Cariye Toplu Dekont
2. **Örnek 2**: Borcu 10000 TL Üzerindeki Carilere E-Posta İle Toplu Ekstre Gönder
3. **Örnek 3**: Stok Kartına Resim Ekleme
4. **Örnek 4**: Stok Kartına Barkod Ekleme (Dinamik, EAN13)
5. **Örnek 5**: Bugün Alınan Tüm Siparişlerin Sabit Mail Adresine Gönderilmesi
6. **Örnek 6**: Sevk Edilen Siparişlere Göre Carilere Mail Gönderilmesi
7. **Örnek 7**: Otelde Konaklayan Misafirlerin CSV Dosyasına Kaydedilmesi
8. **Örnek 8**: Anket Fişi Oluşturulması
9. **Örnek 9**: Excelden Veri Alıp Cari Hesap Fişi Oluşturma
10. **Örnek 10**: Stok Kart Barkod Okutma
11. **Örnek 11**: Servis Formu Oluşturup PDF Mail Gönderilmesi
12. **Örnek 12**: Stok Karta Resim Eklenmesi
13. **Örnek 13**: E-Arşiv Fatura Örneği
14. **Örnek 14**: Vade Bakiye Raporunun Carilere Mail ile Gönderilmesi
15. **Örnek 15**: Stok Fiyat Güncelleme
16. **Örnek 16**: Restoran Siparişlerine Göre Üretim Fişi Eklenmesi
17. **Örnek 17**: Teklife Bağlı Görev Ekleme

### Örnek Projeler
- **Örnek C# Projesi**: Tam kapsamlı uygulama örneği
- **Örnek Stok Listeleme Scripti**: Basit başlangıç scripti

---

## 🔧 Diğer Önemli Sayfalar

- **diadestek kullanıcısı nasıl açılır?**: Teknik destek kullanıcısı oluşturma
- **Sık Sorulan Sorular**: Yaygın sorunlar ve çözümleri

---

## 📞 İletişim ve Destek

- **API Key Talebi**: satis@dia.com.tr
- **Teknik Destek**: DİA Yazılım destek kanalları

---

## ⚠️ Önemli Hatırlatmalar

1. **TLS 1.2+ zorunluluğu** (30 Ekim 2022 sonrası)
2. **Kontör takibi** gereksinimi
3. **Session timeout** (1 saat)
4. **Yetkilendirme** kontrolü
5. **SSL şifreli haberleşme**

---

*Bu dokümantasyon, DİA Web Servis API'nin resmi dokümantasyonundan FireCrawler MCP kullanılarak 21 Ağustos 2025 tarihinde taranmıştır.*