# Güvenlik Politikası

## Desteklenen sürüm

Proje aktif geliştirme aşamasındadır. Güvenlik düzeltmeleri yalnızca `main`
dalındaki en güncel sürüme uygulanır.

## Güvenlik açığı bildirme

Bir güvenlik açığı bulursanız ayrıntıları herkese açık bir issue içinde
paylaşmayın. Depoda GitHub Private Vulnerability Reporting etkinse **Security →
Report a vulnerability** yolunu kullanın; etkin değilse depo sahibiyle özel bir
kanaldan iletişime geçin.

Bildirimde mümkünse şunları ekleyin:

- Etkilenen commit veya sürüm
- Tekrarlanabilir adımlar ve kavram kanıtı
- Olası etki ve saldırı ön koşulları
- Varsa önerilen düzeltme veya geçici önlem

API anahtarı, yüz fotoğrafı, gerçek kullanıcı profili ya da başka kişisel
verileri rapora eklemeyin. Örneklerde yalnızca sentetik veri kullanın.

## Güvenlik kapsamı

Özellikle şu konulardaki bildirimler değerlidir:

- Kimlik doğrulama atlatma veya profil verisine yetkisiz erişim
- Dosya yolu geçişi, kötü amaçlı görsel işleme veya kaynak tüketimi
- API anahtarı, fotoğraf, günlük ya da rapor sızıntısı
- VLM sağlayıcısına gönderilen veride kapsam aşımı
- Bağımlılık ve tedarik zinciri riskleri

## Dağıtım sorumluluğu

Uygulamanın yerleşik erişim anahtarı tek kiracılı kullanım içindir. Birbirinden
bağımsız kullanıcı hesapları bulunan internet dağıtımlarında kimlik sağlayıcı,
TLS sonlandırma, merkezi hız sınırı, yedekleme ve izleme sunan bir reverse proxy
veya platform katmanı kullanılmalıdır. Ayrıntılı kontrol listesi README içindeki
“Canlı ortama güvenli dağıtım” bölümündedir.
