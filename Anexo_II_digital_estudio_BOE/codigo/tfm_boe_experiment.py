#!/usr/bin/env python3
"""Estudio exploratorio reproducible para el TFM sobre PLN jurídico-administrativo.

El script realiza cuatro operaciones:
1) construye una muestra temporal de disposiciones BOE-A mediante la API oficial del BOE;
2) mide su longitud con cuatro tokenizadores, sin descargar pesos de modelos;
3) mide la fragmentación de un listado predefinido de términos jurídicos;
4) entrena, de forma opcional, un baseline TF-IDF + LinearSVC con partición temporal.

Los resultados principales se guardan en CSV/PNG y en un ZIP que excluye los textos
completos de las disposiciones. El corpus local se conserva aparte para trazabilidad.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import random
import re
import shutil
import sys
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import urlparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from huggingface_hub import snapshot_download
from lxml import etree
from requests.adapters import HTTPAdapter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from tqdm import tqdm
from transformers import AutoTokenizer
from urllib3.util.retry import Retry

SCRIPT_VERSION = "1.0.0"
BOE_API = "https://www.boe.es/datosabiertos/api/boe/sumario/{date}"
DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025)
DEFAULT_ANCHORS = ((1, 15), (2, 15), (4, 15), (5, 15), (7, 15), (8, 15), (10, 15), (11, 15))
DEFAULT_MODELS: dict[str, str] = {
    "BETO": "dccuchile/bert-base-spanish-wwm-cased",
    "RoBERTalex": "PlanTL-GOB-ES/RoBERTalex",
    "MEL": "IIC/MEL",
    "MrBERT-legal": "BSC-LT/MrBERT-legal",
}
TOKENIZER_PATTERNS = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.txt",
    "vocab.json",
    "merges.txt",
    "sentencepiece.bpe.model",
    "spiece.model",
    "*.model",
]
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[-'][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*")
SPACE_RE = re.compile(r"\s+")
DIRECT_METADATA_RE = re.compile(
    r"(?im)^\s*(?:bolet[ií]n oficial del estado|núm\.?\s*\d+|sec\.?\s*[ivx]+|"
    r"departamento|ministerio|identificador|boe-[ab]-\d{4}-\d+)\s*[:\-]?.*$"
)


@dataclass(frozen=True)
class BOEItem:
    issue_date: str
    year: int
    diary_number: str
    section_code: str
    section_name: str
    department_code: str
    department_name: str
    epigraph: str
    identifier: str
    title: str
    url_xml: str
    url_html: str
    url_pdf: str


@dataclass
class FetchResult:
    item: BOEItem
    text: str
    source_format: str
    sha256: str
    char_count: int
    word_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Muestra BOE + análisis de tokenización + baseline TF-IDF/SVM para el TFM."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("resultados_boe"),
        help="Directorio de salida (por defecto: resultados_boe).",
    )
    parser.add_argument(
        "--terms-file",
        type=Path,
        default=Path(__file__).with_name("terminos_juridicos_125.csv"),
        help="CSV con columnas categoria,termino.",
    )
    parser.add_argument("--target-docs", type=int, default=400, help="Número final de documentos válidos.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=list(DEFAULT_YEARS),
        help="Años que forman la muestra; el último se reserva como test temporal del SVM.",
    )
    parser.add_argument(
        "--docs-per-issue",
        type=int,
        default=10,
        help="Asignación inicial máxima por fecha de publicación.",
    )
    parser.add_argument("--seed", type=int, default=20260730, help="Semilla reproducible.")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.20,
        help="Pausa mínima entre peticiones al BOE, en segundos.",
    )
    parser.add_argument(
        "--max-search-days",
        type=int,
        default=7,
        help="Días posteriores al ancla en los que buscar el siguiente BOE disponible.",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=200,
        help="Longitud mínima para considerar válida una extracción.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=1_500_000,
        help="Límite de seguridad; documentos mayores se excluyen y quedan registrados.",
    )
    parser.add_argument(
        "--svm-target",
        choices=("section", "department"),
        default="section",
        help="Variable del baseline: sección (recomendado) o departamento.",
    )
    parser.add_argument("--skip-svm", action="store_true", help="Omite el baseline TF-IDF + SVM.")
    parser.add_argument(
        "--no-download-tokenizers",
        action="store_true",
        help="Exige que los tokenizadores ya estén en la caché local de Hugging Face.",
    )
    parser.add_argument(
        "--user-agent",
        default="TFM-PLN-juridico-administrativo/1.0 (investigacion academica)",
        help="User-Agent enviado al BOE.",
    )
    args = parser.parse_args()
    if not 300 <= args.target_docs <= 500:
        parser.error("--target-docs debe estar entre 300 y 500, conforme al diseño del estudio.")
    if len(set(args.years)) < 3:
        parser.error("La muestra debe cubrir al menos tres años.")
    if args.docs_per_issue < 1:
        parser.error("--docs-per-issue debe ser positivo.")
    return args


def setup_logging(output_dir: Path) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tfm_boe")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(output_dir / "ejecucion.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


def make_session(user_agent: str) -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session = requests.Session()
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session


def local_name(element: etree._Element) -> str:
    try:
        return etree.QName(element).localname
    except Exception:
        tag = str(element.tag)
        return tag.split("}")[-1]


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u00ad", "").replace("\u200b", "")
    return SPACE_RE.sub(" ", value).strip()


def clean_for_classifier(text: str, title: str = "") -> str:
    """Depuración conservadora para el baseline.

    El cuerpo ya se extrae sin metadatos del sumario. Se eliminan posibles líneas de
    cabecera reinyectadas en el HTML/XML y una repetición literal del título.
    No se eliminan citas normativas ni terminología jurídica, pues son contenido legítimo.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = DIRECT_METADATA_RE.sub(" ", text)
    if title:
        title_norm = normalized_text(title)
        if title_norm:
            text = re.sub(re.escape(title_norm), " ", text, flags=re.IGNORECASE)
    return normalized_text(text)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_with_cache(
    session: requests.Session,
    url: str,
    cache_path: Path,
    *,
    accept: str | None = None,
    delay: float = 0.2,
    timeout: int = 60,
) -> bytes:
    if cache_path.exists():
        return cache_path.read_bytes()
    headers = {"Accept": accept} if accept else {}
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.content
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(payload)
    if delay > 0:
        time.sleep(delay)
    return payload


def descendants(element: etree._Element, name: str) -> list[etree._Element]:
    return element.xpath(f".//*[local-name()='{name}']")


def first_child_text(element: etree._Element, name: str) -> str:
    matches = element.xpath(f"./*[local-name()='{name}']")
    if not matches:
        return ""
    return normalized_text(" ".join(matches[0].itertext()))


def parse_issue_xml(payload: bytes, issue_date: str) -> list[BOEItem]:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(payload, parser=parser)
    items: list[BOEItem] = []
    for diary in root.xpath(".//*[local-name()='diario']"):
        diary_number = diary.get("numero", "")
        for section in diary.xpath("./*[local-name()='seccion']"):
            section_code = section.get("codigo", "")
            section_name = section.get("nombre", "")
            for department in section.xpath("./*[local-name()='departamento']"):
                dep_code = department.get("codigo", "")
                dep_name = department.get("nombre", "")
                for item in department.xpath(".//*[local-name()='item']"):
                    identifier = first_child_text(item, "identificador")
                    if not identifier.startswith("BOE-A-"):
                        continue
                    parent = item.getparent()
                    epigraph = parent.get("nombre", "") if parent is not None and local_name(parent) == "epigrafe" else ""
                    url_pdf_node = item.xpath("./*[local-name()='url_pdf']")
                    url_pdf = normalized_text(" ".join(url_pdf_node[0].itertext())) if url_pdf_node else ""
                    items.append(
                        BOEItem(
                            issue_date=issue_date,
                            year=int(issue_date[:4]),
                            diary_number=diary_number,
                            section_code=section_code,
                            section_name=section_name,
                            department_code=dep_code,
                            department_name=dep_name,
                            epigraph=epigraph,
                            identifier=identifier,
                            title=first_child_text(item, "titulo"),
                            url_xml=first_child_text(item, "url_xml"),
                            url_html=first_child_text(item, "url_html"),
                            url_pdf=url_pdf,
                        )
                    )
    # El XML puede contener diarios extraordinarios; se elimina cualquier duplicado por identificador.
    unique: dict[str, BOEItem] = {}
    for item in items:
        unique.setdefault(item.identifier, item)
    return list(unique.values())


def resolve_issue(
    session: requests.Session,
    anchor: date,
    cache_dir: Path,
    delay: float,
    max_search_days: int,
    logger: logging.Logger,
) -> tuple[str, list[BOEItem]] | None:
    for offset in range(max_search_days + 1):
        current = anchor + timedelta(days=offset)
        key = current.strftime("%Y%m%d")
        url = BOE_API.format(date=key)
        cache_path = cache_dir / "sumarios" / f"{key}.xml"
        try:
            payload = request_with_cache(
                session, url, cache_path, accept="application/xml", delay=delay
            )
            items = parse_issue_xml(payload, key)
            if items:
                return key, items
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                continue
            logger.warning("Fallo al consultar sumario %s: %s", key, exc)
        except Exception as exc:
            logger.warning("No se pudo procesar el sumario %s: %s", key, exc)
    return None


def build_anchors(years: Sequence[int]) -> list[date]:
    anchors = [date(year, month, day) for year in sorted(set(years)) for month, day in DEFAULT_ANCHORS]
    return anchors


def round_robin_by_section(items: Sequence[BOEItem], rng: random.Random) -> list[BOEItem]:
    groups: dict[str, list[BOEItem]] = defaultdict(list)
    for item in items:
        groups[item.section_code or "SIN_SECCION"].append(item)
    for values in groups.values():
        rng.shuffle(values)
    ordered: list[BOEItem] = []
    keys = sorted(groups)
    while any(groups.values()):
        for key in keys:
            if groups[key]:
                ordered.append(groups[key].pop())
    return ordered


def choose_candidates(
    issues: dict[str, list[BOEItem]],
    target: int,
    docs_per_issue: int,
    seed: int,
) -> list[BOEItem]:
    rng = random.Random(seed)
    selected: list[BOEItem] = []
    reserve: list[BOEItem] = []
    for issue_date in sorted(issues):
        ordered = round_robin_by_section(issues[issue_date], rng)
        selected.extend(ordered[:docs_per_issue])
        reserve.extend(ordered[docs_per_issue:])
    if len(selected) > target:
        # Mantiene equilibrio temporal mediante recorrido circular por fecha.
        by_date: dict[str, list[BOEItem]] = defaultdict(list)
        for item in selected:
            by_date[item.issue_date].append(item)
        balanced: list[BOEItem] = []
        dates = sorted(by_date)
        while len(balanced) < target and any(by_date.values()):
            for d in dates:
                if by_date[d] and len(balanced) < target:
                    balanced.append(by_date[d].pop())
        selected = balanced
    rng.shuffle(reserve)
    # Se añaden reservas para sustituir posibles fallos de extracción.
    return selected + reserve


def extract_xml_text(payload: bytes) -> str:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(payload, parser=parser)
    candidates: list[str] = []
    for node in root.iter():
        lname = local_name(node).lower()
        if lname in {"texto", "texto_original", "texto_consolidado", "texto_disposicion"}:
            value = normalized_text(" ".join(node.itertext()))
            if value:
                candidates.append(value)
    if not candidates:
        # Algunos documentos antiguos usan nodos p dentro de una zona de texto sin nombre estable.
        for node in root.xpath(".//*[local-name()='p']"):
            value = normalized_text(" ".join(node.itertext()))
            if value:
                candidates.append(value)
        if candidates:
            return normalized_text(" ".join(candidates))
        return ""
    return max(candidates, key=len)


def extract_html_text(payload: bytes) -> str:
    soup = BeautifulSoup(payload, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]):
        tag.decompose()
    selectors = (
        "#textoxslt",
        "#texto",
        ".texto",
        ".documento",
        "article",
        "main",
    )
    candidates: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            value = normalized_text(node.get_text(" ", strip=True))
            if value:
                candidates.append(value)
    if candidates:
        return max(candidates, key=len)
    return normalized_text(soup.get_text(" ", strip=True))


def safe_cache_name(identifier: str, suffix: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier)
    return f"{safe}.{suffix}"


def fetch_document(
    session: requests.Session,
    item: BOEItem,
    cache_dir: Path,
    delay: float,
    min_chars: int,
    max_chars: int,
) -> FetchResult:
    errors: list[str] = []
    if item.url_xml:
        try:
            payload = request_with_cache(
                session,
                item.url_xml,
                cache_dir / "documentos_xml" / safe_cache_name(item.identifier, "xml"),
                accept="application/xml",
                delay=delay,
            )
            text = extract_xml_text(payload)
            text = clean_for_classifier(text, item.title)
            if min_chars <= len(text) <= max_chars:
                return FetchResult(item, text, "xml", sha256_text(text), len(text), len(WORD_RE.findall(text)))
            errors.append(f"XML con {len(text)} caracteres")
        except Exception as exc:
            errors.append(f"XML: {exc}")
    if item.url_html:
        try:
            payload = request_with_cache(
                session,
                item.url_html,
                cache_dir / "documentos_html" / safe_cache_name(item.identifier, "html"),
                accept="text/html",
                delay=delay,
            )
            text = extract_html_text(payload)
            text = clean_for_classifier(text, item.title)
            if min_chars <= len(text) <= max_chars:
                return FetchResult(item, text, "html", sha256_text(text), len(text), len(WORD_RE.findall(text)))
            errors.append(f"HTML con {len(text)} caracteres")
        except Exception as exc:
            errors.append(f"HTML: {exc}")
    raise ValueError("; ".join(errors) if errors else "sin URL XML/HTML")


def collect_sample(args: argparse.Namespace, logger: logging.Logger) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir: Path = args.output_dir
    cache_dir = output_dir / "cache"
    session = make_session(args.user_agent)
    issues: dict[str, list[BOEItem]] = {}
    seen_issue_dates: set[str] = set()

    logger.info("Consultando sumarios en %d años y %d fechas ancla.", len(set(args.years)), len(build_anchors(args.years)))
    for anchor in tqdm(build_anchors(args.years), desc="Sumarios BOE"):
        resolved = resolve_issue(
            session,
            anchor,
            cache_dir,
            args.request_delay,
            args.max_search_days,
            logger,
        )
        if resolved is None:
            logger.warning("No se localizó un BOE con disposiciones desde el ancla %s.", anchor)
            continue
        issue_date, items = resolved
        if issue_date in seen_issue_dates:
            continue
        seen_issue_dates.add(issue_date)
        issues[issue_date] = items

    if len(issues) < 12:
        raise RuntimeError(f"Solo se obtuvieron {len(issues)} fechas distintas; se requieren al menos 12.")

    candidates = choose_candidates(issues, args.target_docs, args.docs_per_issue, args.seed)
    logger.info("Fechas válidas: %d; candidatos con reserva: %d.", len(issues), len(candidates))

    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in tqdm(candidates, desc="Textos BOE"):
        if len(rows) >= args.target_docs:
            break
        if item.identifier in seen_ids:
            continue
        seen_ids.add(item.identifier)
        try:
            fetched = fetch_document(
                session,
                item,
                cache_dir,
                args.request_delay,
                args.min_text_chars,
                args.max_text_chars,
            )
            row = asdict(item)
            row.update(
                {
                    "source_format": fetched.source_format,
                    "sha256_text": fetched.sha256,
                    "char_count": fetched.char_count,
                    "word_count": fetched.word_count,
                    "clean_text": fetched.text,
                }
            )
            rows.append(row)
        except Exception as exc:
            exclusions.append({"identifier": item.identifier, "reason": str(exc)})

    if len(rows) < args.target_docs:
        raise RuntimeError(
            f"Solo se recuperaron {len(rows)} documentos válidos de {args.target_docs}. "
            "Reejecute con más años o más fechas/anclas."
        )

    corpus = pd.DataFrame(rows)
    corpus = corpus.drop_duplicates(subset="identifier").sort_values(["issue_date", "identifier"]).reset_index(drop=True)
    exclusion_df = pd.DataFrame(exclusions, columns=["identifier", "reason"])

    n_years = corpus["year"].nunique()
    n_dates = corpus["issue_date"].nunique()
    if n_years < 3 or n_dates < 12:
        raise RuntimeError(f"Muestra insuficientemente distribuida: {n_years} años, {n_dates} fechas.")

    # Corpus local comprimido. No se incluye en el ZIP para integrar en el TFM.
    corpus.to_csv(output_dir / "corpus_boe_local.csv.gz", index=False, compression="gzip", encoding="utf-8")
    exclusion_df.to_csv(output_dir / "exclusiones_extraccion.csv", index=False, encoding="utf-8-sig")

    metadata_cols = [c for c in corpus.columns if c != "clean_text"]
    corpus[metadata_cols].to_csv(output_dir / "muestra_boe_metadatos.csv", index=False, encoding="utf-8-sig")

    distribution = (
        corpus.groupby(["year", "issue_date", "section_code", "section_name"], dropna=False)
        .size()
        .reset_index(name="n")
    )
    distribution.to_csv(output_dir / "distribucion_muestra.csv", index=False, encoding="utf-8-sig")
    logger.info(
        "Muestra final: n=%d, años=%d, fechas=%d, secciones=%d.",
        len(corpus), n_years, n_dates, corpus["section_code"].nunique()
    )
    return corpus, exclusion_df


def resolve_snapshot_commit(snapshot_path: str | Path) -> str:
    path = Path(snapshot_path).resolve()
    parts = list(path.parts)
    if "snapshots" in parts:
        idx = parts.index("snapshots")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return path.name


def load_tokenizers(args: argparse.Namespace, logger: logging.Logger) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    tokenizers: dict[str, Any] = {}
    provenance: dict[str, dict[str, str]] = {}
    hf_cache = args.output_dir / "hf_cache"
    hf_cache.mkdir(parents=True, exist_ok=True)
    for label, repo_id in DEFAULT_MODELS.items():
        logger.info("Preparando tokenizador %s (%s).", label, repo_id)
        snapshot = snapshot_download(
            repo_id=repo_id,
            allow_patterns=TOKENIZER_PATTERNS,
            cache_dir=hf_cache,
            local_files_only=args.no_download_tokenizers,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot,
            use_fast=True,
            local_files_only=True,
            trust_remote_code=False,
        )
        # Evita advertencias de truncamiento; nunca se trunca en este estudio.
        tokenizer.model_max_length = 10**12
        tokenizers[label] = tokenizer
        provenance[label] = {
            "repo_id": repo_id,
            "snapshot_commit_or_dir": resolve_snapshot_commit(snapshot),
            "tokenizer_class": tokenizer.__class__.__name__,
            "vocab_size": str(getattr(tokenizer, "vocab_size", "")),
        }
    return tokenizers, provenance


def percentile(values: Sequence[int], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q, method="linear"))


def analyse_document_lengths(
    corpus: pd.DataFrame,
    tokenizers: dict[str, Any],
    output_dir: Path,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = corpus[[
        "identifier", "issue_date", "year", "section_code", "section_name",
        "department_name", "char_count", "word_count"
    ]].copy()
    summaries: list[dict[str, Any]] = []

    for label, tokenizer in tokenizers.items():
        lengths: list[int] = []
        for text in tqdm(corpus["clean_text"].tolist(), desc=f"Tokenizando {label}"):
            encoded = tokenizer(
                text,
                add_special_tokens=True,
                truncation=False,
                return_attention_mask=False,
                return_token_type_ids=False,
            )
            lengths.append(len(encoded["input_ids"]))
        detail[f"tokens_{label}"] = lengths
        arr = np.asarray(lengths)
        summaries.append(
            {
                "tokenizer": label,
                "n": int(len(arr)),
                "median": percentile(lengths, 50),
                "p90": percentile(lengths, 90),
                "p95": percentile(lengths, 95),
                "min": int(arr.min()),
                "max": int(arr.max()),
                "pct_gt_512": float((arr > 512).mean() * 100),
                "pct_gt_4096": float((arr > 4096).mean() * 100),
                "pct_gt_8192": float((arr > 8192).mean() * 100),
            }
        )
    summary = pd.DataFrame(summaries)
    detail.to_csv(output_dir / "longitudes_por_documento.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output_dir / "tabla_longitudes_resumen.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    logger.info("Análisis de longitudes completado.")
    return detail, summary


def read_terms(path: Path) -> pd.DataFrame:
    terms = pd.read_csv(path, encoding="utf-8-sig")
    expected = {"categoria", "termino"}
    if not expected.issubset(terms.columns):
        raise ValueError(f"El fichero de términos debe contener {sorted(expected)}.")
    terms = terms[["categoria", "termino"]].dropna().copy()
    terms["termino"] = terms["termino"].map(normalized_text)
    terms = terms[terms["termino"] != ""].drop_duplicates(subset="termino")
    if not 100 <= len(terms) <= 150:
        raise ValueError(f"Se esperaban 100–150 términos; se encontraron {len(terms)}.")
    return terms.reset_index(drop=True)


def analyse_term_fragmentation(
    terms: pd.DataFrame,
    tokenizers: dict[str, Any],
    output_dir: Path,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detail = terms.copy()
    detail["orthographic_words"] = detail["termino"].map(lambda x: max(1, len(WORD_RE.findall(x))))

    long_rows: list[dict[str, Any]] = []
    for label, tokenizer in tokenizers.items():
        token_counts: list[int] = []
        tokens_rendered: list[str] = []
        for term in detail["termino"]:
            encoded = tokenizer(
                term,
                add_special_tokens=False,
                truncation=False,
                return_attention_mask=False,
                return_token_type_ids=False,
            )
            token_ids = encoded["input_ids"]
            tokens = tokenizer.convert_ids_to_tokens(token_ids)
            token_counts.append(len(token_ids))
            tokens_rendered.append(" | ".join(tokens))
        detail[f"subtokens_{label}"] = token_counts
        detail[f"pieces_{label}"] = tokens_rendered
        for idx, row in detail.iterrows():
            n_words = int(row["orthographic_words"])
            n_tokens = int(row[f"subtokens_{label}"])
            long_rows.append(
                {
                    "categoria": row["categoria"],
                    "termino": row["termino"],
                    "tokenizer": label,
                    "orthographic_words": n_words,
                    "subtokens": n_tokens,
                    "excess_subtokens": n_tokens - n_words,
                    "subtokens_per_word": n_tokens / n_words,
                    "fragmented": n_tokens > n_words,
                    "token_pieces": row[f"pieces_{label}"],
                }
            )

    long_df = pd.DataFrame(long_rows)
    overall = (
        long_df.groupby("tokenizer", sort=False)
        .agg(
            n_terms=("termino", "size"),
            mean_subtokens=("subtokens", "mean"),
            median_subtokens=("subtokens", "median"),
            p90_subtokens=("subtokens", lambda s: np.percentile(s, 90, method="linear")),
            mean_subtokens_per_word=("subtokens_per_word", "mean"),
            median_subtokens_per_word=("subtokens_per_word", "median"),
            pct_fragmented=("fragmented", lambda s: float(np.mean(s) * 100)),
            mean_excess_subtokens=("excess_subtokens", "mean"),
        )
        .reset_index()
    )
    by_category = (
        long_df.groupby(["tokenizer", "categoria"], sort=False)
        .agg(
            n_terms=("termino", "size"),
            mean_subtokens_per_word=("subtokens_per_word", "mean"),
            median_subtokens_per_word=("subtokens_per_word", "median"),
            pct_fragmented=("fragmented", lambda s: float(np.mean(s) * 100)),
        )
        .reset_index()
    )

    detail.to_csv(output_dir / "fragmentacion_terminos_formato_ancho.csv", index=False, encoding="utf-8-sig")
    long_df.to_csv(output_dir / "fragmentacion_terminos_detalle.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(output_dir / "tabla_fragmentacion_resumen.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    by_category.to_csv(output_dir / "fragmentacion_por_categoria.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    logger.info("Análisis de fragmentación completado sobre %d términos.", len(terms))
    return long_df, overall, by_category


def plot_length_ecdf(detail: pd.DataFrame, tokenizers: Sequence[str], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for label in tokenizers:
        values = np.sort(detail[f"tokens_{label}"].to_numpy(dtype=float))
        y = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, y, linewidth=1.6, label=label)
    for threshold in (512, 4096, 8192):
        ax.axvline(threshold, linestyle="--", linewidth=1.0)
        ax.text(threshold, 0.04, f"{threshold:,}".replace(",", "."), rotation=90, va="bottom", ha="right", fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("Longitud tokenizada del documento (escala logarítmica)")
    ax.set_ylabel("Proporción acumulada de documentos")
    ax.set_title("Distribución acumulada de longitudes tokenizadas en la muestra BOE")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    path = output_dir / "figura_ecdf_longitudes.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_fragmentation(overall: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.bar(overall["tokenizer"], overall["mean_subtokens_per_word"])
    ax.set_ylabel("Subtokens medios por palabra ortográfica")
    ax.set_title("Fragmentación media del léxico jurídico")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    path = output_dir / "figura_fragmentacion_media.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def run_svm_baseline(
    corpus: pd.DataFrame,
    output_dir: Path,
    target: str,
    logger: logging.Logger,
) -> dict[str, Any]:
    years = sorted(corpus["year"].unique())
    test_year = max(years)
    if target == "section":
        label_col = "section_code"
        label_name_col = "section_name"
    else:
        label_col = "department_code"
        label_name_col = "department_name"

    data = corpus[["year", "clean_text", label_col, label_name_col]].copy()
    data[label_col] = data[label_col].fillna("").astype(str)
    data = data[data[label_col] != ""]
    train = data[data["year"] < test_year].copy()
    test = data[data["year"] == test_year].copy()

    train_counts = train[label_col].value_counts()
    test_counts = test[label_col].value_counts()
    eligible = sorted(
        set(train_counts[train_counts >= 10].index).intersection(test_counts[test_counts >= 5].index)
    )
    train = train[train[label_col].isin(eligible)]
    test = test[test[label_col].isin(eligible)]
    if len(eligible) < 2:
        raise RuntimeError(
            f"No hay al menos dos clases con >=10 ejemplos de entrenamiento y >=5 de test para {target}."
        )

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.95,
                    sublinear_tf=True,
                    max_features=50_000,
                    dtype=np.float64,
                ),
            ),
            ("svm", LinearSVC(C=1.0, class_weight="balanced", random_state=0)),
        ]
    )
    pipeline.fit(train["clean_text"], train[label_col])
    predictions = pipeline.predict(test["clean_text"])
    labels = eligible
    report_dict = classification_report(
        test[label_col], predictions, labels=labels, output_dict=True, zero_division=0
    )
    report_rows: list[dict[str, Any]] = []
    name_map = (
        pd.concat([train[[label_col, label_name_col]], test[[label_col, label_name_col]]])
        .drop_duplicates(subset=label_col)
        .set_index(label_col)[label_name_col]
        .to_dict()
    )
    for label in labels:
        metrics = report_dict[str(label)]
        report_rows.append(
            {
                "class_code": label,
                "class_name": name_map.get(label, ""),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1-score"],
                "support": int(metrics["support"]),
            }
        )
    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(output_dir / "svm_metricas_por_clase.csv", index=False, encoding="utf-8-sig", float_format="%.4f")

    matrix = confusion_matrix(test[label_col], predictions, labels=labels)
    pd.DataFrame(matrix, index=labels, columns=labels).to_csv(
        output_dir / "svm_matriz_confusion.csv", encoding="utf-8-sig"
    )

    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    image = ax.imshow(matrix, interpolation="nearest")
    fig.colorbar(image, ax=ax)
    ax.set_xticks(range(len(labels)), labels=labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("Predicción")
    ax.set_ylabel("Clase real")
    ax.set_title(f"Matriz de confusión TF-IDF + LinearSVC (test temporal {test_year})")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center")
    fig.tight_layout()
    fig.savefig(output_dir / "svm_matriz_confusion.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    metrics = {
        "target": target,
        "label_column": label_col,
        "test_year": int(test_year),
        "train_years": [int(y) for y in years if y < test_year],
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "n_classes": int(len(labels)),
        "classes": labels,
        "macro_f1": float(f1_score(test[label_col], predictions, average="macro")),
        "accuracy": float(accuracy_score(test[label_col], predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(test[label_col], predictions)),
        "vectorizer": {
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_df": 0.95,
            "sublinear_tf": True,
            "max_features": 50000,
        },
        "classifier": {"name": "LinearSVC", "C": 1.0, "class_weight": "balanced"},
    }
    (output_dir / "svm_resumen.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "Baseline SVM: target=%s, test=%d, n_train=%d, n_test=%d, macro-F1=%.4f.",
        target, test_year, len(train), len(test), metrics["macro_f1"]
    )
    return metrics


def format_float(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def dataframe_to_markdown(df: pd.DataFrame, columns: Sequence[str], headers: Sequence[str], digits: int = 1) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in df.iterrows():
        values: list[str] = []
        for col in columns:
            value = row[col]
            if isinstance(value, (float, np.floating)):
                values.append(format_float(float(value), digits))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def generate_tfm_markdown(
    corpus: pd.DataFrame,
    length_summary: pd.DataFrame,
    frag_summary: pd.DataFrame,
    tokenizer_provenance: dict[str, dict[str, str]],
    svm_metrics: dict[str, Any] | None,
    output_dir: Path,
) -> Path:
    years = sorted(int(y) for y in corpus["year"].unique())
    n_dates = int(corpus["issue_date"].nunique())
    n_sections = int(corpus["section_code"].nunique())

    length_table = dataframe_to_markdown(
        length_summary,
        ["tokenizer", "median", "p90", "p95", "pct_gt_512", "pct_gt_4096", "pct_gt_8192"],
        ["Tokenizador", "Mediana", "P90", "P95", "% >512", "% >4.096", "% >8.192"],
        digits=1,
    )
    frag_table = dataframe_to_markdown(
        frag_summary,
        ["tokenizer", "mean_subtokens_per_word", "median_subtokens_per_word", "pct_fragmented", "mean_excess_subtokens"],
        ["Tokenizador", "Subtokens/palabra (media)", "Subtokens/palabra (mediana)", "% términos fragmentados", "Exceso medio de subtokens"],
        digits=2,
    )

    svm_text = ""
    if svm_metrics:
        svm_text = (
            f"El baseline TF-IDF con LinearSVC, entrenado con los años "
            f"{', '.join(map(str, svm_metrics['train_years']))} y evaluado temporalmente en "
            f"{svm_metrics['test_year']}, obtuvo una F1-macro de "
            f"{format_float(svm_metrics['macro_f1'], 3)} sobre {svm_metrics['n_classes']} clases "
            f"(n_train={svm_metrics['n_train']}; n_test={svm_metrics['n_test']}). "
            "El detalle por clase y la matriz de confusión se incluyen en el Anexo II."
        )

    commits = "; ".join(
        f"{label}: {meta['repo_id']} ({meta['snapshot_commit_or_dir']})"
        for label, meta in tokenizer_provenance.items()
    )

    content = f"""# Texto y tablas generados para integrar en el TFM

> Este fichero se genera automáticamente a partir de resultados reales. Revise la redacción y no copie nada si la ejecución no finalizó sin errores.

## Datos para 5.6 Descripción de la muestra

La muestra exploratoria quedó formada por **{len(corpus)} disposiciones BOE-A**, publicadas en **{n_dates} fechas** de los años **{years[0]}–{years[-1]}** y distribuidas entre **{n_sections} códigos de sección**. La selección partió de fechas ancla predefinidas y, dentro de cada sumario, aplicó un muestreo reproducible con rotación entre secciones. De cada disposición se recuperó el cuerpo textual mediante la URL XML publicada en el sumario; cuando el XML no produjo texto válido, se utilizó la versión HTML. Se excluyeron del texto analizado el título y los metadatos estructurados utilizados para construir la muestra.

La muestra no constituye un corpus de jurisprudencia ni permite estimar directamente la longitud de las resoluciones CENDOJ. Las disposiciones del BOE suelen presentar estructura y extensión diferentes de las resoluciones judiciales; por ello, las longitudes observadas se interpretan como una **cota inferior exploratoria** del problema de contexto que previsiblemente planteará la jurisprudencia.

## Datos para 6.4 Procedimiento del estudio exploratorio

Se emplearon únicamente los tokenizadores, sin descargar ni ejecutar los pesos de los modelos. Para cada documento se calculó la longitud de la secuencia incluyendo los tokens especiales y sin truncamiento. Se registraron mediana, percentiles 90 y 95 y proporción de documentos que supera 512, 4.096 y 8.192 tokens. Los tokenizadores y revisiones resueltas fueron: {commits}.

La fragmentación léxica se midió sobre **125 expresiones predefinidas**, agrupadas en latinismos, colocaciones jurídicas, fórmulas rituales y términos técnicos o arcaizantes. Para evitar que las expresiones multi-palabra quedaran penalizadas por su mera longitud, el indicador principal fue el número de subtokens por palabra ortográfica; se añadió la proporción de expresiones cuyo número de subtokens supera el de palabras. No se añadieron tokens especiales en este análisis.

{svm_text}

## Tabla 7.2. Distribución de longitudes tokenizadas

{length_table}

**Nota.** Longitudes calculadas sobre el cuerpo depurado del documento, incluyendo tokens especiales y sin truncamiento. La muestra BOE no equivale a jurisprudencia; los resultados son una cota inferior exploratoria para el caso CENDOJ.

## Tabla 7.3. Fragmentación del léxico jurídico

{frag_table}

**Nota.** Se considera fragmentada una expresión cuando el número de subtokens supera el número de palabras ortográficas. El listado completo y las piezas producidas por cada tokenizador se incluyen en el Anexo II.

## Interpretación sugerida para 7.2

Los resultados convierten en observación medida dos hipótesis que en la revisión se formulaban únicamente a partir de las propiedades declaradas de los modelos. En primer lugar, la distribución de longitudes permite cuantificar qué proporción de disposiciones puede procesarse íntegramente con ventanas de 512, 4.096 y 8.192 tokens. En segundo lugar, la fragmentación demuestra que el tamaño nominal del vocabulario no basta para inferir su adecuación al dominio: la comparación debe realizarse sobre unidades jurídicas concretas y mediante un indicador normalizado por número de palabras.

La interpretación debe mantenerse acotada al BOE. Un resultado favorable a 512 tokens en esta muestra no demostraría que esa ventana sea suficiente para resoluciones judiciales; del mismo modo, una menor fragmentación léxica no acredita por sí sola mejor clasificación. Ambas mediciones sirven para priorizar candidatos y estrategias de segmentación, pero la decisión final sobre CENDOJ requiere el experimento específico previsto para la segunda fase.
"""
    path = output_dir / "texto_para_integrar_en_TFM.md"
    path.write_text(content, encoding="utf-8")
    return path


def build_manifest(
    args: argparse.Namespace,
    corpus: pd.DataFrame,
    exclusion_df: pd.DataFrame,
    tokenizer_provenance: dict[str, dict[str, str]],
    svm_metrics: dict[str, Any] | None,
    output_dir: Path,
) -> Path:
    manifest = {
        "script_version": SCRIPT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sampling": {
            "target_docs": args.target_docs,
            "actual_docs": int(len(corpus)),
            "years": sorted(int(y) for y in corpus["year"].unique()),
            "issue_dates": sorted(corpus["issue_date"].unique().tolist()),
            "n_issue_dates": int(corpus["issue_date"].nunique()),
            "docs_per_issue_initial": args.docs_per_issue,
            "anchor_month_days": [list(x) for x in DEFAULT_ANCHORS],
            "seed": args.seed,
            "min_text_chars": args.min_text_chars,
            "max_text_chars": args.max_text_chars,
            "excluded_documents": int(len(exclusion_df)),
        },
        "boe_api": BOE_API,
        "tokenizers": tokenizer_provenance,
        "document_length": {
            "add_special_tokens": True,
            "truncation": False,
            "thresholds": [512, 4096, 8192],
            "percentiles": [50, 90, 95],
        },
        "term_fragmentation": {
            "terms_file": args.terms_file.name,
            "n_terms": 125,
            "add_special_tokens": False,
            "primary_measure": "subtokens_per_orthographic_word",
        },
        "svm": svm_metrics,
    }
    path = output_dir / "manifiesto_reproducibilidad.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_shareable_zip(output_dir: Path) -> Path:
    excluded_names = {"corpus_boe_local.csv.gz"}
    excluded_dirs = {"cache", "hf_cache"}
    zip_path = output_dir / "resultados_para_integrar.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path == zip_path or not path.is_file():
                continue
            relative = path.relative_to(output_dir)
            if path.name in excluded_names or any(part in excluded_dirs for part in relative.parts):
                continue
            archive.write(path, arcname=str(relative))
    return zip_path


def main() -> int:
    args = parse_args()
    args.output_dir = args.output_dir.resolve()
    args.terms_file = args.terms_file.resolve()
    logger = setup_logging(args.output_dir)
    logger.info("Inicio del estudio BOE, versión %s.", SCRIPT_VERSION)
    logger.info("Directorio de salida: %s", args.output_dir)

    try:
        corpus, exclusions = collect_sample(args, logger)
        tokenizers, provenance = load_tokenizers(args, logger)
        length_detail, length_summary = analyse_document_lengths(corpus, tokenizers, args.output_dir, logger)
        terms = read_terms(args.terms_file)
        _, frag_summary, _ = analyse_term_fragmentation(terms, tokenizers, args.output_dir, logger)
        plot_length_ecdf(length_detail, list(tokenizers), args.output_dir)
        plot_fragmentation(frag_summary, args.output_dir)

        svm_metrics: dict[str, Any] | None = None
        if not args.skip_svm:
            try:
                svm_metrics = run_svm_baseline(corpus, args.output_dir, args.svm_target, logger)
            except Exception as exc:
                logger.exception("El baseline SVM no pudo completarse: %s", exc)
                (args.output_dir / "svm_NO_EJECUTADO.txt").write_text(str(exc), encoding="utf-8")

        generate_tfm_markdown(corpus, length_summary, frag_summary, provenance, svm_metrics, args.output_dir)
        build_manifest(args, corpus, exclusions, provenance, svm_metrics, args.output_dir)
        zip_path = make_shareable_zip(args.output_dir)
        logger.info("Ejecución finalizada. ZIP para integrar: %s", zip_path)
        print("\nRESULTADO LISTO:", zip_path)
        return 0
    except KeyboardInterrupt:
        logger.error("Ejecución interrumpida por el usuario.")
        return 130
    except Exception as exc:
        logger.exception("La ejecución terminó con error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
