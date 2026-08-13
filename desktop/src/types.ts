export type Discipline =
  | "structural"
  | "architectural"
  | "landscape"
  | "mechanical"
  | "electrical";
export type DrawingUnit = "mm" | "cm" | "m" | "unknown";
export type FloorKind =
  | "general"
  | "basement"
  | "ground"
  | "typical"
  | "roof"
  | "foundation"
  | "detail";
export type SheetKind =
  | "unspecified"
  | "plan"
  | "column_application"
  | "rebar_plan"
  | "foundation"
  | "detail"
  | "schedule"
  | "section"
  | "elevation"
  | "other";
export type ReviewStatus = "pending" | "needs_review" | "accepted" | "rejected";

export interface ProjectSummary {
  project: { project_id: string; name: string; updated_at: string };
  source_count: number;
  element_count: number;
  review_counts: Record<ReviewStatus, number>;
  quantity_count: number;
}

export interface SourceFile {
  id: string;
  original_name: string;
  discipline: Discipline;
  role: string;
  floor: string;
  floor_kind: FloorKind;
  sheet_kind: SheetKind;
  repeat_floors: string[];
  revision: string;
  drawing_unit: DrawingUnit;
  detected_unit: DrawingUnit;
  unit_confirmed: boolean;
  sha256: string;
}

export interface DetectedElement {
  id: string;
  source_id: string;
  discipline: Discipline;
  element_type: string;
  floor: string;
  layer: string;
  source_handle: string;
  geometry: {
    kind: string;
    points: [number, number][];
    bbox: [number, number, number, number] | null;
  };
  measurements: Record<string, number>;
  properties: Record<string, unknown>;
  required_inputs: string[];
  confidence: number;
  review_status: ReviewStatus;
  issues: string[];
}

export interface QuantityLine {
  id: string;
  element_id: string;
  discipline: Discipline;
  floor: string;
  category: string;
  description: string;
  unit: string;
  quantity: number;
  formula: string;
}

export interface AnalysisWarning {
  id: string;
  code: string;
  message: string;
  severity: "info" | "warning" | "error";
  element_id: string;
}

export interface AnalysisRun {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  element_count: number;
  warning_count: number;
}

export type RevisionChangeKind = "added" | "deleted" | "modified" | "unchanged";

export interface RevisionElementChange {
  kind: RevisionChangeKind;
  element_type: string;
  floor: string;
  label: string;
  old_element_id: string;
  new_element_id: string;
  old_measurements: Record<string, number>;
  new_measurements: Record<string, number>;
  changed_measurements: Record<string, [number | null, number | null]>;
  match_method: string;
  match_confidence: number;
}

export interface RevisionComparison {
  old_source_id: string;
  new_source_id: string;
  old_revision: string;
  new_revision: string;
  summary: Record<RevisionChangeKind, number>;
  changes: RevisionElementChange[];
  warnings: string[];
}
