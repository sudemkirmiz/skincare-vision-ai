# Third-party licenses and trademark notices

This file lists the main third-party components distributed directly in the SkinCare Vision AI repository. Complete, version-specific license information for dependencies ships with the respective Python and npm packages.

## Ultralytics YOLO

The application uses the `ultralytics` Python package, and `models/acne_like_spot.pt` was trained with Ultralytics YOLO. Ultralytics software, and by default the models produced with it, are licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). This is why the project itself is licensed `AGPL-3.0-or-later`.

For a closed-source, internal or commercial deployment, check whether the use case meets the AGPL-3.0 terms; if not, an Ultralytics Enterprise license is required:

- https://www.ultralytics.com/license
- https://www.ultralytics.com/legal/agpl-3-0-software-license

Model file SHA-256: `15D7368C5F256CC1AAAC81B396E00B8E78DDB316DD4D22945F037537B43C2813`

> Dataset rights are separate from the model license. The source of the training images and labels, and the permission to redistribute them, must be documented by the project owner before a public release (see [docs/model-training.md](docs/model-training.md)).

## Google MediaPipe Face Landmarker

`models/face_landmarker.task` is the Google MediaPipe Face Landmarker model bundle, licensed under the Apache License 2.0. The license text is in `licenses/APACHE-2.0.txt`.

- Source: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- Model card: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf
- SHA-256: `64184E229B263107BC2B804C6625DB1341FF2BB731874B0BCC2FE6544E0BC9FF`

## Sample portrait (demo and README media)

The face shown in the live demo (`frontend/src/demo/assets/sample.jpg`), in the recorded demo data and in the README screenshots and animation is an AI-generated portrait, not a photo of a real person. It was obtained from Freepik / Magnific and is not owned by the author of this project; its rights remain with their holders. It is included only to demonstrate the software, and it is not covered by the AGPL-3.0 license of this repository. Replace it with your own image before reusing the demo or the media elsewhere.

## Fonts

- `assets/fonts/Poppins-*.ttf`: Poppins Project Authors, SIL Open Font License 1.1. License text: `assets/fonts/OFL.txt`.
- `@fontsource-variable/fraunces`: Fraunces Project Authors, SIL Open Font License 1.1. License text: `licenses/FRAUNCES-OFL-1.1.txt`.
- `@fontsource-variable/inter`: Inter Project Authors, SIL Open Font License 1.1. License text: `licenses/INTER-OFL-1.1.txt`.

## Store names and logos

Google, Hepsiburada and Trendyol names and logos are trademarks of their respective owners. They appear in the repository only to identify the target store and imply no partnership or endorsement. The AGPL-3.0 grants no rights to these third-party trademarks.

## Other dependencies

Other components installed through `requirements.txt`, `constraints.txt`, `frontend/package.json` and `frontend/package-lock.json` keep their own licenses. Their license and notice obligations must be preserved in any container or binary distribution.

This document is not legal advice.
