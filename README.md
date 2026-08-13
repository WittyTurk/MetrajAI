# MetrajAI

MetrajAI, DXF kaynaklarını cihazdan çıkarmadan analiz eden ve yalnız mühendis
tarafından onaylanmış elemanlardan izlenebilir metraj üreten yerel masaüstü
uygulamasıdır.

Bu depo iki ayrı kod alanı içerir:

- `metrajai/`: yeni, güvenilir hesap motoru. Aktif geliştirme burada yapılır.
- `SRC/`: önceki deneysel uygulama. Karşılaştırma amacıyla `legacy` olarak korunur;
  yeni motor tarafından içe aktarılmaz.

## Güvenlik ilkeleri

- Aks kesişimleri kolon, tüm bina boyunca uzanan akslar kiriş sayılmaz.
- Eksik birim veya fiziksel ölçü yerine `0` ya da gizli varsayım yazılmaz.
- Donatı paftası/çizelgesi yoksa tonaj tahmin edilmez.
- Tespit, mühendis kararı ve kesin metraj ayrı veri kayıtlarıdır.
- Aynı kaynak aynı eleman kimliklerini üretir; yeniden analiz mühendis kararlarını
  mümkün olduğu sürece korur.
- Kesin hesap yalnız `accepted` elemanlardan oluşur.

## Mimari

```text
Tauri 2 + React/TypeScript
          │ 127.0.0.1 + tek kullanımlık oturum anahtarı
          ▼
FastAPI / başsız CLI (PyInstaller sidecar)
          │
          ├─ muhafazakâr DXF tespiti (ezdxf)
          ├─ mühendis onaylı hesap politikaları
          ├─ SQLite karar ve iz kayıtları
          └─ formüllü Excel raporu (artifact-tool çalışma zamanı)
```

Her proje taşınabilir bir klasördür:

```text
pilot.metrajai/
├── manifest.json
├── project.metrajai.sqlite3
├── sources/       # SHA-256 isimli, değiştirilmeyen kaynak kopyaları
├── cache/
├── exports/
├── logs/          # JSONL tanılama kayıtları
└── backups/       # şema geçişi ve kullanıcı yedekleri
```

## Yerel geliştirme

Python 3.12 veya 3.13 kullanın:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
```

Mevcut geliştirme sürümünü tek komutla çalıştırın:

```bash
.venv/bin/python scripts/run_dev.py
```

Tarayıcıda `http://127.0.0.1:1420/` açılır. Kapatmak için komutu çalıştırdığınız
terminalde `Ctrl+C` kullanın. Klasör ve dosya düğmeleri, tarayıcı modunda da yerel
motor üzerinden işletim sisteminin güvenli seçicisini açar. Yol alanına elle giriş de
mümkündür.

Motor başsız kullanılabilir:

```bash
metrajai init ./pilot.metrajai --name "Taziye Evi Pilot"
metrajai import-source ./pilot.metrajai ./kalip.dxf \
  --discipline structural --role kalip --floor "1. KAT" \
  --floor-kind typical --sheet-kind plan \
  --repeat-floor "2. KAT" --repeat-floor "3. KAT"
metrajai analyze ./pilot.metrajai
metrajai elements ./pilot.metrajai --status needs_review
metrajai review ./pilot.metrajai elm_... accepted \
  --reviewer "Mühendis" --reason "K01 kesiti" --set height_m=3.0
metrajai quantities ./pilot.metrajai
metrajai compare-revisions ./pilot.metrajai src_eski src_yeni
metrajai add-floor ./pilot.metrajai "2. KAT" --kind typical --order 2 \
  --elevation 3.20 --height 3.20
metrajai add-repeat ./pilot.metrajai src_... --scope template --template M1 \
  --floor-id flr_... --reviewer "Mühendis" --reason "Kat listesi kontrol edildi"
metrajai import-catalog ./pilot.metrajai ./birim-fiyat.xlsx \
  --name "2026 Birim Fiyatları" --year 2026 --version 1 --currency TRY
metrajai suggest-prices ./pilot.metrajai
metrajai backup ./pilot.metrajai --reason "Teklif öncesi"
```

Yerel API dış ağa bağlanmaz:

```bash
metrajai serve --host 127.0.0.1 --port 0 --token "oturum-anahtarı"
```

Ön yüz:

```bash
cd desktop
npm ci
npm run build
```

### IFC/DXF doğrulama laboratuvarı

IFC, masaüstü uygulamasının kullanıcı dosya formatı değildir. Yalnız geliştirme
doğrulamasında, açık lisanslı kaynaktan kontrollü DXF ve eleman bazlı altın sonuç
üretmek için kullanılır. Büyük kaynaklar ile türetilmiş dosyalar Git'e alınmaz.

```bash
.venv/bin/python -m pip install -e '.[reference]'
.venv/bin/python scripts/reference_dataset.py fetch --dataset pcert
.venv/bin/python scripts/reference_dataset.py build --dataset pcert
.venv/bin/python scripts/reference_dataset.py validate --dataset pcert
```

Komutlar `pcert`, `duplex` veya `all` veri setini kabul eder. Sabit commit, URL,
SHA-256, CC BY 4.0 lisansı ve atıf bilgisi `reference/manifest.json` içindedir.
Kaynak IFC'ler önce şema ve EXPRESS doğrulamasından geçer; doğrulama hatası, checksum
farkı veya zorunlu geometri üretim hatası kapıyı durdurur. Temiz DXF'lere ek olarak
kopya/döndürme/aynalama, iç içe blok, açık polyline, bulge, boşluklu hatch, uzak
geometri ve yanlış/eksik birim içeren kontrollü zor dosyalar oluşturulur.

PCERT küçük resmî model kapısıdır. İkinci kapı; dört katlı, mimari elemanlarla birlikte
`LoadBearing` kanıtlı duvar/döşeme, kiriş ve temel içeren buildingSMART Duplex
Apartment modelidir. Birleşik IFC'den mimari ve statik altın setler ayrı üretilir;
taşıyıcı niteliği olmayan duvar ve döşemeler statik setine alınmaz.

### macOS masaüstü penceresi

Tauri masaüstü uygulaması bir Xcode projesi değildir; Xcode/Command Line Tools macOS
derleme altyapısını sağlar. Rust kurulduktan sonra gerçek yerel pencereyi açmak için:

```bash
cd /Users/karakus/Documents/ChatGPT/MetrajAI
.venv/bin/python scripts/build_macos_ocr.py
.venv/bin/python scripts/package_sidecar.py  # motor değiştiğinde bir kez
npm --prefix desktop run tauri dev
```

Tauri derlemesi Rust araç zinciri gerektirir. `scripts/package_sidecar.py` Python
motorunu hedef platform sidecar adına paketler. `scripts/build_macos_ocr.py`, taranmış
PDF metnini cihazda okuyan Apple Vision yardımcısını derler. Excel raporu paket içindeki
Python çalışma zamanıyla çevrimdışı üretilebilir; geliştirme ortamında isteğe bağlı
artifact-tool doğrulama yolu da desteklenir. Bu pilot yalnız macOS için paketlenir.
Pilot `.app` yerel ad-hoc kimlikle imzalanır ve paket bütünlüğü doğrulanabilir; Apple
notarizasyonu ile Developer ID imzası ticari dağıtım aşamasına bırakılmıştır.

## Test kapsamı

Yeni test paketi aşağıdaki riskleri kapsar:

- mm/cm/m dönüşümü ve eksik `$INSUNITS` güvenlik kapısı,
- açık/kapalı polyline, bulge/yay, iç boşluklu hatch,
- döndürülmüş ve ölçeklenmiş blok,
- beton, kalıp ve donatı formülleri,
- onaysız elemanın kesin toplam dışında kalması,
- yeniden analizde mühendis kararının korunması,
- oturum anahtarı/CORS korumalı API akışı,
- bodrum/zemin/tip kat/çatı/temel/detay pafta sınıflandırması,
- yalnız kullanıcı tarafından yazılan hedef katlara tip-kat tekrarı,
- temel, perde, merdiven ve döşeme boşluğu güvenlik kapıları,
- kopya plan ve detay/donatı geometrisi ayıklama,
- tek DXF içindeki çoklu kalıp/donatı/kolon aplikasyon bölgelerinin kotlara ayrılması,
- doğrudan çizilmiş kirişlerde çift kenar + kesit etiketi eşleştirmesi,
- döşeme etiketi + çevreleyen gerçek kiriş yüzlerinden panel alanı,
- DXF başlığı ile fiziksel kesit kanıtı çeliştiğinde birim uyuşmazlığı engeli,
- kolon, kiriş, döşeme, perde, temel, merdiven ve boşluk revizyon karşılaştırması,
- sürümlü SQLite geçişi ve geçiş öncesi tutarlı proje yedeği,
- pafta/şablon/eleman kapsamlı onaylı tekrar ataması,
- XLS/XLSX mahal ve poz listeleri, PDF ölçek kapısı ve cihaz-içi OCR kanıtı,
- Decimal tabanlı fiyat eşleştirme, sıralı teklif oranları ve Excel uzlaşması.

Gerçek proje paftaları Git'e eklenmez. Taziye Evi altın referansı, mühendis onaylı
eleman ve manuel kontrol toplamları sağlandığında özel test alanında oluşturulacaktır.

## Durum

1.2 macOS pilotu, mimari/statik motoru kullanıcı paftalarından bağımsız ölçen açık
kaynak doğrulama laboratuvarını içerir. Şema ve EXPRESS doğrulaması temiz olan PCERT
ile Duplex modellerinden üretilen temiz ve kontrollü zor DXF'ler GlobalId düzeyinde
karşılaştırılır. IFC ve türetilmiş dosyalar uygulama paketine veya Git deposuna girmez.

Taziye Evi'nde gerçek kat planı bağlamı kopya/görünüş/detay bölgelerinden ayrılır;
"açılımlı pencere" açıklaması artık detay başlığı sayılmaz. DXF başlığındaki `mm` ile
fiziksel alan kanıtı çeliştiğinde motor `cm` önerir ve kesin mimari metrajı kilitler.
`cm` doğrulamasında ZK01-ZK10 ile 166,94 m² çizelge kanıtı korunur; çizelge ve plan
alanı arasındaki `%1` üzeri farklar otomatik düzeltilmeden mühendis incelemesinde kalır.
Defterdarlık uygulama, asma tavan ve mahal matrisi birlikte incelemeye alınır.
Sütçüler mimari kaynakları ve üç projenin mühendis altın referansları tamamlanmadan
mimari disiplin `reliable` durumuna geçirilmez. Mekanik ve elektrik kesin metrajı da
küçük ve karmaşık gerçek proje doğrulamasına kadar kilitli kalır.

Copyright © 2026. All rights reserved.
