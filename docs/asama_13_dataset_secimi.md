# Asama 13: Akne Benzeri Nokta Dataset Secimi

Bu asamada amac tibbi tani modeli egitmek degildir. Amac, yuz kirpimi uzerinde gorsel olarak fark edilebilen `acne_like_spot` kutularini tespit eden tek sinifli bir YOLO modeli icin uygun dataset secmektir.

## Hedef Model

```text
Model gorevi: Object Detection
Sinif sayisi: 1
Sinif adi: acne_like_spot
Girdi: 640x640 letterbox uygulanmis yuz kirpimi
Cikti: akne benzeri kucuk nokta kutulari
```

Model su iddialari uretmeyecek:

```text
akne hastaligi
egzama
rosacea
enfeksiyon
ilac gerekir
kesin neden
kesin tedavi
```

## Roboflow Arama Terimleri

Roboflow Universe uzerinde sirayla su aramalar yapilmali:

```text
acne detection
facial acne detection
pimple detection
acne object detection
acne spots detection
face acne detection
```

## Kabul Kriterleri

Bir dataset ancak su kosullari sagliyorsa kullanilmali:

```text
Project Type: Object Detection
Gorsel tipi: yuz veya yuz yakin cekimi
Etiket tipi: bounding box
Sinif: acne, pimple, spot gibi noktasal gorunum sinifi
Gorsel sayisi: mumkunse 500+, tercihen 1000+
Etiket kalitesi: kutular gercekten kucuk lezyon/nokta bolgelerini sariyor
Lisans: kullanim izni acik ve proje icin uygun
Format export: YOLOv8/YOLOv11 veya Ultralytics uyumlu
```

## Eleme Kriterleri

Su datasetler kullanilmamali:

```text
Classification datasetleri
Sadece "mild/moderate/severe acne" siniflandirmasi yapan datasetler
Yuz disi cilt goruntuleri agirlikli datasetler
Cok dusuk cozunurluklu veya asiri bulanik gorseller
Yanlis/daginik bounding box etiketleri
Cok fazla tibbi sinif iceren datasetler
Ben, melanom, kanser, yara gibi yuksek riskli siniflar iceren datasetler
```

## Sinif Adi Donusturme

Kaynak dataset siniflari farkli olabilir:

```text
acne
pimple
whitehead
blackhead
papule
```

Ilk MVP icin bunlarin hepsi tek guvenli sinifa indirgenir:

```text
acne_like_spot
```

Boylece model tibbi alt tur ayrimi yapmaz, yalnizca gorsel bulgu kutusu uretir.

## Egitim Icin Baslangic Karari

Ilk egitimde onerilen ayarlar:

```text
base model: yolo11n.pt
imgsz: 640
epochs: 50
batch: 8 veya 16
classes: 1
class name: acne_like_spot
```

GPU yetersizse:

```text
epochs: 30
batch: 8
```

## Basari Kriteri

Model ilk MVP icin su davranisi gostermeli:

```text
Yuz kirpimi uzerindeki belirgin akne benzeri kucuk noktalari kacirmamali
Normal golge, dudak, burun deligi, goz cevresi gibi bolgeleri fazla isaretlememeli
Cok dusuk guvenli kutulari filtreleyebilmeli
Cikti JSON formatina cevrilebilir olmali
```

## Sonraki Adim

Secilen Roboflow dataset linki alindiktan sonra Asama 14'e gecilecek:

```text
Google Colab YOLO egitim notebook/prompt hazirligi
```
