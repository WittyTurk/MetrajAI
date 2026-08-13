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
└── logs/          # JSONL tanılama kayıtları
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

### macOS masaüstü penceresi

Tauri masaüstü uygulaması bir Xcode projesi değildir; Xcode/Command Line Tools macOS
derleme altyapısını sağlar. Rust kurulduktan sonra gerçek yerel pencereyi açmak için:

```bash
cd /Users/karakus/Documents/ChatGPT/MetrajAI
.venv/bin/python scripts/package_sidecar.py  # motor değiştiğinde bir kez
npm --prefix desktop run tauri dev
```

Tauri derlemesi Rust araç zinciri gerektirir. `scripts/package_sidecar.py` Python
motorunu hedef platform sidecar adına paketler. Excel çalışma zamanı özel dağıtım
paketinde `scripts/stage_report_runtime.py` ile Tauri kaynaklarına alınır. Windows ve
macOS paketleri ayrı GitHub Actions işlerinde üretilir.

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
- kolon, kiriş ve döşeme DXF revizyon karşılaştırması.

Gerçek proje paftaları Git'e eklenmez. Taziye Evi altın referansı, mühendis onaylı
eleman ve manuel kontrol toplamları sağlandığında özel test alanında oluşturulacaktır.

## Durum

Bu sürüm güvenilir çekirdeği, yerel API/CLI'ı, masaüstü pilot arayüzünü, kat/pafta
yönetimini, kullanıcı kontrollü tip-kat tekrarını, statik revizyon karşılaştırmasını
ve altı sayfalı izlenebilir Excel raporunu içerir. Defterdarlık güvenlik regresyonu
çalışmaktadır. Sütçüler'in tek DXF içindeki kotlu paftaları ayrıştırılır; kiriş ve
döşeme adayları gerçek çizgi/etiket kanıtıyla kat bazında mühendis onayına sunulur.
Altın referans tamamlanmadan bu adaylar otomatik olarak kesin metraja girmez.

Copyright © 2026. All rights reserved.
