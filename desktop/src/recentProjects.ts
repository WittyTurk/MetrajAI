const STORAGE_KEY = "metrajai.recent-projects.v1";
const MAX_RECENT_PROJECTS = 8;

export interface RecentProject {
  projectId: string;
  name: string;
  path: string;
  openedAt: string;
}

type RecentStorage = Pick<Storage, "getItem" | "setItem">;

function availableStorage(storage?: RecentStorage): RecentStorage | null {
  if (storage) return storage;
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function cleanPath(path: string): string {
  const trimmed = path.trim();
  if (trimmed === "/" || /^[A-Za-z]:[\\/]$/.test(trimmed)) return trimmed;
  return trimmed.replace(/[\\/]+$/, "");
}

function isRecentProject(value: unknown): value is RecentProject {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.projectId === "string" && item.projectId.length > 0
    && typeof item.name === "string" && item.name.length > 0
    && typeof item.path === "string" && item.path.length > 0
    && typeof item.openedAt === "string" && Number.isFinite(Date.parse(item.openedAt));
}

export function readRecentProjects(storage?: RecentStorage): RecentProject[] {
  try {
    const raw = availableStorage(storage)?.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    const seenPaths = new Set<string>();
    const seenProjects = new Set<string>();
    return parsed
      .filter(isRecentProject)
      .map((item) => ({ ...item, path: cleanPath(item.path) }))
      .sort((left, right) => Date.parse(right.openedAt) - Date.parse(left.openedAt))
      .filter((item) => {
        if (!item.path || seenPaths.has(item.path) || seenProjects.has(item.projectId)) return false;
        seenPaths.add(item.path);
        seenProjects.add(item.projectId);
        return true;
      })
      .slice(0, MAX_RECENT_PROJECTS);
  } catch {
    return [];
  }
}

export function rememberRecentProject(
  project: Pick<RecentProject, "projectId" | "name" | "path">,
  storage?: RecentStorage,
  now = new Date(),
): RecentProject[] {
  const path = cleanPath(project.path);
  if (!path) return readRecentProjects(storage);
  const next = [
    { projectId: project.projectId, name: project.name, path, openedAt: now.toISOString() },
    ...readRecentProjects(storage).filter((item) => item.path !== path && item.projectId !== project.projectId),
  ].slice(0, MAX_RECENT_PROJECTS);
  try {
    availableStorage(storage)?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // A disabled or full WebView storage must never block opening a project.
  }
  return next;
}

export function removeRecentProject(
  path: string,
  storage?: RecentStorage,
): RecentProject[] {
  const next = readRecentProjects(storage).filter((item) => item.path !== cleanPath(path));
  try {
    availableStorage(storage)?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // The project itself is never deleted; only this local shortcut is removed.
  }
  return next;
}
