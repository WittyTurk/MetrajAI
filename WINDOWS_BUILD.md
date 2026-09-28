# MetrajAI Windows x64

Windows paketi `MetrajAI_*_x64-setup.exe` biçiminde üretilir. Kurulum dosyası
başka bir Windows bilgisayara taşınabilir; WebView2 çevrimdışı kurulum paketi
içindedir. Windows SmartScreen, imzalanmamış iç pilot uygulaması için uyarı
gösterebilir.

## GitHub Actions

`.github/workflows/desktop.yml` içindeki `build-windows` işi Python motorunu
Windows üzerinde PyInstaller ile, masaüstü uygulamasını Tauri ile paketler.
Tamamlanan işin `MetrajAI-Windows-x64` artefaktından `.exe` dosyasını indirin.
Gerçek proje DXF/Excel dosyalarını depoya yüklemeyin.

## Windows bilgisayarda yerel derleme

Python 3.13, Node.js 22 ve Rust kurulu, internet erişimi olan Windows x64
bilgisayarda proje klasöründen şunu çalıştırın:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Betik testleri çalıştırır ve kurulum dosyasını `local-releases` klasörüne kopyalar.
Kaynak kodu taşıma paketi üretildiğinde gerçek paftalar ve proje veritabanları
içermez. Kurulum dosyasını harici diske kopyalayın; diğer Windows bilgisayarda
çalıştırıp MetrajAI'yi kurun. Bu bir *kurulum* paketidir, taşınabilir/kurulumsuz
uygulama değildir.
