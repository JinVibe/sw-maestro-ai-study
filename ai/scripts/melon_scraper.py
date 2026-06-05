from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://www.melon.com"
MENU_ID = "19070205"
DETAIL_MENU_ID = "29010101"


class FetchError(RuntimeError):
    def __init__(self, url: str, message: str, status: int | None = None) -> None:
        super().__init__(f"Failed to fetch {url}: {message}")
        self.url = url
        self.status = status
        self.message = message


def chart_page_url(year: int) -> str:
    return f"{BASE_URL}/chart/age/index.htm?chartType=YE&chartGenre=KPOP&chartDate={year}"


def chart_ajax_url(year: int) -> str:
    return f"{BASE_URL}/chart/age/list.htm?idx=1&chartType=YE&chartGenre=KPOP&chartDate={year}&moved=Y"


def detail_url(song_id: str) -> str:
    return f"{BASE_URL}/song/detail.htm?songId={song_id}"


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)

    def text(self, separator: str = " ") -> str:
        parts: list[str] = []

        def walk(node: "Node | str") -> None:
            if isinstance(node, str):
                parts.append(node)
                return
            for child in node.children:
                walk(child)

        walk(self)
        return normalize_text(separator.join(parts))

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def find_all(
        self,
        tag: str | None = None,
        class_name: str | None = None,
        id_: str | None = None,
        attr: tuple[str, str | None] | None = None,
    ) -> list["Node"]:
        matches: list[Node] = []

        def matches_node(node: Node) -> bool:
            if tag is not None and node.tag != tag:
                return False
            if class_name is not None and class_name not in node.classes():
                return False
            if id_ is not None and node.attrs.get("id") != id_:
                return False
            if attr is not None:
                key, value = attr
                if key not in node.attrs:
                    return False
                if value is not None and node.attrs.get(key) != value:
                    return False
            return True

        def walk(node: Node) -> None:
            for child in node.children:
                if isinstance(child, Node):
                    if matches_node(child):
                        matches.append(child)
                    walk(child)

        walk(self)
        return matches

    def find(
        self,
        tag: str | None = None,
        class_name: str | None = None,
        id_: str | None = None,
        attr: tuple[str, str | None] | None = None,
    ) -> "Node | None":
        found = self.find_all(tag=tag, class_name=class_name, id_=id_, attr=attr)
        return found[0] if found else None


class TreeBuilder(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.stack[-1].children.append("\n")
            return
        node = Node(tag.lower(), {key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag.lower() not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    parser = TreeBuilder()
    parser.feed(html)
    parser.close()
    return parser.root


def normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def query_param(url: str, name: str) -> str | None:
    values = parse_qs(urlparse(url).query).get(name)
    return values[0] if values else None


def extract_id_from_href(href: str, param: str, fallback_pattern: str | None = None) -> str | None:
    value = query_param(href, param)
    if value:
        return value
    if fallback_pattern:
        match = re.search(fallback_pattern, href)
        if match:
            return match.group(1)
    return None


def unique_people(people: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for person in people:
        key = (person.get("artistId", ""), person.get("name", ""))
        if key in seen or not person.get("name"):
            continue
        seen.add(key)
        result.append(person)
    return result


def parse_chart_entries(html: str, year: int) -> list[dict[str, Any]]:
    root = parse_html(html)
    rows = [
        row
        for row in root.find_all("tr")
        if row.classes() & {"lst50", "lst100"}
    ]
    entries: list[dict[str, Any]] = []
    for row in rows:
        rank_node = row.find("span", class_name="rank")
        rank = int(rank_node.text()) if rank_node and rank_node.text().isdigit() else None
        song_id = None
        checkbox = row.find("input", attr=("name", "input_check"))
        if checkbox:
            song_id = checkbox.attrs.get("value")
        detail_link = row.find("a", class_name="btn_icon_detail")
        if detail_link and not song_id:
            song_id = extract_id_from_href(detail_link.attrs.get("href", ""), "songId")
        detail_href = extract_bg_album_frame_detail_href(row) or (detail_link.attrs.get("href", "") if detail_link else "")
        title_node = row.find("div", class_name="rank01")
        title = title_node.text() if title_node else ""
        artist_node = row.find("div", class_name="rank02")
        artists = extract_artists(artist_node) if artist_node else []
        album_node = row.find("div", class_name="rank03")
        album = extract_album(album_node) if album_node else {"albumId": None, "name": ""}
        if not song_id or rank is None:
            continue
        entries.append(
            {
                "songId": song_id,
                "title": title,
                "artists": artists,
                "album": album,
                "year": year,
                "rank": rank,
                "sourceUrls": {
                    "chart": chart_page_url(year),
                    "detail": urljoin(BASE_URL, detail_href) if detail_href else detail_url(song_id),
                },
            }
        )
    return sorted(entries, key=lambda item: item["rank"])


def extract_bg_album_frame_detail_href(row: Node) -> str | None:
    for link in row.find_all("a"):
        href = link.attrs.get("href", "")
        if "/song/detail.htm" not in href:
            continue
        if link.find("span", class_name="bg_album_frame"):
            return href
    return None


def extract_artists(node: Node) -> list[dict[str, str]]:
    people: list[dict[str, str]] = []
    for link in node.find_all("a"):
        href = link.attrs.get("href", "")
        artist_id = extract_id_from_href(href, "artistId", r"goArtistDetail\('?(\d+)'?\)")
        people.append({"artistId": artist_id or "", "name": link.text()})
    return unique_people(people)


def extract_album(node: Node) -> dict[str, str | None]:
    link = node.find("a")
    if not link:
        return {"albumId": None, "name": node.text()}
    href = link.attrs.get("href", "")
    album_id = extract_id_from_href(href, "albumId", r"goAlbumDetail\('?(\d+)'?\)")
    return {"albumId": album_id, "name": link.text()}


def parse_song_detail(html: str, song_id: str) -> dict[str, Any]:
    root = parse_html(html)
    song_name = root.find("div", class_name="song_name")
    meta = parse_meta(root.find("dl", class_name="list"))
    lyrics_node = root.find("div", id_="d_video_summary")
    like_node = root.find(id_="d_like_count")
    artists = extract_detail_artists(root)
    album_name = meta.get("앨범", "")
    album_id = extract_album_id_from_detail(root)
    return {
        "songId": song_id,
        "title": clean_song_name(song_name.text()) if song_name else "",
        "artists": artists,
        "album": {"albumId": album_id, "name": album_name},
        "releaseDate": meta.get("발매일"),
        "genres": split_genres(meta.get("장르", "")),
        "flac": meta.get("FLAC"),
        "likeCount": parse_int(like_node.text() if like_node else ""),
        "lyrics": lyrics_node.text(separator="") if lyrics_node else "",
        "sourceUrls": {"detail": detail_url(song_id)},
    }


def clean_song_name(value: str) -> str:
    return normalize_text(re.sub(r"^곡명\s*", "", value))


def parse_meta(dl: Node | None) -> dict[str, str]:
    if dl is None:
        return {}
    result: dict[str, str] = {}
    current_key: str | None = None
    for child in dl.children:
        if not isinstance(child, Node):
            continue
        if child.tag == "dt":
            current_key = child.text()
        elif child.tag == "dd" and current_key:
            result[current_key] = child.text()
            current_key = None
    return result


def split_genres(value: str) -> list[str]:
    return [genre.strip() for genre in value.split(",") if genre.strip()]


def parse_int(value: str) -> int:
    digits = re.sub(r"\D+", "", value)
    return int(digits) if digits else 0


def extract_detail_artists(root: Node) -> list[dict[str, str]]:
    section = root.find("div", class_name="section_info") or root
    artists: list[dict[str, str]] = []
    for link in section.find_all("a", class_name="artist_name"):
        href = link.attrs.get("href", "")
        artist_id = extract_id_from_href(href, "artistId", r"goArtistDetail\('?(\d+)'?\)")
        name_span = link.find("span")
        name = name_span.text() if name_span else link.text()
        artists.append({"artistId": artist_id or "", "name": name})
    return unique_people(artists)


def extract_album_id_from_detail(root: Node) -> str | None:
    dl = root.find("dl", class_name="list")
    if not dl:
        return None
    for link in dl.find_all("a"):
        href = link.attrs.get("href", "")
        album_id = extract_id_from_href(href, "albumId", r"goAlbumDetail\('?(\d+)'?\)")
        if album_id:
            return album_id
    return None


def merge_chart_entry(songs: dict[str, dict[str, Any]], chart_entry: dict[str, Any], detail: dict[str, Any]) -> None:
    song_id = chart_entry["songId"]
    existing = songs.get(song_id)
    merged = {
        "songId": song_id,
        "title": detail.get("title") or chart_entry.get("title", ""),
        "artists": detail.get("artists") or chart_entry.get("artists", []),
        "album": detail.get("album") or chart_entry.get("album", {"albumId": None, "name": ""}),
        "releaseDate": detail.get("releaseDate"),
        "genres": detail.get("genres", []),
        "flac": detail.get("flac"),
        "likeCount": detail.get("likeCount", 0),
        "lyrics": detail.get("lyrics", ""),
        "errors": detail.get("errors", []),
        "chartAppearances": [],
        "sourceUrls": {
            "chart": chart_entry.get("sourceUrls", {}).get("chart"),
            "detail": detail.get("sourceUrls", {}).get("detail") or chart_entry.get("sourceUrls", {}).get("detail") or detail_url(song_id),
        },
    }
    if not merged["errors"]:
        merged.pop("errors")
    if existing:
        merged = {**existing, **{key: value for key, value in merged.items() if value not in (None, "", [])}}
        merged["chartAppearances"] = existing.get("chartAppearances", [])
        merged["sourceUrls"] = {
            "chart": existing.get("sourceUrls", {}).get("chart") or chart_entry.get("sourceUrls", {}).get("chart"),
            "detail": detail.get("sourceUrls", {}).get("detail") or chart_entry.get("sourceUrls", {}).get("detail") or detail_url(song_id),
        }
        if detail.get("errors"):
            merged["errors"] = existing.get("errors", []) + [
                error for error in detail.get("errors", []) if error not in existing.get("errors", [])
            ]
        else:
            merged.pop("errors", None)
    appearance = {"year": chart_entry["year"], "rank": chart_entry["rank"]}
    if appearance not in merged["chartAppearances"]:
        merged["chartAppearances"].append(appearance)
        merged["chartAppearances"].sort(key=lambda item: (item["year"], item["rank"]))
    songs[song_id] = merged


def fetch_text(url: str, referer: str, ajax: bool = False, timeout: float = 20.0, retries: int = 3, sleep: float = 1.0) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        "Referer": referer,
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(sleep * attempt)
    status = last_error.code if isinstance(last_error, HTTPError) else None
    raise FetchError(url, str(last_error), status=status) from last_error


Fetcher = Callable[..., str]


def polite_sleep(base_sleep: float, jitter: float = 0.0) -> None:
    delay = base_sleep + (random.uniform(0, jitter) if jitter > 0 else 0)
    if delay > 0:
        time.sleep(delay)


def collect_year(year: int, sleep: float, timeout: float, retries: int, fetcher: Fetcher = fetch_text) -> list[dict[str, Any]]:
    html = fetcher(
        chart_ajax_url(year),
        referer=chart_page_url(year),
        ajax=True,
        timeout=timeout,
        retries=retries,
        sleep=sleep,
    )
    return parse_chart_entries(html, year)


def collect_songs(
    start_year: int,
    end_year: int,
    sleep: float,
    timeout: float,
    retries: int,
    checkpoint: Path | None = None,
    error_log: Path | None = None,
    progress_state: Path | None = None,
    resume: bool = True,
    jitter: float = 0.0,
    block_cooldown: float = 300.0,
    block_retries: int = 1,
    fetcher: Fetcher = fetch_text,
) -> dict[str, dict[str, Any]]:
    songs = load_jsonl_songs(checkpoint) if resume and checkpoint and checkpoint.exists() else {}
    detail_cache: dict[str, dict[str, Any]] = {
        song_id: song
        for song_id, song in songs.items()
        if has_successful_detail(song)
    }
    for year in range(start_year, end_year + 1):
        try:
            entries = collect_year(year, sleep=sleep, timeout=timeout, retries=retries, fetcher=fetcher)
        except FetchError as exc:
            log_error(error_log, {"type": "chart", "year": year, "url": exc.url, "status": exc.status, "message": exc.message})
            print(f"{year}: chart fetch failed ({exc.message})", file=sys.stderr)
            continue
        print(f"{year}: parsed {len(entries)} chart rows", file=sys.stderr)
        for entry in entries:
            song_id = entry["songId"]
            save_progress_state(progress_state, entry)
            if song_id not in detail_cache:
                polite_sleep(sleep, jitter)
                try:
                    detail_html = fetch_detail_with_block_retry(
                        entry,
                        timeout=timeout,
                        retries=retries,
                        sleep=sleep,
                        jitter=jitter,
                        block_cooldown=block_cooldown,
                        block_retries=block_retries,
                        checkpoint=checkpoint,
                        progress_state=progress_state,
                        songs=songs,
                        fetcher=fetcher,
                    )
                    detail_cache[song_id] = parse_song_detail(detail_html, song_id)
                except FetchError as exc:
                    error = {
                        "type": "detail",
                        "year": entry["year"],
                        "rank": entry["rank"],
                        "songId": song_id,
                        "url": exc.url,
                        "status": exc.status,
                        "message": exc.message,
                    }
                    log_error(error_log, error)
                    detail_cache[song_id] = detail_from_chart_error(entry, error)
                    print(f"{year} #{entry['rank']} {song_id}: detail fetch failed ({exc.message})", file=sys.stderr)
            merge_chart_entry(songs, entry, detail_cache[song_id])
            if checkpoint:
                write_jsonl(songs, checkpoint)
        polite_sleep(sleep, jitter)
    return songs


def fetch_detail_with_block_retry(
    entry: dict[str, Any],
    timeout: float,
    retries: int,
    sleep: float,
    jitter: float,
    block_cooldown: float,
    block_retries: int,
    checkpoint: Path | None,
    progress_state: Path | None,
    songs: dict[str, dict[str, Any]],
    fetcher: Fetcher,
) -> str:
    url = entry["sourceUrls"].get("detail") or detail_url(entry["songId"])
    attempts = 0
    while True:
        try:
            return fetcher(
                url,
                referer=entry["sourceUrls"]["chart"],
                timeout=timeout,
                retries=retries,
                sleep=sleep,
            )
        except FetchError as exc:
            if exc.status not in {403, 406, 429} or attempts >= block_retries:
                raise
            attempts += 1
            save_progress_state(progress_state, entry, blocked_error=exc)
            if checkpoint:
                write_jsonl(songs, checkpoint)
            print(
                f"{entry['year']} #{entry['rank']} {entry['songId']}: blocked ({exc.message}); "
                f"cooling down {block_cooldown:g}s before retry {attempts}/{block_retries}",
                file=sys.stderr,
            )
            polite_sleep(block_cooldown, jitter)


def detail_from_chart_error(chart_entry: dict[str, Any], error: dict[str, Any]) -> dict[str, Any]:
    return {
        "songId": chart_entry["songId"],
        "title": chart_entry.get("title", ""),
        "artists": chart_entry.get("artists", []),
        "album": chart_entry.get("album", {"albumId": None, "name": ""}),
        "releaseDate": None,
        "genres": [],
        "flac": None,
        "likeCount": 0,
        "lyrics": "",
        "sourceUrls": {"detail": detail_url(chart_entry["songId"])},
        "errors": [error],
    }


def has_successful_detail(song: dict[str, Any]) -> bool:
    if song.get("errors"):
        return False
    return bool(song.get("releaseDate") or song.get("genres") or song.get("lyrics"))


def log_error(error_log: Path | None, error: dict[str, Any]) -> None:
    if not error_log:
        return
    error_log.parent.mkdir(parents=True, exist_ok=True)
    with error_log.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(error, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl_songs(path: Path) -> dict[str, dict[str, Any]]:
    songs: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            song = json.loads(line)
            songs[str(song["songId"])] = song
    return songs


def save_progress_state(progress_state: Path | None, entry: dict[str, Any], blocked_error: FetchError | None = None) -> None:
    if not progress_state:
        return
    progress_state.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "updatedAt": dt.datetime.now(dt.UTC).isoformat(),
        "current": {
            "year": entry["year"],
            "rank": entry["rank"],
            "songId": entry["songId"],
        },
    }
    if blocked_error:
        state["blockedError"] = {
            "url": blocked_error.url,
            "status": blocked_error.status,
            "message": blocked_error.message,
        }
    temp_state = progress_state.with_suffix(progress_state.suffix + ".tmp")
    temp_state.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    temp_state.replace(progress_state)


def load_progress_state(progress_state: Path) -> dict[str, Any]:
    return json.loads(progress_state.read_text(encoding="utf-8"))


def backup_existing_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{timestamp}")
    shutil.copy2(path, backup)
    return backup


def write_jsonl(songs: dict[str, dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        songs.values(),
        key=lambda song: (
            song.get("chartAppearances", [{"year": 9999, "rank": 9999}])[0]["year"],
            song.get("chartAppearances", [{"year": 9999, "rank": 9999}])[0]["rank"],
            song["songId"],
        ),
    )
    temp_output = output.with_suffix(output.suffix + ".tmp")
    with temp_output.open("w", encoding="utf-8", newline="\n") as file:
        for song in ordered:
            file.write(json.dumps(song, ensure_ascii=False, sort_keys=True) + "\n")
    temp_output.replace(output)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Melon yearly K-pop chart metadata as song-centric JSONL.")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output", type=Path, default=Path("data/melon_kpop_2000_2025.jsonl"))
    parser.add_argument("--checkpoint", type=Path, default=None, help="Partial JSONL path for resume/checkpoint writes.")
    parser.add_argument("--error-log", type=Path, default=None, help="JSONL path for failed chart/detail requests.")
    parser.add_argument("--progress-state", type=Path, default=None, help="JSON file containing the latest year/rank/song checkpoint.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore an existing checkpoint file.")
    parser.add_argument("--sleep", type=float, default=2.0, help="Delay between requests in seconds.")
    parser.add_argument("--jitter", type=float, default=1.5, help="Random extra delay added to request waits.")
    parser.add_argument("--block-cooldown", type=float, default=300.0, help="Cooldown after 403/406/429 before retrying the same song.")
    parser.add_argument("--block-retries", type=int, default=1, help="Same-song retries after a blocking response.")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.start_year > args.end_year:
        raise SystemExit("--start-year must be less than or equal to --end-year")
    checkpoint = args.checkpoint or args.output.with_suffix(args.output.suffix + ".partial")
    error_log = args.error_log or args.output.with_suffix(args.output.suffix + ".errors")
    progress_state = args.progress_state or args.output.with_suffix(args.output.suffix + ".state.json")
    songs = collect_songs(
        start_year=args.start_year,
        end_year=args.end_year,
        sleep=args.sleep,
        timeout=args.timeout,
        retries=args.retries,
        checkpoint=checkpoint,
        error_log=error_log,
        progress_state=progress_state,
        resume=not args.no_resume,
        jitter=args.jitter,
        block_cooldown=args.block_cooldown,
        block_retries=args.block_retries,
    )
    backup = backup_existing_file(args.output)
    write_jsonl(songs, args.output)
    if backup:
        print(f"Backed up previous output to {backup}", file=sys.stderr)
    print(f"Checkpoint saved to {checkpoint}", file=sys.stderr)
    print(f"Error log saved to {error_log}", file=sys.stderr)
    print(f"Progress state saved to {progress_state}", file=sys.stderr)
    print(f"Wrote {len(songs)} songs to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
