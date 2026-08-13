# -*- coding: utf-8 -*-
"""
Half-Edge Topology - Dikdörtgen Örnek
Basit bir oda (A-B-C-D) üzerinden next/prev/face oluşumu
"""

from dataclasses import dataclass, field


# -------------------------------------------------
# 1) Temel veri yapıları
# -------------------------------------------------

@dataclass
class Vertex:
    id: int
    x: float
    y: float
    incident_edges: list = field(default_factory=list)  # bu köşeden çıkan half-edge id'leri


@dataclass
class HalfEdge:
    id: int
    origin: int          # başlangıç vertex id
    twin: int = None     # ters yönlü half-edge id
    next: int = None     # aynı yüzdeki sonraki half-edge
    prev: int = None     # aynı yüzdeki önceki half-edge
    face: int = None     # ait olduğu oda


@dataclass
class Face:
    id: int
    edge_ids: list = field(default_factory=list)  # sınır half-edge'leri


# -------------------------------------------------
# 2) Dikdörtgen geometri
# -------------------------------------------------
#        2
#   A -------- B
#   |          |
#  1|          |3
#   |          |
#   D -------- C
#        4
#
# A(0,1)  B(2,1)  C(2,0)  D(0,0)

vertices = {
    1: Vertex(1, 0.0, 1.0),  # A
    2: Vertex(2, 2.0, 1.0),  # B
    3: Vertex(3, 2.0, 0.0),  # C
    4: Vertex(4, 0.0, 0.0),  # D
}

# Her duvar için iki half-edge (gidiş + dönüş)
half_edges = {
    # Dışa bakan yönler (örnek)
    1: HalfEdge(1, origin=1),  # A → B
    2: HalfEdge(2, origin=2),  # B → A  (1'in twin'i)

    3: HalfEdge(3, origin=2),  # B → C
    4: HalfEdge(4, origin=3),  # C → B  (3'ün twin'i)

    5: HalfEdge(5, origin=3),  # C → D
    6: HalfEdge(6, origin=4),  # D → C  (5'in twin'i)

    7: HalfEdge(7, origin=4),  # D → A
    8: HalfEdge(8, origin=1),  # A → D  (7'nin twin'i)
}

# Twin bağları
half_edges[1].twin = 2
half_edges[2].twin = 1
half_edges[3].twin = 4
half_edges[4].twin = 3
half_edges[5].twin = 6
half_edges[6].twin = 5
half_edges[7].twin = 8
half_edges[8].twin = 7


# -------------------------------------------------
# 3) Her vertex'e incident edge'leri yaz
# -------------------------------------------------
# Bir vertex'in incident_edges listesi:
# o vertex'ten ÇIKAN half-edge'lerdir.

vertices[1].incident_edges = [1, 8]  # A'dan çıkan: A→B ve A→D
vertices[2].incident_edges = [2, 3]  # B'den çıkan: B→A ve B→C
vertices[3].incident_edges = [4, 5]  # C'den çıkan: C→B ve C→D
vertices[4].incident_edges = [6, 7]  # D'den çıkan: D→C ve D→A


# -------------------------------------------------
# 4) next bağlarını kur (iç oda, saat yönünün tersi)
# -------------------------------------------------
# İç yüz: A → B → C → D → A
# Half-edge'ler: 1 (A→B), 3 (B→C), 5 (C→D), 7 (D→A)

half_edges[1].next = 3   # A→B  den sonra  B→C
half_edges[3].next = 5   # B→C  den sonra  C→D
half_edges[5].next = 7   # C→D  den sonra  D→A
half_edges[7].next = 1   # D→A  den sonra  A→B

# prev = tersi
half_edges[3].prev = 1
half_edges[5].prev = 3
half_edges[7].prev = 5
half_edges[1].prev = 7


# -------------------------------------------------
# 5) Face (oda) oluştur
# -------------------------------------------------
face = Face(id=1, edge_ids=[1, 3, 5, 7])

for eid in face.edge_ids:
    half_edges[eid].face = face.id


# -------------------------------------------------
# 6) Dolaşma testi
# -------------------------------------------------
print("=" * 40)
print("HALF-EDGE DOLAŞMA (İç Oda)")
print("=" * 40)

start = half_edges[1]
current = start
steps = 0

while True:
    v = vertices[current.origin]
    print(f"  Edge {current.id}: Vertex {v.id} ({v.x}, {v.y})")

    current = half_edges[current.next]
    steps += 1

    if current.id == start.id or steps > 10:
        break

print(f"\nKapalı döngü: {steps} adımda geri dönüldü → Oda bulundu")
print(f"Face id = {face.id}")
print(f"Edge listesi = {face.edge_ids}")