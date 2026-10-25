<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/brand/logo-tile-dark.svg">
    <img src="frontend/public/brand/logo-tile.svg" alt="SkinCare Vision AI logosu" width="104" height="104">
  </picture>
</p>

<h1 align="center">SkinCare Vision AI</h1>

<p align="center">
  <strong>Tek bir selfie'yi ölçülmüş bir Cilt Skoruna, gerekçesi açıklanan bir bakım rutinine ve elinizdeki ürünlerle kurulan haftalık bir plana dönüştüren bilgisayarlı görü tabanlı cilt bakım asistanı.</strong>
</p>

<p align="center"><a href="README.md">English</a> · <b>Türkçe</b></p>

<p align="center">
  <a href="https://github.com/sudemkirmiz/skincare-vision-ai/actions/workflows/ci.yml"><img src="https://github.com/sudemkirmiz/skincare-vision-ai/actions/workflows/ci.yml/badge.svg" alt="CI durumu"></a>
  <a href="https://github.com/sudemkirmiz/skincare-vision-ai/actions/workflows/codeql.yml"><img src="https://github.com/sudemkirmiz/skincare-vision-ai/actions/workflows/codeql.yml/badge.svg" alt="CodeQL durumu"></a>
  <img src="https://img.shields.io/badge/testler-273_ba%C5%9Far%C4%B1l%C4%B1-4caf50" alt="273 otomatik test">
  <a href="LICENSE"><img src="https://img.shields.io/badge/lisans-AGPL--3.0-blue.svg" alt="AGPL-3.0 lisansı"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10 veya üstü">
  <img src="https://img.shields.io/badge/React_19-TypeScript-3178C6?logo=typescript&logoColor=white" alt="React 19 ve TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PWA-kurulabilir-4caf50" alt="Kurulabilir PWA">
</p>

<p align="center">
  <a href="https://sudemkirmiz.github.io/skincare-vision-ai/"><img src="https://img.shields.io/badge/%E2%96%B6_Canl%C4%B1_demo-taray%C4%B1c%C4%B1da_a%C3%A7-2f6b45?style=for-the-badge" alt="Canlı demoyu açın"></a>
  &nbsp;
  <a href="#hızlı-başlangıç"><img src="https://img.shields.io/badge/Yerelde_%C3%A7al%C4%B1%C5%9Ft%C4%B1r-5_dakika-4caf50?style=for-the-badge" alt="Yerelde çalıştırın"></a>
  &nbsp;
  <a href="#telefonda-kullanım-ve-arkadaşlarla-paylaşım"><img src="https://img.shields.io/badge/Arkada%C5%9Flarla_payla%C5%9F-tek_komut-8fcb96?style=for-the-badge" alt="Arkadaşlarla paylaşın"></a>
</p>

<p align="center">
  <a href="https://sudemkirmiz.github.io/skincare-vision-ai/"><img src="screenshots/demo.webp" alt="Tüm sayfaları ve sekmeleri sırayla gösteren demo turu: analiz (özet, detaylı analiz, rutin, rapor), ürünler (7 gecelik planlı raf, içerik kontrolü), günlük takip, geçmiş (önce/sonra, kızarıklık ve leke haritaları, yolculuk kartı), ardından koyu tema, yapay zekâ ayarları ve cilt koçu" width="100%"></a>
</p>

> [!IMPORTANT]
> SkinCare Vision AI bir tıbbi cihaz değildir. Yalnızca kozmetik, bakım odaklı görsel tahminler sunar; hastalık teşhisi koymaz, reçeteli tedavi önermez ve dermatoloğun yerini tutmaz.

## Öne çıkanlar

<table>
  <tr>
    <td width="33%" valign="top"><b>Önce ölçer, sonra açıklar</b><br>MediaPipe'ın 478 yüz noktası yüzü bölgelere ayırır; özel eğitilmiş YOLO modeli, CIELAB renk analizi ve göz akına göre beyaz ayarı beş alt skor ve 0–100 arası bir Cilt Skoru üretir. Önerilen her aktif, kendisini gerektiren skoru belirtir.</td>
    <td width="33%" valign="top"><b>Yapay zekâ anahtarı olmadan çalışır</b><br>Analiz, skorlar, rutin, raf planı ve kişiye özel kural tabanlı yorum tamamen çevrimdışı çalışır. Gemini, OpenAI, Groq veya Hugging Face yalnızca daha zengin bir yorum ekler; otomatik yedekleme, devre kesici ve önbellek ile.</td>
    <td width="33%" valign="top"><b>Elinizdekiyle planlar</b><br>Raf planlayıcı ürünlerinizi inceden kalına sıralar ve çakışan aktiflerin (retinol, AHA, BHA) asla aynı geceye düşmediği 7 gecelik bir takvim kurar.</td>
  </tr>
  <tr>
    <td valign="top"><b>Günlük kullanım için</b><br>Kurulabilir PWA, rehberli kamera çekimi, tek dokunuşla rutin işaretleme, seri ve rozetler, cihaz üzerinde hatırlatıcılar, kişisel tetikleyici içgörüleri, açık ve koyu tema.</td>
    <td valign="top"><b>Gizlilik temelden</b><br>Fotoğraflar diske yazılmaz. Paylaşılan bir bağlantıda her tarayıcı yalnızca kendi profillerini görür. Sıkı CSP, sabit zamanlı anahtar karşılaştırması, CSRF'e dayanıklı çerezler, ayrıştırmadan önce istek sınırları, sertleştirilmiş salt okunur container.</td>
    <td valign="top"><b>Ürün gibi test edilir</b><br>248 backend testi (rota rota güvenlik testleri dahil), 22 frontend birim testi ve Playwright uçtan uca testleri; hepsi çevrimdışı. CI her push'ta Ruff, Bandit, CodeQL, pip-audit, npm audit, tür denetimi ve Docker derlemesi çalıştırır.</td>
  </tr>
</table>

## İçindekiler

[Deneyin](#deneyin) · [Özellikler](#özellikler) · [Yapay zekâ sağlayıcıları](#yapay-zekâ-sağlayıcıları-ve-anahtarsız-mod) · [Telefon ve paylaşım](#telefonda-kullanım-ve-arkadaşlarla-paylaşım) · [Mimari](#mimari) · [Hızlı başlangıç](#hızlı-başlangıç) · [Güvenlik](#güvenlik-ve-gizlilik) · [Testler](#testler-ve-kalite) · [Belgeler](#belgeler) · [Lisans](#lisans)

## Deneyin

| | Ne sunar | Ne gerekir |
| --- | --- | --- |
| **[Canlı demo](https://sudemkirmiz.github.io/skincare-vision-ai/)** | Masaüstünde veya telefonda tüm arayüz; yapay zekâ ile üretilmiş örnek bir portrenin gerçek analizi ve birkaç haftalık örnek geçmiş | Hiçbir şey; tarayıcıda çalışır, hiçbir şey yüklenmez |
| **[Yerelde çalıştırma](#hızlı-başlangıç)** | Kendi fotoğraflarınızın analizi, kamera rehberi, geçmiş, raf, cilt koçu | Python 3.10+, Node.js 22+ |
| **[Bilgisayarınızdan paylaşma](#telefonda-kullanım-ve-arkadaşlarla-paylaşım)** | Arkadaşlarınızın telefonu için HTTPS davet bağlantısı; her telefon kendi özel profillerini tutar | Yerel kurulum ve `cloudflared` |

## Özellikler

### Analiz

- Bir ile üç fotoğraf (önden, sol, sağ) bölge bölge birleştirilir; ya da mesafe, kadraj, baş açısı, ışık ve netliği canlı kontrol edip kendiliğinden çeken **rehberli kamera çekimi**
- MediaPipe yüz noktaları ve OpenCV Haar yedeği; alın, burun, yanaklar ve çene ayrı ayrı ölçülür, göz, kaş ve dudak hesaba katılmaz
- Tek sınıflı, özel eğitilmiş <code>acne_like_spot</code> YOLO modeli ve renk adayları; yanlış alarmları eleyen isteğe bağlı Gemini ikinci görüşü
- Beş alt skor (nokta yoğunluğu, kızarıklık dengesi, ton eşitliği, doku, parlama) ve ağırlıklı Cilt Skoru; fotoğraf kalitesi kontrolü ve profil ile fotoğraf arasındaki uyumsuzluk ipuçları

<table>
  <tr>
    <td width="33%"><img src="screenshots/analiz-sonucu.png" alt="Cilt Skoru, yüz bölgeleri ve bakım yorumuyla analiz sonucu"></td>
    <td width="33%"><img src="screenshots/detayli-analiz.png" alt="Detaylı analiz: alt skorlar, fotoğraf kalitesi ve bölgesel dağılım"></td>
    <td width="33%"><img src="screenshots/kamera-rehberi.png" alt="Canlı kadraj ovali ve otomatik çekimle rehberli kamera"></td>
  </tr>
</table>

### Rutin, ürünler ve planlama

- Ölçümlerden ve profilden, gerekçesi açıklanan sabah ve akşam rutini; yaş, hassasiyet, alerji, hamilelik ve emzirme için güvenlik kuralları
- Yapıştırılan metinden ya da etiket fotoğrafından INCI içerik kontrolü: sonuç, bulunan aktifler, dikkat edilecekler ve artılar
- Çakışma, aynı aktifin tekrarı, eksik adım ve açıldıktan sonraki kullanım süresi (PAO) kontrolleriyle ürün rafı
- **Raf planlayıcı:** kullanıcının kendi ürünleriyle uygulama sırası (güneş kremi her zaman en sonda) ve 7 gecelik skin cycling takvimi; çakışan aktifler hep farklı gecelerde, hassas ciltte daha az aktif gece, süresi dolmuş ürünler plan dışı

<table>
  <tr>
    <td width="33%"><img src="screenshots/rutin.png" alt="Aktiflerle kişisel sabah ve akşam rutini"></td>
    <td width="33%"><img src="screenshots/raf-rutinim.png" alt="Kontrolleriyle ürün rafı, uygulama sırası ve 7 gecelik plan"></td>
    <td width="33%"><img src="screenshots/icerik-kontrolu.png" alt="Sonuç, aktifler, dikkat edilecekler ve artılarla INCI içerik kontrolü"></td>
  </tr>
</table>

### Takip, geçmiş ve raporlar

- Tek dokunuşla sabah ve akşam rutini işaretleme, 3–100 günlük rozetlerle rutin serisi ve rutin işaretlendiğinde susan cihaz üzerinde hatırlatıcılar
- Günlük kayıt (cilt hissi, tetikleyiciler, belirtiler) ve "az uyuduğunuz günlerin ertesinde cildinizi 2,3 puan daha kötü değerlendirmişsiniz" gibi kişisel içgörüler; her zaman ilişki olarak, neden-sonuç olarak değil
- Rutin olaylarıyla skor grafikleri, hizalanmış önce/sonra kaydırıcısı, kızarıklık ve leke değişim haritaları
- Çok sayfalı PDF rapor, JSON ve CSV dışa aktarma; yalnızca skorlardan, asla fotoğraftan çizilen paylaşılabilir cilt yolculuğu kartı

<table>
  <tr>
    <td width="33%"><img src="screenshots/gunluk-takip.png" alt="Günlük kayıt, rutin serisi, takvim ve kişisel içgörüler"></td>
    <td width="33%"><img src="screenshots/gecmis.png" alt="Cilt Skoru grafikleri, önce/sonra karşılaştırması ve kayıtlar"></td>
    <td width="33%"><img src="screenshots/pdf-rapor.png" alt="Oluşturulan PDF raporun iki sayfası"></td>
  </tr>
</table>

### Cilt koçu, profil ve uygulama deneyimi

- Kullanıcının profili, rutini, rafı, günlüğü ve günün UV ve nem bilgisini bilerek yanıt veren cilt koçu
- Fotoğraf işleme için açık onay içeren iki adımlı profil oluşturma ve çoklu profil
- Çevrimdışı açılan kurulabilir PWA; açık, koyu ve sistem teması; telefona göre ayarlanmış düzen

<table>
  <tr>
    <td width="30%"><img src="screenshots/cilt-kocu.png" alt="Önerilen sorularla cilt koçu paneli"></td>
    <td width="22%"><img src="screenshots/yolculuk-karti.png" alt="Fotoğraf içermeyen, skorlardan üretilen cilt yolculuğu kartı"></td>
    <td width="24%"><img src="screenshots/profil.png" alt="Zorunlu bilgiler ve fotoğraf onayıyla profil oluşturma"></td>
    <td width="12%"><img src="screenshots/mobil-analiz.png" alt="Telefonda koyu temada analiz sonucu"></td>
    <td width="12%"><img src="screenshots/mobil-takip.png" alt="Telefonda koyu temada günlük takip"></td>
  </tr>
</table>

<p align="center"><img src="screenshots/koyu-tema.png" alt="Koyu temada günlük rutin kartıyla ana sayfa" width="80%"></p>

## Yapay zekâ sağlayıcıları ve anahtarsız mod

Analizin çekirdeği hiçbir bulut modeline ihtiyaç duymaz. Yapay zekâ sağlayıcısı yalnızca serbest metin bakım yorumunu yazar, etiket fotoğraflarını okur ve cilt koçunu çalıştırır.

| Sağlayıcı | Varsayılan model | Ücret | Not |
| --- | --- | --- | --- |
| **Anahtarsız** | yerel kural motoru | ücretsiz | Ölçümlerden kişiye özel yorum: şiddete göre değişen ifadeler, en çok etkilenen bölge ve T/U-bölgesi dağılımı, birlikte görülen bulgular, profil hedefleri ve son kayıtlı analize göre değişim; her cümle ekrandaki bir sayıya dayanır |
| **Gemini** | <code>gemini-3.8-flash</code> ve üç yedek model | ücretsiz kota var | Başlangıç için önerilir; nokta ikinci görüşünü de sağlar. [Anahtar alın](https://aistudio.google.com/apikey) |
| **OpenAI** | Responses API ile <code>gpt-6-luna</code> | ücretli, en uygun fiyatlı görsel model | [Anahtar alın](https://platform.openai.com/api-keys) |
| **Groq** | <code>meta-llama/llama-4-scout-17b-16e-instruct</code> | ücretsiz kota var | OpenAI uyumlu uç nokta |
| **Hugging Face** | <code>google/gemma-3-4b-it</code> | ücretsiz kredi | Inference Providers'taki herhangi bir görsel model |

Sunucu anahtarları <code>.env</code> dosyasında durur ve tarayıcıya asla gönderilmez. <code>ALLOW_USER_API_KEYS=true</code> olduğunda kullanıcılar kendi anahtarlarını girebilir; anahtar sekme belleğinde (ya da kullanıcı "bu cihazda hatırla"yı seçerse yalnızca o cihazda) kalır ve sunucuda saklanmaz. Seçilen sağlayıcı hata verirse anahtarı olan diğerleri sırayla denenir; hepsi başarısız olursa kural tabanlı yorum, sebebiyle birlikte gösterilir. Her model adı bir ortam değişkenidir; kaldırılan bir model kod değişikliği gerektirmez ([yapılandırma](docs/configuration.md)).

## Telefonda kullanım ve arkadaşlarla paylaşım

**Sadece göz atmak için:** [canlı demo](https://sudemkirmiz.github.io/skincare-vision-ai/) bağlantısını gönderin. Her telefonda çalışır, ana ekrana eklenebilir ve hiçbir şey yüklemez.

**Bilgisayarınızdan gerçek analiz:** tek komut, Cloudflare hızlı tüneliyle ücretsiz bir HTTPS davet bağlantısı oluşturur; telefon kameraları HTTPS gerektirir.

~~~powershell
winget install Cloudflare.cloudflared        # macOS: brew install cloudflared
.\.venv\Scripts\python scripts\share.py
~~~

Davet bağlantısını açan telefon erişim anahtarını kendisi kaydeder. **Her telefon yalnızca kendi profillerini, geçmişini, günlüğünü ve rafını görür:** tarayıcı rastgele bir cihaz anahtarı tutar, sunucu bunun yalnızca SHA-256 özetini saklar. Arkadaşlarınız kendi Gemini veya OpenAI anahtarlarını kullanabilir ya da hiç anahtar kullanmayabilir. Bağlantı bilgisayarınız açıkken çalışır. Sürekli açık barındırma ve üretim kontrol listesi için [dağıtım](docs/deployment.md) belgesine bakın.

## Mimari

~~~mermaid
flowchart LR
    subgraph Browser["Tarayıcı / kurulu PWA"]
        UI["React 19 + TypeScript<br/>TanStack Query, Tailwind v4"]
        SW["Servis çalışanı<br/>yalnızca uygulama kabuğu"]
    end
    subgraph API["FastAPI (tek origin)"]
        Guard["Koruma: anahtar, cihaz kapsamı,<br/>gövde ve hız sınırları, CSP"]
        Pipeline["Analiz akışı"]
        Plan["Rutin, INCI, raf planı,<br/>yerel yorum"]
        Store[("SQLite<br/>profiller, geçmiş,<br/>günlük, raf")]
    end
    subgraph Vision["Cihaz üzerindeki modeller"]
        MP["MediaPipe<br/>478 nokta"]
        YOLO["YOLO<br/>acne_like_spot"]
        CV["OpenCV ölçümleri<br/>CIELAB, beyaz ayarı"]
    end
    subgraph Cloud["İsteğe bağlı yapay zekâ (yedekleme zinciri)"]
        G["Gemini"]
        O["OpenAI"]
        Q["Groq"]
        H["Hugging Face"]
    end
    UI -->|"/api"| Guard --> Pipeline
    Pipeline --> MP & YOLO & CV
    Pipeline --> Plan --> Store
    Pipeline -.->|"yüz kırpımı + sınırlı bağlam"| G & O & Q & H
~~~

Ölçümler önce gelir ve deterministiktir; dil modeli yalnızca yorumu ifade eder. Fotoğraflar geçici bir klasörde işlenip silinir; sağlayıcılar yalnızca yüz kırpımını, tercih edilen adı ve hitap biçimini alır. Modül yapısı, istek akışı, tasarım kararları, skor ağırlıkları ve API haritası [mimari](docs/architecture.md) belgesindedir.

| Katman | Teknolojiler |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, Recharts, servis çalışanı |
| API | FastAPI, Pydantic, Uvicorn |
| Bilgisayarlı görü | Ultralytics YOLO, MediaPipe, OpenCV, Pillow, NumPy |
| İsteğe bağlı yapay zekâ | Gemini, OpenAI (Responses API), Groq, Hugging Face Inference Providers |
| Veri ve raporlar | Sürümlü geçişlerle SQLite, ReportLab, JSON, CSV, Canvas |
| Kalite ve teslim | Pytest, Ruff, Bandit, CodeQL, pip-audit, Vitest, Oxlint, Playwright, Docker, GitHub Actions, GitHub Pages |

## Hızlı başlangıç

Gerekenler: Python 3.10+ (CI 3.12 kullanır), Node.js 22+ ve Git. Sağlayıcı anahtarı isteğe bağlıdır.

~~~powershell
git clone https://github.com/sudemkirmiz/skincare-vision-ai.git
cd skincare-vision-ai

python -m venv .venv
./.venv/Scripts/python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -c constraints.txt -r requirements.txt
./.venv/Scripts/python.exe -m pip install --no-deps mediapipe==1.1.1
Copy-Item .env.example .env

cd frontend; npm ci; npm run build; cd ..
./.venv/Scripts/python.exe -m uvicorn api.server:app --app-dir src --host 127.0.0.1 --port 8000
~~~

<http://127.0.0.1:8000> adresini açın. macOS ve Linux'ta <code>python3</code>, <code>./.venv/bin/python</code> ve <code>cp</code> kullanın. MediaPipe, YOLO'nun kullandığı OpenCV sürümünü değiştirmesin diye <code>--no-deps</code> ile kurulur.

Geliştirme için API'yi <code>--reload</code> ile, arayüzü <code>cd frontend; npm run dev</code> ile çalıştırın (Vite <http://localhost:5173> adresinde, <code>/api</code> isteklerini 8000 portuna yönlendirir). Docker: <code>docker compose up --build -d</code>; ayrıntılar [dağıtım](docs/deployment.md) belgesinde.

## Güvenlik ve gizlilik

- Herkese açık modda her <code>/api</code> rotası erişim anahtarı ister; bir test tüm rotaları tarar, böylece korumasız yeni bir uç nokta yayına çıkamaz. 20 hatalı denemeden sonra IP bir süre durdurulur.
- Cihaz bazlı profiller aynı bağlantıyı paylaşan kişileri birbirinden ayırır; başka bir cihazın verisi "bulunamadı" ile aynı yanıtı verir.
- Çerezler (görseller ve indirmeler için gerekli) yalnızca okuma isteklerinde geçerlidir; veri değiştiren istekler, siteler arası isteklerin gönderemeyeceği başlıklar ister.
- Her modda sıkı CSP, HSTS, COOP ve CORP, host ve CORS izin listeleri, ayrıştırmadan önce gövde sınırları, görsel ve piksel bombası doğrulaması.
- Fotoğraflar diske yazılmaz; servis çalışanı <code>/api</code> yanıtlarını asla önbelleğe almaz; kişisel anahtarlar saklanmaz ve günlüğe yazılmaz.
- CI Bandit, CodeQL, pip-audit ve npm audit çalıştırır; Dependabot bağımlılıkları izler.

Ayrıntılar ve güvenlik açığı bildirimi: [SECURITY.md](SECURITY.md).

## Testler ve kalite

~~~powershell
pytest; ruff check .; python -m bandit -r src -q                      # backend
cd frontend; npm run lint; npm run typecheck; npm test; npm run test:e2e   # frontend
~~~

Testler gerçek ağ erişimini engeller ve tüm sağlayıcı çağrılarını taklit eder. Görü akışını ve ölçümleri, rutin ve güvenlik kurallarını, raf planlayıcıyı, yerel yorumu, sağlayıcı istemcilerini ve yedeklemeyi, herkese açık mod ve cihaz ayrımı dahil API'yi, güvenlik regresyon testlerini, demo veri katmanını, hatırlatıcıları ve ana tarayıcı akışlarını kapsar. GitHub Actions her push'ta bunların hepsini, ayrıca Docker derlemesini ve Pages demo yayınını çalıştırır.

## Belgeler

Ayrıntılı belgeler İngilizcedir.

| Belge | İçerik |
| --- | --- |
| [Mimari](docs/architecture.md) | Modül yapısı, istek akışı, tasarım kararları, skorlama, API haritası |
| [Yapılandırma](docs/configuration.md) | Tüm ortam değişkenleri ve varsayılanları |
| [Dağıtım ve paylaşım](docs/deployment.md) | Arkadaşlar için davet bağlantısı, Docker, barındırma, üretim kontrol listesi |
| [Canlı demo](docs/live-demo.md) | Tarayıcıda çalışan demonun işleyişi, demonun ve README görsellerinin yeniden üretimi |
| [Model eğitimi](docs/model-training.md) | Veri kümesi gereksinimleri, kaynak kaydı ve tekrarlanabilir YOLO eğitimi |
| [Güvenlik politikası](SECURITY.md) | Yerleşik korumalar ve güvenlik açığı bildirimi |

## Proje yapısı

~~~text
skincare-vision-ai/
|-- .github/workflows/   CI, CodeQL, container imajı ve Pages demosu
|-- assets/              PDF yazı tipleri ve rapor logosu
|-- data/                başlangıç ürün kataloğu ve şeması
|-- docs/                mimari, yapılandırma, dağıtım, demo, model eğitimi
|-- frontend/            React uygulaması (src/), demo veri katmanı (src/demo/), marka dosyaları, e2e testleri, görsel betikleri
|-- licenses/            üçüncü taraf lisans metinleri
|-- models/              YOLO ve MediaPipe model dosyaları
|-- screenshots/         demodan üretilen README görselleri
|-- scripts/             paylaşım, demo verisi, README animasyonu ve örnek değerlendirme
|-- src/                 Python backend: api, analysis, detection, vlm, recommendation, history, ...
`-- tests/               çevrimdışı backend testleri, tests/test_security.py dahil
~~~

## Modelin sınırları

Projedeki YOLO modeli tek sınıflıdır (<code>acne_like_spot</code>) ve mAP50 değeri şu an yaklaşık 0,37'dir: faydalı bir sinyaldir, kesin ya da klinik bir dedektör değildir. Renk analizi ve isteğe bağlı ikinci görüş birbirini tamamlayan sinyallerdir, bir durumun doğrulaması değildir. En değerli sonraki adım, farklı cilt tonlarını, ışık koşullarını, kameraları ve çil, ben, gözenek, gölge gibi zor örnekleri kapsayan daha büyük ve lisanslı bir veri kümesiyle yeniden eğitimdir ([model eğitimi](docs/model-training.md)).

## Lisans

**Telif hakkı © 2026 Sudem Kırmız.** Kodun, arayüzün, belgelerin, adın ve logonun özgün yazarı ve telif hakkı sahibi.

| Bölüm | Koşullar |
| --- | --- |
| Kaynak kod | [GNU AGPL-3.0-or-later](LICENSE): kodu değiştiren veya başkaları için çalıştıran herkes, yalnızca ağ üzerinden sunsa bile, telif bildirimlerini korumak ve tüm kaynak kodunu aynı lisansla yayımlamak zorundadır |
| "SkinCare Vision AI" adı ve logo | **Tüm hakları saklıdır.** AGPL kapsamında değildir (madde 7(e)); kopyalar kendi adlarını ve logolarını kullanmalıdır. Bkz. [TRADEMARKS.md](TRADEMARKS.md) |
| Üçüncü taraf modeller, yazı tipleri, kütüphaneler ve örnek portre | Kendi lisansları ve sahipleri; bkz. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

Proje Ultralytics YOLO'ya dayandığı ve YOLO ile eğitilmiş bir model içerdiği için AGPL zorunludur; kapalı kaynak veya ticari kullanımdan önce [Ultralytics lisans seçeneklerini](https://www.ultralytics.com/license) inceleyin. Her kaynak dosya telif satırı içeren bir SPDX başlığı taşır ve [NOTICE](NOTICE) dosyası her kopyayla birlikte dağıtılmalıdır. Bu özet hukuki danışmanlık değildir.

<p align="center">
  <img src="frontend/public/brand/logo-tile.svg" alt="" width="40" height="40"><br>
  Tasarlayan ve geliştiren: <b>Sudem Kırmız</b> · © 2026
</p>
