from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from repomap.models import LanguageSummary, ModuleInfo

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "node_modules",
    "dist",
    "build",
    "vendor",
}

LANGUAGE_EXTENSIONS = {
    "Python": {".py", ".pyi", ".pyw"},
    "JavaScript": {".js", ".jsx", ".mjs", ".cjs"},
    "TypeScript": {".ts", ".tsx", ".mts", ".cts"},
    "Go": {".go"},
    "Rust": {".rs"},
    "Java": {".java"},
    "Kotlin": {".kt", ".kts"},
    "Scala": {".scala", ".sc"},
    "Groovy": {".groovy", ".gradle"},
    "C": {".c"},
    "C++": {".cc", ".cpp", ".cxx", ".c++", ".hh", ".hpp", ".hxx", ".ipp", ".inl", ".h"},
    "C#": {".cs", ".csx"},
    "Swift": {".swift"},
    "Objective-C": {".m", ".mm"},
    "PHP": {".php", ".phtml", ".php3", ".php4", ".php5", ".php7", ".php8"},
    "Ruby": {".rb", ".rake", ".gemspec", ".ru"},
    "Perl": {".pl", ".pm", ".t"},
    "Lua": {".lua"},
    "R": {".r"},
    "Julia": {".jl"},
    "Dart": {".dart"},
    "Shell": {".sh", ".bash", ".zsh", ".ksh", ".fish", ".command"},
    "PowerShell": {".ps1", ".psm1", ".psd1"},
    "Batch": {".bat", ".cmd"},
    "Tcl": {".tcl", ".tk"},
    "Elixir": {".ex", ".exs"},
    "Erlang": {".erl", ".hrl"},
    "Haskell": {".hs", ".lhs"},
    "OCaml": {".ml", ".mli", ".mll", ".mly"},
    "F#": {".fs", ".fsi", ".fsx"},
    "Nim": {".nim", ".nims"},
    "Zig": {".zig"},
    "Crystal": {".cr"},
    "Elm": {".elm"},
    "Clojure": {".clj", ".cljs", ".cljc"},
    "Common Lisp": {".lisp", ".lsp", ".cl"},
    "Scheme": {".scm", ".ss"},
    "Racket": {".rkt"},
    "Fortran": {".f", ".f77", ".f90", ".f95", ".f03", ".f08", ".for"},
    "COBOL": {".cob", ".cbl", ".cpy"},
    "Ada": {".adb", ".ads", ".ada"},
    "Pascal": {".pas", ".pp", ".inc"},
    "Visual Basic": {".vb", ".vbs"},
    "D": {".d", ".di"},
    "Solidity": {".sol"},
    "Move": {".move"},
    "V": {".v"},
    "Verilog": {".vh", ".sv", ".svh"},
    "VHDL": {".vhd", ".vhdl"},
    "Assembly": {".asm", ".s"},
    "SQL": {".sql", ".ddl", ".prc"},
    "GraphQL": {".graphql", ".gql"},
    "CSS": {".css", ".scss", ".sass", ".less", ".styl"},
    "HTML": {".html", ".htm", ".xhtml"},
    "XML": {".xml", ".xsd", ".xsl", ".xslt", ".svg"},
    "Vue": {".vue"},
    "Svelte": {".svelte"},
    "Astro": {".astro"},
    "Nix": {".nix"},
    "Starlark": {".bzl"},
    "Terraform": {".tf", ".tfvars"},
    "HCL": {".hcl"},
    "Bicep": {".bicep"},
    "Jsonnet": {".jsonnet", ".libsonnet"},
    "Cue": {".cue"},
    "Rego": {".rego"},
    "Puppet": {".pp"},
    "Raku": {".raku", ".rakumod", ".p6", ".pm6", ".pod6"},
    "Apex": {".cls", ".trigger"},
    "Haxe": {".hx"},
    "ReasonML": {".re", ".rei"},
    "Standard ML": {".sml", ".sig", ".fun"},
    "Awk": {".awk"},
    "AppleScript": {".applescript", ".scpt"},
}

SPECIAL_FILENAMES = {
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    "makefile": "Makefile",
    "cmakelists.txt": "CMake",
    "jenkinsfile": "Groovy",
    "vagrantfile": "Ruby",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "brewfile": "Ruby",
    "podfile": "Ruby",
    "fastfile": "Ruby",
    "build": "Starlark",
    "workspace": "Starlark",
    "build.bazel": "Starlark",
    "workspace.bazel": "Starlark",
    "buck": "Starlark",
    "buck2": "Starlark",
    ".bashrc": "Shell",
    ".bash_profile": "Shell",
    ".bash_login": "Shell",
    ".profile": "Shell",
    ".zshrc": "Shell",
    ".kshrc": "Shell",
}

SHEBANG_LANGUAGE_HINTS = {
    "python": "Python",
    "python3": "Python",
    "node": "JavaScript",
    "deno": "TypeScript",
    "bun": "JavaScript",
    "bash": "Shell",
    "sh": "Shell",
    "zsh": "Shell",
    "ksh": "Shell",
    "fish": "Shell",
    "pwsh": "PowerShell",
    "powershell": "PowerShell",
    "ruby": "Ruby",
    "perl": "Perl",
    "php": "PHP",
    "lua": "Lua",
    "rscript": "R",
    "julia": "Julia",
    "tclsh": "Tcl",
    "wish": "Tcl",
    "groovy": "Groovy",
}

DEEP_ANALYSIS_LANGUAGES = {
    "Python",
    "JavaScript",
    "TypeScript",
    "Go",
    "Rust",
    "Java",
    "Kotlin",
    "Scala",
    "Groovy",
    "C#",
    "PHP",
    "Swift",
    "C",
    "C++",
    "Objective-C",
    "Ruby",
    "Dart",
    "Lua",
    "Perl",
    "Shell",
}
JS_TS_LANGUAGES = {"JavaScript", "TypeScript"}
JVM_LANGUAGES = {"Java", "Kotlin"}
C_FAMILY_LANGUAGES = {"C", "C++", "Objective-C"}
JS_TS_EXTENSIONS = tuple(
    sorted(
        LANGUAGE_EXTENSIONS["JavaScript"] | LANGUAGE_EXTENSIONS["TypeScript"],
        key=len,
        reverse=True,
    )
)
SORTED_EXTENSION_MATCHES = sorted(
    (
        (extension, language_name)
        for language_name, extensions in LANGUAGE_EXTENSIONS.items()
        for extension in extensions
    ),
    key=lambda item: len(item[0]),
    reverse=True,
)
IMPORT_FROM_RE = re.compile(r"""(?:import|export)\s+(?:[^;]*?\s+from\s+)?["']([^"']+)["']""")
REQUIRE_RE = re.compile(r"""require\(\s*["']([^"']+)["']\s*\)""")
DYNAMIC_IMPORT_RE = re.compile(r"""import\(\s*["']([^"']+)["']\s*\)""")
GO_MODULE_RE = re.compile(r"^\s*module\s+(\S+)\s*$", re.MULTILINE)
GO_SINGLE_IMPORT_RE = re.compile(r'^\s*import\s+"([^"]+)"\s*$', re.MULTILINE)
GO_IMPORT_BLOCK_RE = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
GO_IMPORT_LINE_RE = re.compile(r'^\s*(?:[\w.]+\s+)?"([^"]+)"\s*$', re.MULTILINE)
JAVA_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", re.MULTILINE)
KOTLIN_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
KOTLIN_IMPORT_RE = re.compile(r"^\s*import\s+([\w.*]+)", re.MULTILINE)
SCALA_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
SCALA_IMPORT_RE = re.compile(r"^\s*import\s+([^\n;]+)", re.MULTILINE)
C_SHARP_NAMESPACE_RE = re.compile(r"^\s*(?:file\s+)?namespace\s+([\w.]+)", re.MULTILINE)
C_SHARP_USING_RE = re.compile(r"^\s*(?:global\s+)?using\s+(?:static\s+)?([\w.]+)\s*;", re.MULTILINE)
PHP_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([^;]+);", re.MULTILINE)
PHP_USE_RE = re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE)
PHP_FILE_IMPORT_RE = re.compile(r"""(?:require|require_once|include|include_once)\s*(?:\(\s*)?["']([^"']+)["']""")
RUBY_REQUIRE_RE = re.compile(r"""^\s*require\s+["']([^"']+)["']""", re.MULTILINE)
RUBY_REQUIRE_RELATIVE_RE = re.compile(r"""^\s*require_relative\s+["']([^"']+)["']""", re.MULTILINE)
DART_PACKAGE_NAME_RE = re.compile(r"^\s*name\s*:\s*([A-Za-z0-9_]+)\s*$", re.MULTILINE)
DART_IMPORT_RE = re.compile(r"""^\s*(?:import|export|part)\s+["']([^"']+)["']""", re.MULTILINE)
LUA_REQUIRE_RE = re.compile(r"""require\s*(?:\(\s*)?["']([^"']+)["']\s*\)?""")
PERL_USE_RE = re.compile(r"^\s*use\s+([A-Za-z_]\w*(?:::\w+)*)", re.MULTILINE)
PERL_REQUIRE_RE = re.compile(r"""^\s*require\s+["']([^"']+)["']""", re.MULTILINE)
SHELL_SOURCE_RE = re.compile(r"""^\s*(?:source|\.)\s+["']?([^\s"';&|]+)["']?""", re.MULTILINE)
RUST_USE_RE = re.compile(r"^\s*use\s+(.+?);", re.MULTILINE)
RUST_MOD_RE = re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_]\w*)\s*;", re.MULTILINE)
RUST_CRATE_NAME_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
SWIFT_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_]\w*)", re.MULTILINE)
C_INCLUDE_RE = re.compile(r'^\s*#\s*(?:include|import)\s*([<"])([^">]+)[">]', re.MULTILINE)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        if detect_language(path):
            yield path


def detect_language(path: Path) -> str | None:
    special_name = SPECIAL_FILENAMES.get(path.name.lower())
    if special_name:
        return special_name

    name_lower = path.name.lower()
    for extension, language_name in SORTED_EXTENSION_MATCHES:
        if name_lower.endswith(extension):
            return language_name

    return _detect_language_from_shebang(path)


def build_module_inventory(root: Path) -> tuple[list[ModuleInfo], list[LanguageSummary], str | None]:
    source_files = list(iter_source_files(root))
    language_by_path = {file_path: detect_language(file_path) for file_path in source_files}

    language_counter = Counter()
    extension_counter: dict[str, set[str]] = defaultdict(set)
    for file_path, language in language_by_path.items():
        if not language:
            continue
        language_counter[language] += 1
        extension_counter[language].add(_display_extension(file_path))

    modules: list[ModuleInfo] = []
    analyzed_files: set[Path] = set()

    python_files = [path for path, language in language_by_path.items() if language == "Python"]
    js_ts_files = [path for path, language in language_by_path.items() if language in JS_TS_LANGUAGES]
    go_files = [path for path, language in language_by_path.items() if language == "Go"]
    rust_files = [path for path, language in language_by_path.items() if language == "Rust"]
    java_files = [path for path, language in language_by_path.items() if language == "Java"]
    kotlin_files = [path for path, language in language_by_path.items() if language == "Kotlin"]
    scala_files = [path for path, language in language_by_path.items() if language == "Scala"]
    groovy_files = [path for path, language in language_by_path.items() if language == "Groovy"]
    csharp_files = [path for path, language in language_by_path.items() if language == "C#"]
    php_files = [path for path, language in language_by_path.items() if language == "PHP"]
    ruby_files = [path for path, language in language_by_path.items() if language == "Ruby"]
    dart_files = [path for path, language in language_by_path.items() if language == "Dart"]
    lua_files = [path for path, language in language_by_path.items() if language == "Lua"]
    perl_files = [path for path, language in language_by_path.items() if language == "Perl"]
    shell_files = [path for path, language in language_by_path.items() if language == "Shell"]
    swift_files = [path for path, language in language_by_path.items() if language == "Swift"]
    c_family_files = [path for path, language in language_by_path.items() if language in C_FAMILY_LANGUAGES]

    modules.extend(_analyze_python_modules(root, python_files))
    modules.extend(_analyze_javascript_modules(root, js_ts_files, language_by_path))
    modules.extend(_analyze_go_packages(root, go_files))
    modules.extend(_analyze_rust_modules(root, rust_files))
    modules.extend(_analyze_jvm_modules(root, java_files, "Java"))
    modules.extend(_analyze_jvm_modules(root, kotlin_files, "Kotlin"))
    modules.extend(_analyze_jvm_modules(root, scala_files, "Scala"))
    modules.extend(_analyze_jvm_modules(root, groovy_files, "Groovy"))
    modules.extend(_analyze_csharp_modules(root, csharp_files))
    modules.extend(_analyze_php_modules(root, php_files))
    modules.extend(_analyze_ruby_modules(root, ruby_files))
    modules.extend(_analyze_dart_modules(root, dart_files))
    modules.extend(_analyze_lua_modules(root, lua_files))
    modules.extend(_analyze_perl_modules(root, perl_files))
    modules.extend(_analyze_shell_modules(root, shell_files))
    modules.extend(_analyze_swift_modules(root, swift_files))
    modules.extend(_analyze_c_family_modules(root, c_family_files, language_by_path))

    analyzed_files.update(python_files)
    analyzed_files.update(js_ts_files)
    analyzed_files.update(go_files)
    analyzed_files.update(rust_files)
    analyzed_files.update(java_files)
    analyzed_files.update(kotlin_files)
    analyzed_files.update(scala_files)
    analyzed_files.update(groovy_files)
    analyzed_files.update(csharp_files)
    analyzed_files.update(php_files)
    analyzed_files.update(ruby_files)
    analyzed_files.update(dart_files)
    analyzed_files.update(lua_files)
    analyzed_files.update(perl_files)
    analyzed_files.update(shell_files)
    analyzed_files.update(swift_files)
    analyzed_files.update(c_family_files)

    generic_files = [path for path in source_files if path not in analyzed_files]
    modules.extend(_build_generic_modules(root, generic_files, language_by_path))

    languages = [
        LanguageSummary(
            name=language_name,
            file_count=language_counter[language_name],
            extensions=sorted(extension_counter[language_name]),
        )
        for language_name in sorted(language_counter, key=lambda name: (-language_counter[name], name))
    ]
    primary_language = languages[0].name if languages else None
    modules.sort(key=lambda module: (module.language, module.path))
    return modules, languages, primary_language


def module_name_from_path(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if not parts:
        return root.name
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else root.name


def parse_imports(file_path: Path, module_name: str) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.update(_resolve_python_from_import(node, module_name))
    return imports


def parse_javascript_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    imports = set(IMPORT_FROM_RE.findall(source))
    imports.update(REQUIRE_RE.findall(source))
    imports.update(DYNAMIC_IMPORT_RE.findall(source))
    return imports


def parse_go_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    imports = set(GO_SINGLE_IMPORT_RE.findall(source))
    for block in GO_IMPORT_BLOCK_RE.findall(source):
        imports.update(GO_IMPORT_LINE_RE.findall(block))
    return imports


def read_go_module_name(root: Path) -> str | None:
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return None

    match = GO_MODULE_RE.search(go_mod.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else None


def _analyze_python_modules(root: Path, python_files: list[Path]) -> list[ModuleInfo]:
    module_map = {module_name_from_path(root, file_path): file_path for file_path in python_files}
    id_map = {module_name: f"python:{module_name}" for module_name in module_map}
    modules: list[ModuleInfo] = []

    for module_name, file_path in sorted(module_map.items()):
        raw_imports = sorted(parse_imports(file_path, module_name))
        resolved_modules = {
            _resolve_python_internal_module(import_name, module_map)
            for import_name in raw_imports
        }
        internal_dependencies = sorted(
            id_map[resolved_name]
            for resolved_name in resolved_modules
            if resolved_name and resolved_name != module_name
        )
        external_dependencies = sorted(
            _normalize_python_dependency(import_name)
            for import_name in raw_imports
            if _resolve_python_internal_module(import_name, module_map) is None
        )

        modules.append(
            ModuleInfo(
                id=id_map[module_name],
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="Python",
                imports=raw_imports,
                internal_dependencies=internal_dependencies,
                external_dependencies=sorted(set(external_dependencies)),
            )
        )

    return modules


def _analyze_javascript_modules(
    root: Path,
    script_files: list[Path],
    language_by_path: dict[Path, str | None],
) -> list[ModuleInfo]:
    project_metadata = _build_javascript_project_metadata(root)
    alias_index: dict[str, str] = {}
    path_to_id: dict[Path, str] = {}
    display_by_path: dict[Path, str] = {}

    for file_path in sorted(script_files):
        relative = file_path.relative_to(root)
        base_name = _script_display_name(relative)
        module_id = f"{_language_slug(language_by_path[file_path] or 'script')}:{base_name}"
        resolved_path = file_path.resolve()
        path_to_id[resolved_path] = module_id
        display_by_path[resolved_path] = base_name
        alias_index[base_name] = module_id
        if base_name.endswith("/index"):
            alias_index[base_name[:-6]] = module_id

    modules: list[ModuleInfo] = []
    for file_path in sorted(script_files):
        resolved_path = file_path.resolve()
        module_id = path_to_id[resolved_path]
        display_name = display_by_path[resolved_path]
        language_name = language_by_path[file_path] or "JavaScript"
        raw_imports = sorted(parse_javascript_imports(file_path))

        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in raw_imports:
            resolved = _resolve_javascript_internal_import(
                root,
                file_path,
                import_name,
                path_to_id,
                alias_index,
                project_metadata,
            )
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_javascript_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=display_name,
                path=file_path.relative_to(root).as_posix(),
                language=language_name,
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_go_packages(root: Path, go_files: list[Path]) -> list[ModuleInfo]:
    module_path = read_go_module_name(root)
    package_to_files: dict[Path, list[Path]] = defaultdict(list)
    for file_path in go_files:
        if file_path.name.endswith("_test.go"):
            continue
        package_to_files[file_path.parent].append(file_path)

    package_map: dict[str, tuple[str, str, Path]] = {}
    for package_dir in sorted(package_to_files):
        relative_dir = package_dir.relative_to(root)
        import_path = _go_import_path(module_path, relative_dir)
        package_key = import_path or relative_dir.as_posix() or "."
        module_id = f"go:{relative_dir.as_posix() or 'root'}"
        display_name = import_path or relative_dir.as_posix() or "root"
        package_map[package_key] = (module_id, display_name, package_dir)

    modules: list[ModuleInfo] = []
    for package_key, (module_id, display_name, package_dir) in sorted(package_map.items()):
        imports: set[str] = set()
        for file_path in package_to_files[package_dir]:
            imports.update(parse_go_imports(file_path))

        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()
        for import_name in sorted(imports):
            resolved = _resolve_go_internal_import(import_name, package_map)
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_go_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=display_name,
                path=(package_dir.relative_to(root).as_posix() or "."),
                language="Go",
                imports=sorted(imports),
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_rust_modules(root: Path, rust_files: list[Path]) -> list[ModuleInfo]:
    crate_name = _read_rust_crate_name(root) or root.name.replace("-", "_")
    module_name_by_file = {file_path: _rust_module_name(root, file_path, crate_name) for file_path in rust_files}
    id_by_name = {
        module_name: f"rust:{file_path.relative_to(root).with_suffix('').as_posix()}"
        for file_path, module_name in module_name_by_file.items()
    }
    modules: list[ModuleInfo] = []

    for file_path in sorted(rust_files):
        module_name = module_name_by_file[file_path]
        module_id = id_by_name[module_name]
        raw_imports = sorted(_parse_rust_imports(file_path))
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in raw_imports:
            resolved = _resolve_rust_internal_import(import_name, module_name, crate_name, id_by_name)
            if resolved:
                internal_dependencies.update(dep for dep in resolved if dep != module_id)
            else:
                normalized = _normalize_rust_dependency(import_name, crate_name)
                if normalized:
                    external_dependencies.add(normalized)

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="Rust",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_jvm_modules(root: Path, files: list[Path], language_name: str) -> list[ModuleInfo]:
    if not files:
        return []

    metadata: dict[Path, tuple[str, list[str]]] = {}
    name_to_id: dict[str, str] = {}
    for file_path in sorted(files):
        package_name, imports = _parse_jvm_metadata(file_path, language_name)
        module_name = _jvm_module_name(root, file_path, package_name)
        metadata[file_path] = (module_name, imports)
        name_to_id[module_name] = f"{_language_slug(language_name)}:{file_path.relative_to(root).with_suffix('').as_posix()}"

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_name, imports = metadata[file_path]
        module_id = name_to_id[module_name]
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()
        for import_name in sorted(set(imports)):
            resolved = _resolve_dotted_internal_import(import_name, name_to_id)
            if resolved:
                internal_dependencies.update(dep for dep in resolved if dep != module_id)
            else:
                external_dependencies.add(_normalize_dotted_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language=language_name,
                imports=sorted(set(imports)),
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_csharp_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    metadata: dict[Path, tuple[str, list[str]]] = {}
    name_to_id: dict[str, str] = {}

    for file_path in sorted(files):
        namespace_name, imports = _parse_csharp_metadata(file_path)
        module_name = _namespaced_file_name(root, file_path, namespace_name)
        metadata[file_path] = (module_name, imports)
        name_to_id[module_name] = f"c-sharp:{file_path.relative_to(root).with_suffix('').as_posix()}"

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_name, imports = metadata[file_path]
        module_id = name_to_id[module_name]
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()
        for import_name in sorted(set(imports)):
            resolved = _resolve_dotted_internal_import(import_name, name_to_id)
            if resolved:
                internal_dependencies.update(dep for dep in resolved if dep != module_id)
            else:
                external_dependencies.add(_normalize_dotted_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="C#",
                imports=sorted(set(imports)),
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_php_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    metadata: dict[Path, tuple[str, list[str], list[str]]] = {}
    name_to_id: dict[str, str] = {}
    path_alias_index: dict[str, str] = {}

    for file_path in sorted(files):
        namespace_name, namespace_imports, file_imports = _parse_php_metadata(file_path)
        module_name = _namespaced_file_name(root, file_path, namespace_name, separator="\\")
        metadata[file_path] = (module_name, namespace_imports, file_imports)
        module_id = f"php:{file_path.relative_to(root).with_suffix('').as_posix()}"
        name_to_id[module_name] = module_id
        path_alias_index[file_path.relative_to(root).with_suffix('').as_posix()] = module_id
        path_alias_index[file_path.relative_to(root).as_posix()] = module_id

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_name, namespace_imports, file_imports = metadata[file_path]
        module_id = name_to_id[module_name]
        raw_imports = sorted(set(namespace_imports + file_imports))
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in namespace_imports:
            resolved = _resolve_php_namespace_import(import_name, name_to_id)
            if resolved:
                internal_dependencies.update(dep for dep in resolved if dep != module_id)
            else:
                external_dependencies.add(_normalize_php_dependency(import_name))

        for import_name in file_imports:
            resolved = _resolve_path_like_import(root, file_path, import_name, path_alias_index, (".php",))
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(import_name)

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="PHP",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_ruby_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    alias_index: dict[str, str] = {}
    metadata: dict[Path, tuple[list[str], list[str]]] = {}

    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = f"ruby:{relative_stem}"
        alias_index[relative_stem] = module_id
        alias_index[file_path.relative_to(root).as_posix()] = module_id
        alias_index[file_path.name] = module_id
        alias_index[file_path.stem] = module_id
        metadata[file_path] = _parse_ruby_imports(file_path)

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = alias_index[relative_stem]
        require_imports, require_relative_imports = metadata[file_path]
        raw_imports = sorted(set(require_imports + require_relative_imports))
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in require_relative_imports:
            resolved = _resolve_path_like_import(root, file_path, import_name, alias_index, (".rb",))
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(import_name)

        for import_name in require_imports:
            resolved = alias_index.get(import_name) or alias_index.get(import_name.removesuffix(".rb"))
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            else:
                external_dependencies.add(_normalize_path_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=relative_stem,
                path=file_path.relative_to(root).as_posix(),
                language="Ruby",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_dart_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    if not files:
        return []

    package_name = _read_dart_package_name(root)
    alias_index: dict[str, str] = {}
    metadata: dict[Path, list[str]] = {}

    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = f"dart:{relative_stem}"
        alias_index[relative_stem] = module_id
        alias_index[file_path.relative_to(root).as_posix()] = module_id
        metadata[file_path] = sorted(_parse_dart_imports(file_path))

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = alias_index[relative_stem]
        raw_imports = metadata[file_path]
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in raw_imports:
            resolved = _resolve_dart_internal_import(root, file_path, import_name, alias_index, package_name)
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_dart_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=relative_stem,
                path=file_path.relative_to(root).as_posix(),
                language="Dart",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_lua_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    if not files:
        return []

    module_name_to_id: dict[str, str] = {}
    metadata: dict[Path, list[str]] = {}
    for file_path in sorted(files):
        module_name = _lua_module_name(root, file_path)
        module_name_to_id[module_name] = f"lua:{file_path.relative_to(root).with_suffix('').as_posix()}"
        metadata[file_path] = sorted(_parse_lua_imports(file_path))

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_name = _lua_module_name(root, file_path)
        module_id = module_name_to_id[module_name]
        raw_imports = metadata[file_path]
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in raw_imports:
            resolved = _resolve_lua_internal_import(import_name, module_name_to_id)
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_path_dependency(import_name.replace(".", "/")))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="Lua",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_perl_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    if not files:
        return []

    metadata: dict[Path, tuple[list[str], list[str]]] = {}
    namespace_to_id: dict[str, str] = {}
    path_alias_index: dict[str, str] = {}
    normalized_namespace_to_id: dict[str, str] = {}

    for file_path in sorted(files):
        module_name = _perl_module_name(root, file_path)
        module_id = f"perl:{file_path.relative_to(root).with_suffix('').as_posix()}"
        namespace_to_id[module_name] = module_id
        normalized_namespace_to_id[module_name.replace("::", ".")] = module_id
        path_alias_index[file_path.relative_to(root).with_suffix('').as_posix()] = module_id
        path_alias_index[file_path.relative_to(root).as_posix()] = module_id
        metadata[file_path] = _parse_perl_imports(file_path)

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_name = _perl_module_name(root, file_path)
        module_id = namespace_to_id[module_name]
        namespace_imports, file_imports = metadata[file_path]
        raw_imports = sorted(set(namespace_imports + file_imports))
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in namespace_imports:
            resolved = _resolve_dotted_internal_import(import_name.replace("::", "."), normalized_namespace_to_id)
            if resolved:
                internal_dependencies.update(dep for dep in resolved if dep != module_id)
            else:
                external_dependencies.add(_normalize_perl_dependency(import_name))

        for import_name in file_imports:
            resolved = _resolve_path_like_import(root, file_path, import_name, path_alias_index, (".pm", ".pl", ".t"))
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(import_name)

        modules.append(
            ModuleInfo(
                id=module_id,
                name=module_name,
                path=file_path.relative_to(root).as_posix(),
                language="Perl",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_shell_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    if not files:
        return []

    alias_index: dict[str, str] = {}
    metadata: dict[Path, list[str]] = {}

    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = f"shell:{relative_stem}"
        alias_index[relative_stem] = module_id
        alias_index[file_path.relative_to(root).as_posix()] = module_id
        alias_index[file_path.name] = module_id
        metadata[file_path] = sorted(_parse_shell_imports(file_path))

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = alias_index[relative_stem]
        raw_imports = metadata[file_path]
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()

        for import_name in raw_imports:
            resolved = _resolve_path_like_import(
                root,
                file_path,
                import_name,
                alias_index,
                ("", ".sh", ".bash", ".zsh", ".ksh", ".fish"),
            )
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_path_dependency(import_name))

        modules.append(
            ModuleInfo(
                id=module_id,
                name=relative_stem,
                path=file_path.relative_to(root).as_posix(),
                language="Shell",
                imports=raw_imports,
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _analyze_swift_modules(root: Path, files: list[Path]) -> list[ModuleInfo]:
    target_to_files: dict[str, list[Path]] = defaultdict(list)
    for file_path in files:
        target_to_files[_swift_target_name(root, file_path)].append(file_path)

    modules: list[ModuleInfo] = []
    target_to_id = {target_name: f"swift:{target_name}" for target_name in target_to_files}
    for target_name, target_files in sorted(target_to_files.items()):
        imports: set[str] = set()
        for file_path in target_files:
            imports.update(_parse_swift_imports(file_path))

        internal_dependencies = sorted(
            target_to_id[import_name]
            for import_name in imports
            if import_name in target_to_id and target_to_id[import_name] != target_to_id[target_name]
        )
        external_dependencies = sorted(import_name for import_name in imports if import_name not in target_to_id)

        modules.append(
            ModuleInfo(
                id=target_to_id[target_name],
                name=target_name,
                path=_swift_target_path(root, target_files[0]),
                language="Swift",
                imports=sorted(imports),
                internal_dependencies=internal_dependencies,
                external_dependencies=external_dependencies,
            )
        )

    return modules


def _analyze_c_family_modules(
    root: Path,
    files: list[Path],
    language_by_path: dict[Path, str | None],
) -> list[ModuleInfo]:
    alias_index: dict[str, str] = {}
    path_to_id: dict[Path, str] = {}
    for file_path in sorted(files):
        relative_stem = file_path.relative_to(root).with_suffix("").as_posix()
        module_id = f"{_language_slug(language_by_path[file_path] or 'c-family')}:{relative_stem}"
        path_to_id[file_path.resolve()] = module_id
        alias_index[file_path.relative_to(root).as_posix()] = module_id
        alias_index[relative_stem] = module_id
        alias_index[file_path.name] = module_id
        alias_index[file_path.stem] = module_id

    modules: list[ModuleInfo] = []
    for file_path in sorted(files):
        module_id = path_to_id[file_path.resolve()]
        imports = _parse_c_family_imports(file_path)
        internal_dependencies: set[str] = set()
        external_dependencies: set[str] = set()
        for import_name, is_local in imports:
            resolved = _resolve_c_family_import(root, file_path, import_name, alias_index)
            if resolved and resolved != module_id:
                internal_dependencies.add(resolved)
            elif not resolved:
                external_dependencies.add(_normalize_path_dependency(import_name) if is_local else import_name.split("/", 1)[0])

        modules.append(
            ModuleInfo(
                id=module_id,
                name=file_path.relative_to(root).with_suffix("").as_posix(),
                path=file_path.relative_to(root).as_posix(),
                language=language_by_path[file_path] or "C++",
                imports=[import_name for import_name, _is_local in imports],
                internal_dependencies=sorted(internal_dependencies),
                external_dependencies=sorted(external_dependencies),
            )
        )

    return modules


def _build_generic_modules(
    root: Path,
    source_files: list[Path],
    language_by_path: dict[Path, str | None],
) -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    for file_path in sorted(source_files):
        language_name = language_by_path[file_path]
        if not language_name:
            continue
        relative_path = file_path.relative_to(root).as_posix()
        module_id = f"{_language_slug(language_name)}:{relative_path}"
        modules.append(
            ModuleInfo(
                id=module_id,
                name=relative_path,
                path=relative_path,
                language=language_name,
                imports=[],
                internal_dependencies=[],
                external_dependencies=[],
            )
        )
    return modules


def _package_for_module(module_name: str) -> str:
    if not module_name:
        return ""
    parts = module_name.split(".")
    if len(parts) == 1:
        return module_name
    return ".".join(parts[:-1])


def _resolve_relative_base(module_name: str, level: int) -> str:
    package = _package_for_module(module_name)
    package_parts = [part for part in package.split(".") if part]
    if level <= 0:
        return package
    if level > len(package_parts):
        return ""
    return ".".join(package_parts[: len(package_parts) - level + 1])


def _resolve_python_from_import(node: ast.ImportFrom, module_name: str) -> set[str]:
    imports: set[str] = set()

    if node.level == 0:
        base = node.module or ""
    else:
        relative_base = _resolve_relative_base(module_name, node.level)
        if node.module:
            base = ".".join(part for part in [relative_base, node.module] if part)
        else:
            base = relative_base

    if base:
        imports.add(base)

    for alias in node.names:
        if alias.name == "*":
            continue
        if base:
            imports.add(f"{base}.{alias.name}")
        else:
            imports.add(alias.name)

    return imports


def _resolve_python_internal_module(import_name: str, module_map: dict[str, Path]) -> str | None:
    if import_name in module_map:
        return import_name

    parts = import_name.split(".")
    for index in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in module_map:
            return candidate

    return None


def _normalize_python_dependency(import_name: str) -> str:
    return import_name.split(".", 1)[0]


def _resolve_javascript_internal_import(
    root: Path,
    file_path: Path,
    import_name: str,
    path_to_id: dict[Path, str],
    alias_index: dict[str, str],
    project_metadata: dict[str, object],
) -> str | None:
    normalized_import = import_name.replace("\\", "/")

    if normalized_import.startswith(("@/", "~/")):
        candidate_base = root / normalized_import[2:]
    elif normalized_import.startswith("/"):
        candidate_base = root / normalized_import.lstrip("/")
    elif normalized_import.startswith("."):
        candidate_base = (file_path.parent / normalized_import).resolve()
    else:
        candidate_base = root / normalized_import

    resolved_path = _resolve_javascript_path(candidate_base)
    if resolved_path and resolved_path in path_to_id:
        return path_to_id[resolved_path]

    alias_key = candidate_base.relative_to(root).as_posix() if candidate_base.is_relative_to(root) else None
    if alias_key and alias_key in alias_index:
        return alias_index[alias_key]

    normalized_key = normalized_import.lstrip("./")
    if normalized_key in alias_index:
        return alias_index[normalized_key]

    for candidate_base in _resolve_javascript_monorepo_candidates(root, normalized_import, project_metadata):
        resolved_path = _resolve_javascript_path(candidate_base)
        if resolved_path and resolved_path in path_to_id:
            return path_to_id[resolved_path]
        alias_key = candidate_base.relative_to(root).as_posix() if candidate_base.is_relative_to(root) else None
        if alias_key and alias_key in alias_index:
            return alias_index[alias_key]

    return None


def _resolve_javascript_path(candidate_base: Path) -> Path | None:
    candidates = [candidate_base]
    if candidate_base.suffix:
        candidates.append(candidate_base.with_suffix(""))

    base_without_suffix = candidate_base if not candidate_base.suffix else candidate_base.with_suffix("")
    for extension in JS_TS_EXTENSIONS:
        candidates.append(base_without_suffix.with_suffix(extension))

    if candidate_base.is_dir() or not candidate_base.suffix:
        for extension in JS_TS_EXTENSIONS:
            candidates.append(candidate_base / f"index{extension}")

    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        if normalized.exists() and normalized.is_file():
            return normalized

    return None


def _normalize_javascript_dependency(import_name: str) -> str:
    if import_name.startswith("@"):
        parts = import_name.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else import_name
    return import_name.split("/", 1)[0]


def _build_javascript_project_metadata(root: Path) -> dict[str, object]:
    package_dirs = _discover_workspace_package_dirs(root)
    workspace_packages: dict[str, Path] = {}
    for package_dir in package_dirs:
        package_json = package_dir / "package.json"
        if not package_json.exists():
            continue
        package_data = _read_json_file(package_json)
        package_name = package_data.get("name")
        if isinstance(package_name, str) and package_name.strip():
            workspace_packages[package_name.strip()] = package_dir

    tsconfig_data = _read_json_file(root / "tsconfig.json") or _read_json_file(root / "jsconfig.json")
    compiler_options = tsconfig_data.get("compilerOptions", {}) if isinstance(tsconfig_data, dict) else {}
    base_url_value = compiler_options.get("baseUrl") if isinstance(compiler_options, dict) else None
    base_url = (root / base_url_value).resolve() if isinstance(base_url_value, str) and base_url_value else root
    raw_paths = compiler_options.get("paths") if isinstance(compiler_options, dict) else {}
    tsconfig_paths = raw_paths if isinstance(raw_paths, dict) else {}

    return {
        "workspace_packages": workspace_packages,
        "tsconfig_base_url": base_url,
        "tsconfig_paths": tsconfig_paths,
    }


def _discover_workspace_package_dirs(root: Path) -> list[Path]:
    patterns = _discover_workspace_patterns(root)
    if not patterns:
        return []

    package_dirs: list[Path] = []
    for pattern in patterns:
        package_dirs.extend(path for path in root.glob(pattern) if path.is_dir())
    return sorted(set(package_dirs))


def _discover_workspace_patterns(root: Path) -> list[str]:
    patterns: list[str] = []

    package_json = root / "package.json"
    if package_json.exists():
        package_data = _read_json_file(package_json)
        workspaces = package_data.get("workspaces") if isinstance(package_data, dict) else None
        if isinstance(workspaces, list):
            patterns.extend(item for item in workspaces if isinstance(item, str))
        elif isinstance(workspaces, dict):
            packages = workspaces.get("packages")
            if isinstance(packages, list):
                patterns.extend(item for item in packages if isinstance(item, str))

    patterns.extend(_read_pnpm_workspace_patterns(root / "pnpm-workspace.yaml"))
    patterns.extend(_read_lerna_workspace_patterns(root / "lerna.json"))
    return sorted(set(patterns))


def _read_pnpm_workspace_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []

    patterns: list[str] = []
    in_packages_block = False
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "packages:":
            in_packages_block = True
            continue
        if in_packages_block and stripped.startswith("-"):
            candidate = stripped[1:].strip().strip("'\"")
            if candidate:
                patterns.append(candidate)
            continue
        if in_packages_block and not raw_line.startswith((" ", "\t")):
            break
    return patterns


def _read_lerna_workspace_patterns(path: Path) -> list[str]:
    lerna_data = _read_json_file(path)
    packages = lerna_data.get("packages") if isinstance(lerna_data, dict) else None
    if isinstance(packages, list):
        return [item for item in packages if isinstance(item, str)]
    return []


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_javascript_monorepo_candidates(
    root: Path,
    import_name: str,
    project_metadata: dict[str, object],
) -> list[Path]:
    candidates: list[Path] = []

    tsconfig_base_url = project_metadata.get("tsconfig_base_url")
    tsconfig_paths = project_metadata.get("tsconfig_paths")
    if isinstance(tsconfig_base_url, Path) and isinstance(tsconfig_paths, dict):
        for alias_pattern, replacements in tsconfig_paths.items():
            if not isinstance(alias_pattern, str) or not isinstance(replacements, list):
                continue
            wildcard_value = _match_alias_pattern(alias_pattern, import_name)
            if wildcard_value is None:
                continue
            for replacement in replacements:
                if not isinstance(replacement, str):
                    continue
                mapped = replacement.replace("*", wildcard_value)
                candidates.append((tsconfig_base_url / mapped).resolve())

    workspace_packages = project_metadata.get("workspace_packages")
    if isinstance(workspace_packages, dict):
        for package_name, package_dir in workspace_packages.items():
            if not isinstance(package_name, str) or not isinstance(package_dir, Path):
                continue
            if import_name == package_name:
                candidates.extend(_workspace_entry_candidates(package_dir))
            elif import_name.startswith(f"{package_name}/"):
                suffix = import_name[len(package_name) + 1 :]
                candidates.append((package_dir / suffix).resolve())
                candidates.append((package_dir / "src" / suffix).resolve())

    return [candidate for candidate in candidates if candidate.is_relative_to(root) or candidate.exists()]


def _match_alias_pattern(pattern: str, import_name: str) -> str | None:
    if "*" not in pattern:
        return "" if pattern == import_name else None
    prefix, suffix = pattern.split("*", 1)
    if not import_name.startswith(prefix):
        return None
    if suffix and not import_name.endswith(suffix):
        return None
    return import_name[len(prefix) : len(import_name) - len(suffix) if suffix else None]


def _workspace_entry_candidates(package_dir: Path) -> list[Path]:
    package_data = _read_json_file(package_dir / "package.json")
    candidates: list[Path] = []
    for field_name in ("source", "module", "main", "types", "typings"):
        value = package_data.get(field_name)
        if isinstance(value, str) and value:
            candidates.append((package_dir / value).resolve())
    candidates.extend(
        [
            (package_dir / "src" / "index").resolve(),
            (package_dir / "index").resolve(),
            package_dir.resolve(),
        ]
    )
    return candidates


def _go_import_path(module_path: str | None, relative_dir: Path) -> str | None:
    relative_text = relative_dir.as_posix()
    if module_path:
        return module_path if relative_text == "." else f"{module_path}/{relative_text}"
    return relative_text if relative_text != "." else None


def _resolve_go_internal_import(import_name: str, package_map: dict[str, tuple[str, str, Path]]) -> str | None:
    if import_name in package_map:
        return package_map[import_name][0]
    return None


def _normalize_go_dependency(import_name: str) -> str:
    if "/" not in import_name:
        return import_name
    parts = import_name.split("/")
    return "/".join(parts[:3]) if "." in parts[0] else parts[0]


def _read_rust_crate_name(root: Path) -> str | None:
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        return None

    match = RUST_CRATE_NAME_RE.search(cargo_toml.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1).replace("-", "_") if match else None


def _rust_module_name(root: Path, file_path: Path, crate_name: str) -> str:
    relative = file_path.relative_to(root)
    if relative.parts and relative.parts[0] == "src":
        inner = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(relative.name)
        if inner.name in {"lib.rs", "main.rs"}:
            return crate_name
        if inner.name == "mod.rs":
            inner = inner.parent
        else:
            inner = inner.with_suffix("")
        dotted = ".".join(inner.parts)
        return f"{crate_name}.{dotted}" if dotted else crate_name

    dotted = relative.with_suffix("").as_posix().replace("/", ".")
    return f"{crate_name}.{dotted}" if dotted else crate_name


def _parse_rust_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    imports = {_normalize_rust_use(raw_import) for raw_import in RUST_USE_RE.findall(source)}
    imports.update(f"self::{mod_name}" for mod_name in RUST_MOD_RE.findall(source))
    return {import_name for import_name in imports if import_name}


def _normalize_rust_use(raw_import: str) -> str:
    normalized = raw_import.split(" as ", 1)[0].strip()
    if "{" in normalized:
        normalized = normalized.split("{", 1)[0].rstrip(":")
    return normalized.strip()


def _resolve_rust_internal_import(
    import_name: str,
    current_module: str,
    crate_name: str,
    name_to_id: dict[str, str],
) -> list[str]:
    candidates = _rust_import_candidates(import_name, current_module, crate_name)
    resolved: list[str] = []
    for candidate in candidates:
        if candidate in name_to_id:
            resolved.append(name_to_id[candidate])
            continue
        for dotted_name, module_id in name_to_id.items():
            if dotted_name.startswith(f"{candidate}."):
                resolved.append(module_id)
    return sorted(set(resolved))


def _rust_import_candidates(import_name: str, current_module: str, crate_name: str) -> list[str]:
    if not import_name:
        return []

    parts = import_name.split("::")
    if parts[0] == "crate":
        return [crate_name + (f".{'.'.join(parts[1:])}" if len(parts) > 1 else "")]
    if parts[0] == "self":
        return [current_module + (f".{'.'.join(parts[1:])}" if len(parts) > 1 else "")]
    if parts[0] == "super":
        base = _package_for_module(current_module)
        parent = _package_for_module(base) if base else ""
        suffix = ".".join(parts[1:])
        return [part for part in [f"{parent}.{suffix}".strip("."), suffix] if part]

    dotted = import_name.replace("::", ".")
    if dotted == crate_name or dotted.startswith(f"{crate_name}."):
        return [dotted]
    return [f"{crate_name}.{dotted}".strip("."), dotted]


def _normalize_rust_dependency(import_name: str, crate_name: str) -> str | None:
    parts = [part for part in import_name.split("::") if part]
    if not parts:
        return None
    if parts[0] in {"crate", "self", "super"}:
        return None
    if parts[0] == crate_name:
        return None
    return parts[0]


def _parse_jvm_metadata(file_path: Path, language_name: str) -> tuple[str | None, list[str]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    if language_name == "Java":
        package_match = JAVA_PACKAGE_RE.search(source)
        package_name = package_match.group(1) if package_match else None
        imports = JAVA_IMPORT_RE.findall(source)
    elif language_name == "Kotlin":
        package_match = KOTLIN_PACKAGE_RE.search(source)
        package_name = package_match.group(1) if package_match else None
        imports = KOTLIN_IMPORT_RE.findall(source)
    elif language_name == "Scala":
        package_match = SCALA_PACKAGE_RE.search(source)
        package_name = package_match.group(1) if package_match else None
        imports = []
        for raw_import in SCALA_IMPORT_RE.findall(source):
            imports.extend(_normalize_scala_imports(raw_import))
    else:
        package_match = JAVA_PACKAGE_RE.search(source)
        package_name = package_match.group(1) if package_match else None
        imports = JAVA_IMPORT_RE.findall(source)
    return package_name, sorted(set(imports))


def _normalize_scala_imports(raw_import: str) -> list[str]:
    normalized = raw_import.strip().replace("_root_.", "")
    if not normalized:
        return []
    if "{" not in normalized:
        candidate = normalized.split("=>", 1)[0].strip()
        return [candidate.removesuffix("._")]

    base, remainder = normalized.split("{", 1)
    base = base.rstrip(". ").strip()
    items = remainder.rstrip("}").split(",")
    imports: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned == "_":
            if base:
                imports.append(base)
            continue
        cleaned = cleaned.split("=>", 1)[0].strip()
        imports.append(f"{base}.{cleaned}".strip("."))
    return imports


def _jvm_module_name(root: Path, file_path: Path, package_name: str | None) -> str:
    stem = file_path.stem
    if package_name:
        return f"{package_name}.{stem}"
    return file_path.relative_to(root).with_suffix("").as_posix().replace("/", ".")


def _parse_csharp_metadata(file_path: Path) -> tuple[str | None, list[str]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    namespace_match = C_SHARP_NAMESPACE_RE.search(source)
    namespace_name = namespace_match.group(1) if namespace_match else None
    return namespace_name, sorted(set(C_SHARP_USING_RE.findall(source)))


def _namespaced_file_name(
    root: Path,
    file_path: Path,
    namespace_name: str | None,
    separator: str = ".",
) -> str:
    if namespace_name:
        return f"{namespace_name}{separator}{file_path.stem}"
    return file_path.relative_to(root).with_suffix("").as_posix().replace("/", separator)


def _resolve_dotted_internal_import(import_name: str, name_to_id: dict[str, str]) -> list[str]:
    if not import_name:
        return []

    normalized = import_name.removesuffix(".*")
    if normalized in name_to_id:
        return [name_to_id[normalized]]

    if import_name.endswith(".*"):
        return sorted(
            module_id for dotted_name, module_id in name_to_id.items() if dotted_name.startswith(f"{normalized}.")
        )

    parts = normalized.split(".")
    for index in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:index])
        matches = [module_id for dotted_name, module_id in name_to_id.items() if dotted_name.startswith(f"{prefix}.")]
        if matches:
            return sorted(matches)
    return []


def _normalize_dotted_dependency(import_name: str) -> str:
    normalized = import_name.removesuffix(".*").replace("\\", ".")
    parts = [part for part in normalized.split(".") if part]
    if not parts:
        return import_name
    if len(parts) >= 2 and parts[0] in {"com", "org", "io", "dev", "net", "javax", "android", "androidx"}:
        return ".".join(parts[:2])
    return ".".join(parts[:2]) if len(parts) >= 2 and parts[0].islower() else parts[0]


def _parse_php_metadata(file_path: Path) -> tuple[str | None, list[str], list[str]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    namespace_match = PHP_NAMESPACE_RE.search(source)
    namespace_name = namespace_match.group(1).strip().lstrip("\\") if namespace_match else None

    namespace_imports: list[str] = []
    for raw_import in PHP_USE_RE.findall(source):
        for chunk in raw_import.split(","):
            cleaned = chunk.strip()
            if not cleaned:
                continue
            cleaned = cleaned.split(" as ", 1)[0].strip().lstrip("\\")
            namespace_imports.append(cleaned)

    file_imports = PHP_FILE_IMPORT_RE.findall(source)
    return namespace_name, sorted(set(namespace_imports)), sorted(set(file_imports))


def _resolve_php_namespace_import(import_name: str, name_to_id: dict[str, str]) -> list[str]:
    normalized = import_name.lstrip("\\")
    if normalized in name_to_id:
        return [name_to_id[normalized]]
    return sorted(
        module_id for dotted_name, module_id in name_to_id.items() if dotted_name.startswith(f"{normalized}\\")
    )


def _normalize_php_dependency(import_name: str) -> str:
    return import_name.lstrip("\\").split("\\", 1)[0]


def _parse_ruby_imports(file_path: Path) -> tuple[list[str], list[str]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return (
        sorted(set(RUBY_REQUIRE_RE.findall(source))),
        sorted(set(RUBY_REQUIRE_RELATIVE_RE.findall(source))),
    )


def _read_dart_package_name(root: Path) -> str | None:
    pubspec = root / "pubspec.yaml"
    if not pubspec.exists():
        return None
    match = DART_PACKAGE_NAME_RE.search(pubspec.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else None


def _parse_dart_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return set(DART_IMPORT_RE.findall(source))


def _resolve_dart_internal_import(
    root: Path,
    file_path: Path,
    import_name: str,
    alias_index: dict[str, str],
    package_name: str | None,
) -> str | None:
    if import_name.startswith("."):
        return _resolve_path_like_import(root, file_path, import_name, alias_index, (".dart",))

    if package_name and import_name.startswith(f"package:{package_name}/"):
        suffix = import_name[len(f"package:{package_name}/") :]
        return _resolve_path_like_import(root, root / "lib" / "__anchor__.dart", f"./{suffix}", alias_index, (".dart",))

    return None


def _normalize_dart_dependency(import_name: str) -> str:
    if import_name.startswith("package:"):
        remainder = import_name[len("package:") :]
        return remainder.split("/", 1)[0]
    return import_name


def _lua_module_name(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root).with_suffix("")
    path_text = relative.as_posix().replace("/", ".")
    return path_text[:-5] if path_text.endswith(".init") else path_text


def _parse_lua_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return set(LUA_REQUIRE_RE.findall(source))


def _resolve_lua_internal_import(import_name: str, module_name_to_id: dict[str, str]) -> str | None:
    if import_name in module_name_to_id:
        return module_name_to_id[import_name]
    init_candidate = f"{import_name}.init"
    return module_name_to_id.get(init_candidate)


def _perl_module_name(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root).with_suffix("")
    if relative.parts and relative.parts[0] == "lib":
        relative = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(relative.name)
    return "::".join(relative.parts) if relative.parts else file_path.stem


def _parse_perl_imports(file_path: Path) -> tuple[list[str], list[str]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return (
        sorted(set(PERL_USE_RE.findall(source))),
        sorted(set(PERL_REQUIRE_RE.findall(source))),
    )


def _normalize_perl_dependency(import_name: str) -> str:
    return import_name.split("::", 1)[0]


def _parse_shell_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return set(SHELL_SOURCE_RE.findall(source))


def _swift_target_name(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root)
    if len(relative.parts) >= 2 and relative.parts[0] in {"Sources", "Tests"}:
        return relative.parts[1].removesuffix("Tests")
    return relative.parts[0] if relative.parts else file_path.stem


def _swift_target_path(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root)
    if len(relative.parts) >= 2 and relative.parts[0] in {"Sources", "Tests"}:
        return "/".join(relative.parts[:2])
    return relative.parent.as_posix() or "."


def _parse_swift_imports(file_path: Path) -> set[str]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return set(SWIFT_IMPORT_RE.findall(source))


def _parse_c_family_imports(file_path: Path) -> list[tuple[str, bool]]:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    return [(import_name, delimiter == '"') for delimiter, import_name in C_INCLUDE_RE.findall(source)]


def _resolve_c_family_import(
    root: Path,
    file_path: Path,
    import_name: str,
    alias_index: dict[str, str],
) -> str | None:
    if "/" in import_name or "\\" in import_name:
        resolved = _resolve_path_like_import(root, file_path, import_name, alias_index, ("",))
        if resolved:
            return resolved

    normalized = import_name.replace("\\", "/")
    candidates = [normalized, normalized.rsplit("/", 1)[-1], Path(normalized).stem]
    for candidate in candidates:
        if candidate in alias_index:
            return alias_index[candidate]
    return None


def _resolve_path_like_import(
    root: Path,
    file_path: Path,
    import_name: str,
    alias_index: dict[str, str],
    default_extensions: tuple[str, ...],
) -> str | None:
    normalized_import = import_name.replace("\\", "/")
    candidates: list[Path] = []

    if normalized_import.startswith("."):
        candidates.append((file_path.parent / normalized_import).resolve())
    else:
        candidates.append((root / normalized_import).resolve())
        candidates.append((file_path.parent / normalized_import).resolve())

    expanded: list[Path] = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix:
            expanded.append(candidate.with_suffix(""))
        base_without_suffix = candidate if not candidate.suffix else candidate.with_suffix("")
        for extension in default_extensions:
            if extension:
                expanded.append(base_without_suffix.with_suffix(extension))
            else:
                expanded.append(base_without_suffix)

    seen: set[str] = set()
    for candidate in expanded:
        key = candidate.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file():
            relative_with_suffix = candidate.relative_to(root).as_posix()
            relative_without_suffix = candidate.relative_to(root).with_suffix("").as_posix()
            return alias_index.get(relative_with_suffix) or alias_index.get(relative_without_suffix)

    normalized = normalized_import.removesuffix(".php").removesuffix(".rb")
    return alias_index.get(normalized_import) or alias_index.get(normalized)


def _normalize_path_dependency(import_name: str) -> str:
    return import_name.replace("\\", "/").split("/", 1)[0]


def _detect_language_from_shebang(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            first_line = handle.readline(512).strip()
    except OSError:
        return None

    if not first_line.startswith("#!"):
        return None

    lower_line = first_line.lower()
    for hint, language_name in SHEBANG_LANGUAGE_HINTS.items():
        if hint in lower_line:
            return language_name
    return None


def _display_extension(path: Path) -> str:
    lower_name = path.name.lower()
    if lower_name in SPECIAL_FILENAMES:
        return path.name
    for extension, _language_name in SORTED_EXTENSION_MATCHES:
        if lower_name.endswith(extension):
            return extension
    return path.suffix.lower() or "(shebang)"


def _script_display_name(relative_path: Path) -> str:
    path_text = relative_path.as_posix()
    if path_text.endswith(".d.ts"):
        base_name = path_text[:-5]
    else:
        base_name = relative_path.with_suffix("").as_posix()
    return base_name[:-6] if base_name.endswith("/index") else base_name


def _language_slug(language_name: str) -> str:
    return NON_ALNUM_RE.sub("-", language_name.strip().lower()).strip("-") or "source"
