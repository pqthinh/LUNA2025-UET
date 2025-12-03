import React, { useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "../state/auth.jsx";
import { useLocation } from "react-router-dom";

// Format date to Vietnamese locale (Asia/Ho_Chi_Minh)
const toVietnameseTime = (dateStr) => {
  if (!dateStr) return "";
  try {
    // If timestamp has no timezone offset (e.g. "2025-12-03T05:10:43"),
    // treat it as UTC by appending 'Z' before parsing. This avoids
    // inconsistent parsing across browsers which can interpret such
    // strings as local time and cause a ~7 hour shift.
    let s = String(dateStr);
    const noTZ = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(s);
    if (noTZ) s = s + "Z";
    return new Date(s).toLocaleString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return String(dateStr);
  }
};

export default function Datasets() {
  const { API, authHeader, user } = useAuth();
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("LUNA25 Test");
  const [desc, setDesc] = useState("");
  const [dataFile, setDataFile] = useState(null);
  const [gtFile, setGtFile] = useState(null);
  const [msg, setMsg] = useState("");

  const location = useLocation();
  const qParam = (() => {
    try {
      return String(new URLSearchParams(location.search).get("q") || "").trim().toLowerCase();
    } catch {
      return "";
    }
  })();

  // Replace / implement load function to include auth header and handle 401
  const load = async () => {
    setLoading(true);
    try {
      const headers =
        typeof authHeader === "function" ? authHeader() : authHeader || {};
      const res = await fetch(`${API}/datasets?page=${page}&page_size=20`, {
        headers,
      });

      if (res.status === 401) {
        setMsg("Unauthorized — please login");
        setItems([]);
        setTotal(0);
        setLoading(false);
        return;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const json = await res.json();
      const results = json.items ?? json.results ?? json.data ?? json;
      let list = results || [];
      if (qParam) {
        list = (list || []).filter((d) => {
          const name = String(d.name || "").toLowerCase();
          const uploader = String(d.uploader_username || d.uploader_full_name || d.uploader || d.uploader_id || "").toLowerCase();
          return name.includes(qParam) || uploader.includes(qParam);
        });
      }
      setItems(list);
      setTotal(qParam ? list.length : (json.total ?? json.total_items ?? json.count ?? (results ? results.length : 0)));
      setMsg("");
    } catch (err) {
      console.error("load datasets error", err);
      setMsg("Failed to load datasets");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page, location.search]);

  const upload = async (e) => {
    e.preventDefault();
    if (!gtFile) {
      setMsg("Ground truth CSV required");
      return;
    }
    const fd = new FormData();
    fd.append("name", name);
    fd.append("description", desc);
    if (dataFile) fd.append("data_file", dataFile);
    fd.append("groundtruth_csv", gtFile);
    try {
      // axios header helper
      const headers =
        typeof authHeader === "function" ? authHeader() : authHeader || {};
      await axios.post(`${API}/datasets/`, fd, { headers });
      setMsg("Uploaded");
      setDataFile(null);
      setGtFile(null);
      load();
    } catch (ex) {
      const errMsg = ex.response?.data?.detail || "Upload failed";
      setMsg(errMsg);
      window.alert("Dataset upload error: " + errMsg);
    }
  };

  // toggle official state (admin only) — backend expected to accept is_official field or toggle
  const toggleOfficial = async (d) => {
    if (!user?.role || user.role !== "admin") return;
    const headers = typeof authHeader === "function" ? authHeader() : authHeader || {};
    const newState = !d.is_official;
    try {
      await axios.post(`${API}/datasets/${d.id}/mark_official`, { is_official: newState }, { headers });
      load();
    } catch (err) {
      console.error("toggleOfficial error", err);
      alert("Failed to change official state");
    }
  };

  const analyze = async (id) => {
    const headers = typeof authHeader === "function" ? authHeader() : authHeader || {};
    try {
      await axios.post(`${API}/datasets/${id}/analyze`, null, { headers });
      load();
    } catch (err) {
      console.error("analyze error", err);
      alert("Analyze failed");
    }
  };

  // Ensure download uses the same auth header
  const downloadGroundtruth = async (id, name) => {
    // backend enforces access (admin or dataset uploader). UI only delegates request.
    try {
      const headers =
        typeof authHeader === "function"
          ? authHeader()
          : authHeader || {};
      const res = await fetch(`${API}/datasets/${id}/groundtruth`, { headers });
      if (res.status === 401) {
        alert("Unauthorized — please login");
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(name || "dataset")}_groundtruth.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("downloadGroundtruth error:", err);
      if (err && String(err).toLowerCase().includes('403')) {
        alert('Access denied — groundtruth restricted');
      } else {
        alert("Failed to download groundtruth");
      }
    }
  };

  const hasDatasetFile = (d) => {
    const p = d?.data_file_path || d?.data_file || d?.data_url;
    return !!p && typeof p === "string" && p.length > 0;
  };

  const canDownloadDataset = (d) => {
    if (!user) return false;
    if (user.role === "admin") return true;
    return !!(hasDatasetFile(d) && (d?.is_official || d?.uploader_id === user?.id));
  };

  const downloadDataset = async (id, name) => {
    try {
      const headers = typeof authHeader === "function" ? authHeader() : authHeader || {};
      const res = await fetch(`${API}/datasets/${id}/data`, { headers });
      if (res.status === 401) {
        alert("Unauthorized — please login");
        return;
      }
      if (res.status === 403) {
        alert("Access denied");
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(name || "dataset")}_data`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("downloadDataset error:", err);
      alert("Failed to download dataset file");
    }
  };

  const canDelete = (d) => {
    if (!user) return false;
    if (user.role === "admin") return true;
    return d?.uploader_id === user?.id;
  };

  const deleteDataset = async (id) => {
    if (!window.confirm("Delete this dataset? This cannot be undone.")) return;
    try {
      const headers = typeof authHeader === "function" ? authHeader() : authHeader || {};
      const res = await fetch(`${API}/datasets/${id}`, { method: "DELETE", headers });
      if (res.status === 401) {
        alert("Unauthorized — please login");
        return;
      }
      if (res.status === 403) {
        alert("Access denied");
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (err) {
      console.error("deleteDataset error:", err);
      alert("Failed to delete dataset");
    }
  };

  // Normalize stats coming from different shapes (object or JSON string)
  const getStats = (d) => {
    if (!d) return null;
    if (d.stats_json && typeof d.stats_json === "object") return d.stats_json;
    if (d.stats && typeof d.stats === "object") return d.stats;
    if (d.stats && typeof d.stats === "string") {
      try {
        return JSON.parse(d.stats);
      } catch {
        // not JSON — ignore
      }
    }
    if (d.stats_raw && typeof d.stats_raw === "string") {
      try {
        return JSON.parse(d.stats_raw);
      } catch {}
    }
    return null;
  };

  // Display uploader as readable text (name / uploader_id / id) instead of dumping JSON
  const getUploaderDisplay = (d) => {
    // prefer explicit uploader_username/full_name provided by the API
    if (d?.uploader_username) return String(d.uploader_username);
    if (d?.uploader_full_name) return String(d.uploader_full_name);
    const u = d?.uploader;
    if (!u) {
      if (d?.uploader_id) return String(d.uploader_id);
      return "N/A";
    }
    if (typeof u === "string" || typeof u === "number") return String(u);
    if (typeof u === "object") {
      return u.name ?? u.uploader_id ?? u.id ?? JSON.stringify(u);
    }
    return String(u);
  };

  // Render any extra/unexpected fields (useful for MinIO-returned objects)
  const renderExtraFields = (d) => {
    const known = new Set([
      "id",
      "name",
      "description",
      "uploader",
      "uploader_id",
      "created_at",
      "created",
      "createdAt",
      "is_official",
      "stats_json",
      "stats",
      "stats_raw",
      "groundtruth_csv",
      "groundtruth_path",
      "groundtruth_url",
      "data_file",
      "data_file_path",
      "data_url",
    ]);
    const extras = Object.keys(d).filter(
      (k) => !known.has(k) && !k.startsWith("uploader") && !k.startsWith("user")
    );
    if (extras.length === 0) return null;
    const obj = {};
    extras.forEach((k) => (obj[k] = d[k]));
    return (
      <pre className="text-xs mt-2 bg-slate-50 p-2 rounded overflow-auto">
        {JSON.stringify(obj, null, 2)}
      </pre>
    );
  };

  return (
    <div className="space-y-6">
      <div className="text-2xl font-semibold">Datasets</div>
      {user && (
        <form onSubmit={upload} className="card grid gap-3">
          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <div className="label">Name</div>
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <div className="label">Description</div>
              <input
                className="input"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>
            <div>
              <div className="label">Data file (optional)</div>
              <input
                type="file"
                onChange={(e) => setDataFile(e.target.files[0])}
              />
            </div>
            <div>
              <div className="label">Ground truth CSV (id,label)</div>
              <input
                type="file"
                required
                onChange={(e) => setGtFile(e.target.files[0])}
              />
            </div>
          </div>
          <button className="btn w-fit" disabled={!gtFile}>
            Upload dataset
          </button>
          {msg && <div className="text-green-700 text-sm">{msg}</div>}
        </form>
      )}

      <div className="grid gap-3">
        {loading ? (
          <div className="card flex items-center gap-3">
            <div className="spinner" /> <div>Loading datasets...</div>
          </div>
        ) : items.length === 0 ? (
          <div className="card text-center text-slate-600">
            No datasets found. Upload a dataset to get started.
          </div>
        ) : (
          items.map((d) => {
            const stats = getStats(d);
            return (
              <div key={d.id || d.name} className="card">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <div className="font-semibold text-lg">{d.name}</div>
                      {d.is_official ? (
                        <span className="badge ml-2">Official</span>
                      ) : null}
                      <div className="text-sm opacity-70 ml-2">
                        {getUploaderDisplay(d)}
                        {d.created_at || d.created || d.createdAt
                          ? " • " + toVietnameseTime(d.created_at || d.created || d.createdAt)
                          : ""}
                      </div>
                    </div>
                    <div className="text-sm opacity-80 mt-1">{d.description}</div>

                    {stats && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-sm">
                        <div>
                          Total:{" "}
                          <b>
                            {stats.total_rows ??
                              stats.total_samples ??
                              stats.total ??
                              0}
                          </b>
                        </div>
                        <div>
                          Dup IDs:{" "}
                          <b>
                            {stats.duplicate_id ??
                              stats.duplicates ??
                              stats.duplicate_ids ??
                              0}
                          </b>
                        </div>
                        <div>
                          Null label: <b>{stats.null_label ?? stats.nulls ?? 0}</b>
                        </div>
                        <div>
                          Labels:{" "}
                          <b>
                            {Object.entries(
                              stats.label_distribution ||
                                stats.class_distribution ||
                                stats.labels ||
                                {}
                            )
                              .map(([k, v]) =>
                                typeof v === "number"
                                  ? `${k}:${(v * 100).toFixed(1)}%`
                                  : `${k}:${v}`
                              )
                              .join(", ")}
                          </b>
                        </div>
                      </div>
                    )}

                    {/* Extra fields for MinIO / unexpected payloads */}
                    {renderExtraFields(d)}
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <div className="flex gap-2">
                      {(user?.role === "admin" || user?.id === d?.uploader_id) && (
                        <button
                          className="btn"
                          onClick={() => downloadGroundtruth(d.id, d.name)}
                        >
                          Download GT
                        </button>
                      )}

                      {hasDatasetFile(d) && canDownloadDataset(d) && (
                        <button
                          className="btn"
                          onClick={() => downloadDataset(d.id, d.name)}
                        >
                          Download Dataset
                        </button>
                      )}

                      {canDelete(d) && (
                        <button className="btn btn-danger" onClick={() => deleteDataset(d.id)}>
                          Delete
                        </button>
                      )}

                      {(user?.role === "admin" || user?.id === d?.uploader_id) && (
                        <>
                          <button className="btn" onClick={() => analyze(d.id)}>
                            Analyze
                          </button>

                          {user?.role === "admin" && (
                            <label className="flex items-center gap-2 ml-1">
                              <input
                                type="checkbox"
                                className="checkbox"
                                checked={!!d.is_official}
                                onChange={() => toggleOfficial(d)}
                                title="Mark official (admin only)"
                              />
                              <span className="text-sm">Official</span>
                            </label>
                          )}
                        </>
                      )}
                    </div>

                    {/* small meta table shown aligned right */}
                    <div className="text-xs opacity-80 text-right mt-2">
                      <div>Uploader: {getUploaderDisplay(d)}</div>
                      <div>
                        Created:{" "}
                        {d.created_at || d.created || d.createdAt
                          ? toVietnameseTime(d.created_at || d.created || d.createdAt)
                          : "N/A"}
                      </div>
                      <div>
                        ID: <span className="font-mono">{d.id ?? "—"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="flex justify-end gap-2">
        <button className="btn" onClick={() => setPage(Math.max(1, page - 1))}>
          Prev
        </button>
        <button className="btn" onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
      {/* removed duplicate table view; single unified list above */}
    </div>
  );
}
