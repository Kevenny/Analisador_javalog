import { Cell, Pie, PieChart, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface Insight {
  nivel: "info" | "aviso" | "critico";
  titulo: string;
  descricao: string;
}

interface HeapResult {
  summary: {
    heap_size_bytes: number;
    total_objects: number;
    analysis_date: string;
    note?: string;
  };
  leak_suspects: Array<{ description: string; retained_bytes: number; percentage: number }>;
  top_consumers: Array<{ class_name: string; instances: number; retained_bytes: number; percentage: number }>;
  dominator_tree: Array<{ object: string; retained_bytes: number; percentage: number }>;
  package_breakdown?: Array<{ package: string; instance_count: number; retained_bytes: number; percent: number }>;
  insights?: Insight[];
}

const COLORS = ["#3b82f6","#6366f1","#8b5cf6","#ec4899","#f43f5e","#f97316","#eab308","#22c55e","#14b8a6","#06b6d4"];

const NIVEL_STYLE: Record<string, string> = {
  info:    "bg-blue-50 border-blue-200 text-blue-800",
  aviso:   "bg-yellow-50 border-yellow-300 text-yellow-800",
  critico: "bg-red-50 border-red-400 text-red-800",
};
const NIVEL_ICON: Record<string, string> = {
  info: "ℹ️", aviso: "⚠️", critico: "🔴",
};

function fmt(bytes: number) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(2)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(2)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(2)} KB`;
  return `${bytes} B`;
}

function InsightsList({ insights }: { insights: Insight[] }) {
  if (!insights?.length) return null;
  return (
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
  );
}

export default function HeapReport({ result }: { result: HeapResult }) {
  const { summary, leak_suspects, top_consumers, dominator_tree, package_breakdown, insights } = result;

  const pieData = top_consumers.slice(0, 10).map((c) => ({
    name: c.class_name.split(".").pop() || c.class_name,
    value: c.retained_bytes,
  }));

  return (
    <div className="space-y-8">
      {/* Insights */}
      {insights && insights.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Contexto e Insights</h2>
          <InsightsList insights={insights} />
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Tamanho do Heap</p>
          <p className="text-2xl font-bold text-blue-700">{fmt(summary.heap_size_bytes)}</p>
        </div>
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Total de Objetos</p>
          <p className="text-2xl font-bold text-blue-700">{summary.total_objects.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl border p-5 shadow-sm">
          <p className="text-sm text-gray-500">Data da Análise</p>
          <p className="text-lg font-semibold text-gray-700">{new Date(summary.analysis_date).toLocaleString("pt-BR")}</p>
        </div>
      </div>

      {summary.note && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800 text-sm">
          {summary.note}
        </div>
      )}

      {/* Package Breakdown */}
      {package_breakdown && package_breakdown.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Consumo por Pacote</h2>
          <p className="text-xs text-gray-400 mb-4">Memória retida agrupada por pacote Java.</p>
          <div className="space-y-2">
            {package_breakdown.map((pkg, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="font-mono text-xs text-gray-600 w-48 truncate flex-shrink-0" title={pkg.package}>
                  {pkg.package}
                </span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pkg.percent}%` }} />
                </div>
                <span className="text-xs text-gray-500 w-16 text-right">{fmt(pkg.retained_bytes)}</span>
                <span className="text-xs font-medium text-blue-700 w-10 text-right">{pkg.percent.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leak Suspects */}
      {leak_suspects.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Suspeitos de Vazamento</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2">Descrição</th>
                <th className="pb-2 text-right">Retido</th>
                <th className="pb-2 text-right w-32">%</th>
              </tr>
            </thead>
            <tbody>
              {leak_suspects.map((s, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-2 pr-4 text-gray-700 max-w-sm truncate">{s.description}</td>
                  <td className="py-2 text-right text-gray-600">{fmt(s.retained_bytes)}</td>
                  <td className="py-2 pl-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div className="bg-red-400 h-2 rounded-full" style={{ width: `${Math.min(s.percentage, 100)}%` }} />
                      </div>
                      <span className="text-gray-600 w-12 text-right">{s.percentage.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Top Consumers */}
      {top_consumers.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Maiores Consumidores</h2>
          <div className="flex flex-col lg:flex-row gap-6 items-start">
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="pb-2">Classe</th>
                    <th className="pb-2 text-right">Instâncias</th>
                    <th className="pb-2 text-right">Retido</th>
                    <th className="pb-2 text-right">%</th>
                  </tr>
                </thead>
                <tbody>
                  {top_consumers.map((c, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-2 pr-4 text-gray-700 font-mono text-xs max-w-xs truncate">{c.class_name}</td>
                      <td className="py-2 text-right text-gray-600">{c.instances.toLocaleString()}</td>
                      <td className="py-2 text-right text-gray-600">{fmt(c.retained_bytes)}</td>
                      <td className="py-2 text-right text-gray-600">{c.percentage.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pieData.length > 0 && (
              <div className="w-full lg:w-72 flex-shrink-0" style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart margin={{ top: 5, right: 5, bottom: 40, left: 5 }}>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="42%" outerRadius={85}>
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => fmt(v)} />
                    <Legend verticalAlign="bottom" height={40}
                      formatter={(value) => value.length > 20 ? value.slice(0, 18) + "…" : value}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dominator Tree */}
      {dominator_tree.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Árvore de Dominadores</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2">Objeto</th>
                <th className="pb-2 text-right">Retido</th>
                <th className="pb-2 text-right">%</th>
              </tr>
            </thead>
            <tbody>
              {dominator_tree.map((d, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-2 pr-4 text-gray-700 font-mono text-xs max-w-sm truncate">{d.object}</td>
                  <td className="py-2 text-right text-gray-600">{fmt(d.retained_bytes)}</td>
                  <td className="py-2 text-right text-gray-600">{d.percentage.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
