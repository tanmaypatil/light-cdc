import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ChangeBadge } from "../components/ChangeBadge";
import { DiffViewer } from "../components/DiffViewer";
import { RollbackModal } from "../components/RollbackModal";
import type { ChangeEvent, PollRun } from "../types";

const ENV_OPTIONS = ["dev", "qa"];

export function SnapshotsPage() {
  const [env, setEnv] = useState("dev");
  const [selectedRun, setSelectedRun] = useState<PollRun | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<ChangeEvent | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<ChangeEvent | null>(null);

  const { data: pollRuns } = useQuery({
    queryKey: ["poll-runs", env],
    queryFn: () => api.getPollRuns(env),
    refetchInterval: 30_000,
  });

  const { data: changes } = useQuery({
    queryKey: ["changes", env, selectedRun?.id],
    queryFn: () =>
      api.getChanges(env, { page: 1 }),
    enabled: !!selectedRun,
    refetchInterval: 30_000,
  });

  const runChanges = changes?.data.filter((c) => c.poll_run_id === selectedRun?.id) ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <span className="text-lg font-bold text-gray-900">light-cdc</span>
        <nav className="flex gap-4 text-sm text-gray-600">
          <a href="/" className="hover:text-gray-900">Dashboard</a>
          <a href="/snapshots" className="font-medium text-blue-600">Snapshots</a>
          <a href="/history" className="hover:text-gray-900">History</a>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <select
            value={env}
            onChange={(e) => { setEnv(e.target.value); setSelectedRun(null); setSelectedEvent(null); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            {ENV_OPTIONS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-5 gap-6">
          {/* Poll run list */}
          <div className="col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 text-sm font-semibold text-gray-900">
              Poll Runs
            </div>
            <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
              {(pollRuns?.data ?? []).map((run) => (
                <button
                  key={run.id}
                  onClick={() => { setSelectedRun(run); setSelectedEvent(null); }}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                    selectedRun?.id === run.id ? "bg-blue-50 border-l-2 border-blue-500" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-gray-500">#{run.id}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      run.status === "success" ? "bg-green-100 text-green-700" :
                      run.status === "error" ? "bg-red-100 text-red-700" :
                      "bg-yellow-100 text-yellow-700"
                    }`}>{run.status}</span>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">
                    {new Date(run.started_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {run.changes_found} change{run.changes_found !== 1 ? "s" : ""} · {run.tables_polled} tables
                  </p>
                </button>
              ))}
              {(pollRuns?.data ?? []).length === 0 && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">No poll runs yet</p>
              )}
            </div>
          </div>

          {/* Change events + diff */}
          <div className="col-span-3 space-y-4">
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 text-sm font-semibold text-gray-900">
                {selectedRun ? `Changes in poll run #${selectedRun.id}` : "Select a poll run"}
              </div>
              <div className="divide-y divide-gray-100 max-h-64 overflow-y-auto">
                {runChanges.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedEvent(c)}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-50 flex items-center gap-3 ${
                      selectedEvent?.id === c.id ? "bg-blue-50" : ""
                    }`}
                  >
                    <ChangeBadge type={c.change_type} />
                    <span className="font-mono text-xs text-gray-700">{c.table_name}</span>
                    <span className="font-mono text-xs text-gray-400">{c.pk_value}</span>
                    {c.rolled_back ? (
                      <span className="ml-auto text-xs text-gray-400 italic">rolled back</span>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); setRollbackTarget(c); }}
                        className="ml-auto text-xs text-red-600 hover:underline"
                      >
                        Rollback
                      </button>
                    )}
                  </button>
                ))}
                {selectedRun && runChanges.length === 0 && (
                  <p className="px-4 py-6 text-sm text-gray-400 text-center">No changes in this run</p>
                )}
              </div>
            </div>

            {selectedEvent && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 text-sm font-semibold text-gray-900">
                  Diff — {selectedEvent.change_type} on {selectedEvent.table_name}
                </div>
                <div className="p-4">
                  <DiffViewer event={selectedEvent} />
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {rollbackTarget && (
        <RollbackModal
          env={env}
          event={rollbackTarget}
          onClose={() => setRollbackTarget(null)}
        />
      )}
    </div>
  );
}
