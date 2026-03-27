import { useParams, Link } from "react-router-dom";
import { useAnalysis } from "../api/client";
import AnalysisStatus from "../components/AnalysisStatus";
import HeapReport from "../components/HeapReport";
import ThreadReport from "../components/ThreadReport";
import ProfileReport from "../components/ProfileReport";

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const analysisId = id ? parseInt(id, 10) : null;
  const { data, isLoading, isError } = useAnalysis(analysisId, true);

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

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <Link to="/" className="text-blue-600 hover:underline text-sm">
          ← Home
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-gray-700 text-sm font-medium">{data.filename}</span>
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
