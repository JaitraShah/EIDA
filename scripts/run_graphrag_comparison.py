"""
Phase 3.2 — GraphRAG comparison, run end-to-end (EDIA_Project_Plan_v2.md Sec. 3.2).

Microsoft GraphRAG (`graphrag==3.2.0`, installed in its own venv `.venv-graphrag`
so its dependency pins cannot disturb the main environment) is run off the shelf
on each of the 5 gold meetings -- the only meetings with hand-built reasoning
ground truth, so the only ones where completeness can be scored:

  1. one GraphRAG workspace per meeting (default `graphrag init` config and prompts;
     only the model endpoint is changed), transcript as a single text document
  2. `graphrag index` (standard method)
  3. `graphrag query --method local` with the plan's own query
  4. the prose answer is restructured into EDIA's record schema by ONE fixed,
     deterministic mistral call that is told to restate, never add (see CONVERT_*)
  5. scored with the same `score_extraction` as EDIA and multi-hop, at the same
     thresholds: lexical 0.45 and semantic 0.55

Same model as every other row (mistral via Ollama's OpenAI-compatible endpoint,
temperature 0, seed 0) so Table 4 compares methods, not models. Embeddings use
`nomic-embed-text` via Ollama -- GraphRAG needs a vector store and Ollama cannot
serve the sentence-transformer used elsewhere; embeddings affect retrieval only.

Hallucination is not reported for this row: the answer is a summary, not quotes,
so evidence grounding has nothing to check (evidence is left empty by design).

    python scripts/run_graphrag_comparison.py                 # all 5 gold meetings
    python scripts/run_graphrag_comparison.py --only QSUM_003 # one meeting
    python scripts/run_graphrag_comparison.py --rescore-only  # reuse cached answers

Workspaces (large: cache, parquet, lancedb) live in outputs/graphrag_ws/ (git-
ignored); per-meeting answers + records are cached in outputs/graphrag_answers/
and results in outputs/graphrag_results.{md,json}.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edia.benchmark.qmsum_ground_truth import GROUND_TRUTH
from edia.benchmark.score import SemanticMatcher, score_extraction
from edia.extraction.extractor import coerce_record, extract_json_object
from edia.extraction.llm_client import OllamaClient
from edia.extraction.prompts import OUTPUT_CONTRACT
from edia.extraction.schema import ExtractionResult

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "qmsum"
# `python -m graphrag`, not graphrag.exe: console-script launchers hard-code the
# venv path and break if the repo folder is moved; the interpreter does not.
GR = [str(ROOT / ".venv-graphrag" / "Scripts" / "python.exe"), "-m", "graphrag"]
WS_DIR = ROOT / "outputs" / "graphrag_ws"
ANSWER_DIR = ROOT / "outputs" / "graphrag_answers"
REPORT_MD = ROOT / "outputs" / "graphrag_results.md"
REPORT_JSON = ROOT / "outputs" / "graphrag_results.json"

OLLAMA_V1 = "http://localhost:11434/v1"
CHAT_MODEL = "mistral"
EMBED_MODEL = "nomic-embed-text"
# Matches edia.extraction.llm_client.DETERMINISTIC_OPTIONS as far as the
# OpenAI-compatible API allows (top_k / num_ctx are not exposed there).
CALL_ARGS = {"temperature": 0.0, "top_p": 1.0, "seed": 0}

# The plan's query, verbatim (EDIA_Project_Plan_v2.md Sec. 3.2).
QUERY = "What decisions were made and what reasoning was given?"

LEX_THRESHOLD = 0.45   # run_qmsum_eval.py default -- EDIA's 33.3% lexical
SEM_THRESHOLD = 0.55   # EDIA's 58.3% semantic (runbook Sec. 4.2b)

CONVERT_SYSTEM = """\
You restructure a written answer into JSON. The answer was produced by another \
system describing the decisions made in a meeting. You return a single JSON object \
and nothing else.

Absolute rules:
- Restate ONLY what the answer says. Never add, infer, or complete anything the \
answer does not state. An empty field is a correct answer.
- One entry per distinct decision the answer describes.
- "evidence" must always be an empty list: the answer is a summary, not a transcript.
- If the answer describes no decisions, return {"decisions": []}.\
"""

CONVERT_USER = """\
{contract}

Answer to restructure:
<<<
{answer}
>>>"""


def load_text(pair_id: str) -> str:
    raw = json.loads((DATA / f"{pair_id}_transcript.json").read_text(encoding="utf-8"))
    turns = raw.get("meeting_transcripts", raw) if isinstance(raw, dict) else raw
    return "\n".join(
        f"{(t.get('speaker') or '').strip()}: {(t.get('content') or t.get('text') or '').strip()}"
        for t in turns
    )


def _run(cmd: list[str], log: Path) -> str:
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=ROOT)
        fh.write(proc.stdout)
        fh.write(proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[3]} failed (exit {proc.returncode}); see {log}")
    return proc.stdout


def setup_workspace(pair_id: str) -> Path:
    ws = WS_DIR / pair_id
    if not (ws / "settings.yaml").exists():
        ws.mkdir(parents=True, exist_ok=True)
        subprocess.run([*GR, "init", "--root", str(ws), "--model", CHAT_MODEL,
                        "--embedding", EMBED_MODEL, "--force"],
                       check=True, capture_output=True, cwd=ROOT)
        cfg = yaml.safe_load((ws / "settings.yaml").read_text(encoding="utf-8"))
        for section in ("completion_models", "embedding_models"):
            for model in cfg[section].values():
                model["api_base"] = OLLAMA_V1
        cfg["completion_models"]["default_completion_model"]["call_args"] = dict(CALL_ARGS)
        (ws / "settings.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        (ws / ".env").write_text("GRAPHRAG_API_KEY=ollama\n", encoding="utf-8")
    inp = ws / "input"
    inp.mkdir(exist_ok=True)
    (inp / f"{pair_id}.txt").write_text(load_text(pair_id), encoding="utf-8")
    return ws


def graphrag_answer(pair_id: str) -> dict:
    cache = ANSWER_DIR / f"{pair_id}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    ws = setup_workspace(pair_id)
    log = ws / "run.log"
    t0 = time.time()
    if not (ws / "output" / "entities.parquet").exists():
        _run([*GR, "index", "--root", str(ws)], log)
    t_index = time.time() - t0
    answer = _run([*GR, "query", "--root", str(ws), "--method", "local", QUERY], log)
    payload = {"pair_id": pair_id, "query": QUERY, "method": "local",
               "answer": answer.strip(), "index_seconds": round(t_index, 1),
               "total_seconds": round(time.time() - t0, 1)}
    ANSWER_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def convert(pair_id: str, payload: dict, client: OllamaClient) -> ExtractionResult:
    if "records" not in payload:
        resp = client.chat_json(CONVERT_SYSTEM, CONVERT_USER.format(
            contract=OUTPUT_CONTRACT, answer=payload["answer"]))
        payload["records"] = extract_json_object(resp.text).get("decisions") or []
        (ANSWER_DIR / f"{pair_id}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    records = []
    for n, raw in enumerate(payload["records"], start=1):
        if not isinstance(raw, dict) or not str(raw.get("decision") or "").strip():
            continue
        raw = {**raw, "evidence": []}  # summary, not transcript -- see module docstring
        records.append(coerce_record(raw, decision_id=f"graphrag_{pair_id}_d{n}",
                                     source_id=pair_id, chunk_id=f"graphrag_{pair_id}"))
    return ExtractionResult(source_id=pair_id, model_name=f"graphrag-local:{CHAT_MODEL}",
                            records=records, merged_across_chunks=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="run a single pair id, e.g. QSUM_003")
    ap.add_argument("--rescore-only", action="store_true",
                    help="no GraphRAG / model calls; score cached answers only")
    args = ap.parse_args(argv)

    truths = [t for t in GROUND_TRUTH if not args.only or t.pair_id == args.only]
    client = OllamaClient(model=CHAT_MODEL, timeout=1200)
    matcher = SemanticMatcher()

    rows = []
    for truth in truths:
        cache = ANSWER_DIR / f"{truth.pair_id}.json"
        if args.rescore_only and not cache.exists():
            print(f"{truth.pair_id}: no cached answer, skipped")
            continue
        payload = graphrag_answer(truth.pair_id)
        result = convert(truth.pair_id, payload, client)
        lex = score_extraction(result, truth, threshold=LEX_THRESHOLD)
        sem = score_extraction(result, truth, threshold=SEM_THRESHOLD, semantic=matcher)
        row = {"pair_id": truth.pair_id, "records": len(result.records),
               "gt_total": lex.gt_total,
               "lex_matched": lex.gt_matched, "sem_matched": sem.gt_matched,
               "index_seconds": payload.get("index_seconds")}
        rows.append(row)
        print(f"{truth.pair_id}: {row['records']} records | lex {lex.gt_matched}/{lex.gt_total}"
              f" | sem {sem.gt_matched}/{sem.gt_total}")

    if not rows:
        print("nothing scored")
        return 1
    t = sum(r["gt_total"] for r in rows)
    lex_c = sum(r["lex_matched"] for r in rows) / t
    sem_c = sum(r["sem_matched"] for r in rows) / t

    lines = [
        "# Phase 3.2 — GraphRAG comparison (end-to-end)",
        "",
        f"- GraphRAG 3.2.0, default config/prompts, standard index, `local` search",
        f"- chat model `{CHAT_MODEL}` (temperature 0, seed 0) and embeddings "
        f"`{EMBED_MODEL}`, both via Ollama",
        f"- query (plan Sec. 3.2, verbatim): \"{QUERY}\"",
        "- answer restructured into EDIA's schema by one fixed deterministic mistral call "
        "(restate-only prompt, evidence left empty); scored with `score_extraction`",
        f"- thresholds: lexical {LEX_THRESHOLD}, semantic {SEM_THRESHOLD} "
        "(identical to the EDIA baseline)",
        "",
        "| pair | records | completeness (lex) | completeness (sem) | index time |",
        "|---|--:|--:|--:|--:|",
    ]
    for r in rows:
        g = r["gt_total"]
        lines.append(f"| {r['pair_id']} | {r['records']} | {r['lex_matched']/g:.3f} "
                     f"({r['lex_matched']}/{g}) | {r['sem_matched']/g:.3f} "
                     f"({r['sem_matched']}/{g}) | {r['index_seconds']} s |")
    lines += [f"| **total** | | **{lex_c:.3f}** | **{sem_c:.3f}** | |", "",
              "Hallucination is not reported: the answer is a summary with no quotes to "
              "ground. The restructuring call is a possible source of error in either "
              "direction and should be stated alongside the number.", "",
              "Render Table 4 with:", "",
              f"    python scripts/build_comparison_table.py --graphrag {sem_c:.3f} "
              f"--graphrag-lex {lex_c:.3f} --graphrag-note \"5 gold meetings, local search\""]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"rows": rows, "completeness_lex": lex_c,
                                       "completeness_sem": sem_c}, indent=2), encoding="utf-8")
    print("\n".join(lines[-1:]))
    print(f"wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
