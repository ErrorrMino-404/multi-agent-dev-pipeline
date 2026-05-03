#!/usr/bin/env python3
"""
orchestrate.py — Pipeline multi-agent per sviluppo software con Claude Code CLI

Refactor v2:
- Validazione contract files (JSON parsabile + schema minimo)
- Cleanup reports/ tra retry per evitare letture stale
- Esito subprocess propagato e considerato (no più silent failures)
- Logging strutturato su file pipeline.log
- Timeout configurabili per fase (CLI o config file)
- Dry-run mode (--dry-run): valida task_plan senza chiamare worker pesanti
- Integrazione agent_memory.md in FASE 4 (knowledge vault Obsidian)
- Git integration opzionale (--git): commit per fase su branch dedicato
- FASE 3: review prima, test dopo (serializzato per risolvere prerequisito)
- Validazione esistenza tech_stack nel task_plan

Uso:
    python orchestrate.py --requirements requirements.md
    python orchestrate.py --requirements requirements.md --max-retries 3
    python orchestrate.py --requirements requirements.md --dry-run
    python orchestrate.py --requirements requirements.md --git
    python orchestrate.py --requirements requirements.md --config pipeline.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import contract_compressor as cc

# ─── Configurazione di default ────────────────────────────────────────────────

AGENTS_DIR = Path("agents")
CONTRACTS = Path("contracts")
TASKS = Path("tasks")
REPORTS = Path("reports")
VAULT = Path("vault")
LOG_FILE = Path("pipeline.log")

DEFAULT_MAX_RETRIES = 2

# Timeout per fase (secondi). Sovrascrivibili da config.
DEFAULT_TIMEOUTS = {
    "orchestrator": 240,
    "db": 240,
    "be": 600,
    "fe": 600,
    "review": 300,
    "test_writer": 360,
    "test_runner": 240,
    "security": 360,
    "comments": 300,
    "wiki": 300,
    "memory": 300,
}

# Mapping agente → modello consigliato (override via --config)
# Opus: ragionamento complesso (orchestrazione)
# Sonnet: task tecnici (codice, review)
# Haiku: task meccanici (commenti, wiki, memory)
DEFAULT_MODELS = {
    "orchestrator": "opus",
    "db": "sonnet",
    "be": "sonnet",
    "fe": "sonnet",
    "review": "sonnet",
    "test_writer": "sonnet",   # ragiona su contract per generare test
    "test_runner": "haiku",    # esegue e parsa, meccanico
    "security": "sonnet",
    "comments": "haiku",
    "wiki": "haiku",
    "memory": "sonnet",
}


# File contract → chiavi minime richieste per validazione
CONTRACT_SCHEMA = {
    "contracts/db_contract.json": ["version", "tables"],
    "contracts/api_contract.json": ["version", "endpoints"],
    "tasks/task_plan.json": ["version", "tech_stack", "tasks"],
    "tasks/test_manifest.json": ["version"],
    "reports/static_review.json": ["version", "build_ok"],
    "reports/test_report.json": ["version", "build_ok"],
    "reports/security_audit.json": ["version", "build_ok"],
}


# ─── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    requirements: Path
    max_retries: int = DEFAULT_MAX_RETRIES
    skip_tests: bool = False
    skip_security: bool = False
    dry_run: bool = False
    git: bool = False
    compress: bool = True   # comprime contract per agente (riduce token)
    timeouts: dict = field(default_factory=lambda: dict(DEFAULT_TIMEOUTS))
    models: dict = field(default_factory=lambda: dict(DEFAULT_MODELS))
    max_budget_usd: Optional[float] = None
    max_turns: Optional[int] = None


# ─── Logging setup ────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configura logger con output su stdout + file pipeline.log."""
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


log = setup_logging()


def phase_banner(phase: str, msg: str) -> None:
    log.info("=" * 60)
    log.info("  [%s] %s", phase.upper(), msg)
    log.info("=" * 60)


# ─── Utility I/O ──────────────────────────────────────────────────────────────


def read_json(path: Path) -> dict:
    """Legge un JSON, ritorna {} se inesistente o malformato (loggando)."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log.error("JSON malformato in %s: %s", path, e)
        return {}


def validate_contract(path: Path) -> tuple[bool, str]:
    """
    Verifica che un contract file sia JSON valido e contenga le chiavi minime.
    Ritorna (ok, motivo_errore).
    """
    rel = str(path).replace("\\", "/")
    required = CONTRACT_SCHEMA.get(rel)
    if required is None:
        # Contract non noto allo schema → solo verifica esistenza/parsing
        if not path.exists():
            return False, f"file inesistente: {path}"
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"JSON malformato: {e}"

    if not path.exists():
        return False, f"file inesistente: {path}"

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"JSON malformato: {e}"

    missing = [k for k in required if k not in data]
    if missing:
        return False, f"chiavi mancanti: {missing}"

    return True, ""


def wait_for_valid_contract(
    path: Path, timeout: int = 180, poll: float = 2.0
) -> bool:
    """
    Aspetta che un contract file esista E sia valido (parsabile + schema).
    Ritorna False se scade il timeout.
    """
    elapsed = 0.0
    last_reason = ""
    while elapsed < timeout:
        ok, reason = validate_contract(path)
        if ok:
            log.info("✅ Contract valido: %s", path)
            return True
        last_reason = reason
        time.sleep(poll)
        elapsed += poll
    log.error("⏱️ Timeout in attesa di %s — ultimo errore: %s", path, last_reason)
    return False


def cleanup_reports() -> None:
    """Rimuove i report del ciclo precedente per evitare letture stale."""
    for f in [
        REPORTS / "static_review.json",
        REPORTS / "test_report.json",
        REPORTS / "security_audit.json",
    ]:
        if f.exists():
            f.unlink()
            log.debug("Rimosso report stale: %s", f)


# ─── Git integration ──────────────────────────────────────────────────────────


def git_run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Wrapper su git con logging."""
    cmd = ["git", *args]
    log.debug("git %s", " ".join(args))
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def git_commit_phase(phase: str, paths: list[Path], cycle: int) -> None:
    """
    Commit atomico per fase su branch dedicato.
    Crea branch pipeline/cycle-{N} se non esiste.
    """
    branch = f"pipeline/cycle-{cycle}"

    # Verifica che siamo in un repo git
    res = git_run("rev-parse", "--is-inside-work-tree")
    if res.returncode != 0:
        log.warning("Non in un repo git, skip commit fase %s", phase)
        return

    # Switch/crea branch
    res = git_run("rev-parse", "--verify", branch)
    if res.returncode != 0:
        git_run("checkout", "-b", branch)
    else:
        git_run("checkout", branch)

    # Add solo i path specificati per restare atomici
    for p in paths:
        if p.exists():
            git_run("add", str(p))

    res = git_run("diff", "--cached", "--quiet")
    if res.returncode == 0:
        log.info("Niente da committare per fase %s", phase)
        return

    msg = f"pipeline({phase}): cycle {cycle} — {datetime.now(timezone.utc).isoformat()}"
    res = git_run("commit", "-m", msg)
    if res.returncode == 0:
        log.info("📝 Git commit fase %s su %s", phase, branch)
    else:
        log.warning("Git commit fallito: %s", res.stderr)


# ─── Subprocess wrapper ───────────────────────────────────────────────────────


def run_agent(
    agent_md: Path,
    prompt: str,
    allowed_tools: Optional[str] = None,
    timeout: int = 300,
    dry_run: bool = False,
    model: Optional[str] = None,
    max_turns: Optional[int] = None,
    max_budget_usd: Optional[float] = None,
) -> bool:
    """
    Esegue un agente Claude Code con il system prompt dal file .md.

    Usa --system-prompt-file per beneficiare del prompt caching automatico
    (i system prompt degli agenti sono stabili e riutilizzati a ogni run,
    quindi vengono cached con sconto fino al 90% sui token).

    Usa --permission-mode bypassPermissions perché in modalità CI non
    possiamo rispondere ai prompt di conferma. La sicurezza è demandata
    a --allowedTools che restringe gli strumenti disponibili.

    Ritorna True se exit code == 0.
    """
    if dry_run:
        log.info("[DRY-RUN] %s ← %s", agent_md.name, prompt[:80])
        return True

    if not agent_md.exists():
        log.error("Agent file non trovato: %s", agent_md)
        return False

    cmd = [
        "claude",
        "--print",
        "--permission-mode", "bypassPermissions",
        "--system-prompt-file", str(agent_md.resolve()),
        "-p", prompt,
    ]
    if allowed_tools:
        cmd += ["--allowedTools", allowed_tools]
    if model:
        cmd += ["--model", model]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    if max_budget_usd is not None:
        cmd += ["--max-budget-usd", f"{max_budget_usd:.2f}"]

    log.info("▶️  Run agent: %s (model=%s)", agent_md.name, model or "default")
    log.debug("   prompt: %s", prompt[:200])

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=False,
        )
        ok = result.returncode == 0
        if not ok:
            log.error("❌ %s ha terminato con exit code %s",
                      agent_md.name, result.returncode)
        return ok
    except subprocess.TimeoutExpired:
        log.error("⏱️ Timeout (%ds) per %s", timeout, agent_md.name)
        return False
    except FileNotFoundError:
        log.error("❌ 'claude' CLI non trovato. Installa Claude Code.")
        sys.exit(1)


def run_phase_agent(
    cfg: "PipelineConfig",
    phase_key: str,
    agent_md: Path,
    prompt: str,
    allowed_tools: Optional[str] = None,
) -> bool:
    """Wrapper su run_agent che applica config (timeout, model, budget) per fase."""
    return run_agent(
        agent_md=agent_md,
        prompt=prompt,
        allowed_tools=allowed_tools,
        timeout=cfg.timeouts.get(phase_key, 300),
        dry_run=cfg.dry_run,
        model=cfg.models.get(phase_key),
        max_turns=cfg.max_turns,
        max_budget_usd=cfg.max_budget_usd,
    )


# ─── Fasi del pipeline ────────────────────────────────────────────────────────


def phase_0_orchestrator(cfg: PipelineConfig, retry_cycle: int = 0) -> bool:
    """FASE 0 — Orchestratore: analizza requisiti e produce task_plan.json"""
    phase_banner("FASE 0", "Orchestratore — analisi requisiti")

    prompt = (
        f"Leggi {cfg.requirements} e produci tasks/task_plan.json. "
        f"Includi sempre il campo tech_stack popolato."
    )
    if retry_cycle > 0:
        prompt += (
            f" Questo è il ciclo di retry #{retry_cycle}. "
            f"Leggi anche reports/static_review.json e reports/test_report.json "
            f"per aggiornare il piano con il retry_context appropriato. "
            f"Limita le modifiche ai soli file segnalati negli errori."
        )

    ok = run_phase_agent(
        cfg,
        "orchestrator",
        AGENTS_DIR / "orchestrator.md",
        prompt,
        allowed_tools="Read,Write",
    )
    if not ok and not cfg.dry_run:
        return False

    # Validazione task_plan
    if cfg.dry_run:
        log.info("[DRY-RUN] skip validazione task_plan")
        return True

    valid, reason = validate_contract(TASKS / "task_plan.json")
    if not valid:
        log.error("❌ task_plan.json non valido: %s", reason)
        return False

    plan = read_json(TASKS / "task_plan.json")
    stack = plan.get("tech_stack", {})
    log.info("✅ task_plan.json valido — stack: %s", stack)

    if cfg.git:
        git_commit_phase("orchestrator", [TASKS / "task_plan.json"], retry_cycle)
    return True


def phase_1_database(cfg: PipelineConfig, cycle: int) -> bool:
    """FASE 1 — Agente DB: schema, migration, db_contract.json"""
    phase_banner("FASE 1", "Agente DB — schema PostgreSQL e contratti")

    # Compressione task_plan per DB (vede solo tasks.database)
    if cfg.compress and not cfg.dry_run:
        task_plan_path = cc.compress_for_db()
        log.info("📦 Task plan compresso per DB: %s", task_plan_path)
    else:
        task_plan_path = TASKS / "task_plan.json"

    ok = run_phase_agent(
        cfg,
        "db",
        AGENTS_DIR / "agent_db.md",
        f"Leggi {task_plan_path} sezione 'database' e genera le migration "
        f"in db/migrations/. Poi produci contracts/db_contract.json.",
        allowed_tools="Read,Write,Bash(psql)",
    )
    if not ok and not cfg.dry_run:
        return False

    if cfg.dry_run:
        return True

    if not wait_for_valid_contract(CONTRACTS / "db_contract.json", timeout=60):
        return False

    if cfg.git:
        git_commit_phase("db", [Path("db"), CONTRACTS / "db_contract.json"], cycle)
    return True


def phase_2_backend_frontend(cfg: PipelineConfig, cycle: int) -> bool:
    """
    FASE 2 — BE e FE in parallelo.
    BE parte subito, FE aspetta api_contract.json.
    """
    phase_banner("FASE 2", "Agenti BE + FE (parallelo)")

    if cfg.dry_run:
        log.info("[DRY-RUN] skip BE+FE")
        return True

    # Compressione per BE (FE viene compresso dopo che il BE produce api_contract)
    if cfg.compress:
        be_plan, be_db = cc.compress_for_be()
        log.info("📦 BE inputs compressi: %s, %s", be_plan, be_db)
    else:
        be_plan = TASKS / "task_plan.json"
        be_db = CONTRACTS / "db_contract.json"

    be_ok = [False]
    fe_ok = [False]

    def run_be():
        be_ok[0] = run_phase_agent(
            cfg,
            "be",
            AGENTS_DIR / "agent_be.md",
            f"Leggi {be_plan} e {be_db}. "
            f"Produci PRIMA contracts/api_contract.json con le firme degli endpoint, "
            f"poi implementa il codice in backend/src/. "
            f"Se il task plan contiene retry_context, modifica SOLO i file indicati.",
            allowed_tools="Read,Write,Bash(./gradlew,pytest)",
        )

    def run_fe():
        log.info("[FE] In attesa di api_contract.json...")
        if not wait_for_valid_contract(
            CONTRACTS / "api_contract.json", timeout=cfg.timeouts["be"]
        ):
            log.error("[FE] api_contract.json non disponibile, abort FE")
            return
        log.info("[FE] api_contract.json valido — avvio agente FE")

        # Compressione per FE (deve avvenire DOPO che BE ha scritto api_contract)
        if cfg.compress:
            fe_plan, fe_api = cc.compress_for_fe()
            log.info("📦 FE inputs compressi: %s, %s", fe_plan, fe_api)
        else:
            fe_plan = TASKS / "task_plan.json"
            fe_api = CONTRACTS / "api_contract.json"

        fe_ok[0] = run_phase_agent(
            cfg,
            "fe",
            AGENTS_DIR / "agent_fe.md",
            f"Leggi {fe_plan} e {fe_api}. "
            f"Implementa i componenti in frontend/src/. "
            f"Se il task plan contiene retry_context, modifica SOLO i file indicati.",
            allowed_tools="Read,Write,Bash(npm)",
        )

    t_be = threading.Thread(target=run_be, name="AgentBE")
    t_fe = threading.Thread(target=run_fe, name="AgentFE")
    t_be.start()
    t_fe.start()
    t_be.join()
    t_fe.join()

    if not be_ok[0]:
        log.error("❌ Agente BE fallito.")
    if not fe_ok[0]:
        log.error("❌ Agente FE fallito.")

    success = be_ok[0] and fe_ok[0]
    if success and cfg.git:
        git_commit_phase(
            "be_fe",
            [Path("backend"), Path("frontend"), CONTRACTS / "api_contract.json"],
            cycle,
        )
    return success


def phase_3_qa(cfg: PipelineConfig, cycle: int) -> bool:
    """
    FASE 3 — Review statica prima (gate), poi test + security in parallelo.

    La review è gate iniziale: se fallisce, evitiamo di sprecare token su
    test e security. Se passa, test e security girano in parallelo perché
    indipendenti tra loro.

    Ritorna True se TUTTI i report attivi hanno build_ok: true.
    """
    phase_banner("FASE 3", "QA — Review → (Test + Security in parallelo)")

    if cfg.dry_run:
        log.info("[DRY-RUN] skip QA")
        return True

    # Cleanup report del ciclo precedente (incluso security)
    cleanup_reports()

    # Compressione input per la review (vede plan + entrambi i contract)
    if cfg.compress:
        review_paths = cc.compress_for_review()
        log.info("📦 Review inputs compressi: %s", list(review_paths.values()))

    # 1) Review statica — sempre eseguita per prima (gate)
    log.info("🔍 Review statica...")
    run_phase_agent(
        cfg,
        "review",
        AGENTS_DIR / "agent_review_static.md",
        "Analizza tutto il codice in backend/src/ e frontend/src/. "
        "Produci reports/static_review.json con la checklist completa. "
        "Se non ci sono file da revisionare, build_ok=false con error specifico.",
        allowed_tools="Read,Write",
    )

    valid, reason = validate_contract(REPORTS / "static_review.json")
    if not valid:
        log.error("❌ static_review.json non valido: %s", reason)
        return False

    review = read_json(REPORTS / "static_review.json")
    review_ok = review.get("build_ok", False)
    log.info("Review statica: %s", "✅ OK" if review_ok else "❌ FAIL")
    if not review_ok:
        errors = review.get("summary", {}).get("errors", "?")
        log.warning("→ %s errori bloccanti nella review", errors)
        if cfg.git:
            git_commit_phase("qa", [REPORTS], cycle)
        return False  # gate: niente test/security se review fallisce

    # 2) Test + Security in parallelo (entrambi indipendenti)
    tests_ok = [True]
    security_ok = [True]

    def run_tests():
        """Test = writer (scrive) → runner (esegue). Serializzati tra loro."""
        if cfg.skip_tests:
            log.info("⏭️ Test saltati (--skip-tests)")
            return

        # Compressione test inputs (DOPO che review ha scritto il suo report)
        if cfg.compress:
            cc.compress_for_test()

        # 2a) Test Writer — scrive i test
        log.info("✍️  Test Writer...")
        writer_ok = run_phase_agent(
            cfg,
            "test_writer",
            AGENTS_DIR / "agent_test_writer.md",
            "Leggi contracts/api_contract.json, il codice in backend/src/ "
            "e frontend/src/, e reports/static_review.json. "
            "Scrivi i test in backend/tests/ e frontend/src/**/__tests__/. "
            "Produci tasks/test_manifest.json con i comandi esatti per eseguirli.",
            allowed_tools="Read,Write",
        )
        if not writer_ok:
            log.error("❌ Test Writer fallito")
            tests_ok[0] = False
            return

        valid, reason = validate_contract(TASKS / "test_manifest.json")
        if not valid:
            log.error("❌ test_manifest.json non valido: %s", reason)
            tests_ok[0] = False
            return

        manifest = read_json(TASKS / "test_manifest.json")
        if manifest.get("skipped"):
            log.info("⏭️ Test runner saltato (manifest skipped)")
            # Scriviamo comunque test_report per coerenza
            (REPORTS / "test_report.json").write_text(
                json.dumps({
                    "version": "1.0",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "skipped": True,
                    "build_ok": False,
                    "reason": manifest.get("reason", "unknown"),
                }, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            tests_ok[0] = False
            return

        # 2b) Test Runner — esegue i test scritti dal writer
        log.info("🧪 Test Runner...")
        run_phase_agent(
            cfg,
            "test_runner",
            AGENTS_DIR / "agent_test_runner.md",
            "Leggi tasks/test_manifest.json. Esegui esattamente i comandi "
            "specificati. Parsa l'output e produci reports/test_report.json.",
            allowed_tools="Read,Write,Bash(./gradlew *,pytest *,npm *)",
        )
        valid, reason = validate_contract(REPORTS / "test_report.json")
        if not valid:
            log.error("❌ test_report.json non valido: %s", reason)
            tests_ok[0] = False
            return
        tests = read_json(REPORTS / "test_report.json")
        tests_ok[0] = tests.get("build_ok", False) or tests.get("skipped", False)
        log.info("Test: %s", "✅ OK" if tests_ok[0] else "❌ FAIL")

    def run_security():
        if cfg.skip_security:
            log.info("⏭️ Security audit saltato (--skip-security)")
            return
        # Compressione security inputs
        if cfg.compress:
            cc.compress_for_security()
        log.info("🔒 Security audit...")
        run_phase_agent(
            cfg,
            "security",
            AGENTS_DIR / "agent_security.md",
            "Esegui security audit completo su backend/src/, frontend/src/, "
            "db/migrations/ e file di dipendenze. "
            "Produci reports/security_audit.json con findings classificati per severity.",
            allowed_tools="Read,Write,Bash(pip-audit,npm,./gradlew)",
        )
        valid, reason = validate_contract(REPORTS / "security_audit.json")
        if not valid:
            log.error("❌ security_audit.json non valido: %s", reason)
            security_ok[0] = False
            return
        audit = read_json(REPORTS / "security_audit.json")
        security_ok[0] = audit.get("build_ok", False)
        crit = audit.get("summary", {}).get("critical", 0)
        log.info("Security: %s (critical=%s)",
                 "✅ OK" if security_ok[0] else "❌ FAIL", crit)

    t_test = threading.Thread(target=run_tests, name="AgentTest")
    t_sec = threading.Thread(target=run_security, name="AgentSecurity")
    t_test.start()
    t_sec.start()
    t_test.join()
    t_sec.join()

    if cfg.git:
        git_commit_phase("qa", [REPORTS], cycle)
    return review_ok and tests_ok[0] and security_ok[0]


def phase_4_docs(cfg: PipelineConfig, cycle: int) -> None:
    """FASE 4 — Commenti + Wiki + Memory in parallelo."""
    phase_banner("FASE 4", "Documentazione — Commenti + Wiki + Memory")

    if cfg.dry_run:
        log.info("[DRY-RUN] skip docs")
        return

    # Compressione per i 3 agenti finali
    if cfg.compress:
        cc.compress_for_comments()
        cc.compress_for_wiki()
        cc.compress_for_memory()
        log.info("📦 Docs inputs compressi")

    def run_comments():
        run_phase_agent(
            cfg,
            "comments",
            AGENTS_DIR / "agent_comments.md",
            "Aggiungi KDoc/docstring/JSDoc a tutto il codice in "
            "backend/src/ e frontend/src/. Non modificare la logica.",
            allowed_tools="Read,Write",
        )

    def run_wiki():
        run_phase_agent(
            cfg,
            "wiki",
            AGENTS_DIR / "agent_wiki.md",
            "Aggiorna wiki/api.md, wiki/database.md, wiki/architecture.md "
            "e wiki/changelog.md basandoti sui contract files e sui report.",
            allowed_tools="Read,Write",
        )

    def run_memory():
        run_phase_agent(
            cfg,
            "memory",
            AGENTS_DIR / "agent_memory.md",
            "Aggiorna il knowledge vault Obsidian in vault/ basandoti sui "
            "contract files, sui report e sul task_plan. Crea/aggiorna note "
            "per entità, endpoint, ADR, pattern e una nota di sintesi del run "
            "corrente. Aggiorna vault/index.md e produci "
            "vault/_context_for_next_run.md.",
            allowed_tools="Read,Write",
        )

    threads = [
        threading.Thread(target=run_comments, name="AgentComments"),
        threading.Thread(target=run_wiki, name="AgentWiki"),
        threading.Thread(target=run_memory, name="AgentMemory"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if cfg.git:
        git_commit_phase(
            "docs",
            [Path("backend"), Path("frontend"), Path("wiki"), VAULT],
            cycle,
        )


# ─── Setup directory ──────────────────────────────────────────────────────────


def ensure_directories() -> None:
    """Crea le directory necessarie se non esistono."""
    for d in [
        CONTRACTS, TASKS, REPORTS, VAULT,
        Path("wiki"), Path("db/migrations"),
        Path("backend/src"), Path("frontend/src"),
    ]:
        d.mkdir(parents=True, exist_ok=True)


# ─── Config loader ────────────────────────────────────────────────────────────


def load_config_file(path: Path) -> dict:
    """
    Carica config opzionale (YAML o JSON).
    Atteso formato:
        timeouts:
          be: 900
          fe: 600
        max_retries: 3
    """
    if not path.exists():
        return {}
    try:
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore
            except ImportError:
                log.error("PyYAML non installato, usa JSON o `pip install pyyaml`")
                return {}
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        else:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.error("Errore lettura config %s: %s", path, e)
        return {}


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-agent dev pipeline")
    parser.add_argument("--requirements", required=True,
                        help="Path al file requirements.md")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help=f"Max retry dopo errori QA (default: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Salta test (solo review statica)")
    parser.add_argument("--skip-security", action="store_true",
                        help="Salta security audit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Valida task_plan senza chiamare worker pesanti")
    parser.add_argument("--git", action="store_true",
                        help="Commit per fase su branch pipeline/cycle-N")
    parser.add_argument("--config", type=Path,
                        help="Path a config YAML/JSON con timeouts/models/budget")
    parser.add_argument("--no-compress", action="store_true",
                        help="Disabilita compressione contract files (debug)")
    parser.add_argument("--keep-compressed", action="store_true",
                        help="Non rimuovere contracts/_compressed/ a fine pipeline")
    parser.add_argument("--max-budget-usd", type=float, default=None,
                        help="Budget USD massimo per ogni agente")
    parser.add_argument("--max-turns", type=int, default=None,
                        help="Massimo turni agentici per agente")
    args = parser.parse_args()

    requirements = Path(args.requirements)
    if not requirements.exists():
        log.error("File requisiti non trovato: %s", requirements)
        return 1

    # Build config
    cfg = PipelineConfig(
        requirements=requirements,
        max_retries=args.max_retries,
        skip_tests=args.skip_tests,
        skip_security=args.skip_security,
        dry_run=args.dry_run,
        git=args.git,
        compress=not args.no_compress,
        max_budget_usd=args.max_budget_usd,
        max_turns=args.max_turns,
    )

    if args.config:
        ext_cfg = load_config_file(args.config)
        if "timeouts" in ext_cfg:
            cfg.timeouts.update(ext_cfg["timeouts"])
        if "models" in ext_cfg:
            cfg.models.update(ext_cfg["models"])
        if "max_retries" in ext_cfg:
            cfg.max_retries = ext_cfg["max_retries"]
        if "max_budget_usd" in ext_cfg and cfg.max_budget_usd is None:
            cfg.max_budget_usd = ext_cfg["max_budget_usd"]
        if "max_turns" in ext_cfg and cfg.max_turns is None:
            cfg.max_turns = ext_cfg["max_turns"]
        if "compress" in ext_cfg and not args.no_compress:
            cfg.compress = ext_cfg["compress"]

    ensure_directories()

    log.info("🚀 Avvio pipeline multi-agent")
    log.info("   Requisiti:    %s", cfg.requirements)
    log.info("   Max retry:    %s", cfg.max_retries)
    log.info("   Dry-run:      %s", cfg.dry_run)
    log.info("   Git:          %s", cfg.git)
    log.info("   Skip tests:   %s", cfg.skip_tests)
    log.info("   Skip security:%s", cfg.skip_security)
    log.info("   Compress:     %s", cfg.compress)
    log.info("   Budget USD:   %s", cfg.max_budget_usd)
    log.info("   Max turns:    %s", cfg.max_turns)
    log.info("   Models:       %s", cfg.models)

    cycle = 0
    while cycle <= cfg.max_retries:
        if cycle > 0:
            phase_banner("RETRY", f"Ciclo {cycle}/{cfg.max_retries} dopo errori QA")

        if not phase_0_orchestrator(cfg, retry_cycle=cycle):
            log.error("❌ FASE 0 fallita. Aborting.")
            return 1

        if not phase_1_database(cfg, cycle):
            log.error("❌ FASE 1 fallita. Aborting.")
            return 1

        if not phase_2_backend_frontend(cfg, cycle):
            log.error("❌ FASE 2 fallita. Aborting.")
            return 1

        if phase_3_qa(cfg, cycle):
            break

        cycle += 1
        if cycle > cfg.max_retries:
            phase_banner(
                "ABORT",
                f"QA fallito dopo {cfg.max_retries} retry. Pipeline interrotto.",
            )
            log.error("Controlla reports/static_review.json e reports/test_report.json")
            return 1

    phase_4_docs(cfg, cycle)

    # Cleanup file compressi (a meno di --keep-compressed per debug)
    if cfg.compress and not args.keep_compressed:
        cc.cleanup_compressed()
        log.debug("Cleanup file compressi completato")

    phase_banner("DONE", "✅ Pipeline completato con successo!")
    log.info("Output generati:")
    log.info("  - db/migrations/      → SQL migration")
    log.info("  - backend/src/        → codice backend")
    log.info("  - frontend/src/       → codice frontend")
    log.info("  - wiki/               → documentazione")
    log.info("  - vault/              → knowledge vault Obsidian")
    log.info("  - contracts/          → api_contract.json, db_contract.json")
    log.info("  - reports/            → static_review.json, test_report.json")
    log.info("  - pipeline.log        → log di esecuzione")
    return 0


if __name__ == "__main__":
    sys.exit(main())
