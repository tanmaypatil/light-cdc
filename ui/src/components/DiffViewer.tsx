import type { ChangeEvent } from "../types";

interface Props {
  event: ChangeEvent;
}

function parseJson(s: string | null): Record<string, unknown> {
  if (!s) return {};
  try {
    return JSON.parse(s);
  } catch {
    return {};
  }
}

export function DiffViewer({ event }: Props) {
  const before = parseJson(event.before_data);
  const after = parseJson(event.after_data);
  const diffCols = new Set<string>(parseJson(event.diff_columns) as unknown as string[]);
  const allKeys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));

  const cellClass = (key: string) => {
    if (event.change_type === "INSERT") return "bg-green-50 text-green-900";
    if (event.change_type === "DELETE") return "bg-red-50 text-red-900";
    if (diffCols.has(key)) return "bg-amber-50 text-amber-900 font-medium";
    return "";
  };

  return (
    <div className="overflow-x-auto text-sm">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-100 text-left text-xs uppercase tracking-wider text-gray-500">
            <th className="px-3 py-2 border border-gray-200 w-1/4">Column</th>
            <th className="px-3 py-2 border border-gray-200 w-3/8">Before</th>
            <th className="px-3 py-2 border border-gray-200 w-3/8">After</th>
          </tr>
        </thead>
        <tbody>
          {allKeys.map((key) => (
            <tr key={key} className="border-b border-gray-100">
              <td className="px-3 py-1.5 border border-gray-200 font-mono text-gray-600">{key}</td>
              <td className={`px-3 py-1.5 border border-gray-200 font-mono ${cellClass(key)}`}>
                {before[key] !== undefined ? String(before[key]) : <span className="text-gray-300">—</span>}
              </td>
              <td className={`px-3 py-1.5 border border-gray-200 font-mono ${cellClass(key)}`}>
                {after[key] !== undefined ? String(after[key]) : <span className="text-gray-300">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
