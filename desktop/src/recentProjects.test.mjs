import assert from "node:assert/strict";
import test from "node:test";
import { readRecentProjects, rememberRecentProject, removeRecentProject } from "./recentProjects.ts";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("recent projects are stored newest-first and deduplicated by folder", () => {
  const storage = memoryStorage();
  rememberRecentProject({ projectId: "a", name: "Taziye", path: "/projects/taziye/" }, storage, new Date("2026-01-01T10:00:00Z"));
  rememberRecentProject({ projectId: "b", name: "Defterdarlık", path: "/projects/defter" }, storage, new Date("2026-01-02T10:00:00Z"));
  rememberRecentProject({ projectId: "a", name: "Taziye Evi", path: "/projects/taziye" }, storage, new Date("2026-01-03T10:00:00Z"));
  assert.deepEqual(readRecentProjects(storage).map(({ name, path }) => [name, path]), [
    ["Taziye Evi", "/projects/taziye"],
    ["Defterdarlık", "/projects/defter"],
  ]);
});

test("a broken list is ignored and removing a shortcut leaves other projects", () => {
  const storage = memoryStorage();
  storage.setItem("metrajai.recent-projects.v1", "not-json");
  assert.deepEqual(readRecentProjects(storage), []);
  rememberRecentProject({ projectId: "a", name: "A", path: "/a" }, storage);
  rememberRecentProject({ projectId: "b", name: "B", path: "/b" }, storage);
  assert.deepEqual(removeRecentProject("/a", storage).map((item) => item.path), ["/b"]);
});

test("a moved project replaces its old shortcut and unavailable storage is harmless", () => {
  const storage = memoryStorage();
  rememberRecentProject({ projectId: "same", name: "Project", path: "/old" }, storage);
  rememberRecentProject({ projectId: "same", name: "Project", path: "/new" }, storage);
  assert.deepEqual(readRecentProjects(storage).map((item) => item.path), ["/new"]);
  assert.deepEqual(readRecentProjects(), []);
  assert.deepEqual(readRecentProjects({ getItem: () => { throw new Error("blocked"); }, setItem: () => {} }), []);
});

test("only the eight latest project shortcuts are retained", () => {
  const storage = memoryStorage();
  for (let index = 0; index < 11; index += 1) {
    rememberRecentProject(
      { projectId: String(index), name: `Project ${index}`, path: `/projects/${index}` },
      storage,
      new Date(Date.UTC(2026, 0, index + 1)),
    );
  }
  assert.equal(readRecentProjects(storage).length, 8);
  assert.equal(readRecentProjects(storage)[0].path, "/projects/10");
  assert.equal(readRecentProjects(storage).at(-1).path, "/projects/3");
});
