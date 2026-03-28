import { DiffViewer } from "./DiffViewer";
import { ChangeBadge } from "./ChangeBadge";
import type { ChangeEvent } from "../types";

interface Props {
  env: string;
  event: ChangeEvent;
  onClose: () => void;
  onRollback: (event: ChangeEvent) => void;
}

export function ChangeDetailModal({ event, onClose, onRollback }: Props) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <ChangeBadge type={event.change_type} />
            <div>
              <span className="text-sm font-semibold text-gray-900 font-mono">{event.table_name}</span>
              <p className="text-xs text-gray-500 mt-0.5">pk {event.pk_value}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
        </div>

        <div className="px-5 py-4 max-h-[60vh] overflow-y-auto">
          <DiffViewer event={event} />
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50">
          <span className="text-xs text-gray-400">
            {new Date(event.detected_at).toLocaleString(undefined, {
              year: "numeric", month: "short", day: "numeric",
              hour: "2-digit", minute: "2-digit"
            })}
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800">
              Close
            </button>
            {!event.rolled_back && (
              <button
                onClick={() => { onClose(); onRollback(event); }}
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Rollback
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
