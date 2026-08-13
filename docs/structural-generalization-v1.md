# Statik Genelleştirme V1 Doğrulama Raporu

Tarih: 13 Ağustos 2026

## Kapsam

Bu dilim aşağıdaki ürün davranışlarını uygular:

1. Bodrum, zemin, normal/tip kat, çatı, temel ve detay kat türleri.
2. Plan, kolon aplikasyonu, donatı planı, temel, detay, çizelge, kesit ve görünüş
   pafta rolleri.
3. Yalnız kullanıcının açıkça yazdığı hedef katlara tip-kat tekrarı.
4. Temel, perde, merdiven ve döşeme boşluğu adayları.
5. Aynı paftadaki kopya planların, detayların ve açık donatı kanıtı taşımayan
   çizgilerin fiziksel adetlerden çıkarılması.
6. İki kaynak revizyonu arasında eklenen, silinen ve ölçüsü değişen kolon, kiriş ve
   döşemelerin karşılaştırılması.

## Güvenlik politikaları

- Detay, kesit, görünüş ve açıklama paftaları fiziksel eleman adedi üretmez.
- Kolon aplikasyonu varsa aynı katın kalıp planındaki kolonlar ikinci kez üretilmez.
- Saf donatı planı betonarme konturları yeniden adetlendirmez.
- Tek bir çizgi kiriş veya perde kabul edilmez. Kiriş için kapalı fiziksel kontur ya
  da doğrulanmış plan ayrıştırıcısı; perde için ölçülebilir kapalı kalınlık gerekir.
- Donatı çizgisi, açık çap ve adet kanıtı olmadan miktar adayı değildir.
- Merdiven hacmi için toplam yükselme ve plak kalınlığı açıkça verilmelidir.
- Tip kat yalnız `normal/tip kat + plan` eşlemesinde ve kullanıcı hedef katları
  yazdığında çoğaltılır. Donatı çizelgesi/detayı çoğaltılmaz.
- Revizyon eşleşmesi önce benzersiz etiketi, ardından pafta genel kaymasını düzelten
  geometrik yakınlığı kullanır; düşük güven ayrı uyarıdır.

## Gerçek proje regresyonu

Sonuçlar kesin metraj değil, mühendis onayı bekleyen güvenli aday sayılarıdır.

| Proje | Önceki aday | V1 adayı | V1 dağılımı | Sonuç |
|---|---:|---:|---|---|
| Defterdarlık | 10.336 | 90 | 55 kolon, 15 kiriş, 20 merdiven | Detaylar ve ikinci kolon kaynağı ayrıştırıldı |
| Sütçüler V1 güvenlik filtresi | 46.247 | 68 | 46 kolon, 14 perde, 8 merdiven | 31.072 sahte donatı ve 13.675 sahte kiriş kaldırıldı |
| Sütçüler V2 çoklu pafta taslağı | 46.247 | 380 | 108 kolon, 162 kiriş, 98 döşeme, 8 perde, 4 merdiven | Gerçek kot/pafta ve etiketli çift kenar kanıtına bağlı inceleme adayları |
| Sütçüler V3 temel/boşluk/merdiven | 46.247 | 385 | 108 kolon, 162 kiriş, 98 döşeme, 8 perde, 1 radye, 8 merdiven | Kopya radye tekilleştirildi; açık boşluk ve merdiven etiketleri kanıta bağlandı |

Defterdarlık kaynak sahipliği:

- `SU.01 KALIP VE DONATI`: kiriş ve merdiven adayı.
- `SU.02 KOLON APLİKASYON`: kolonların yetkili kaynağı.
- `SU.03 KOLON DETAYLARI` ve `SU.04 KİRİŞ DETAYLARI`: referans; adet üretmez.

Sütçüler’de motor artık 22 ana statik pafta bölgesini kalıp, donatı ve kolon
aplikasyon rollerine ayırır. `+1.20`, `+5.20`, `+9.20`, `+13.20`, `+17.20` ve
`+21.20` kotları ayrı katlar olarak saklanır; aynı görünüm başka kata körlemesine
çoğaltılmaz.

- Kirişler `KİRİŞ` katmanındaki iki çizilmiş kenarın, kesit genişliği kadar aralığı
  ve `KB… (40/80)` benzeri etiketi birlikte doğrulamasıyla oluşturulur.
- Döşemeler `D…` etiketi, açık kalınlık yazısı ve etiketi dört yönde çevreleyen
  gerçek kiriş yüzleriyle oluşturulur.
- Aynı kat/etiket/ölçüye sahip üç çevrilmiş plan kopyası ikinci kez sayılmamıştır.
- Pafta görevine bağlanamayan 337 detay veya yanlış-pafta adayı çıkarılmıştır.
- 50 iç kirişte iki döşeme yüzü, 43 dış kirişte bir döşeme ve dış cephe kanıtıyla
  kalıp alanı hesaplanmıştır. Diğer 69 kirişin kalıp alanı eksik bilgi olarak kalır.
- Aynı 20 köşeli radye sınırının taşınmış üç çizimi tek adayda birleştirilmiş;
  1.558,832 m² alan ve 80 cm kalınlık açık geometri/yazı kanıtıyla bağlanmıştır.
- Dört döşemede kapalı `BOSLUK` geometrisinden toplam 7,80 m² düşülmüştür.
- M1–M4 için dört açık `-3.30 → +1.20` ve dört tip merdiven etiketi ayrıştırılmıştır.
  Plan alanı/yatay koşu/plak kalınlığı eksik olanlar ve kat tekrarı tanımsız tip
  merdivenler kesin metraja alınmaz.
- Donatı hâlâ açık çizelge/geometri kanıtı olmadan hesaplanmaz.

DXF başlığı birimi `mm` olarak bildirse de çizilmiş 30/40 cm kiriş kenar aralıkları
ve kesit etiketleri `cm` ile uyuşmaktadır. Motor bu çelişkide sıfır eleman üretip
birim onayı ister; kullanıcı `cm` seçmeden Sütçüler miktarı oluşmaz. 385 satırın
tamamı kesin metraj değil, mühendis onay taslağıdır.

## Otomatik doğrulama

- Ruff: başarılı.
- mypy: başarılı.
- pytest: 40 test başarılı.
- React/TypeScript üretim derlemesi: başarılı.
- Taziye (88), Defterdarlık (90) ve Sütçüler (385) pilot doğrulama kapısı: başarılı.

## Sonraki mühendislik kapısı

Sütçüler için her kotta manuel olarak işaretlenmiş en az bir kalıp planı gerekir.
Mevcut 162 kiriş ve 98 döşeme taslağı bu referansla satır satır karşılaştırılacak;
uzunluk/alan yüzde 1 sınırını geçmeden proje “güvenilir” işaretlenmeyecektir.
Merdivende sıradaki kapı, M1–M4 plan konturlarından plan alanı/yatay koşuyu ve açık
kesit kanıtından plak kalınlığını bağlamak; ardından dört tip merdivenin uygulanacağı
kat aralıklarını kullanıcı kararıyla çoğaltmaktır.
