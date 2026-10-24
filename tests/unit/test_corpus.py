"""Corpus acquisition: polite fetcher, source list validation, crawl strategies (no network)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest
import yaml

from reglens.config import PROJECT_ROOT
from reglens.corpus.crawl import Crawler, read_manifest, write_manifest
from reglens.corpus.fetch import FetchError, PoliteFetcher
from reglens.corpus.sources import SourceDoc, SourceList, load_sources

Handler = Callable[[httpx.Request], httpx.Response]
PDF_BYTES = b"%PDF-1.7\n" + b"x" * 2_000


def make_fetcher(
    tmp_path: Path, handler: Handler, sleeps: list[float] | None = None
) -> PoliteFetcher:
    record = sleeps if sleeps is not None else []
    return PoliteFetcher(
        cache_dir=tmp_path / "cache",
        user_agent="RegLens-test",
        delay_seconds=1.0,
        transport=httpx.MockTransport(handler),
        sleep=record.append,
    )


def site(pages: dict[str, tuple[int, bytes]], robots: str = "") -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        status, body = pages.get(url, (404, b"missing"))
        content_type = "application/pdf" if body.startswith(b"%PDF") else "text/html"
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    return handler


# ---------------------------------------------------------------- fetcher
def test_fetch_caches_and_never_refetches(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"<html>hi</html>")

    fetcher = make_fetcher(tmp_path, handler)
    first = fetcher.get("https://reg.example/a")
    second = fetcher.get("https://reg.example/a")
    assert not first.from_cache
    assert second.from_cache
    assert second.content == b"<html>hi</html>"
    assert second.sha256 == first.sha256
    assert calls.count("https://reg.example/a") == 1


def test_fetch_respects_robots_txt(tmp_path: Path) -> None:
    handler = site(
        {"https://reg.example/ok": (200, b"fine")}, robots="User-agent: *\nDisallow: /private"
    )
    fetcher = make_fetcher(tmp_path, handler)
    assert fetcher.get("https://reg.example/ok").content == b"fine"
    with pytest.raises(FetchError, match=r"robots\.txt"):
        fetcher.get("https://reg.example/private/doc")


def test_fetch_retries_server_errors_with_backoff(tmp_path: Path) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] < 3 else httpx.Response(200, content=b"ok")

    sleeps: list[float] = []
    fetcher = make_fetcher(tmp_path, handler, sleeps)
    assert fetcher.get("https://reg.example/flaky").content == b"ok"
    assert attempts["n"] == 3
    assert 1.0 in sleeps and 2.0 in sleeps  # exponential backoff


def test_fetch_gives_up_fast_on_not_found(tmp_path: Path) -> None:
    fetcher = make_fetcher(tmp_path, site({}))
    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.get("https://reg.example/nothing")


def test_fetch_waits_between_requests_to_same_host(tmp_path: Path) -> None:
    pages = {f"https://reg.example/{i}": (200, b"x") for i in range(3)}
    sleeps: list[float] = []
    fetcher = make_fetcher(tmp_path, site(pages), sleeps)
    for i in range(3):
        fetcher.get(f"https://reg.example/{i}")
    assert len([s for s in sleeps if 0 < s <= 1.0]) >= 2


def test_fetch_network_error_retries_then_fails(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    fetcher = make_fetcher(tmp_path, handler)
    with pytest.raises(FetchError, match="ConnectError"):
        fetcher.get("https://reg.example/x")
    fetcher.close()


# ---------------------------------------------------------------- sources
def test_real_source_list_is_valid() -> None:
    sources = load_sources(PROJECT_ROOT / "configs" / "sources.yaml")
    assert {d.regulator for d in sources.documents} == {"RBI", "SEBI", "FCA", "PRA"}
    assert sources.by_id("pra-ss2-21").snapshots[0].label == date(2021, 3, 29)
    with pytest.raises(KeyError):
        sources.by_id("nope")


def doc(**overrides: object) -> SourceDoc:
    base: dict[str, object] = {
        "id": "x-doc",
        "regulator": "RBI",
        "kind": "html",
        "doc_type": "circular",
        "title": "X",
        "topics": ["kyc"],
        "applies_to": ["commercial_banks"],
        "url": "https://reg.example/x",
    }
    return SourceDoc.model_validate(base | overrides)


def test_source_validation_rejects_bad_entries() -> None:
    with pytest.raises(ValueError, match="missing"):
        doc(url=None)
    with pytest.raises(ValueError, match="missing"):
        doc(kind="pra_part", part="outsourcing")  # no as_of dates
    with pytest.raises(ValueError, match="duplicate"):
        SourceList(documents=[doc(), doc()])


def test_load_sources_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({"documents": [doc().model_dump(mode="json")]}))
    assert load_sources(path).documents[0].id == "x-doc"


# ---------------------------------------------------------------- crawl strategies
def test_crawl_html_with_archived_snapshot(tmp_path: Path) -> None:
    pages = {
        "https://reg.example/x": (200, b"<html>current</html>"),
        "https://archive.example/x-2024": (200, PDF_BYTES),
    }
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    snapshot = {"label": "2024-01-31", "url": "https://archive.example/x-2024"}
    versions = crawler.crawl(doc(snapshots=[snapshot]))
    assert [v.version for v in versions] == ["current", "v2024-01-31"]
    assert versions[1].parts[0].path.endswith(".pdf")  # format detected from content
    assert (tmp_path / "raw" / versions[0].parts[0].path).read_bytes() == b"<html>current</html>"


def test_crawl_pdf_rejects_html_error_page(tmp_path: Path) -> None:
    pages = {"https://reg.example/x.pdf": (200, b"<html>bot check</html>")}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    with pytest.raises(FetchError, match="expected a PDF"):
        crawler.crawl(doc(kind="pdf", url="https://reg.example/x.pdf"))


def test_crawl_sebi_circular_follows_embedded_pdf(tmp_path: Path) -> None:
    pdf_url = "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/123.pdf"
    page = f"<iframe src='../../../web/?file={pdf_url}'></iframe>".encode()
    pages = {"https://reg.example/c.html": (200, page), pdf_url: (200, PDF_BYTES)}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    versions = crawler.crawl(doc(kind="sebi_circular", url="https://reg.example/c.html"))
    assert versions[0].parts[0].url == pdf_url


def test_crawl_sebi_circular_follows_site_relative_pdf(tmp_path: Path) -> None:
    pdf_url = "https://www.sebi.gov.in/sebi_data/attachdocs/1323947579579.PDF"
    page = b"<iframe src='../../../web/?file=/sebi_data/attachdocs/1323947579579.PDF'></iframe>"
    pages = {"https://reg.example/c.html": (200, page), pdf_url: (200, PDF_BYTES)}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    versions = crawler.crawl(doc(kind="sebi_circular", url="https://reg.example/c.html"))
    assert versions[0].parts[0].url == pdf_url


def test_crawl_sebi_circular_without_pdf_keeps_html(tmp_path: Path) -> None:
    pages = {"https://reg.example/c.html": (200, b"<html><p>1. Old circular</p></html>")}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    versions = crawler.crawl(doc(kind="sebi_circular", url="https://reg.example/c.html"))
    assert versions[0].parts[0].path.endswith(".html")


def test_crawl_fca_chapter_probes_sections_until_empty(tmp_path: Path) -> None:
    base = "https://handbook.fca.org.uk/handbook/sysc8/sysc8s"
    card = b"<p-card>provision</p-card>"
    pages = {f"{base}1": (200, card), f"{base}2": (200, b"no cards"), f"{base}3": (200, card)}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    versions = crawler.crawl(doc(regulator="FCA", kind="fca_chapter", chapter="sysc8", url=None))
    assert [p.name for p in versions[0].parts] == ["s01", "s03"]  # a gap is tolerated


def test_crawl_fca_chapter_with_no_sections_fails(tmp_path: Path) -> None:
    crawler = Crawler(make_fetcher(tmp_path, site({})), tmp_path / "raw")
    with pytest.raises(FetchError, match="no FCA sections"):
        crawler.crawl(doc(regulator="FCA", kind="fca_chapter", chapter="zzz9", url=None))


def test_crawl_pra_part_snapshots_each_date(tmp_path: Path) -> None:
    base = "https://www.prarulebook.co.uk/pra-rules/outsourcing"
    pages = {f"{base}/24-10-2026": (200, b"now"), f"{base}/30-06-2025": (200, b"before")}
    crawler = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw")
    dates = ["2026-10-24", "2025-06-30"]
    pra = doc(regulator="PRA", kind="pra_part", part="outsourcing", url=None, as_of=dates)
    versions = crawler.crawl(pra)
    assert [v.version for v in versions] == ["asof2026-10-24", "asof2025-06-30"]
    assert {v.source for v in versions} == {"pra_point_in_time"}


def test_manifest_round_trip(tmp_path: Path) -> None:
    pages = {"https://reg.example/x": (200, b"<html>x</html>")}
    versions = Crawler(make_fetcher(tmp_path, site(pages)), tmp_path / "raw").crawl(doc())
    path = tmp_path / "raw" / "manifest.jsonl"
    write_manifest(versions, path)
    assert read_manifest(path) == versions
