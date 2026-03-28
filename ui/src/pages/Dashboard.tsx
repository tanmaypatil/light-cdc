import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { ChangeBadge } from "../components/ChangeBadge";
import { RollbackModal } from "../components/RollbackModal";
import { ChangeDetailModal } from "../components/ChangeDetailModal";
import type { ChangeEvent } from "../types";

export function Dashboard() {
  const [env, setEnv] = useState("dev");
  const [selectedEvent, setSelectedEvent] = useState<ChangeEvent | null>(null);
  const [detailEvent, setDetailEvent] = useState<ChangeEvent | null>(null);
  const queryClient = useQueryClient();

  const { data: environments } = useQuery({
    queryKey: ["environments"],
    queryFn: api.getEnvironments,
    refetchInterval: 30_000,
  });

  const { data: changes } = useQuery({
    queryKey: ["changes", env],
    queryFn: () => api.getChanges(env, { page: 1 }),
    refetchInterval: 30_000,
    enabled: !!env,
  });

  const triggerMutation = useMutation({
    mutationFn: () => api.triggerPoll(env),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["changes", env] }),
  });

  const currentEnv = environments?.find((e) => e.name === env);
  const recentChanges = changes?.data.slice(0, 10) ?? [];
  const totalChanges = changes?.meta.total ?? 0;
  const rolledBack = recentChanges.filter((c) => c.rolled_back).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-gray-900">light-cdc</span>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">agent</span>
        </div>
        <nav className="flex gap-4 text-sm text-gray-600">
          <a href="/" className="font-medium text-blue-600">Dashboard</a>
          <a href="/snapshots" className="hover:text-gray-900">Snapshots</a>
          <a href="/history" className="hover:text-gray-900">History</a>
        </nav>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Controls */}
        <div className="flex items-center gap-3">
          <select
            value={env}
            onChange={(e) => setEnv(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            {environments?.map((e) => (
              <option key={e.name} value={e.name}>{e.name}</option>
            ))}
          </select>
          <button
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {triggerMutation.isPending ? "Triggering…" : "Trigger Poll Now"}
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Last Poll</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {currentEnv?.last_poll
                ? new Date(currentEnv.last_poll.started_at).toLocaleString(undefined, {
                    year: "numeric", month: "short", day: "numeric",
                    hour: "2-digit", minute: "2-digit"
                  })
                : "—"}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {currentEnv?.last_poll?.status ?? "no data"}
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Total Changes</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">{totalChanges}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Rolled Back</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">{rolledBack}</p>
          </div>
        </div>

        {/* Recent changes table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Recent Changes</h2>
          </div>
          {recentChanges.length === 0 ? (
            <p className="px-5 py-8 text-sm text-gray-400 text-center">
              No changes detected yet. Waiting for next poll…
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-gray-500 bg-gray-50">
                  <th className="px-5 py-3 text-left">Table</th>
                  <th className="px-5 py-3 text-left">PK</th>
                  <th className="px-5 py-3 text-left">Type</th>
                  <th className="px-5 py-3 text-left">Detected</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentChanges.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-mono text-gray-700">{c.table_name}</td>
                    <td className="px-5 py-3 font-mono text-xs text-gray-500">{c.pk_value}</td>
                    <td className="px-5 py-3">
                      <ChangeBadge type={c.change_type} />
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs">
                      {new Date(c.detected_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3">
                      {c.rolled_back ? (
                        <span className="text-xs text-gray-400 italic">rolled back</span>
                      ) : (
                        <span className="text-xs text-green-600">active</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right flex items-center justify-end gap-3">
                      <button
                        onClick={() => setDetailEvent(c)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View
                      </button>
                      {!c.rolled_back && (
                        <button
                          onClick={() => setSelectedEvent(c)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Rollback
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {detailEvent && (
        <ChangeDetailModal
          env={env}
          event={detailEvent}
          onClose={() => setDetailEvent(null)}
          onRollback={(e) => { setDetailEvent(null); setSelectedEvent(e); }}
        />
      )}

      {selectedEvent && (
        <RollbackModal
          env={env}
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
}
