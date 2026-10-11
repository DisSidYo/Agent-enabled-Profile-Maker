

## Proofpoint

Proofpoint is a local, human-in-the-loop workspace for drafting resume bullets
for Software Engineering, AI / ML, Data Analytics, and Consulting, plus GitHub
project summaries, LinkedIn profile snippets, and a LinkedIn post draft. It
uses the existing LiteLLM gateway and only reads the selected Git diff.

### Run locally

1. Start the LiteLLM gateway using the existing `docker-compose.yml` setup.
2. Install the Python dependencies in your chosen environment:

   ```powershell
   pip install -r requirements.txt
   ```

3. Install and build the React app:

   ```powershell
   Set-Location web
   npm install
   npm run build
   Set-Location ..
   ```

4. Start the local API and UI:

   ```powershell
   uvicorn app:app --reload
   ```

   Open <http://127.0.0.1:8000>.

For frontend iteration, run `npm run dev` from `web` in a second terminal; Vite
proxies `/api` requests to the local API on port 8000.

Enter the path to a **local clone** of the GitHub repository, an optional
personal website URL, and the base/head refs to compare. Generated resume,
GitHub, portfolio-site, and LinkedIn copy is a draft, not verified fact. Review
the evidence notes and checklist, choose each destination independently, and
approve before downloading the selected JSON. This app does not connect to or
write to Overleaf, GitHub, LinkedIn, or a personal website. No publishing,
repository edits, or profile updates occur in the background. Credential-like
diff paths (`.env*`, `*secret*`, `*credentials*`, `*.pem`, and `*.key`) are
excluded from the agent's read-only Git tools; review your selected code for
sensitive values before sending it to your LiteLLM provider.