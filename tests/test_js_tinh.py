import os
import re
from pathlib import Path

def test_js_tinh():
    editor_dir = Path("webui/editor")
    js_files = list(editor_dir.glob("*.js"))
    
    # 1. Gather all exports for each module
    exports_by_module = {}
    for path in js_files:
        module_name = path.name
        exports = set()
        content = path.read_text(encoding="utf-8")
        # match `export function X`, `export const X`, `export let X`, `export class X`
        for match in re.finditer(r'export\s+(?:async\s+)?(?:function|const|let|class)\s+([a-zA-Z0-9_$]+)', content):
            exports.add(match.group(1))
        # match `export { a, b }`
        for match in re.finditer(r'export\s*\{\s*([^}]+)\s*\}', content):
            items = match.group(1).split(',')
            for item in items:
                name = item.strip().split()[0] # handle `a as b` by just taking `a` or `b`? Wait, `export { a }` or `export { a as b }`. Let's just take the exported name, which is the last token if `as` is used. But `export { a as b }` means exported name is `b`. Let's assume simple `export { a, b }`.
                name = item.strip().split()[-1]
                if name:
                    exports.add(name)
        exports_by_module[module_name] = exports

    # extract `tao` keys from store.js
    store_content = (editor_dir / "store.js").read_text(encoding="utf-8")
    # match `export const tao = { ... };` with nested braces
    tao_match = re.search(r'export const tao = (\{(?:[^{}]*|\{(?:[^{}]*|\{[^{}]*\})*\})*\})', store_content)
    tao_keys = set()
    if tao_match:
        for m in re.finditer(r'([a-zA-Z0-9_$]+)\s*:\s*\(', tao_match.group(1)):
            tao_keys.add(m.group(1))
            
    bus_methods = {"on", "off", "emit"}
    
    # get chung.js exports
    chung_exports = exports_by_module.get("chung.js", set())

    # Extract ctx keys
    ctx_keys = set()
    main_content = (editor_dir / "main.js").read_text(encoding="utf-8")
    ctx_match = re.search(r'const ctx = \{([^}]+)\}', main_content)
    if ctx_match:
        for item in ctx_match.group(1).split(','):
            k = item.split(':')[0].strip()
            if k: ctx_keys.add(k)
    for m in re.finditer(r'ctx\.([a-zA-Z0-9_$]+)\s*=', main_content):
        ctx_keys.add(m.group(1))

    # Extract CSS vars
    css_vars = set()
    css_path = editor_dir / "editor.css"
    if css_path.exists():
        for m in re.finditer(r'(--[a-zA-Z0-9_-]+)\s*:', css_path.read_text(encoding="utf-8")):
            css_vars.add(m.group(1))
    html_files = list(Path("webui").glob("*.html"))
    for hf in html_files:
        for m in re.finditer(r'(--[a-zA-Z0-9_-]+)\s*:', hf.read_text(encoding="utf-8")):
            css_vars.add(m.group(1))

    errors = []
    
    for path in js_files:
        module_name = path.name
        lines = path.read_text(encoding="utf-8").splitlines()
        
        imported_from_chung = set()
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Check imports: import { a, b as c } from './m.js'
            for import_match in re.finditer(r'import\s*\{\s*([^}]+)\s*\}\s*from\s*[\'"]\.\/([^"^\']+\.js)[\'"]', line):
                imported_items = import_match.group(1)
                source_module = import_match.group(2)
                
                source_exports = exports_by_module.get(source_module, set())
                for item in imported_items.split(','):
                    item = item.strip()
                    if not item: continue
                    parts = item.split(' as ')
                    original_name = parts[0].strip()
                    
                    if source_module == "chung.js":
                        local_name = parts[1].strip() if len(parts) > 1 else original_name
                        imported_from_chung.add(local_name)
                    
                    if original_name not in source_exports:
                        errors.append(f"{module_name}:{line_num}: '{original_name}' không được export từ '{source_module}'")
            
            # Check tao.<ten>(
            for tao_call_match in re.finditer(r'\btao\.([a-zA-Z0-9_$]+)\s*\(', line):
                method_name = tao_call_match.group(1)
                if method_name not in tao_keys:
                    errors.append(f"{module_name}:{line_num}: 'tao.{method_name}' không tồn tại trong store.js")
            
            # Check ctx.bus.<ten>( / bus.<ten>(
            for bus_call_match in re.finditer(r'\b(?:ctx\.)?bus\.([a-zA-Z0-9_$]+)\s*\(', line):
                method_name = bus_call_match.group(1)
                if method_name not in bus_methods:
                    errors.append(f"{module_name}:{line_num}: 'bus.{method_name}' không tồn tại")
                    
        # Check usage of chung.js exports without import
        content = path.read_text(encoding="utf-8")
        
        # simple check for local definitions (function X, class X, const X, let X)
        local_defs = set()
        for m in re.finditer(r'\b(?:function|class|const|let)\s+([a-zA-Z0-9_$]+)', content):
            local_defs.add(m.group(1))
            
        for i, line in enumerate(lines):
            line_num = i + 1
            # ignore comments for usage check (simple heuristic)
            if line.strip().startswith("//"): continue
            
            for chung_name in chung_exports:
                if chung_name not in imported_from_chung and chung_name not in local_defs:
                    if re.search(rf'\b{chung_name}\s*\(', line):
                        errors.append(f"{module_name}:{line_num}: Dùng '{chung_name}(' từ chung.js nhưng chưa import")

            # Check ctx.<ten>
            for ctx_match in re.finditer(r'\bctx\.([a-zA-Z0-9_$]+)\b', line):
                key = ctx_match.group(1)
                if key not in ctx_keys:
                    errors.append(f"{module_name}:{line_num}: 'ctx.{key}' không hợp lệ (chưa được khai báo trong main.js)")
                    
            # Check var(--ten)
            for m in re.finditer(r'var\((--[a-zA-Z0-9_-]+)\)', line):
                if m.group(1) not in css_vars:
                    errors.append(f"{module_name}:{line_num}: Biến CSS '{m.group(1)}' chưa được định nghĩa")

    # check in HTML
    for hf in html_files:
        lines = hf.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            for m in re.finditer(r'var\((--[a-zA-Z0-9_-]+)\)', line):
                if m.group(1) not in css_vars:
                    errors.append(f"{hf.name}:{i+1}: Biến CSS '{m.group(1)}' chưa được định nghĩa")

    if errors:
        for e in errors:
            print(e)
        assert False, f"Tìm thấy {len(errors)} lỗi JS tĩnh:\n" + "\n".join(errors)
