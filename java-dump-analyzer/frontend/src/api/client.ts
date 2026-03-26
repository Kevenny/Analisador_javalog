import axios from "axios";
import { useQuery, useMutation } from "react-query";

const api = axios.create({ baseURL: "/api" });

export interface UploadResponse {
  job_id: string;
  analysis_id: number;
  status: string;
}

export interface AnalysisSummary {
  id: number;
  filename: string;
  type: string;
  status: string;
  created_at: string;
}

export interface AnalysisDetail extends AnalysisSummary {
  job_id: string;
  result: any;
  error_message: string | null;
}

export function useUpload() {
  return useMutation(
    async ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (pct: number) => void;
    }): Promise<UploadResponse> => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<UploadResponse>("/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total && onProgress) {
            onProgress(Math.round((e.loaded * 100) / e.total));
          }
        },
      });
      return data;
    }
  );
}

export function useAnalysis(id: number | null, refetchWhilePending = false) {
  return useQuery<AnalysisDetail>(
    ["analysis", id],
    async () => {
      const { data } = await api.get<AnalysisDetail>(`/analysis/${id}`);
      return data;
    },
    {
      enabled: id !== null,
      refetchInterval: (data) => {
        if (!refetchWhilePending) return false;
        if (!data) return 3000;
        return data.status === "done" || data.status === "error" ? false : 3000;
      },
    }
  );
}

export function useHistory(page = 1) {
  return useQuery<AnalysisSummary[]>(["analyses", page], async () => {
    const { data } = await api.get<AnalysisSummary[]>(`/analyses?page=${page}`);
    return data;
  });
}
