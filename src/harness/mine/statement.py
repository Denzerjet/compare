"""Build problem statements from django's Trac tickets.

The ticket *description* is the reporter's original bug report, written before a
fix existed, and usually carries a concrete reproduction -- exactly what a
developer receives. That is the statement.

Two things get removed, because measurement showed both occur:

  - Analysis sections. Reporters often append a headed "Root cause" / "Proposed
    fix" section diagnosing the bug. Everything from the first such heading is
    dropped; the symptom and reproduction above it are kept.
  - Code-bearing parentheticals in the summary. Measured incidence was 1 in 12,
    and that one gave away the whole fix.

Deliberately NOT fetched: comments, attachments, and the change history. Those are
where the diagnosis and the patch actually live.

Any statement we modified is flagged for review. The truncation is a heuristic, so
a flag means "a human should confirm this cut was right", not "this is broken".
"""

from __future__ import annotations

import csv
import io
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = HARNESS_ROOT / "repo" / ".trac-cache"
BASE_URL = "https://code.djangoproject.com/ticket"
USER_AGENT = "django-eval-harness/0.1 (research; one request per second)"
RATE_LIMIT_SEC = 1.2
# Trac is slow and periodically unreachable. Short timeout plus one retry: a long
# timeout just makes an outage take longer to detect, and the caller has a
# circuit breaker for sustained failure.
FETCH_TIMEOUT_SEC = 15
FETCH_ATTEMPTS = 2

# Headings that introduce diagnosis rather than symptom. Anchored to whole short
# lines so prose merely containing the word "fix" is not caught -- loose substring
# matching flagged clean tickets in testing and would have truncated the
# expected-behaviour text we specifically want to keep.
ANALYSIS_HEADING = re.compile(
    r"^[ \t]*(?:#+[ \t]*)?"
    r"(root cause|the cause|cause|proposed fix|suggested fix|the fix|fix|patch|"
    r"solution|analysis|diagnosis|how to fix|possible fix)"
    r"[ \t]*:?[ \t]*$",
    re.I | re.M,
)
CODEY_PAREN = re.compile(r"\(([^)]{4,})\)")
CODEY_HINT = re.compile(r"[`\"']|->|=>|should be|instead of", re.I)
# Markers meaning the fix is present verbatim even after truncation. A pasted diff
# IS the answer, so these blocks are removed outright.
DIFF_MARKERS = ("diff --git", "--- a/", "+++ b/", "@@ ")
RESIDUAL_LEAK = DIFF_MARKERS
# A PR or commit URL is recorded but NOT treated as a leak: the agent loop has no
# network access and no fetch tool, so a link it cannot follow reveals nothing.
UNFOLLOWABLE_LINK = re.compile(r"https?://\S*(?:/pull/|/commit/)\S*")
PATCH_PLACEHOLDER = "_[a proposed patch was removed from this report]_"
# A diff can start at any of these; body lines are the usual unified-diff prefixes
# plus `index`/`similarity` metadata git emits.
DIFF_HEADER = re.compile(r"^\s*(diff --git |--- a/|\+\+\+ b/|@@ .*@@|Index: )")
DIFF_BODY = re.compile(r"^\s*([+\- ]|@@|diff --git |index [0-9a-f]|similarity index|"
                       r"rename (from|to) |new file mode|deleted file mode|Index: |=====)")

TICKET_TYPE_MAP = {
    "bug": "bug",
    "new feature": "feature",
    "cleanup/optimization": "cleanup",
    "uncategorized": "unknown",
}


@dataclass
class Statement:
    ticket: str
    summary: str
    body: str
    ticket_type: str = "unknown"
    truncated_at: str = ""
    stripped_parens: list[str] = field(default_factory=list)
    residual_leaks: list[str] = field(default_factory=list)
    stripped_diff_blocks: int = 0
    unfollowable_links: int = 0
    source: str = "trac_description"

    @property
    def needs_review(self) -> bool:
        """True when we altered the statement or a leak survived truncation.

        Not an error -- truncation is heuristic, so this is the short list worth
        reading, not a list of failures.
        """
        return bool(
            self.truncated_at
            or self.stripped_parens
            or self.residual_leaks
            or self.stripped_diff_blocks
        )

    def to_markdown(self) -> str:
        parts = [f"# {self.summary}", ""]
        if self.body.strip():
            parts += [self.body.strip(), ""]
        parts.append(f"Reported in django ticket #{self.ticket}: {BASE_URL}/{self.ticket}")
        return "\n".join(parts) + "\n"


def _fetch_raw(ticket: str, *, cache_dir: Path | None = None) -> str:
    """GET the ticket as TSV, caching so re-runs are offline.

    Cached because django's Trac is community-run infrastructure -- a re-mine
    should cost it nothing.
    """
    cache_dir = Path(cache_dir or CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{ticket}.tab"
    if cached.exists():
        return cached.read_text()

    req = urllib.request.Request(
        f"{BASE_URL}/{ticket}?format=tab", headers={"User-Agent": USER_AGENT}
    )
    last: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            raw = urllib.request.urlopen(
                req, timeout=FETCH_TIMEOUT_SEC
            ).read().decode("utf-8", "replace")
            break
        except Exception as exc:
            last = exc
            if attempt + 1 < FETCH_ATTEMPTS:
                time.sleep(2.0)
    else:
        raise last  # type: ignore[misc]

    cached.write_text(raw)
    time.sleep(RATE_LIMIT_SEC)
    return raw


def _wiki_to_markdown(text: str) -> str:
    """Minimal Trac wiki -> markdown, enough to read naturally in a prompt."""
    text = text.replace("\r\n", "\n")
    # Trac writes `{{{#!py` for a syntax-highlighted block; keep the language hint
    # so the statement renders as a proper fenced block in the prompt.
    text = re.sub(r"^\{\{\{#!(\w+)\s*$", r"```\1", text, flags=re.M)
    text = re.sub(r"^\{\{\{\s*$", "```", text, flags=re.M)
    text = re.sub(r"^\}\}\}\s*$", "```", text, flags=re.M)
    text = re.sub(r"\{\{\{(.+?)\}\}\}", r"`\1`", text, flags=re.S)
    text = re.sub(r"'''(.+?)'''", r"**\1**", text, flags=re.S)
    return text


def strip_diff_blocks(text: str) -> tuple[str, int]:
    """Remove fenced blocks that contain a diff.

    Safe to do bluntly: reproductions are interpreter transcripts or tracebacks,
    never unified diffs, so a fence containing `@@` or `diff --git` is the patch
    rather than the symptom. Measured on 100 tickets, ~6 pasted the fix outright.
    """
    out, removed = [], 0
    for chunk in re.split(r"(^```.*?^```)", text, flags=re.M | re.S):
        if chunk.startswith("```") and any(m in chunk for m in DIFF_MARKERS):
            removed += 1
            out.append(PATCH_PLACEHOLDER)
        else:
            out.append(chunk)
    text = "".join(out)

    # Second pass: many reporters paste the diff as plain text with no fence, so
    # the fence-based pass above misses it entirely. Consume from a diff header
    # through every following line that still looks like diff content.
    lines, kept, i = text.splitlines(), [], 0
    while i < len(lines):
        if DIFF_HEADER.match(lines[i]):
            removed += 1
            while i < len(lines) and (DIFF_BODY.match(lines[i]) or not lines[i].strip()):
                i += 1
            kept.append(PATCH_PLACEHOLDER)
            continue
        kept.append(lines[i])
        i += 1
    return "\n".join(kept), removed


def build(ticket: str, *, cache_dir: Path | None = None) -> Statement:
    raw = _fetch_raw(ticket, cache_dir=cache_dir)
    rows = list(csv.DictReader(io.StringIO(raw), delimiter="\t"))
    if not rows:
        raise ValueError(f"ticket {ticket}: no rows in Trac response")
    row = rows[0]

    summary = (row.get("summary") or "").strip()
    description = _wiki_to_markdown((row.get("description") or "").strip())
    ticket_type = TICKET_TYPE_MAP.get(
        (row.get("type") or "").strip().lower(), "unknown"
    )

    stripped: list[str] = []
    for inner in CODEY_PAREN.findall(summary):
        if CODEY_HINT.search(inner):
            stripped.append(inner)
            summary = summary.replace(f"({inner})", "").strip()
    summary = re.sub(r"\s{2,}", " ", summary)

    description, n_diff = strip_diff_blocks(description)

    truncated_at = ""
    match = ANALYSIS_HEADING.search(description)
    if match:
        truncated_at = match.group(1)
        description = description[: match.start()].rstrip()
        # Drop a setext underline left dangling by the cut.
        description = re.sub(r"\n[-=]{3,}\s*$", "", description)

    stmt = Statement(
        ticket=ticket,
        summary=summary,
        body=description,
        ticket_type=ticket_type,
        truncated_at=truncated_at,
        stripped_parens=stripped,
        stripped_diff_blocks=n_diff,
    )
    rendered = stmt.to_markdown()
    stmt.residual_leaks = [m for m in RESIDUAL_LEAK if m in rendered]
    stmt.unfollowable_links = len(UNFOLLOWABLE_LINK.findall(rendered))
    return stmt
