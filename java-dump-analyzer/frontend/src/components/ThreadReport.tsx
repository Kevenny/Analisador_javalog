import { useState } from "react";

interface ThreadInfo {
  name: string;
  state: string;
  priority: number;
  stack_trace: string[];
  waiting_on: string | null;
  locked: string[];
}

interface ThreadResult {
  summary: {
    total_threads: number;
    states: Record<string, number>;
    deadlocks_found: boolean;
  };
  deadlocks: Array<{ threads: string[]; description: string }>;
  threads: ThreadInfo[];
  hotspots: Array<{ frame: string; count: number }>;
  stack_groups: Array<{ stack_hash: string; count: number; sample_thread: string; frames: string[] }>;
}

const STATE_COLORS: Record<string, string> = {
  RUNNABLE: "bg-green-100 text-green-800",
  BLOCKED: "bg-red-100 text-red-800",
  WAITING: "bg-yellow-100 text-yellow-800",
  TIMED_WAITING: "bg-orange-100 text-orange-800",
};

export default function ThreadReport({ result }: { result: ThreadResult }) {
  const { summary, deadlocks, threads, hotspots, stack_groups } = result;
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);

  const stateEntries = Object.entries(summary.states).filter(([, v]) => v > 0);

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border p-5 shadow-sm col-span-2 sm:col-span-1">
          <p className="text-sm text-gray-500">Total de Threads</p>
          <p className="text-3xl font-bold text-blue-700">{summary.total_threads}</p>
        </div>
        {stateEntries.map(([state, count]) => (
          <div key={state} className="bg-white rounded-xl border p-5 shadow-sm">
            <p className="text-sm text-gray-500">{state}</p>
            <p className="text-2xl font-bold text-gray-700">{count}</p>
          </div>
        ))}
      </div>

      {/* Deadlock alert */}
      {summary.deadlocks_found && (
        <div className="bg-red-50 border-2 border-red-400 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🔴</span>
            <h2 className="text-lg font-bold text-red-700">Deadlock Detectado!</h2>
          </div>
          {deadlocks.map((dl, i) => (
            <div key={i} className="mb-4">
              <p className="font-medium text-red-800 mb-1">Threads envolvidas: {dl.threads.join(", ")}</p>
              <pre className="text-xs text-red-700 bg-red-100 rounded p-3 overflow-auto whitespace-pre-wrap">
                {dl.description}
              </pre>
            </div>
          ))}
        </div>
      )}

      {/* Hotspots */}
      {hotspots.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Frames Mais Frequentes</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2">Frame</th>
                <th className="pb-2 text-right w-24">Ocorrências</th>
              </tr>
            </thead>
            <tbody>
              {hotspots.slice(0, 20).map((h, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-700 max-w-xl truncate">{h.frame}</td>
                  <td className="py-2 text-right">
                    <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded">
                      {h.count}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Stack Groups */}
      {stack_groups.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Grupos de Threads (por similaridade de stack)</h2>
          <div className="space-y-3">
            {stack_groups.slice(0, 20).map((g) => (
              <div key={g.stack_hash} className="border rounded-lg overflow-hidden">
                <button
                  className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
                  onClick={() => setExpandedGroup(expandedGroup === g.stack_hash ? null : g.stack_hash)}
                >
                  <div>
                    <span className="font-medium text-gray-700">{g.count} thread{g.count > 1 ? "s" : ""}</span>
                    <span className="ml-3 text-gray-500 text-sm">exemplo: {g.sample_thread}</span>
                  </div>
                  <span className="text-gray-400">{expandedGroup === g.stack_hash ? "▲" : "▼"}</span>
                </button>
                {expandedGroup === g.stack_hash && (
                  <pre className="px-4 py-3 text-xs font-mono text-gray-600 bg-white overflow-auto">
                    {g.frames.map((f) => `  at ${f}`).join("\n")}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Thread list */}
      <div className="bg-white rounded-xl border shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Todas as Threads ({threads.length})</h2>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {threads.map((t, i) => (
            <div key={i} className="border rounded-lg px-4 py-3">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATE_COLORS[t.state] || "bg-gray-100 text-gray-700"}`}>
                  {t.state}
                </span>
                <span className="font-medium text-gray-700 text-sm">{t.name}</span>
                {t.waiting_on && (
                  <span className="text-xs text-orange-600">aguardando: {t.waiting_on}</span>
                )}
              </div>
              {t.stack_trace.length > 0 && (
                <pre className="mt-2 text-xs text-gray-500 font-mono truncate">
                  at {t.stack_trace[0]}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
