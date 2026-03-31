import { useState } from "react";

interface Insight {
  nivel: "info" | "aviso" | "critico";
  titulo: string;
  descricao: string;
}

interface ThreadInfo {
  name: string;
  state: string;
  priority: number;
  stack_trace: string[];
  waiting_on: string | null;
  locked: string[];
  category?: string;
}

interface CategoryInfo {
  count: number;
  percent: number;
  threads: string[];
}

interface LockContention {
  lock_id: string;
  lock_type: string;
  holder: string | null;
  waiters: string[];
}

interface ThreadResult {
  summary: {
    total_threads: number;
    states: Record<string, number>;
    deadlocks_found: boolean;
    jvm_info?: string;
    app_threads?: number;
    jvm_system_threads?: number;
  };
  categories?: Record<string, CategoryInfo>;
  lock_contention?: LockContention[];
  insights?: Insight[];
  deadlocks: Array<{ threads: string[]; description: string }>;
  threads: ThreadInfo[];
  hotspots: Array<{ frame: string; count: number }>;
  stack_groups: Array<{ stack_hash: string; count: number; sample_thread: string; frames: string[] }>;
}

const STATE_COLORS: Record<string, string> = {
  RUNNABLE:      "bg-green-100 text-green-800",
  BLOCKED:       "bg-red-100 text-red-800",
  WAITING:       "bg-yellow-100 text-yellow-800",
  TIMED_WAITING: "bg-orange-100 text-orange-800",
  DESCONHECIDO:  "bg-gray-100 text-gray-600",
};

const CATEGORY_COLORS: Record<string, string> = {
  jvm_sistema:  "bg-slate-100 text-slate-600",
  rmi:          "bg-cyan-100 text-cyan-700",
  servidor_rpc: "bg-purple-100 text-purple-700",
  monitoramento:"bg-teal-100 text-teal-700",
  http_servidor:"bg-blue-100 text-blue-700",
  agendador:    "bg-indigo-100 text-indigo-700",
  banco_dados:  "bg-amber-100 text-amber-700",
  aplicacao:    "bg-green-100 text-green-700",
};

const CATEGORY_LABELS: Record<string, string> = {
  jvm_sistema:  "JVM Sistema",
  rmi:          "RMI",
  servidor_rpc: "Servidor RPC",
  monitoramento:"Monitoramento",
  http_servidor:"HTTP Servidor",
  agendador:    "Agendador",
  banco_dados:  "Banco de Dados",
  aplicacao:    "Aplicação",
};

const NIVEL_STYLE: Record<string, string> = {
  info:    "bg-blue-50 border-blue-200 text-blue-800",
  aviso:   "bg-yellow-50 border-yellow-300 text-yellow-800",
  critico: "bg-red-50 border-red-400 text-red-800",
};
const NIVEL_ICON: Record<string, string> = { info: "ℹ️", aviso: "⚠️", critico: "🔴" };

export default function ThreadReport({ result }: { result: ThreadResult }) {
  const { summary, categories, lock_contention, insights, deadlocks, threads, hotspots, stack_groups } = result;
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [expandedCat, setExpandedCat] = useState<string | null>(null);
  const [expandedLock, setExpandedLock] = useState<string | null>(null);

  const stateEntries = Object.entries(summary.states).filter(([, v]) => v > 0);

  return (
    <div className="space-y-8">

      {/* JVM info */}
      {summary.jvm_info && (
        <div className="bg-gray-50 border rounded-lg px-4 py-2 text-xs text-gray-500 font-mono">
          {summary.jvm_info}
        </div>
      )}

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

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border p-5 shadow-sm col-span-2 sm:col-span-1">
          <p className="text-sm text-gray-500">Total de Threads</p>
          <p className="text-3xl font-bold text-blue-700">{summary.total_threads}</p>
          {(summary.app_threads !== undefined) && (
            <p className="text-xs text-gray-400 mt-1">
              {summary.app_threads} app · {summary.jvm_system_threads} JVM
            </p>
          )}
        </div>
        {stateEntries.map(([state, count]) => (
          <div key={state} className="bg-white rounded-xl border p-5 shadow-sm">
            <p className="text-sm text-gray-500">{state.replace("_", " ")}</p>
            <p className="text-2xl font-bold text-gray-700">{count}</p>
            <p className="text-xs text-gray-400">{(count / summary.total_threads * 100).toFixed(1)}%</p>
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

      {/* Categories */}
      {categories && Object.keys(categories).length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Categorias de Threads</h2>
          <div className="space-y-2">
            {Object.entries(categories)
              .sort(([, a], [, b]) => b.count - a.count)
              .map(([cat, info]) => (
                <div key={cat} className="border rounded-lg overflow-hidden">
                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left"
                    onClick={() => setExpandedCat(expandedCat === cat ? null : cat)}
                  >
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${CATEGORY_COLORS[cat] ?? "bg-gray-100 text-gray-600"}`}>
                      {CATEGORY_LABELS[cat] ?? cat}
                    </span>
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-blue-400"
                        style={{ width: `${info.percent}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-gray-700 w-8 text-right">{info.count}</span>
                    <span className="text-xs text-gray-400 w-10 text-right">{info.percent.toFixed(1)}%</span>
                    <span className="text-gray-400">{expandedCat === cat ? "▲" : "▼"}</span>
                  </button>
                  {expandedCat === cat && (
                    <div className="px-4 py-3 bg-white">
                      <div className="flex flex-wrap gap-1">
                        {info.threads.map((t, ti) => (
                          <span key={ti} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono truncate max-w-xs" title={t}>
                            {t.length > 50 ? t.slice(0, 48) + "…" : t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Lock Contention */}
      {lock_contention && lock_contention.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Contenção de Lock</h2>
          <p className="text-xs text-gray-400 mb-4">Locks disputados por múltiplas threads.</p>
          <div className="space-y-2">
            {lock_contention.map((lc, i) => (
              <div key={i} className="border rounded-lg overflow-hidden">
                <button
                  className="w-full flex items-center gap-3 px-4 py-3 bg-orange-50 hover:bg-orange-100 text-left"
                  onClick={() => setExpandedLock(expandedLock === lc.lock_id ? null : lc.lock_id)}
                >
                  <span className="font-mono text-xs text-orange-700 font-medium flex-shrink-0">
                    0x{lc.lock_id}
                  </span>
                  <span className="text-xs text-gray-500 truncate flex-1">{lc.lock_type}</span>
                  <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium flex-shrink-0">
                    {lc.waiters.length} aguardando
                  </span>
                  <span className="text-gray-400">{expandedLock === lc.lock_id ? "▲" : "▼"}</span>
                </button>
                {expandedLock === lc.lock_id && (
                  <div className="px-4 py-3 bg-white space-y-2 text-sm">
                    {lc.holder && (
                      <p>
                        <span className="font-medium text-green-700">Detentora: </span>
                        <span className="font-mono text-xs">{lc.holder}</span>
                      </p>
                    )}
                    <div>
                      <p className="font-medium text-red-700 mb-1">Aguardando ({lc.waiters.length}):</p>
                      <ul className="space-y-0.5">
                        {lc.waiters.map((w, wi) => (
                          <li key={wi} className="font-mono text-xs text-gray-600">{w}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hotspots */}
      {hotspots.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Frames Mais Frequentes</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2 w-8">#</th>
                <th className="pb-2">Frame</th>
                <th className="pb-2 text-right w-24">Ocorrências</th>
              </tr>
            </thead>
            <tbody>
              {hotspots.slice(0, 20).map((h, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-2 text-gray-400 text-xs">{i + 1}</td>
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
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATE_COLORS[t.state] ?? "bg-gray-100 text-gray-700"}`}>
                  {t.state}
                </span>
                {t.category && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ${CATEGORY_COLORS[t.category] ?? "bg-gray-100 text-gray-600"}`}>
                    {CATEGORY_LABELS[t.category] ?? t.category}
                  </span>
                )}
                <span className="font-medium text-gray-700 text-sm truncate max-w-md">{t.name}</span>
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
