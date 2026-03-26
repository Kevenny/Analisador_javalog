import { useNavigate } from "react-router-dom";
import { useHistory } from "../api/client";
import UploadZone from "../components/UploadZone";

export default function Home() {
  const navigate = useNavigate();
  const { data: history } = useHistory();

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Upload a Java Dump</h1>
        <p className="text-gray-500 mb-6">
          Upload a heap dump (.hprof) or thread dump (.txt / jstack) to get a detailed analysis.
        </p>
        <UploadZone />
      </div>

      {history && history.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Recent Analyses</h2>
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr className="text-left text-gray-500">
                  <th className="px-4 py-3">File</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((a) => (
                  <tr
                    key={a.id}
                    className="border-t hover:bg-blue-50 cursor-pointer"
                    onClick={() => navigate(`/analysis/${a.id}`)}
                  >
                    <td className="px-4 py-3 text-blue-700 hover:underline">{a.filename}</td>
                    <td className="px-4 py-3 capitalize">
                      <span className="bg-gray-100 px-2 py-0.5 rounded text-xs font-medium text-gray-700">
                        {a.type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          a.status === "done"
                            ? "bg-green-100 text-green-700"
                            : a.status === "error"
                            ? "bg-red-100 text-red-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
