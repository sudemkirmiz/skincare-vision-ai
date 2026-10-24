# Üçüncü Taraf Lisans ve Marka Bildirimleri

Bu dosya, SkinCare Vision AI deposunda doğrudan dağıtılan başlıca üçüncü taraf
bileşenleri açıklar. Bağımlılıkların eksiksiz ve sürüme özgü lisans bilgileri,
ilgili Python ve npm paketlerinin kendi dağıtımlarında bulunur.

## Ultralytics YOLO

Uygulama `ultralytics` Python paketini kullanır ve
`models/acne_like_spot.pt` dosyası Ultralytics YOLO ile eğitilmiştir.
Ultralytics yazılımı ve varsayılan olarak bu yazılımla üretilen modeller
GNU Affero General Public License v3.0 (AGPL-3.0) kapsamındadır. Bu nedenle
projenin ana lisansı `AGPL-3.0-or-later` olarak belirlenmiştir.

Kapalı kaynak, kurum içi veya ticari bir dağıtım planlanıyorsa, kullanım
senaryosunun AGPL-3.0 koşullarını karşılayıp karşılamadığı değerlendirilmelidir;
gerekiyorsa Ultralytics Enterprise lisansı edinilmelidir:

- https://www.ultralytics.com/license
- https://www.ultralytics.com/legal/agpl-3-0-software-license

Model dosyası SHA-256:
`15D7368C5F256CC1AAAC81B396E00B8E78DDB316DD4D22945F037537B43C2813`

> Veri kümesi hakları model lisansından ayrıdır. Modelin eğitiminde kullanılan
> görüntü ve etiketlerin kaynağı ile yeniden dağıtım izni, herkese açık bir
> sürüm yayımlanmadan önce proje sahibi tarafından kayıt altına alınmalıdır.

## Google MediaPipe Face Landmarker

`models/face_landmarker.task`, Google MediaPipe Face Landmarker model paketidir
ve Apache License 2.0 kapsamındadır. Lisans metni
`licenses/APACHE-2.0.txt` dosyasındadır.

- Kaynak: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- Model kartı: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf
- SHA-256: `64184E229B263107BC2B804C6625DB1341FF2BB731874B0BCC2FE6544E0BC9FF`

## Yazı tipleri

- `assets/fonts/Poppins-*.ttf`: Poppins Project Authors, SIL Open Font License
  1.1. Lisans metni `assets/fonts/OFL.txt` dosyasındadır.
- `@fontsource-variable/fraunces`: Fraunces Project Authors, SIL Open Font
  License 1.1. Lisans metni `licenses/FRAUNCES-OFL-1.1.txt` dosyasındadır.
- `@fontsource-variable/inter`: Inter Project Authors, SIL Open Font License
  1.1. Lisans metni `licenses/INTER-OFL-1.1.txt` dosyasındadır.

## Mağaza adları ve görselleri

Google, Hepsiburada ve Trendyol adları ile logoları ilgili hak sahiplerinin
ticari markalarıdır. Depodaki kullanımları yalnızca hedef mağazayı tanımlamak
içindir; herhangi bir ortaklık veya onay anlamına gelmez. AGPL-3.0 bu üçüncü
taraf ticari markaları üzerinde hak vermez.

## Diğer bağımlılıklar

`requirements.txt`, `constraints.txt`, `frontend/package.json` ve
`frontend/package-lock.json` ile kurulan diğer bileşenler kendi lisansları
altındadır. Bir container veya ikili dağıtım yapılırken bu bileşenlerin lisans
ve bildirim yükümlülükleri ayrıca korunmalıdır.

Bu belge hukuki danışmanlık değildir.
