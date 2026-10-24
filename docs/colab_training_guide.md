# Asama 14: Google Colab YOLO Egitim Rehberi

Bu rehber, `acne_like_spot` adli tek sinif icin YOLO modeli egitmek uzere hazirlandi. Amac tibbi tani modeli gelistirmek degildir; model yalnizca yuz kirpimi uzerindeki akne benzeri kucuk gorsel noktalar icin bounding box uretir.

Hedef cikti:

```text
models/acne_like_spot.pt
```

## 0. Colab Runtime Ayari

Google Colab'da su yolu izleyin:

```text
Runtime > Change runtime type > Hardware accelerator > GPU
```

Ardindan GPU kontrolu:

```python
!nvidia-smi
```

## 1. Ortam Kurulumu

```python
!pip install -q ultralytics roboflow
```

Kurulumu dogrulayin:

```python
import ultralytics
ultralytics.checks()
```

## 2. Veri Seti Indirme

Roboflow dataset sayfasindan Python indirme kodunu alabilirsiniz. Asagidaki blok placeholder olarak hazirlandi.

Onemli:

```text
Dataset tipi: Object Detection
Export formati: YOLOv8 veya YOLOv11/Ultralytics uyumlu
Sinif hedefi: acne_like_spot
```

```python
from roboflow import Roboflow

ROBOFLOW_API_KEY = "BURAYA_API_KEY"
WORKSPACE_NAME = "BURAYA_WORKSPACE_ADI"
PROJECT_NAME = "BURAYA_PROJECT_ADI"
VERSION_NUMBER = 1

rf = Roboflow(api_key=ROBOFLOW_API_KEY)
project = rf.workspace(WORKSPACE_NAME).project(PROJECT_NAME)
version = project.version(VERSION_NUMBER)

dataset = version.download("yolov8")
print(dataset.location)
```

Dataset indirildikten sonra `data.yaml` yolunu kontrol edin:

```python
from pathlib import Path

dataset_path = Path(dataset.location)
data_yaml = dataset_path / "data.yaml"

print(data_yaml)
print(data_yaml.exists())
```

## 3. Sinif Adini Tek Sinifa Sabitleme

Roboflow datasetindeki sinif adi `acne`, `pimple`, `spot` gibi gelebilir. MVP icin model ciktisini tek guvenli sinifa indiriyoruz:

```text
acne_like_spot
```

`data.yaml` icindeki `names` alanini kontrol edin:

```python
import yaml

with open(data_yaml, "r", encoding="utf-8") as file:
    data_config = yaml.safe_load(file)

print(data_config)
```

Eger dataset zaten tek sinifliysa sinif adini guvenli ada donusturun:

```python
data_config["nc"] = 1
data_config["names"] = ["acne_like_spot"]

with open(data_yaml, "w", encoding="utf-8") as file:
    yaml.safe_dump(data_config, file, sort_keys=False)

print(data_yaml.read_text())
```

Not: Dataset birden fazla sinif iceriyorsa sadece YAML adini degistirmek yetmez. Bu durumda Roboflow tarafinda siniflari birlestirerek yeni bir version export etmek daha dogrudur.

## 4. YOLO Egitimi

Onerilen baslangic modeli:

```text
yolo11n.pt
```

GPU bellegi yetersiz olursa `batch=8` deneyin.

Python API ile egitim:

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data=str(data_yaml),
    epochs=50,
    imgsz=640,
    batch=16,
    project="/content/runs/acne_like_spot",
    name="yolo11n_50ep",
    patience=10,
)
```

Alternatif CLI komutu:

```python
!yolo detect train \
  model=yolo11n.pt \
  data={data_yaml} \
  epochs=50 \
  imgsz=640 \
  batch=16 \
  project=/content/runs/acne_like_spot \
  name=yolo11n_50ep \
  patience=10
```

## 5. Sonuclari Kontrol Etme

Egitim klasorunu bulun:

```python
from pathlib import Path

run_dir = Path("/content/runs/acne_like_spot/yolo11n_50ep")
print(run_dir)
print(run_dir.exists())
```

Metrik grafigini gosterin:

```python
from IPython.display import Image, display

display(Image(filename=str(run_dir / "results.png")))
```

Validation tahmin orneklerini gosterin:

```python
for image_name in [
    "val_batch0_pred.jpg",
    "val_batch1_pred.jpg",
    "val_batch2_pred.jpg",
]:
    image_path = run_dir / image_name
    if image_path.exists():
        display(Image(filename=str(image_path)))
```

Son metrikleri tablo olarak inceleyin:

```python
import pandas as pd

results_csv = run_dir / "results.csv"
metrics = pd.read_csv(results_csv)
display(metrics.tail())
```

Bakilacak temel degerler:

```text
train/box_loss: dusmesi beklenir
val/box_loss: dusmesi beklenir
metrics/precision(B): yuksek olmasi iyi
metrics/recall(B): yuksek olmasi iyi
metrics/mAP50(B): yuksek olmasi iyi
metrics/mAP50-95(B): yuksek olmasi iyi
```

Pratik MVP yorumu:

```text
Model belirgin akne benzeri noktalari yakaliyorsa,
normal golge/dudak/burun/goruntu parazitlerini fazla isaretlemiyorsa,
ilk entegrasyon icin kullanilabilir.
```

## 6. Best.pt Dosyasini Hazirlama

Egitim sonunda en iyi agirlik dosyasi:

```text
runs/.../weights/best.pt
```

Bu dosyayi proje standardimiz olan ada kopyalayin:

```python
import shutil

best_path = run_dir / "weights" / "best.pt"
export_path = Path("/content/acne_like_spot.pt")

print(best_path)
print(best_path.exists())

shutil.copy(best_path, export_path)
print(export_path)
```

Colab'dan bilgisayara indirin:

```python
from google.colab import files

files.download(str(export_path))
```

Indirilen dosyayi lokal projede su yola koyun:

```text
C:\Users\MSI\Desktop\YZT\SkinCareVisionAI\models\acne_like_spot.pt
```

## 7. Tum Egitim Klasorunu Yedekleme

Metrikleri ve gorselleri de saklamak icin:

```python
!zip -r /content/acne_like_spot_training_run.zip /content/runs/acne_like_spot/yolo11n_50ep
files.download("/content/acne_like_spot_training_run.zip")
```

## 8. Sonraki Asama

`acne_like_spot.pt` dosyasi projeye eklendikten sonra Asama 16'ya gecilecek:

```text
src/detection/skin_finding_detector.py
letterboxing/padding
YOLO inference
structured JSON output
```
