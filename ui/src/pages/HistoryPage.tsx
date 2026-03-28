import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

const ENV_OPTIONS = ["dev", "qa"];

export function HistoryPage() {
  const [env, setEnv] = useState("dev");
  const [purgeDays, setPurgeDays] = useState("30");
  const [confirmText, setConfirmText] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: stats, refetch } = useQuery({
    queryKey: ["history-stats", env],
    queryFn: () => api.getHistoryStats(env),
    refetchInterval: 60_000,
  });

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const purgeMutation = useMutation({
    mutationFn: () => api.purgeByAge(env, parseInt(purgeDays)),
    onSuccess: () => {
      showToast(`Purged records older than ${purgeDays} days`);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["changes", env] });
    },
  });

  const purgeAllMutation = useMutation({
    mutationFn: () => api.purgeAll(env),
    onSuccess: () => {
      showToast("All history purged");
      setConfirmText("");
      refetch();
      queryClient.invalidateQueries({ queryKey: ["changes", env] });
    },
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <span className="text-lg font-bold text-gray-900">light-cdc</span>
        <nav className="flex gap-4 text-sm text-gray-600">
          <a href="/" className="hover:text-gray-900">Dashboard</a>
          <a href="/snapshots" className="hover:text-gray-900">Snapshots</a>
          <a href="/history" className="font-medium text-blue-600">History</a>
        </nav>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {toast && (
          <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg px-4 py-3 text-sm">
            {toast}
          </div>
        )}

        <div className="flex items-center gap-3">
          <select
            value={env}
            onChange={(e) => setEnv(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            {ENV_OPTIONS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>

        {/* Stats */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 text-sm font-semibold text-gray-900">
            Database Stats
          </div>
          <div className="px-5 py-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">File size</span>
              <span className="font-medium">{stats?.db_size_mb ?? 0} MB</span>
            </div>
            {stats?.counts && Object.entries(stats.counts).map(([key, val]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-gray-500 font-mono">{key}</span>
                <span className="font-medium">{val.toLocaleString()} rows</span>
              </div>
            ))}
            <div className="flex justify-between text-sm pt-2 border-t border-gray-100">
              <span className="text-gray-500">Oldest event</span>
              <span className="text-xs text-gray-600">
                {stats?.oldest_event ? new Date(stats.oldest_event).toLocaleString() : "—"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Newest event</span>
              <span className="text-xs text-gray-600">
                {stats?.newest_event ? new Date(stats.newest_event).toLocaleString() : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Age-based purge */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 text-sm font-semibold text-gray-900">
            Purge by Age
          </div>
          <div className="px-5 py-4 flex items-center gap-3">
            <span className="text-sm text-gray-600">Delete records older than</span>
            <input
              type="number"
              value={purgeDays}
              onChange={(e) => setPurgeDays(e.target.value)}
              min="1"
              className="w-20 text-sm border border-gray-300 rounded-lg px-3 py-2"
            />
            <span className="text-sm text-gray-600">days</span>
            <button
              onClick={() => purgeMutation.mutate()}
              disabled={purgeMutation.isPending}
              className="ml-auto text-sm bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 disabled:opacity-50"
            >
              {purgeMutation.isPending ? "Purging…" : "Purge"}
            </button>
          </div>
        </div>

        {/* Full purge */}
        <div className="bg-white rounded-xl border border-red-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-red-100 text-sm font-semibold text-red-700">
            Full Purge
          </div>
          <div className="px-5 py-4 space-y-3">
            <p className="text-sm text-gray-600">
              This will permanently delete <strong>all</strong> history for the{" "}
              <strong>{env}</strong> environment. Type the environment name to confirm.
            </p>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={`Type "${env}" to confirm`}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2"
            />
            <button
              onClick={() => purgeAllMutation.mutate()}
              disabled={confirmText !== env || purgeAllMutation.isPending}
              className="w-full text-sm bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {purgeAllMutation.isPending ? "Purging…" : `Delete all history for ${env}`}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
