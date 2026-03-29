import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { sql, PostgreSQL } from "@codemirror/lang-sql";
import { autocompletion, closeBrackets } from "@codemirror/autocomplete";
import { oneDark } from "@codemirror/theme-one-dark";
import { api } from "../api/client";

const ENV_OPTIONS = ["dev", "qa"];

type ResultRow = Record<string, unknown>;

export function PlaygroundPage() {
  const [env, setEnv] = useState("dev");
  const [result, setResult] = useState<{
    rows?: ResultRow[];
    row_count?: number;
    message?: string;
    rows_affected?: number;
    error?: string;
  } | null>(null);

  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);

  const { data: schemaData } = useQuery({
    queryKey: ["playgroundSchema", env],
    queryFn: () => api.getPlaygroundSchema(env),
  });

  const executeMutation = useMutation({
    mutationFn: (sqlText: string) => api.executeSQL(env, sqlText),
    onSuccess: (data) => setResult(data),
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setResult({ error: detail ?? (e instanceof Error ? e.message : String(e)) });
    },
  });

  const runSQL = useCallback(() => {
    if (!viewRef.current) return;
    const text = viewRef.current.state.doc.toString().trim();
    if (!text) return;
    setResult(null);
    executeMutation.mutate(text);
  }, [executeMutation]);

  // Build schema map for CodeMirror SQL dialect
  const schemaMap = useCallback(() => {
    if (!schemaData) return {};
    const map: Record<string, string[]> = {};
    for (const [table, info] of Object.entries(schemaData.tables)) {
      map[table] = info.schema.map((c) => c.column_name);
    }
    return map;
  }, [schemaData]);

  // (Re-)create editor when schema or env changes
  useEffect(() => {
    if (!editorRef.current) return;

    const tables = schemaMap();

    const extensions = [
      lineNumbers(),
      history(),
      closeBrackets(),
      autocompletion(),
      sql({ dialect: PostgreSQL, schema: tables }),
      oneDark,
      keymap.of([
        ...defaultKeymap,
        ...historyKeymap,
        {
          key: "Mod-Enter",
          run: () => {
            runSQL();
            return true;
          },
        },
      ]),
      EditorView.theme({
        "&": { fontSize: "13px", borderRadius: "8px", overflow: "hidden" },
        ".cm-scroller": { minHeight: "140px", maxHeight: "300px" },
      }),
    ];

    // Preserve existing content if view already exists
    const currentContent = viewRef.current
      ? viewRef.current.state.doc.toString()
      : "";

    if (viewRef.current) {
      viewRef.current.destroy();
    }

    viewRef.current = new EditorView({
      state: EditorState.create({
        doc: currentContent || "-- Cmd+Enter to run\n",
        extensions,
      }),
      parent: editorRef.current,
    });

    return () => {
      viewRef.current?.destroy();
      viewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [env, schemaData]);

  const tables = schemaData ? Object.entries(schemaData.tables) : [];
  const resultCols =
    result?.rows && result.rows.length > 0 ? Object.keys(result.rows[0]) : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <span className="text-lg font-bold text-gray-900">light-cdc</span>
        <nav className="flex gap-4 text-sm text-gray-600">
          <a href="/" className="hover:text-gray-900">Dashboard</a>
          <a href="/snapshots" className="hover:text-gray-900">Snapshots</a>
          <a href="/playground" className="font-medium text-blue-600">Playground</a>
          <a href="/history" className="hover:text-gray-900">History</a>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 flex gap-6">
        {/* Schema sidebar */}
        <aside className="w-56 shrink-0 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Schema</p>
            <select
              value={env}
              onChange={(e) => { setEnv(e.target.value); setResult(null); }}
              className="text-xs border border-gray-300 rounded px-2 py-1 bg-white"
            >
              {ENV_OPTIONS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          {tables.length === 0 ? (
            <p className="text-xs text-gray-400">Loading schema…</p>
          ) : (
            tables.map(([table, info]) => (
              <div key={table} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center gap-1.5">
                  <span className="text-xs font-mono font-semibold text-gray-800">{table}</span>
                </div>
                <ul className="divide-y divide-gray-100">
                  {info.schema.map((col) => (
                    <li key={col.column_name} className="px-3 py-1.5 flex items-center justify-between gap-2">
                      <span className="text-xs font-mono text-gray-700 truncate">
                        {col.column_name}
                        {info.primary_key.includes(col.column_name) && (
                          <span className="ml-1 text-blue-400">PK</span>
                        )}
                      </span>
                      <span className="text-xs text-gray-400 shrink-0">{col.data_type.replace("character varying", "varchar")}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </aside>

        {/* Editor + results */}
        <div className="flex-1 space-y-4 min-w-0">
          {/* Editor */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-900">SQL Editor</span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">Ctrl+Space for autocomplete · Cmd+Enter to run</span>
                <button
                  onClick={runSQL}
                  disabled={executeMutation.isPending}
                  className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {executeMutation.isPending ? "Running…" : "Run"}
                </button>
              </div>
            </div>
            <div ref={editorRef} />
          </div>

          {/* Results */}
          {result && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900">Result</span>
                {result.error ? (
                  <span className="text-xs text-red-600">{result.error}</span>
                ) : result.rows !== undefined ? (
                  <span className="text-xs text-gray-400">{result.row_count} row{result.row_count !== 1 ? "s" : ""}</span>
                ) : (
                  <span className="text-xs text-green-600">{result.message} · {result.rows_affected} row{result.rows_affected !== 1 ? "s" : ""} affected</span>
                )}
              </div>

              {result.error && (
                <pre className="px-4 py-3 text-xs text-red-700 bg-red-50 whitespace-pre-wrap">{result.error}</pre>
              )}

              {result.rows && result.rows.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-xs uppercase tracking-wider text-gray-500">
                        {resultCols.map((c) => (
                          <th key={c} className="px-4 py-2 text-left font-medium whitespace-nowrap">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {result.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-gray-50">
                          {resultCols.map((c) => (
                            <td key={c} className="px-4 py-2 font-mono text-xs text-gray-700 whitespace-nowrap">
                              {row[c] === null ? <span className="text-gray-300">null</span> : String(row[c])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {result.rows && result.rows.length === 0 && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">No rows returned</p>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
