# Model Training and Dataset Governance

This document describes the reproducible training workflow for the
<code>acne_like_spot</code> detector. The model identifies small, acne-like visual
spots on a facial crop. It is not intended to diagnose acne or any other
medical condition.

## Dataset requirements

Use only an object-detection dataset that satisfies all of the following:

- Images are facial or close-up facial photographs.
- Labels are bounding boxes around visible spots.
- The dataset contains at least 500 images; 1,000 or more is preferable.
- Skin tones, lighting conditions, camera types, poses, and image quality are
  sufficiently varied.
- Hard negatives include freckles, moles, pores, facial hair, shadows,
  highlights, and compression artifacts.
- The license explicitly permits the intended training, redistribution, and
  deployment use.
- Consent and privacy terms permit processing of the included face images.

Do not use classification-only datasets, datasets with unclear provenance, or
datasets whose terms prohibit redistribution of trained weights.

## Required provenance record

Before training, create a record containing:

- Dataset name, version, and source URL
- Publisher and copyright holder
- License identifier and a copy of the applicable terms
- Download date and immutable dataset hash where available
- Image count and train/validation/test split sizes
- Original class names and the mapping to <code>acne_like_spot</code>
- Any removed images, relabeling, augmentation, or other transformations
- Confirmation that the terms permit distribution of the resulting weights

Keep this record with the release artifacts. Dataset rights and model-code
licenses are separate obligations.

## Environment

The reference workflow uses Google Colab or another CUDA-capable environment:

~~~python
!pip install -q ultralytics roboflow

import ultralytics
ultralytics.checks()
~~~

Never commit Roboflow or provider API keys. Store them in the notebook secret
manager or another short-lived secret store.

## Dataset download

Replace every placeholder with values from the approved dataset:

~~~python
from roboflow import Roboflow

rf = Roboflow(api_key="READ_FROM_SECRET_STORE")
project = rf.workspace("WORKSPACE_NAME").project("PROJECT_NAME")
version = project.version(1)
dataset = version.download("yolov8")

print(dataset.location)
~~~

Review the generated <code>data.yaml</code> before training. Normalize all
accepted source classes to a single class:

~~~yaml
names:
  0: acne_like_spot
nc: 1
~~~

## Baseline training

Start from a small Ultralytics detection model and preserve every parameter in
the experiment record:

~~~python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")
model.train(
    data=f"{dataset.location}/data.yaml",
    epochs=50,
    imgsz=640,
    batch=8,
    workers=2,
    project="runs",
    name="acne_like_spot",
    seed=42,
    deterministic=True,
)
~~~

Adjust batch size only when required by available memory. Do not select a model
using training-set performance.

## Evaluation

Evaluate the final candidate on a held-out test set and report at minimum:

- Precision and recall
- mAP50 and mAP50-95
- Per-image false-positive and false-negative counts
- Results grouped by skin tone, lighting, camera type, and pose
- Performance on hard-negative images
- Model size and CPU inference latency

Inspect predictions visually. A headline mAP value is not sufficient for a
face-analysis feature, especially when subgroup coverage is limited.

~~~python
metrics = model.val(data=f"{dataset.location}/data.yaml", split="test")
print(metrics.results_dict)
~~~

## Release

Copy the validated weights to:

~~~text
models/acne_like_spot.pt
~~~

Record the SHA-256 hash, Ultralytics version, base model, training parameters,
dataset provenance, evaluation results, and known limitations. Update
<code>THIRD_PARTY_NOTICES.md</code> when the released weight file changes.

Ultralytics applies AGPL-3.0 terms to its open-source software and, by default,
models produced with it. Review the current
[Ultralytics licensing terms](https://www.ultralytics.com/license) before
distribution or commercial deployment.
