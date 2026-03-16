from pathlib import Path

from repomap.graph import graph_to_mermaid
from repomap.layers import detect_module_layer
from repomap.models import ModuleInfo
from repomap.parser import (
    build_module_inventory,
    detect_language,
    module_name_from_path,
    parse_go_imports,
    parse_imports,
    parse_javascript_imports,
)


def test_module_name_from_init_file() -> None:
    root = Path("repo")
    file_path = root / "pkg" / "__init__.py"
    assert module_name_from_path(root, file_path) == "pkg"


def test_parse_imports_resolves_relative_imports(tmp_path: Path) -> None:
    module_file = tmp_path / "pkg" / "feature.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        "import os\nfrom . import helpers\nfrom ..core import service\n",
        encoding="utf-8",
    )

    imports = parse_imports(module_file, "pkg.feature")

    assert "os" in imports
    assert "pkg.helpers" in imports
    assert "core.service" in imports


def test_parse_javascript_imports_collects_common_forms(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "app.js"
    module_file.parent.mkdir(parents=True)
    module_file.write_text(
        '\n'.join(
            [
                'import React from "react";',
                'import { api } from "./lib/api";',
                'const db = require("../db");',
                'const lazy = import("./lazy");',
            ]
        ),
        encoding="utf-8",
    )

    imports = parse_javascript_imports(module_file)

    assert "react" in imports
    assert "./lib/api" in imports
    assert "../db" in imports
    assert "./lazy" in imports


def test_detect_language_supports_typescript_shell_and_special_files(tmp_path: Path) -> None:
    ts_file = tmp_path / "src" / "app.tsx"
    ts_file.parent.mkdir(parents=True)
    ts_file.write_text("export const App = () => null;\n", encoding="utf-8")

    shell_file = tmp_path / "scripts" / "deploy"
    shell_file.parent.mkdir(parents=True)
    shell_file.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")

    docker_file = tmp_path / "Dockerfile"
    docker_file.write_text("FROM python:3.12-slim\n", encoding="utf-8")

    assert detect_language(ts_file) == "TypeScript"
    assert detect_language(shell_file) == "Shell"
    assert detect_language(docker_file) == "Dockerfile"


def test_parse_go_imports_handles_blocks(tmp_path: Path) -> None:
    module_file = tmp_path / "server.go"
    module_file.write_text(
        '\n'.join(
            [
                'package main',
                'import (',
                '    "fmt"',
                '    api "github.com/example/project/api"',
                ')',
            ]
        ),
        encoding="utf-8",
    )

    imports = parse_go_imports(module_file)

    assert "fmt" in imports
    assert "github.com/example/project/api" in imports


def test_build_module_inventory_includes_generic_languages_and_typescript(tmp_path: Path) -> None:
    python_file = tmp_path / "app.py"
    python_file.write_text("import os\n", encoding="utf-8")

    ts_file = tmp_path / "web" / "main.ts"
    ts_file.parent.mkdir(parents=True)
    ts_file.write_text('import "./ui";\n', encoding="utf-8")

    ts_dep = tmp_path / "web" / "ui.ts"
    ts_dep.write_text("export const ui = true;\n", encoding="utf-8")

    rust_file = tmp_path / "src" / "lib.rs"
    rust_file.parent.mkdir(parents=True)
    rust_file.write_text("fn main() {}\n", encoding="utf-8")

    modules, languages, primary_language = build_module_inventory(tmp_path)

    language_names = [language.name for language in languages]
    module_languages = {module.path: module.language for module in modules}

    assert "Python" in language_names
    assert "TypeScript" in language_names
    assert "Rust" in language_names
    assert module_languages["src/lib.rs"] == "Rust"
    assert module_languages["web/main.ts"] == "TypeScript"
    assert primary_language in {"Python", "TypeScript", "Rust"}


def test_build_module_inventory_resolves_java_and_ruby_dependencies(tmp_path: Path) -> None:
    java_service = tmp_path / "src" / "main" / "java" / "com" / "example" / "core" / "Service.java"
    java_service.parent.mkdir(parents=True)
    java_service.write_text(
        "\n".join(
            [
                "package com.example.core;",
                "public class Service {}",
            ]
        ),
        encoding="utf-8",
    )

    java_api = tmp_path / "src" / "main" / "java" / "com" / "example" / "api" / "Controller.java"
    java_api.parent.mkdir(parents=True, exist_ok=True)
    java_api.write_text(
        "\n".join(
            [
                "package com.example.api;",
                "import com.example.core.Service;",
                "public class Controller {}",
            ]
        ),
        encoding="utf-8",
    )

    ruby_service = tmp_path / "lib" / "service.rb"
    ruby_service.parent.mkdir(parents=True, exist_ok=True)
    ruby_service.write_text("class Service; end\n", encoding="utf-8")

    ruby_app = tmp_path / "lib" / "app.rb"
    ruby_app.write_text('require_relative "./service"\n', encoding="utf-8")

    modules, _languages, _primary_language = build_module_inventory(tmp_path)
    dependencies = {module.name: module.internal_dependencies for module in modules}

    assert any(name.endswith("com.example.api.Controller") for name in dependencies)
    java_dependency_ids = next(value for name, value in dependencies.items() if name.endswith("com.example.api.Controller"))
    ruby_dependency_ids = dependencies["lib/app"]

    assert java_dependency_ids
    assert ruby_dependency_ids


def test_build_module_inventory_resolves_rust_and_c_family_dependencies(tmp_path: Path) -> None:
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text(
        "\n".join(
            [
                "[package]",
                'name = "sample-crate"',
            ]
        ),
        encoding="utf-8",
    )

    rust_lib = tmp_path / "src" / "lib.rs"
    rust_lib.parent.mkdir(parents=True, exist_ok=True)
    rust_lib.write_text("mod api;\n", encoding="utf-8")

    rust_api = tmp_path / "src" / "api.rs"
    rust_api.write_text("pub fn run() {}\n", encoding="utf-8")

    header = tmp_path / "include" / "util.h"
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text("#pragma once\n", encoding="utf-8")

    source = tmp_path / "src" / "main.cpp"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('#include "../include/util.h"\n', encoding="utf-8")

    modules, _languages, _primary_language = build_module_inventory(tmp_path)
    dependency_map = {module.path: module.internal_dependencies for module in modules}

    assert dependency_map["src/lib.rs"]
    assert dependency_map["src/main.cpp"]


def test_build_module_inventory_resolves_workspace_packages_and_tsconfig_paths(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    package_json.write_text(
        """
        {
          "workspaces": ["packages/*"]
        }
        """,
        encoding="utf-8",
    )
    tsconfig_json = tmp_path / "tsconfig.json"
    tsconfig_json.write_text(
        """
        {
          "compilerOptions": {
            "baseUrl": ".",
            "paths": {
              "@app/*": ["apps/web/src/*"]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    workspace_pkg = tmp_path / "packages" / "ui"
    workspace_pkg.mkdir(parents=True)
    (workspace_pkg / "package.json").write_text(
        """
        {
          "name": "@acme/ui",
          "source": "src/index.ts"
        }
        """,
        encoding="utf-8",
    )
    (workspace_pkg / "src").mkdir()
    (workspace_pkg / "src" / "index.ts").write_text("export const Button = 1;\n", encoding="utf-8")

    app_root = tmp_path / "apps" / "web" / "src"
    app_root.mkdir(parents=True)
    (app_root / "utils.ts").write_text("export const helper = true;\n", encoding="utf-8")
    (app_root / "main.ts").write_text(
        'import { Button } from "@acme/ui";\nimport { helper } from "@app/utils";\n',
        encoding="utf-8",
    )

    modules, _languages, _primary_language = build_module_inventory(tmp_path)
    dependency_map = {module.path: module.internal_dependencies for module in modules}

    assert len(dependency_map["apps/web/src/main.ts"]) == 2


def test_build_module_inventory_resolves_pnpm_and_lerna_workspaces(tmp_path: Path) -> None:
    (tmp_path / "pnpm-workspace.yaml").write_text(
        """
        packages:
          - packages/*
          - apps/*
        """,
        encoding="utf-8",
    )
    (tmp_path / "lerna.json").write_text(
        """
        {
          "packages": ["packages/*"]
        }
        """,
        encoding="utf-8",
    )

    package_root = tmp_path / "packages" / "shared"
    package_root.mkdir(parents=True)
    (package_root / "package.json").write_text(
        """
        {
          "name": "@repo/shared",
          "main": "src/index.ts"
        }
        """,
        encoding="utf-8",
    )
    (package_root / "src").mkdir()
    (package_root / "src" / "index.ts").write_text("export const shared = true;\n", encoding="utf-8")

    app_root = tmp_path / "apps" / "web" / "src"
    app_root.mkdir(parents=True)
    (app_root / "main.ts").write_text('import { shared } from "@repo/shared";\n', encoding="utf-8")

    modules, _languages, _primary_language = build_module_inventory(tmp_path)
    dependency_map = {module.path: module.internal_dependencies for module in modules}

    assert dependency_map["apps/web/src/main.ts"]


def test_build_module_inventory_resolves_dart_lua_perl_and_shell_dependencies(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: sample_app\n", encoding="utf-8")

    dart_lib = tmp_path / "lib"
    dart_lib.mkdir()
    (dart_lib / "util.dart").write_text("const util = 1;\n", encoding="utf-8")
    (dart_lib / "main.dart").write_text("import 'package:sample_app/util.dart';\n", encoding="utf-8")

    lua_root = tmp_path / "lua"
    lua_root.mkdir()
    (lua_root / "util.lua").write_text("return {}\n", encoding="utf-8")
    (lua_root / "main.lua").write_text('local util = require("lua.util")\n', encoding="utf-8")

    perl_root = tmp_path / "lib" / "Sample"
    perl_root.mkdir(parents=True, exist_ok=True)
    (perl_root / "Util.pm").write_text("package Sample::Util;\n1;\n", encoding="utf-8")
    (perl_root / "App.pm").write_text("use Sample::Util;\n1;\n", encoding="utf-8")

    shell_root = tmp_path / "scripts"
    shell_root.mkdir()
    (shell_root / "common.sh").write_text("echo common\n", encoding="utf-8")
    (shell_root / "deploy.sh").write_text('source "./common.sh"\n', encoding="utf-8")

    modules, _languages, _primary_language = build_module_inventory(tmp_path)
    dependency_map = {module.path: module.internal_dependencies for module in modules}

    assert dependency_map["lib/main.dart"]
    assert dependency_map["lua/main.lua"]
    assert dependency_map["lib/Sample/App.pm"]
    assert dependency_map["scripts/deploy.sh"]


def test_layer_detection_uses_path_and_dependencies() -> None:
    module = ModuleInfo(
        id="javascript:web/components/button",
        name="web/components/button",
        path="web/components/button.tsx",
        language="JavaScript",
        imports=[],
        internal_dependencies=[],
        external_dependencies=["react"],
    )

    assert detect_module_layer(module) == "Frontend"


def test_graph_to_mermaid_generates_edges() -> None:
    import networkx as nx

    graph = nx.DiGraph()
    graph.add_node(
        "javascript:api/handlers",
        label="api/handlers",
        path="api/handlers.js",
        language="JavaScript",
        layer="Backend",
        url="https://github.com/example/repo/blob/main/api/handlers.js",
    )
    graph.add_node(
        "python:core.service",
        label="core.service",
        path="core/service.py",
        language="Python",
        layer="Backend",
        url="https://github.com/example/repo/blob/main/core/service.py",
    )
    graph.add_edge("javascript:api/handlers", "python:core.service")

    mermaid = graph_to_mermaid(graph)

    assert "flowchart LR" in mermaid
    assert "api/handlers" in mermaid
    assert "core.service" in mermaid
    assert "click N0" in mermaid or "click N1" in mermaid
