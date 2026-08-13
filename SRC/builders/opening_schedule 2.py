Kaynak önceliği:
  1) Mahal listesi Excel/CSV
  2) Kapı detay tablosu (no, tip, W×H, adet, mahal)
  3) Pencere detay tablosu
  4) Detay DXF paftası (blok TEXT → 90x210)
  5) Plan DXF INSERT (konum; ölçü eksikse yukarıdan doldur)


from SRC.builders.door_builder_v2 import DoorBuilderV2
from SRC.builders.window_builder_v2 import WindowBuilderV2
from SRC.builders.opening_schedule import OpeningSchedule

sched = OpeningSchedule()
sched.load_mahal("INPUT/mahal_listesi.xlsx")
sched.load_door_schedule("INPUT/kapi_detay.xlsx")
sched.load_window_schedule("INPUT/pencere_detay.xlsx")
sched.load_detail_dxf("INPUT/kapi_detay.dxf", kind="door")
sched.load_detail_dxf("INPUT/pencere_detay.dxf", kind="window")

# Plan DXF'ten konum
doors = DoorBuilderV2(project=project).build()
windows = WindowBuilderV2(project=project).build()

# Detay + mahal ile ölçü doldur
doors = sched.apply_to_doors(doors)
windows = sched.apply_to_windows(windows)

# Plan yoksa sadece tablodan adet metrajı
# doors, windows = sched.openings_from_schedule_only()


Plan DXF          → kapı/pencere konumu
Detay Excel/DXF   → W × H, tip, adet
Mahal listesi     → oda no, kaplama (sıva/boya için)
        ↓
Metraj: adet × alan, mahal bazlı özet