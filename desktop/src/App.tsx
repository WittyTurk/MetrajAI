import { useEffect, useMemo, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import {
  AlertTriangle,
  BadgeDollarSign,
  Boxes,
  Check,
  ChevronRight,
  CircleStop,
  FilePlus2,
  FileSpreadsheet,
  Focus,
  FolderOpen,
  Gauge,
  GitCompareArrows,
  LoaderCircle,
  Layers3,
  Play,
  Ruler,
  Repeat2,
  ShieldCheck,
  Trash2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { EngineApi } from "./api";
import type {
  AnalysisRun,
  AnalysisWarning,
  DetectedElement,
  Discipline,
  DrawingUnit,
  FloorDefinition,
  FloorKind,
  OfferScenario,
  PriceCatalog,
  PriceItem,
  PriceMapping,
  ProjectSummary,
  QuantityLine,
  RevisionChangeKind,
  RevisionComparison,
  RepeatAssignment,
  ReviewStatus,
  SheetKind,
  SourceFile,
  ValidationGate,
} from "./types";

type View = "sources" | "floors" | "mapping" | "review" | "quantities" | "commercial" | "revisions";

const DISCIPLINES: { value: Discipline; label: string }[] = [
  { value: "structural", label: "Statik" },
  { value: "architectural", label: "Mimari" },
  { value: "landscape", label: "Çevre düzenleme" },
  { value: "mechanical", label: "Mekanik" },
  { value: "electrical", label: "Elektrik" },
];

const FLOOR_KINDS: { value: FloorKind; label: string }[] = [
  { value: "general", label: "Genel / tek kat" },
  { value: "basement", label: "Bodrum" },
  { value: "ground", label: "Zemin" },
  { value: "typical", label: "Normal / tip kat" },
  { value: "roof", label: "Çatı" },
  { value: "foundation", label: "Temel" },
  { value: "detail", label: "Detay (kat değil)" },
];

const SHEET_KINDS: { value: SheetKind; label: string }[] = [
  { value: "unspecified", label: "Seçilmedi" },
  { value: "plan", label: "Uygulama / kalıp planı" },
  { value: "column_application", label: "Kolon aplikasyonu" },
  { value: "rebar_plan", label: "Donatı planı" },
  { value: "foundation", label: "Temel planı" },
  { value: "detail", label: "Detay paftası" },
  { value: "schedule", label: "Çizelge" },
  { value: "section", label: "Kesit" },
  { value: "elevation", label: "Görünüş" },
  { value: "other", label: "Diğer / açıklama" },
];

const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Onay bekliyor",
  needs_review: "Eksik bilgi",
  accepted: "Onaylandı",
  rejected: "Hariç tutuldu",
};

const MEASUREMENT_LABELS: Record<string, string> = {
  width_m: "Genişlik (m)",
  depth_m: "Derinlik (m)",
  height_m: "Yükseklik (m)",
  length_m: "Uzunluk (m)",
  thickness_m: "Kalınlık (m)",
  area_m2: "Alan (m²)",
  perimeter_m: "Çevre (m)",
  count: "Adet",
  diameter_mm: "Çap (mm)",
  formwork_area_m2: "Kiriş kalıp alanı (m²)",
  plan_area_m2: "İzdüşüm alanı (m²)",
  horizontal_run_m: "Yatay koşu (m)",
  total_rise_m: "Toplam yükselme (m)",
  waist_thickness_m: "Merdiven plak kalınlığı (m)",
  step_volume_m3: "Basamak beton hacmi (m³)",
  landing_volume_m3: "Sahanlık beton hacmi (m³)",
  side_formwork_m2: "Yan kalıp alanı (m²)",
  riser_formwork_m2: "Rıht kalıp alanı (m²)",
  landing_formwork_m2: "Sahanlık alt kalıbı (m²)",
};

function App() {
  const [api, setApi] = useState<EngineApi | null>(null);
  const [engineError, setEngineError] = useState("");
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [sources, setSources] = useState<SourceFile[]>([]);
  const [elements, setElements] = useState<DetectedElement[]>([]);
  const [quantities, setQuantities] = useState<QuantityLine[]>([]);
  const [warnings, setWarnings] = useState<AnalysisWarning[]>([]);
  const [floors, setFloors] = useState<FloorDefinition[]>([]);
  const [repeatAssignments, setRepeatAssignments] = useState<RepeatAssignment[]>([]);
  const [priceCatalogs, setPriceCatalogs] = useState<PriceCatalog[]>([]);
  const [priceItems, setPriceItems] = useState<PriceItem[]>([]);
  const [priceMappings, setPriceMappings] = useState<PriceMapping[]>([]);
  const [offerScenarios, setOfferScenarios] = useState<OfferScenario[]>([]);
  const [validationGates, setValidationGates] = useState<ValidationGate[]>([]);
  const [view, setView] = useState<View>("sources");
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    EngineApi.connect().then(setApi).catch((error: Error) => setEngineError(error.message));
  }, []);

  async function refresh(projectId = project?.project.project_id) {
    if (!api || !projectId) return;
    const [
      summary, nextSources, nextElements, nextQuantities, nextWarnings,
      nextFloors, nextRepeats, nextCatalogs, nextPriceItems, nextMappings,
      nextOffers, nextGates,
    ] =
      await Promise.all([
        api.project(projectId),
        api.sources(projectId),
        api.elements(projectId),
        api.quantities(projectId),
        api.warnings(projectId),
        api.floors(projectId),
        api.repeatAssignments(projectId),
        api.priceCatalogs(projectId),
        api.priceItems(projectId),
        api.priceMappings(projectId),
        api.offerScenarios(projectId),
        api.validationGates(projectId),
      ]);
    setProject(summary);
    setSources(nextSources);
    setElements(nextElements);
    setQuantities(nextQuantities);
    setWarnings(nextWarnings);
    setFloors(nextFloors);
    setRepeatAssignments(nextRepeats);
    setPriceCatalogs(nextCatalogs);
    setPriceItems(nextPriceItems);
    setPriceMappings(nextMappings);
    setOfferScenarios(nextOffers);
    setValidationGates(nextGates);
  }

  async function startAnalysis() {
    if (!api || !project) return;
    try {
      const started = await api.analyze(project.project.project_id);
      setRun(started);
      setView("review");
      let current = started;
      while (["queued", "running"].includes(current.status)) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        current = await api.analysis(started.id);
        setRun(current);
      }
      await refresh();
      if (current.status === "failed") setMessage(current.message);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  if (!api) {
    return <EngineGate error={engineError} />;
  }

  if (!project) {
    return (
      <ProjectStart
        api={api}
        onReady={(summary) => {
          setProject(summary);
          setView("sources");
          void refresh(summary.project.project_id);
        }}
      />
    );
  }

  const pendingCount =
    (project.review_counts.pending ?? 0) + (project.review_counts.needs_review ?? 0);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Ruler size={21} /></div>
          <div><strong>MetrajAI</strong><span>Mühendis kontrollü metraj</span></div>
        </div>
        <div className="project-chip">
          <span>Aktif proje</span>
          <strong>{project.project.name}</strong>
          <small>{sources.length} kaynak · {elements.length} eleman</small>
        </div>
        <nav className="workflow-nav" aria-label="İş akışı">
          <NavItem index="01" label="Kaynak dosyalar" active={view === "sources"} complete={sources.length > 0} onClick={() => setView("sources")} />
          <NavItem index="02" label="Kat ve tekrarlar" active={view === "floors"} complete={floors.length > 0} onClick={() => setView("floors")} />
          <NavItem index="03" label="Birim ve eşleme" active={view === "mapping"} complete={sources.length > 0 && sources.every((source) => source.source_format !== "dxf" || source.unit_confirmed || source.detected_unit !== "unknown")} onClick={() => setView("mapping")} />
          <NavItem index="04" label="Tespit ve onay" active={view === "review"} complete={elements.length > 0 && pendingCount === 0} onClick={() => setView("review")} />
          <NavItem index="05" label="Kesin metraj" active={view === "quantities"} complete={quantities.length > 0} onClick={() => setView("quantities")} />
          <NavItem index="06" label="Fiyat ve teklif" active={view === "commercial"} complete={priceMappings.some((item) => item.status === "approved")} onClick={() => setView("commercial")} />
          <NavItem index="07" label="Revizyon karşılaştır" active={view === "revisions"} complete={false} onClick={() => setView("revisions")} />
        </nav>
        <div className="safety-note">
          <ShieldCheck size={18} />
          <div><strong>Güvenli hesap</strong><span>Onaysız elemanlar toplam dışındadır.</span></div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">YEREL PROJE · {project.project.project_id.slice(-8).toUpperCase()}</span>
            <h1>{viewTitle(view)}</h1>
          </div>
          <div className="topbar-actions">
            {run && ["queued", "running"].includes(run.status) && (
              <div className="run-progress">
                <LoaderCircle className="spin" size={17} />
                <span>{run.message}</span>
                <b>{Math.round(run.progress * 100)}%</b>
              </div>
            )}
            <button className="button primary" disabled={sources.length === 0 || run?.status === "running"} onClick={() => void startAnalysis()}>
              <Play size={16} fill="currentColor" /> Analizi başlat
            </button>
          </div>
        </header>

        {message && <div className="banner error"><AlertTriangle size={18} /><span>{message}</span><button onClick={() => setMessage("")}><X size={16} /></button></div>}

        {view === "sources" && <SourcesView api={api} project={project} sources={sources} onChanged={() => void refresh()} onNext={() => setView("floors")} onError={setMessage} />}
        {view === "floors" && <FloorsView api={api} projectId={project.project.project_id} sources={sources} elements={elements} floors={floors} repeatAssignments={repeatAssignments} onChanged={() => void refresh()} onError={setMessage} onNext={() => setView("mapping")} />}
        {view === "mapping" && <MappingView api={api} projectId={project.project.project_id} sources={sources} onChanged={() => void refresh()} onNext={() => void startAnalysis()} />}
        {view === "review" && <ReviewView api={api} projectId={project.project.project_id} elements={elements} warnings={warnings} onChanged={() => void refresh()} onNext={() => setView("quantities")} />}
        {view === "quantities" && <QuantitiesView api={api} projectId={project.project.project_id} quantities={quantities} pendingCount={pendingCount} onMessage={setMessage} />}
        {view === "commercial" && <CommercialView api={api} projectId={project.project.project_id} quantities={quantities} catalogs={priceCatalogs} priceItems={priceItems} mappings={priceMappings} scenarios={offerScenarios} gates={validationGates} onChanged={() => void refresh()} onError={setMessage} />}
        {view === "revisions" && <RevisionComparisonView api={api} projectId={project.project.project_id} sources={sources} />}
      </main>
    </div>
  );
}

function EngineGate({ error }: { error: string }) {
  return (
    <div className="gate">
      <div className="gate-card">
        <div className="brand-mark large"><Ruler size={28} /></div>
        <p className="eyebrow">METRAJAI YEREL MOTOR</p>
        <h1>{error ? "Motor başlatılamadı" : "Hesap motoru hazırlanıyor"}</h1>
        <p>{error || "Dosyalarınız cihazdan çıkmadan güvenli çalışma alanı kuruluyor."}</p>
        {!error && <div className="loading-track"><span /></div>}
      </div>
    </div>
  );
}

function ProjectStart({ api, onReady }: { api: EngineApi; onReady: (project: ProjectSummary) => void }) {
  const [mode, setMode] = useState<"create" | "open">("create");
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function chooseFolder() {
    const title = mode === "create" ? "Yeni proje klasörünü seçin" : "MetrajAI proje klasörünü seçin";
    setError("");
    try {
      const selected = isTauri()
        ? await open({ directory: true, multiple: false, title })
        : (await api.selectDirectory(title)).path;
      if (typeof selected === "string") setPath(selected);
    } catch (dialogError) {
      setError((dialogError as Error).message);
    }
  }

  async function submit() {
    if (!path || (mode === "create" && !name.trim())) return;
    setBusy(true);
    setError("");
    try {
      onReady(mode === "create" ? await api.createProject(path, name.trim()) : await api.openProject(path));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="start-screen">
      <section className="start-intro">
        <div className="brand light"><div className="brand-mark"><Ruler size={21} /></div><strong>MetrajAI</strong></div>
        <div>
          <span className="eyebrow">MÜHENDİS KONTROLLÜ · YEREL · İZLENEBİLİR</span>
          <h1>Çizimden kesin metraja,<br />her karar görünür.</h1>
          <p>DXF tespitlerini kaynağına kadar izleyin, eksikleri doğrulayın ve yalnız onaylı elemanlardan metraj üretin.</p>
        </div>
        <div className="intro-metrics"><span><b>%100</b> yerel veri</span><span><b>0</b> görünmez varsayım</span><span><b>1</b> denetlenebilir kayıt</span></div>
      </section>
      <section className="start-form">
        <div className="mode-switch"><button className={mode === "create" ? "active" : ""} onClick={() => setMode("create")}>Yeni proje</button><button className={mode === "open" ? "active" : ""} onClick={() => setMode("open")}>Projeyi aç</button></div>
        <h2>{mode === "create" ? "Çalışma alanı oluşturun" : "Çalışma alanına dönün"}</h2>
        <p>{mode === "create" ? "Kaynaklar, kararlar ve çıktılar seçtiğiniz klasörde birlikte saklanır." : "manifest.json içeren mevcut bir MetrajAI klasörü seçin."}</p>
        {mode === "create" && <label>Proje adı<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Örn. Taziye Evi Pilot" /></label>}
        <label>Proje klasörü<div className="path-picker"><input value={path} onChange={(event) => setPath(event.target.value)} placeholder="Bir klasör seçin veya yolu yazın" /><button onClick={() => void chooseFolder()}><FolderOpen size={17} /></button></div></label>
        {error && <div className="inline-error">{error}</div>}
        <button className="button primary wide" onClick={() => void submit()} disabled={busy || !path || (mode === "create" && !name.trim())}>{busy ? <LoaderCircle className="spin" size={17} /> : <ChevronRight size={17} />}{mode === "create" ? "Projeyi oluştur" : "Projeyi aç"}</button>
      </section>
    </div>
  );
}

function NavItem({ index, label, active, complete, onClick }: { index: string; label: string; active: boolean; complete: boolean; onClick: () => void }) {
  return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}><span className="nav-index">{complete ? <Check size={14} /> : index}</span><span>{label}</span><ChevronRight size={15} /></button>;
}

function SourcesView({ api, project, sources, onChanged, onNext, onError }: { api: EngineApi; project: ProjectSummary; sources: SourceFile[]; onChanged: () => void; onNext: () => void; onError: (message: string) => void }) {
  const [path, setPath] = useState("");
  const [discipline, setDiscipline] = useState<Discipline>("structural");
  const [role, setRole] = useState("kalip");
  const [floor, setFloor] = useState("GENEL");
  const [floorKind, setFloorKind] = useState<FloorKind>("general");
  const [sheetKind, setSheetKind] = useState<SheetKind>("plan");
  const [revision, setRevision] = useState("");
  const [unit, setUnit] = useState<DrawingUnit>("unknown");
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  async function chooseFile() {
    try {
      const selected = isTauri()
        ? await open({ multiple: false, filters: [{ name: "Proje kaynakları", extensions: ["dxf", "xlsx", "xls", "pdf"] }] })
        : (await api.selectFile("DXF, Excel veya PDF kaynak dosyasını seçin")).path;
      if (typeof selected === "string") setPath(selected);
    } catch (dialogError) {
      onError((dialogError as Error).message);
    }
  }

  async function addSource() {
    if (!path || !role.trim()) return;
    setBusy(true);
    try {
      await api.importSource(project.project.project_id, {
        path,
        discipline,
        role,
        floor,
        floor_kind: floorKind,
        sheet_kind: sheetKind,
        repeat_floors: [],
        revision,
        drawing_unit: unit,
      });
      setPath("");
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeSource(source: SourceFile) {
    const confirmed = window.confirm(
      `“${source.original_name}” proje kaynaklarından silinsin mi?\n\n` +
      "Bu kaynaktan üretilen elemanlar, kararlar ve metrajlar da silinir. Özgün DXF dosyanıza dokunulmaz.",
    );
    if (!confirmed) return;
    setDeletingId(source.id);
    try {
      await api.deleteSource(project.project.project_id, source.id);
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setDeletingId(null);
    }
  }

  async function changeDiscipline(source: SourceFile, nextDiscipline: Discipline) {
    if (nextDiscipline === source.discipline) return;
    setUpdatingId(source.id);
    try {
      await api.updateSourceDiscipline(
        project.project.project_id,
        source.id,
        nextDiscipline,
      );
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="content-grid source-layout">
      <section className="panel source-form-panel">
        <div className="section-heading"><div><span className="eyebrow">KAYNAK EKLE</span><h2>Değiştirilmeyen pafta</h2></div><FilePlus2 size={21} /></div>
        <label>DXF, Excel veya PDF<div className="path-picker"><input value={path} onChange={(event) => setPath(event.target.value)} placeholder="Dosya seçin veya yolu yazın" /><button onClick={() => void chooseFile()}><FolderOpen size={17} /></button></div></label>
        <div className="form-row"><label>Disiplin<select value={discipline} onChange={(event) => setDiscipline(event.target.value as Discipline)}>{DISCIPLINES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Pafta rolü<input value={role} onChange={(event) => setRole(event.target.value)} placeholder="kalip / detay / mahal" /></label></div>
        <div className="form-row"><label>Kat türü<select value={floorKind} onChange={(event) => setFloorKind(event.target.value as FloorKind)}>{FLOOR_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Pafta türü<select value={sheetKind} onChange={(event) => setSheetKind(event.target.value as SheetKind)}>{SHEET_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label></div>
        <div className="form-row three"><label>Kat<input value={floor} onChange={(event) => setFloor(event.target.value)} /></label><label>Revizyon<input value={revision} onChange={(event) => setRevision(event.target.value)} placeholder="R00" /></label><label>Çizim birimi<select value={unit} onChange={(event) => setUnit(event.target.value as DrawingUnit)}><option value="unknown">DXF'ten oku</option><option value="mm">mm</option><option value="cm">cm</option><option value="m">m</option></select></label></div>
        <small className="field-help">Kat tekrarları sonraki ekranda M1–M4 gibi eleman/şablon bazında ve mühendis onayıyla tanımlanır.</small>
        <button className="button primary wide" disabled={!path || busy} onClick={() => void addSource()}>{busy ? <LoaderCircle className="spin" size={17} /> : <FilePlus2 size={17} />}Kaynağı projeye al</button>
        <p className="hint">Dosya SHA-256 kimliğiyle proje klasörüne kopyalanır; özgün dosya değiştirilmez.</p>
      </section>
      <section className="panel source-list-panel">
        <div className="section-heading"><div><span className="eyebrow">PROJE KAYNAKLARI</span><h2>{sources.length} dosya hazır</h2></div><span className="count-badge">{sources.length}</span></div>
        <div className="source-list">
          {sources.length === 0 ? <EmptyState icon={<Boxes />} title="Henüz kaynak yok" detail="İlk DXF paftasını veya referans çizelgesini ekleyin." /> : sources.map((source) => <div className="source-row" key={source.id}><div className={`file-icon ${source.discipline}`}>{source.original_name.split(".").pop()?.toUpperCase()}</div><div className="source-main"><strong>{source.original_name}</strong><span>{disciplineLabel(source.discipline)} · {sheetKindLabel(source.sheet_kind)} · {floorKindLabel(source.floor_kind)} / {source.floor}</span><small>SHA {source.sha256.slice(0, 12)}</small></div><div className="source-actions"><select className="source-discipline" aria-label={`${source.original_name} disiplini`} value={source.discipline} disabled={updatingId === source.id} onChange={(event) => void changeDiscipline(source, event.target.value as Discipline)}>{DISCIPLINES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><div className={`unit-pill ${sourceStatusReady(source) ? "confirmed" : ""}`}>{sourceStatusLabel(source)}</div><button className="source-delete" aria-label={`${source.original_name} kaynağını sil`} title="Kaynağı sil" disabled={deletingId === source.id} onClick={() => void removeSource(source)}>{deletingId === source.id ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}</button></div></div>)}
        </div>
        <button className="button secondary next-button" disabled={sources.length === 0} onClick={onNext}>Kat ve tekrarlara geç <ChevronRight size={16} /></button>
      </section>
    </div>
  );
}

function FloorsView({ api, projectId, sources, elements, floors, repeatAssignments, onChanged, onError, onNext }: { api: EngineApi; projectId: string; sources: SourceFile[]; elements: DetectedElement[]; floors: FloorDefinition[]; repeatAssignments: RepeatAssignment[]; onChanged: () => void; onError: (message: string) => void; onNext: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<FloorKind>("ground");
  const [elevation, setElevation] = useState("0");
  const [height, setHeight] = useState("3");
  const [sourceId, setSourceId] = useState(sources[0]?.id ?? "");
  const [scope, setScope] = useState<"source" | "template">("template");
  const [templateLabel, setTemplateLabel] = useState("");
  const [targetFloorIds, setTargetFloorIds] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!sourceId && sources[0]) setSourceId(sources[0].id);
  }, [sourceId, sources]);
  const detectedLabels = useMemo(() => Array.from(new Set(elements.filter((item) => item.source_id === sourceId).map((item) => String(item.properties.element_label ?? "").trim()).filter(Boolean))).sort(), [elements, sourceId]);

  async function addFloor() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.createFloor(projectId, {
        name: name.trim(), kind, order: floors.length,
        elevation_m: elevation === "" ? null : Number(elevation),
        height_m: height === "" ? null : Number(height),
      });
      setName("");
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addRepeat() {
    if (!sourceId || targetFloorIds.length === 0 || reason.trim().length < 3) return;
    setBusy(true);
    try {
      await api.createRepeatAssignment(projectId, {
        source_id: sourceId,
        scope,
        target_floor_ids: targetFloorIds,
        element_ids: [],
        template_label: scope === "template" ? templateLabel.trim() : "",
        approved: true,
        reviewer: "Mühendis",
        reason: reason.trim(),
      });
      setTemplateLabel("");
      setReason("");
      setTargetFloorIds([]);
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="stack">
    <section className="callout"><Layers3 size={22} /><div><strong>Katlar bir kez tanımlanır, tekrarlar eleman bazında onaylanır</strong><p>M1–M4 gibi şablonlar yalnız seçilen hedef katlarda oluşur; kaynak dosyanın tamamı kendiliğinden çoğalmaz.</p></div><span className={floors.length ? "safe" : "risk"}>{floors.length ? `${floors.length} kat` : "Kat gerekli"}</span></section>
    <div className="content-grid source-layout">
      <section className="panel source-form-panel"><div className="section-heading"><div><span className="eyebrow">KAT TANIMI</span><h2>Kot ve yükseklik</h2></div><Layers3 size={21} /></div><label>Kat adı<input value={name} onChange={(event) => setName(event.target.value)} placeholder="ZEMİN KAT" /></label><div className="form-row"><label>Kat türü<select value={kind} onChange={(event) => setKind(event.target.value as FloorKind)}>{FLOOR_KINDS.filter((item) => item.value !== "detail" && item.value !== "general").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Sıra<input type="number" value={floors.length} readOnly /></label></div><div className="form-row"><label>Kot (m)<input type="number" step="0.01" value={elevation} onChange={(event) => setElevation(event.target.value)} /></label><label>Kat yüksekliği (m)<input type="number" min="0" step="0.01" value={height} onChange={(event) => setHeight(event.target.value)} /></label></div><button className="button primary wide" disabled={busy || !name.trim()} onClick={() => void addFloor()}><FilePlus2 size={16} /> Katı ekle</button></section>
      <section className="panel source-list-panel"><div className="section-heading"><div><span className="eyebrow">KAT LİSTESİ</span><h2>{floors.length} kat tanımlı</h2></div></div><div className="source-list">{floors.map((floor) => <div className="source-row" key={floor.id}><div className="file-icon structural">{floor.order + 1}</div><div className="source-main"><strong>{floor.name}</strong><span>{floorKindLabel(floor.kind)} · Kot {floor.elevation_m ?? "—"} m</span><small>Yükseklik {floor.height_m ?? "eksik"} m</small></div><button className="source-delete" title="Katı sil" onClick={async () => { try { await api.deleteFloor(projectId, floor.id); onChanged(); } catch (error) { onError((error as Error).message); } }}><Trash2 size={16} /></button></div>)}{floors.length === 0 && <EmptyState icon={<Layers3 />} title="Kat tanımı yok" detail="Önce bodrum, zemin, normal, çatı ve temel katlarını ekleyin." />}</div></section>
    </div>
    <section className="panel"><div className="section-heading"><div><span className="eyebrow">ONAYLI TEKRAR</span><h2>Şablon veya kaynak kapsamı</h2></div><Repeat2 size={21} /></div><div className="repeat-form"><label>Kaynak<select value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">Seçiniz</option>{sources.filter((item) => item.source_format === "dxf").map((source) => <option key={source.id} value={source.id}>{source.original_name}</option>)}</select></label><label>Kapsam<select value={scope} onChange={(event) => setScope(event.target.value as "source" | "template")}><option value="template">Eleman şablonu</option><option value="source">Kaynağın fiziksel elemanları</option></select></label><label>Şablon etiketi<input value={templateLabel} disabled={scope !== "template"} onChange={(event) => setTemplateLabel(event.target.value)} list="detected-template-labels" placeholder="M1" /><datalist id="detected-template-labels">{detectedLabels.map((label) => <option key={label} value={label} />)}</datalist></label><label>Hedef katlar<select multiple value={targetFloorIds} onChange={(event) => setTargetFloorIds(Array.from(event.target.selectedOptions, (option) => option.value))}>{floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}</select></label><label className="repeat-reason">Mühendis gerekçesi<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Tip kat merdiven detayı ve kat listesi kontrol edildi" /></label><button className="button primary" disabled={busy || !sourceId || targetFloorIds.length === 0 || reason.trim().length < 3 || (scope === "template" && !templateLabel.trim())} onClick={() => void addRepeat()}><Check size={16} /> Onaylı tekrar ekle</button></div><div className="repeat-list">{repeatAssignments.map((item) => <div className="repeat-row" key={item.id}><span className="status-tag accepted">Onaylı</span><div><strong>{item.scope === "template" ? item.template_label : "Kaynak kapsamı"}</strong><small>{sources.find((source) => source.id === item.source_id)?.original_name ?? item.source_id}</small></div><span>{item.target_floor_ids.map((id) => floors.find((floor) => floor.id === id)?.name ?? id).join(", ")}</span><small>{item.reason}</small><button className="source-delete" onClick={async () => { try { await api.deleteRepeatAssignment(projectId, item.id); onChanged(); } catch (error) { onError((error as Error).message); } }}><Trash2 size={15} /></button></div>)}</div></section>
    <div className="footer-action"><p>Analiz, yalnız burada onaylanmış tekrar kararlarını uygular.</p><button className="button primary" disabled={floors.length === 0} onClick={onNext}>Birim ve eşlemeye geç <ChevronRight size={16} /></button></div>
  </div>;
}

function MappingView({ api, projectId, sources, onChanged, onNext }: { api: EngineApi; projectId: string; sources: SourceFile[]; onChanged: () => void; onNext: () => void }) {
  const dxfSources = sources.filter((source) => source.source_format === "dxf");
  const pdfSources = sources.filter((source) => source.source_format === "pdf");
  const unresolvedUnits = dxfSources.filter((source) => !source.unit_confirmed && source.detected_unit === "unknown" && !(source.discipline === "structural" && ["detail", "section", "elevation", "other"].includes(source.sheet_kind)));
  const unresolvedSheets = dxfSources.filter((source) => source.discipline === "structural" && source.sheet_kind === "unspecified");
  const unresolvedPdf = pdfSources.filter((source) => source.calibration_status !== "confirmed");
  const unresolvedCount = unresolvedUnits.length + unresolvedSheets.length + unresolvedPdf.length;
  return <div className="stack">
    <section className="callout"><Gauge size={22} /><div><strong>Pafta ve birim güvenlik kapısı</strong><p>DXF birimi ve pafta görevi açıkça eşlenir. Detay/kesit paftaları fiziksel eleman adedine girmez.</p></div><span className={unresolvedCount ? "risk" : "safe"}>{unresolvedCount ? `${unresolvedCount} karar gerekli` : "Hazır"}</span></section>
    <section className="panel">
      <div className="section-heading"><div><span className="eyebrow">KAT VE PAFTA YÖNETİMİ</span><h2>Her dosyanın tek ve açık görevi</h2></div></div>
      <div className="sheet-mapping-list">{sources.map((source) => <SourceMappingEditor key={source.id} api={api} projectId={projectId} source={source} onChanged={onChanged} />)}</div>
    </section>
    {dxfSources.length > 0 && <section className="panel"><div className="section-heading"><div><span className="eyebrow">BİRİM DOĞRULAMA</span><h2>DXF kaynakları metre standardına dönüştürülür</h2></div></div><div className="mapping-table"><div className="mapping-head"><span>Kaynak</span><span>DXF algısı</span><span>Kullanılacak birim</span><span>Durum</span></div>{dxfSources.map((source) => <div className="mapping-row" key={source.id}><div><strong>{source.original_name}</strong><small>{source.floor} · {source.role}</small></div><code>{source.detected_unit}</code><select value={source.unit_confirmed ? source.drawing_unit : source.detected_unit} onChange={async (event) => { const selected = event.target.value as DrawingUnit; if (selected !== "unknown") { await api.confirmUnit(projectId, source.id, selected); onChanged(); } }}><option value="unknown">Seçiniz</option><option value="mm">Milimetre</option><option value="cm">Santimetre</option><option value="m">Metre</option></select><span className={`status-dot-label ${source.unit_confirmed || source.detected_unit !== "unknown" ? "ok" : "warn"}`}><i />{source.unit_confirmed ? "Onaylandı" : source.detected_unit !== "unknown" ? "DXF değeri" : "Bekliyor"}</span></div>)}</div></section>}
    {pdfSources.length > 0 && <section className="panel"><div className="section-heading"><div><span className="eyebrow">PDF KALİBRASYONU</span><h2>İki noktalı ölçek doğrulaması</h2></div></div><div className="sheet-mapping-list">{pdfSources.map((source) => <PdfCalibrationEditor key={source.id} api={api} projectId={projectId} source={source} onChanged={onChanged} />)}</div></section>}
    <div className="footer-action"><p>Yalnız onaylı eleman/şablon tekrarları uygulanır; çizelge ve detaylar körlemesine çoğaltılmaz.</p><button className="button primary" disabled={unresolvedCount > 0} onClick={onNext}><Play size={16} fill="currentColor" /> Tespitleri oluştur</button></div>
  </div>;
}

function PdfCalibrationEditor({ api, projectId, source, onChanged }: { api: EngineApi; projectId: string; source: SourceFile; onChanged: () => void }) {
  const [pageDistance, setPageDistance] = useState("100");
  const [realDistance, setRealDistance] = useState("1");
  const [error, setError] = useState("");
  async function confirm() {
    const page = Number(pageDistance);
    const real = Number(realDistance);
    if (!(page > 0 && real > 0)) return;
    try {
      await api.confirmCalibration(projectId, source.id, real / page, [[0, 0], [page, 0]]);
      setError("");
      onChanged();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }
  return <div className="sheet-mapping-card"><div className="sheet-mapping-title"><div><strong>{source.original_name}</strong><small>Kalibrasyon: {source.calibration_status}</small></div><span className={`sheet-kind-pill ${source.calibration_status === "confirmed" ? "plan" : "detail"}`}>{source.calibration_status === "confirmed" ? "Onaylandı" : "Ölçek gerekli"}</span></div><div className="sheet-mapping-grid"><label>PDF ölçüsü<input type="number" min="0" value={pageDistance} onChange={(event) => setPageDistance(event.target.value)} /></label><label>Gerçek mesafe (m)<input type="number" min="0" value={realDistance} onChange={(event) => setRealDistance(event.target.value)} /></label><div className="sheet-mapping-footer"><small>{error || "Aynı iki nokta arasındaki PDF ve gerçek mesafeyi girin."}</small><button className="button secondary" onClick={() => void confirm()}><Check size={15} /> Ölçeği onayla</button></div></div></div>;
}

function SourceMappingEditor({ api, projectId, source, onChanged }: { api: EngineApi; projectId: string; source: SourceFile; onChanged: () => void }) {
  const [role, setRole] = useState(source.role);
  const [floor, setFloor] = useState(source.floor);
  const [floorKind, setFloorKind] = useState<FloorKind>(source.floor_kind);
  const [sheetKind, setSheetKind] = useState<SheetKind>(source.sheet_kind);
  const [revision, setRevision] = useState(source.revision);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setRole(source.role);
    setFloor(source.floor);
    setFloorKind(source.floor_kind);
    setSheetKind(source.sheet_kind);
    setRevision(source.revision);
  }, [source]);

  async function save() {
    if (!role.trim() || !floor.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      const result = await api.updateSourceMapping(projectId, source.id, {
        role,
        floor,
        floor_kind: floorKind,
        sheet_kind: sheetKind,
        repeat_floors: [],
        revision,
      });
      setMessage(result.cleared_element_count ? `${result.cleared_element_count} eski tespit temizlendi; analiz gerekli.` : "Eşleme kaydedildi.");
      onChanged();
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <div className="sheet-mapping-card">
    <div className="sheet-mapping-title"><div><strong>{source.original_name}</strong><small>{disciplineLabel(source.discipline)} · SHA {source.sha256.slice(0, 10)}</small></div><span className={`sheet-kind-pill ${sheetKind}`}>{sheetKindLabel(sheetKind)}</span></div>
    <div className="sheet-mapping-grid">
      <label>Pafta türü<select value={sheetKind} onChange={(event) => setSheetKind(event.target.value as SheetKind)}>{SHEET_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>Kat türü<select value={floorKind} onChange={(event) => setFloorKind(event.target.value as FloorKind)}>{FLOOR_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>Kat adı<input value={floor} onChange={(event) => setFloor(event.target.value)} /></label>
      <label>Pafta rolü<input value={role} onChange={(event) => setRole(event.target.value)} /></label>
      <label>Revizyon<input value={revision} onChange={(event) => setRevision(event.target.value)} placeholder="R00" /></label>
      <label className="repeat-field">Tekrar politikası<input value="Kat ve tekrarlar ekranından yönetilir" disabled /><small>Şablon/eleman seçimi ve mühendis gerekçesi zorunludur.</small></label>
    </div>
    <div className="sheet-mapping-footer"><small className={message.includes("hata") ? "risk" : ""}>{message}</small><button className="button secondary" disabled={busy || !role.trim() || !floor.trim()} onClick={() => void save()}>{busy ? <LoaderCircle className="spin" size={15} /> : <Check size={15} />} Eşlemeyi kaydet</button></div>
  </div>;
}

interface RebarRevisionCandidate {
  label: string;
  table_handle: string;
  declared_total_kg: number;
  calculated_total_kg: number;
  row_count: number;
  scope_labels: string[];
}

function ReviewView({ api, projectId, elements, warnings, onChanged, onNext }: { api: EngineApi; projectId: string; elements: DetectedElement[]; warnings: AnalysisWarning[]; onChanged: () => void; onNext: () => void }) {
  const [filter, setFilter] = useState<ReviewStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [floorFilter, setFloorFilter] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bulkReason, setBulkReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [resultMessage, setResultMessage] = useState("");
  const elementTypes = Array.from(new Set(elements.map((item) => item.element_type)));
  const floors = Array.from(new Set(elements.map((item) => item.floor))).sort((a, b) => a.localeCompare(b, "tr"));
  const floorElements = floorFilter === "all" ? elements : elements.filter((item) => item.floor === floorFilter);
  const filtered = elements.filter((item) =>
    (filter === "all" || item.review_status === filter)
    && (typeFilter === "all" || item.element_type === typeFilter)
    && (floorFilter === "all" || item.floor === floorFilter)
  );
  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0];
  const pending = floorElements.filter((item) => ["pending", "needs_review"].includes(item.review_status)).length;
  const bulkEligible = filtered.filter((item) =>
    ["pending", "needs_review"].includes(item.review_status)
    && item.required_inputs.every((key) => (item.measurements[key] ?? 0) > 0)
    && !item.issues.some((issue) => issue.startsWith("blocking:"))
  );
  const scopeElements = floorElements.filter((item) =>
    item.review_status !== "rejected" && (typeFilter === "all" || item.element_type === typeFilter)
  );
  const previewTotals = quantityPreviewTotals(scopeElements);
  const approvedTotals = quantityPreviewTotals(
    scopeElements.filter((item) => item.review_status === "accepted"),
  );
  const rebarElement = elements.find((item) =>
    item.element_type === "rebar" && Array.isArray(item.properties.revision_candidates)
  );
  const revisionCandidates = (rebarElement?.properties.revision_candidates ?? []) as RebarRevisionCandidate[];
  const selectedRevisionHandle = elements.find((item) =>
    item.element_type === "rebar" && item.properties.revision_selected === true
  )?.properties.table_handle as string | undefined;

  useEffect(() => {
    if (filtered[0] && !filtered.some((item) => item.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  async function bulkAccept() {
    if (typeFilter === "all" || bulkEligible.length === 0 || bulkReason.trim().length < 3) return;
    const label = elementTypeLabel(typeFilter);
    if (!window.confirm(`${bulkEligible.length} ${label.toLocaleLowerCase("tr-TR")} topluca onaylanacak. Devam edilsin mi?`)) return;
    setBusy(true);
    try {
      const result = await api.reviewBulk(
        projectId,
        bulkEligible.map((item) => item.id),
        "accepted",
        bulkReason.trim(),
      );
      const skippedCount = Object.keys(result.skipped).length;
      setResultMessage(`${result.reviewed_element_ids.length} eleman onaylandı${skippedCount ? `, ${skippedCount} güvenlik nedeniyle atlandı` : ""}.`);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function chooseRevision(candidate: RebarRevisionCandidate) {
    if (!rebarElement || selectedRevisionHandle === candidate.table_handle) return;
    const message = `Revizyon ${candidate.label} (${formatQuantity(candidate.declared_total_kg)} kg) güncel donatı çizelgesi olarak seçilsin mi? Diğer adayın satırları hariç tutulacak.`;
    if (!window.confirm(message)) return;
    setBusy(true);
    try {
      const result = await api.selectRebarRevision(
        projectId,
        rebarElement.source_id,
        candidate.table_handle,
      );
      setResultMessage(`Revizyon ${candidate.label} seçildi; ${result.selected_element_count} donatı pozu onaya açıldı.`);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return <div className="review-layout">
    <section className="panel preview-panel">
      <div className="section-heading compact"><div><span className="eyebrow">DXF ÖNİZLEME</span><h2>Kaynak geometrisi</h2></div><span className="count-badge">{floorElements.length}</span></div>
      <GeometryPreview elements={floorElements} selectedId={selected?.id} onSelect={setSelectedId} />
      <div className="legend"><span><i className="accepted" />Onaylı</span><span><i className="pending" />Bekliyor</span><span><i className="needs" />Eksik</span><span><i className="rejected" />Hariç</span></div>
      {warnings.length > 0 && <div className="warning-stack">{warnings.map((warning) => <div key={warning.id} className={`mini-warning ${warning.severity}`}><AlertTriangle size={15} /><span>{warning.message}</span></div>)}</div>}
    </section>
    <section className="panel review-panel">
      <div className="review-toolbar">
        <div><span className="eyebrow">MÜHENDİS ONAYI</span><h2>{pending} karar bekliyor</h2></div>
        <div className="review-filters">
          <select value={floorFilter} onChange={(event) => { setFloorFilter(event.target.value); setFilter("all"); }}><option value="all">Tüm katlar</option>{floors.map((floor) => <option value={floor} key={floor}>{floor}</option>)}</select>
          <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setFilter("all"); }}><option value="all">Tüm türler</option>{elementTypes.map((type) => <option value={type} key={type}>{elementTypeLabel(type)}</option>)}</select>
          <select value={filter} onChange={(event) => setFilter(event.target.value as ReviewStatus | "all")}><option value="all">Tüm durumlar</option><option value="needs_review">Eksik bilgi</option><option value="pending">Onay bekliyor</option><option value="accepted">Onaylı</option><option value="rejected">Hariç</option></select>
        </div>
      </div>
      {revisionCandidates.length > 1 && (typeFilter === "all" || typeFilter === "rebar") && <div className="revision-picker"><div><strong>Donatı revizyonunu seçin</strong><small>Seçim yapılmadan donatı kesin toplama giremez.</small></div>{revisionCandidates.map((candidate) => <button key={candidate.table_handle} className={selectedRevisionHandle === candidate.table_handle ? "selected" : ""} disabled={busy} onClick={() => void chooseRevision(candidate)}><span>Revizyon {candidate.label}</span><strong>{formatQuantity(candidate.declared_total_kg)} kg</strong><small>{candidate.row_count} poz · formül {formatQuantity(candidate.calculated_total_kg)} kg</small></button>)}</div>}
      <div className="review-subtotals">{previewTotals.map((total) => { const approved = approvedTotals.find((item) => item.key === total.key)?.value ?? 0; return <div key={total.key}><span>{total.category}</span><strong>{formatQuantity(approved)} <small>{total.unit}</small></strong><small>Aday: {formatQuantity(total.value)} {total.unit}</small></div>; })}{previewTotals.length === 0 && <div><span>Ara toplam</span><strong>—</strong><small>Hesaplanabilir eleman yok</small></div>}</div>
      {typeFilter !== "all" && <div className="comparison-wrap"><div className="comparison-head"><strong>{elementTypeLabel(typeFilter)} karşılaştırması</strong><span>{filtered.length} satır</span></div><div className="comparison-table"><div className="comparison-row head"><span>Eleman</span><span>Ölçüler</span><span>Hesap adayı</span><span>Durum</span></div>{filtered.map((element) => <button className={`comparison-row ${selected?.id === element.id ? "selected" : ""}`} key={element.id} onClick={() => setSelectedId(element.id)}><span><strong>{String(element.properties.element_label || elementTypeLabel(element.element_type))}</strong><small>{element.source_handle}</small></span><span>{measurementSummary(element)}</span><span>{quantitySummary(element)}</span><span className={`table-status ${element.review_status}`}>{STATUS_LABELS[element.review_status]}</span></button>)}</div></div>}
      <div className="element-strip">{filtered.map((element) => <button key={element.id} className={selected?.id === element.id ? "selected" : ""} onClick={() => setSelectedId(element.id)}><span className={`status-pin ${element.review_status}`} /><strong>{elementTypeLabel(element.element_type)}{element.properties.element_label ? ` · ${String(element.properties.element_label)}` : ""}</strong><small>{element.floor} · {element.layer}</small></button>)}</div>
      {typeFilter !== "all" && <div className="bulk-review"><div><strong>Güvenli toplu onay</strong><small>{bulkEligible.length} görünür eleman uygun; eksik/engelli satırlar dahil edilmez.</small></div><input value={bulkReason} onChange={(event) => setBulkReason(event.target.value)} placeholder="Pafta ve kontrol gerekçesi…" /><button className="button primary" disabled={busy || bulkEligible.length === 0 || bulkReason.trim().length < 3} onClick={() => void bulkAccept()}><Check size={16} /> {bulkEligible.length} elemanı onayla</button></div>}
      {resultMessage && <div className="inline-result"><Check size={15} />{resultMessage}</div>}
      {selected ? <ElementReview api={api} projectId={projectId} element={selected} onChanged={onChanged} /> : <EmptyState icon={<Ruler />} title="Bu filtrede tespit yok" detail="Tür veya durum filtresini değiştirin." />}
      <div className="review-footer"><span>{elements.filter((item) => item.review_status === "accepted").length} onaylı eleman kesin metraja girecek.</span><button className="button secondary" onClick={onNext}>Kesin metrajı gör <ChevronRight size={16} /></button></div>
    </section>
  </div>;
}

function quantityPreview(element: DetectedElement) {
  const value = (key: string) => element.measurements[key] ?? 0;
  if (element.required_inputs.some((key) => value(key) <= 0)) return [];
  if (element.element_type === "column") return [
    { category: "Beton", unit: "m³", value: value("width_m") * value("depth_m") * value("height_m") },
    { category: "Kalıp · brüt", unit: "m²", value: 2 * (value("width_m") + value("depth_m")) * value("height_m") },
  ];
  if (element.element_type === "beam") return [
    { category: "Beton", unit: "m³", value: value("width_m") * value("height_m") * value("length_m") },
    { category: "Kalıp", unit: "m²", value: value("formwork_area_m2") },
  ];
  if (element.element_type === "slab") return [
    { category: "Beton", unit: "m³", value: value("area_m2") * value("thickness_m") },
    { category: "Kalıp", unit: "m²", value: value("area_m2") },
  ];
  if (element.element_type === "rebar" && element.properties.revision_selected !== false) return [
    { category: "Donatı · net", unit: "kg", value: value("length_m") * value("count") * value("diameter_mm") ** 2 / 162 },
  ];
  return [];
}

function quantityPreviewTotals(elements: DetectedElement[]) {
  const totals = new Map<string, { key: string; category: string; unit: string; value: number }>();
  elements.forEach((element) => quantityPreview(element).forEach((line) => {
    const key = `${line.category}|${line.unit}`;
    const current = totals.get(key) ?? { key, category: line.category, unit: line.unit, value: 0 };
    current.value += line.value;
    totals.set(key, current);
  }));
  return Array.from(totals.values());
}

function measurementSummary(element: DetectedElement) {
  const m = element.measurements;
  if (element.element_type === "column") return `${formatQuantity(m.width_m)} × ${formatQuantity(m.depth_m)} × h ${formatQuantity(m.height_m)} m`;
  if (element.element_type === "beam") return `L ${formatQuantity(m.length_m)} · ${formatQuantity(m.width_m)} × ${formatQuantity(m.height_m)} m`;
  if (element.element_type === "slab") return `${formatQuantity(m.area_m2)} m² · d ${formatQuantity(m.thickness_m)} m`;
  if (element.element_type === "rebar") return `${formatQuantity(m.count)}Ø${formatQuantity(m.diameter_mm)} · ${formatQuantity(m.length_m)} m`;
  return Object.entries(m).slice(0, 3).map(([key, value]) => `${measurementLabel(element.element_type, key)} ${formatQuantity(value)}`).join(" · ");
}

function quantitySummary(element: DetectedElement) {
  const lines = quantityPreview(element);
  return lines.length ? lines.map((line) => `${line.category}: ${formatQuantity(line.value)} ${line.unit}`).join(" · ") : "Hesap dışında";
}

function ElementReview({ api, projectId, element, onChanged }: { api: EngineApi; projectId: string; element: DetectedElement; onChanged: () => void }) {
  const keys = element.required_inputs;
  const [values, setValues] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setValues(Object.fromEntries(keys.map((key) => [key, element.measurements[key]?.toString() ?? ""]))); setReason(""); }, [element.id]);
  async function decide(status: ReviewStatus) {
    setBusy(true);
    try {
      const overrides = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== "").map(([key, value]) => [key, Number(value)]));
      await api.review(projectId, element.id, status, overrides, reason || (status === "accepted" ? "Geometri ve ölçüler kontrol edildi" : "Mühendis kararı"));
      onChanged();
    } finally { setBusy(false); }
  }
  const missing = element.required_inputs.filter((key) => !values[key] || Number(values[key]) <= 0);
  const blocking = element.issues.filter((issue) => issue.startsWith("blocking:"));
  const heightEvidence = element.properties.height_evidence as {
    source_name: string;
    floor_label: string;
    lower_level_m: number;
    upper_level_m: number;
    height_m: number;
    block_name: string;
  } | undefined;
  const levelHeightEvidence = element.properties.level_height_evidence as {
    lower_level_m: number;
    upper_level_m: number;
    method: string;
  } | undefined;
  const beamEvidence = element.properties.beam_section_evidence as {
    element_label: string;
    section_text: string;
    section_width_m: number;
    section_height_m: number;
    annotation_handle: string;
  } | undefined;
  const lengthEvidence = element.properties.length_evidence as {
    policy: string;
    support_labels?: string[];
    axis_length_m?: number;
    gross_support_extent_m?: number;
  } | undefined;
  const slabEvidence = element.properties.slab_evidence as { label: string; thickness_text: string; boundary_layers: string[]; void_count: number; void_area_m2?: number } | undefined;
  const foundationEvidence = element.properties.foundation_evidence as {
    boundary_handles: string[];
    translated_copy_count: number;
    thickness_note_handles: string[];
    thickness_texts: string[];
  } | undefined;
  const stairEvidence = element.properties.stair_evidence as {
    label: string;
    annotation_text: string;
    scope_text: string;
    step_count: number;
    tread_m: number;
    riser_m: number;
    lower_level_m: number | null;
    upper_level_m: number | null;
    repeat_definition_required: boolean;
  } | undefined;
  const formworkEvidence = element.properties.formwork_evidence as { adjacent_slab_thicknesses_m: number[]; exposed_side_depths_m: number[]; policy: string } | undefined;
  const rebarEvidence = element.element_type === "rebar" ? element.properties as { position_number: number; declared_weight_kg: number; calculated_weight_kg: number; rebar_scope_labels: string[]; table_handle: string } : undefined;
  const elementLabel = typeof element.properties.element_label === "string" ? element.properties.element_label : "";
  const blockingMessage = blocking.some((issue) => issue === "blocking:stair_floor_repeat_required")
    ? "Tip merdivenin uygulanacağı kat aralıkları henüz tanımlanmadı; bu aday kesin metraja kapalıdır."
    : "Pafta birimi veya kesit kanıtı geometriyle uyuşmuyor. Kaynak eşlemesini düzeltip analizi yeniden çalıştırın.";
  return (
    <div className="element-review">
      <div className="element-title">
        <div>
          <span className={`status-tag ${element.review_status}`}>{STATUS_LABELS[element.review_status]}</span>
          <h3>{elementTypeLabel(element.element_type)}{elementLabel ? ` · ${elementLabel}` : ""}</h3>
          <p>{element.floor} · {element.layer} · Handle {element.source_handle || "—"}</p>
        </div>
        <div className="confidence"><span>Güven</span><strong>%{Math.round(element.confidence * 100)}</strong></div>
      </div>
      {missing.length > 0 && (
        <div className="missing-note"><AlertTriangle size={17} /><span>Kesin hesap için eksik: {missing.map((key) => measurementLabel(element.element_type, key)).join(", ")}</span></div>
      )}
      {blocking.length > 0 && (
        <div className="missing-note"><AlertTriangle size={17} /><span>{blockingMessage}</span></div>
      )}
      {heightEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Mimari kesitten yükseklik adayı</strong>{heightEvidence.floor_label}: {formatSigned(heightEvidence.lower_level_m)} → {formatSigned(heightEvidence.upper_level_m)} = {formatQuantity(heightEvidence.height_m)} m<small>{heightEvidence.source_name} · {heightEvidence.block_name} bloğu</small></span></div>
      )}
      {levelHeightEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Statik kotlardan kat yüksekliği</strong>{formatSigned(levelHeightEvidence.lower_level_m)} → {formatSigned(levelHeightEvidence.upper_level_m)} = {formatQuantity(levelHeightEvidence.upper_level_m - levelHeightEvidence.lower_level_m)} m<small>Ardışık kalıp planı kotları arasındaki açık fark</small></span></div>
      )}
      {beamEvidence && (
        <div className="evidence-note beam-evidence"><Ruler size={17} /><span><strong>Statik plandan kiriş kesiti</strong>{beamEvidence.element_label}: {formatQuantity(beamEvidence.section_width_m * 100)} × {formatQuantity(beamEvidence.section_height_m * 100)} cm{lengthEvidence?.support_labels && <small>Mesnetler: {lengthEvidence.support_labels.filter(Boolean).join(" – ")} · net {formatQuantity(element.measurements.length_m)} m{lengthEvidence.axis_length_m ? ` · aks ${formatQuantity(lengthEvidence.axis_length_m)} m` : ""}</small>}{formworkEvidence && <small>Kalıp: döşeme düşümü sonrası açık yanlar {formworkEvidence.exposed_side_depths_m.map(formatQuantity).join(" / ")} m · toplam {formatQuantity(element.measurements.formwork_area_m2)} m²</small>}<small>{beamEvidence.section_text} · Etiket handle {beamEvidence.annotation_handle}</small></span></div>
      )}
      {slabEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Döşeme paneli · {slabEvidence.label}</strong>Net alan {formatQuantity(element.measurements.area_m2)} m² · {slabEvidence.thickness_text}<small>{slabEvidence.boundary_layers.join(" / ")} sınırları · algılanan boşluk: {slabEvidence.void_count}{slabEvidence.void_area_m2 ? ` · ${formatQuantity(slabEvidence.void_area_m2)} m² düşüldü` : ""}</small></span></div>
      )}
      {foundationEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Radye temel sınırı</strong>{formatQuantity(element.measurements.area_m2)} m² · {formatQuantity(element.measurements.thickness_m * 100)} cm<small>Aynı biçimli {foundationEvidence.translated_copy_count} çizim tek adayda birleştirildi; {foundationEvidence.boundary_handles.length} sınır ve {foundationEvidence.thickness_note_handles.length} kalınlık notu bağlı.</small></span></div>
      )}
      {stairEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Merdiven planı · {stairEvidence.label}</strong>{stairEvidence.step_count} rıhtım · {formatQuantity(stairEvidence.tread_m * 100)}/{formatQuantity(stairEvidence.riser_m * 100)} cm · toplam yükselme {formatQuantity(element.measurements.total_rise_m)} m<small>{stairEvidence.repeat_definition_required ? "Tip merdiven; kat aralığı tekrarı kullanıcı tarafından tanımlanmalı." : stairEvidence.scope_text}</small></span></div>
      )}
      {rebarEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Açık donatı metraj satırı · Poz {rebarEvidence.position_number}</strong>Pafta {formatQuantity(rebarEvidence.declared_weight_kg)} kg · formül kontrolü {formatQuantity(rebarEvidence.calculated_weight_kg)} kg<small>Kapsam {rebarEvidence.rebar_scope_labels[0]}–{rebarEvidence.rebar_scope_labels.at(-1)} · tablo handle {rebarEvidence.table_handle}</small></span></div>
      )}
      <div className="measurement-grid">
        {keys.map((key) => (
          <label key={key}>{measurementLabel(element.element_type, key)}<input type="number" min="0" step="any" value={values[key] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} className={!values[key] && element.required_inputs.includes(key) ? "required" : ""} /></label>
        ))}
      </div>
      <label>Karar gerekçesi<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Kontrol edilen pafta, kesit veya düzeltme notu…" /></label>
      <div className="decision-actions">
        <button className="button danger-ghost" disabled={busy} onClick={() => void decide("rejected")}><CircleStop size={16} />Hariç tut</button>
        <button className="button primary" disabled={busy || missing.length > 0 || blocking.length > 0} onClick={() => void decide("accepted")}><Check size={16} />Onayla ve hesaba kat</button>
      </div>
    </div>
  );
}

function GeometryPreview({ elements, selectedId, onSelect }: { elements: DetectedElement[]; selectedId?: string; onSelect: (id: string) => void }) {
  const drawingElements = elements.filter((item) => item.geometry.kind !== "rebar_schedule_row");
  const [focusSelected, setFocusSelected] = useState(false);
  const [zoom, setZoom] = useState(1);
  const allBounds = useMemo(() => {
    const boxes = elements
      .filter((item) => item.geometry.kind !== "rebar_schedule_row")
      .map((item) => item.geometry.bbox)
      .filter((box): box is [number, number, number, number] => Boolean(box));
    if (!boxes.length) return [0, 0, 100, 100] as const;
    return [
      Math.min(...boxes.map((box) => box[0])),
      Math.min(...boxes.map((box) => box[1])),
      Math.max(...boxes.map((box) => box[2])),
      Math.max(...boxes.map((box) => box[3])),
    ] as const;
  }, [elements]);
  const selected = drawingElements.find((item) => item.id === selectedId);
  const focusBounds = focusSelected && selected?.geometry.bbox
    ? selected.geometry.bbox
    : allBounds;
  const [x1, y1, x2, y2] = focusBounds;
  const baseWidth = Math.max(x2 - x1, 0.5);
  const baseHeight = Math.max(y2 - y1, 0.5);
  const centerX = (x1 + x2) / 2;
  const centerY = (y1 + y2) / 2;
  const viewWidth = baseWidth / zoom;
  const viewHeight = baseHeight / zoom;
  const pad = Math.max(viewWidth, viewHeight) * 0.08;
  const viewBox = `${centerX - viewWidth / 2 - pad} ${-(centerY + viewHeight / 2 + pad)} ${viewWidth + pad * 2} ${viewHeight + pad * 2}`;

  return <div className="drawing">
    <div className="drawing-controls">
      <button title="Uzaklaştır" onClick={() => setZoom((value) => Math.max(0.5, value / 1.35))}><ZoomOut size={15} /></button>
      <button title="Yakınlaştır" onClick={() => setZoom((value) => Math.min(12, value * 1.35))}><ZoomIn size={15} /></button>
      <button title="Seçili elemana odaklan" className={focusSelected ? "active" : ""} disabled={!selected?.geometry.bbox} onClick={() => { setFocusSelected((value) => !value); setZoom(1); }}><Focus size={15} /></button>
      <button title="Tümünü göster" onClick={() => { setFocusSelected(false); setZoom(1); }}>1:1</button>
    </div>
    <svg viewBox={viewBox} preserveAspectRatio="xMidYMid meet">{drawingElements.map((element) => {
      const points = element.geometry.points;
      const box = element.geometry.bbox;
      const coords = points.length > 1
        ? points.map(([x, y]) => `${x},${-y}`).join(" ")
        : box ? `${box[0]},${-box[1]} ${box[2]},${-box[1]} ${box[2]},${-box[3]} ${box[0]},${-box[3]} ${box[0]},${-box[1]}` : "";
      return coords && <polyline key={element.id} points={coords} className={`${element.review_status} ${selectedId === element.id ? "selected" : ""}`} vectorEffect="non-scaling-stroke" onClick={() => onSelect(element.id)} />;
    })}</svg>
    {drawingElements.length === 0 && <div className="drawing-empty">Analiz sonrası geometri burada görünür.</div>}
  </div>;
}

function QuantitiesView({ api, projectId, quantities, pendingCount, onMessage }: { api: EngineApi; projectId: string; quantities: QuantityLine[]; pendingCount: number; onMessage: (message: string) => void }) {
  const totals = useMemo(() => { const grouped = new Map<string, { category: string; unit: string; value: number }>(); quantities.forEach((line) => { const key = `${line.category}|${line.unit}`; const current = grouped.get(key) ?? { category: line.category, unit: line.unit, value: 0 }; current.value += line.quantity; grouped.set(key, current); }); return Array.from(grouped.values()); }, [quantities]);
  async function exportPayload() { const result = await api.exportReport(projectId); onMessage(`Excel raporu oluşturuldu: ${result.path}`); }
  return <div className="stack"><section className={`callout ${pendingCount ? "warning" : "success"}`}>{pendingCount ? <AlertTriangle size={22} /> : <ShieldCheck size={22} />}<div><strong>{pendingCount ? "Kesin toplam dışında bekleyen elemanlar var" : "Mühendis onaylı kesin metraj"}</strong><p>{pendingCount ? `${pendingCount} eleman onaylanana kadar aşağıdaki toplamların dışında tutulur.` : "Tüm satırlar onaylı bir kaynak elemana ve açık formüle bağlıdır."}</p></div></section><div className="metric-grid">{totals.length ? totals.map((total) => <div className="metric-card" key={`${total.category}-${total.unit}`}><span>{total.category}</span><strong>{formatQuantity(total.value)}</strong><small>{total.unit}</small></div>) : <div className="metric-card empty"><span>Henüz kesin metraj yok</span><strong>0</strong><small>Onay bekleniyor</small></div>}</div><section className="panel"><div className="section-heading"><div><span className="eyebrow">İZLENEBİLİR METRAJ</span><h2>{quantities.length} hesap satırı</h2></div><button className="button primary" disabled={quantities.length === 0} onClick={() => void exportPayload()}><FileSpreadsheet size={17} /> Excel raporu hazırla</button></div><div className="quantity-table"><div className="quantity-head"><span>Kat / Disiplin</span><span>Kalem</span><span>Formül</span><span>Miktar</span></div>{quantities.map((line) => <div className="quantity-row" key={line.id}><span><strong>{line.floor}</strong><small>{disciplineLabel(line.discipline)}</small></span><span><strong>{line.description}</strong><small>{line.element_id.slice(-10)}</small></span><code>{line.formula}</code><span className="quantity-value">{formatQuantity(line.quantity)} <small>{line.unit}</small></span></div>)}{quantities.length === 0 && <EmptyState icon={<FileSpreadsheet />} title="Onaylı hesap satırı yok" detail="Tespit ekranında eleman ölçülerini doğrulayıp onaylayın." />}</div></section></div>;
}

function CommercialView({ api, projectId, quantities, catalogs, priceItems, mappings, scenarios, gates, onChanged, onError }: { api: EngineApi; projectId: string; quantities: QuantityLine[]; catalogs: PriceCatalog[]; priceItems: PriceItem[]; mappings: PriceMapping[]; scenarios: OfferScenario[]; gates: ValidationGate[]; onChanged: () => void; onError: (message: string) => void }) {
  const [catalogPath, setCatalogPath] = useState("");
  const [catalogName, setCatalogName] = useState("2026 Birim Fiyatları");
  const [catalogYear, setCatalogYear] = useState("2026");
  const [official, setOfficial] = useState(true);
  const [scenarioName, setScenarioName] = useState("Ana Teklif");
  const [generalRate, setGeneralRate] = useState("0");
  const [profitRate, setProfitRate] = useState("0");
  const [escalationFactor, setEscalationFactor] = useState("1");
  const [vatRate, setVatRate] = useState("0");
  const [busy, setBusy] = useState(false);
  const quantityById = useMemo(() => new Map(quantities.map((item) => [item.id, item])), [quantities]);
  const priceById = useMemo(() => new Map(priceItems.map((item) => [item.id, item])), [priceItems]);

  async function chooseCatalog() {
    try {
      const selected = isTauri() ? await open({ multiple: false, filters: [{ name: "Birim fiyat kataloğu", extensions: ["xlsx", "xls"] }] }) : (await api.selectFile("Birim fiyat Excel dosyasını seçin")).path;
      if (typeof selected === "string") setCatalogPath(selected);
    } catch (error) { onError((error as Error).message); }
  }

  async function importCatalog() {
    if (!catalogPath) return;
    setBusy(true);
    try {
      await api.importPriceCatalog(projectId, { path: catalogPath, name: catalogName, year: Number(catalogYear), version: "1", currency: "TRY", is_official: official, source_url: official ? "https://yfk.csb.gov.tr/birim-fiyatlar-100468" : "" });
      setCatalogPath("");
      onChanged();
    } catch (error) { onError((error as Error).message); } finally { setBusy(false); }
  }

  async function suggest() {
    setBusy(true);
    try { await api.suggestPriceMappings(projectId); onChanged(); } catch (error) { onError((error as Error).message); } finally { setBusy(false); }
  }

  async function approve(mapping: PriceMapping) {
    try {
      await api.putPriceMapping(projectId, { quantity_line_id: mapping.quantity_line_id, price_item_id: mapping.price_item_id, status: "approved", confidence: mapping.confidence, reviewer: "Mühendis", reason: "Poz açıklaması, birim ve imalat kapsamı kontrol edildi" });
      onChanged();
    } catch (error) { onError((error as Error).message); }
  }

  async function createScenario() {
    setBusy(true);
    const values = [
      { label: "Genel gider", kind: "percent" as const, base: "direct_cost" as const, value: generalRate, order: 10, applicable: Number(generalRate) > 0 },
      { label: "Yüklenici kârı", kind: "percent" as const, base: "running_total" as const, value: profitRate, order: 20, applicable: Number(profitRate) > 0 },
      { label: "Eskalasyon", kind: "index" as const, base: "running_total" as const, value: escalationFactor, order: 30, applicable: Number(escalationFactor) !== 1 },
      { label: "KDV", kind: "percent" as const, base: "running_total" as const, value: vatRate, order: 40, applicable: Number(vatRate) > 0 },
    ];
    try {
      const result = await api.createOfferScenario(projectId, { name: scenarioName, currency: "TRY", exchange_rate: "1", adjustments: values.map((item, index) => ({ id: `ui-${index}`, ...item, source: "Kullanıcı onayı", source_date: new Date().toISOString().slice(0, 10) })), approved: true, reviewer: "Mühendis" });
      onError(`Teklif hesaplandı: ${String(result.totals.grand_total ?? "—")} TRY`);
      onChanged();
    } catch (error) { onError((error as Error).message); } finally { setBusy(false); }
  }

  return <div className="stack">
    <section className="callout"><BadgeDollarSign size={22} /><div><strong>Metraj ile fiyat birbirinden bağımsız ve izlenebilir</strong><p>Yalnız mühendis onaylı poz eşleşmeleri teklife girer; oran ve vergiler açık senaryo kalemleridir.</p></div><span className={mappings.some((item) => item.status === "approved") ? "safe" : "risk"}>{mappings.filter((item) => item.status === "approved").length} onaylı poz</span></section>
    <div className="content-grid source-layout"><section className="panel source-form-panel"><div className="section-heading"><div><span className="eyebrow">FİYAT KATALOĞU</span><h2>Resmî veya özel Excel</h2></div><FileSpreadsheet size={21} /></div><label>Katalog dosyası<div className="path-picker"><input value={catalogPath} onChange={(event) => setCatalogPath(event.target.value)} placeholder=".xlsx veya .xls" /><button onClick={() => void chooseCatalog()}><FolderOpen size={17} /></button></div></label><label>Katalog adı<input value={catalogName} onChange={(event) => setCatalogName(event.target.value)} /></label><div className="form-row"><label>Yıl<input type="number" value={catalogYear} onChange={(event) => setCatalogYear(event.target.value)} /></label><label className="checkbox-label"><input type="checkbox" checked={official} onChange={(event) => setOfficial(event.target.checked)} /> Resmî katalog</label></div><button className="button primary wide" disabled={busy || !catalogPath} onClick={() => void importCatalog()}><FilePlus2 size={16} /> Kataloğu içe al</button></section><section className="panel source-list-panel"><div className="section-heading"><div><span className="eyebrow">KATALOGLAR</span><h2>{catalogs.length} sürümlü kaynak</h2></div><span className="count-badge">{priceItems.length} poz</span></div><div className="source-list">{catalogs.map((catalog) => <div className="source-row" key={catalog.id}><div className="file-icon architectural">{catalog.year}</div><div className="source-main"><strong>{catalog.name}</strong><span>{catalog.is_official ? "Resmî" : "Özel"} · {catalog.currency} · v{catalog.version}</span><small>SHA {catalog.sha256.slice(0, 12)}</small></div></div>)}{catalogs.length === 0 && <EmptyState icon={<FileSpreadsheet />} title="Katalog yok" detail="Poz, açıklama, birim ve birim fiyat sütunlu Excel ekleyin." />}</div></section></div>
    <section className="panel"><div className="section-heading"><div><span className="eyebrow">POZ EŞLEŞTİRME</span><h2>{mappings.length} öneri / karar</h2></div><button className="button secondary" disabled={busy || quantities.length === 0 || priceItems.length === 0} onClick={() => void suggest()}><Focus size={16} /> Önerileri oluştur</button></div><div className="commercial-table"><div className="commercial-row head"><span>Metraj</span><span>Poz</span><span>Güven</span><span>Karar</span></div>{mappings.map((mapping) => { const quantity = quantityById.get(mapping.quantity_line_id); const price = priceById.get(mapping.price_item_id); return <div className="commercial-row" key={mapping.id}><span><strong>{quantity?.description ?? mapping.quantity_line_id}</strong><small>{quantity ? `${formatQuantity(quantity.quantity)} ${quantity.unit}` : "Metraj yenilenmiş"}</small></span><span><strong>{price?.code ?? mapping.price_item_id}</strong><small>{price?.description}</small></span><span>%{Math.round(mapping.confidence * 100)}</span><span>{mapping.status === "approved" ? <span className="status-tag accepted">Onaylı</span> : <button className="button secondary" onClick={() => void approve(mapping)}><Check size={14} /> Onayla</button>}</span></div>; })}{mappings.length === 0 && <EmptyState icon={<Focus />} title="Poz eşleşmesi yok" detail="Kesin metraj ve katalog hazır olduğunda önerileri oluşturun." />}</div></section>
    <section className="panel"><div className="section-heading"><div><span className="eyebrow">TAM TEKLİF</span><h2>Sıralı ticari ayarlamalar</h2></div><BadgeDollarSign size={21} /></div><div className="offer-form"><label>Senaryo adı<input value={scenarioName} onChange={(event) => setScenarioName(event.target.value)} /></label><label>Genel gider %<input type="number" value={generalRate} onChange={(event) => setGeneralRate(event.target.value)} /></label><label>Kâr %<input type="number" value={profitRate} onChange={(event) => setProfitRate(event.target.value)} /></label><label>Eskalasyon çarpanı<input type="number" step="0.001" value={escalationFactor} onChange={(event) => setEscalationFactor(event.target.value)} /></label><label>KDV %<input type="number" value={vatRate} onChange={(event) => setVatRate(event.target.value)} /></label><button className="button primary" disabled={busy || !mappings.some((item) => item.status === "approved")} onClick={() => void createScenario()}><Check size={16} /> Onaylı teklifi hesapla</button></div><div className="offer-list">{scenarios.map((scenario) => <div className="repeat-row" key={scenario.id}><span className={`status-tag ${scenario.approved ? "accepted" : "pending"}`}>{scenario.approved ? "Onaylı" : "Taslak"}</span><div><strong>{scenario.name}</strong><small>{scenario.currency} · kur {scenario.exchange_rate}</small></div><span>{scenario.adjustments.length} ayarlama</span><small>{scenario.reviewer || "Onay bekliyor"}</small></div>)}</div></section>
    <section className="panel"><div className="section-heading"><div><span className="eyebrow">GÜVENİLİRLİK KAPILARI</span><h2>Disiplin bazlı yayın durumu</h2></div><ShieldCheck size={21} /></div><div className="gate-grid">{gates.map((gate) => <div className="metric-card" key={gate.discipline}><span>{disciplineLabel(gate.discipline)}</span><strong>{gate.state}</strong><small>{gate.small_project_approved ? "Küçük ✓" : "Küçük bekliyor"} · {gate.complex_project_approved ? "Karmaşık ✓" : "Karmaşık bekliyor"}</small></div>)}</div></section>
  </div>;
}

const REVISION_LABELS: Record<RevisionChangeKind, string> = {
  added: "Eklendi",
  deleted: "Silindi",
  modified: "Değişti",
  unchanged: "Aynı",
};

function RevisionComparisonView({ api, projectId, sources }: { api: EngineApi; projectId: string; sources: SourceFile[] }) {
  const structural = sources.filter((source) => source.discipline === "structural");
  const [oldSourceId, setOldSourceId] = useState(structural[0]?.id ?? "");
  const [newSourceId, setNewSourceId] = useState(structural[1]?.id ?? "");
  const [comparison, setComparison] = useState<RevisionComparison | null>(null);
  const [filter, setFilter] = useState<RevisionChangeKind | "all">("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!oldSourceId && structural[0]) setOldSourceId(structural[0].id);
    if (!newSourceId && structural[1]) setNewSourceId(structural[1].id);
  }, [structural, oldSourceId, newSourceId]);

  async function compare() {
    if (!oldSourceId || !newSourceId || oldSourceId === newSourceId) return;
    setBusy(true);
    setError("");
    try {
      setComparison(await api.compareRevisions(projectId, oldSourceId, newSourceId));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const rows = comparison?.changes.filter((item) => filter === "all" || item.kind === filter) ?? [];
  return <div className="stack revision-view">
    <section className="panel revision-select-panel">
      <div className="section-heading"><div><span className="eyebrow">DXF REVİZYON KARŞILAŞTIRMASI</span><h2>Kolon, kiriş ve döşeme değişiklikleri</h2></div><GitCompareArrows size={22} /></div>
      <div className="revision-select-grid">
        <label>Eski kaynak<select value={oldSourceId} onChange={(event) => setOldSourceId(event.target.value)}><option value="">Seçiniz</option>{structural.map((source) => <option key={source.id} value={source.id}>{source.revision || "Revizyonsuz"} · {source.floor} · {source.original_name}</option>)}</select></label>
        <label>Yeni kaynak<select value={newSourceId} onChange={(event) => setNewSourceId(event.target.value)}><option value="">Seçiniz</option>{structural.map((source) => <option key={source.id} value={source.id}>{source.revision || "Revizyonsuz"} · {source.floor} · {source.original_name}</option>)}</select></label>
        <button className="button primary" disabled={busy || !oldSourceId || !newSourceId || oldSourceId === newSourceId} onClick={() => void compare()}>{busy ? <LoaderCircle className="spin" size={16} /> : <GitCompareArrows size={16} />} Karşılaştır</button>
      </div>
      <p className="hint">Eşleşme önce benzersiz eleman etiketini, ardından paftanın genel kaymasını düzelten geometriyi kullanır. Düşük güvenli eşleşmeler ayrıca uyarılır.</p>
      {error && <div className="inline-error">{error}</div>}
    </section>
    {comparison && <>
      <div className="revision-summary">{(["added", "deleted", "modified", "unchanged"] as RevisionChangeKind[]).map((kind) => <button key={kind} className={`${kind} ${filter === kind ? "active" : ""}`} onClick={() => setFilter(filter === kind ? "all" : kind)}><span>{REVISION_LABELS[kind]}</span><strong>{comparison.summary[kind] ?? 0}</strong></button>)}</div>
      {comparison.warnings.map((warning) => <section className="callout warning" key={warning}><AlertTriangle size={20} /><div><strong>Karşılaştırma uyarısı</strong><p>{warning}</p></div></section>)}
      <section className="panel revision-results"><div className="revision-result-head"><strong>{filter === "all" ? "Tüm karşılaştırma" : REVISION_LABELS[filter]}</strong><span>{rows.length} eleman</span></div><div className="revision-table"><div className="revision-row head"><span>Durum</span><span>Eleman</span><span>Eski ölçüler</span><span>Yeni ölçüler</span><span>Eşleşme</span></div>{rows.map((item, index) => <div className="revision-row" key={`${item.old_element_id}-${item.new_element_id}-${index}`}><span><i className={`revision-status ${item.kind}`} />{REVISION_LABELS[item.kind]}</span><span><strong>{item.label || elementTypeLabel(item.element_type)}</strong><small>{item.floor} · {elementTypeLabel(item.element_type)}</small></span><span>{revisionMeasurements(item.old_measurements)}</span><span>{revisionMeasurements(item.new_measurements)}</span><span><strong>%{Math.round(item.match_confidence * 100)}</strong><small>{item.match_method === "unique_label" ? "Etiket" : item.match_method === "translated_geometry" ? "Geometri" : "Eşleşmedi"}</small></span></div>)}</div></section>
    </>}
  </div>;
}

function EmptyState({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) { return <div className="empty-state"><span>{icon}</span><strong>{title}</strong><p>{detail}</p></div>; }
function viewTitle(view: View) { return ({ sources: "Kaynak dosyalar", floors: "Kat ve tekrar yönetimi", mapping: "Birim ve eşleme", review: "Tespit ve mühendis onayı", quantities: "Kesin metraj", commercial: "Fiyat ve teklif", revisions: "Revizyon karşılaştırması" })[view]; }
function disciplineLabel(value: Discipline) { return DISCIPLINES.find((item) => item.value === value)?.label ?? value; }
function floorKindLabel(value: FloorKind) { return FLOOR_KINDS.find((item) => item.value === value)?.label ?? value; }
function sheetKindLabel(value: SheetKind) { return SHEET_KINDS.find((item) => item.value === value)?.label ?? value; }
function elementTypeLabel(value: string) { return ({ column: "Kolon", beam: "Kiriş", shear_wall: "Perde", slab: "Döşeme", slab_opening: "Döşeme boşluğu", raft: "Radye temel", foundation: "Temel", stair: "Merdiven", rebar: "Donatı", wall: "Duvar", door: "Kapı", window: "Pencere", room: "Mahal", finish_area: "Kaplama", pipe: "Boru", duct: "Kanal", mechanical_fitting: "Fittings", mechanical_equipment: "Mekanik cihaz", cable: "Kablo", cable_tray: "Kablo tavası", light: "Armatür", socket: "Priz", panel: "Pano", electrical_item: "Elektrik ekipmanı", landscape_area: "Peyzaj alanı", landscape_linear: "Bordür / hat", landscape_item: "Bitki / ekipman", schedule_item: "Poz çizelgesi", pdf_evidence: "PDF kanıtı" } as Record<string, string>)[value] ?? value; }
function measurementLabel(elementType: string, key: string) { if (elementType === "beam" && key === "height_m") return "Kesit yüksekliği (m)"; if (elementType === "beam" && key === "width_m") return "Kesit genişliği (m)"; return MEASUREMENT_LABELS[key] ?? key; }
function formatQuantity(value: number) { return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 3 }).format(value); }
function formatSigned(value: number) { return `${value >= 0 ? "+" : ""}${formatQuantity(value)}`; }
function revisionMeasurements(values: Record<string, number>) { const keys = ["width_m", "depth_m", "height_m", "length_m", "area_m2", "thickness_m", "void_area_m2", "plan_area_m2", "total_rise_m"]; const parts = keys.filter((key) => values[key] !== undefined).map((key) => `${measurementLabel("", key)}: ${formatQuantity(values[key])}`); return parts.length ? parts.join(" · ") : "—"; }
function sourceStatusReady(source: SourceFile) { if (source.source_format === "pdf") return source.calibration_status === "confirmed"; if (source.source_format !== "dxf") return true; return source.unit_confirmed || source.detected_unit !== "unknown"; }
function sourceStatusLabel(source: SourceFile) { if (source.source_format === "pdf") return source.calibration_status === "confirmed" ? "ölçek onaylı" : "ölçek bekliyor"; if (source.source_format !== "dxf") return source.source_format.toUpperCase(); return source.unit_confirmed ? source.drawing_unit : source.detected_unit !== "unknown" ? `${source.detected_unit} algılandı` : "birim bekliyor"; }

export default App;
