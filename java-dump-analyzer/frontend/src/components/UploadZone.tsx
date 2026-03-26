import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "react-router-dom";
import { useUpload } from "../api/client";

export default function UploadZone() {
  const navigate = useNavigate();
  const { mutateAsync: upload, isLoading } = useUpload();
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (!accepted.length) return;
      const file = accepted[0];
      setError(null);
      setProgress(0);
      try {
        const res = await upload({ file, onProgress: setProgress });
        navigate(`/analysis/${res.analysis_id}`);
      } catch (e: any) {
        setError(e?.response?.data?.detail || e.message || "Upload failed");
      }
    },
    [upload, navigate]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/octet-stream": [".hprof"],
      "text/plain": [".txt"],
    },
    multiple: false,
    disabled: isLoading,
  });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 bg-white"}
          ${isLoading ? "opacity-60 cursor-not-allowed" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-4">📂</div>
        {isDragActive ? (
          <p className="text-blue-600 font-medium">Drop the file here...</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">
              Drag & drop a heap dump (.hprof) or thread dump (.txt) here
            </p>
            <p className="text-gray-400 text-sm mt-1">or click to browse</p>
          </>
        )}
      </div>

      {isLoading && (
        <div className="mt-4">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Uploading...</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
