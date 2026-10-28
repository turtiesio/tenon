#!/usr/bin/env python3
"""The GitHub side of the unattended runs (docs/dev/automation.md), through `gh`.

    ops/repo/gh.py issues FILE            open or update one issue per entry of FILE
    ops/repo/gh.py pr BRANCH TITLE BODY_FILE [--only PREFIX]
                                       commit the working tree to BRANCH, open its
                                       pull request with auto-merge, run CI on it
    ops/repo/gh.py claim                  the oldest open `agent-ok` issue: label it
                                       `in-progress`, write .agent/issue.md, print its number
    ops/repo/gh.py release N REASON_FILE  give issue N back: `needs-owner`, with the reason

FILE is a JSON list of {"key", "title", "body", "labels"} (ops/repo/status.py writes
.evidence/regressions.json; the review agents write .agent/issues.json). The
key is stable across runs and leads the title in brackets, so a problem seen
again updates its issue (reopens it if it was fixed) instead of opening another.
Exit status 3 from `pr`: the change was refused (outside PREFIX, or
ops/repo/approvals.py --pr); nothing was pushed.
"""
import json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AI_CREDIT = re.compile(r"^\s*co-authored-by:.*(claude|anthropic|openai|codex|gpt)|generated with .*(claude|codex)", re.I)
LABELS = {"regression", "redteam", "hygiene", "agent-ok", "needs-owner", "in-progress"}  # ops/repo/gh_labels.sh
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}  # whose issues an agent may take as instructions
BOT = "github-actions[bot]"


def run(*cmd, check=True):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"gh.py: {' '.join(cmd[:3])} failed: {r.stderr.strip()[:500]}")
    return r


def gh_json(*args):
    return json.loads(run("gh", *args).stdout or "null")


def repo():
    return os.environ.get("GITHUB_REPOSITORY") or gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]


def issues(path):
    entries = json.load(open(path)) if os.path.exists(path) else []
    known = gh_json("issue", "list", "--state", "all", "--limit", "1000", "--json", "number,title,state,stateReason")
    by_key = {}
    for i in sorted(known, key=lambda i: i["number"]):
        if i["title"].startswith("["):
            by_key.setdefault(i["title"][1:].split("]")[0], i)  # the oldest issue with a key owns it
    stamp = f"\n\n---\nSeen by `{os.environ.get('GITHUB_WORKFLOW', 'ops/repo/gh.py')}` at `{run('git', 'rev-parse', '--short', 'HEAD').stdout.strip()}`" \
            + (f" ({os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']})"
               if os.environ.get("GITHUB_RUN_ID") else "") + "."
    for e in entries:
        key = e["key"].replace("]", ")")
        title = f"[{key}] {e['title']}"[:250]
        labels = sorted(set(e.get("labels", [])) & LABELS)
        body = "\n".join(l for l in (e.get("body") or e["title"])[:60000].splitlines() if not AI_CREDIT.search(l)) + stamp
        old = by_key.get(key)
        if old is None:
            r = run("gh", "issue", "create", "--title", title, "--body", body, *sum((["--label", l] for l in labels), []))
            print(f"gh.py: opened {r.stdout.strip()} [{key}]")
        elif old["state"] == "CLOSED" and old.get("stateReason") == "NOT_PLANNED":
            print(f"gh.py: #{old['number']} [{key}] was closed as not planned; left closed")
        else:
            if old["state"] == "CLOSED":
                run("gh", "issue", "reopen", str(old["number"]), "--comment", "Seen again: reopened." + stamp)
            run("gh", "issue", "edit", str(old["number"]), "--title", title, "--body", body,
                *sum((["--add-label", l] for l in labels), []))
            print(f"gh.py: updated #{old['number']} [{key}]")


def pr(branch, title, body_file, only=None):
    run("git", "add", "-A")
    changed = run("git", "diff", "--cached", "--name-only").stdout.split()
    if not changed:
        print("gh.py: no changes; no pull request")
        return 0
    outside = [p for p in changed if only and not p.startswith(only)]
    if outside:
        print(f"gh.py: refused: this run may change only {only}, not: {' '.join(outside)}")
        return 3
    # owner rule (docs/log.md): no AI co-author trailer or "generated with" line, in the commit or the pull request
    body = "\n".join(l for l in open(body_file).read().splitlines() if not AI_CREDIT.search(l)).strip() + "\n"
    open(body_file, "w").write(body)
    who = ["-c", f"user.name={BOT}", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]
    run("git", "checkout", "-q", "-B", branch)
    run("git", *who, "commit", "-q", "-m", title, "-m", body)
    run("git", "fetch", "-q", "origin", "main")
    # the base's checker, not this branch's (the branch may not change it, but it could)
    base = run("git", "merge-base", "origin/main", "HEAD").stdout.strip()
    checker = os.path.join(ROOT, ".git", "approvals_base.py")
    open(checker, "w").write(run("git", "show", f"{base}:ops/repo/approvals.py").stdout)
    r = run(sys.executable, checker, "--pr", base, check=False)
    print(r.stdout, end="")
    if r.returncode != 0:
        print("gh.py: refused by ops/repo/approvals.py --pr; nothing pushed")
        return 3
    run("git", "push", "-q", "-f", "origin", f"HEAD:refs/heads/{branch}")
    open_prs = gh_json("pr", "list", "--head", branch, "--state", "open", "--json", "number")
    if open_prs:
        run("gh", "pr", "edit", branch, "--title", title, "--body-file", body_file)
    else:
        run("gh", "pr", "create", "--base", "main", "--head", branch, "--title", title, "--body-file", body_file)
    url = run("gh", "pr", "view", branch, "--json", "url", "-q", ".url").stdout.strip()
    run("gh", "pr", "merge", branch, "--auto", "--squash")  # the repository deletes merged branches
    start_ci(branch, run("git", "rev-parse", "HEAD").stdout.strip())
    print(f"gh.py: {url} (auto-merge when CI passes)")
    return 0


def start_ci(branch, sha):
    """CI's pull_request run is what branch protection counts. GitHub holds it ("action_required") while
    github-actions[bot] counts as a first-time contributor: approve it. If none appears, start ci.yml."""
    runs = []
    for _ in range(12):
        runs = gh_json("api", f"repos/{repo()}/actions/runs?event=pull_request&head_sha={sha}")["workflow_runs"]
        if runs:
            break
        time.sleep(10)
    for r in runs:
        if r["conclusion"] == "action_required":
            ok = run("gh", "api", "-X", "POST", f"repos/{repo()}/actions/runs/{r['id']}/approve", check=False).returncode == 0
            print(f"gh.py: CI run {r['html_url']} " + ("approved" if ok else "waits for the owner's approval"))
    if not runs:
        run("gh", "workflow", "run", "ci.yml", "--ref", branch)
        print("gh.py: no pull_request run appeared; started ci.yml on the branch")


def claim():
    items = gh_json("api", f"repos/{repo()}/issues?labels=agent-ok&state=open&sort=created&direction=asc&per_page=100")
    for i in items:
        names = {l["name"] for l in i["labels"]}
        if "pull_request" in i or names & {"in-progress", "needs-owner"}:
            continue
        if i["author_association"] not in TRUSTED and i["user"]["login"] != BOT:
            print(f"gh.py: skipping #{i['number']}: opened by {i['user']['login']}, who is not a collaborator", file=sys.stderr)
            continue
        run("gh", "issue", "edit", str(i["number"]), "--add-label", "in-progress")
        os.makedirs(os.path.join(ROOT, ".agent"), exist_ok=True)
        open(os.path.join(ROOT, ".agent", "issue.md"), "w").write(
            f"# Issue #{i['number']}: {i['title']}\n\nLabels: {', '.join(sorted(names))}\n\n{i['body'] or ''}\n")
        print(i["number"])
        return 0
    print("gh.py: no open agent-ok issue to take", file=sys.stderr)
    return 0


def release(number, reason_file):
    run("gh", "issue", "edit", number, "--remove-label", "in-progress", "--add-label", "needs-owner")
    run("gh", "issue", "comment", number, "--body-file", reason_file)
    return 0


def main():
    a = sys.argv[1:]
    if a[:1] == ["issues"] and len(a) == 2:
        return issues(a[1])
    if a[:1] == ["pr"] and len(a) in (4, 6):
        return pr(a[1], a[2], a[3], a[5] if len(a) == 6 and a[4] == "--only" else None)
    if a == ["claim"]:
        return claim()
    if a[:1] == ["release"] and len(a) == 3:
        return release(a[1], a[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
