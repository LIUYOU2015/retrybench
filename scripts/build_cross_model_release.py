"""Package original collected evidence without editing frozen plans or records."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile


VERIFY = '''"""Verify every distributed byte, then rescore without model calls."""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
expected=json.loads((root/'FILE-HASHES.json').read_text())
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='FILE-HASHES.json' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
if actual!=set(expected):raise SystemExit('Archive file inventory mismatch')
for name,digest in expected.items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise SystemExit('Hash mismatch: '+name)
full=json.loads((root/'full/plan.json').read_text())
for entry in full['prior_run_evidence']:
 path=root/'prior-summaries'/(entry['sha256']+'.json')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise SystemExit('Prior accounting mismatch')
with tempfile.TemporaryDirectory(prefix='retrybench-replay-') as temporary:
 for name in ('pilot-v2','full'):
  env=dict(os.environ,PYTHONPATH=str(root/name/'source'),PYTHONDONTWRITEBYTECODE='1')
  subprocess.run([sys.executable,str(root/'analysis/verify_cross_model_pilot.py'),str(root/name),'--output',str(Path(temporary)/(name+'.json'))],env=env,check=True,cwd=root)
 env=dict(os.environ,PYTHONPATH=str(root/'pilot-v1/source'),PYTHONDONTWRITEBYTECODE='1')
 subprocess.run([sys.executable,str(root/'analysis/verify_stopped.py'),str(root/'pilot-v1')],env=env,check=True,cwd=root)
print('Verified file integrity, full/pilot rescoring, raw arguments/usage and budget accounting. No inference ran.')
'''

STOPPED = '''import json,sys
from pathlib import Path
from retrybench.evaluation import score_predictions
from verify_cross_model_pilot import resolve_attachments
root=Path(sys.argv[1]);summary=json.loads((root/'run/summary.json').read_text())
assert summary['status']=='stopped' and summary['stop_reason']=='invalid normalized decision'
for provider in ('openai','anthropic'):
 base=root/'run'/provider;path=base/'predictions.jsonl'
 rows=[json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
 saved=json.loads((base/'report.json').read_text());new=score_predictions(rows,model=saved['model'],settings=saved['settings'])
 for key in ('suite_sha256','prediction_sha256','metrics','per_condition','per_task','per_block','usage','raw_capture'):assert new.report[key]==saved[key],key
 assert new.cases==[json.loads(s) for s in (base/'case-scores.jsonl').read_text().splitlines()]
 if provider=='openai':
  assert len(rows)==1 and saved['metrics']['status_counts']=={'invalid':1,'missing':239}
  response=resolve_attachments(rows[0]['raw_calls'][0]['response'],rows[0]['transcript_attachments'])
  call=next(x for x in response['output'] if x['type']=='function_call')
  assert json.loads(call['arguments'])=={'action':rows[0]['action'],'idempotency_key':rows[0]['arguments']['idempotency_key']}
 else:assert len(rows)==0
print('Original stopped attempt preserved and independently rescored.')
'''


def build(source_root, output, repository):
    with tempfile.TemporaryDirectory(prefix="retrybench-release-stage-") as temporary:
        stage = Path(temporary)
        runs = {"pilot-v1": "cross-model-pilot-v1-2026-10-19", "pilot-v2": "cross-model-pilot-v2-2026-10-19", "full": "cross-model-full-v1-2026-10-19"}
        for name, folder in runs.items():
            source = source_root / "results" / folder
            target = stage / name
            target.mkdir()
            for leaf in ("plan.json", "cases.jsonl", "requirements-lock.txt", "verification.json"):
                if (source / leaf).exists():
                    shutil.copy2(source / leaf, target / leaf)
            for leaf in ("source", "run"):
                shutil.copytree(source / leaf, target / leaf, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "analysis").mkdir()
        shutil.copy2(repository / "scripts/verify_cross_model_pilot.py", stage / "analysis/verify_cross_model_pilot.py")
        (stage / "analysis/verify_stopped.py").write_text(STOPPED)
        (stage / "verify.py").write_text(VERIFY)
        for name in ("LICENSE", "CITATION.cff"):
            shutil.copy2(repository / name, stage / name)
        shutil.copy2(repository / "docs/cross-model-full-2026-10-19.md", stage / "comparison.md")
        (stage / "README.md").write_text(
            "# RetryBench cross-model evidence v1\n\n"
            "Run `python3 verify.py` from a fresh extraction. Python 3.9+ and its standard library are sufficient; no API keys, provider packages or paid calls are needed.\n\n"
            "The full collection contains 240 fresh responses per model (GPT-5.4 mini snapshot / Claude Sonnet 4.6), using the explicit v2 null-only-unkeyed interface. See comparison.md for exact results and limitations. This is a public reused suite, not a held-out or general-ranking claim.\n\n"
            "full/, pilot-v2/ and pilot-v1/ preserve original plans, raw responses, outputs and collection-source snapshots. pilot-v1/ is the stopped first attempt, not discarded evidence. analysis/ audits native arguments/usage, score replay and the full collection's rolling budget. Original absolute paths remain in frozen provenance; the verifier uses bundled copies and does not require those paths.\n\n"
            "Frozen source snapshots reflect collection-time code; the public package may have later maintenance changes. Dependency locks describe collection, not requirements for offline verification. FILE-HASHES.json covers every distributed file except itself. The existing PolyForm Noncommercial license applies.\n")
        (stage / "prior-summaries").mkdir()
        for entry in json.loads((stage / "full/plan.json").read_text())["prior_run_evidence"]:
            shutil.copy2(Path(entry["path"]), stage / "prior-summaries" / (entry["sha256"] + ".json"))
        hashes = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob("*")) if p.is_file()}
        (stage / "FILE-HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    item = zipfile.ZipInfo(str(path.relative_to(stage)), date_time=(2026, 10, 19, 0, 0, 0))
                    item.compress_type = zipfile.ZIP_DEFLATED
                    item.external_attr = 0o100644 << 16
                    archive.writestr(item, path.read_bytes())
    return {"archive": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "bytes": output.stat().st_size, "files": len(hashes) + 1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_root, args.output, Path(__file__).resolve().parents[1]), indent=2))
