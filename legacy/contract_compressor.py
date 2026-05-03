"""
contract_compressor.py — Compressione contract files per ridurre token

Ogni agente riceve solo le sezioni di contract/task_plan che gli servono.
Risparmio stimato: 30-50% sui token di input nelle fasi BE/FE/QA.

Strategia:
- I contract originali in contracts/ e tasks/ restano immutati (single source of truth)
- I file compressi vengono scritti in contracts/_compressed/{agent}_{name}.json
  e tasks/_compressed/{agent}_{name}.json
- Gli agenti vengono istruiti via prompt a leggere i file compressi
- Al termine del run, contracts/_compressed/ può essere rimosso (è derivato)

Filosofia di compressione:
1. Drop di sezioni non rilevanti per l'agente (es. il DB non vede tasks.frontend)
2. Pruning di campi descrittivi prolissi quando l'agente non ne ha bisogno
   (es. il FE non ha bisogno di `description` lunga su ogni endpoint, gli serve la firma)
3. Flatten di strutture annidate ridondanti
4. Mai droppare retry_context: è vitale per i retry mirati
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("pipeline.compressor")

# Directory dove finiscono i file compressi
COMPRESSED_CONTRACTS = Path("contracts/_compressed")
COMPRESSED_TASKS = Path("tasks/_compressed")


# ─── Helpers di pruning ───────────────────────────────────────────────────────


def _drop_keys(d: dict, keys: list[str]) -> dict:
    """Ritorna una copia di d senza le chiavi in keys."""
    return {k: v for k, v in d.items() if k not in keys}


def _keep_keys(d: dict, keys: list[str]) -> dict:
    """Ritorna una copia di d con SOLO le chiavi in keys (se presenti)."""
    return {k: d[k] for k in keys if k in d}


def _truncate_string(s: Any, max_len: int = 200) -> Any:
    """Tronca stringhe lunghe, lascia altri tipi invariati."""
    if isinstance(s, str) and len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _prune_descriptions(obj: Any, max_len: int = 200) -> Any:
    """Tronca ricorsivamente i campi 'description' lunghi."""
    if isinstance(obj, dict):
        return {
            k: _truncate_string(v, max_len) if k == "description"
            else _prune_descriptions(v, max_len)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_prune_descriptions(x, max_len) for x in obj]
    return obj


def _ensure_dirs() -> None:
    COMPRESSED_CONTRACTS.mkdir(parents=True, exist_ok=True)
    COMPRESSED_TASKS.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error("JSON malformato in %s: %s", path, e)
        return {}


def _write_compressed(path: Path, data: dict, label: str) -> Path:
    """
    Scrive il JSON compresso in formato compatto (separators stretti, no indent).
    Per LLM la differenza in token è minima ma evitiamo di "inflate" file
    già piccoli rispetto agli originali.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    log.debug("📦 %s → %s (%d bytes)", label, path, len(text))
    return path


def _size_of(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


# ─── Compressione per agente ──────────────────────────────────────────────────


def compress_for_db(
    task_plan_path: Path = Path("tasks/task_plan.json"),
) -> Path:
    """
    Compressione per agent_db.
    Tiene: tech_stack, tasks.database, assumptions, retry_context.
    Drop: tasks.backend, tasks.frontend.
    """
    _ensure_dirs()
    plan = _read_json(task_plan_path)
    if not plan:
        return task_plan_path  # fallback all'originale

    compressed = {
        "version": plan.get("version"),
        "project": plan.get("project"),
        "tech_stack": _keep_keys(plan.get("tech_stack", {}), ["database"]),
        "tasks": {
            "database": plan.get("tasks", {}).get("database", {}),
        },
        "execution_order": plan.get("execution_order"),
        "assumptions": plan.get("assumptions"),
        "retry_context": plan.get("retry_context"),
    }
    # Rimuovi campi None per pulizia
    compressed = {k: v for k, v in compressed.items() if v is not None}

    out = COMPRESSED_TASKS / "db_task_plan.json"
    return _write_compressed(out, compressed, "db_task_plan")


def compress_for_be(
    task_plan_path: Path = Path("tasks/task_plan.json"),
    db_contract_path: Path = Path("contracts/db_contract.json"),
) -> tuple[Path, Path]:
    """
    Compressione per agent_be.
    Task plan: tutto tranne tasks.frontend.
    DB contract: nessun pruning (serve interamente per mappare entità).
    """
    _ensure_dirs()
    plan = _read_json(task_plan_path)

    if plan:
        compressed_plan = {
            "version": plan.get("version"),
            "project": plan.get("project"),
            "tech_stack": _drop_keys(plan.get("tech_stack", {}), ["frontend"]),
            "tasks": {
                "database": plan.get("tasks", {}).get("database", {}),
                "backend": plan.get("tasks", {}).get("backend", {}),
            },
            "assumptions": plan.get("assumptions"),
            "retry_context": plan.get("retry_context"),
        }
        compressed_plan = {k: v for k, v in compressed_plan.items() if v is not None}
        out_plan = _write_compressed(
            COMPRESSED_TASKS / "be_task_plan.json",
            compressed_plan,
            "be_task_plan",
        )
    else:
        out_plan = task_plan_path

    # DB contract: copia senza modifiche (è già denso)
    db_contract = _read_json(db_contract_path)
    if db_contract:
        out_db = _write_compressed(
            COMPRESSED_CONTRACTS / "be_db_contract.json",
            db_contract,
            "be_db_contract",
        )
    else:
        out_db = db_contract_path

    return out_plan, out_db


def compress_for_fe(
    task_plan_path: Path = Path("tasks/task_plan.json"),
    api_contract_path: Path = Path("contracts/api_contract.json"),
) -> tuple[Path, Path]:
    """
    Compressione per agent_fe.
    Task plan: solo tech_stack.frontend, tasks.frontend, retry_context.
    API contract: drop description lunghe sugli endpoint (FE ha bisogno
    di metodo, path, requestBody, responses — non di descrizioni narrative).
    """
    _ensure_dirs()
    plan = _read_json(task_plan_path)

    if plan:
        compressed_plan = {
            "version": plan.get("version"),
            "project": plan.get("project"),
            "tech_stack": _keep_keys(plan.get("tech_stack", {}), ["frontend"]),
            "tasks": {
                "frontend": plan.get("tasks", {}).get("frontend", {}),
            },
            "assumptions": plan.get("assumptions"),
            "retry_context": plan.get("retry_context"),
        }
        compressed_plan = {k: v for k, v in compressed_plan.items() if v is not None}
        out_plan = _write_compressed(
            COMPRESSED_TASKS / "fe_task_plan.json",
            compressed_plan,
            "fe_task_plan",
        )
    else:
        out_plan = task_plan_path

    # API contract: pruna le description sugli endpoint
    api_contract = _read_json(api_contract_path)
    if api_contract:
        compressed_api = dict(api_contract)
        if "endpoints" in compressed_api:
            pruned = []
            for ep in compressed_api["endpoints"]:
                ep_pruned = dict(ep)
                # Tronca description a 100 char (FE ha bisogno della firma, non del racconto)
                if "description" in ep_pruned:
                    ep_pruned["description"] = _truncate_string(
                        ep_pruned["description"], 100
                    )
                pruned.append(ep_pruned)
            compressed_api["endpoints"] = pruned
        out_api = _write_compressed(
            COMPRESSED_CONTRACTS / "fe_api_contract.json",
            compressed_api,
            "fe_api_contract",
        )
    else:
        out_api = api_contract_path

    return out_plan, out_api


def compress_for_review(
    task_plan_path: Path = Path("tasks/task_plan.json"),
    db_contract_path: Path = Path("contracts/db_contract.json"),
    api_contract_path: Path = Path("contracts/api_contract.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_review_static.
    Necessita di vedere tutti i contratti per controllare consistency
    BE↔contract, FE↔contract, codice↔schema.
    Drop: descrizioni narrative del task_plan, assumptions (non rilevanti per review).
    """
    _ensure_dirs()
    plan = _read_json(task_plan_path)

    if plan:
        # Taglia description lunghe ovunque ma mantieni la struttura
        compressed_plan = _prune_descriptions(plan, max_len=150)
        # Rimuovi assumptions: la review non valida semantica del piano,
        # solo il rispetto del contratto da parte del codice
        compressed_plan = _drop_keys(compressed_plan, ["assumptions"])
        out_plan = _write_compressed(
            COMPRESSED_TASKS / "review_task_plan.json",
            compressed_plan,
            "review_task_plan",
        )
    else:
        out_plan = task_plan_path

    # DB e API contract: copia integrale (servono per consistency check)
    paths = {"task_plan": out_plan}
    for name, src, prefix in [
        ("db_contract", db_contract_path, "review_db_contract"),
        ("api_contract", api_contract_path, "review_api_contract"),
    ]:
        data = _read_json(src)
        if data:
            paths[name] = _write_compressed(
                COMPRESSED_CONTRACTS / f"{prefix}.json", data, prefix
            )
        else:
            paths[name] = src

    return paths


def compress_for_test(
    api_contract_path: Path = Path("contracts/api_contract.json"),
    static_review_path: Path = Path("reports/static_review.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_test.
    API contract: serve completo (genera test happy/error path per ogni endpoint).
    Static review: solo build_ok e summary (per decidere se skippare).
    Drop: findings completi, files_reviewed (long list non utile al test).
    """
    _ensure_dirs()
    paths: dict[str, Path] = {}

    # API contract integrale (ma description tagliate)
    api_contract = _read_json(api_contract_path)
    if api_contract:
        compressed = _prune_descriptions(api_contract, max_len=120)
        paths["api_contract"] = _write_compressed(
            COMPRESSED_CONTRACTS / "test_api_contract.json",
            compressed,
            "test_api_contract",
        )
    else:
        paths["api_contract"] = api_contract_path

    # Review report ridotto al minimo
    review = _read_json(static_review_path)
    if review:
        slim = _keep_keys(review, ["version", "build_ok", "summary"])
        out = COMPRESSED_CONTRACTS.parent / "reports/_compressed"
        out.mkdir(parents=True, exist_ok=True)
        slim_path = out / "test_static_review.json"
        slim_path.write_text(
            json.dumps(slim, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        paths["static_review"] = slim_path
    else:
        paths["static_review"] = static_review_path

    return paths


def compress_for_security(
    api_contract_path: Path = Path("contracts/api_contract.json"),
    db_contract_path: Path = Path("contracts/db_contract.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_security.
    Necessita degli endpoint (per identificare quelli sensibili: auth, user-scoped)
    e dello schema DB (per SQL injection, password in chiaro).
    Drop: description narrative.
    """
    _ensure_dirs()
    paths: dict[str, Path] = {}

    api = _read_json(api_contract_path)
    if api:
        slim = _prune_descriptions(api, max_len=80)
        paths["api_contract"] = _write_compressed(
            COMPRESSED_CONTRACTS / "security_api_contract.json",
            slim,
            "security_api_contract",
        )
    else:
        paths["api_contract"] = api_contract_path

    db = _read_json(db_contract_path)
    if db:
        # DB contract è già denso, tieni com'è ma copia in _compressed
        # per coerenza di interfaccia
        paths["db_contract"] = _write_compressed(
            COMPRESSED_CONTRACTS / "security_db_contract.json",
            db,
            "security_db_contract",
        )
    else:
        paths["db_contract"] = db_contract_path

    return paths


def compress_for_comments(
    static_review_path: Path = Path("reports/static_review.json"),
    test_report_path: Path = Path("reports/test_report.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_comments.
    L'agente Commenti necessita SOLO di sapere se i build sono ok prima di
    procedere (è il prerequisito dichiarato nel suo prompt).
    Tieni: build_ok di entrambi i report.
    Drop: tutto il resto (findings, summary dettagliato, stacktrace).
    """
    _ensure_dirs()
    out_dir = Path("reports/_compressed")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for name, src, key in [
        ("static_review", static_review_path, "comments_static_review"),
        ("test_report", test_report_path, "comments_test_report"),
    ]:
        data = _read_json(src)
        if data:
            slim = _keep_keys(data, ["version", "build_ok", "skipped"])
            out_path = out_dir / f"{key}.json"
            out_path.write_text(
                json.dumps(slim, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            paths[name] = out_path
        else:
            paths[name] = src

    return paths


def compress_for_wiki(
    api_contract_path: Path = Path("contracts/api_contract.json"),
    db_contract_path: Path = Path("contracts/db_contract.json"),
    task_plan_path: Path = Path("tasks/task_plan.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_wiki.
    La wiki HA BISOGNO delle description complete (è documentazione narrativa).
    Tieni i contract integralmente, ma droppa retry_context dal task_plan
    (non rilevante per docs finale, è meta-informazione di processo).
    """
    _ensure_dirs()
    paths: dict[str, Path] = {}

    plan = _read_json(task_plan_path)
    if plan:
        slim_plan = _drop_keys(plan, ["retry_context"])
        paths["task_plan"] = _write_compressed(
            COMPRESSED_TASKS / "wiki_task_plan.json",
            slim_plan,
            "wiki_task_plan",
        )
    else:
        paths["task_plan"] = task_plan_path

    for name, src, key in [
        ("api_contract", api_contract_path, "wiki_api_contract"),
        ("db_contract", db_contract_path, "wiki_db_contract"),
    ]:
        data = _read_json(src)
        if data:
            paths[name] = _write_compressed(
                COMPRESSED_CONTRACTS / f"{key}.json", data, key
            )
        else:
            paths[name] = src

    return paths


def compress_for_memory(
    api_contract_path: Path = Path("contracts/api_contract.json"),
    db_contract_path: Path = Path("contracts/db_contract.json"),
    task_plan_path: Path = Path("tasks/task_plan.json"),
    static_review_path: Path = Path("reports/static_review.json"),
    test_report_path: Path = Path("reports/test_report.json"),
) -> dict[str, Path]:
    """
    Compressione per agent_memory.
    Memory necessita una vista olistica per estrarre ADR e pattern.
    Tieni tutto, ma droppa stacktrace dai test (non utile per memoria semantica).
    """
    _ensure_dirs()
    paths: dict[str, Path] = {}

    # Task plan e contracts: integrali
    for name, src, key in [
        ("task_plan", task_plan_path, "memory_task_plan"),
        ("api_contract", api_contract_path, "memory_api_contract"),
        ("db_contract", db_contract_path, "memory_db_contract"),
    ]:
        data = _read_json(src)
        if data:
            target = (
                COMPRESSED_TASKS if name == "task_plan" else COMPRESSED_CONTRACTS
            )
            paths[name] = _write_compressed(target / f"{key}.json", data, key)
        else:
            paths[name] = src

    # Review report: integrale (i finding sono pattern preziosi)
    out_dir = Path("reports/_compressed")
    out_dir.mkdir(parents=True, exist_ok=True)

    review = _read_json(static_review_path)
    if review:
        slim_path = out_dir / "memory_static_review.json"
        slim_path.write_text(
            json.dumps(review, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        paths["static_review"] = slim_path
    else:
        paths["static_review"] = static_review_path

    # Test report: drop stacktrace (rumore per memoria)
    tests = _read_json(test_report_path)
    if tests:
        slim_tests = dict(tests)
        if "failures" in slim_tests:
            slim_tests["failures"] = [
                _drop_keys(f, ["stacktrace"]) for f in slim_tests["failures"]
            ]
        slim_path = out_dir / "memory_test_report.json"
        slim_path.write_text(
            json.dumps(slim_tests, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        paths["test_report"] = slim_path
    else:
        paths["test_report"] = test_report_path

    return paths


# ─── Stats e cleanup ──────────────────────────────────────────────────────────


def compression_stats(
    original_paths: list[Path], compressed_paths: list[Path]
) -> dict:
    """Calcola statistiche di compressione per logging."""
    orig_total = sum(_size_of(p) for p in original_paths)
    comp_total = sum(_size_of(p) for p in compressed_paths)
    if orig_total == 0:
        return {"original_bytes": 0, "compressed_bytes": 0, "savings_pct": 0}
    savings = (orig_total - comp_total) / orig_total * 100
    return {
        "original_bytes": orig_total,
        "compressed_bytes": comp_total,
        "savings_pct": round(savings, 1),
    }


def cleanup_compressed() -> None:
    """Rimuove le directory di compressione al termine del run."""
    import shutil
    for d in [
        COMPRESSED_CONTRACTS,
        COMPRESSED_TASKS,
        Path("reports/_compressed"),
    ]:
        if d.exists():
            shutil.rmtree(d)
            log.debug("Rimosso: %s", d)
