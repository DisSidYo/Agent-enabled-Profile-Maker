import { useMemo, useState } from "react";
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
  WandSparkles,
} from "lucide-react";

const ROLES = ["Software Engineering", "AI / ML", "Data Analytics", "Consulting"];
const ROLE_SHORT = {
  "Software Engineering": "Engineering",
  "AI / ML": "AI / ML",
  "Data Analytics": "Analytics",
  Consulting: "Consulting",
};

const emptySelection = () => ({
  resume: new Set(),
  github: new Set(),
  website: new Set(),
  linkedin: new Set(),
  post: false,
});

function App() {
  const [repoPath, setRepoPath] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [base, setBase] = useState("HEAD~1");
  const [head, setHead] = useState("HEAD");
  const [prompt, setPrompt] = useState("");
  const [roles, setRoles] = useState(["Software Engineering", "AI / ML"]);
  const [repo, setRepo] = useState(null);
  const [result, setResult] = useState(null);
  const [selection, setSelection] = useState(emptySelection);
  const [checklist, setChecklist] = useState([]);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedCount = useMemo(() => (
    selection.resume.size + selection.github.size + selection.website.size + selection.linkedin.size
    + Number(selection.post)
  ), [selection]);

  async function api(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Something went wrong.");
    return data;
  }

  async function connectRepo(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setResult(null);
    setRepo(null);
    setApproved(false);
    setBusy(true);
    try {
      const data = await api("/api/repo", { repo_path: repoPath });
      setRepo(data);
      setRepoPath(data.path);
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
    setBusy(true);
    try {
      const data = await api("/api/generate", {
        repo_path: repo?.path || repoPath,
        base,
        head,
        prompt,
        roles,
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
      setNotice("Drafts ready. Review every claim and choose where each one belongs.");
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

  function toggleTarget(target, id) {
    setApproved(false);
    setSelection((current) => {
      const next = { ...current, [target]: new Set(current[target]) };
      next[target].has(id) ? next[target].delete(id) : next[target].add(id);
      return next;
    });
  }

  function togglePost() {
    setApproved(false);
    setSelection((current) => ({ ...current, post: !current.post }));
  }

  function exportApproved() {
    const approvedContent = {
      approved_at: new Date().toISOString(),
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
    const blob = new Blob([JSON.stringify(approvedContent, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "approved-career-content.json";
    anchor.click();
    URL.revokeObjectURL(url);
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
          setResult(null);
          setApproved(false);
        }}><FileText size={17} /> Review drafts</button>
        <div className="sidebar-bottom">
          <div className="privacy-card">
            <div className="privacy-icon"><LockKeyhole size={16} /></div>
            <strong>You’re in control</strong>
            <p>Nothing gets published or changed unless you approve it.</p>
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
              <span className="ref-hint">Git commits or refs</span>
            </div>
            <div className="website-field">
              <label className="field-label" htmlFor="website-url">PERSONAL WEBSITE URL <span>OPTIONAL</span></label>
              <input id="website-url" type="url" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} placeholder="https://yourname.com" />
              <p>Saved with your approved export only. No website connection is made.</p>
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
              {ROLES.map((role) => (
                <button
                  type="button"
                  key={role}
                  onClick={() => toggleRole(role)}
                  className={`role-chip ${roles.includes(role) ? "selected" : ""}`}
                  aria-pressed={roles.includes(role)}
                >
                  <span className="role-check">{roles.includes(role) && <Check size={12} />}</span>
                  {ROLE_SHORT[role]}
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
              <span><ShieldCheck size={15} /> Only the selected Git diff is sent to LiteLLM for drafting.</span>
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
                  <p>Every item starts unselected. Choose a destination for each one.</p>
                </div>
                <button className="text-button" onClick={() => {
                  setResult(null);
                  setApproved(false);
                }}><RefreshCw size={15} /> Start over</button>
              </div>
              <div className="review-meta">
                <span><Github size={15} /> {result.repo.path}</span>
                <span>{result.base} <ArrowRight size={13} /> {result.head}</span>
              </div>

              <div className="destination-title"><div className="step-number">03</div><div><h3>Career stories</h3><p>Overleaf-ready resume text. Select each destination independently.</p></div></div>
              <div className="bullet-list">
                {bulletItems.length ? bulletItems.map((item) => (
                  <article className="bullet-card" key={item.id}>
                    <div className="bullet-body">
                      <span className="role-tag">{item.role}</span>
                      <p>{item.text}</p>
                    </div>
                    <div className="target-row">
                      <TargetToggle active={selection.resume.has(item.id)} onClick={() => toggleTarget("resume", item.id)}><FileText size={14} /> Resume · {ROLE_SHORT[item.role] || item.role}</TargetToggle>
                      <TargetToggle active={selection.github.has(item.id)} onClick={() => toggleTarget("github", item.id)}><Github size={14} /> GitHub</TargetToggle>
                      <TargetToggle active={selection.website.has(item.id)} onClick={() => toggleTarget("website", item.id)}><FileText size={14} /> Website</TargetToggle>
                      <TargetToggle active={selection.linkedin.has(item.id)} onClick={() => toggleTarget("linkedin", item.id)}><Linkedin size={14} /> LinkedIn</TargetToggle>
                    </div>
                  </article>
                )) : <div className="empty-state">No resume bullets were supported by this diff. The summaries below may still contain useful drafts.</div>}
              </div>

              <div className="destination-title other-destinations"><div className="step-number">04</div><div><h3>Profile &amp; post drafts</h3><p>Nothing is sent to GitHub, your website, LinkedIn, or Overleaf from here.</p></div></div>
              <div className="artifact-grid">
                <ArtifactCard icon={<Github size={16} />} title="GitHub project summary" text={result.github_summary} empty="No summary generated." checked={selection.github.has("github-summary")} onToggle={() => toggleTarget("github", "github-summary")} target="Use for GitHub" />
                <ArtifactCard icon={<FileText size={16} />} title="Personal website copy" text={result.website_copy} empty="No website copy generated." checked={selection.website.has("website-copy")} onToggle={() => toggleTarget("website", "website-copy")} target="Use for website" />
                <ArtifactCard icon={<Linkedin size={16} />} title="LinkedIn profile snippet" text={result.linkedin_summary} empty="No summary generated." checked={selection.linkedin.has("linkedin-summary")} onToggle={() => toggleTarget("linkedin", "linkedin-summary")} target="Use for LinkedIn" />
                <ArtifactCard icon={<Linkedin size={16} />} title="LinkedIn post draft" text={result.linkedin_post} empty="No post draft generated." checked={selection.post} onToggle={togglePost} target="Select post draft" />
              </div>

              <div className="review-bottom">
                <div className="checklist-card">
                  <div className="checklist-heading"><ClipboardCheck size={17} /><div><strong>Before you approve</strong><span>Confirm each item yourself.</span></div></div>
                  {result.checklist.map((item, index) => (
                    <label className="checklist-item" key={`${index}-${item}`}>
                      <input type="checkbox" checked={Boolean(checklist[index])} onChange={() => {
                        setApproved(false);
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
                  <div className="approval-copy"><strong>Nothing moves without you.</strong><p>Approval only prepares a local JSON export. No profile, resume, repository, or post is updated.</p></div>
                  <button className="approve-button" disabled={!canApprove} onClick={() => {
                    setApproved(true);
                    setNotice("Approved for local export only. Nothing has been published or changed.");
                  }}>
                    <CheckCircle2 size={16} /> Approve {selectedCount} selected
                  </button>
                  {approved && <button className="export-button" onClick={exportApproved}><ArrowDownToLine size={16} /> Download approved selection</button>}
                  {!canApprove && <span className="approval-hint">{selectedCount === 0 ? "Select at least one item and verify the checklist." : "Verify every checklist item to approve."}</span>}
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

function ArtifactCard({ icon, title, text, empty, checked, onToggle, target }) {
  return (
    <article className="artifact-card">
      <div className="artifact-title">{icon}<strong>{title}</strong></div>
      <p className={text ? "" : "muted"}>{text || empty}</p>
      <TargetToggle active={checked} disabled={!text} onClick={onToggle}><Plus size={14} /> {target}</TargetToggle>
    </article>
  );
}

export default App;
