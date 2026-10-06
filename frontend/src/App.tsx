import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Braces,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  FileSearch,
  FileJson,
  FlaskConical,
  Layers3,
  LoaderCircle,
  LogOut,
  Play,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  getCurrentAdmin,
  getEvaluationSummary,
  getExportPage,
  getHealth,
  getResearchSummary,
  getRefreshStatus,
  getUserRecommendations,
  loginAdmin,
  logoutAdmin,
  startRefresh,
} from "./apiClient";
import type {
  AuthUser,
  DataMode,
  EvaluationResponse,
  ExportResponse,
  HealthResponse,
  RefreshJob,
  ResearchSummaryResponse,
  UserResponse,
} from "./types";

type Page = "overview" | "data-quality" | "model-card" | "error-analysis" | "user-search" | "export-review" | "evaluation" | "refresh" | "raw-response";
type RawKind = "health" | "user" | "export" | "evaluation" | "refresh";

const pages: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "data-quality", label: "Data Quality", icon: Database },
  { id: "model-card", label: "Model Card", icon: BrainCircuit },
  { id: "user-search", label: "User Search", icon: Search },
  { id: "export-review", label: "Export Review", icon: Database },
  { id: "evaluation", label: "Evaluation", icon: BarChart3 },
  { id: "error-analysis", label: "Error Analysis", icon: FileSearch },
  { id: "refresh", label: "Refresh", icon: RefreshCw },
  { id: "raw-response", label: "Raw Response", icon: Braces },
];

const navigationGroups: { label: string; pages: Page[] }[] = [
  { label: "Research workspace", pages: ["overview", "data-quality", "model-card", "evaluation", "error-analysis"] },
  { label: "Inference & export", pages: ["user-search", "export-review"] },
  { label: "Operations", pages: ["refresh", "raw-response"] },
];

const formatNumber = new Intl.NumberFormat("en-US");
const formatDate = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      }).format(new Date(value))
    : "Not available";

function routeToPage(): Page {
  const route = window.location.pathname.replace(/^\//, "") || "overview";
  return pages.some((page) => page.id === route) ? (route as Page) : "overview";
}

function percent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)}%` : "N/A";
}

function scorePercent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "N/A";
}

function learningStatusLabel(value: string) {
  if (value === "Completed") return "Selesai";
  if (value === "On Going") return "Sedang berjalan";
  if (value === "Enroll") return "Terdaftar";
  if (value === "Unenroll") return "Dibatalkan";
  return value || "Tidak tersedia";
}

function usePageRoute() {
  const [page, setPage] = useState<Page>(routeToPage);

  useEffect(() => {
    const handlePop = () => setPage(routeToPage());
    window.addEventListener("popstate", handlePop);
    return () => window.removeEventListener("popstate", handlePop);
  }, []);

  const navigate = (nextPage: Page) => {
    setPage(nextPage);
    window.history.pushState(null, "", `/${nextPage}`);
  };

  return { page, navigate };
}

function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onLogin(await loginAdmin(username, password));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-screen">
      <form className="login-panel" onSubmit={submit}>
        <span className="brand-icon login-icon"><ShieldCheck size={21} /></span>
        <div>
          <p className="eyebrow">Admin access</p>
          <h1>CRE ML Console</h1>
        </div>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
        <button className="primary-button" type="submit" disabled={loading || !username || !password}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <ShieldCheck size={17} />} Login
        </button>
      </form>
    </main>
  );
}

function Sidebar({
  activePage,
  onNavigate,
  onLogout,
}: {
  activePage: Page;
  onNavigate: (page: Page) => void;
  onLogout: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand-mark" aria-label="CRE ML Console">
        <span className="brand-icon"><Sparkles size={18} /></span>
        <span className="brand-copy"><strong>CRE</strong><small>ML Console</small></span>
      </div>
      <nav className="sidebar-nav" aria-label="Main navigation">
        {navigationGroups.map((group) => (
          <div className="nav-group" key={group.label}>
            <p>{group.label}</p>
            {group.pages.map((pageId) => {
              const page = pages.find((item) => item.id === pageId)!;
              const Icon = page.icon;
              return (
                <button
                  key={page.id}
                  className={`nav-item ${activePage === page.id ? "active" : ""}`}
                  onClick={() => onNavigate(page.id)}
                  type="button"
                >
                  <Icon size={18} /><span>{page.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="environment-dot" /> Admin session
        <span className="version-label">Console v0.2.0</span>
        <button className="logout-button" onClick={onLogout} type="button"><LogOut size={14} /> Logout</button>
      </div>
    </aside>
  );
}

function Topbar({
  page,
  mode,
  onModeChange,
}: {
  page: Page;
  mode: DataMode;
  onModeChange: (mode: DataMode) => void;
}) {
  const current = pages.find((item) => item.id === page);
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Research & model monitoring</p>
        <h1>{current?.label ?? "Overview"}</h1>
      </div>
      <div className="topbar-actions">
        <div className="mode-control" aria-label="Data mode">
          <button className={mode === "test" ? "selected" : ""} onClick={() => onModeChange("test")} type="button">
            <FlaskConical size={15} /> Test
          </button>
          <button className={mode === "normal" ? "selected" : ""} onClick={() => onModeChange("normal")} type="button">
            <Layers3 size={15} /> Normal
          </button>
        </div>
        <a className="icon-button" href="http://127.0.0.1:8001/docs" title="Open API documentation" aria-label="Open API documentation"><ExternalLink size={18} /></a>
      </div>
    </header>
  );
}

function DataModeNotice({ mode }: { mode: DataMode }) {
  const isFixture = mode === "test";
  return (
    <div className={`data-mode-notice ${isFixture ? "fixture" : "production"}`} role="status">
      <span className="mode-notice-icon">{isFixture ? <FlaskConical size={17} /> : <Layers3 size={17} />}</span>
      <div>
        <strong>{isFixture ? "Test mode — fixture export" : "Normal mode — production export"}</strong>
        <span>{isFixture ? "Use this mode for safe interface and API-contract checks; it is not the primary experiment output." : "Displaying the generated recommendation export for the active model artifact."}</span>
      </div>
    </div>
  );
}

function OverviewPage({
  health,
  evaluation,
  refreshJob,
  serviceError,
  mode,
}: {
  health: HealthResponse | null;
  evaluation: EvaluationResponse | null;
  refreshJob: RefreshJob | null;
  serviceError: string;
  mode: DataMode;
}) {
  return (
    <section className="overview-section page-section">
      <div className="section-heading">
        <div><h2>Service overview</h2><p>Runtime, model, export, and evaluation status</p></div>
        <span className="refresh-stamp"><Clock3 size={14} /> Checked just now</span>
      </div>
      <div className="status-grid">
        <article className="status-tile primary-status">
          <span className="tile-icon green"><Server size={19} /></span>
          <div><span className="tile-label">API status</span><strong>{serviceError ? "Unavailable" : health?.status === "ok" ? "Operational" : "Checking"}</strong></div>
          <span className={`status-badge ${serviceError ? "status-error" : ""}`}><span /> {serviceError ? "Disconnected" : "Healthy"}</span>
        </article>
        <article className="status-tile">
          <span className="tile-icon amber"><Sparkles size={19} /></span>
          <div><span className="tile-label">Model version</span><strong>{health?.model_version ?? "Loading..."}</strong></div>
          <span className="tile-note">Latest</span>
        </article>
        <article className="status-tile">
          <span className="tile-icon blue"><Database size={19} /></span>
          <div><span className="tile-label">Recommendations</span><strong>{health ? formatNumber.format(health.recommendation_count) : "..."}</strong></div>
          <span className="tile-note">Export rows, not test samples</span>
        </article>
        <article className="status-tile">
          <span className="tile-icon violet"><Check size={19} /></span>
          <div><span className="tile-label">Artifact check</span><strong>{health?.artifact_status ?? "Pending"}</strong></div>
          <span className="tile-note">Version & catalog consistency</span>
        </article>
      </div>
      <div className="metadata-strip">
        <span>Last generated</span><strong>{formatDate(health?.generated_at)}</strong><i />
        <span>Data source</span><strong>{mode === "test" ? "Fixture export" : "Production export"}</strong><i />
        <span>Primary ranking</span><strong>{evaluation?.primary_ranking ?? "Loading..."}</strong><i />
        <span>Evaluation samples</span><strong>{evaluation?.evaluation_samples ?? "..."}</strong><i />
        <span>Export type</span><strong>{health?.export_mode === "demonstration_subset" ? "Demonstration Subset" : "Full Batch Export"}</strong>
        <span>Active export users</span><strong>{health?.active_export_users ?? "..."}</strong>
        <span>Active export Top-K</span><strong>{health?.active_export_top_k ?? "..."}</strong>
        <span>Refresh job</span><strong>{refreshJob?.status ?? "Idle"}</strong>
      </div>
      <div className="metric-grid">
        {(evaluation?.overall_metrics ?? []).slice(0, 5).map((metric) => (
          <article className="metric-card" key={`${metric.label}-${metric.context}`}>
            <span>{metric.label}</span>
            <strong>{percent(metric.value)}</strong>
            <small>{metric.context}</small>
          </article>
        ))}
      </div>
      <div className="overview-note">
        <BrainCircuit size={18} />
        <p><strong>Research scope.</strong> This console exposes model artifacts, ranking evaluation, active recommendation-export inspection, and export monitoring. It is designed for reproducible ML analysis rather than end-user course delivery.</p>
      </div>
    </section>
  );
}

function UserSearchPage({
  mode,
  userId,
  setUserId,
  userResult,
  loading,
  error,
  onSearch,
}: {
  mode: DataMode;
  userId: string;
  setUserId: (value: string) => void;
  userResult: UserResponse | null;
  loading: boolean;
  error: string;
  onSearch: (value: string) => void;
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (userId.trim()) onSearch(userId.trim());
  };

  return (
    <section className="panel page-panel">
      <div className="panel-header">
        <div><span className="panel-icon"><Search size={18} /></span><div><h2>Rekomendasi course pegawai</h2><p>Masukkan satu ID untuk melihat profil, riwayat, perhatian model, dan Top-10 rekomendasi</p></div></div>
        <span className="mode-tag">{mode} mode</span>
      </div>
      <form className="search-form" onSubmit={submit}>
        <label htmlFor="user-id">Employee / User ID</label>
        <div className="input-row">
          <div className="input-wrap"><Search size={17} /><input id="user-id" type="text" value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Contoh: 002156217" /></div>
          <button className="primary-button" type="submit" disabled={loading || !userId.trim()}>
            {loading ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />} Tampilkan
          </button>
        </div>
        <p className="field-hint">ID boleh dimasukkan dengan atau tanpa nol di depan. Sistem akan mencari ID lengkap yang tersimpan pada data.</p>
      </form>
      {error ? (
        <div className="error-state"><CircleAlert size={20} /><div><strong>Rekomendasi tidak tersedia</strong><span>{error}</span></div></div>
      ) : (
        <div className="result-block">
          <div className="result-summary">
            <div><span>Hasil untuk ID</span><strong>{userResult?.canonical_user_id ?? userResult?.user_id ?? "..."}</strong>{userResult?.match_type === "normalized_unique_match" && <small>ID lengkap yang ditemukan: {userResult.canonical_user_id}</small>}</div>
            <span>{userResult?.recommendations.length ?? 0} rekomendasi</span>
          </div>

          {userResult?.profile && (
            <div className="employee-profile-grid">
              <article><span>Nama pegawai</span><strong>{userResult.profile.employee_name}</strong></article>
              <article><span>User ID</span><strong>{userResult.profile.user_id}</strong></article>
              <article><span>Jumlah riwayat</span><strong>{userResult.profile.history_count} course</strong></article>
              <article><span>Sumber data</span><strong>{userResult.profile.source_system}</strong></article>
            </div>
          )}

          {userResult?.learning_progress && (
            <div className="user-result-section">
              <div className="section-heading compact-heading">
                <div>
                  <h3>Progres belajar</h3>
                  <p>Ringkasan ini hanya informasi pendukung dan tidak mengubah urutan rekomendasi.</p>
                </div>
                <span>{userResult.learning_progress.status_available ? "Data tersedia" : "Data terbatas"}</span>
              </div>
              <div className="learning-progress-grid">
                <article>
                  <span>Tingkat penyelesaian</span>
                  <strong>{userResult.learning_progress.completion_rate_percent !== null ? `${userResult.learning_progress.completion_rate_percent.toFixed(2)}%` : "Belum tersedia"}</strong>
                  <small>Dihitung dari course aktif yang memiliki status.</small>
                </article>
                <article>
                  <span>Course selesai</span>
                  <strong>{userResult.learning_progress.status_available ? userResult.learning_progress.completed_count : "—"}</strong>
                  <small>Dari {userResult.learning_progress.tracked_course_count} course yang tercatat statusnya.</small>
                </article>
                <article>
                  <span>Sedang dipelajari</span>
                  <strong>{userResult.learning_progress.status_available ? userResult.learning_progress.ongoing_count + userResult.learning_progress.enrolled_count : "—"}</strong>
                  <small>{userResult.learning_progress.ongoing_count} berjalan · {userResult.learning_progress.enrolled_count} terdaftar</small>
                </article>
                <article>
                  <span>Nilai rata-rata</span>
                  <strong>{userResult.learning_progress.average_score !== null ? userResult.learning_progress.average_score.toFixed(2) : "Belum tersedia"}</strong>
                  <small>Berdasarkan {userResult.learning_progress.score_count} data nilai.</small>
                </article>
                <article>
                  <span>Sertifikat</span>
                  <strong>{userResult.learning_progress.certificate_count}</strong>
                  <small>Jumlah course unik yang tercatat bersertifikat.</small>
                </article>
              </div>
              <div className="progress-note"><CircleAlert size={16} /><span>{userResult.learning_progress.note}</span></div>

              {(userResult.progress_items?.length ?? 0) > 0 && (
                <div className="table-scroll progress-detail-table">
                  <table className="wide-table">
                    <thead><tr><th>Course</th><th>Status belajar</th><th>Nilai</th><th>Sertifikat</th></tr></thead>
                    <tbody>
                      {userResult.progress_items.map((item) => (
                        <tr key={`${item.course_id}-${item.learning_status}`}>
                          <td><strong className="course-title">{item.course_name}</strong><small>{item.course_id}</small></td>
                          <td><span className={`learning-status status-${item.learning_status.toLowerCase().replaceAll(" ", "-")}`}>{learningStatusLabel(item.learning_status)}</span></td>
                          <td>{item.score !== null ? item.score.toFixed(2) : "Belum tersedia"}</td>
                          <td>{item.has_certificate ? "Bersertifikat" : "Tidak tercatat"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {(userResult?.history.length ?? 0) > 0 && (
            <div className="user-result-section">
              <div className="section-heading compact-heading"><div><h3>Riwayat course sebelum rekomendasi</h3><p>Course diurutkan dari yang paling lama sampai yang terbaru.</p></div><span>{userResult?.history.length} course</span></div>
              <div className="table-scroll">
                <table className="wide-table history-table">
                  <thead><tr><th>No.</th><th>Waktu</th><th>Course</th><th>Kompetensi</th><th>Level</th><th>Sertifikat</th></tr></thead>
                  <tbody>
                    {userResult?.history.map((item, index) => (
                      <tr key={`${item.course_id}-${index}`}>
                        <td>{index + 1}</td>
                        <td>{item.event_timestamp ? new Date(item.event_timestamp).toLocaleString("id-ID") : "Tidak tersedia"}</td>
                        <td><strong className="course-title">{item.course_name}</strong><small>{item.course_id}</small></td>
                        <td>{item.competency}</td>
                        <td>{item.level}</td>
                        <td>{item.certificate_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {(userResult?.attention.length ?? 0) > 0 && (
            <div className="user-result-section">
              <div className="section-heading compact-heading"><div><h3>Course yang paling diperhatikan model</h3><p>Bobot lebih besar berarti course tersebut lebih diperhatikan saat model membuat prediksi.</p></div></div>
              <div className="attention-list">
                {userResult?.attention.slice(0, 5).map((item) => (
                  <article key={`${item.input_position}-${item.course_id}`}>
                    <div><strong>{item.course_name}</strong><small>Posisi input {item.input_position} · Course {item.course_id}</small></div>
                    <span>{(item.attention_weight * 100).toFixed(2)}%</span>
                  </article>
                ))}
              </div>
            </div>
          )}

          <div className="user-result-section">
            <div className="section-heading compact-heading"><div><h3>Rekomendasi course untuk Anda</h3><p>Top-10 course dari model. Course yang sudah pernah diambil tidak dimasukkan kembali.</p></div><span>{userResult?.inference_source === "live_model" ? "Model langsung" : "Data hasil model"}</span></div>
          <div className="table-scroll">
            <table className="wide-table">
              <thead><tr><th>Peringkat</th><th>Course</th><th>Skor Softmax</th><th>Alasan rekomendasi</th><th>Kompetensi</th><th>Level</th><th>Sertifikat</th></tr></thead>
              <tbody>
                {userResult?.recommendations.map((item) => (
                  <tr key={`${item.rank}-${item.canonical_course_id}`}>
                    <td><span className={`rank rank-${item.rank}`}>{item.rank}</span></td>
                    <td><strong className="course-title">{item.course_title ?? "Nama course tidak tersedia"}</strong><small>{item.canonical_course_id}</small></td>
                    <td><div className="score-cell"><span className="score-track"><i style={{ width: `${Math.min((item.softmax_score ?? item.score) * 100, 100)}%` }} /></span><strong>{percent(item.softmax_score_percent)}</strong></div></td>
                    <td className="recommendation-reason">{item.recommendation_reason ?? "Alasan belum tersedia."}</td>
                    <td>{item.competency ?? "Tidak tersedia"}</td>
                    <td>{item.level ?? "Tidak tersedia"}</td>
                    <td>{item.certificate_status === "certified" ? "Bersertifikat" : item.certificate_status === "not_certified" ? "Tidak Bersertifikat" : item.certificate_status ?? "Tidak tersedia"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>

          {userResult?.actual_course && (
            <div className={`actual-course-check ${userResult.actual_course.rank === 1 ? "is-success" : ""}`}>
              <div><span>Course aktual berikutnya</span><strong>{userResult.actual_course.course_name}</strong><small>{userResult.actual_course.course_id}</small></div>
              <div><span>Peringkat pada rekomendasi</span><strong>{userResult.actual_course.rank ?? "Tidak masuk Top-10"}</strong><small>{userResult.actual_course.status}</small></div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ExportReviewPage({
  mode,
  health,
  exportResult,
  loading,
  error,
  page,
  limit,
  setLimit,
  cursorStack,
  loadExport,
}: {
  mode: DataMode;
  health: HealthResponse | null;
  exportResult: ExportResponse | null;
  loading: boolean;
  error: string;
  page: number;
  limit: number;
  setLimit: (value: number) => void;
  cursorStack: (string | null)[];
  loadExport: (page: number, cursor: string | null, limit?: number, mode?: DataMode) => void;
}) {
  return (
    <section className="panel page-panel">
      <div className="panel-header">
        <div><span className="panel-icon"><Database size={18} /></span><div><h2>Export review</h2><p>Browse the current recommendation batch</p></div></div>
        <label className="limit-select">Rows<select value={limit} onChange={(event) => { const next = Number(event.target.value); setLimit(next); loadExport(0, null, next, mode); }}><option value={6}>6</option><option value={10}>10</option><option value={20}>20</option></select><ChevronDown size={14} /></label>
      </div>
      <div className="overview-note export-summary">
        <Database size={18} />
        <p><strong>Active export: {health?.export_mode === "demonstration_subset" ? "Demonstration Subset" : "Full Batch Export"}.</strong> Users: {health?.active_export_users ?? "..."} · Top-K: {health?.active_export_top_k ?? "..."} · Rows: {health ? formatNumber.format(health.recommendation_count) : "..."} · Model: {health?.model_version ?? "..."} · Primary ranking: {health?.primary_ranking ?? "Softmax Ranking"}. Export Review displays only the currently active recommendation export; a demonstration subset does not represent the full user population.</p>
      </div>
      <div className={`export-table-wrap ${loading ? "is-loading" : ""}`}>
        {error && <div className="export-error"><CircleAlert size={19} /><span>{error}</span></div>}
        <table className="wide-table">
          <thead><tr><th>User</th><th>Rank</th><th>Course</th><th>Score</th><th>Competency</th><th>Level</th><th>Reason</th></tr></thead>
          <tbody>
            {exportResult?.recommendations.map((item) => (
              <tr key={`${item.user_id}-${item.rank}-${item.canonical_course_id}`}>
                <td><strong className="course-id">{item.user_id}</strong></td>
                <td><span className={`rank rank-${item.rank}`}>{item.rank}</span></td>
                <td><strong className="course-title">{item.course_title ?? "Untitled course"}</strong><small>{item.canonical_course_id}</small></td>
                <td>{scorePercent(item.score)}</td>
                <td>{item.competency ?? "N/A"}</td>
                <td>{item.level ?? "N/A"}</td>
                <td><span className="reason-code">{item.fallback_reason ?? item.reason_code ?? "model"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>Page {page + 1}</span>
        <div>
          <button className="icon-button small" aria-label="Previous page" title="Previous page" disabled={page === 0 || loading} onClick={() => loadExport(page - 1, cursorStack[page - 1] ?? null)}><ArrowLeft size={16} /></button>
          <button className="icon-button small" aria-label="Next page" title="Next page" disabled={!exportResult?.page.has_more || loading} onClick={() => loadExport(page + 1, exportResult?.page.next_cursor ?? null)}><ArrowRight size={16} /></button>
        </div>
      </div>
    </section>
  );
}

function EvaluationPage({ evaluation, error }: { evaluation: EvaluationResponse | null; error: string }) {
  const tables = evaluation?.metric_tables ?? {};
  return (
    <section className="page-stack">
      {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
      <div className="section-heading evaluation-heading">
        <div><h2>Evaluation summary</h2><p>Artifact-backed ranking results for the current model version</p></div>
      </div>
      <div className="metric-grid">
        {(evaluation?.overall_metrics ?? []).map((metric) => (
          <article className="metric-card" key={`${metric.label}-${metric.context}`}>
            <span>{metric.label}</span>
            <strong>{percent(metric.value)}</strong>
            <small>{metric.context}</small>
          </article>
        ))}
      </div>
      <MetricChart metrics={evaluation?.overall_metrics ?? []} />
      <MetricTable title="Top-K performance" rows={tables.topk_performance ?? []} />
      <MetricTable title="Alternative: Similarity Ranking" rows={tables.similarity_metrics ?? []} />
      <MetricTable title="Popularity baseline comparison" rows={tables.popularity_baseline ?? []} />
      <MetricTable title="Coverage" rows={tables.coverage ?? []} />
      <MetricTable title="Strict robustness check (strict_train_history)" rows={tables.strict_comparison ?? []} />
    </section>
  );
}

function MetricChart({ metrics }: { metrics: EvaluationResponse["overall_metrics"] }) {
  const visibleMetrics = metrics.filter((metric) => typeof metric.value === "number" && Number.isFinite(metric.value)).slice(0, 6);
  return (
    <section className="panel evaluation-chart">
      <div className="panel-header">
        <div><span className="panel-icon"><BarChart3 size={18} /></span><div><h2>Metric snapshot</h2><p>Quick visual comparison of the reported evaluation metrics</p></div></div>
      </div>
      {visibleMetrics.length ? (
        <div className="metric-bars">
          {visibleMetrics.map((metric) => {
            const value = Math.max(0, Math.min(metric.value ?? 0, 100));
            return <div className="metric-bar-row" key={`${metric.label}-${metric.context}`}>
              <div><span>{metric.label}</span><small>{metric.context}</small></div>
              <span className="metric-bar-track"><i style={{ width: `${value}%` }} /></span>
              <strong>{percent(metric.value)}</strong>
            </div>;
          })}
        </div>
      ) : <div className="empty-metric-state">Evaluation metrics will appear after the artifact tables are available.</div>}
    </section>
  );
}

function MetricTable({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  const columns = rows[0] ? Object.keys(rows[0]).slice(0, 8) : [];
  return (
    <section className="panel page-panel">
      <div className="panel-header"><div><span className="panel-icon"><BarChart3 size={18} /></span><div><h2>{title}</h2><p>{rows.length} rows loaded from artifacts</p></div></div></div>
      <div className="table-scroll">
        <table className="wide-table">
          <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? "N/A")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function readableField(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayValue(value: unknown) {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? formatNumber.format(value) : value.toFixed(2);
  return value === null || value === undefined || value === "" ? "Not available" : String(value);
}

function DataQualityPage({ research, error }: { research: ResearchSummaryResponse | null; error: string }) {
  const quality = research?.data_quality ?? {};
  const splitRows = quality.data_split ?? [];
  const noiseRows = quality.noise_cleaning ?? [];
  const interaction = quality.interaction_per_user?.[0] ?? {};
  const popularity = quality.course_popularity?.[0] ?? {};

  return (
    <section className="page-stack">
      {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
      <div className="section-heading evaluation-heading"><div><h2>Data quality & preprocessing</h2><p>Artifact-backed audit of the cleaned dataset and temporal evaluation split</p></div></div>
      <section className="panel data-audit-panel">
        <div className="panel-header"><div><span className="panel-icon"><Database size={18} /></span><div><h2>Temporal split audit</h2><p>Rows retained for training, validation history, and isolated test targets</p></div></div></div>
        <div className="split-cards">
          {splitRows.map((row) => <article key={String(row.split)}><span>{displayValue(row.split)}</span><strong>{displayValue(row.rows)}</strong><small>{displayValue(row.unique_users)} users · {displayValue(row.unique_courses)} courses</small></article>)}
        </div>
      </section>
      <div className="research-grid">
        <ArtifactStatPanel title="Noise cleaning" icon={<FileSearch size={18} />} rows={noiseRows} />
        <ArtifactStatPanel title="Interaction history" icon={<Activity size={18} />} rows={Object.entries(interaction).map(([metric, value]) => ({ metric, value }))} />
        <ArtifactStatPanel title="Course popularity" icon={<BarChart3 size={18} />} rows={Object.entries(popularity).map(([metric, value]) => ({ metric, value }))} />
      </div>
    </section>
  );
}

function ArtifactStatPanel({ title, icon, rows }: { title: string; icon: ReactNode; rows: Record<string, unknown>[] }) {
  return <section className="panel artifact-stat-panel">
    <div className="panel-header"><div><span className="panel-icon">{icon}</span><div><h2>{title}</h2><p>Summary generated during notebook export</p></div></div></div>
    <dl>{rows.slice(0, 8).map((row, index) => {
      const label = row.metric ?? row["Metric"] ?? `Statistic ${index + 1}`;
      const value = row.value ?? row["Value"];
      return <div key={`${String(label)}-${index}`}><dt>{displayValue(label)}</dt><dd>{displayValue(value)}</dd></div>;
    })}</dl>
  </section>;
}

function ModelCardPage({ research, error }: { research: ResearchSummaryResponse | null; error: string }) {
  const card = research?.model_card ?? {};
  const sections = [
    { title: "Final model", fields: ["model_version", "configuration", "architecture", "primary_ranking", "alternative_ranking"] },
    { title: "Input & vocabulary", fields: ["max_sequence_length", "seen_course_masking", "num_courses", "num_competencies", "num_levels"] },
    { title: "Representation", fields: ["course_embedding_dim", "competency_embedding_dim", "level_embedding_dim", "latent_dim"] },
    { title: "Reproducibility", fields: ["random_seed", "min_course_count_train", "repeated_run_seeds", "evaluation_protocol"] },
  ];
  return <section className="page-stack">
    {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
    <div className="section-heading evaluation-heading"><div><h2>Model card</h2><p>Architecture, ranking policy, and reproducibility parameters saved with the model artifact</p></div></div>
    <section className="model-hero panel"><span className="panel-icon"><BrainCircuit size={22} /></span><div><span>Active model</span><h2>{displayValue(card.architecture)}</h2><p>Softmax Ranking is primary; Cosine Similarity Ranking is an alternative score. The model uses at most ten latest interactions as its input sequence, while all available pre-prediction course history excludes already completed courses from recommendation candidates.</p></div><span className="model-version">{research?.model_version ?? "Loading..."}</span></section>
    <div className="model-card-grid">{sections.map((section) => <section className="panel model-detail-panel" key={section.title}><div className="panel-header"><div><span className="panel-icon"><Layers3 size={18} /></span><div><h2>{section.title}</h2><p>Saved experiment configuration</p></div></div></div><dl>{section.fields.map((field) => <div key={field}><dt>{readableField(field)}</dt><dd>{displayValue(card[field])}</dd></div>)}</dl></section>)}</div>
  </section>;
}

function ErrorAnalysisPage({ research, error }: { research: ResearchSummaryResponse | null; error: string }) {
  const summary = research?.error_analysis.summary ?? [];
  const errorTypes = research?.error_analysis.error_types ?? [];
  return <section className="page-stack">
    {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
    <div className="section-heading evaluation-heading"><div><h2>Error analysis</h2><p>Top-10 outcomes, ground-truth ranks, history length, and target frequency from isolated test samples</p></div></div>
    <div className="error-summary-grid">{summary.map((row) => <article className="panel error-summary-card" key={String(row.ranking_method)}><span>{displayValue(row.ranking_method)}</span><strong>{displayValue(row["Hit@10_percent"])}%</strong><small>Hit@10 · {displayValue(row.total_samples)} test samples</small><div><span>Miss@10</span><b>{displayValue(row["Miss@10_percent"])}%</b></div><p>Average history: hit {displayValue(row.avg_history_length_hit)} · miss {displayValue(row.avg_history_length_miss)}</p></article>)}</div>
    <section className="panel error-distribution"><div className="panel-header"><div><span className="panel-icon"><FileSearch size={18} /></span><div><h2>Rank outcome distribution</h2><p>Where the ground-truth course appears in the Top-10 list</p></div></div></div><div className="error-bars">{errorTypes.map((row) => { const value = Number(row.percentage ?? 0); return <div className="error-bar-row" key={`${row.ranking_method}-${row.error_type}`}><span>{displayValue(row.ranking_method)}</span><div><strong>{displayValue(row.error_type)}</strong><i><b style={{ width: `${Math.max(0, Math.min(value, 100))}%` }} /></i></div><em>{displayValue(row.percentage)}%</em></div>; })}</div></section>
    <MetricTable title="Detailed error summary" rows={summary} />
  </section>;
}

function RefreshPage({
  refreshJob,
  setRefreshJob,
}: {
  refreshJob: RefreshJob | null;
  setRefreshJob: (job: RefreshJob | null) => void;
}) {
  const [topK, setTopK] = useState(20);
  const [maxUsers, setMaxUsers] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!refreshJob || !["running", "queued"].includes(refreshJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        setRefreshJob(await getRefreshStatus(refreshJob.job_id));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load refresh status.");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [refreshJob, setRefreshJob]);

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      setRefreshJob(await startRefresh(topK, maxUsers.trim() ? Number(maxUsers) : null));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not start refresh.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel page-panel">
      <div className="panel-header">
        <div><span className="panel-icon"><RefreshCw size={18} /></span><div><h2>Recommendation export refresh</h2><p>Regenerates batch recommendations using the active trained model. This process does not retrain the model.</p></div></div>
        <span className={`mode-tag status-${refreshJob?.status ?? "idle"}`}>{refreshJob?.status ?? "idle"}</span>
      </div>
      <div className="refresh-controls">
        <label>Top-K<input type="number" min={1} max={100} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></label>
        <label>Max users<input value={maxUsers} onChange={(event) => setMaxUsers(event.target.value)} placeholder="Optional" /></label>
        <button className="primary-button" onClick={run} disabled={loading || refreshJob?.status === "running"} type="button">
          {loading ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />} Regenerate Recommendations
        </button>
      </div>
      {error && <div className="compact-error"><CircleAlert size={17} /> {error}</div>}
      <pre className="log-panel"><code>{refreshJob?.logs.join("\n") || "No refresh job has been started."}</code></pre>
      {refreshJob?.result && <pre><code>{JSON.stringify(refreshJob.result, null, 2)}</code></pre>}
    </section>
  );
}

function RawResponsePage({
  health,
  userResult,
  exportResult,
  evaluation,
  refreshJob,
}: {
  health: HealthResponse | null;
  userResult: UserResponse | null;
  exportResult: ExportResponse | null;
  evaluation: EvaluationResponse | null;
  refreshJob: RefreshJob | null;
}) {
  const [kind, setKind] = useState<RawKind>("user");
  const payload = { health, user: userResult, export: exportResult, evaluation, refresh: refreshJob }[kind];
  const json = useMemo(() => JSON.stringify(payload, null, 2), [payload]);

  return (
    <section className="response-panel raw-page">
      <div className="response-toggle static-toggle">
        <span><FileJson size={18} /><span><strong>Raw API response</strong><small>Inspect the exact response payload</small></span></span>
        <span className="response-actions">
          <span className="response-tabs">
            {(["health", "user", "export", "evaluation", "refresh"] as RawKind[]).map((item) => (
              <button key={item} className={kind === item ? "active" : ""} onClick={() => setKind(item)} type="button">{item}</button>
            ))}
          </span>
          <button className="icon-button small" type="button" onClick={() => void navigator.clipboard.writeText(json)} title="Copy JSON" aria-label="Copy JSON"><Copy size={15} /></button>
        </span>
      </div>
      <pre><code>{json}</code></pre>
    </section>
  );
}

function App() {
  const { page, navigate } = usePageRoute();
  const [admin, setAdmin] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [mode, setMode] = useState<DataMode>("normal");
  const [userId, setUserId] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [userResult, setUserResult] = useState<UserResponse | null>(null);
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [research, setResearch] = useState<ResearchSummaryResponse | null>(null);
  const [refreshJob, setRefreshJob] = useState<RefreshJob | null>(null);
  const [loadingUser, setLoadingUser] = useState(false);
  const [loadingExport, setLoadingExport] = useState(false);
  const [userError, setUserError] = useState("");
  const [serviceError, setServiceError] = useState("");
  const [exportError, setExportError] = useState("");
  const [evaluationError, setEvaluationError] = useState("");
  const [researchError, setResearchError] = useState("");
  const [exportPage, setExportPage] = useState(0);
  const [limit, setLimit] = useState(6);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);

  useEffect(() => {
    getCurrentAdmin()
      .then(setAdmin)
      .catch(() => setAdmin({ authenticated: false, username: null }))
      .finally(() => setAuthChecked(true));
  }, []);

  const runUserLookup = async (lookupId: string, selectedMode: DataMode) => {
    setLoadingUser(true);
    setUserError("");
    try {
      setUserResult(await getUserRecommendations(lookupId.trim(), selectedMode));
    } catch (lookupError) {
      setUserResult(null);
      setUserError(lookupError instanceof Error ? lookupError.message : "The request could not be completed.");
    } finally {
      setLoadingUser(false);
    }
  };

  const loadExport = async (
    nextPage: number,
    cursor: string | null,
    nextLimit = limit,
    selectedMode = mode,
  ) => {
    setLoadingExport(true);
    setExportError("");
    try {
      const result = await getExportPage(cursor, nextLimit, selectedMode);
      setExportResult(result);
      setExportPage(nextPage);
      setCursorStack((current) => {
        const updated = current.slice(0, nextPage + 1);
        updated[nextPage] = cursor;
        return updated;
      });
    } catch (requestError) {
      setExportError(requestError instanceof Error ? requestError.message : "Could not load the export.");
    } finally {
      setLoadingExport(false);
    }
  };

  const loadDashboardData = (selectedMode: DataMode) => {
    getHealth().then(setHealth).catch((healthError) => {
      setServiceError(healthError instanceof Error ? healthError.message : "The ML service is unavailable.");
    });
    getEvaluationSummary().then(setEvaluation).catch((requestError) => {
      setEvaluationError(requestError instanceof Error ? requestError.message : "Could not load evaluation.");
    });
    getResearchSummary().then(setResearch).catch((requestError) => {
      setResearchError(requestError instanceof Error ? requestError.message : "Could not load research artifacts.");
    });
    if (userId.trim()) {
      void runUserLookup(userId, selectedMode);
    } else {
      setUserResult(null);
      setUserError("");
    }
    void loadExport(0, null, limit, selectedMode);
  };

  useEffect(() => {
    if (admin?.authenticated) loadDashboardData(mode);
  }, [admin?.authenticated]);

  const changeMode = (nextMode: DataMode) => {
    setMode(nextMode);
    setExportPage(0);
    setCursorStack([null]);
    loadDashboardData(nextMode);
  };

  const handleLogout = async () => {
    await logoutAdmin().catch(() => undefined);
    setAdmin({ authenticated: false, username: null });
  };

  if (!authChecked) {
    return <main className="login-screen"><LoaderCircle className="spin" size={28} /></main>;
  }

  if (!admin?.authenticated) {
    return <LoginPage onLogin={(user) => setAdmin(user)} />;
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={page} onNavigate={navigate} onLogout={handleLogout} />
      <main className="main-content">
        <Topbar page={page} mode={mode} onModeChange={changeMode} />
        <DataModeNotice mode={mode} />
        {page === "overview" && <OverviewPage health={health} evaluation={evaluation} refreshJob={refreshJob} serviceError={serviceError} mode={mode} />}
        {page === "data-quality" && <DataQualityPage research={research} error={researchError} />}
        {page === "model-card" && <ModelCardPage research={research} error={researchError} />}
        {page === "user-search" && (
          <UserSearchPage
            mode={mode}
            userId={userId}
            setUserId={setUserId}
            userResult={userResult}
            loading={loadingUser}
            error={userError}
            onSearch={(value) => void runUserLookup(value, mode)}
          />
        )}
        {page === "export-review" && (
          <ExportReviewPage
            mode={mode}
            health={health}
            exportResult={exportResult}
            loading={loadingExport}
            error={exportError}
            page={exportPage}
            limit={limit}
            setLimit={setLimit}
            cursorStack={cursorStack}
            loadExport={(nextPage, cursor, nextLimit, selectedMode) => void loadExport(nextPage, cursor, nextLimit, selectedMode)}
          />
        )}
        {page === "evaluation" && <EvaluationPage evaluation={evaluation} error={evaluationError} />}
        {page === "error-analysis" && <ErrorAnalysisPage research={research} error={researchError} />}
        {page === "refresh" && <RefreshPage refreshJob={refreshJob} setRefreshJob={setRefreshJob} />}
        {page === "raw-response" && (
          <RawResponsePage
            health={health}
            userResult={userResult}
            exportResult={exportResult}
            evaluation={evaluation}
            refreshJob={refreshJob}
          />
        )}
        <footer><span>CRE ML Recommendation Service</span><span><span className={`footer-dot ${serviceError ? "offline" : ""}`} /> {serviceError ? "Backend disconnected" : `Admin: ${admin.username}`}</span></footer>
      </main>
    </div>
  );
}

export default App;
