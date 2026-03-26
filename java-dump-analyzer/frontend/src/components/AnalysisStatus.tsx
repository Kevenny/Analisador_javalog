interface Props {
  status: string;
  filename: string;
}

const STATUS_LABELS: Record<string, string> = {
  queued: "Na fila — aguardando worker...",
  processing: "Processando — analisando o dump...",
  done: "Análise concluída",
  error: "Falha na análise",
};

export default function AnalysisStatus({ status, filename }: Props) {
  const isDone = status === "done";
  const isError = status === "error";

  return (
    <div className="flex flex-col items-center gap-4 py-12">
      {!isDone && !isError && (
        <svg
          className="animate-spin h-12 w-12 text-blue-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
      )}
      {isError && <div className="text-4xl">❌</div>}
      {isDone && <div className="text-4xl">✅</div>}
      <p className="text-gray-700 font-medium">{STATUS_LABELS[status] || status}</p>
      <p className="text-gray-400 text-sm">{filename}</p>
    </div>
  );
}
