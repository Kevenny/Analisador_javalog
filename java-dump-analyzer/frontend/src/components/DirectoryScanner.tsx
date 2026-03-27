import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "react-query";
import { useScanDir, useAnalyzeLocalFile, FileEntry } from "../api/client";

const TYPE_COLORS: Record<string, string> = {
  heap: "bg-purple-100 text-purple-700",
  thread: "bg-blue-100 text-blue-700",
  profile: "bg-orange-100 text-orange-700",
};

const TYPE_LABELS: Record<string, string> = {
  heap: "Heap Dump",
  thread: "Thread Dump",
  profile: "Profile",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export default function DirectoryScanner() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: files, isLoading, refetch } = useScanDir();
  const { mutateAsync: analyzeFile } = useAnalyzeLocalFile();
  const [analyzing, setAnalyzing] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");

  async function handleAnalyze(file: FileEntry) {
    setAnalyzing((prev) => new Set(prev).add(file.absolute_path));
    try {
      const res = await analyzeFile(file.absolute_path);
      queryClient.invalidateQueries(["analyses"]);
      navigate(`/analysis/${res.analysis_id}`);
    } catch (e: any) {
      alert(e?.response?.data?.detail || e.message || "Erro ao iniciar análise");
      setAnalyzing((prev) => {
        const next = new Set(prev);
        next.delete(file.absolute_path);
        return next;
      });
    }
  }

  const filtered = (files ?? []).filter((f) =>
    f.relative_path.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b bg-gray-50">
        <div>
          <h2 className="text-base font-semibold text-gray-800">Diretório de Dumps</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Coloque arquivos em <code className="bg-gray-100 px-1 rounded">./input_dumps/</code> no host.
            Ideal para arquivos grandes (20 GB+).
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors"
        >
          ↻ Atualizar
        </button>
      </div>

      {isLoading ? (
        <div className="px-5 py-8 text-center text-gray-400 text-sm">Escaneando diretório...</div>
      ) : !files || files.length === 0 ? (
        <div className="px-5 py-8 text-center text-gray-400 text-sm">
          <p className="mb-1">Nenhum arquivo encontrado em <code>./input_dumps/</code></p>
          <p>Adicione arquivos <code>.hprof</code>, <code>.tdump</code> ou <code>.nps</code> ao diretório e clique em Atualizar.</p>
        </div>
      ) : (
        <>
          <div className="px-5 py-3 border-b">
            <input
              type="text"
              placeholder="Filtrar arquivos..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </div>
          <div className="divide-y max-h-96 overflow-y-auto">
            {filtered.map((f) => {
              const isAnalyzing = analyzing.has(f.absolute_path);
              return (
                <div key={f.absolute_path} className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate" title={f.relative_path}>
                      {f.relative_path}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${TYPE_COLORS[f.type] ?? "bg-gray-100 text-gray-600"}`}>
                        {TYPE_LABELS[f.type] ?? f.type}
                      </span>
                      <span className="text-xs text-gray-400">{formatBytes(f.size_bytes)}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleAnalyze(f)}
                    disabled={isAnalyzing}
                    className="flex-shrink-0 px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isAnalyzing ? "Iniciando..." : "Analisar"}
                  </button>
                </div>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-5 py-6 text-center text-gray-400 text-sm">
                Nenhum arquivo corresponde ao filtro.
              </div>
            )}
          </div>
          <div className="px-5 py-2 border-t bg-gray-50 text-xs text-gray-400">
            {filtered.length} de {files.length} arquivo{files.length !== 1 ? "s" : ""}
          </div>
        </>
      )}
    </div>
  );
}
