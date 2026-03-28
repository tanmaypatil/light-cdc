import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { DiffViewer } from "./DiffViewer";
import type { ChangeEvent } from "../types";

interface Props {
  env: string;
  event: ChangeEvent;
  onClose: () => void;
}

export function RollbackModal({ env, event, onClose }: Props) {
  const [showSql, setShowSql] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.rollbackChange(env, event.id),
    onSuccess: (data) => {
      setToast(data.message);
      queryClient.invalidateQueries({ queryKey: ["changes", env] });
      setTimeout(onClose, 1800);
    },
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Confirm Rollback</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {event.change_type} on <span className="font-mono">{event.table_name}</span> — pk{" "}
              <span className="font-mono">{event.pk_value}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {toast ? (
            <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg px-4 py-3 text-sm">
              {toast}
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-600">
                This will reverse the change shown below in the <strong>{env}</strong> database.
              </p>
              <DiffViewer event={event} />
              <button
                onClick={() => setShowSql((v) => !v)}
                className="text-xs text-blue-600 hover:underline"
              >
                {showSql ? "Hide" : "Show"} rollback SQL
              </button>
              {showSql && (
                <pre className="bg-gray-900 text-green-400 text-xs rounded-lg p-3 overflow-x-auto">
                  {`-- Generated rollback for change_event #${event.id}\n-- Execute manually if needed`}
                </pre>
              )}
            </>
          )}
        </div>

        {!toast && (
          <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-200 bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {mutation.isPending ? "Rolling back…" : "Confirm Rollback"}
            </button>
          </div>
        )}

        {mutation.isError && (
          <p className="px-5 pb-3 text-xs text-red-600">
            Error: {(mutation.error as Error).message}
          </p>
        )}
      </div>
    </div>
  );
}
