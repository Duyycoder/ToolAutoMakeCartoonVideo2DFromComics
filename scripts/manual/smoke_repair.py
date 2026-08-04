"""Test repair on actual chapters 21 and 22."""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "toolCaoTruyen"))

from translator.ollama_translator import OllamaTranslator
from translator.glossary_manager import GlossaryManager

RAW_DIR = r"F:\programfiles\ToolAutoMakeCartoonVideo2DFromComics\storage\truyen\bang_hoc_tap_hogwarts\raw"

# Load glossary
glossary_mgr = GlossaryManager(root_dir="toolCaoTruyen")
glossary_mgr.load_story_glossary(RAW_DIR)
glossary = glossary_mgr.get_combined_glossary()

# Create translator
translator = OllamaTranslator(model="qwen2.5:7b-instruct")
translator.set_glossary(glossary)
translator.set_genre("khoa_huyen")

def progress(msg):
    print(msg, flush=True)

# Find chapters with MISSING_CHUNK markers
for fname in sorted(os.listdir(RAW_DIR)):
    if not fname.endswith(".md") or " - [VI] " not in fname:
        continue
    fpath = os.path.join(RAW_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    if "[[MISSING_CHUNK:" not in content:
        continue
    
    import re
    markers = list(re.finditer(r"\[\[MISSING_CHUNK:\d+\]\]", content))
    print(f"\n{'='*60}")
    print(f"File: {fname}")
    print(f"Markers found: {len(markers)}")
    
    # Find corresponding report
    # Report is named after the source (Chinese) file, not the translated file
    report_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".translation_report.json")]
    report = None
    report_path = None
    for rf in report_files:
        rp = os.path.join(RAW_DIR, rf)
        with open(rp, "r", encoding="utf-8") as f:
            r = json.load(f)
        if os.path.normpath(r.get("output_file", "")) == os.path.normpath(fpath):
            report = r
            report_path = rp
            break
    
    if not report:
        print(f"  No report found for {fname}, skipping")
        continue
    
    print(f"  Report: {os.path.basename(report_path)}")
    print(f"  Failed chunks in report: {len(report.get('failed_chunks', []))}")
    for fc in report.get("failed_chunks", []):
        print(f"    chunk={fc.get('chunk_index')}, reason={fc.get('reason')}, preview={fc.get('original_text_preview', '')[:40]}...")
        has_orig = bool(fc.get("original_text", "").strip())
        print(f"    has_original_text: {has_orig}")
    
    # Load report into translator
    translator.last_report = report
    translator.last_report_path = report_path
    
    # Run repair
    print("\n  Starting repair...")
    remaining = translator.repair_missing_chunks(
        fpath,
        progress_callback=progress
    )
    print(f"\n  Repair result: {remaining} chunks still failed")
    
    # Check if markers remain
    with open(fpath, "r", encoding="utf-8") as f:
        new_content = f.read()
    new_markers = list(re.finditer(r"\[\[MISSING_CHUNK:\d+\]\]", new_content))
    print(f"  Markers remaining in file: {len(new_markers)}")

print("\nDone!")
