import React, { useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "../state/auth.jsx";

export default function Submissions() {
  const { API, authHeader, user } = useAuth();
  const [submissions, setSubmissions] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  // Use same header helper as Datasets.jsx (keeps behavior identical)
  const getHeaders = () => (typeof authHeader === "function" ? authHeader() : authHeader || {});

  const loadAll = async () => {
    setLoading(true);
    try {
      const headers = getHeaders();

      // load submissions
      const sRes = await fetch(`${API}/submissions?page=1&page_size=200`, { headers });
      const sJson = sRes.ok ? await sRes.json() : [];
      const sItems = sJson.items ?? sJson.results ?? sJson.data ?? sJson ?? [];

      // Normalize submissions: parse metrics JSON and promote common metric keys
      const normalized = (Array.isArray(sItems) ? sItems : []).map((s) => {
        const copy = { ...s };

        // parse legacy/backend variants: score_json -> metrics
        if (copy.score_json && typeof copy.score_json === "string") {
          try {
            copy.metrics = JSON.parse(copy.score_json);
          } catch {
            copy.metrics = undefined;
          }
        } else if (copy.score_json && typeof copy.score_json === "object") {
          copy.metrics = copy.metrics ?? copy.score_json;
        }

        // parse metrics if it's still a JSON string
        if (typeof copy.metrics === "string") {
          try {
            copy.metrics = JSON.parse(copy.metrics);
          } catch {
            // ignore parse error
          }
        }

        // promote common metric keys from metrics or nested structures
        if (copy.metrics && typeof copy.metrics === "object") {
          // direct keys
          ["f1", "precision", "recall", "accuracy", "auc"].forEach((k) => {
            if (copy[k] === undefined && copy.metrics[k] !== undefined) {
              copy[k] = copy.metrics[k];
            }
          });
          // some backends place results under .results
          if (copy.metrics.results && typeof copy.metrics.results === "object") {
            Object.keys(copy.metrics.results).forEach((mk) => {
              if (["f1", "precision", "recall", "accuracy", "auc"].includes(mk) && copy[mk] === undefined) {
                copy[mk] = copy.metrics.results[mk];
              }
            });
          }
        }

        // map auc -> accuracy/score for UI where appropriate
        if (copy.accuracy === undefined && copy.auc !== undefined) {
          copy.accuracy = copy.auc;
        }
        if (copy.score === undefined && copy.auc !== undefined) {
          copy.score = copy.auc;
        }

        // ensure score alias is present from accuracy if needed
        if (copy.score === undefined && copy.accuracy !== undefined) {
          copy.score = copy.accuracy;
        }

        // uploaded time fallback
        if (!copy.uploaded_at) {
          if (copy.created_at) copy.uploaded_at = copy.created_at;
          else if (copy.created) copy.uploaded_at = copy.created;
        }
        // filename fallback from other possible fields
        if (!copy.filename) {
          const f = copy.file_name || copy.file_path || copy.path || copy.storage_path;
          if (f) {
            const parts = String(f).split("/").pop().split("\\").pop();
            copy.filename = parts;
          }
        }
        return copy;
      });

      setSubmissions(normalized);

      // --- replace fetch with axios to surface backend validation error ---
      let dItems = [];
      try {
        const resp = await axios.get(`${API}/datasets/`, {
          params: { page: 1, page_size: 50 }, // use safe page_size to avoid 422
          headers: headers,
        });
        dItems = resp.data.items ?? resp.data.results ?? resp.data.data ?? resp.data ?? [];
        console.log("datasets response", resp.data);
      } catch (err) {
        // show full error payload (FastAPI returns validation details in response.data)
        console.error("datasets axios error", err.response?.status, err.response?.data ?? err.message);
        setMsg(
          err.response?.data?.detail
            ? String(err.response.data.detail)
            : `Datasets load error: ${err.response?.status || err.message}`
        );
        dItems = [];
      }

      setDatasets(Array.isArray(dItems) ? dItems : []);
      if (!selectedDatasetId && dItems.length > 0) {
        setSelectedDatasetId(String(dItems[0].id ?? ""));
      }
      if (!dItems.length && !msg) {
        setMsg(dItems.length === 0 ? "No datasets available" : "");
      }
    } catch (err) {
      console.error("loadAll error", err);
      setMsg("Failed to load submissions/datasets");
      setSubmissions([]);
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const upload = async (e) => {
    e.preventDefault();
    if (!file) {
      setMsg("Choose a file to upload");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    if (selectedDatasetId) fd.append("dataset_id", selectedDatasetId);
    try {
      const headers = getHeaders();
      await axios.post(`${API}/submissions/`, fd, {
        headers,
      });
      setMsg("Uploaded");
      setFile(null);
      // refresh lists
      await loadAll();
    } catch (ex) {
      console.error("upload error", ex);
      const errMsg = ex.response?.data?.detail || ex.message || "Upload failed";
      setMsg(errMsg);
      window.alert("Upload error: " + errMsg);
    }
  };

  const deleteSubmission = async (id, uploaderId) => {
    // allow only admin or owner in UI, backend will enforce too
    if (user?.role !== "admin" && user?.id !== uploaderId) {
      alert("Not allowed to delete this submission");
      return;
    }
    if (!confirm("Delete this submission?")) return;
    try {
      const headers = getHeaders();
      await axios.delete(`${API}/submissions/${id}`, { headers });
      setMsg("Deleted");
      await loadAll();
    } catch (err) {
      console.error("delete error", err);
      alert("Failed to delete submission");
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-2xl font-semibold">Submissions</div>

      <form onSubmit={upload} className="card grid gap-3">
        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <div className="label">Dataset to evaluate against</div>
            <select
              className="input"
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
            >
              <option value="">(none)</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name ?? d.id} {d.is_official ? "— Official" : ""}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="label">Submission file (CSV)</div>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        </div>

        <div>
          <button className="btn" type="submit" disabled={!file}>
            Upload submission
          </button>
          {msg && <span className="text-sm ml-3">{msg}</span>}
        </div>
      </form>

      {loading ? (
        <div className="card">Loading submissions...</div>
      ) : submissions.length === 0 ? (
        <div className="card">No submissions found.</div>
      ) : (
        <div className="grid gap-3">
          {submissions.map((s) => (
            <div key={s.id ?? s.filename} className="card flex items-center justify-between p-4">
              {/* left: basic info */}
              <div className="flex-1 pr-6">
                <div className="text-lg font-semibold">{s.filename ?? "submission"}</div>
                <div className="text-sm text-gray-600 mt-1">
                  Dataset:{" "}
                  <span className="font-medium text-gray-800">
                    {s.dataset_name ?? (s.dataset_id ? `Dataset ${s.dataset_id}` : "—")}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  Uploader:{" "}
                  <span className="font-medium text-gray-800">{String(s.uploader_id ?? s.uploader ?? "N/A")}</span>
                </div>
                {s.uploaded_at && (
                  <div className="text-xs text-gray-500 mt-1">
                    Uploaded: {new Date(s.uploaded_at).toLocaleString()}
                  </div>
                )}
              </div>

              {/* right: metrics + actions */}
              <div className="flex items-center gap-4">
                {/* metrics card (moved slightly left) */}
                <div className="w-100 mr-10 bg-gradient-to-br from-white to-gray-50 border border-gray-200 rounded-lg p-4 shadow-sm flex items-center space-x-6">
                  {/* four metrics horizontally with extra spacing */}
                  <div className="flex-1 text-center min-w-[64px]">
                    <div className="text-xs text-gray-500 uppercase tracking-wide">F1</div>
                    <div className="text-2xl text-indigo-600 font-semibold">
                      {s.f1 !== undefined ? Number(s.f1).toFixed(3) : "—"}
                    </div>
                  </div>
                  <div className="flex-1 text-center min-w-[64px]">
                    <div className="text-xs text-gray-500 uppercase tracking-wide">Accuracy</div>
                    <div className="text-2xl text-indigo-600 font-semibold">
                      {s.accuracy !== undefined ? Number(s.accuracy).toFixed(3) : "—"}
                    </div>
                  </div>
                  <div className="flex-1 text-center min-w-[64px]">
                    <div className="text-xs text-gray-500 uppercase tracking-wide">Recall</div>
                    <div className="text-2xl text-indigo-600 font-semibold">
                      {s.recall !== undefined ? Number(s.recall).toFixed(3) : "—"}
                    </div>
                  </div>
                  <div className="flex-1 text-center min-w-[64px]">
                    <div className="text-xs text-gray-500 uppercase tracking-wide">AUC</div>
                    <div className="text-2xl text-indigo-600 font-semibold">
                      {s.auc !== undefined ? Number(s.auc).toFixed(3) : "—"}
                    </div>
                  </div>
                </div>

                {/* actions */}
                <div className="flex flex-col items-end gap-2">
                  <a
                    className="btn"
                    href={`${API}/submissions/${s.id}/download`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                  {(user?.role === "admin" || user?.id === s.uploader_id) && (
                    <button className="btn btn-danger" onClick={() => deleteSubmission(s.id, s.uploader_id)}>
                      Delete
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
