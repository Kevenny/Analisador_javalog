import { useState } from "react";

interface ProfileThread {
  name: string;
  state: string;
  priority: number;
  stack_trace: string[];
  waiting_on: string | null;
  locked: string[];
}

interface ProfileResult {
  summary: {
    total_threads: number;
    states: Record<string, number>;
    deadlocks_found: boolean;
    note?: string;
  };
  deadlocks: Array<{ threads: string[]; description: string }>;
  threads: ProfileThread[];
  hotspots: Array<{ frame: string; count: number }>;
  stack_groups: Array<{ stack_hash: string; count: number; sample_thread: string; frames: string[] }>;
}

export default function ProfileReport({ result }: { result: ProfileResult }) {
  const { summary, threads, hotspots } = result;
  const [expandedThread, setExpandedThread] = useState<number | null>(null);

  const totalFrames = threads.reduce((acc, t) => acc + t.stack_trace.length, 0);

  return (
    <div className="space-y-8">
      {/* Nota informativa sobre o snapshot */}
      {summary.note && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-sm text-blue-800">
          <span className="font-semibold">ℹ️ Snapshot de CPU: </span>
          {summary.note}
        </div>
      )}

      {/* Cards de resumo */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Threads Capturadas</p>
          <p className="text-3xl font-bold text-blue-700">{summary.total_threads}</p>
        </div>
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Frames no Call Tree</p>
          <p className="text-3xl font-bold text-purple-700">{totalFrames.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Hotspots Identificados</p>
          <p className="text-3xl font-bold text-orange-600">{hotspots.length}</p>
        </div>
      </div>

      {/* Hotspots — métodos mais frequentes */}
      {hotspots.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">
            Hotspots — Métodos Mais Frequentes
          </h2>
          <p className="text-xs text-gray-400 mb-4">
            Métodos observados com maior frequência durante o profiling de CPU.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2 w-8">#</th>
                <th className="pb-2">Método</th>
                <th className="pb-2 text-right w-28">Ocorrências</th>
              </tr>
            </thead>
            <tbody>
              {hotspots.slice(0, 30).map((h, i) => {
                const maxCount = hotspots[0]?.count || 1;
                const pct = Math.round((h.count / maxCount) * 100);
                return (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-2 text-gray-400 text-xs">{i + 1}</td>
                    <td className="py-2 pr-4">
                      <div className="font-mono text-xs text-gray-700 truncate max-w-xl" title={h.frame}>
                        {h.frame}
                      </div>
                      <div className="mt-1 h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-400 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-2 text-right">
                      <span className="bg-orange-100 text-orange-800 text-xs font-medium px-2 py-0.5 rounded">
                        {h.count}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Call trees por thread */}
      <div className="bg-white rounded-xl border shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Call Trees por Thread ({threads.length})
        </h2>
        <div className="space-y-2">
          {threads.map((t, i) => (
            <div key={i} className="border rounded-lg overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
                onClick={() => setExpandedThread(expandedThread === i ? null : i)}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="bg-purple-100 text-purple-700 text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0">
                    {t.stack_trace.length} frames
                  </span>
                  <span className="font-medium text-gray-700 text-sm truncate">{t.name}</span>
                </div>
                <span className="text-gray-400 flex-shrink-0 ml-2">
                  {expandedThread === i ? "▲" : "▼"}
                </span>
              </button>
              {expandedThread === i && (
                <div className="px-4 py-3 bg-white overflow-auto max-h-80">
                  <ol className="text-xs font-mono text-gray-600 space-y-0.5 list-decimal list-inside">
                    {t.stack_trace.map((frame, fi) => (
                      <li key={fi} className="truncate" title={frame}>
                        {frame}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
