# SkinCare Vision AI

Fotoğraftan bakım odaklı cilt görünümü analizi yapan, kişiselleştirilmiş rutin oluşturan ve değişimi zaman içinde takip etmeye yardımcı olan açık kaynaklı web uygulaması.

**Teknolojiler:** FastAPI · React 19 · TypeScript · Tailwind CSS v4 · YOLO · MediaPipe · OpenCV · Gemini / Groq / Hugging Face

> [!IMPORTANT]
> SkinCare Vision AI bir tıbbi cihaz değildir. Yalnızca kozmetik ve görsel bir ön değerlendirme sunar; hastalık teşhis etmez, reçeteli tedavi önermez ve dermatoloğun yerini tutmaz.

<p align="center">
  <img src="screenshots/cilt-analizi.png" alt="SkinCare Vision AI analiz sonucu" width="100%">
</p>

## İçindekiler

- [Öne çıkan özellikler](#öne-çıkan-özellikler)
- [Ekran görüntüleri](#ekran-görüntüleri)
- [Mimari](#mimari)
- [Hızlı başlangıç](#hızlı-başlangıç)
- [Yapılandırma](#yapılandırma)
- [Güvenlik ve gizlilik](#güvenlik-ve-gizlilik)
- [Canlı ortama güvenli dağıtım](#canlı-ortama-güvenli-dağıtım)
- [Test ve kalite](#test-ve-kalite)
- [Docker](#docker)
- [Proje yapısı](#proje-yapısı)
- [Model sınırları](#model-sınırları)
- [Lisans](#lisans)

## Öne çıkan özellikler

### Cilt görünümü analizi

- Önden, soldan ve sağdan olmak üzere 1–3 fotoğrafla çoklu görünüm analizi
- Mesafe, konum, baş açısı, ışık ve netlik için canlı yönlendirmeli kamera
- MediaPipe 478 noktalı yüz haritası; gerektiğinde OpenCV Haar yedeği
- Alın, burun, yanak ve çene bölgeleri; göz, kaş ve dudakların analiz dışı tutulması
- Özel `acne_like_spot` YOLO modeli, renk tabanlı adaylar ve isteğe bağlı Gemini ikinci görüşü
- Sklera tabanlı beyaz ayarı sonrasında 0–100 arası Cilt Skoru
- Nokta yoğunluğu, kızarıklık dengesi, ton eşitliği, doku ve parlama alt skorları

### Rutin ve ürün desteği

- Profil ve ölçümlere göre açıklanabilir sabah/akşam rutini
- Hamilelik/emzirme, yaş, hassasiyet ve alerji kontrolleri
- Birbiriyle çakışan aktifleri farklı akşamlara ayıran haftalık plan
- Metin veya etiket fotoğrafından INCI içerik kontrolü
- Ürün rafı, eksik rutin adımı, yinelenen aktif ve PAO süresi uyarıları
- Düzenlenebilir, doğrulanmış başlangıç ürün kataloğu

### Takip ve raporlama

- Cilt Skoru eğilimleri ve kayıt geçmişi
- Hizalanmış önce/sonra karşılaştırması
- Kızarıklık ve koyu iz değişim haritaları
- Günlük rutin uyumu, tetikleyiciler, belirtiler ve kişisel içgörüler
- PDF, JSON ve CSV dışa aktarma
- Profil geçmişini ve kayıtlı küçük görselleri silme

### Yardımcı araçlar

- Open-Meteo verisinden UV, sıcaklık ve nem odaklı cilt hava durumu
- Profil, rutin, ürün rafı ve günlük bağlamını kullanan cilt koçu
- Gemini, Groq ve Hugging Face için geri dönüş zinciri, devre kesici ve önbellek

## Ekran görüntüleri

### Profil oluşturma

Zorunlu bilgiler ve açık fotoğraf işleme onayı önce alınır; ikinci adımda bakım hedefleri ve kişiselleştirme ayrıntıları seçilir.

<table>
  <tr>
    <td width="50%"><img src="screenshots/profil1.png" alt="Profil oluşturma birinci adım"></td>
    <td width="50%"><img src="screenshots/profil2.png" alt="Profil oluşturma ikinci adım"></td>
  </tr>
</table>

### Ürünler ve cilt koçu

<table>
  <tr>
    <td width="50%"><img src="screenshots/urunler.png" alt="Ürün rafı ve ürün değerlendirmesi"></td>
    <td width="50%"><img src="screenshots/cilt-kocu.png" alt="Cilt koçu ve hava durumu"></td>
  </tr>
</table>

### Günlük takip

<table>
  <tr>
    <td width="50%"><img src="screenshots/gunluk-takip.png" alt="Günlük cilt takibi"></td>
    <td width="50%"><img src="screenshots/gunluk-takip-devam.png" alt="Takvim ve kişisel içgörüler"></td>
  </tr>
</table>

### Geçmiş ve karşılaştırma

<table>
  <tr>
    <td width="33%"><img src="screenshots/gecmis-ve-ayarlar.png" alt="Geçmiş ve yapay zekâ ayarları"></td>
    <td width="33%"><img src="screenshots/gecmis-devam.png" alt="Önce ve sonra karşılaştırması"></td>
    <td width="33%"><img src="screenshots/gecmis-son.png" alt="Kayıtlar ve veri yönetimi"></td>
  </tr>
</table>

## Mimari

```text
React + Vite
    │
    │ /api (JSON / multipart)
    ▼
FastAPI ── güvenlik, doğrulama, hız ve istek boyutu sınırları
    ├── analysis/         çoklu görünüm, bölgeler, metrikler, değişim haritası
    ├── detection/        YOLO, MediaPipe ve Haar
    ├── recommendation/   rutin, aktifler, INCI, katalog ve ürün rafı
    ├── history/          SQLite, günlük, karşılaştırma ve içgörüler
    ├── report/           PDF, metin ve JSON raporları
    ├── vlm_engine.py     sağlayıcı istemcileri
    └── vlm_router.py     geri dönüş, devre kesici ve önbellek
```

HTTP katmanı `src/api/server.py` içinde kalır; analiz ve iş kuralları alan modüllerinde yürütülür. Uzun ömürlü model ve servis örnekleri `src/api/container.py` tarafından yönetilir. Üretim derlemesinde FastAPI, `frontend/dist` içeriğini aynı origin üzerinden sunar.

Bir analiz isteğinin temel akışı şöyledir:

1. Kimlik doğrulama, hız sınırı ve toplam istek boyutu kontrol edilir.
2. Görsel formatı, bütünlüğü, dosya boyutu ve açılmış piksel sayısı doğrulanır.
3. Fotoğraf özel bir geçici dizinde normalize edilir; EXIF bilgisi taşınmaz.
4. Yüz, bölgeler ve bakım odaklı görsel metrikler hesaplanır.
5. Etkinse sınırlı veriyle VLM yorumu ve ikinci görüş alınır.
6. Geçici dosyalar silinir; kullanıcı açıkça seçerse yalnızca küçük önizleme geçmişe kaydedilir.

## Hızlı başlangıç

### Gereksinimler

- Python 3.10 veya üzeri; CI Python 3.12 kullanır
- Node.js 22 veya üzeri
- İsteğe bağlı AI yorumları için en az bir VLM sağlayıcı anahtarı

AI anahtarı olmadan klasik görüntü analizi, rutin motoru, günlük ve raporlama özellikleri çalışmaya devam eder.

### Windows / PowerShell kurulumu

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --extra-index-url https://download.pytorch.org/whl/cpu -c constraints.txt -r requirements.txt
pip install --no-deps mediapipe==1.1.1

Copy-Item .env.example .env

cd frontend
npm ci
npm run build
cd ..

.\.venv\Scripts\python -m uvicorn api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

Ardından `http://127.0.0.1:8000` adresini açın. Geliştirme modunda API belgeleri `http://127.0.0.1:8000/docs` adresindedir. Public modda saldırı yüzeyini küçültmek için Swagger, ReDoc ve OpenAPI uçları kapatılır.

`constraints.txt`, CI ve Docker'da doğrulanan doğrudan bağımlılık sürümlerini sabitler. MediaPipe `--no-deps` ile kurulur; gerekli çalışma zamanı bağımlılıkları `requirements.txt` içinde açıkça tutulur. Böylece MediaPipe'ın `opencv-contrib-python` paketi, YOLO için kullanılan OpenCV kurulumunu değiştirmez.

### Geliştirme modu

İki terminal kullanın:

```powershell
# Terminal 1
.\.venv\Scripts\python -m uvicorn api.server:app --app-dir src --port 8000 --reload

# Terminal 2
cd frontend
npm run dev
```

Vite geliştirme sunucusu `http://localhost:5173` üzerinden çalışır ve `/api` isteklerini 8000 portuna yönlendirir.

## Yapılandırma

`.env.example` dosyasını `.env` adıyla kopyalayın. `.env` Git tarafından yok sayılır; gerçek anahtarları hiçbir zaman commit etmeyin.

| Değişken | Varsayılan | Açıklama |
|---|---:|---|
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN` | boş | Kullanılacak sağlayıcı anahtarları |
| `VLM_PROVIDER` | `Gemini` | Arayüzde varsayılan sağlayıcı |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Birincil Gemini modeli |
| `GEMINI_FALLBACK_MODELS` | örnek dosyada | Kota/sunucu hatasında sırayla denenen modeller |
| `GROQ_MODEL`, `HF_VLM_MODEL`, `HF_PROVIDER` | örnek dosyada | Alternatif sağlayıcı ayarları |
| `VLM_FALLBACK` | `true` | Anahtarı bulunan diğer sağlayıcılara geçiş |
| `VLM_SECOND_OPINION` | `true` | Tek fotoğrafta isteğe bağlı Gemini nokta kontrolü |
| `VLM_TIMEOUT_SECONDS` | `90` | Sağlayıcı istek zaman aşımı |
| `VLM_MAX_RETRIES` | `2` | Geçici sağlayıcı hatalarında tekrar sayısı |
| `VLM_TRUST_ENV_PROXY` | `false` | Sistem proxy değişkenlerini kullanma izni |
| `YOLO_MODEL_PATH` | `models/acne_like_spot.pt` | YOLO ağırlık dosyası |
| `YOLO_CONFIDENCE` | `0.10` | YOLO güven eşiği |
| `FACE_LANDMARKER_PATH` | `models/face_landmarker.task` | MediaPipe model dosyası |
| `HISTORY_ENABLED` | `true` | Profil, geçmiş, günlük ve raf depolama |
| `HISTORY_DB_PATH` | `data/history.db` | Yerel SQLite dosyası |
| `PRODUCT_CATALOG_PATH` | `data/products.json` | Düzenlenebilir ürün kataloğu |
| `MAX_UPLOAD_MB` | `10` | Tek görselin sıkıştırılmış boyut sınırı |
| `MAX_IMAGE_PIXELS` | `40000000` | Açılmış görsel piksel sınırı |
| `MAX_REQUEST_BODY_MB` | `32` | JSON/multipart toplam istek sınırı |
| `ANALYSIS_RATE_LIMIT` | `12` | IP başına saatlik analiz sınırı |
| `LABEL_RATE_LIMIT` | `30` | Etiket okuma ve koç istek sınırı |
| `CAPTURE_RATE_LIMIT` | `600` | Kamera kalite kontrolü saatlik sınırı |
| `ALLOW_USER_API_KEYS` | `true` | Sekmeye özel sağlayıcı anahtarı girişine izin |
| `PUBLIC_DEPLOYMENT` | `false` | Canlı ortam güvenlik kontrollerini zorunlu kılar |
| `APP_ACCESS_TOKEN` | boş | Tek kiracılı uygulama erişim anahtarı |
| `CORS_ORIGINS` | `http://localhost:5173` | İzin verilen tarayıcı origin listesi |
| `ALLOWED_HOSTS` | yerel hostlar | Kabul edilen HTTP Host başlıkları |
| `LOG_LEVEL` | `INFO` | Uygulama günlük seviyesi |

## Güvenlik ve gizlilik

Uygulamada aşağıdaki savunmalar bulunur:

- Public modda en az 32 karakterli erişim anahtarı zorunludur.
- Token karşılaştırması sabit zamanlı yapılır; token yalnızca sekme belleğinde (`sessionStorage`) tutulur.
- Public mod, kullanıcı tarafından sağlayıcı anahtarı girilmesine izin vermez.
- CORS metotları ve başlıkları açık bir izin listesiyle sınırlandırılmıştır.
- `Host` başlığı izin listesiyle doğrulanır; public modda joker karakter reddedilir.
- İstek gövdesi sınırı hem `Content-Length` hem chunked aktarımlarda multipart ayrıştırmasından önce uygulanır.
- Görseller dosya boyutu, format, bütünlük ve piksel sayısı açısından doğrulanır.
- Kamera önizlemeleri ayrıca 2 milyon piksel ve 1,5 MB ile sınırlandırılır.
- Analiz, etiket okuma, koç ve kamera uçlarında IP tabanlı hız sınırı vardır.
- CSP, HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` ve `Permissions-Policy` başlıkları uygulanır.
- Public sağlık ucu yalnızca hazır olma bilgisini döndürür; sağlayıcı ve model ayrıntıları erişim korumalı `/api/status` ucundadır.
- Profil, analiz ve geçmiş cevapları `no-store` olarak işaretlenir.
- CSV dışa aktarmada elektronik tablo formülü enjeksiyonu engellenir.
- VLM devre kesicisi sağlayıcı ve kimlik bilgisi kapsamında tutulur; bir kullanıcının hatalı anahtarı diğer anahtarları devre dışı bırakmaz.
- Beklenmeyen sunucu hatalarının teknik ayrıntıları istemciye gönderilmez.

Fotoğraflar özel bir geçici dizinde işlenir ve analiz sonrasında silinir. Kullanıcı onay verirse geçmiş için en fazla 320 piksel genişliğinde yüz önizlemesi SQLite içinde saklanabilir. Kamera kontrol kareleri kaydedilmez.

Sunucu anahtarları tarayıcıya gönderilmez. VLM sağlayıcısına yalnızca yüz kırpımı, analiz bağlamı, hitap adı ve hitap biçimi gider; soyadı, cinsiyet ve hamilelik/emzirme yanıtı gönderilmez. Koç bağlamında ham alerji seçenekleri yerine yalnızca nötr bir “önerilmeyecek içerikler” listesi kullanılır. Sağlayıcı kullanımı yine de üçüncü taraf veri işleme anlamına gelir; canlı dağıtımda ilgili sağlayıcının gizlilik ve saklama koşullarını ayrıca değerlendirin.

Tehdit bildirim süreci için [SECURITY.md](SECURITY.md) dosyasına bakın.

## Canlı ortama güvenli dağıtım

Bu proje varsayılan olarak yerel ve tek kiracılı kullanıma uygundur. İnternete veya yerel ağa açmadan önce:

1. En az 32 rastgele karakterli bir token üretin:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. `.env` içinde aşağıdaki ayarları yapın:

   ```dotenv
   PUBLIC_DEPLOYMENT=true
   ALLOW_USER_API_KEYS=false
   APP_ACCESS_TOKEN=üretilen-gizli-token
   ALLOWED_HOSTS=cilt.example.com
   CORS_ORIGINS=https://cilt.example.com
   ```

3. Uygulamayı TLS/HTTPS sağlayan güvenilir bir reverse proxy arkasında çalıştırın.
4. Reverse proxy üzerinde bağlantı, toplam gövde boyutu ve merkezi hız sınırı tanımlayın; yalnızca gereken portları açın.
5. `.env`, `data/history.db`, yüklenen fotoğraflar ve yedekleri Git'e veya genel artifact depolarına göndermeyin.
6. SQLite dosyası için şifreli, erişim kontrollü yedekleme ve saklama politikası belirleyin.
7. Sağlayıcı anahtarlarını düzenli döndürün ve minimum kota/yetkiyle kullanın.
8. CI güvenlik kontrollerini ve Dependabot uyarılarını kapatmayın.

`APP_ACCESS_TOKEN` tek kiracılı erişim korumasıdır; kullanıcı hesabı sistemi değildir. Birbirinden bağımsız son kullanıcıların bulunduğu dağıtımlarda OIDC veya benzeri bir kimlik sağlayıcı, kullanıcı bazlı yetkilendirme, kalıcı merkezi hız sınırı ve denetim kaydı eklenmelidir. Bu mimari kurulmadan uygulamayı çok kiracılı servis olarak yayınlamayın.

## Analiz yönteminin özeti

Beş alt skor, normalize edilmiş yüz kırpımı üzerinde klasik görüntü işleme ve gerektiğinde tespit modelinin çıktılarıyla hesaplanır:

| Alt skor | Ölçüm yaklaşımı | Ağırlık |
|---|---|---:|
| Nokta yoğunluğu | YOLO, renk adayları ve isteğe bağlı ikinci görüş | %35 |
| Kızarıklık dengesi | CIELAB a* dağılımı ve bölgesel fark | %25 |
| Ton eşitliği | Aydınlatma etkisi azaltılmış parlaklık değişimi | %15 |
| Doku düzgünlüğü | İnce ölçekli parlaklık enerjisi | %15 |
| Parlama kontrolü | Speküler parlama alanı | %10 |

Kalibrasyon eşikleri `src/analysis/skin_metrics.py` içindeki `CALIBRATION` tablosundadır. Sonuçlar ışık, kamera, açı ve görüntü kalitesinden etkilenir; klinik ölçüm olarak yorumlanmamalıdır.

## Test ve kalite

### Backend

```powershell
pip install -c constraints.txt -r requirements-dev.txt
ruff check .
python -m bandit -r src -q
pytest
```

### Frontend

```powershell
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Pytest sırasında gerçek ağ erişimi engellenir; sağlayıcı çağrıları mock edilir. Playwright testleri gerçek Chromium üzerinde ana akışı, erişim anahtarı girişini ve kurtarılabilir profil hatasını sınar.

GitHub Actions her push ve pull request için şunları çalıştırır:

- Python lint, Bandit güvenlik taraması ve test paketi
- Çalışma zamanı import smoke testi
- `pip-audit` ile bilinen Python bağımlılık açıkları
- Frontend lint, tip kontrolü, birim testi ve üretim derlemesi
- `npm audit` ve Playwright uçtan uca testleri
- Docker imajının gerçek BuildKit ortamında oluşturulması

Dependabot; Python, npm ve GitHub Actions bağımlılıklarını düzenli kontrol eder.

## Docker

### Yerel kullanım

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Uygulama yalnızca `http://127.0.0.1:8000` üzerinde yayınlanır. Logları ve
healthcheck durumunu görmek için:

```powershell
docker compose logs -f app
docker compose ps
```

Container'ı durdurmak için `docker compose down` kullanın. Bu komut geçmişi
silmez; SQLite verisi `skincare-vision-ai-state` adlı volume içinde kalır.
Veriyi de bilinçli olarak silmek isterseniz önce doğru Compose projesinde
olduğunuzu doğrulayın, ardından `docker compose down --volumes` çalıştırın.

### Canlı ortam

```powershell
Copy-Item .env.production.example .env.production
# .env.production içindeki token, alan adı ve sağlayıcı anahtarlarını doldurun.

$env:ENV_FILE = ".env.production"
docker compose --env-file .env.production `
  -f compose.yaml `
  -f compose.production.yaml `
  up --build -d
```

Canlı Compose katmanı `PUBLIC_DEPLOYMENT=true` ve
`ALLOW_USER_API_KEYS=false` değerlerini zorunlu kılar; erişim tokeni, izinli
host ve CORS origin'i boşsa Compose başlamaz. Port yine yalnızca loopback'e
bağlanır; HTTPS sağlayan host tabanlı reverse proxy bu porta yönlendirilmelidir.

Docker güvenlik özellikleri:

- Çok aşamalı Node/Python build; final imajda kaynak geliştirme araçları yoktur.
- Uygulama sabit `10001:10001` kimlikli root olmayan kullanıcıyla çalışır.
- Root dosya sistemi salt okunurdur; yalnızca `/tmp` ve `/app/state` yazılabilir.
- Tüm Linux capability'leri düşürülür ve `no-new-privileges` uygulanır.
- SQLite verisi ürün kataloğundan ayrılmış `/app/state` volume'ünde saklanır.
- PID ve log dosyası büyüklüğü sınırlandırılır; kapanış sinyalleri `tini` ile
  düzgün iletilir.
- `/api/health` modeli ve veritabanını denetler; hazır değilse `503` döndürür.
- Tek worker kullanılır; bellek içi analiz önbelleği, devre kesici ve hız
  sınırlarının süreçler arasında ayrışması önlenir.

GitHub'da `v*` etiketi oluşturulduğunda veya Container workflow'u elle
çalıştırıldığında imaj GHCR'a gönderilir. Yayınlanan imaj SBOM ve provenance
bilgisi içerir. Normal push ve pull request'lerde CI imajı oluşturur ancak
registry'ye göndermez.

## Proje yapısı

```text
SkinCareVisionAI/
├── .github/
│   ├── workflows/             CI ve GHCR container yayını
│   └── dependabot.yml         otomatik bağımlılık güncellemeleri
├── assets/                    PDF fontları ve mağaza görselleri
├── data/
│   ├── products.json          doğrulanmış başlangıç kataloğu
│   └── products.example.json  katalog şema örneği
├── docs/                      veri kümesi ve model eğitim notları
├── frontend/
│   ├── e2e/                   Playwright senaryoları
│   └── src/
│       ├── components/        ortak arayüz bileşenleri
│       ├── icons/             özel ikon seti
│       ├── lib/               API, durum ve tipler
│       └── pages/             uygulama sayfaları
├── models/                    YOLO ve MediaPipe model dosyaları
├── licenses/                  üçüncü taraf lisans metinleri
├── scripts/                   örnek değerlendirme araçları
├── src/
│   ├── analysis/              analiz hattı ve metrikler
│   ├── api/                   FastAPI, şemalar, güvenlik ve servis kabı
│   ├── detection/             yüz ve bulgu tespiti
│   ├── history/               SQLite ve kişisel içgörüler
│   ├── recommendation/        rutin, INCI ve katalog
│   ├── report/                PDF, metin ve JSON raporları
│   ├── safety/                tıbbi iddia filtreleri
│   └── users/                 profil ve onboarding kuralları
├── tests/                     çevrimdışı pytest paketi
├── constraints.txt            doğrulanmış doğrudan sürümler
├── compose.yaml               güvenli yerel container çalıştırma
├── compose.production.yaml    canlı ortam zorunlulukları
├── Dockerfile
├── LICENSE
├── SECURITY.md
├── THIRD_PARTY_NOTICES.md
└── README.md
```

`inputs/`, `outputs/`, `samples/`, `frontend/dist`, test artifact'ları ve yerel SQLite dosyası `.gitignore` ile korunur. Model dosyaları bilinçli olarak depoda tutulur; kaynak, lisans ve SHA-256 bilgileri `THIRD_PARTY_NOTICES.md` içinde kayıtlıdır. YOLO eğitim veri kümesinin kaynağı ve yeniden dağıtım izni ise yayın öncesinde proje sahibi tarafından ayrıca belgelenmelidir.

## Ürün kataloğu

`data/products.json` altı ürünlük doğrulanmış bir başlangıç kataloğudur. Ürün adı, resmi sayfa, içerik listesi mevcutsa INCI ve doğrulama tarihi içerir. Katalog değişiklikleri yayınlanmadan önce üreticinin resmi sayfasından yeniden kontrol edilmelidir; formüller ve bağlantılar zaman içinde değişebilir.

## Model sınırları

YOLO dedektörü tek sınıflıdır: `acne_like_spot`. Mevcut ilk sürümün mAP50 değeri yaklaşık `0,37` olduğu için tek başına klinik veya kesin bir tespit aracı değildir. Renk analizi ve isteğe bağlı ikinci görüş bu nedenle tamamlayıcı olarak kullanılır.

En değerli sonraki model çalışması; farklı cilt tonları, ışıklar, kamera türleri ve ben, çil, gözenek, gölge gibi negatif örnekler içeren daha geniş ve izinli bir veri kümesiyle yeniden eğitimdir. Eğitim notları `docs/` altındadır.

## Lisans

Bu proje, Ultralytics YOLO bağımlılığı ve YOLO ile eğitilmiş model nedeniyle
**GNU Affero General Public License v3.0 veya sonrası (AGPL-3.0-or-later)**
altında yayımlanır. Tam koşullar için [`LICENSE`](LICENSE), doğrudan dağıtılan
model, font ve marka varlıklarının ayrı koşulları için
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) dosyasını okuyun.

AGPL kapsamında uygulamayı değiştirerek ağ üzerinden kullanıma sunanların,
kullanıcılara karşılık gelen kaynak koda erişim sağlaması gerekir. Kapalı
kaynak veya ticari kullanım düşünülüyorsa özellikle Ultralytics lisans koşulları
incelenmeli ve gerekiyorsa Enterprise lisansı edinilmelidir. Eğitim veri
kümesinin kullanım ve yeniden dağıtım hakkı ayrıca doğrulanmalıdır.

Copyright © 2026 SkinCare Vision AI katkıda bulunanları.

## Yayın öncesi kontrol listesi

- [ ] `.env` ve gerçek kullanıcı verileri Git tarafından takip edilmiyor
- [ ] `ruff check .` ve `pytest` başarılı
- [ ] Frontend lint, tip kontrolü, test ve build başarılı
- [ ] Playwright senaryoları başarılı
- [ ] `npm audit` ve `pip-audit` temiz
- [ ] Public dağıtım değişkenleri ve alan adı izin listesi tanımlı
- [ ] HTTPS, reverse proxy limitleri ve yedekleme politikası hazır
- [x] Ana lisans, üçüncü taraf bildirimleri ve dağıtılan lisans metinleri eklendi
- [ ] YOLO eğitim veri kümesinin kaynağı ve yeniden dağıtım izni belgelendi
- [ ] `git diff --check` temiz ve değişiklikler gözden geçirilmiş

## Yol haritası

- Çok kiracılı dağıtım için OIDC tabanlı kullanıcı hesapları ve yetkilendirme
- Daha güçlü ve daha dengeli veri kümesiyle eğitilmiş bulgu dedektörü
- Ürün formülleri ve resmi bağlantılar için periyodik doğrulama
- Merkezi hız sınırı, gözlemlenebilirlik ve üretim veritabanı seçeneği
