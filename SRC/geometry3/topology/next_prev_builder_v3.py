from SRC.geometry3.direction.axis_system import AxisSystem

print(">>> NEXT PREV BUILDER V3 LOADED <<<")

class NextPrevBuilderV3:

    # ---------------------------------------------------------

    def __init__(self, project):

        self.project = project

        print(">>> NextPrevBuilderV3 __init__ <<<")

    # ---------------------------------------------------------

    def build(self):

        
        print()
        print("=" * 40)
        print("NEXT PREV BUILDER V3")
        print("=" * 40)

        self.sort_incident_edges()

        self.classify_vertices()

        self.assign_next()

        # self.assign_prev()

        print()
        print("Next assignment finished.")

        return

    	
 
    # ---------------------------------------------------------
    # AXIS DIRECTION (X-Y)
    # ---------------------------------------------------------

    def get_axis(self, angle):

        a = angle % 180.0

        if a < 45 or a >= 135:
            return "X"

        else:
            return "Y"
    # ---------------------------------------------------------
    def assign_next(self):

        print("### ASSIGN_NEXT START ###")
    

        mesh = self.project.mesh
        

        assigned = 0

       
        for edge in mesh.half_edges.values():

            twin = mesh.get_half_edge(edge.twin)

            if twin is None:
                continue

            vertex = mesh.get_vertex(twin.origin)

            if vertex is None:
                continue

            
            edge.next = self.find_next_edge(edge, vertex)

            
            if edge.next is not None:
                assigned += 1

        print()
        print("Assigned next :", assigned)

        count_next = 0

        for e in mesh.half_edges.values():

            if e.next is not None:
                count_next += 1

                  

    # ---------------------------------------------------------
    def classify_vertices(self):

        mesh = self.project.mesh

        self.vertex_type = {}

        for vertex in mesh.vertices.values():

            degree = len(vertex.incident_edges)

            if degree == 1:
                self.vertex_type[vertex.id] = "END"

            elif degree == 2:
                self.vertex_type[vertex.id] = "STRAIGHT"

            elif degree == 3:
                self.vertex_type[vertex.id] = "T"

            elif degree == 4:
                self.vertex_type[vertex.id] = "CROSS"

            else:
                self.vertex_type[vertex.id] = "COMPLEX"
    # ---------------------------------------------------------
    def sort_incident_edges(self):

        mesh = self.project.mesh

        for vertex in mesh.vertices.values():

            vertex.incident_edges.sort(
                key=lambda edge_id: mesh.get_half_edge(edge_id).angle
            )
    
    # ---------------------------------------------------------
    
    def assign_prev(self):

        print("ENTER ASSIGN PREV")
        mesh = self.project.mesh
   
        count = 0

        for edge in mesh.half_edges.values():

            if edge.next is None:
                continue


            nxt = mesh.get_half_edge(edge.next)

            if nxt is None:
                continue
            if nxt.prev is not None:

                print(
                    "PREV CONFLICT",
                    "target=", nxt.id,
                    "old=", nxt.prev,
                    "new=", edge.id
                )

            else:

                nxt.prev = edge.id

                count += 1


        print("Assigned prev :", count)

        print("EXIT ASSIGN PREV")

        # ---------- ikinci geçiş ----------
        for edge in mesh.half_edges.values():

            if edge.next is None:
                continue

            next_edge = mesh.get_half_edge(edge.next)

            next_edge.prev = edge.id
        
        print()
        print("Assigned prev :", count)      
    
    # ---------------------------------------------------------

    def find_next_edge(
        self,
        edge,
        vertex
    ):
 
        print(
            "FIND NEXT",
            "edge=", edge.id,
            "vertex=", vertex.id,
            "incident=", vertex.incident_edges
    )

        mesh = self.project.mesh

        candidates = []

        for eid in vertex.incident_edges:

            if eid == edge.id:
                continue

            if eid == edge.twin:
                continue

            e = mesh.get_half_edge(eid)

            if e is None:
                continue

            candidates.append(eid)

      
        if len(candidates) == 0:
            

            print(
                "NO CANDIDATE DETAIL",
                "edge=", edge.id,
                "vertex=", vertex.id,
                "incident=", vertex.incident_edges,
                "count=", len(vertex.incident_edges),
                "twin=", edge.twin
            )

            print(
                "END CHECK",
                "edge=", edge.id,
                "vertex=", vertex.id,
                "degree=", len(vertex.incident_edges)
            )

            return None

        incoming_axis = self.get_axis(edge.angle)

        same_axis = []

        for eid in candidates:

            candidate = mesh.get_half_edge(eid)

            if candidate is None:
                continue

            if self.get_axis(candidate.angle) == incoming_axis:
                same_axis.append(eid)


        if same_axis:
   
            candidates = same_axis
  
       
        degree = len(candidates)


        if degree == 1:
            return candidates[0]
        
        elif degree == 2:
            return self.solve_straight(edge, vertex)

        elif degree == 3:
            return self.solve_t(edge, vertex)

        elif degree == 4:
            return self.solve_cross(edge, vertex)

        else:
            return self.solve_complex(edge, vertex)
            
   
    # ---------------------------------------------------------

    def solve_end(self, edge, vertex):
        mesh = self.project.mesh

        twin = mesh.get_half_edge(edge.twin)

        print(
            "END VERTEX",
            "edge=", edge.id,
            "vertex=", vertex.id,
            "incident=", vertex.incident_edges,
            "twin=", twin.id
        )


        return None

    # ---------------------------------------------------------

    def solve_straight(self, edge, vertex):

        
        mesh = self.project.mesh

        twin = mesh.get_half_edge(edge.twin)

        
        candidates = []

        for edge_id in vertex.incident_edges:
  
            if edge_id == edge.id:
                continue

            if edge_id == twin.id:
                continue

            candidate = mesh.get_half_edge(edge_id)

            if candidate is not None:
                candidates.append(candidate)
        
        print(
            "STRAIGHT",
            "edge=", edge.id,
            "vertex=", vertex.id,
            "candidates=", [c.id for c in candidates]
        )


        print(
            "STRAIGHT DETAIL",
            "incoming=",
            edge.id,
            "angle=",
            edge.angle,
            "candidates=",
            [
                (c.id, c.angle)
                for c in candidates
            ]
        )

        
        return candidates[0].id
    # ---------------------------------------------------------

    def solve_t(self, edge, vertex):

        mesh = self.project.mesh

        twin = mesh.get_half_edge(edge.twin)

        target = (twin.angle + 180.0) % 360.0

        best_edge = None
        best_diff = 360.0

        for edge_id in vertex.incident_edges:

            if edge_id == twin.id:
                continue

            candidate = mesh.get_half_edge(edge_id)

            diff = abs(
                ((candidate.angle - target + 180.0) % 360.0) - 180.0
            )

            if diff < best_diff:
                best_diff = diff
                best_edge = edge_id

        return best_edge
    # ---------------------------------------------------------

    def solve_cross(self, edge, vertex):

        mesh = self.project.mesh

        twin = mesh.get_half_edge(edge.twin)

        if twin is None:
            return None


        candidates = []

        for edge_id in vertex.incident_edges:

            if edge_id == edge.id:
                continue

            if edge_id == twin.id:
                continue

            candidate = mesh.get_half_edge(edge_id)

            if candidate is not None:
                candidates.append(candidate)


        if not candidates:
            return None


        # açıya göre sırala
        candidates.sort(
            key=lambda e: e.angle
        )


        # gelen yönün sol tarafındaki dönüşü seç
        incoming = (edge.angle + 180.0) % 360.0


        best = None
        best_turn = 360.0


        for candidate in candidates:

            turn = (
                candidate.angle - incoming
            ) % 360.0


            if turn < best_turn:
   
                best_turn = turn
                best = candidate


        if best is not None:
            return best.id


        return candidates[0].id
      
    
    # ---------------------------------------------------------

    def solve_complex(self, edge, vertex):

        mesh = self.project.mesh

        twin = mesh.get_half_edge(edge.twin)

        if twin is None:
            return None


        candidates = []

        print()
        print("COMPLEX DEBUG")
        print("edge =", edge.id)
        print("vertex =", vertex.id)

        for eid in vertex.incident_edges:

            e = mesh.get_half_edge(eid)

            print(
                "candidate",
                eid,
                "angle=",
                e.angle,
                "origin=",
                e.origin,
                "twin=",
                e.twin
            )
        

        for edge_id in vertex.incident_edges:

            if edge_id == edge.id:
                continue

            if edge_id == twin.id:
                continue

            candidate = mesh.get_half_edge(edge_id)

            if candidate is not None:
                candidates.append(candidate)

        # aynı açılı kenarları tekilleştir
        unique = {}

        for c in candidates:

            key = round(c.angle, 6)

            if key not in unique:

                unique[key] = c

            else:

                if c.id < unique[key].id:
                    unique[key] = c


        candidates = list(unique.values())

        print(
            "AFTER UNIQUE",
            [c.id for c in candidates]
        )


        if not candidates:
            return None


        incoming = (edge.angle + 180.0) % 360.0


        best = None
        best_turn = 360.0


        for candidate in candidates:

            turn = (candidate.angle - incoming) % 360.0

            if turn < best_turn:

                best_turn = turn
                best = candidate


        if best:
            return best.id


        return candidates[0].id