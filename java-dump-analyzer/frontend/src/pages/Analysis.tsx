import { useParams, Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "react-query";
import { useAnalysis, useDeleteAnalysis, useCancelAnalysis } from "../api/client";
import AnalysisStatus from "../components/AnalysisStatus";
import HeapReport from "../components/HeapReport";
import ThreadReport from "../components/ThreadReport";
import ProfileReport from "../components/ProfileReport";

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const analysisId = id ? parseInt(id, 10) : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useAnalysis(analysisId, true);
  const { mutateAsync: deleteAnalysis, isLoading: isDeleting } = useDeleteAnalysis();
  const { mutateAsync: cancelAnalysis, isLoading: isCancelling } = useCancelAnalysis();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-400">Carregando...</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500 mb-4">Falha ao carregar análise.</p>
        <Link to="/" className="text-blue-600 hover:underline">
          Voltar ao início
        </Link>
      </div>
    );
  }

  const isPending = data.status === "queued" || data.status === "processing";

  async function handleDelete() {
    if (!analysisId) return;
    if (!confirm("Excluir esta análise?")) return;
    await deleteAnalysis(analysisId);
    queryClient.invalidateQueries(["analyses"]);
    navigate("/");
  }

  async function handleCancel() {
    if (!analysisId) return;
    await cancelAnalysis(analysisId);
    queryClient.invalidateQueries(["analysis", analysisId]);
    queryClient.invalidateQueries(["analyses"]);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Link to="/" className="text-blue-600 hover:underline text-sm">
            ← Início
          </Link>
          <span className="text-gray-300">/</span>
          <span className="text-gray-700 text-sm font-medium">{data.filename}</span>
        </div>
        <div className="flex items-center gap-2">
          {isPending && (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-yellow-300 text-yellow-700 hover:bg-yellow-50 disabled:opacity-50 transition-colors"
            >
              ⏹ {isCancelling ? "Cancelando..." : "Cancelar"}
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            🗑 {isDeleting ? "Excluindo..." : "Excluir"}
          </button>
        </div>
      </div>

      {isPending && <AnalysisStatus status={data.status} filename={data.filename} />}

      {data.status === "error" && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <AnalysisStatus status="error" filename={data.filename} />
          {data.error_message && (
            <pre className="mt-4 text-xs text-red-700 bg-red-100 rounded p-4 overflow-auto">
              {data.error_message}
            </pre>
          )}
        </div>
      )}

      {data.status === "done" && data.result && (
        <div>
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-gray-900">{data.filename}</h1>
            <span className="bg-gray-100 px-3 py-1 rounded-full text-sm font-medium text-gray-700">
              {data.type === "heap" ? "Heap Dump" : data.type === "profile" ? "Profile (.nps)" : "Thread Dump"}
            </span>
          </div>
          {data.type === "heap" ? (
            <HeapReport result={data.result} />
          ) : data.type === "profile" ? (
            <ProfileReport result={data.result} />
          ) : (
            <ThreadReport result={data.result} />
          )}
        </div>
      )}
    </div>
  );
}
