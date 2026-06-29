#!/usr/bin/env python3
"""
Fetch a YouTube video's metadata + transcript via Playwright and write a
Markdown file with a YAML front-matter header.

The script drives a real Chromium, expands the description, dispatches
YouTube's `yt-show-engagement-panel-action` event so YouTube's own Polymer
app loads the transcript panel through its internal RPC (which carries the
required PoT / session tokens), then scrapes the resulting DOM.

Metadata is pulled from `window.ytInitialPlayerResponse` and
`window.ytInitialData` once the page has hydrated.

Usage:
    python fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python fetch_transcript.py "VIDEO_ID" --json
    python fetch_transcript.py "URL" -o transcript.md --headed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml
from playwright.async_api import async_playwright, Page


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def extract_video_id(value: str) -> str:
    """Accept a full URL (youtube.com/watch?v=, youtu.be/, /shorts/, /embed/, /live/)
    or a bare 11-char video ID."""
    if VIDEO_ID_RE.match(value):
        return value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        if VIDEO_ID_RE.match(candidate):
            return candidate
    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs and VIDEO_ID_RE.match(qs["v"][0]):
            return qs["v"][0]
        m = re.search(r"/(?:shorts|embed|v|live)/([A-Za-z0-9_-]{11})", parsed.path)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from {value!r}")


# ---------------------------------------------------------------------------
# Page interactions
# ---------------------------------------------------------------------------

async def _dismiss_consent(page: Page) -> None:
    """First-time visitors land on consent.youtube.com. Click 'Reject all' if
    the dialog is present. Best-effort; ignore failures."""
    try:
        for label in ("Reject all", "Alles afwijzen", "Tout refuser", "Alle ablehnen"):
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                await page.wait_for_load_state("domcontentloaded")
                return
    except Exception:
        pass


async def _grab_metadata(page: Page) -> dict:
    """Read the rich metadata blob from ytInitialPlayerResponse + ytInitialData.
    Optional chaining keeps partial DOM-drift from crashing — fields just go null."""
    return await page.evaluate(
        """() => {
            const pr = window.ytInitialPlayerResponse || {};
            const id = window.ytInitialData || {};
            const vd = pr.videoDetails || {};
            const mf = pr.microformat?.playerMicroformatRenderer || {};
            const captionTracks = pr.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

            // Chapters: walk engagementPanels for the macro-markers list.
            let chapters = [];
            for (const panel of (id.engagementPanels || [])) {
                const items = panel?.engagementPanelSectionListRenderer
                    ?.content?.macroMarkersListRenderer?.contents;
                if (items && items.length) {
                    chapters = items
                        .map(c => c.macroMarkersListItemRenderer)
                        .filter(Boolean)
                        .map(c => ({
                            title: c.title?.simpleText || c.title?.runs?.[0]?.text || '',
                            start: c.timeDescription?.simpleText || '',
                            start_ms: Number(c.timeRangeStartMillis ?? 0),
                        }))
                        .filter(c => c.title);
                    break;
                }
            }

            const thumbs = (vd.thumbnail?.thumbnails || []).map(t => ({
                url: t.url, width: t.width, height: t.height,
            }));
            const bestThumb = thumbs.length ? thumbs[thumbs.length - 1].url : null;

            return {
                video_id: vd.videoId || null,
                title: vd.title || null,
                url: `https://www.youtube.com/watch?v=${vd.videoId || ''}`,
                channel: vd.author || null,
                channel_id: vd.channelId || null,
                channel_url: vd.channelId ? `https://www.youtube.com/channel/${vd.channelId}` : null,

                // shortDescription is the FULL creator-written description (not truncated)
                description: vd.shortDescription || null,
                keywords: vd.keywords || [],
                category: mf.category || null,

                publish_date: mf.publishDate || null,    // when YT made it visible
                upload_date: mf.uploadDate || null,      // when the file was uploaded

                length_seconds: Number(vd.lengthSeconds) || null,
                view_count: Number(vd.viewCount) || null,

                default_language: mf.defaultLanguage || mf.defaultAudioLanguage || null,
                available_countries: mf.availableCountries || [],

                is_family_safe: mf.isFamilySafe ?? null,
                is_live: !!vd.isLiveContent,
                is_upcoming: !!vd.isUpcoming,
                is_private: !!vd.isPrivate,

                thumbnail: bestThumb,
                thumbnails: thumbs,

                caption_tracks: captionTracks.map(t => ({
                    language_code: t.languageCode,
                    name: t.name?.simpleText || t.name?.runs?.[0]?.text || null,
                    kind: t.kind || 'manual',     // 'asr' = auto-generated, else creator-uploaded
                    is_translatable: !!t.isTranslatable,
                })),

                chapters,

                playability: {
                    status: pr.playabilityStatus?.status || null,
                    reason: pr.playabilityStatus?.reason || null,
                },
            };
        }"""
    )


async def _trigger_transcript_panel(page: Page) -> bool:
    """Open the transcript engagement panel. Returns True iff a transcript-bearing
    UI element exists on the page (whether or not the open succeeds — the caller
    waits for content separately).

    YouTube has shipped multiple transcript-panel flavours; this function tries
    both the legacy `yt-action` event-dispatch and a direct click on the
    'Show transcript' button as a fallback. See GH #2.
    """
    has_transcript_ui = await page.evaluate(
        """() => {
            if (document.querySelector('ytd-video-description-transcript-section-renderer')) return true;
            const btn = Array.from(document.querySelectorAll('button')).find(
                b => /show transcript/i.test(b.innerText || '')
            );
            return !!btn;
        }"""
    )
    if not has_transcript_ui:
        return False
    # Try YouTube's own engagement-panel action first.
    await page.evaluate(
        """() => {
            const sec = document.querySelector('ytd-video-description-transcript-section-renderer');
            if (sec && sec.data) {
                const cmd = sec.data.primaryButton?.buttonRenderer?.command;
                const targetId = cmd?.commandExecutorCommand?.commands?.[0]
                    ?.showEngagementPanelEndpoint?.identifier?.tag || 'PAmodern_transcript_view';
                document.dispatchEvent(new CustomEvent('yt-action', {
                    bubbles: true,
                    detail: {
                        actionName: 'yt-show-engagement-panel-action',
                        args: [{ panelIdentifier: targetId }],
                    },
                }));
            }
        }"""
    )
    # Fallback: direct click on the 'Show transcript' button. Robust to panel-
    # target-id drift; the click expands whichever panel YouTube currently uses.
    await page.evaluate(
        """() => {
            const btn = Array.from(document.querySelectorAll('button')).find(
                b => /show transcript/i.test(b.innerText || '')
            );
            if (btn) btn.click();
        }"""
    )
    return True


async def _wait_for_transcript(page: Page, timeout_ms: int) -> None:
    """Wait until transcript content is loaded — segment renderers preferred,
    falling back to any expanded engagement-panel with substantial text."""
    await page.wait_for_function(
        """() => {
            const renderers = document.querySelectorAll('ytd-transcript-segment-renderer');
            if (renderers.length >= 3) return true;
            const panels = document.querySelectorAll('ytd-engagement-panel-section-list-renderer');
            for (const p of panels) {
                if (p.getAttribute('visibility') === 'ENGAGEMENT_PANEL_VISIBILITY_EXPANDED'
                    && (p.innerText || '').length > 200) {
                    return true;
                }
            }
            return false;
        }""",
        timeout=timeout_ms,
    )


async def _scroll_panel(page: Page) -> None:
    """For long videos the segment list virtualizes. Scroll the segment-renderer
    container to the bottom repeatedly so all segments materialize, then back to
    the top."""
    await page.evaluate(
        """async () => {
            const renderer = document.querySelector('ytd-transcript-segment-renderer');
            if (!renderer) return;
            // Walk up the ancestry to find the scrollable container.
            let scroller = renderer.parentElement;
            while (scroller) {
                if (scroller.scrollHeight > scroller.clientHeight + 50 && scroller.clientHeight > 100) {
                    break;
                }
                scroller = scroller.parentElement;
            }
            if (!scroller) return;
            for (let i = 0; i < 40; i++) {
                const before = scroller.scrollTop;
                scroller.scrollTop = scroller.scrollHeight;
                await new Promise(r => setTimeout(r, 150));
                if (scroller.scrollTop === before) break;
            }
            scroller.scrollTop = 0;
        }"""
    )


async def _extract_segments(page: Page) -> list[dict]:
    return await page.evaluate(
        """() => {
            // Preferred: query structured segment renderers anywhere on the page.
            const renderers = document.querySelectorAll('ytd-transcript-segment-renderer');
            if (renderers.length) {
                return Array.from(renderers).map(r => ({
                    ts: (r.querySelector('.segment-timestamp')?.innerText || '').trim(),
                    text: (r.querySelector('.segment-text, yt-formatted-string.segment-text')?.innerText || '').trim(),
                })).filter(s => s.text);
            }
            // Fallback: parse innerText of the first expanded engagement panel.
            let panel = null;
            for (const p of document.querySelectorAll('ytd-engagement-panel-section-list-renderer')) {
                if (p.getAttribute('visibility') === 'ENGAGEMENT_PANEL_VISIBILITY_EXPANDED'
                    && (p.innerText || '').length > 200) {
                    panel = p; break;
                }
            }
            if (!panel) return [];
            const lines = (panel.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
            const tsRe = /^\\d+:\\d{2}(?::\\d{2})?$/;
            const durRe = /^\\d+\\s+(seconds?|minutes?(?:\\s+and\\s+\\d+\\s+seconds?)?)$/i;
            const dutchRe = /^\\d+\\s+(seconde[n]?|minu(?:ut|ten))(\\s+en\\s+\\d+\\s+seconde[n]?)?$/i;
            const out = [];
            for (let i = 0; i < lines.length; i++) {
                if (!tsRe.test(lines[i])) continue;
                const ts = lines[i];
                const parts = [];
                let j = i + 1;
                while (j < lines.length && !tsRe.test(lines[j])) {
                    if (!durRe.test(lines[j]) && !dutchRe.test(lines[j])) parts.push(lines[j]);
                    j++;
                }
                if (parts.length) out.push({ ts, text: parts.join(' ') });
                i = j - 1;
            }
            return out;
        }"""
    )


# ---------------------------------------------------------------------------
# Top-level fetch
# ---------------------------------------------------------------------------

async def fetch(video_id: str, *, headless: bool = True, timeout_ms: int = 30000) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            # Suppress the Chromium-level automation flag that lets sites detect
            # WebDriver via Blink's runtime signals. Pair with the navigator
            # spoofing in the init script below — YouTube's /youtubei/v1/get_transcript
            # endpoint started rejecting WEBDRIVER-flagged sessions (HTTP 400
            # "Precondition check failed") around 2026-05-13.
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            bypass_csp=True,
            # The default Playwright UA contains "HeadlessChrome", which is a
            # secondary anti-bot signal. Pinning to a stable non-headless string
            # avoids that without needing the Chromium version to stay in lockstep.
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.7258.66 Safari/537.36"
            ),
        )
        # Init scripts run before any YouTube JS, so the spoofs are in place
        # when get_transcript's preflight runs. See GH #2 / 2026-05-13 incident.
        await ctx.add_init_script(
            """
            // Mask navigator.webdriver — the primary automation signal YouTube
            // checks before issuing /youtubei/v1/get_transcript.
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
            // Make navigator.plugins look populated (headless reports 0).
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            // Realistic languages array (headless Chrome ships with just one).
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            // chrome.runtime stub: headless Chromium omits window.chrome.
            window.chrome = window.chrome || { runtime: {} };
            // Notifications permission: headless reports 'denied', real Chrome 'default'.
            const origPerm = navigator.permissions && navigator.permissions.query
                ? navigator.permissions.query.bind(navigator.permissions)
                : null;
            if (origPerm) {
                navigator.permissions.query = (p) =>
                    p && p.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : origPerm(p);
            }
            """
        )
        page = await ctx.new_page()
        # Defense-in-depth: register a default Trusted Types policy so string-form
        # JS predicates passed to wait_for_function / evaluate aren't rejected
        # if bypass_csp is ever removed (see GH #2).
        await page.add_init_script(
            """
            if (window.trustedTypes && window.trustedTypes.createPolicy) {
                try {
                    window.trustedTypes.createPolicy('default', {
                        createScript: (s) => s,
                        createScriptURL: (s) => s,
                        createHTML: (s) => s,
                    });
                } catch (e) { /* policy already exists; fine */ }
            }
            """
        )
        page.set_default_timeout(timeout_ms)
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await _dismiss_consent(page)
            await page.wait_for_selector("ytd-watch-flexy", timeout=timeout_ms)
            # Wait for the player to mount so ytInitialPlayerResponse is populated.
            await page.wait_for_selector("video", timeout=timeout_ms)

            # Expand the description so the transcript section element is mounted.
            try:
                await page.click("#expand", timeout=4000)
            except Exception:
                pass

            metadata = await _grab_metadata(page)

            triggered = await _trigger_transcript_panel(page)
            if not triggered:
                return {
                    "video_id": video_id,
                    "metadata": metadata,
                    "transcript": None,
                    "error": "no transcript section (video has no captions or hasn't been processed)",
                }

            try:
                await _wait_for_transcript(page, timeout_ms)
            except Exception as e:
                return {
                    "video_id": video_id,
                    "metadata": metadata,
                    "transcript": None,
                    "error": f"transcript panel did not render: {e}",
                }

            await _scroll_panel(page)
            segments = await _extract_segments(page)
            return {"video_id": video_id, "metadata": metadata, "transcript": segments}
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _ts_to_ms(ts: str) -> int:
    """Convert "mm:ss" or "h:mm:ss" to milliseconds."""
    parts = ts.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        return (nums[0] * 60 + nums[1]) * 1000
    if len(nums) == 3:
        return (nums[0] * 3600 + nums[1] * 60 + nums[2]) * 1000
    return 0


def _format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class _YtDumper(yaml.SafeDumper):
    """Local Dumper so our str representer doesn't leak globally."""


def _str_representer(dumper, data: str):
    # Use literal block scalar for any multi-line string (description, etc.)
    if "\n" in data:
        # Normalize CRLF -> LF so '|' renders cleanly.
        data = data.replace("\r\n", "\n").replace("\r", "\n")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_YtDumper.add_representer(str, _str_representer)


# Field order for the YAML header — readable, scannable, with `description` last
# because it's the longest free-text field.
_YAML_KEY_ORDER = [
    "title",
    "video_id",
    "url",
    "channel",
    "channel_id",
    "channel_url",
    "publish_date",
    "upload_date",
    "category",
    "duration",
    "length_seconds",
    "view_count",
    "default_language",
    "is_live",
    "is_upcoming",
    "is_private",
    "is_family_safe",
    "thumbnail",
    "keywords",
    "caption_tracks",
    "available_countries",
    "thumbnails",
    "chapters",
    "description",
]


def _build_yaml_header(meta: dict) -> str:
    enriched = dict(meta)
    if enriched.get("length_seconds"):
        enriched["duration"] = _format_duration(int(enriched["length_seconds"]))

    ordered = {}
    for k in _YAML_KEY_ORDER:
        v = enriched.get(k)
        if v in (None, "", []):
            continue
        ordered[k] = v
    # Append any unexpected fields at the end so we don't silently drop data.
    for k, v in enriched.items():
        if k not in ordered and v not in (None, "", []):
            ordered[k] = v

    return yaml.dump(
        ordered,
        Dumper=_YtDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    ).rstrip()


def to_markdown(result: dict) -> str:
    meta = result.get("metadata") or {}
    segments = result.get("transcript") or []
    chapters = sorted(meta.get("chapters") or [], key=lambda c: c.get("start_ms", 0))

    out: list[str] = ["---", _build_yaml_header(meta), "---", ""]

    if not segments:
        out += ["## Transcript", "", "_(no transcript segments returned)_"]
        return "\n".join(out).rstrip() + "\n"

    if not chapters:
        out += ["## Transcript", ""]
        out += [f"[{s['ts']}] {s['text']}" for s in segments]
        return "\n".join(out).rstrip() + "\n"

    # Chapter-aware rendering: each chapter becomes a section heading.
    boundaries = [c.get("start_ms", 0) for c in chapters] + [10**12]
    pre = [s for s in segments if _ts_to_ms(s["ts"]) < boundaries[0]]
    if pre:
        out += ["## Transcript", ""]
        out += [f"[{s['ts']}] {s['text']}" for s in pre]
        out.append("")
    for i, ch in enumerate(chapters):
        chunk = [s for s in segments if boundaries[i] <= _ts_to_ms(s["ts"]) < boundaries[i + 1]]
        label = ch.get("start") or ""
        title = ch.get("title") or f"Chapter {i + 1}"
        heading = f"## [{label}] {title}".strip() if label else f"## {title}"
        out += [heading, ""]
        out += [f"[{s['ts']}] {s['text']}" for s in chunk]
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a YouTube video's transcript via Playwright.")
    ap.add_argument("url", help="YouTube URL or 11-char video ID")
    ap.add_argument("-o", "--output", help="Output Markdown path (default: ./<video_id>.md)")
    ap.add_argument("--json", action="store_true", help="Emit raw JSON to stdout instead of Markdown")
    ap.add_argument("--headed", action="store_true", help="Run with a visible browser window")
    ap.add_argument("--timeout", type=int, default=30000, help="Per-step timeout in ms (default: 30000)")
    args = ap.parse_args()

    try:
        video_id = extract_video_id(args.url)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = await fetch(video_id, headless=not args.headed, timeout_ms=args.timeout)

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if result.get("transcript") else 1

    # Even when no transcript is available (no captions, timeout, panel never
    # rendered), write the markdown file with full metadata + a placeholder
    # transcript section so the metadata isn't lost. Exit code reflects whether
    # the transcript was successfully fetched.
    out_path = Path(args.output) if args.output else Path(f"{video_id}.md")
    out_path.write_text(to_markdown(result), encoding="utf-8")

    if not result.get("transcript"):
        err = result.get("error", "no transcript")
        n_chs = len(result.get("metadata", {}).get("chapters") or [])
        print(
            f"wrote {out_path} (metadata only — {err}; {n_chs} chapters)",
            file=sys.stderr,
        )
        return 1

    n_segs = len(result["transcript"])
    n_chs = len(result["metadata"].get("chapters") or [])
    print(f"wrote {out_path} ({n_segs} segments, {n_chs} chapters)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
