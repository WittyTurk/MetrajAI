import { invoke } from "@tauri-apps/api/core";
import type {
  AnalysisRun,
  AnalysisWarning,
  ArchitecturalAssignment,
  ArchitecturalAssignmentKind,
  DetectedElement,
  Discipline,
  DrawingUnit,
  FloorKind,
  FloorDefinition,
  OfferScenario,
  PriceCatalog,
  PriceItem,
  PriceMapping,
  ProjectSummary,
  QuantityLine,
  ReviewStatus,
  RevisionComparison,
  RepeatAssignment,
  SheetKind,
  SourceFile,
  ValidationGate,
} from "./types";

interface EngineConnection {
  url: string | null;
  token: string;
  status: string;
}

export class EngineApi {
  private constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  static async connect(): Promise<EngineApi> {
    const developmentUrl = import.meta.env.VITE_ENGINE_URL as string | undefined;
    const developmentToken = import.meta.env.VITE_ENGINE_TOKEN as string | undefined;
    if (developmentUrl && developmentToken) {
      return new EngineApi(developmentUrl, developmentToken);
    }
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const connection = await invoke<EngineConnection>("engine_connection");
      if (connection.url) return new EngineApi(connection.url, connection.token);
      await new Promise((resolve) => window.setTimeout(resolve, 100));
    }
    throw new Error("Yerel hesap motoru başlatılamadı.");
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        "x-metrajai-token": this.token,
        ...init.headers,
      },
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new Error(payload.detail || `İstek başarısız (${response.status})`);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  createProject(path: string, name: string) {
    return this.request<ProjectSummary>("/projects", {
      method: "POST",
      body: JSON.stringify({ path, name }),
    });
  }

  openProject(path: string) {
    return this.request<ProjectSummary>("/projects/open", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
  }

  selectDirectory(title: string) {
    return this.request<{ path: string | null }>("/system/select-directory", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  selectFile(title: string) {
    return this.request<{ path: string | null }>("/system/select-file", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  project(projectId: string) {
    return this.request<ProjectSummary>(`/projects/${projectId}`);
  }

  sources(projectId: string) {
    return this.request<SourceFile[]>(`/projects/${projectId}/sources`);
  }

  importSource(
    projectId: string,
    payload: {
      path: string;
      discipline: Discipline;
      role: string;
      floor: string;
      floor_kind: FloorKind;
      sheet_kind: SheetKind;
      repeat_floors: string[];
      revision: string;
      drawing_unit: DrawingUnit;
    },
  ) {
    return this.request<SourceFile>(`/projects/${projectId}/sources`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  deleteSource(projectId: string, sourceId: string) {
    return this.request<{
      source_id: string;
      original_name: string;
      deleted_element_count: number;
      deleted_warning_count: number;
      project_copy_removed: boolean;
      project: ProjectSummary;
    }>(`/projects/${projectId}/sources/${sourceId}`, { method: "DELETE" });
  }

  confirmUnit(projectId: string, sourceId: string, unit: DrawingUnit) {
    return this.request<SourceFile>(`/projects/${projectId}/sources/${sourceId}/unit`, {
      method: "PATCH",
      body: JSON.stringify({ unit }),
    });
  }

  confirmCalibration(
    projectId: string,
    sourceId: string,
    scale: number,
    points: [[number, number], [number, number]],
  ) {
    return this.request<SourceFile>(`/projects/${projectId}/sources/${sourceId}/calibration`, {
      method: "PATCH",
      body: JSON.stringify({ scale, points }),
    });
  }

  floors(projectId: string) {
    return this.request<FloorDefinition[]>(`/projects/${projectId}/floors`);
  }

  createFloor(projectId: string, payload: Omit<FloorDefinition, "id">) {
    return this.request<FloorDefinition>(`/projects/${projectId}/floors`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  deleteFloor(projectId: string, floorId: string) {
    return this.request<void>(`/projects/${projectId}/floors/${floorId}`, {
      method: "DELETE",
    });
  }

  repeatAssignments(projectId: string) {
    return this.request<RepeatAssignment[]>(`/projects/${projectId}/repeat-assignments`);
  }

  createRepeatAssignment(
    projectId: string,
    payload: Omit<RepeatAssignment, "id">,
  ) {
    return this.request<RepeatAssignment>(`/projects/${projectId}/repeat-assignments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  deleteRepeatAssignment(projectId: string, assignmentId: string) {
    return this.request<void>(
      `/projects/${projectId}/repeat-assignments/${assignmentId}`,
      { method: "DELETE" },
    );
  }

  architecturalAssignments(projectId: string) {
    return this.request<ArchitecturalAssignment[]>(
      `/projects/${projectId}/architectural-assignments`,
    );
  }

  createArchitecturalAssignment(
    projectId: string,
    payload: {
      source_id: string;
      subject_element_id: string;
      kind: ArchitecturalAssignmentKind;
      target_element_ids: string[];
      values?: Record<string, string | number | boolean>;
      approved: boolean;
      reviewer: string;
      reason: string;
    },
  ) {
    return this.request<ArchitecturalAssignment>(
      `/projects/${projectId}/architectural-assignments`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  deleteArchitecturalAssignment(projectId: string, assignmentId: string) {
    return this.request<void>(
      `/projects/${projectId}/architectural-assignments/${assignmentId}`,
      { method: "DELETE" },
    );
  }

  updateSourceDiscipline(projectId: string, sourceId: string, discipline: Discipline) {
    return this.request<{
      source: SourceFile;
      cleared_element_count: number;
      project: ProjectSummary;
    }>(`/projects/${projectId}/sources/${sourceId}/discipline`, {
      method: "PATCH",
      body: JSON.stringify({ discipline }),
    });
  }

  updateSourceMapping(
    projectId: string,
    sourceId: string,
    payload: {
      role: string;
      floor: string;
      floor_kind: FloorKind;
      sheet_kind: SheetKind;
      repeat_floors: string[];
      revision: string;
    },
  ) {
    return this.request<{
      source: SourceFile;
      cleared_element_count: number;
      project: ProjectSummary;
    }>(`/projects/${projectId}/sources/${sourceId}/mapping`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  analyze(projectId: string) {
    return this.request<AnalysisRun>(`/projects/${projectId}/analyses`, {
      method: "POST",
      body: "{}",
    });
  }

  analysis(runId: string) {
    return this.request<AnalysisRun>(`/analyses/${runId}`);
  }

  cancelAnalysis(runId: string) {
    return this.request<AnalysisRun>(`/analyses/${runId}`, { method: "DELETE" });
  }

  elements(projectId: string) {
    return this.request<DetectedElement[]>(`/projects/${projectId}/elements`);
  }

  review(
    projectId: string,
    elementId: string,
    status: ReviewStatus,
    measurementOverrides: Record<string, number>,
    reason: string,
  ) {
    return this.request<DetectedElement>(
      `/projects/${projectId}/elements/${elementId}/review`,
      {
        method: "PATCH",
        body: JSON.stringify({
          status,
          reviewer: "Mühendis",
          reason,
          measurement_overrides: measurementOverrides,
        }),
      },
    );
  }

  reviewBulk(
    projectId: string,
    elementIds: string[],
    status: ReviewStatus,
    reason: string,
  ) {
    return this.request<{
      requested_count: number;
      reviewed_element_ids: string[];
      skipped: Record<string, string>;
    }>(`/projects/${projectId}/elements/review-bulk`, {
      method: "PATCH",
      body: JSON.stringify({
        element_ids: elementIds,
        status,
        reviewer: "Mühendis",
        reason,
      }),
    });
  }

  selectRebarRevision(projectId: string, sourceId: string, tableHandle: string) {
    return this.request<{
      source_id: string;
      revision_group: string;
      table_handle: string;
      selected_element_count: number;
      rejected_element_count: number;
      declared_total_kg: number;
    }>(`/projects/${projectId}/rebar-revision`, {
      method: "PATCH",
      body: JSON.stringify({ source_id: sourceId, table_handle: tableHandle }),
    });
  }

  compareRevisions(projectId: string, oldSourceId: string, newSourceId: string) {
    return this.request<RevisionComparison>(`/projects/${projectId}/revision-comparisons`, {
      method: "POST",
      body: JSON.stringify({ old_source_id: oldSourceId, new_source_id: newSourceId }),
    });
  }

  quantities(projectId: string) {
    return this.request<QuantityLine[]>(`/projects/${projectId}/quantities`);
  }

  priceCatalogs(projectId: string) {
    return this.request<PriceCatalog[]>(`/projects/${projectId}/price-catalogs`);
  }

  priceItems(projectId: string) {
    return this.request<PriceItem[]>(`/projects/${projectId}/price-items`);
  }

  importPriceCatalog(
    projectId: string,
    payload: {
      path: string;
      name: string;
      year: number;
      version: string;
      currency: string;
      is_official: boolean;
      source_url: string;
    },
  ) {
    return this.request<{ catalog: PriceCatalog; item_count: number }>(
      `/projects/${projectId}/price-catalogs/import`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  priceMappings(projectId: string) {
    return this.request<PriceMapping[]>(`/projects/${projectId}/price-mappings`);
  }

  suggestPriceMappings(projectId: string, catalogIds: string[] = []) {
    return this.request<PriceMapping[]>(`/projects/${projectId}/price-mappings/suggest`, {
      method: "POST",
      body: JSON.stringify({ catalog_ids: catalogIds, minimum_confidence: 0.55 }),
    });
  }

  putPriceMapping(
    projectId: string,
    payload: Omit<PriceMapping, "id">,
  ) {
    return this.request<PriceMapping>(`/projects/${projectId}/price-mappings`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  offerScenarios(projectId: string) {
    return this.request<OfferScenario[]>(`/projects/${projectId}/offer-scenarios`);
  }

  createOfferScenario(
    projectId: string,
    payload: Omit<OfferScenario, "id">,
  ) {
    return this.request<{
      scenario: OfferScenario;
      line_count: number;
      totals: Record<string, unknown>;
    }>(`/projects/${projectId}/offer-scenarios`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  validationGates(projectId: string) {
    return this.request<ValidationGate[]>(`/projects/${projectId}/validation-gates`);
  }

  warnings(projectId: string) {
    return this.request<AnalysisWarning[]>(`/projects/${projectId}/warnings`);
  }

  exportReport(projectId: string) {
    return this.request<{ path: string }>(`/projects/${projectId}/reports`, {
      method: "POST",
    });
  }
}
