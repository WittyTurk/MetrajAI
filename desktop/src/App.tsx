import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeDollarSign,
  Boxes,
  Check,
  ChevronRight,
  CircleStop,
  Clock3,
  FilePlus2,
  FileSpreadsheet,
  Focus,
  FolderOpen,
  FolderPlus,
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
import logoMark from "../app-icon.svg";
import { readRecentProjects, rememberRecentProject, removeRecentProject } from "./recentProjects";
import type { RecentProject } from "./recentProjects";
import type {
  AnalysisRun,
  AnalysisWarning,
  ArchitecturalAssignment,
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
  SourceDrawingPreview,
  SourceInspection,
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
  { value: "plan", label: "Kat planı" },
  { value: "column_application", label: "Kolon aplikasyonu" },
  { value: "rebar_plan", label: "Donatı planı" },
  { value: "foundation", label: "Temel planı" },
  { value: "detail", label: "Detay paftası" },
  { value: "schedule", label: "Çizelge" },
  { value: "section", label: "Kesit" },
  { value: "elevation", label: "Görünüş" },
  { value: "other", label: "Diğer / açıklama" },
];

function defaultSourceRole(discipline: Discipline, sheetKind: SheetKind) {
  const roles: Partial<Record<SheetKind, string>> = {
    column_application: "kolon aplikasyonu", rebar_plan: "donatı", foundation: "temel",
    detail: "detay", schedule: "çizelge", section: "kesit", elevation: "görünüş", other: "açıklama",
  };
  return roles[sheetKind] ?? ({ structural: "kalip", architectural: "mimari", landscape: "çevre", mechanical: "mekanik", electrical: "elektrik" } as Record<Discipline, string>)[discipline];
}

const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Onay bekliyor",
  needs_review: "Eksik bilgi",
  accepted: "Onaylandı",
  rejected: "Hariç tutuldu",
};

function reviewStatusLabel(element: DetectedElement) {
  if (element.review_status !== "needs_review") return STATUS_LABELS[element.review_status];
  const missing = element.required_inputs.some((key) => !(element.measurements[key] > 0));
  const blocked = element.issues.some((issue) => issue.startsWith("blocking:"));
  return missing || blocked ? "Eksik bilgi" : "Mühendis kontrolü";
}

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
  sill_height_m: "Açıklık alt kotu (bitmiş döşemeden m)",
};

function App() {
  const activeProjectId = useRef<string | null>(null);
  const [api, setApi] = useState<EngineApi | null>(null);
  const [engineError, setEngineError] = useState("");
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [sources, setSources] = useState<SourceFile[]>([]);
  const [elements, setElements] = useState<DetectedElement[]>([]);
  const [quantities, setQuantities] = useState<QuantityLine[]>([]);
  const [warnings, setWarnings] = useState<AnalysisWarning[]>([]);
  const [floors, setFloors] = useState<FloorDefinition[]>([]);
  const [repeatAssignments, setRepeatAssignments] = useState<RepeatAssignment[]>([]);
  const [architecturalAssignments, setArchitecturalAssignments] = useState<ArchitecturalAssignment[]>([]);
  const [priceCatalogs, setPriceCatalogs] = useState<PriceCatalog[]>([]);
  const [priceItems, setPriceItems] = useState<PriceItem[]>([]);
  const [priceMappings, setPriceMappings] = useState<PriceMapping[]>([]);
  const [offerScenarios, setOfferScenarios] = useState<OfferScenario[]>([]);
  const [validationGates, setValidationGates] = useState<ValidationGate[]>([]);
  const [view, setView] = useState<View>("sources");
  const [advancedOpen, setAdvancedOpen] = useState(false);
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
      nextOffers, nextGates, nextArchitecturalAssignments,
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
        api.architecturalAssignments(projectId),
      ]);
    if (activeProjectId.current !== projectId) return;
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
    setArchitecturalAssignments(nextArchitecturalAssignments);
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
      if (["failed", "cancelled"].includes(current.status)) setMessage(current.message);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  async function cancelAnalysis() {
    if (!api || !run || !["queued", "running"].includes(run.status)) return;
    try {
      setRun(await api.cancelAnalysis(run.id));
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
          activeProjectId.current = summary.project.project_id;
          setSources([]);
          setElements([]);
          setQuantities([]);
          setWarnings([]);
          setFloors([]);
          setRepeatAssignments([]);
          setArchitecturalAssignments([]);
          setPriceCatalogs([]);
          setPriceItems([]);
          setPriceMappings([]);
          setOfferScenarios([]);
          setValidationGates([]);
          setRun(null);
          setMessage("");
          setProject(summary);
          setView("sources");
          void refresh(summary.project.project_id);
        }}
      />
    );
  }

  const reviewableCount = elements.filter((item) => item.properties.evidence_only !== true).length;
  const pendingCount = elements.filter((item) =>
    item.properties.evidence_only !== true && ["pending", "needs_review"].includes(item.review_status)
  ).length;
  const structuralBlockers = structuralCompletionMessages(elements);
  const analysisActive = run != null && ["queued", "running"].includes(run.status);
  const setupIssueCount = sources.filter(sourceNeedsSetup).length;
  const reviewComplete = reviewableCount > 0 && pendingCount === 0;
  const quantitiesComplete = quantities.length > 0 && pendingCount === 0 && structuralBlockers.length === 0;
  const advancedActive = ["floors", "mapping", "revisions"].includes(view);
  function continueToReview() {
    if (setupIssueCount > 0) {
      setAdvancedOpen(true);
      setView("mapping");
      return;
    }
    void startAnalysis();
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-mark" src={logoMark} alt="MetrajAI logosu" />
          <div><strong>MetrajAI</strong><span>Mühendis kontrollü metraj</span></div>
        </div>
        <div className="project-chip">
          <span>Aktif proje</span>
          <strong>{project.project.name}</strong>
          <small>{sources.length} kaynak · {reviewableCount} metraj adayı{elements.length > reviewableCount ? ` · ${elements.length - reviewableCount} çizim izi` : ""}</small>
          <button
            className="project-switch"
            disabled={analysisActive}
            title={analysisActive ? "Analiz tamamlanınca proje değiştirebilirsiniz" : "Proje seçimine dön"}
            onClick={() => {
              activeProjectId.current = null;
              setProject(null);
              setRun(null);
              setMessage("");
            }}
          ><FolderOpen size={14} /> Projelere dön</button>
        </div>
        <span className="sidebar-section-label">PROJE AKIŞI</span>
        <nav className="workflow-nav" aria-label="Proje adımları">
          <StageNavItem index="1" label="Dosyaları ekle" status={sources.length === 0 ? "Dosya bekleniyor" : setupIssueCount ? `${setupIssueCount} dosyada ayar gerekli` : `${sources.length} dosya hazır`} active={view === "sources"} complete={sources.length > 0 && setupIssueCount === 0} onClick={() => setView("sources")} />
          <StageNavItem index="2" label="Ölçüleri kontrol et" status={elements.length === 0 ? "Analiz yapılmadı" : pendingCount ? `${pendingCount} karar bekliyor` : "Kararlar tamamlandı"} active={view === "review"} complete={reviewComplete} onClick={() => setView("review")} />
          <StageNavItem index="3" label="Sonuçları al" status={quantities.length === 0 ? "Henüz sonuç yok" : !quantitiesComplete ? "Kısmi sonuç" : `${quantities.length} kesin satır`} active={view === "quantities"} complete={quantitiesComplete} onClick={() => setView("quantities")} />
        </nav>
        <div className="sidebar-tools">
          <span className="sidebar-section-label">İSTEĞE BAĞLI</span>
          <ToolNavItem icon={<BadgeDollarSign size={17} />} label="Teklif hazırla" active={view === "commercial"} onClick={() => setView("commercial")} />
          <button className={`advanced-toggle ${advancedActive ? "active" : ""}`} aria-expanded={advancedOpen} aria-controls="advanced-tools" onClick={() => setAdvancedOpen(!advancedOpen)}><span>Gelişmiş araçlar</span><ChevronRight size={16} /></button>
          {advancedOpen && <nav id="advanced-tools" className="advanced-tools" aria-label="Gelişmiş araçlar">
            <ToolNavItem icon={<Layers3 size={16} />} label="Kat ve tekrarlar" active={view === "floors"} onClick={() => setView("floors")} />
            <ToolNavItem icon={<Gauge size={16} />} label="Birim ve eşleme" active={view === "mapping"} onClick={() => setView("mapping")} />
            <ToolNavItem icon={<GitCompareArrows size={16} />} label="Revizyon karşılaştır" active={view === "revisions"} onClick={() => setView("revisions")} />
          </nav>}
        </div>
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
            <p className="topbar-description">{viewDescription(view)}</p>
          </div>
          <div className="topbar-actions">
            {run && ["queued", "running"].includes(run.status) && (
              <div className="run-progress">
                <LoaderCircle className="spin" size={17} />
                <span>{run.message}</span>
                <b>{Math.round(run.progress * 100)}%</b>
              </div>
            )}
            {run && ["queued", "running"].includes(run.status) && <button className="button secondary" onClick={() => void cancelAnalysis()}><CircleStop size={16} /> İptal et</button>}
            {["sources", "review", "mapping"].includes(view) && <button className="button primary" disabled={sources.length === 0 || analysisActive} onClick={continueToReview}>
              {setupIssueCount ? <Gauge size={16} /> : <Play size={16} fill="currentColor" />}{setupIssueCount ? "Eksik ayarları tamamla" : elements.length ? "Analizi yenile" : "Ölçüleri bul"}
            </button>}
          </div>
        </header>

        {message && <div className="banner error"><AlertTriangle size={18} /><span>{message}</span><button onClick={() => setMessage("")}><X size={16} /></button></div>}
        {project.source_safety_notices?.map((notice) => <div className="banner error" key={notice}><AlertTriangle size={18} /><span>{notice}</span></div>)}

        {view === "sources" && <SourcesView api={api} project={project} sources={sources} setupIssueCount={setupIssueCount} onChanged={() => void refresh()} onNext={continueToReview} onError={setMessage} />}
        {view === "floors" && <FloorsView api={api} projectId={project.project.project_id} sources={sources} elements={elements} floors={floors} repeatAssignments={repeatAssignments} onChanged={() => void refresh()} onError={setMessage} onNext={() => setView("mapping")} />}
        {view === "mapping" && <MappingView api={api} projectId={project.project.project_id} sources={sources} onChanged={() => void refresh()} onError={setMessage} onNext={() => void startAnalysis()} />}
        {view === "review" && <ReviewView api={api} projectId={project.project.project_id} sources={sources} elements={elements} assignments={architecturalAssignments} warnings={warnings} hasSources={sources.length > 0} analysisActive={analysisActive} onSources={() => setView("sources")} onMapping={() => setView("mapping")} onAnalyze={continueToReview} onReanalyze={() => void startAnalysis()} onChanged={() => void refresh()} onError={setMessage} onNext={() => setView("quantities")} />}
        {view === "quantities" && <QuantitiesView api={api} projectId={project.project.project_id} quantities={quantities} pendingCount={pendingCount} structuralBlockers={structuralBlockers} onReview={() => setView("review")} onCommercial={() => setView("commercial")} onMessage={setMessage} />}
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
        <img className="brand-mark large" src={logoMark} alt="MetrajAI logosu" />
        <p className="eyebrow">METRAJAI YEREL MOTOR</p>
        <h1>{error ? "Motor başlatılamadı" : "Hesap motoru hazırlanıyor"}</h1>
        <p>{error || "Dosyalarınız cihazdan çıkmadan güvenli çalışma alanı kuruluyor."}</p>
        {!error && <div className="loading-track"><span /></div>}
      </div>
    </div>
  );
}

function ProjectStart({ api, onReady }: { api: EngineApi; onReady: (project: ProjectSummary) => void }) {
  const [mode, setMode] = useState<"home" | "create" | "open">("home");
  const [createPath, setCreatePath] = useState("");
  const [openPath, setOpenPath] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyPath, setBusyPath] = useState<string | null>(null);
  const [recentError, setRecentError] = useState<{ path: string; message: string } | null>(null);
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>(() => readRecentProjects());

  function changeMode(nextMode: "home" | "create" | "open") {
    setMode(nextMode);
    setError("");
    setRecentError(null);
  }

  async function chooseFolder() {
    if (mode === "home") return;
    const title = mode === "create" ? "Yeni proje klasörünü seçin" : "MetrajAI proje klasörünü seçin";
    setError("");
    try {
      const selected = isTauri()
        ? await open({ directory: true, multiple: false, title })
        : (await api.selectDirectory(title)).path;
      if (typeof selected === "string") {
        if (mode === "create") setCreatePath(selected);
        else setOpenPath(selected);
      }
    } catch (dialogError) {
      setError((dialogError as Error).message);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "home") return;
    const path = (mode === "create" ? createPath : openPath).trim();
    if (!path || (mode === "create" && !name.trim())) return;
    setBusy(true);
    setError("");
    try {
      const summary = mode === "create"
        ? await api.createProject(path, name.trim())
        : await api.openProject(path);
      setRecentProjects(rememberRecentProject({
        projectId: summary.project.project_id,
        name: summary.project.name,
        path,
      }));
      onReady(summary);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function openRecent(project: RecentProject) {
    if (busy || busyPath) return;
    setBusyPath(project.path);
    setRecentError(null);
    try {
      const summary = await api.openProject(project.path);
      setRecentProjects(rememberRecentProject({
        projectId: summary.project.project_id,
        name: summary.project.name,
        path: project.path,
      }));
      onReady(summary);
    } catch (requestError) {
      setRecentError({ path: project.path, message: (requestError as Error).message });
    } finally {
      setBusyPath(null);
    }
  }

  const currentPath = mode === "create" ? createPath : openPath;
  const actionBusy = busy || busyPath !== null;

  return (
    <div className="start-screen">
      <section className="start-intro">
        <div className="brand light"><img className="brand-mark" src={logoMark} alt="MetrajAI logosu" /><strong>MetrajAI</strong></div>
        <div className="intro-main">
          <span className="eyebrow">MÜHENDİS KONTROLLÜ · YEREL · İZLENEBİLİR</span>
          <h1>Çizimden kesin metraja,<br />her karar görünür.</h1>
          <p>Projelerinize kaldığınız yerden dönün. Kaynakları, mühendis kararlarını ve metraj çıktılarını aynı çalışma alanında yönetin.</p>
          <div className="intro-steps" aria-label="MetrajAI iş akışı">
            <div><span>01</span><strong>Kaynağı ekle</strong><small>DXF, Excel ve PDF paftaları</small></div>
            <div><span>02</span><strong>Tespitleri doğrula</strong><small>Ölçü ve varsayımlar görünür</small></div>
            <div><span>03</span><strong>Metrajı üret</strong><small>Yalnız onaylı elemanlardan</small></div>
          </div>
        </div>
        <div className="intro-local"><ShieldCheck size={19} /><span>Dosyalarınız ve proje geçmişiniz bu Mac'te kalır.</span></div>
      </section>
      <main className="start-main">
        <div className="start-content">
          {mode === "home" ? (
            <>
              <div className="start-heading">
                <span className="eyebrow">ÇALIŞMA ALANINIZ</span>
                <h2>Projelerinize hoş geldiniz</h2>
                <p>Devam etmek istediğiniz projeyi seçin veya yeni bir çalışma alanı oluşturun.</p>
              </div>
              <div className="start-action-grid">
                <button className="start-action start-action-primary" onClick={() => changeMode("create")}>
                  <span className="start-action-icon"><FolderPlus size={24} /></span>
                  <span><strong>Yeni proje</strong><small>Yeni bir çalışma klasörüyle başlayın</small></span>
                  <ChevronRight size={19} />
                </button>
                <button className="start-action" onClick={() => changeMode("open")}>
                  <span className="start-action-icon"><FolderOpen size={24} /></span>
                  <span><strong>Klasörden aç</strong><small>Mevcut MetrajAI projenize dönün</small></span>
                  <ChevronRight size={19} />
                </button>
              </div>
              <RecentProjects
                projects={recentProjects}
                busy={actionBusy}
                busyPath={busyPath}
                error={recentError}
                onOpen={(project) => void openRecent(project)}
                onRemove={(path) => {
                  setRecentProjects(removeRecentProject(path));
                  if (recentError?.path === path) setRecentError(null);
                }}
                onBrowse={() => changeMode("open")}
              />
            </>
          ) : (
            <>
              <button className="start-back" onClick={() => changeMode("home")} disabled={actionBusy}><ArrowLeft size={16} /> Projelere dön</button>
              <div className="start-heading">
                <span className="eyebrow">{mode === "create" ? "YENİ ÇALIŞMA ALANI" : "MEVCUT ÇALIŞMA ALANI"}</span>
                <h2>{mode === "create" ? "Yeni proje oluşturun" : "Projenizi açın"}</h2>
                <p>{mode === "create"
                  ? "Projeye bir ad verin ve dosyalarının saklanacağı klasörü seçin."
                  : "MetrajAI proje klasörünü seçin veya aşağıdaki son açılanlardan devam edin."}</p>
              </div>
              <div className="start-mode-tabs" role="group" aria-label="Proje işlemi">
                <button className={mode === "create" ? "active" : ""} onClick={() => changeMode("create")} disabled={actionBusy}>Yeni proje</button>
                <button className={mode === "open" ? "active" : ""} onClick={() => changeMode("open")} disabled={actionBusy}>Projeyi aç</button>
              </div>
              <form className="start-project-form" onSubmit={(event) => void submit(event)}>
                {mode === "create" && (
                  <div className="start-field">
                    <label htmlFor="project-name">Proje adı</label>
                    <input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Örn. Taziye Evi" autoFocus required />
                    <small>Bu ad proje listesinde ve raporlarda görünür.</small>
                  </div>
                )}
                <div className="start-field">
                  <label htmlFor="project-path">Proje klasörü</label>
                  <div className="start-path-picker">
                    <input
                      id="project-path"
                      value={currentPath}
                      onChange={(event) => mode === "create" ? setCreatePath(event.target.value) : setOpenPath(event.target.value)}
                      placeholder={mode === "create" ? "Boş bir klasör seçin veya yolunu yazın" : "MetrajAI proje klasörünü seçin"}
                      spellCheck={false}
                      required
                    />
                    <button type="button" onClick={() => void chooseFolder()} disabled={actionBusy} aria-label="Proje klasörünü seç"><FolderOpen size={19} /></button>
                  </div>
                  <small>{mode === "create"
                    ? "MetrajAI kaynakları, kararları ve çıktıları seçtiğiniz klasöre kaydeder."
                    : "Klasörün içinde MetrajAI manifest.json dosyası bulunmalı."}</small>
                </div>
                {error && <div className="start-error" role="alert"><AlertTriangle size={17} /><span>{error}</span></div>}
                <button className="button primary start-submit" type="submit" disabled={actionBusy || !currentPath.trim() || (mode === "create" && !name.trim())}>
                  {busy ? <LoaderCircle className="spin" size={18} /> : mode === "create" ? <FolderPlus size={18} /> : <FolderOpen size={18} />}
                  {mode === "create" ? "Projeyi oluştur" : "Projeyi aç"}
                  {!busy && <ChevronRight size={17} />}
                </button>
              </form>
              {mode === "open" && (
                <RecentProjects
                  projects={recentProjects}
                  busy={actionBusy}
                  busyPath={busyPath}
                  error={recentError}
                  onOpen={(project) => void openRecent(project)}
                  onRemove={(path) => {
                    setRecentProjects(removeRecentProject(path));
                    if (recentError?.path === path) setRecentError(null);
                  }}
                  onBrowse={() => void chooseFolder()}
                />
              )}
              {mode === "create" && <div className="start-form-note"><ShieldCheck size={18} /><span>Yeni proje oluşturmak mevcut projelerinizi değiştirmez.</span></div>}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function RecentProjects({ projects, busy, busyPath, error, onOpen, onRemove, onBrowse }: {
  projects: RecentProject[];
  busy: boolean;
  busyPath: string | null;
  error: { path: string; message: string } | null;
  onOpen: (project: RecentProject) => void;
  onRemove: (path: string) => void;
  onBrowse: () => void;
}) {
  return (
    <section className="recent-section" aria-label="Son açılan projeler">
      <div className="recent-heading"><div><Clock3 size={18} /><h3>Son açılan projeler</h3></div><span>{projects.length}</span></div>
      {projects.length === 0 ? (
        <div className="recent-empty">
          <FolderOpen size={24} />
          <strong>Henüz kayıtlı proje yok</strong>
          <p>Önceki sürümde oluşturduğunuz bir projeyi klasöründen bir kez açın; sonraki açılışlarda burada görünecek.</p>
          <button type="button" onClick={onBrowse}>Klasörden proje aç <ChevronRight size={15} /></button>
        </div>
      ) : (
        <div className="recent-list">
          {projects.map((project) => (
            <div className={`recent-row ${error?.path === project.path ? "has-error" : ""}`} key={project.path}>
              <button className="recent-open" type="button" onClick={() => onOpen(project)} disabled={busy}>
                <span className="recent-icon"><FolderOpen size={20} /></span>
                <span className="recent-details">
                  <strong>{project.name}</strong>
                  <small title={project.path}>{project.path}</small>
                  <em>Son açılış: {new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", year: "numeric" }).format(new Date(project.openedAt))}</em>
                </span>
                {busyPath === project.path ? <LoaderCircle className="spin" size={18} /> : <ChevronRight size={18} />}
              </button>
              <button className="recent-remove" type="button" onClick={() => onRemove(project.path)} disabled={busy} title="Yalnız listeden kaldır; proje dosyaları silinmez" aria-label={`${project.name} projesini son açılanlar listesinden kaldır`}><X size={16} /></button>
              {error?.path === project.path && <div className="recent-row-error" role="alert">{error.message} <span>Konumu kontrol edin veya listeden kaldırın.</span></div>}
            </div>
          ))}
        </div>
      )}
      {projects.length > 0 && <p className="recent-footnote">Bir projeyi listeden kaldırmak klasördeki dosyalarını silmez.</p>}
    </section>
  );
}

function StageNavItem({ index, label, status, active, complete, onClick }: { index: string; label: string; status: string; active: boolean; complete: boolean; onClick: () => void }) {
  return <button className={`stage-nav-item ${active ? "active" : ""}`} aria-current={active ? "step" : undefined} onClick={onClick}><span className="stage-index">{complete ? <Check size={15} /> : index}</span><span className="stage-copy"><strong>{label}</strong><small>{status}</small></span><ChevronRight size={15} /></button>;
}

function ToolNavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return <button className={`tool-nav-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined} onClick={onClick}><span>{icon}</span><strong>{label}</strong><ChevronRight size={14} /></button>;
}

function SourcesView({ api, project, sources, setupIssueCount, onChanged, onNext, onError }: { api: EngineApi; project: ProjectSummary; sources: SourceFile[]; setupIssueCount: number; onChanged: () => void; onNext: () => void; onError: (message: string) => void }) {
  const [path, setPath] = useState("");
  const [discipline, setDiscipline] = useState<Discipline | "">("");
  const [role, setRole] = useState("");
  const [floor, setFloor] = useState("GENEL");
  const [floorKind, setFloorKind] = useState<FloorKind>("general");
  const [sheetKind, setSheetKind] = useState<SheetKind>("unspecified");
  const [revision, setRevision] = useState("");
  const [unit, setUnit] = useState<DrawingUnit>("unknown");
  const [inspection, setInspection] = useState<SourceInspection | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [inspectionError, setInspectionError] = useState("");
  const inspectionRequest = useRef(0);
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  function changePath(value: string) {
    inspectionRequest.current += 1;
    setPath(value);
    setInspection(null);
    setInspectionError("");
    setDiscipline("");
    setRole("");
    setFloor("GENEL");
    setFloorKind("general");
    setSheetKind("unspecified");
    setRevision("");
    setUnit("unknown");
    setInspecting(false);
  }

  async function inspectPath(value: string) {
    if (!value.trim()) return;
    const requestId = ++inspectionRequest.current;
    setInspecting(true);
    setInspectionError("");
    try {
      const result = await api.inspectSource(value.trim());
      if (requestId === inspectionRequest.current) {
        setInspection(result);
        if (result.suggested_discipline) setDiscipline(result.suggested_discipline);
        if (result.suggested_sheet_kind) setSheetKind(result.suggested_sheet_kind);
        if (result.suggested_discipline) setRole(defaultSourceRole(result.suggested_discipline, result.suggested_sheet_kind ?? "unspecified"));
        if (result.suggested_floor && result.suggested_floor_kind) {
          setFloor(result.suggested_floor);
          setFloorKind(result.suggested_floor_kind);
        }
      }
    } catch (error) {
      if (requestId === inspectionRequest.current) setInspectionError((error as Error).message);
    } finally {
      if (requestId === inspectionRequest.current) setInspecting(false);
    }
  }

  function chooseDiscipline(next: Discipline) {
    setDiscipline(next);
    setRole(defaultSourceRole(next, sheetKind));
  }

  async function chooseFile() {
    try {
      const selected = isTauri()
        ? await open({ multiple: false, filters: [{ name: "Proje kaynakları", extensions: ["dxf", "xlsx", "xls", "pdf"] }] })
        : (await api.selectFile("DXF, Excel veya PDF kaynak dosyasını seçin")).path;
      if (typeof selected === "string") {
        changePath(selected);
        await inspectPath(selected);
      }
    } catch (dialogError) {
      onError((dialogError as Error).message);
    }
  }

  async function addSource() {
    if (!path || !inspection || !discipline || !role.trim()) return;
    if (inspection.source_format === "dxf" && sheetKind === "unspecified") return;
    if (inspection.requires_unit_confirmation && unit === "unknown") return;
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
      changePath("");
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
        <div className="section-heading"><div><span className="eyebrow">1. ADIM · DOSYA EKLE</span><h2>Çizim veya çizelge seçin</h2></div><FilePlus2 size={21} /></div>
        <label>DXF, Excel veya PDF<div className="path-picker"><input value={path} onChange={(event) => changePath(event.target.value)} placeholder="Dosya seçin veya yolu yazın" /><button onClick={() => void chooseFile()}><FolderOpen size={17} /></button></div></label>
        {path && !inspection && <button className="button secondary source-inspect-button" disabled={inspecting} onClick={() => void inspectPath(path)}>{inspecting ? <LoaderCircle className="spin" size={16} /> : <Focus size={16} />}{inspecting ? "Dosya inceleniyor…" : "Dosyayı ön kontrol et"}</button>}
        {inspectionError && <div className="inline-error" role="alert">Ön kontrol başarısız: {inspectionError}</div>}
        {inspection && <div className={`source-inspection ${inspection.unit_conflict || inspection.requires_unit_confirmation ? "warning" : ""}`}><strong>Dosya ön kontrolü</strong>{inspection.source_format === "dxf" && <span>DXF başlığı: {inspection.header_unit === "unknown" ? "birim yok" : inspection.header_unit}{inspection.suggested_unit !== "unknown" && inspection.suggested_unit !== inspection.header_unit ? ` · Çizim kanıtı: ${inspection.suggested_unit} öneriyor` : ""}</span>}{inspection.source_format !== "dxf" && <span>{inspection.source_format.toUpperCase()} dosyası; çizim birimi uygulanmaz.</span>}{inspection.unit_evidence.slice(1).map((evidence, index) => <small key={index}>{evidence}</small>)}{inspection.suggested_discipline && <small>Önerilen alan: {disciplineLabel(inspection.suggested_discipline)} · {inspection.discipline_evidence.slice(0, 3).join(" / ")}</small>}{inspection.suggested_sheet_kind && <small>Önerilen pafta: {sheetKindLabel(inspection.suggested_sheet_kind, discipline || undefined)} · {inspection.sheet_evidence.slice(0, 3).join(" / ")}</small>}{inspection.suggested_floor && <small>Önerilen kat: {inspection.suggested_floor}</small>}{inspection.unit_conflict && <p>DXF başlığı çizim kanıtıyla çelişiyor. Birimi doğrulayın; özgün DXF değişmez.</p>}{inspection.requires_unit_confirmation && !inspection.unit_conflict && inspection.suggested_unit === "unknown" && <p>Birim kanıtı yeterli değil. Bilinen bir ölçüyle kontrol edip birimi seçin.</p>}</div>}
        {inspection?.suggested_discipline === "architectural" && discipline === "structural" && <div className="inline-error" role="alert">Bu paftanın başlıkları mimariyi gösteriyor. Statik kolon/kiriş araması için ayrı statik pafta ekleyin.</div>}
        <div className="form-row"><label>Proje alanı<select value={discipline} onChange={(event) => chooseDiscipline(event.target.value as Discipline)}><option value="">Seçiniz</option>{DISCIPLINES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Bu dosyada ne var?<select value={sheetKind} onChange={(event) => { const next = event.target.value as SheetKind; setSheetKind(next); if (discipline) setRole(defaultSourceRole(discipline, next)); }}>{SHEET_KINDS.map((item) => <option key={item.value} value={item.value}>{sheetKindLabel(item.value, discipline || undefined)}</option>)}</select></label></div>
        {inspection?.requires_unit_confirmation && <label className="source-unit-choice">Kullanılacak çizim birimi{inspection.suggested_unit !== "unknown" && inspection.unit_conflict && <button type="button" className="button secondary unit-suggestion" onClick={() => setUnit(inspection.suggested_unit)}>Önerilen {inspection.suggested_unit} birimini kullan</button>}<select value={unit} onChange={(event) => setUnit(event.target.value as DrawingUnit)}><option value="unknown">Ölçüye bakıp seçiniz</option><option value="mm">Milimetre (mm)</option><option value="cm">Santimetre (cm)</option><option value="m">Metre (m)</option></select><small>Bu seçim tüm dosyaya bir kez uygulanır ve hesaplara kaydedilir. Yazılı ölçülerle tutarsız mahaller ayrıca incelemeye kalır.</small></label>}
        <div className="form-row"><label>Kat adı<input value={floor} onChange={(event) => setFloor(event.target.value)} placeholder="Örn. Zemin Kat" /></label><label>Kat türü<select value={floorKind} onChange={(event) => setFloorKind(event.target.value as FloorKind)}>{FLOOR_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label></div>
        <details className="source-extra"><summary>Diğer dosya bilgileri <span>İsteğe bağlı</span></summary><div className="form-row three"><label>Pafta rolü<input value={role} onChange={(event) => setRole(event.target.value)} placeholder="kalıp / detay / mahal" /></label><label>Revizyon<input value={revision} onChange={(event) => setRevision(event.target.value)} placeholder="R00" /></label>{inspection?.source_format === "dxf" && !inspection.requires_unit_confirmation && <label>Çizim birimi<select value={unit} onChange={(event) => setUnit(event.target.value as DrawingUnit)}><option value="unknown">DXF'ten oku</option><option value="mm">mm</option><option value="cm">cm</option><option value="m">m</option></select></label>}</div><small>Çizim birimi çelişirse analizden önce onayınız istenir.</small></details>
        <small className="field-help">Tekrar eden katları gerekirse Gelişmiş araçlar bölümünde ayrıca tanımlayabilirsiniz.</small>
        <button className="button primary wide" disabled={!path || !inspection || !discipline || !role.trim() || !floor.trim() || (inspection.suggested_discipline === "architectural" && discipline === "structural") || (inspection.source_format === "dxf" && sheetKind === "unspecified") || (inspection.requires_unit_confirmation && unit === "unknown") || busy} onClick={() => void addSource()}>{busy ? <LoaderCircle className="spin" size={17} /> : <FilePlus2 size={17} />}Dosyayı ekle</button>
        <p className="hint">Dosya SHA-256 kimliğiyle proje klasörüne kopyalanır; özgün dosya değiştirilmez.</p>
      </section>
      <section className="panel source-list-panel">
        <div className="section-heading"><div><span className="eyebrow">PROJE KAYNAKLARI</span><h2>{sources.length} dosya hazır</h2></div><span className="count-badge">{sources.length}</span></div>
        <div className="source-list">
          {sources.length === 0 ? <EmptyState icon={<Boxes />} title="Henüz kaynak yok" detail="İlk DXF paftasını veya referans çizelgesini ekleyin." /> : sources.map((source) => <div className="source-row" key={source.id}><div className={`file-icon ${source.discipline}`}>{source.original_name.split(".").pop()?.toUpperCase()}</div><div className="source-main"><strong>{source.original_name}</strong><span>{disciplineLabel(source.discipline)} · {sheetKindLabel(source.sheet_kind, source.discipline)} · {floorKindLabel(source.floor_kind)} / {source.floor}</span><small>SHA {source.sha256.slice(0, 12)}</small></div><div className="source-actions"><select className="source-discipline" aria-label={`${source.original_name} disiplini`} value={source.discipline} disabled={updatingId === source.id} onChange={(event) => void changeDiscipline(source, event.target.value as Discipline)}>{DISCIPLINES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><div className={`unit-pill ${sourceStatusReady(source) ? "confirmed" : ""}`}>{sourceStatusLabel(source)}</div><button className="source-delete" aria-label={`${source.original_name} kaynağını sil`} title="Kaynağı sil" disabled={deletingId === source.id} onClick={() => void removeSource(source)}>{deletingId === source.id ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />}</button></div></div>)}
        </div>
        {setupIssueCount > 0 && <div className="source-setup-note"><AlertTriangle size={17} /><span>{setupIssueCount} dosyada birim, ölçek veya pafta görevi doğrulaması gerekiyor. Ölçü çıkarmadan önce bunları kontrol edeceğiz.</span></div>}
        <button className="button secondary next-button" disabled={sources.length === 0} onClick={onNext}>{setupIssueCount ? "Eksik ayarları kontrol et" : "Ölçüleri bul"} <ChevronRight size={16} /></button>
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

function UnitEvidenceCheck({ api, projectId, source }: { api: EngineApi; projectId: string; source: SourceFile }) {
  const [result, setResult] = useState<SourceInspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function inspect() {
    setBusy(true);
    setError("");
    try {
      setResult(await api.inspectProjectSource(projectId, source.id));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const independentEvidence = result && ["structural_sections", "architectural_area"].includes(result.unit_evidence_basis);
  return <div className="unit-evidence-check"><button type="button" className="unit-evidence-trigger" disabled={busy} onClick={() => void inspect()}>{busy ? "Ölçüler inceleniyor…" : "Birim kanıtını incele"}</button>{error && <small role="alert">{error}</small>}{result && <div className="unit-evidence-result"><strong>{independentEvidence && result.suggested_unit === source.drawing_unit ? `Seçilen ${source.drawing_unit} çizim kanıtıyla uyumlu` : independentEvidence ? `Yazılı ölçü/alan ${result.suggested_unit} öneriyor` : "Bağımsız birim kanıtı yetersiz"}</strong>{result.unit_evidence.map((evidence, index) => <small key={index}>{evidence}</small>)}{independentEvidence && result.suggested_unit !== source.drawing_unit && <small>Öneriyi uygulamak için yanındaki “Kullanılacak birim” alanından seçip analizi yeniden çalıştırın. Çelişen elemanlar kesin hesaba alınmaz.</small>}</div>}</div>;
}

function MappingView({ api, projectId, sources, onChanged, onError, onNext }: { api: EngineApi; projectId: string; sources: SourceFile[]; onChanged: () => void; onError: (message: string) => void; onNext: () => void }) {
  const dxfSources = sources.filter((source) => source.source_format === "dxf");
  const pdfSources = sources.filter((source) => source.source_format === "pdf");
  const unresolvedUnits = dxfSources.filter((source) => !source.unit_confirmed && source.detected_unit === "unknown" && !(source.discipline === "structural" && ["detail", "section", "elevation", "other"].includes(source.sheet_kind)));
  const unresolvedSheets = dxfSources.filter((source) => source.discipline === "structural" && source.sheet_kind === "unspecified");
  const unresolvedPdf = pdfSources.filter((source) => source.calibration_status !== "confirmed");
  const unresolvedCount = unresolvedUnits.length + unresolvedSheets.length + unresolvedPdf.length;
  const conflictingUnits = dxfSources.filter((source) => source.unit_confirmed && source.detected_unit !== "unknown" && source.drawing_unit !== source.detected_unit);
  return <div className="stack">
    <section className="callout"><Gauge size={22} /><div><strong>Pafta ve birim güvenlik kapısı</strong><p>DXF birimi ve pafta görevi açıkça eşlenir. Detay/kesit paftaları fiziksel eleman adedine girmez.</p></div><span className={unresolvedCount || conflictingUnits.length ? "risk" : "safe"}>{unresolvedCount ? `${unresolvedCount} karar gerekli` : conflictingUnits.length ? `${conflictingUnits.length} birim çelişkisi` : "Hazır"}</span></section>
    {conflictingUnits.length > 0 && <section className="callout warning"><AlertTriangle size={22} /><div><strong>DXF başlığı ile seçilen birim farklı</strong><p>{conflictingUnits.map((source) => `${source.original_name}: başlık ${source.detected_unit}, kullanılan ${source.drawing_unit}`).join(" · ")}. Kaynak ölçüsüyle kontrol etmeden kesin metrajı onaylamayın; özgün çizim değiştirilmedi.</p></div></section>}
    <section className="panel">
      <div className="section-heading"><div><span className="eyebrow">KAT VE PAFTA YÖNETİMİ</span><h2>Her dosyanın tek ve açık görevi</h2></div></div>
      <div className="sheet-mapping-list">{sources.map((source) => <SourceMappingEditor key={source.id} api={api} projectId={projectId} source={source} onChanged={onChanged} />)}</div>
    </section>
    {dxfSources.length > 0 && <section className="panel"><div className="section-heading"><div><span className="eyebrow">BİRİM DOĞRULAMA</span><h2>DXF kaynakları metre standardına dönüştürülür</h2></div></div><div className="mapping-table"><div className="mapping-head"><span>Kaynak</span><span>DXF algısı</span><span>Kullanılacak birim</span><span>Durum</span></div>{dxfSources.map((source) => { const conflict = source.unit_confirmed && source.detected_unit !== "unknown" && source.drawing_unit !== source.detected_unit; return <div className="mapping-row" key={source.id}><div><strong>{source.original_name}</strong><small>{source.floor} · {source.role}</small><UnitEvidenceCheck api={api} projectId={projectId} source={source} /></div><code>{source.detected_unit}</code><select value={source.unit_confirmed ? source.drawing_unit : source.detected_unit} onChange={async (event) => { const selected = event.target.value as DrawingUnit; if (selected !== "unknown") { try { await api.confirmUnit(projectId, source.id, selected); onChanged(); } catch (error) { onError((error as Error).message); } } }}><option value="unknown">Seçiniz</option><option value="mm">Milimetre</option><option value="cm">Santimetre</option><option value="m">Metre</option></select><span className={`status-dot-label ${conflict || (!source.unit_confirmed && source.detected_unit === "unknown") ? "warn" : "ok"}`}><i />{conflict ? "Çelişki · kontrol et" : source.unit_confirmed ? "Onaylandı" : source.detected_unit !== "unknown" ? "DXF değeri" : "Bekliyor"}</span></div>; })}</div></section>}
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
  const suspiciousArchitecturalRole = source.discipline === "architectural" && /kalıp|kalip/i.test(role);

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
    <div className="sheet-mapping-title"><div><strong>{source.original_name}</strong><small>{disciplineLabel(source.discipline)} · SHA {source.sha256.slice(0, 10)}</small></div><span className={`sheet-kind-pill ${sheetKind}`}>{sheetKindLabel(sheetKind, source.discipline)}</span></div>
    {suspiciousArchitecturalRole && <div className="mapping-advice"><AlertTriangle size={15} /><span>Disiplin “Mimari”, pafta rolü “kalıp” görünüyor. Bu dosya mimariyse rolü “Mimari uygulama planı” olarak düzeltin; statikse disiplinini kaynaklar ekranından değiştirin.</span><button className="button secondary" onClick={() => setRole("Mimari uygulama planı")}>Rolü öner</button></div>}
    {source.discipline === "architectural" && floor === "GENEL" && <div className="mapping-advice"><Layers3 size={15} /><span>Dosya düzeyindeki kat “GENEL”. Tek DXF’de plan, kesit ve çizelge birlikteyse bölge kanıtları analizde ayrı değerlendirilir; tamamını zorla Zemin Kat saymayın.</span></div>}
    <div className="sheet-mapping-grid">
      <label>Pafta türü<select value={sheetKind} onChange={(event) => setSheetKind(event.target.value as SheetKind)}>{SHEET_KINDS.map((item) => <option key={item.value} value={item.value}>{sheetKindLabel(item.value, source.discipline)}</option>)}</select></label>
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

function ReviewView({ api, projectId, sources, elements, assignments, warnings, hasSources, analysisActive, onSources, onMapping, onAnalyze, onReanalyze, onChanged, onError, onNext }: { api: EngineApi; projectId: string; sources: SourceFile[]; elements: DetectedElement[]; assignments: ArchitecturalAssignment[]; warnings: AnalysisWarning[]; hasSources: boolean; analysisActive: boolean; onSources: () => void; onMapping: () => void; onAnalyze: () => void; onReanalyze: () => void; onChanged: () => void; onError: (message: string) => void; onNext: () => void }) {
  const [disciplineScope, setDisciplineScope] = useState<"all" | "architectural" | "structural">("all");
  const [filter, setFilter] = useState<ReviewStatus | "all" | "evidence">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [floorFilter, setFloorFilter] = useState<string>("all");
  const [architectureTab, setArchitectureTab] = useState<"all" | "rooms" | "walls" | "openings" | "finishes">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bulkReason, setBulkReason] = useState("");
  const [reviewSearch, setReviewSearch] = useState("");
  const [visibleCardCount, setVisibleCardCount] = useState(30);
  const [busy, setBusy] = useState(false);
  const [resultMessage, setResultMessage] = useState("");
  const scopedElements = disciplineScope === "all" ? elements : elements.filter((item) => item.discipline === disciplineScope);
  const scopedSourceIds = new Set(sources.filter((source) => disciplineScope === "all" || source.discipline === disciplineScope).map((source) => source.id));
  const scopedWarnings = disciplineScope === "all" ? warnings : warnings.filter((item) => scopedSourceIds.has(item.source_id));
  const elementTypes = Array.from(new Set(scopedElements.map((item) => item.element_type)));
  const floors = Array.from(new Set(scopedElements.map((item) => item.floor))).sort((a, b) => a.localeCompare(b, "tr"));
  const floorElements = floorFilter === "all" ? scopedElements : scopedElements.filter((item) => item.floor === floorFilter);
  const filtered = scopedElements.filter((item) =>
    (filter === "evidence" ? item.properties.evidence_only === true : item.properties.evidence_only !== true && (filter === "all" || item.review_status === filter))
    && (typeFilter === "all" || item.element_type === typeFilter)
    && (floorFilter === "all" || item.floor === floorFilter)
    && (!reviewSearch.trim() || [item.source_handle, item.layer, item.floor, String(item.properties.room_code ?? ""), String(item.properties.element_label ?? "")].join(" ").toLocaleLowerCase("tr-TR").includes(reviewSearch.trim().toLocaleLowerCase("tr-TR")))
    && (architectureTab === "all"
      || (architectureTab === "rooms" && item.element_type === "room")
      || (architectureTab === "walls" && item.element_type === "wall")
      || (architectureTab === "openings" && ["door", "window"].includes(item.element_type))
      || (architectureTab === "finishes" && item.element_type === "finish_area"))
  );
  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0];
  const evidenceCount = floorElements.filter((item) => item.properties.evidence_only === true).length;
  const pending = floorElements.filter((item) => item.properties.evidence_only !== true && ["pending", "needs_review"].includes(item.review_status)).length;
  const readyForReview = floorElements.filter((item) => item.properties.evidence_only !== true && ["pending", "needs_review"].includes(item.review_status) && !item.issues.some((issue) => issue.startsWith("blocking:")) && item.required_inputs.every((key) => (item.measurements[key] ?? 0) > 0)).length;
  const unitBlocked = floorElements.filter((item) => item.issues.includes("blocking:drawing_unit_evidence_mismatch")).length;
  const unitWarning = scopedWarnings.find((item) => item.code === "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH" && sources.some((source) => source.id === item.source_id) && ["mm", "cm", "m"].includes(String(item.evidence?.suggested_unit)));
  const suggestedUnit = unitWarning?.evidence.suggested_unit as DrawingUnit | undefined;
  const roomAreaMismatch = floorElements.filter((item) => item.element_type === "room" && item.issues.includes("blocking:room_schedule_geometry_mismatch"));
  const grossNetCandidates = sources.filter((source) => source.discipline === "architectural").flatMap((source) => {
    const rooms = scopedElements.filter((item) => item.source_id === source.id && item.element_type === "room" && item.properties.schedule_evidence && item.properties.evidence_only !== true);
    const grossReference = Number(rooms[0]?.properties.reference_gross_area_m2 ?? 0);
    const scheduleReference = Number(rooms[0]?.properties.room_schedule_total_area_m2 ?? 0);
    const grossPlan = rooms.reduce((sum, item) => sum + Number(item.measurements.geometric_area_m2 ?? 0), 0);
    const scheduleNet = rooms.reduce((sum, item) => sum + Number(item.measurements.area_m2 ?? 0), 0);
    const waiting = rooms.filter((item) => item.issues.includes("blocking:room_schedule_geometry_mismatch"));
    if (rooms.length < 2 || waiting.length === 0 || grossReference <= scheduleReference * 1.01
      || rooms.some((item) => !item.properties.boundary_element_id)
      || Math.abs(grossPlan - grossReference) > Math.max(0.02, grossReference * 0.01)
      || Math.abs(scheduleNet - scheduleReference) > 0.02) return [];
    return [{ source, rooms: waiting, grossReference, grossPlan, scheduleNet,
      independentNet: Number(rooms[0]?.properties.reference_net_area_m2 ?? 0) }];
  });
  const roomBoundaryBlocked = floorElements.filter((item) => item.element_type === "room" && item.properties.evidence_only !== true && item.issues.includes("blocking:room_boundary_assignment_required"));
  const openingRelationBlocked = floorElements.filter((item) => ["door", "window"].includes(item.element_type) && item.issues.some((issue) => ["blocking:opening_host_wall_required", "blocking:opening_room_assignment_required", "blocking:opening_schedule_match_required"].includes(issue))).length;
  const dependentAreaBlocked = floorElements.filter((item) => item.issues.includes("blocking:opening_decision_required")).length;
  const orderedWarnings = [...scopedWarnings].sort((a, b) => ({ error: 0, warning: 1, info: 2 })[a.severity] - ({ error: 0, warning: 1, info: 2 })[b.severity]);
  const bulkEligible = filtered.filter((item) =>
    item.properties.evidence_only !== true && ["pending", "needs_review"].includes(item.review_status)
    && item.required_inputs.every((key) => Number.isFinite(item.measurements[key]) && item.measurements[key] > 0)
    && !item.issues.some((issue) => issue.startsWith("blocking:"))
    && !item.issues.includes("previous_acceptance_changed_after_reanalysis")
  );
  const quantityScopeElements = floorElements.filter((item) =>
    item.properties.evidence_only !== true && item.review_status !== "rejected" && (typeFilter === "all" || item.element_type === typeFilter)
  );
  const previewTotals = quantityPreviewTotals(quantityScopeElements);
  const approvedTotals = quantityPreviewTotals(
    quantityScopeElements.filter((item) => item.review_status === "accepted"),
  );
  const rebarElement = scopedElements.find((item) =>
    item.element_type === "rebar" && Array.isArray(item.properties.revision_candidates)
  );
  const revisionCandidates = (rebarElement?.properties.revision_candidates ?? []) as RebarRevisionCandidate[];
  const selectedRevisionHandle = scopedElements.find((item) =>
    item.element_type === "rebar" && item.properties.revision_selected === true
  )?.properties.table_handle as string | undefined;
  const reviewedElements = floorElements.filter((item) => item.properties.evidence_only !== true);
  const foundByType = [...new Set(reviewedElements.map((item) => item.element_type))].map((type) => ({
    type,
    count: reviewedElements.filter((item) => item.element_type === type).length,
    needsAction: reviewedElements.filter((item) => item.element_type === type && ["pending", "needs_review"].includes(item.review_status)).length,
  }));
  const structuralBlockers = structuralCompletionMessages(elements);
  const structuralSamples = ["raft", "shear_wall", "column", "slab", "beam", "rebar"].flatMap((type) => {
    const candidates = reviewedElements.filter((item) => item.element_type === type)
      .sort((a, b) => String(a.properties.element_label ?? a.source_handle).localeCompare(String(b.properties.element_label ?? b.source_handle), "tr"));
    return candidates.length ? [candidates[Math.floor((candidates.length - 1) / 2)]] : [];
  });

  function chooseDisciplineScope(next: "all" | "architectural" | "structural") {
    setDisciplineScope(next);
    setTypeFilter("all");
    setFloorFilter("all");
    setFilter("all");
    setArchitectureTab("all");
    setReviewSearch("");
    setSelectedId(null);
  }

  useEffect(() => {
    if (filtered[0] && !filtered.some((item) => item.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);
  useEffect(() => { setVisibleCardCount(30); }, [floorFilter, typeFilter, filter, architectureTab, reviewSearch]);

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
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function applyUnitSuggestion() {
    if (!unitWarning || !suggestedUnit || analysisActive) return;
    const source = sources.find((item) => item.id === unitWarning.source_id);
    if (!source) return;
    if (!window.confirm(`${source.original_name} için ${suggestedUnit} birimini kullanıp analizi yeniden çalıştıralım mı? Eski tespitler yedeklenir; özgün DXF değişmez.`)) return;
    setBusy(true);
    try {
      await api.confirmUnit(projectId, source.id, suggestedUnit);
      setResultMessage(`${suggestedUnit} birimi kaydedildi; analiz yeniden başlatılıyor.`);
      onChanged();
      onReanalyze();
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function approveScheduleNetBasis(candidate: (typeof grossNetCandidates)[number]) {
    const reason = `Mahal çizelgesi net ${formatQuantity(candidate.scheduleNet)} m²; eşlenen plan poligonları ${formatQuantity(candidate.grossPlan)} m² ve bağımsız bölüm brüt kanıtı ${formatQuantity(candidate.grossReference)} m² ile uzlaşıyor. Net alan kaynağı çizelge olarak seçildi.`;
    if (!window.confirm(`${candidate.rooms.length} mahalde çizelge alanı net, plan poligonları brüt kanıtı olarak kaydedilsin mi? Duvar kaplaması için net çevre ölçüsü ayrıca gerekecek.`)) return;
    setBusy(true);
    try {
      for (const room of candidate.rooms) {
        await api.createArchitecturalAssignment(projectId, {
          source_id: candidate.source.id,
          subject_element_id: room.id,
          kind: "room_area_basis",
          target_element_ids: [],
          values: { net_area_source: "schedule", plan_area_role: "gross" },
          approved: true,
          reviewer: "Mühendis",
          reason,
        });
      }
      setResultMessage(`${candidate.rooms.length} mahal için çizelge-net alan dayanağı kaydedildi. Bağımsız bölüm net alan farkı raporda kalır; donatı ve radye kilitleri değişmez.`);
      onChanged();
    } catch (error) {
      onChanged();
      onError((error as Error).message);
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
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (elements.length === 0) return <div className="stack"><section className="panel review-empty-panel"><div className="review-empty-icon"><Ruler size={26} /></div><span className="eyebrow">2. ADIM · ÖLÇÜLERİ KONTROL ET</span><h2>{analysisActive ? "Çizimler inceleniyor" : "Henüz incelenecek ölçü yok"}</h2><p>{analysisActive ? "Dosyalar işlenirken bu ekrandan ayrılabilirsiniz. Tespitler hazır olunca burada görünecek." : "Dosyaları ekleyip ölçüleri bulun. Bulunan elemanlar mühendis onayı olmadan kesin metraja girmez."}</p><button className="button primary" disabled={analysisActive} onClick={hasSources ? onAnalyze : onSources}>{analysisActive ? <LoaderCircle className="spin" size={16} /> : hasSources ? <Play size={16} fill="currentColor" /> : <FilePlus2 size={16} />}{analysisActive ? "Analiz sürüyor" : hasSources ? "Ölçüleri bul" : "Dosyaları ekle"}</button></section>{warnings.length > 0 && <section className="panel review-empty-warnings"><strong>Analiz uyarıları</strong>{warnings.map((warning) => <p key={warning.id}>{warning.message}</p>)}</section>}</div>;

  return <>
    <div className="discipline-switch" role="group" aria-label="İncelenecek proje alanı">
      {([ ["all", "Tümü"], ["architectural", "Mimari"], ["structural", "Statik"] ] as const).map(([value, label]) => {
        const count = elements.filter((item) => (value === "all" || item.discipline === value) && item.properties.evidence_only !== true).length;
        const sourceCount = sources.filter((source) => value === "all" || source.discipline === value).length;
        return <button key={value} type="button" className={disciplineScope === value ? "active" : ""} aria-pressed={disciplineScope === value} onClick={() => chooseDisciplineScope(value)}><strong>{label}</strong><span>{count} eleman · {sourceCount} dosya</span></button>;
      })}
    </div>
    <div className="review-layout">
    <section className="panel preview-panel">
      <div className="section-heading compact"><div><span className="eyebrow">DXF ÖNİZLEME · {disciplineScope === "all" ? "TÜMÜ" : disciplineLabel(disciplineScope)}</span><h2>Kaynak çizimi + tespitler</h2></div><span className="count-badge">{floorElements.length}</span></div>
      <GeometryPreview api={api} projectId={projectId} elements={scopedElements} selectedId={selected?.id} relatedIds={architecturalRelatedIds(selected)} onSelect={(id) => { if (scopedElements.find((item) => item.id === id)?.properties.evidence_only === true) { setFilter("evidence"); setFloorFilter("all"); setTypeFilter("all"); setArchitectureTab("all"); } setSelectedId(id); }} />
      <div className="legend"><span><i className="accepted" />Onaylı</span><span><i className="pending" />Bekliyor</span><span><i className="needs" />Eksik</span><span><i className="rejected" />Hariç</span></div>
      {scopedWarnings.length > 0 && <div className="warning-stack">{orderedWarnings.slice(0, 4).map((warning) => <div key={warning.id} className={`mini-warning ${warning.severity}`}><AlertTriangle size={15} /><span>{warning.message}</span></div>)}{orderedWarnings.length > 4 && <details className="more-warnings"><summary>Diğer {orderedWarnings.length - 4} uyarıyı göster</summary>{orderedWarnings.slice(4).map((warning) => <div key={warning.id} className={`mini-warning ${warning.severity}`}><AlertTriangle size={15} /><span>{warning.message}</span></div>)}</details>}</div>}
    </section>
    <section className="panel review-panel">
      <div className="review-toolbar">
        <div><span className="eyebrow">{disciplineScope === "all" ? "TÜM ALANLAR" : disciplineLabel(disciplineScope).toLocaleUpperCase("tr-TR")} · MÜHENDİS ONAYI</span><h2>Bulunan ölçüleri kontrol edin</h2><small>{pending} eleman incelemede · {readyForReview} ölçüsü tamam · {evidenceCount} yalnız kanıt izi</small></div>
        <div className="review-filters">
          <select value={floorFilter} onChange={(event) => { setFloorFilter(event.target.value); setFilter("all"); }}><option value="all">Tüm katlar</option>{floors.map((floor) => <option value={floor} key={floor}>{floor}</option>)}</select>
          <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setFilter("all"); }}><option value="all">Tüm türler</option>{elementTypes.map((type) => <option value={type} key={type}>{elementTypeLabel(type)}</option>)}</select>
          <select value={filter} onChange={(event) => setFilter(event.target.value as ReviewStatus | "all" | "evidence")}><option value="all">Tüm durumlar</option><option value="needs_review">Eksik bilgi</option><option value="pending">Onay bekliyor</option><option value="accepted">Onaylı</option><option value="rejected">Hariç</option><option value="evidence">Yalnız kanıt izleri</option></select>
        </div>
      </div>
      <div className="review-findings" aria-label="Analizde bulunan elemanlar"><div className="review-findings-title"><strong>Neler bulundu?</strong><small>{reviewedElements.length} metraj adayı · {evidenceCount} yalnız kaynak kanıtı; onaylananlar kesin hesaba girer</small></div><div className="review-findings-grid">{foundByType.map(({ type, count, needsAction }) => <button key={type} type="button" className={typeFilter === type ? "active" : ""} onClick={() => { setTypeFilter(typeFilter === type ? "all" : type); setArchitectureTab("all"); setFilter("all"); }}><strong>{count}</strong><span>{elementTypeLabel(type)}</span><small>{needsAction ? `${needsAction} kontrol bekliyor` : "Kontrol tamam"}</small></button>)}</div></div>
      {disciplineScope === "architectural" && grossNetCandidates.map((candidate) => <div className="gross-net-basis" key={candidate.source.id}><div><strong>Net alan ile brüt plan sınırını ayırın</strong><small>{candidate.rooms.length} mahal · çizelge neti {formatQuantity(candidate.scheduleNet)} m² · plan poligonları {formatQuantity(candidate.grossPlan)} m² · bağımsız bölüm brütü {formatQuantity(candidate.grossReference)} m²</small><small>{candidate.independentNet > 0 ? `Bağımsız bölüm neti ${formatQuantity(candidate.independentNet)} m² ile ${formatQuantity(Math.abs(candidate.independentNet - candidate.scheduleNet))} m² fark raporda korunur. ` : ""}Bu karar duvar kaplaması için net çevre üretmez.</small></div><button className="button secondary" disabled={busy} onClick={() => void approveScheduleNetBasis(candidate)}>Çizelge netini esas al</button></div>)}
      {disciplineScope === "structural" && <div className="structural-audit" aria-label="Statik pafta kontrolü">
        <div className="structural-audit-heading"><div><strong>Pafta ile örnek kontrol</strong><small>Her türden bir temsilci adayı açıp kaynak çizimde etiket, handle ve ölçüsünü karşılaştırın. Örnek kontrolü diğer elemanları otomatik onaylamaz.</small></div><span className={structuralBlockers.length ? "audit-locked" : "audit-ready"}>{structuralBlockers.length ? "Tam toplam kilitli" : "Kapsam engeli yok"}</span></div>
        {structuralBlockers.length > 0 && <div className="structural-audit-blockers">{structuralBlockers.map((message) => <small key={message}><AlertTriangle size={14} /> {message}</small>)}</div>}
        <div className="structural-audit-samples">{structuralSamples.map((sample) => <button key={sample.id} type="button" onClick={() => { setFloorFilter("all"); setFilter("all"); setTypeFilter(sample.element_type); setSelectedId(sample.id); }}><span>{elementTypeLabel(sample.element_type)} · {String(sample.properties.element_label || sample.source_handle || "etiket yok")}</span><strong>{measurementSummary(sample)}</strong><small>Kaynak handle: {sample.source_handle || "yok"} · çizimde göster →</small></button>)}</div>
      </div>}
      <div className="review-search"><input type="search" value={reviewSearch} onChange={(event) => setReviewSearch(event.target.value)} placeholder="Mahal kodu, eleman etiketi, katman veya handle ara" aria-label="Tespitlerde ara" /><span>{filtered.length} sonuç</span></div>
      {disciplineScope === "architectural" && <div className="architecture-tabs">{([
        ["all", "Tümü"], ["rooms", "Mahaller"], ["walls", "Duvarlar"],
        ["openings", "Kapı / Pencere"], ["finishes", "Kaplamalar"],
      ] as const).map(([value, label]) => <button key={value} className={architectureTab === value ? "active" : ""} onClick={() => { setArchitectureTab(value); setTypeFilter("all"); }}>{label}</button>)}</div>}
      {(unitBlocked > 0 || roomBoundaryBlocked.length > 0 || roomAreaMismatch.length > 0 || openingRelationBlocked > 0 || dependentAreaBlocked > 0) && <div className="review-triage" aria-label="Önce çözülecek ortak sorunlar">
        <strong>Önce ortak sorunları çözün</strong>
        {unitBlocked > 0 && <div><span><b>{unitBlocked} eleman · Dosya birimi</b><small>Tek bir kaynak birimi kararı bu elemanların hepsini etkiler.</small></span>{unitWarning && suggestedUnit ? <button className="button secondary" disabled={busy || analysisActive} onClick={() => void applyUnitSuggestion()}>Önerilen {suggestedUnit} ile yeniden analiz et</button> : <button className="button secondary" onClick={onMapping}>Birimleri kontrol et</button>}</div>}
        {roomBoundaryBlocked.length > 0 && <div><span><b>{roomBoundaryBlocked.length} mahal · Plan sınırı eşleşmedi</b><small>Asıl plan bölgesi önerilir; kopya ve detay çizimleri varsayılan listede gizlenir. Seçim alan uyumsuzluğunu tek başına düzeltmez.</small></span><button className="button secondary" onClick={() => { setFloorFilter("all"); setArchitectureTab("rooms"); setTypeFilter("all"); setFilter("needs_review"); setSelectedId(roomBoundaryBlocked[0].id); }}>Önerilen sınırları gör</button></div>}
        {roomAreaMismatch.length > 0 && <div><span><b>{roomAreaMismatch.length} mahal · Çizelge/çizim alanı farklı</b><small>{grossNetCandidates.length ? "Plan poligonları brüt toplamla eşleşiyor; çizelge net alan kararı yukarıda verilebilir." : "Alanlar aşağıda ayrı gösterilir; yanlış sınır veya eşleşme düzeltilmelidir."}</small></span><button className="button secondary" onClick={() => { setFloorFilter("all"); setArchitectureTab("rooms"); setTypeFilter("all"); setFilter("needs_review"); setSelectedId(roomAreaMismatch[0].id); }}>Mahalleri gör</button></div>}
        {openingRelationBlocked > 0 && <div><span><b>{openingRelationBlocked} açıklık · İlişki/çizelge kanıtı eksik</b><small>Kapı ve pencerelerin duvar, mahal veya tip eşleşmesini kontrol edin.</small></span><button className="button secondary" onClick={() => { setFloorFilter("all"); setArchitectureTab("openings"); setTypeFilter("all"); setFilter("needs_review"); }}>Açıklıkları gör</button></div>}
        {dependentAreaBlocked > 0 && <div><span><b>{dependentAreaBlocked} duvar/kaplama · Açıklık kararı bekliyor</b><small>Kapı veya pencere onaylanmadan/reddedilmeden bağlı net alan kesinleşmez.</small></span><button className="button secondary" onClick={() => { setFloorFilter("all"); setArchitectureTab("openings"); setTypeFilter("all"); setFilter("all"); }}>Kapı/pencereleri incele</button></div>}
      </div>}
      {revisionCandidates.length > 1 && (typeFilter === "all" || typeFilter === "rebar") && <div className="revision-picker"><div><strong>Donatı revizyonunu seçin</strong><small>Seçim yapılmadan donatı kesin toplama giremez.</small></div>{revisionCandidates.map((candidate) => <button key={candidate.table_handle} className={selectedRevisionHandle === candidate.table_handle ? "selected" : ""} disabled={busy} onClick={() => void chooseRevision(candidate)}><span>Revizyon {candidate.label}</span><strong>{formatQuantity(candidate.declared_total_kg)} kg</strong><small>{candidate.row_count} poz · formül {formatQuantity(candidate.calculated_total_kg)} kg</small></button>)}</div>}
      <div className="review-subtotals">{previewTotals.map((total) => { const approved = approvedTotals.find((item) => item.key === total.key)?.value ?? 0; return <div key={total.key}><span>{total.category}</span><strong>{formatQuantity(approved)} <small>{total.unit}</small></strong><small>Aday: {formatQuantity(total.value)} {total.unit}</small></div>; })}{previewTotals.length === 0 && <div><span>Ara toplam</span><strong>—</strong><small>Hesaplanabilir eleman yok</small></div>}</div>
      {typeFilter !== "all" && <div className="comparison-wrap"><div className="comparison-head"><strong>{elementTypeLabel(typeFilter)} karşılaştırması</strong><span>{filtered.length} satır</span></div><div className="comparison-table"><div className="comparison-row head"><span>Eleman</span><span>Ölçüler</span><span>Hesap adayı</span><span>Durum</span></div>{filtered.map((element) => <button className={`comparison-row ${selected?.id === element.id ? "selected" : ""}`} key={element.id} onClick={() => setSelectedId(element.id)}><span><strong>{String(element.properties.element_label || elementTypeLabel(element.element_type))}</strong><small>{element.source_handle}</small></span><span>{measurementSummary(element)}</span><span>{quantitySummary(element)}</span><span className={`table-status ${element.review_status}`}>{reviewStatusLabel(element)}</span></button>)}</div></div>}
      <div className="element-strip">{filtered.slice(0, visibleCardCount).map((element) => <button key={element.id} className={selected?.id === element.id ? "selected" : ""} onClick={() => setSelectedId(element.id)}><span className={`status-pin ${element.review_status}`} /><strong>{elementTypeLabel(element.element_type)}{element.properties.element_label ? ` · ${String(element.properties.element_label)}` : ""}</strong><small>{element.floor} · {element.layer}</small></button>)}</div>
      {filtered.length > visibleCardCount && <button className="button secondary more-elements" onClick={() => setVisibleCardCount((count) => count + 30)}>{Math.min(30, filtered.length - visibleCardCount)} eleman daha göster</button>}
      {typeFilter !== "all" && <div className="bulk-review"><div><strong>Güvenli toplu onay</strong><small>{bulkEligible.length} görünür eleman uygun; eksik/engelli satırlar dahil edilmez.</small></div><input value={bulkReason} onChange={(event) => setBulkReason(event.target.value)} placeholder="Pafta ve kontrol gerekçesi…" /><button className="button primary" disabled={busy || bulkEligible.length === 0 || bulkReason.trim().length < 3} onClick={() => void bulkAccept()}><Check size={16} /> {bulkEligible.length} elemanı onayla</button></div>}
      {resultMessage && <div className="inline-result"><Check size={15} />{resultMessage}</div>}
      {selected ? <ElementReview api={api} projectId={projectId} element={selected} allElements={elements} assignments={assignments} onChanged={onChanged} onReanalyze={onReanalyze} onError={onError} /> : <EmptyState icon={<Ruler />} title="Bu filtrede tespit yok" detail="Tür veya durum filtresini değiştirin." />}
      <div className="review-footer"><span>{scopedElements.filter((item) => item.review_status === "accepted").length} onaylı eleman kesin metraja girecek.</span><button className="button secondary" onClick={onNext}>Kesin metrajı gör <ChevronRight size={16} /></button></div>
    </section>
  </div></>;
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

function structuralCompletionMessages(elements: DetectedElement[]) {
  const structural = elements.filter((item) => item.discipline === "structural" && item.properties.evidence_only !== true);
  if (!structural.length) return [];
  const messages: string[] = [];
  const unresolvedUnits = structural.filter((item) => item.issues.includes("blocking:drawing_unit_evidence_mismatch"));
  if (unresolvedUnits.length) messages.push(`${unresolvedUnits.length} statik elemanda çizim birimi kanıtı çelişiyor.`);
  const incompleteRafts = structural.filter((item) => item.element_type === "raft" && item.review_status !== "rejected" && !(item.measurements.thickness_m > 0));
  if (incompleteRafts.length) messages.push(`${incompleteRafts.length} radye temelde kalınlık kanıtı eksik.`);
  const rebars = structural.filter((item) => item.element_type === "rebar");
  if (!rebars.length) messages.push("Donatı detayı veya çizelgesi bulunmadı.");
  else if (rebars.some((item) => Array.isArray(item.properties.revision_candidates) && item.properties.revision_candidates.length > 1)
    && !rebars.some((item) => item.properties.revision_selected === true)) messages.push("Güncel donatı revizyonu seçilmedi.");
  return messages;
}

function quantitySummary(element: DetectedElement) {
  const lines = quantityPreview(element);
  return lines.length ? lines.map((line) => `${line.category}: ${formatQuantity(line.value)} ${line.unit}`).join(" · ") : "Hesap dışında";
}

function ElementReview({ api, projectId, element, allElements, assignments, onChanged, onReanalyze, onError }: { api: EngineApi; projectId: string; element: DetectedElement; allElements: DetectedElement[]; assignments: ArchitecturalAssignment[]; onChanged: () => void; onReanalyze: () => void; onError: (message: string) => void }) {
  const needsSill = ["door", "window"].includes(element.element_type) && allElements.some((item) => item.element_type === "finish_area" && item.properties.band_bottom_m !== null && item.properties.band_bottom_m !== undefined && Array.isArray(item.properties.opening_element_ids) && item.properties.opening_element_ids.includes(element.id));
  const keys = needsSill ? [...new Set([...element.required_inputs, "sill_height_m"])] : element.required_inputs;
  const [values, setValues] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [relationReason, setRelationReason] = useState("");
  const [hostWallId, setHostWallId] = useState("");
  const [roomIds, setRoomIds] = useState<string[]>([]);
  const [boundaryId, setBoundaryId] = useState("");
  const [showAlternativeRegions, setShowAlternativeRegions] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setValues(Object.fromEntries(keys.map((key) => [key, element.measurements[key]?.toString() ?? ""])));
    setReason("");
    setRelationReason("");
    setHostWallId(String(element.properties.host_wall_id ?? ""));
    setRoomIds((element.properties.adjacent_room_ids as string[] | undefined) ?? []);
    setBoundaryId(String(element.properties.boundary_element_id ?? ""));
    setShowAlternativeRegions(false);
  }, [element]);
  async function decide(status: ReviewStatus) {
    setBusy(true);
    try {
      const overrides = Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== "" && Number(value) !== element.measurements[key]).map(([key, value]) => [key, Number(value)]));
      if (Object.keys(overrides).length > 0 && reason.trim().length < 3) throw new Error("Elle girilen ölçü için kontrol edilen pafta ve gerekçeyi yazın.");
      const reviewReason = element.issues.includes("previous_acceptance_changed_after_reanalysis") && status === "accepted"
        ? reason.trim()
        : reason || (status === "accepted" ? "Geometri ve ölçüler kontrol edildi" : "Mühendis kararı");
      await api.review(projectId, element.id, status, overrides, reviewReason);
      onChanged();
    } catch (error) {
      onError((error as Error).message);
    } finally { setBusy(false); }
  }
  async function saveRelation(kind: "room_boundary" | "opening_host" | "opening_rooms", targets: string[]) {
    if (relationReason.trim().length < 3 || targets.length === 0) return;
    setBusy(true);
    try {
      await api.createArchitecturalAssignment(projectId, {
        source_id: element.source_id,
        subject_element_id: element.id,
        kind,
        target_element_ids: targets,
        approved: true,
        reviewer: "Mühendis",
        reason: relationReason.trim(),
      });
      onChanged();
      if (kind === "room_boundary") onReanalyze();
    } catch (error) {
      onError((error as Error).message);
    } finally { setBusy(false); }
  }
  const missing = element.required_inputs.filter((key) => !values[key] || Number(values[key]) <= 0);
  const hasManualChanges = Object.entries(values).some(([key, value]) => value !== "" && Number(value) !== element.measurements[key]);
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
  const foundationWallEvidence = element.properties.foundation_wall_evidence as {
    annotation_text: string;
    annotation_handle: string;
    hatch_handle: string;
    translated_copy_count: number;
  } | undefined;
  const scheduleEvidence = element.properties.schedule_evidence as {
    table_handle: string;
    table_block: string;
    row_number: number;
    declared_area_text: string;
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
  const relationAssignments = assignments.filter((item) => item.subject_element_id === element.id && item.approved);
  const preferredPlanRegion = String(element.properties.preferred_plan_region_id ?? "");
  const storedBoundaryCandidates = (Array.isArray(element.properties.boundary_candidates) ? element.properties.boundary_candidates : []) as { id: string; room_code: string; area_m2: number; source_handle: string; plan_region_id: string; preferred_plan_region?: boolean }[];
  const visibleBoundaryCandidates = allElements.filter((item) => item.source_id === element.source_id && item.discipline === "architectural" && item.element_type === "room" && item.id !== element.id && item.geometry.kind === "room_boundary" && Boolean(item.properties.boundary_method)).map((item) => ({ id: item.id, room_code: String(item.properties.room_code ?? ""), area_m2: item.measurements.area_m2 ?? 0, source_handle: item.source_handle, plan_region_id: String(item.properties.plan_region_id ?? ""), preferred_plan_region: Boolean(preferredPlanRegion && item.properties.plan_region_id === preferredPlanRegion) }));
  const boundaryCandidates = [...new Map([...storedBoundaryCandidates, ...visibleBoundaryCandidates].map((item) => [item.id, item])).values()].sort((a, b) => {
    const preferredRank = Number(b.preferred_plan_region) - Number(a.preferred_plan_region);
    if (preferredRank) return preferredRank;
    const roomCode = String(element.properties.room_code ?? "");
    const codeRank = Number(b.room_code === roomCode) - Number(a.room_code === roomCode);
    if (codeRank) return codeRank;
    const targetArea = element.measurements.area_m2 ?? 0;
    return Math.abs(a.area_m2 - targetArea) - Math.abs(b.area_m2 - targetArea);
  });
  const displayedBoundaryCandidates = showAlternativeRegions || !preferredPlanRegion ? boundaryCandidates : boundaryCandidates.filter((item) => item.preferred_plan_region);
  const hasMatchingBoundaryCandidate = boundaryCandidates.filter((item) => !preferredPlanRegion || item.preferred_plan_region).some((item) => {
    const scheduledArea = element.measurements.area_m2 ?? 0;
    return scheduledArea > 0 && Math.abs(item.area_m2 - scheduledArea) / scheduledArea <= 0.01;
  });
  const wallCandidates = allElements.filter((item) => item.discipline === "architectural" && item.element_type === "wall");
  const roomCandidates = allElements.filter((item) => item.discipline === "architectural" && item.element_type === "room" && item.properties.evidence_only !== true);
  const blockingMessage = elementBlockingMessage(element, blocking);
  return (
    <div className="element-review">
      <div className="element-title">
        <div>
          <span className={`status-tag ${element.review_status}`}>{reviewStatusLabel(element)}</span>
          <h3>{elementTypeLabel(element.element_type)}{elementLabel ? ` · ${elementLabel}` : ""}</h3>
          <p>{element.floor} · {element.layer} · Handle {element.source_handle || "—"}</p>
        </div>
        <div className="confidence" title={`Tespit puanı %${Math.round(element.confidence * 100)}; bu puan ölçü doğruluğu veya mühendis onayı değildir.`}><span>Kaynak kanıtı</span><strong>{element.properties.evidence_only === true ? "Çizim izi" : element.properties.schedule_evidence ? "Çizelge" : element.properties.beam_section_evidence || element.properties.height_evidence ? "Kesit" : element.properties.boundary_element_id ? "Plan sınırı" : "Geometri"}</strong></div>
      </div>
      {missing.length > 0 && (
        <div className="missing-note"><AlertTriangle size={17} /><span>Kesin hesap için eksik: {missing.map((key) => measurementLabel(element.element_type, key)).join(", ")}</span></div>
      )}
      {blocking.length > 0 && (
        <div className="missing-note"><AlertTriangle size={17} /><span>{blockingMessage}</span></div>
      )}
      {element.issues.includes("previous_acceptance_changed_after_reanalysis") && (
        <div className="missing-note"><AlertTriangle size={17} /><span>Ölçü veya geometri son analizde değişti. Kaynak paftayı yeniden kontrol edip bu elemanı ayrı onaylayın.</span></div>
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
        <div className="evidence-note"><Ruler size={17} /><span><strong>Radye temel sınırı</strong>{formatQuantity(element.measurements.area_m2)} m² · {element.measurements.thickness_m ? `${formatQuantity(element.measurements.thickness_m * 100)} cm` : "kalınlık bekleniyor"}<small>Aynı biçimli {foundationEvidence.translated_copy_count} çizim tek adayda birleştirildi; {foundationEvidence.boundary_handles.length} sınır ve {foundationEvidence.thickness_note_handles.length} kalınlık notu bağlı.</small></span></div>
      )}
      {foundationWallEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Temel perdesi ölçü etiketi</strong>{foundationWallEvidence.annotation_text}<small>Etiket {foundationWallEvidence.annotation_handle} · tarama {foundationWallEvidence.hatch_handle} · {foundationWallEvidence.translated_copy_count} eş çizim tek sayıldı.</small></span></div>
      )}
      {scheduleEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Mahal çizelgesi · {String(element.properties.room_name ?? "")}</strong>{scheduleEvidence.declared_area_text}<small>Tablo {scheduleEvidence.table_handle} · satır {scheduleEvidence.row_number}{element.properties.floor_finish ? ` · döşeme: ${String(element.properties.floor_finish)}` : ""}</small></span></div>
      )}
      {element.element_type === "room" && scheduleEvidence && <div className={`room-area-check ${element.issues.includes("blocking:room_schedule_geometry_mismatch") ? "mismatch" : ""}`}>
        <strong>{element.properties.room_area_basis === "schedule_net_gross_plan" ? "Onaylı net/brüt alan dayanağı" : "Çizelge–plan alan kontrolü"}</strong>
        <span>Çizelge neti <b>{formatQuantity(element.measurements.area_m2 ?? 0)} m²</b> · Plan poligonu <b>{element.measurements.geometric_area_m2 ? `${formatQuantity(element.measurements.geometric_area_m2)} m²` : "eşleşmedi"}</b></span>
        {element.properties.room_area_basis === "schedule_net_gross_plan" ? <small>Plan poligonu brüt alan payı olarak tutulur; net mahal metrajı çizelgeye dayanır. Duvar kaplaması için ayrıca net çevre gerekir.</small> : typeof element.properties.area_difference_ratio === "number" && <small>Fark %{formatQuantity(element.properties.area_difference_ratio * 100)} · {element.properties.gross_net_basis_available ? "Brüt/net ayrımı için ortak kaynak kararı bekliyor." : "İzin verilen en fazla %1; sınır ve mahal eşleşmesini doğrulayın."}</small>}
        {Boolean(element.properties.boundary_source_handle) && <small>Sınır handle {String(element.properties.boundary_source_handle)} · çizim bölgesi {String(element.properties.plan_region_id || "belirsiz")}</small>}
      </div>}
      {stairEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Merdiven planı · {stairEvidence.label}</strong>{stairEvidence.step_count} rıhtım · {formatQuantity(stairEvidence.tread_m * 100)}/{formatQuantity(stairEvidence.riser_m * 100)} cm · toplam yükselme {formatQuantity(element.measurements.total_rise_m)} m<small>{stairEvidence.repeat_definition_required ? "Tip merdiven; kat aralığı tekrarı kullanıcı tarafından tanımlanmalı." : stairEvidence.scope_text}</small></span></div>
      )}
      {rebarEvidence && (
        <div className="evidence-note"><Ruler size={17} /><span><strong>Açık donatı metraj satırı · Poz {rebarEvidence.position_number}</strong>Pafta {formatQuantity(rebarEvidence.declared_weight_kg)} kg · formül kontrolü {formatQuantity(rebarEvidence.calculated_weight_kg)} kg<small>Kapsam {rebarEvidence.rebar_scope_labels[0]}–{rebarEvidence.rebar_scope_labels.at(-1)} · tablo handle {rebarEvidence.table_handle}</small></span></div>
      )}
      {element.properties.evidence_only === true && <div className="evidence-note"><Ruler size={17} /><span><strong>Yalnız çizim kanıtı</strong>Bu iz bağımsız metraj satırı değildir. Eşleştirilebilen fiziksel sınır veya açıklık, ilgili mahal/kapı kararında kullanılabilir.</span></div>}
      {element.discipline === "architectural" && element.properties.evidence_only !== true && <div className="architectural-relations">
        <div><strong>Mimari ilişki kararları</strong><small>{relationAssignments.length ? `${relationAssignments.length} gerekçeli karar kayıtlı` : "Eksik bağlantılar kesin metrajı engeller."}</small></div>
        {element.element_type === "room" && (element.issues.includes("blocking:room_boundary_assignment_required") || element.issues.includes("blocking:room_schedule_geometry_mismatch")) && (boundaryCandidates.length ? <><div className="relation-row"><label>Alternatif plan sınırı<select value={boundaryId} onChange={(event) => setBoundaryId(event.target.value)}><option value="">Sınır seçin</option>{displayedBoundaryCandidates.map((item) => <option value={item.id} key={item.id}>{item.room_code || "Kod yok"} · {formatQuantity(item.area_m2)} m² · {item.plan_region_id || "genel"} · {item.source_handle}</option>)}</select></label><button className="button secondary" disabled={busy || !boundaryId || relationReason.trim().length < 3} onClick={() => void saveRelation("room_boundary", [boundaryId])}>Sınırı bağla ve yeniden analiz et</button></div>{preferredPlanRegion && boundaryCandidates.length > displayedBoundaryCandidates.length && <button className="button secondary" onClick={() => setShowAlternativeRegions(true)}>Kopya/detay bölgelerindeki {boundaryCandidates.length - displayedBoundaryCandidates.length} adayı da göster</button>}</> : <div className="relation-row"><span>Plan sınırı adayları henüz kayıtlı değil.</span><button className="button secondary" disabled={busy} onClick={onReanalyze}>Adayları yeniden tara</button></div>)}
        {element.element_type === "room" && boundaryCandidates.length > 0 && !hasMatchingBoundaryCandidate && <small>Mevcut sınır adaylarının hiçbiri çizelge alanıyla %1 içinde uyuşmuyor. Sınır seçimi tek başına bu mahali kesin metraja açmaz; plan geometrisi ayrıca doğrulanmalı.</small>}
        {["door", "window"].includes(element.element_type) && <>
          <div className="relation-row"><label>Taşıyıcı duvar<select value={hostWallId} onChange={(event) => setHostWallId(event.target.value)}><option value="">Duvar seçin</option>{wallCandidates.map((item) => <option value={item.id} key={item.id}>{item.source_handle} · {formatQuantity(item.measurements.length_m ?? 0)} m</option>)}</select></label><button className="button secondary" disabled={busy || !hostWallId || relationReason.trim().length < 3} onClick={() => void saveRelation("opening_host", [hostWallId])}>Duvara bağla</button></div>
          <div className="relation-row"><label>Komşu mahaller<select multiple value={roomIds} onChange={(event) => setRoomIds(Array.from(event.target.selectedOptions).map((option) => option.value).slice(0, 2))}>{roomCandidates.map((item) => <option value={item.id} key={item.id}>{String(item.properties.room_code || item.properties.room_name || item.source_handle)}</option>)}</select></label><button className="button secondary" disabled={busy || roomIds.length === 0 || relationReason.trim().length < 3} onClick={() => void saveRelation("opening_rooms", roomIds)}>Mahallere bağla</button></div>
        </>}
        {(element.element_type === "room" || ["door", "window"].includes(element.element_type)) && <label>İlişki gerekçesi<input value={relationReason} onChange={(event) => setRelationReason(event.target.value)} placeholder="Kontrol edilen plan/çizelge…" /></label>}
        {element.element_type === "finish_area" && <div className="finish-policy"><span><strong>{String(element.properties.surface_type ?? "Yüzey")}</strong> · {String(element.properties.material ?? "Malzeme bekleniyor")}</span><small>Brüt {formatQuantity(element.measurements.gross_area_m2 ?? 0)} m² − açıklık {formatQuantity(element.measurements.opening_area_m2 ?? 0)} m² = net {formatQuantity(element.measurements.net_area_m2 ?? 0)} m²</small><small>Politika: {String(element.properties.calculation_policy ?? "—")}</small></div>}
      </div>}
      <div className="measurement-grid">
        {keys.map((key) => (
          <label key={key}>{measurementLabel(element.element_type, key)}<input type="number" min="0" step="any" disabled={element.properties.evidence_only === true} value={values[key] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} className={!values[key] && element.required_inputs.includes(key) ? "required" : ""} /></label>
        ))}
      </div>
      {element.properties.evidence_only !== true && <label>Karar gerekçesi<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Kontrol edilen pafta, kesit veya düzeltme notu…" /></label>}
      {element.properties.evidence_only !== true && <div className="decision-actions">
        <button className="button danger-ghost" disabled={busy} onClick={() => void decide("rejected")}><CircleStop size={16} />Hariç tut</button>
        <button className="button primary" disabled={busy || missing.length > 0 || blocking.length > 0 || ((hasManualChanges || element.issues.includes("previous_acceptance_changed_after_reanalysis")) && reason.trim().length < 3)} onClick={() => void decide("accepted")}><Check size={16} />Onayla ve hesaba kat</button>
      </div>}
    </div>
  );
}

type PreviewBounds = [number, number, number, number];
type PreviewMode = "context" | "selected" | "all";

function elementBounds(elements: DetectedElement[]): PreviewBounds {
  const boxes = elements
    .map((item) => item.geometry.bbox)
    .filter((box): box is PreviewBounds => box !== null && box.every(Number.isFinite));
  if (!boxes.length) return [0, 0, 100, 100];
  return [
    Math.min(...boxes.map((box) => box[0])),
    Math.min(...boxes.map((box) => box[1])),
    Math.max(...boxes.map((box) => box[2])),
    Math.max(...boxes.map((box) => box[3])),
  ];
}

function surroundingBounds(box: PreviewBounds): PreviewBounds {
  const centerX = (box[0] + box[2]) / 2;
  const centerY = (box[1] + box[3]) / 2;
  const width = Math.max(14, (box[2] - box[0]) * 1.8);
  const height = Math.max(14, (box[3] - box[1]) * 1.8);
  return [centerX - width / 2, centerY - height / 2, centerX + width / 2, centerY + height / 2];
}

function elementRegionId(element: DetectedElement) {
  const stored = element.properties.plan_region_id;
  if (typeof stored === "string" && stored) return stored;
  const boundaryHandle = element.properties.boundary_source_handle;
  const handle = typeof boundaryHandle === "string" ? boundaryHandle : element.source_handle;
  return handle.includes("/") ? handle.split("/", 1)[0] : "";
}

function previewRegionId(elements: DetectedElement[], selected?: DetectedElement) {
  if (!selected) return "";
  const direct = elementRegionId(selected);
  if (direct) return direct;
  const roomId = selected.properties.room_id;
  const room = typeof roomId === "string" ? elements.find((item) => item.id === roomId) : undefined;
  if (room && elementRegionId(room)) return elementRegionId(room);
  const counts = new Map<string, number>();
  elements.filter((item) => item.source_id === selected.source_id && item.geometry.bbox && item.element_type !== "finish_area").forEach((item) => {
    const region = elementRegionId(item);
    if (region) counts.set(region, (counts.get(region) ?? 0) + 1);
  });
  return [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
}

function architecturalRelatedIds(element?: DetectedElement) {
  if (!element || element.discipline !== "architectural") return [];
  const values = [
    element.properties.room_id,
    element.properties.boundary_element_id,
    element.properties.host_wall_id,
    ...(Array.isArray(element.properties.adjacent_room_ids) ? element.properties.adjacent_room_ids : []),
  ];
  return values.filter((value): value is string => typeof value === "string" && Boolean(value));
}

function GeometryPreview({ api, projectId, elements, selectedId, relatedIds = [], onSelect }: { api: EngineApi; projectId: string; elements: DetectedElement[]; selectedId?: string; relatedIds?: string[]; onSelect: (id: string) => void }) {
  const drawingElements = useMemo(
    () => elements.filter((item) => item.element_type !== "finish_area" && !item.geometry.kind.endsWith("_schedule_row") && Boolean(item.geometry.bbox)),
    [elements],
  );
  const selectedElement = elements.find((item) => item.id === selectedId);
  const selectedDrawing = drawingElements.find((item) => item.id === selectedId);
  const selectedFocusBounds = selectedDrawing?.geometry.bbox ? surroundingBounds(selectedDrawing.geometry.bbox) : undefined;
  const sourceId = selectedElement?.source_id ?? "";
  const suggestedRegionId = previewRegionId(elements, selectedElement);
  const [manualRegionId, setManualRegionId] = useState<string | null>(null);
  const regionId = manualRegionId ?? suggestedRegionId;
  const regions = useMemo(() => {
    const counts = new Map<string, number>();
    drawingElements.filter((item) => item.source_id === sourceId).forEach((item) => {
      const id = elementRegionId(item);
      if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
    });
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [drawingElements, sourceId]);
  const contextElements = drawingElements.filter((item) => item.source_id === sourceId && (regionId ? elementRegionId(item) === regionId : true));
  const [mode, setMode] = useState<PreviewMode>("selected");
  const [zoom, setZoom] = useState(1);
  const [rawDrawing, setRawDrawing] = useState<SourceDrawingPreview | null>(null);
  const [rawError, setRawError] = useState("");
  const [rawLoading, setRawLoading] = useState(false);
  const [rawLoadingMore, setRawLoadingMore] = useState(false);
  const [showLabels, setShowLabels] = useState(false);
  const [showLayers, setShowLayers] = useState(false);
  const [hiddenRoles, setHiddenRoles] = useState<string[]>([]);
  const [hiddenLayers, setHiddenLayers] = useState<string[]>([]);
  const [layerSearch, setLayerSearch] = useState("");
  const [pan, setPan] = useState<[number, number]>([0, 0]);
  const dragStart = useRef<{ x: number; y: number; pan: [number, number] } | null>(null);
  useEffect(() => {
    setManualRegionId(null);
    setMode("selected");
    setZoom(1);
    setPan([0, 0]);
  }, [selectedId]);
  useEffect(() => { setHiddenLayers([]); setLayerSearch(""); }, [sourceId]);
  useEffect(() => {
    let current = true;
    setRawDrawing(null);
    setRawError("");
    if (!sourceId) return () => { current = false; };
    setRawLoading(true);
    void api.sourcePreview(projectId, sourceId, regionId, 0, mode === "selected" ? selectedFocusBounds : undefined).then((drawing) => {
      if (current) setRawDrawing(drawing);
    }).catch((error: Error) => {
      if (current) setRawError(error.message);
    }).finally(() => {
      if (current) setRawLoading(false);
    });
    return () => { current = false; };
  }, [api, projectId, sourceId, regionId, mode, selectedId]);
  const layerCounts = useMemo(() => {
    const counts = new Map<string, number>();
    rawDrawing?.strokes.forEach((stroke) => counts.set(stroke.layer || "0", (counts.get(stroke.layer || "0") ?? 0) + 1));
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [rawDrawing]);
  async function loadMoreDrawing() {
    if (!sourceId || !rawDrawing?.next_offset || rawLoadingMore) return;
    const offset = rawDrawing.next_offset;
    setRawLoadingMore(true);
    try {
      const page = await api.sourcePreview(projectId, sourceId, regionId, offset, mode === "selected" ? selectedFocusBounds : undefined);
      setRawDrawing((current) => {
        if (!current || current.source_id !== sourceId || current.region_id !== regionId || current.next_offset !== offset) return current;
        const a = current.bounds;
        const b = page.bounds;
        return { ...current, strokes: [...current.strokes, ...page.strokes],
          bounds: a && b ? [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])] : a ?? b,
          truncated: page.truncated, next_offset: page.next_offset };
      });
    } catch (error) { setRawError(error instanceof Error ? error.message : String(error)); }
    finally { setRawLoadingMore(false); }
  }
  const visibleElements = mode === "all"
    ? drawingElements
    : mode === "selected" && selectedDrawing
      ? [selectedDrawing]
      : contextElements;
  const rawVisible = mode !== "all" && Boolean(rawDrawing);
  const focusBounds = mode === "selected" && selectedFocusBounds
    ? selectedFocusBounds
    : mode === "context" && rawDrawing?.bounds ? rawDrawing.bounds : elementBounds(visibleElements);
  const [x1, y1, x2, y2] = focusBounds;
  const baseWidth = Math.max(x2 - x1, 0.5);
  const baseHeight = Math.max(y2 - y1, 0.5);
  const centerX = (x1 + x2) / 2 + pan[0];
  const centerY = (y1 + y2) / 2 + pan[1];
  const viewWidth = baseWidth / zoom;
  const viewHeight = baseHeight / zoom;
  const pad = Math.max(viewWidth, viewHeight) * 0.08;
  const viewBox = `${centerX - viewWidth / 2 - pad} ${-(centerY + viewHeight / 2 + pad)} ${viewWidth + pad * 2} ${viewHeight + pad * 2}`;

  return <div className="drawing">
    <div className="drawing-scope">{mode === "all" ? "Tüm tespitler" : mode === "selected" ? "Eleman çevresi" : "Çizim bölgesi"}<span>{mode === "all" ? visibleElements.length : regionId || "genel"} · {visibleElements.length} tespit</span></div>
    {mode === "context" && regions.length > 1 && <label className="drawing-region">Pafta/bölge <select value={regionId} onChange={(event) => { setManualRegionId(event.target.value); setZoom(1); setPan([0, 0]); }} aria-label="DXF çizim bölgesini seç"><option value="">Tüm kaynak</option>{regions.map(([id, count]) => <option key={id} value={id}>{id} · {count} tespit{id === suggestedRegionId ? " · önerilen" : ""}</option>)}</select></label>}
    <div className="drawing-controls">
      <button title="Uzaklaştır" onClick={() => setZoom((value) => Math.max(0.5, value / 1.35))}><ZoomOut size={15} /></button>
      <button title="Yakınlaştır" onClick={() => setZoom((value) => Math.min(12, value * 1.35))}><ZoomIn size={15} /></button>
      <button title="Seçili elemanın çevresini göster" className={mode === "selected" ? "active" : ""} disabled={!selectedDrawing?.geometry.bbox} onClick={() => { setMode("selected"); setZoom(1); setPan([0, 0]); }}><Focus size={15} /></button>
      <button title="Seçili elemanın bulunduğu gerçek DXF çizim bölgesini göster" className={`text ${mode === "context" ? "active" : ""}`} onClick={() => { setMode("context"); setZoom(1); setPan([0, 0]); }}>Plan</button>
      <button title="Yalnız tüm tespitleri göster" className={`text ${mode === "all" ? "active" : ""}`} onClick={() => { setMode("all"); setZoom(1); setPan([0, 0]); }}>Tespitler</button>
      <button title="DXF yazılarını göster veya gizle" className={`text ${showLabels ? "active" : ""}`} onClick={() => setShowLabels((value) => !value)}>Yazılar</button>
      <button title="Çizim katmanlarını göster veya gizle" className={`text ${showLayers ? "active" : ""}`} onClick={() => setShowLayers((value) => !value)}>Katmanlar</button>
    </div>
    {showLayers && <div className="drawing-layers" aria-label="DXF katman görünürlüğü"><strong>Çizim türleri</strong>{([ ["wall", "Duvar"], ["opening", "Açıklık"], ["room", "Mahal"], ["annotation", "Ölçü"], ["other", "Diğer"] ] as const).map(([role, label]) => <label key={role}><input type="checkbox" checked={!hiddenRoles.includes(role)} onChange={() => setHiddenRoles((roles) => roles.includes(role) ? roles.filter((item) => item !== role) : [...roles, role])} />{label}</label>)}<strong>DXF katmanları ({layerCounts.length})</strong><input type="search" value={layerSearch} onChange={(event) => setLayerSearch(event.target.value)} placeholder="Katman ara" aria-label="DXF katmanı ara" />{layerCounts.filter(([name]) => name.toLocaleLowerCase("tr").includes(layerSearch.toLocaleLowerCase("tr"))).map(([name, count]) => <label key={name} title={name}><input type="checkbox" checked={!hiddenLayers.includes(name)} onChange={() => setHiddenLayers((layers) => layers.includes(name) ? layers.filter((item) => item !== name) : [...layers, name])} /><span>{name}</span><small>{count}</small></label>)}</div>}
    <svg viewBox={viewBox} preserveAspectRatio="xMidYMid meet" onPointerDown={(event) => { if (event.target !== event.currentTarget) return; dragStart.current = { x: event.clientX, y: event.clientY, pan }; event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={(event) => { if (!dragStart.current) return; const rect = event.currentTarget.getBoundingClientRect(); const spanX = viewWidth + pad * 2; const spanY = viewHeight + pad * 2; setPan([dragStart.current.pan[0] - (event.clientX - dragStart.current.x) / rect.width * spanX, dragStart.current.pan[1] + (event.clientY - dragStart.current.y) / rect.height * spanY]); }} onPointerUp={() => { dragStart.current = null; }} onPointerCancel={() => { dragStart.current = null; }} onWheel={(event) => { if (event.ctrlKey || event.metaKey) return; setZoom((value) => Math.max(0.5, Math.min(12, value * (event.deltaY < 0 ? 1.15 : 1 / 1.15)))); }}>
      {rawVisible && rawDrawing?.strokes.filter((stroke) => !hiddenRoles.includes(stroke.role) && !hiddenLayers.includes(stroke.layer || "0")).map((stroke, index) => <polyline key={`raw-${index}`} points={stroke.points.map(([x, y]) => `${x},${-y}`).join(" ")} className={`raw-line ${stroke.role}`} vectorEffect="non-scaling-stroke" />)}
      {rawVisible && showLabels && rawDrawing?.texts.map((label, index) => <text key={`raw-text-${index}`} x={label.x} y={-label.y} className="raw-text" fontSize={label.height_m}>{label.text}</text>)}
      {visibleElements.map((element) => {
      const points = element.geometry.points;
      const box = element.geometry.bbox;
      const coords = points.length > 1
        ? points.map(([x, y]) => `${x},${-y}`).join(" ")
        : box ? `${box[0]},${-box[1]} ${box[2]},${-box[1]} ${box[2]},${-box[3]} ${box[0]},${-box[3]} ${box[0]},${-box[1]}` : "";
      return coords && <polyline key={element.id} points={coords} className={`${element.review_status} ${selectedId === element.id ? "selected" : ""} ${relatedIds.includes(element.id) ? "related" : ""}`} vectorEffect="non-scaling-stroke" onClick={() => onSelect(element.id)} />;
    })}</svg>
    {rawLoading && <div className="drawing-message">Kaynak DXF çizimi açılıyor…</div>}
    {!rawLoading && rawError && mode !== "all" && <div className="drawing-message error">Ham DXF gösterilemedi: {rawError}</div>}
    {rawDrawing?.next_offset !== null && rawDrawing?.next_offset !== undefined && mode !== "all" && <div className="drawing-message warning">{rawDrawing.strokes.length.toLocaleString("tr-TR")} çizgi yüklendi. <button disabled={rawLoadingMore} onClick={() => void loadMoreDrawing()}>{rawLoadingMore ? "Yükleniyor…" : "Sonraki çizgileri yükle"}</button></div>}
    {rawDrawing?.truncated && rawDrawing.next_offset === null && mode !== "all" && <div className="drawing-message warning">Yazı önizlemesi sınırlı; ölçü için kaynak dosyayı kontrol edin.</div>}
    {!rawLoading && !rawDrawing && !rawError && visibleElements.length === 0 && <div className="drawing-empty">Bu kayıtta çizilebilir plan geometrisi yok.</div>}
  </div>;
}

function QuantitiesView({ api, projectId, quantities, pendingCount, structuralBlockers, onReview, onCommercial, onMessage }: { api: EngineApi; projectId: string; quantities: QuantityLine[]; pendingCount: number; structuralBlockers: string[]; onReview: () => void; onCommercial: () => void; onMessage: (message: string) => void }) {
  const totals = useMemo(() => { const grouped = new Map<string, { category: string; unit: string; value: number }>(); quantities.forEach((line) => { const key = `${line.category}|${line.unit}`; const current = grouped.get(key) ?? { category: line.category, unit: line.unit, value: 0 }; current.value += line.quantity; grouped.set(key, current); }); return Array.from(grouped.values()); }, [quantities]);
  const incomplete = pendingCount > 0 || structuralBlockers.length > 0;
  async function exportPayload() { const result = await api.exportReport(projectId); onMessage(`Excel raporu oluşturuldu: ${result.path}`); }
  return <div className="stack">
    <section className={`callout ${incomplete || quantities.length === 0 ? "warning" : "success"}`}>
      {incomplete || quantities.length === 0 ? <AlertTriangle size={22} /> : <ShieldCheck size={22} />}
      <div><strong>{quantities.length === 0 ? "Henüz kesin metraj yok" : incomplete ? "Kısmi onaylı metraj · tam toplam kilitli" : "Mühendis onaylı kesin metraj"}</strong><p>{pendingCount ? `${pendingCount} eleman kararı bekliyor. Yalnız onaylı satırlar kısmi toplama girer.` : quantities.length === 0 ? "Ölçüleri kontrol edip uygun elemanları onaylayın." : "Tüm satırlar onaylı bir kaynak elemana ve açık formüle bağlıdır."} {structuralBlockers.join(" ")}</p></div>
      {(incomplete || quantities.length === 0) && <button className="button secondary" onClick={onReview}>Ölçüleri kontrol et <ChevronRight size={15} /></button>}
    </section>
    <div className="metric-grid">{totals.length ? totals.map((total) => <div className="metric-card" key={`${total.category}-${total.unit}`}><span>{total.category}</span><strong>{formatQuantity(total.value)}</strong><small>{total.unit}</small></div>) : <div className="metric-card empty"><span>Henüz kesin metraj yok</span><strong>—</strong><small>Onay bekleniyor</small></div>}</div>
    <section className="panel"><div className="section-heading"><div><span className="eyebrow">İZLENEBİLİR METRAJ</span><h2>{quantities.length} hesap satırı</h2></div><button className="button primary" disabled={quantities.length === 0} onClick={() => void exportPayload()}><FileSpreadsheet size={17} /> {incomplete ? "Kısmi Excel raporu" : "Excel raporu hazırla"}</button></div><div className="quantity-table"><div className="quantity-head"><span>Kat / Disiplin</span><span>Kalem</span><span>Formül</span><span>Miktar</span></div>{quantities.map((line) => <div className="quantity-row" key={line.id}><span><strong>{line.floor}</strong><small>{disciplineLabel(line.discipline)}</small></span><span><strong>{line.description}</strong><small>{line.element_id.slice(-10)}</small></span><code>{line.formula}</code><span className="quantity-value">{formatQuantity(line.quantity)} <small>{line.unit}</small></span></div>)}{quantities.length === 0 && <EmptyState icon={<FileSpreadsheet />} title="Onaylı hesap satırı yok" detail="Ölçüleri kontrol edip uygun elemanları onaylayın." />}</div></section>
    {quantities.length > 0 && !incomplete && <div className="footer-action"><p>İsterseniz onaylı metrajı birim fiyatlarla eşleştirerek teklif hazırlayabilirsiniz.</p><button className="button secondary" onClick={onCommercial}><BadgeDollarSign size={16} /> Teklif hazırla</button></div>}
  </div>;
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
function viewTitle(view: View) { return ({ sources: "Dosyaları ekle", floors: "Kat ve tekrarlar", mapping: "Birim ve eşleme", review: "Ölçüleri kontrol et", quantities: "Sonuçları al", commercial: "Teklif hazırla", revisions: "Revizyon karşılaştırması" })[view]; }
function viewDescription(view: View) { return ({ sources: "DXF, PDF veya Excel dosyalarını bu projeye ekleyin.", floors: "Yalnız gerekli katları ve onaylı tekrarları tanımlayın.", mapping: "Eksik birim, ölçek ve pafta görevlerini doğrulayın.", review: "Bulunan elemanları ve ölçülerini inceleyip onaylayın.", quantities: "Yalnız onaylı metrajı görün ve Excel raporu alın.", commercial: "İsterseniz metrajı birim fiyatlarla eşleştirin.", revisions: "İki pafta arasındaki değişiklikleri inceleyin." })[view]; }
function disciplineLabel(value: Discipline) { return DISCIPLINES.find((item) => item.value === value)?.label ?? value; }
function floorKindLabel(value: FloorKind) { return FLOOR_KINDS.find((item) => item.value === value)?.label ?? value; }
function sheetKindLabel(value: SheetKind, discipline?: Discipline) { if (value === "plan" && discipline === "structural") return "Kalıp planı"; if (value === "plan" && discipline === "architectural") return "Mimari kat planı"; return SHEET_KINDS.find((item) => item.value === value)?.label ?? value; }
function elementBlockingMessage(element: DetectedElement, blocking: string[]) {
  if (blocking.includes("blocking:unmatched_room_boundary_evidence_only")) return "Bu sınır henüz bir mahal çizelgesi satırıyla eşleşmedi. Yalnız çizim kanıtıdır; bağımsız mahal metrajı olarak onaylanamaz.";
  if (blocking.includes("blocking:annotation_opening_not_physical")) return "Bu aday ölçü/açıklama katmanından geldi. Fiziksel kapı veya pencere olarak sayılmaz; doğru plan elemanını seçin.";
  if (blocking.includes("blocking:opening_decision_required")) return "Bu net alan, henüz onaylanmamış veya hariç tutulmamış kapı/pencereye bağlı. Önce açıklık kararlarını tamamlayın; alan otomatik yenilenir.";
  if (blocking.includes("blocking:opening_vertical_position_required")) return "Alt/üst duvar kaplamasına açıklık düşümü için kapı/pencerenin bitmiş döşemeden alt kotu gerekir. Kaynak kesitten doğrulayın; oransal tahmin kesin metraja girmez.";
  if (blocking.includes("blocking:net_room_perimeter_required")) return "Bu mahalin plan poligonu brüt alan payıdır. İç duvar kaplaması için net mahal çevresi/duvar yüzleri ayrıca kanıtlanmalı; brüt çevre kesin hesaba alınmaz.";
  if (blocking.includes("blocking:drawing_unit_evidence_mismatch")) return "Bu dosyada yazılı ölçü ve geometri seçili birimde uyuşmuyor. Birimi kaynak ayarlarında bir kez doğrulayıp analizi yenileyin.";
  if (blocking.includes("blocking:room_schedule_geometry_mismatch")) {
    const declared = element.measurements.area_m2;
    const geometric = element.measurements.geometric_area_m2;
    if (declared && geometric) return `Mahal çizelgesi ${formatQuantity(declared)} m², eşlenen çizim sınırı ${formatQuantity(geometric)} m² (%${formatQuantity(Math.abs(geometric - declared) / declared * 100)} fark). Sınır veya mahal eşleşmesini kontrol edin; değer otomatik değiştirilmez.`;
    return "Mahal çizelgesi ve çizim sınırı uyuşmuyor. Sınır eşleşmesini kontrol edin.";
  }
  if (blocking.includes("blocking:room_boundary_assignment_required")) return "Bu mahalin plan sınırı güvenle eşleşmedi. Doğru sınırı seçip gerekçeyle kaydedin.";
  if (blocking.includes("blocking:opening_host_wall_required")) return "Bu açıklığın hangi duvarda olduğu kanıtlanamadı. Duvarı plandan seçip ilişkiyi kaydedin.";
  if (blocking.includes("blocking:opening_schedule_match_required")) return "Kapı/pencere tipi çizelgeyle eşleşmedi; yükseklik ve malzeme kesinleşmedi.";
  if (blocking.includes("blocking:opening_room_assignment_required")) return "Açıklığın komşu mahalleri güvenle bulunamadı. İlgili mahalleri plandan seçin.";
  if (blocking.includes("blocking:stair_floor_repeat_required")) return "Tip merdivenin uygulanacağı kat aralıkları henüz tanımlanmadı; bu aday kesin metraja kapalıdır.";
  return "Bu elemanın ölçüsü veya kaynak ilişkisi henüz doğrulanamadı; kesin metraja eklenmez.";
}
function elementTypeLabel(value: string) { return ({ column: "Kolon", beam: "Kiriş", shear_wall: "Perde", slab: "Döşeme", slab_opening: "Döşeme boşluğu", raft: "Radye temel", foundation: "Temel", stair: "Merdiven", rebar: "Donatı", wall: "Duvar", door: "Kapı", window: "Pencere", room: "Mahal", finish_area: "Kaplama", pipe: "Boru", duct: "Kanal", mechanical_fitting: "Fittings", mechanical_equipment: "Mekanik cihaz", cable: "Kablo", cable_tray: "Kablo tavası", light: "Armatür", socket: "Priz", panel: "Pano", electrical_item: "Elektrik ekipmanı", landscape_area: "Peyzaj alanı", landscape_linear: "Bordür / hat", landscape_item: "Bitki / ekipman", schedule_item: "Poz çizelgesi", pdf_evidence: "PDF kanıtı" } as Record<string, string>)[value] ?? value; }
function measurementLabel(elementType: string, key: string) { if (elementType === "beam" && key === "height_m") return "Kesit yüksekliği (m)"; if (elementType === "beam" && key === "width_m") return "Kesit genişliği (m)"; return MEASUREMENT_LABELS[key] ?? key; }
function formatQuantity(value: number) { return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 3 }).format(value); }
function formatSigned(value: number) { return `${value >= 0 ? "+" : ""}${formatQuantity(value)}`; }
function revisionMeasurements(values: Record<string, number>) { const keys = ["width_m", "depth_m", "height_m", "length_m", "area_m2", "thickness_m", "void_area_m2", "plan_area_m2", "total_rise_m"]; const parts = keys.filter((key) => values[key] !== undefined).map((key) => `${measurementLabel("", key)}: ${formatQuantity(values[key])}`); return parts.length ? parts.join(" · ") : "—"; }
function sourceStatusReady(source: SourceFile) { if (source.source_format === "pdf") return source.calibration_status === "confirmed"; if (source.source_format !== "dxf") return true; return source.unit_confirmed && (source.detected_unit === "unknown" || source.drawing_unit === source.detected_unit); }
function sourceStatusLabel(source: SourceFile) { if (source.source_format === "pdf") return source.calibration_status === "confirmed" ? "ölçek onaylı" : "ölçek bekliyor"; if (source.source_format !== "dxf") return source.source_format.toUpperCase(); if (source.unit_confirmed && source.detected_unit !== "unknown" && source.drawing_unit !== source.detected_unit) return `${source.drawing_unit} · DXF ${source.detected_unit} ⚠`; return source.unit_confirmed ? source.drawing_unit : source.detected_unit !== "unknown" ? `${source.detected_unit} algılandı` : "birim bekliyor"; }
function sourceNeedsSetup(source: SourceFile) {
  if (source.source_format === "pdf") return source.calibration_status !== "confirmed";
  if (source.source_format !== "dxf") return false;
  if (source.discipline === "structural" && source.sheet_kind === "unspecified") return true;
  return !source.unit_confirmed && source.detected_unit === "unknown" && !(source.discipline === "structural" && ["detail", "section", "elevation", "other"].includes(source.sheet_kind));
}

export default App;
