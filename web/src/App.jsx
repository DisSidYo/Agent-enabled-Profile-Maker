import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  FileText,
  Github,
  Linkedin,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  WandSparkles,
} from "lucide-react";

const CLIENT_HEADER = "proofpoint-web";
const DRAFT_KEY = "proofpoint.drafts.v1";
const FALLBACK_ROLES = [
  { id: "Software Development", short: "Development" },
  { id: "AI / ML", short: "AI / ML" },
  { id: "Data Analytics", short: "Analytics" },
  { id: "Consulting", short: "Consulting" },
];

const emptySelection = () => ({
  resume: new Set(),
  github: new Set(),
  website: new Set(),
  linkedin: new Set(),
  post: false,
});

function serializeSelection(selection) {
  return {
    resume: [...selection.resume],
    github: [...selection.github],
    website: [...selection.website],
    linkedin: [...selection.linkedin],
    post: selection.post,
  };
}

function deserializeSelection(raw) {
  return {
    resume: new Set(raw?.resume || []),
    github: new Set(raw?.github || []),
    website: new Set(raw?.website || []),
    linkedin: new Set(raw?.linkedin || []),
    post: Boolean(raw?.post),
  };
}

function formatDetail(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") return item.msg || item.message || "";
      return "";
    }).filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || `Request failed (${status}).`;
  }
  return `Request failed (${status}).`;
}

async function api(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Proofpoint-Client": CLIENT_HEADER,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (!response.ok) throw new Error(raw.slice(0, 280) || `Request failed (${response.status}).`);
      throw new Error("The server returned a non-JSON response.");
    }
  }
  if (!response.ok) throw new Error(formatDetail(data, response.status));
  return data;
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function App() {
  const saved = useMemo(() => loadDraft(), []);
  const [roleOptions, setRoleOptions] = useState(FALLBACK_ROLES);
  const [publishers, setPublishers] = useState({ overleaf: false, github: false, linkedin: false });
  const [repoPath, setRepoPath] = useState(saved?.repoPath || "");
  const [websiteUrl, setWebsiteUrl] = useState(saved?.websiteUrl || "");
  const [base, setBase] = useState(saved?.base || "ROOT");
  const [head, setHead] = useState(saved?.head || "HEAD");
  const [prompt, setPrompt] = useState(saved?.prompt || "");
  const [roles, setRoles] = useState(saved?.roles || ["Software Development", "AI / ML"]);
  const [repo, setRepo] = useState(saved?.repo || null);
  const [result, setResult] = useState(saved?.result || null);
  const [selection, setSelection] = useState(() => deserializeSelection(saved?.selection));
  const [checklist, setChecklist] = useState(saved?.checklist || []);
  const [approved, setApproved] = useState(Boolean(saved?.approved));
  const [previewHash, setPreviewHash] = useState(saved?.previewHash || "");
  const [approvedContent, setApprovedContent] = useState(saved?.approvedContent || null);
  const [publishLog, setPublishLog] = useState(saved?.publishLog || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(saved?.result ? "Restored saved drafts from this browser." : "");

  const roleShort = useMemo(
    () => Object.fromEntries(roleOptions.map((role) => [role.id, role.short])),
    [roleOptions],
  );

  const selectedCount = useMemo(() => (
    selection.resume.size + selection.github.size + selection.website.size + selection.linkedin.size
    + Number(selection.post)
  ), [selection]);

  useEffect(() => {
    api("/api/roles").then((data) => {
      if (data?.roles?.length) setRoleOptions(data.roles);
    }).catch(() => {});
    api("/api/publishers").then(setPublishers).catch(() => {});
  }, []);

  useEffect(() => {
    const payload = {
      repoPath,
      websiteUrl,
      base,
      head,
      prompt,
      roles,
      repo,
      result,
      selection: serializeSelection(selection),
      checklist,
      approved,
      previewHash,
      approvedContent,
      publishLog,
    };
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
    } catch {
      /* ignore quota */
    }
  }, [repoPath, websiteUrl, base, head, prompt, roles, repo, result, selection, checklist, approved, previewHash, approvedContent, publishLog]);

  function confirmDiscard() {
    if (!result) return true;
    return window.confirm("This will discard the current drafts. Generations cost tokens. Continue?");
  }

  function clearDrafts() {
    if (!confirmDiscard()) return;
    setResult(null);
    setApproved(false);
    setPreviewHash("");
    setApprovedContent(null);
    setSelection(emptySelection());
    setChecklist([]);
    setPublishLog([]);
    setNotice("");
  }

  function buildApproved() {
    return {
      repo: result.repo,
      selected_resume_bullets: result.resume_bullets
        .filter((item) => selection.resume.has(item.id))
        .map(({ role, text }) => ({ role, text })),
      selected_github_bullets: result.resume_bullets
        .filter((item) => selection.github.has(item.id))
        .map(({ role, text }) => ({ role, text })),
      selected_website_bullets: result.resume_bullets
        .filter((item) => selection.website.has(item.id))
        .map(({ role, text }) => ({ role, text })),
      selected_linkedin_bullets: result.resume_bullets
        .filter((item) => selection.linkedin.has(item.id))
        .map(({ role, text }) => ({ role, text })),
      github_summary: selection.github.has("github-summary") ? result.github_summary : "",
      website_copy: selection.website.has("website-copy") ? result.website_copy : "",
      personal_website_url: websiteUrl,
      linkedin_summary: selection.linkedin.has("linkedin-summary") ? result.linkedin_summary : "",
      linkedin_post: selection.post ? result.linkedin_post : "",
    };
  }

  async function connectRepo(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const data = await api("/api/repo", { method: "POST", body: { repo_path: repoPath } });
      setRepo(data);
      setRepoPath(data.path);
      if (!base || base === "HEAD~1") setBase(data.suggested_base || "ROOT");
      setNotice("Repository connected. Nothing has been changed.");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function generate(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setApproved(false);
    setPreviewHash("");
    setApprovedContent(null);
    setBusy(true);
    try {
      const data = await api("/api/generate", {
        method: "POST",
        body: {
          repo_path: repo?.path || repoPath,
          base,
          head,
          prompt,
          roles,
        },
      });
      setResult({
        ...data,
        resume_bullets: data.resume_bullets.map((item, index) => ({
          ...item,
          id: `bullet-${index}`,
        })),
      });
      setSelection(emptySelection());
      setChecklist(data.checklist.map(() => false));
      setNotice("Drafts ready. Review every claim, edit wording, then choose where each one belongs.");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleRole(role) {
    setRoles((current) => current.includes(role)
      ? current.filter((item) => item !== role)
      : [...current, role]);
  }

  function markDirty() {
    setApproved(false);
    setPreviewHash("");
    setApprovedContent(null);
  }

  function toggleTarget(target, id) {
    markDirty();
    setSelection((current) => {
      const next = { ...current, [target]: new Set(current[target]) };
      next[target].has(id) ? next[target].delete(id) : next[target].add(id);
      return next;
    });
  }

  function togglePost() {
    markDirty();
    setSelection((current) => ({ ...current, post: !current.post }));
  }

  function updateBullet(id, text) {
    markDirty();
    setResult((current) => ({
      ...current,
      resume_bullets: current.resume_bullets.map((item) => item.id === id ? { ...item, text } : item),
    }));
  }

  function updateField(field, text) {
    markDirty();
    setResult((current) => ({ ...current, [field]: text }));
  }

  async function approveSelection() {
    setError("");
    setBusy(true);
    try {
      const content = buildApproved();
      const data = await api("/api/approve", { method: "POST", body: content });
      setApprovedContent(data.content);
      setPreviewHash(data.preview_hash);
      setApproved(true);
      setNotice("Approved. Preview hash locked. Publishing will send this exact content.");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  function exportApproved() {
    const payload = approvedContent || buildApproved();
    const blob = new Blob([JSON.stringify({ preview_hash: previewHash, ...payload }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "approved-career-content.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function publish(kind) {
    if (!approvedContent || !previewHash) return;
    setError("");
    setBusy(true);
    try {
      const data = await api(`/api/publish/${kind}`, {
        method: "POST",
        body: { preview_hash: previewHash, content: approvedContent },
      });
      const label = data.url || data.id || data.file || data.status;
      setPublishLog((current) => [...current, `${kind}: ${label}`]);
      setNotice(`Published to ${kind}. ${label}`);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  const bulletItems = result?.resume_bullets || [];
  const canApprove = result && selectedCount > 0 && checklist.length > 0
    && checklist.every(Boolean);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Proofpoint home">
          <span className="brand-mark"><Check size={20} strokeWidth={3} /></span>
          <span>proofpoint<span className="brand-dot">.</span></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <button className="nav-item active"><Sparkles size={17} /> Content studio</button>
        <button className="nav-item" onClick={() => {
          if (!result) {
            setNotice("Generate drafts first, then you can review them here.");
            return;
          }
          document.getElementById("review-title")?.scrollIntoView({ behavior: "smooth" });
        }}><FileText size={17} /> Review drafts</button>
        <div className="sidebar-bottom">
          <div className="privacy-card">
            <div className="privacy-icon"><LockKeyhole size={16} /></div>
            <strong>You’re in control</strong>
            <p>Nothing gets published or changed unless you approve it. Drafts stay in this browser.</p>
          </div>
          <div className="user-row">
            <div className="avatar">S</div>
            <div><strong>Your workspace</strong><span>Personal</span></div>
            <ChevronDown size={16} />
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Content studio</div>
          <div className="topbar-actions">
            <span className="local-pill"><span /> Local workspace</span>
            <button className="icon-button" aria-label="Help"><CircleHelp size={18} /></button>
          </div>
        </header>

        <div className="page-content">
          <section className="hero">
            <div className="eyebrow"><span className="eyebrow-line" /> YOUR WORK, WELL TOLD</div>
            <h1>Turn real work into<br />your next opportunity.</h1>
            <p>Choose a repository, tell us what you’re aiming for, then shape every draft before it goes anywhere.</p>
          </section>

          <form className="source-card" onSubmit={connectRepo}>
            <div className="section-heading">
              <div className="step-number">01</div>
              <div>
                <div className="section-title">Start with your work</div>
                <div className="section-subtitle">Connect a local clone of the GitHub repository you want to showcase.</div>
              </div>
              <div className="source-icon"><Github size={19} /></div>
            </div>
            <label className="field-label" htmlFor="repo-path">LOCAL REPOSITORY FOLDER</label>
            <div className="path-row">
              <input
                id="repo-path"
                value={repoPath}
                onChange={(event) => setRepoPath(event.target.value)}
                placeholder="C:\Users\you\projects\your-repo"
                required
              />
              <button type="submit" className="secondary-button" disabled={busy}>
                {busy && !result ? <LoaderCircle className="spin" size={16} /> : <Github size={16} />}
                {repo ? "Reconnect" : "Connect repository"}
              </button>
            </div>
            {repo && <div className="repo-connected"><CheckCircle2 size={16} /><span><strong>{repo.path}</strong> · {repo.branch} · working tree {repo.working_tree}</span></div>}
            <div className="ref-row">
              <div className="ref-field"><label htmlFor="base-ref">COMPARE FROM</label><input id="base-ref" value={base} onChange={(event) => setBase(event.target.value)} /></div>
              <ArrowRight className="ref-arrow" size={16} />
              <div className="ref-field"><label htmlFor="head-ref">TO</label><input id="head-ref" value={head} onChange={(event) => setHead(event.target.value)} /></div>
              <span className="ref-hint">ROOT = full project</span>
            </div>
            <div className="website-field">
              <label className="field-label" htmlFor="website-url">PERSONAL WEBSITE URL <span>OPTIONAL</span></label>
              <input id="website-url" type="url" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} placeholder="https://yourname.com" />
              <p>Used when publishing website copy to GitHub Pages.</p>
            </div>
          </form>

          <form className="prompt-card" onSubmit={generate}>
            <div className="section-heading">
              <div className="step-number">02</div>
              <div>
                <div className="section-title">Tell us what you’re going for</div>
                <div className="section-subtitle">One project, different stories. Pick the profiles you want to tailor for.</div>
              </div>
            </div>
            <div className="role-grid">
              {roleOptions.map((role) => (
                <button
                  type="button"
                  key={role.id}
                  onClick={() => toggleRole(role.id)}
                  className={`role-chip ${roles.includes(role.id) ? "selected" : ""}`}
                  aria-pressed={roles.includes(role.id)}
                >
                  <span className="role-check">{roles.includes(role.id) && <Check size={12} />}</span>
                  {role.short}
                </button>
              ))}
            </div>
            <label className="field-label prompt-label" htmlFor="prompt">YOUR DIRECTION</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="e.g. Emphasize the technical decisions and measurable impact for senior engineering roles. Keep the tone direct and avoid buzzwords."
              minLength={10}
              maxLength={3000}
              required
            />
            <div className="form-footer">
              <span><ShieldCheck size={15} /> Secrets are redacted before the diff is sent to LiteLLM.</span>
              <button className="primary-button" disabled={busy || !repo || !roles.length}>
                {busy ? <LoaderCircle className="spin" size={17} /> : <WandSparkles size={17} />}
                {busy ? "Working on your drafts…" : "Generate drafts"}
                {!busy && <ArrowRight size={16} />}
              </button>
            </div>
          </form>

          {error && <div className="alert error-alert" role="alert"><CircleHelp size={17} />{error}</div>}
          {notice && !error && <div className="alert notice-alert"><CheckCircle2 size={17} />{notice}</div>}

          {result && (
            <section className="review-section" aria-labelledby="review-title">
              <div className="review-head">
                <div>
                  <div className="eyebrow"><span className="eyebrow-line" /> YOUR DRAFTS</div>
                  <h2 id="review-title">Pick what goes where.</h2>
                  <p>Edit wording, then choose a destination. Drafts are saved in this browser.</p>
                </div>
                <button className="text-button" onClick={clearDrafts}><RefreshCw size={15} /> Start over</button>
              </div>
              <div className="review-meta">
                <span><Github size={15} /> {result.repo.path}</span>
                <span>{result.base} <ArrowRight size={13} /> {result.head}</span>
              </div>

              {result.verification?.length > 0 && (
                <div className="verify-card">
                  <div className="verify-heading"><TriangleAlert size={16} /><strong>Deterministic claim check</strong></div>
                  <p>These technologies or numbers were not found in the repository evidence.</p>
                  {result.verification.map((flag, index) => (
                    <p key={`${flag.claim}-${index}`}><strong>{flag.claim}</strong> — {flag.reason}</p>
                  ))}
                </div>
              )}

              <div className="destination-title"><div className="step-number">03</div><div><h3>Career stories</h3><p>Overleaf-ready resume text. Edit freely, then select each destination independently.</p></div></div>
              <div className="bullet-list">
                {bulletItems.length ? bulletItems.map((item) => (
                  <article className="bullet-card" key={item.id}>
                    <div className="bullet-body">
                      <span className="role-tag">{item.role}</span>
                      <textarea
                        className="bullet-edit"
                        value={item.text}
                        onChange={(event) => updateBullet(item.id, event.target.value)}
                        rows={3}
                      />
                    </div>
                    <div className="target-row">
                      <TargetToggle active={selection.resume.has(item.id)} onClick={() => toggleTarget("resume", item.id)}><FileText size={14} /> Resume · {roleShort[item.role] || item.role}</TargetToggle>
                      <TargetToggle active={selection.github.has(item.id)} onClick={() => toggleTarget("github", item.id)}><Github size={14} /> GitHub</TargetToggle>
                      <TargetToggle active={selection.website.has(item.id)} onClick={() => toggleTarget("website", item.id)}><FileText size={14} /> Website</TargetToggle>
                      <TargetToggle active={selection.linkedin.has(item.id)} onClick={() => toggleTarget("linkedin", item.id)}><Linkedin size={14} /> LinkedIn</TargetToggle>
                    </div>
                  </article>
                )) : <div className="empty-state">No resume bullets were supported by this evidence. The summaries below may still contain useful drafts.</div>}
              </div>

              <div className="destination-title other-destinations"><div className="step-number">04</div><div><h3>Profile &amp; post drafts</h3><p>Approve once, then publish the locked preview to Overleaf, GitHub Pages, or LinkedIn.</p></div></div>
              <div className="artifact-grid">
                <ArtifactCard icon={<Github size={16} />} title="GitHub project summary" text={result.github_summary} empty="No summary generated." checked={selection.github.has("github-summary")} onToggle={() => toggleTarget("github", "github-summary")} onChange={(value) => updateField("github_summary", value)} target="Use for GitHub" />
                <ArtifactCard icon={<FileText size={16} />} title="Personal website copy" text={result.website_copy} empty="No website copy generated." checked={selection.website.has("website-copy")} onToggle={() => toggleTarget("website", "website-copy")} onChange={(value) => updateField("website_copy", value)} target="Use for website" />
                <ArtifactCard icon={<Linkedin size={16} />} title="LinkedIn profile snippet" text={result.linkedin_summary} empty="No summary generated." checked={selection.linkedin.has("linkedin-summary")} onToggle={() => toggleTarget("linkedin", "linkedin-summary")} onChange={(value) => updateField("linkedin_summary", value)} target="Use for LinkedIn" />
                <ArtifactCard icon={<Linkedin size={16} />} title="LinkedIn post draft" text={result.linkedin_post} empty="No post draft generated." checked={selection.post} onToggle={togglePost} onChange={(value) => updateField("linkedin_post", value)} target="Select post draft" />
              </div>

              <div className="review-bottom">
                <div className="checklist-card">
                  <div className="checklist-heading"><ClipboardCheck size={17} /><div><strong>Before you approve</strong><span>Confirm each item yourself.</span></div></div>
                  {result.checklist.map((item, index) => (
                    <label className="checklist-item" key={`${index}-${item}`}>
                      <input type="checkbox" checked={Boolean(checklist[index])} onChange={() => {
                        markDirty();
                        setChecklist((current) => current.map((value, i) => i === index ? !value : value));
                      }} />
                      <span className="custom-check">{checklist[index] && <Check size={12} />}</span>
                      <span>{item}</span>
                    </label>
                  ))}
                  {result.evidence_notes.length > 0 && <div className="evidence-notes"><strong>Evidence notes</strong>{result.evidence_notes.map((note, index) => <p key={index}>{note}</p>)}</div>}
                </div>
                <div className="approval-card">
                  <div className="approval-icon"><LockKeyhole size={17} /></div>
                  <div className="approval-copy"><strong>Nothing moves without you.</strong><p>Approval locks a preview hash. Publishers refuse anything that no longer matches.</p></div>
                  <button className="approve-button" disabled={!canApprove || busy} onClick={approveSelection}>
                    <CheckCircle2 size={16} /> Approve {selectedCount} selected
                  </button>
                  {approved && <button className="export-button" onClick={exportApproved}><ArrowDownToLine size={16} /> Download approved selection</button>}
                  {approved && (
                    <div className="publish-row">
                      <button className="export-button" disabled={busy || !publishers.overleaf} onClick={() => publish("overleaf")}>Publish to Overleaf</button>
                      <button className="export-button" disabled={busy || !publishers.github} onClick={() => publish("github")}>Open GitHub Pages PR</button>
                      <button className="export-button" disabled={busy || !publishers.linkedin || !approvedContent?.linkedin_post} onClick={() => publish("linkedin")}>Post to LinkedIn</button>
                    </div>
                  )}
                  {approved && previewHash && <p className="hash-line">Preview hash {previewHash.slice(0, 16)}…</p>}
                  {publishLog.map((item) => <p className="hash-line" key={item}>{item}</p>)}
                  {!canApprove && <span className="approval-hint">{selectedCount === 0 ? "Select at least one item and verify the checklist." : "Verify every checklist item to approve."}</span>}
                  {approved && !publishers.overleaf && !publishers.github && !publishers.linkedin && (
                    <span className="approval-hint">Set OVERLEAF_GIT_URL, GITHUB_TOKEN + GITHUB_PAGES_REPO, or LINKEDIN_ACCESS_TOKEN + LINKEDIN_PERSON_URN to enable publishing.</span>
                  )}
                </div>
              </div>
            </section>
          )}

          <footer className="page-footer"><span>Built around your approval.</span><span>Drafts are suggestions, not facts. Verify before use.</span></footer>
        </div>
      </main>
    </div>
  );
}

function TargetToggle({ active, disabled = false, onClick, children }) {
  return (
    <button type="button" className={`target-toggle ${active ? "active" : ""}`} onClick={onClick} aria-pressed={active} disabled={disabled}>
      <span className="toggle-box">{active && <Check size={11} />}</span>{children}
    </button>
  );
}

function ArtifactCard({ icon, title, text, empty, checked, onToggle, onChange, target }) {
  return (
    <article className="artifact-card">
      <div className="artifact-title">{icon}<strong>{title}</strong></div>
      <textarea
        className="artifact-edit"
        value={text}
        placeholder={empty}
        onChange={(event) => onChange(event.target.value)}
        rows={6}
      />
      <TargetToggle active={checked} disabled={!text} onClick={onToggle}><Plus size={14} /> {target}</TargetToggle>
    </article>
  );
}

export default App;
