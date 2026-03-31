import { useState } from "react";

interface Insight {
  nivel: "info" | "aviso" | "critico";
  titulo: string;
  descricao: string;
}

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
    capture_duration_ms?: number;
    snapshot_type?: number;
  };
  package_breakdown?: Array<{ package: string; frame_count: number; percent: number }>;
  insights?: Insight[];
  deadlocks: Array<{ threads: string[]; description: string }>;
  threads: ProfileThread[];
  hotspots: Array<{ frame: string; count: number; percent?: number }>;
  stack_groups: Array<{ stack_hash: string; count: number; sample_thread: string; frames: string[] }>;
}

const NIVEL_STYLE: Record<string, string> = {
  info:    "bg-blue-50 border-blue-200 text-blue-800",
  aviso:   "bg-yellow-50 border-yellow-300 text-yellow-800",
  critico: "bg-red-50 border-red-400 text-red-800",
};
const NIVEL_ICON: Record<string, string> = { info: "ℹ️", aviso: "⚠️", critico: "🔴" };

const PKG_COLORS = [
  "bg-purple-400", "bg-blue-400", "bg-teal-400", "bg-orange-400",
  "bg-rose-400", "bg-indigo-400", "bg-cyan-400", "bg-amber-400",
];

export default function ProfileReport({ result }: { result: ProfileResult }) {
  const { summary, package_breakdown, insights, threads, hotspots } = result;
  const [expandedThread, setExpandedThread] = useState<number | null>(null);

  const totalFrames = threads.reduce((acc, t) => acc + t.stack_trace.length, 0);

  return (
    <div className="space-y-8">

      {/* Insights */}
      {insights && insights.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Contexto e Insights</h2>
          <div className="space-y-3">
            {insights.map((ins, i) => (
              <div key={i} className={`flex gap-3 border rounded-xl p-4 ${NIVEL_STYLE[ins.nivel] ?? NIVEL_STYLE.info}`}>
                <span className="text-lg flex-shrink-0">{NIVEL_ICON[ins.nivel]}</span>
                <div>
                  <p className="font-semibold text-sm">{ins.titulo}</p>
                  <p className="text-sm mt-0.5 opacity-90">{ins.descricao}</p>
                </div>
              </div>
            ))}
          </div>
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

      {/* Package Breakdown */}
      {package_breakdown && package_breakdown.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Distribuição por Pacote</h2>
          <p className="text-xs text-gray-400 mb-4">Frequência de frames agrupados por pacote Java.</p>
          {/* Stacked bar visual */}
          <div className="flex w-full h-6 rounded-full overflow-hidden mb-4">
            {package_breakdown.slice(0, 8).map((pkg, i) => (
              <div
                key={i}
                className={`${PKG_COLORS[i % PKG_COLORS.length]} transition-all`}
                style={{ width: `${pkg.percent}%` }}
                title={`${pkg.package}: ${pkg.percent.toFixed(1)}%`}
              />
            ))}
          </div>
          <div className="space-y-2">
            {package_breakdown.map((pkg, i) => (
              <div key={i} className="flex items-center gap-3">
                {i < 8 && (
                  <div className={`w-3 h-3 rounded-full flex-shrink-0 ${PKG_COLORS[i % PKG_COLORS.length]}`} />
                )}
                {i >= 8 && <div className="w-3 h-3 flex-shrink-0" />}
                <span className="font-mono text-xs text-gray-600 w-48 truncate flex-shrink-0" title={pkg.package}>
                  {pkg.package}
                </span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${PKG_COLORS[i % PKG_COLORS.length]}`}
                    style={{ width: `${pkg.percent}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-16 text-right">{pkg.frame_count.toLocaleString()} frames</span>
                <span className="text-xs font-medium text-purple-700 w-10 text-right">{pkg.percent.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
                <th className="pb-2 text-right w-16">%</th>
                <th className="pb-2 text-right w-24">Ocorrências</th>
              </tr>
            </thead>
            <tbody>
              {hotspots.slice(0, 30).map((h, i) => {
                const pct = h.percent ?? Math.round((h.count / (hotspots[0]?.count || 1)) * 100);
                return (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-2 text-gray-400 text-xs">{i + 1}</td>
                    <td className="py-2 pr-4">
                      <div className="font-mono text-xs text-gray-700 truncate max-w-xl" title={h.frame}>
                        {h.frame}
                      </div>
                      <div className="mt-1 h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-orange-400 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                    </td>
                    <td className="py-2 text-right text-xs text-gray-500">{pct.toFixed(1)}%</td>
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
