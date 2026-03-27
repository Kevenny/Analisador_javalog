import { useNavigate } from "react-router-dom";
import { useQueryClient } from "react-query";
import { useHistory, useDeleteAnalysis, useCancelAnalysis } from "../api/client";
import UploadZone from "../components/UploadZone";

const TYPE_LABELS: Record<string, string> = {
  heap: "Heap Dump",
  thread: "Thread Dump",
  profile: "Profile",
};

const STATUS_CLASSES: Record<string, string> = {
  done: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
  queued: "bg-yellow-100 text-yellow-700",
  processing: "bg-blue-100 text-blue-700",
};

const STATUS_LABELS: Record<string, string> = {
  done: "Concluído",
  error: "Erro",
  queued: "Na fila",
  processing: "Processando",
};

export default function Home() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: history } = useHistory();
  const { mutateAsync: deleteAnalysis } = useDeleteAnalysis();
  const { mutateAsync: cancelAnalysis } = useCancelAnalysis();

  async function handleDelete(e: React.MouseEvent, id: number) {
    e.stopPropagation();
    if (!confirm("Excluir esta análise?")) return;
    await deleteAnalysis(id);
    queryClient.invalidateQueries(["analyses"]);
  }

  async function handleCancel(e: React.MouseEvent, id: number) {
    e.stopPropagation();
    await cancelAnalysis(id);
    queryClient.invalidateQueries(["analyses"]);
  }

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Upload de Dump Java</h1>
        <p className="text-gray-500 mb-6">
          Envie um heap dump (.hprof), thread dump (.tdump) ou profile (.nps) para análise.
        </p>
        <UploadZone />
      </div>

      {history && history.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Análises Recentes</h2>
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr className="text-left text-gray-500">
                  <th className="px-4 py-3">Arquivo</th>
                  <th className="px-4 py-3">Tipo</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3 w-24 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {history.map((a) => {
                  const isPending = a.status === "queued" || a.status === "processing";
                  return (
                    <tr
                      key={a.id}
                      className="border-t hover:bg-blue-50 cursor-pointer"
                      onClick={() => navigate(`/analysis/${a.id}`)}
                    >
                      <td className="px-4 py-3 text-blue-700 hover:underline max-w-xs truncate">
                        {a.filename}
                      </td>
                      <td className="px-4 py-3">
                        <span className="bg-gray-100 px-2 py-0.5 rounded text-xs font-medium text-gray-700">
                          {TYPE_LABELS[a.type] ?? a.type}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASSES[a.status] ?? "bg-gray-100 text-gray-700"}`}>
                          {STATUS_LABELS[a.status] ?? a.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(a.created_at).toLocaleString("pt-BR")}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          {isPending && (
                            <button
                              title="Cancelar análise"
                              className="p-1.5 rounded hover:bg-yellow-100 text-yellow-600 hover:text-yellow-800 transition-colors"
                              onClick={(e) => handleCancel(e, a.id)}
                            >
                              ⏹
                            </button>
                          )}
                          <button
                            title="Excluir análise"
                            className="p-1.5 rounded hover:bg-red-100 text-red-400 hover:text-red-700 transition-colors"
                            onClick={(e) => handleDelete(e, a.id)}
                          >
                            🗑
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
