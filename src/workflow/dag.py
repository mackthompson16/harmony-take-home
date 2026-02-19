import json
from pathlib import Path

from workflow.models import PurchaseOrder


def load_dependencies(tests_root: Path, task_names: list[str], suite_name: str | None = None) -> dict[str, list[str]]:
    dependencies: dict[str, list[str]] = {name: [] for name in task_names}

    # Global dependencies file supports full task IDs, e.g. "suite_name/file_name".
    global_dependency_file = tests_root / "dependencies.json"
    if global_dependency_file.exists():
        parsed = json.loads(global_dependency_file.read_text(encoding="utf-8"))
        for name, deps in parsed.items():
            if name in dependencies:
                dependencies[name] = [dep for dep in deps if dep in dependencies]

    # Suite-local dependencies file supports file stems only.
    # Example in tests/attention_suite/dependencies.json:
    # { "urgent_only": ["no_flags"] }
    if suite_name is not None:
        suite_dirs = [tests_root / suite_name]
    else:
        suite_dirs = sorted([p for p in tests_root.iterdir() if p.is_dir()])

    for suite_dir in suite_dirs:
        if not suite_dir.exists() or not suite_dir.is_dir():
            continue
        suite_dependency_file = suite_dir / "dependencies.json"
        if not suite_dependency_file.exists():
            continue
        parsed = json.loads(suite_dependency_file.read_text(encoding="utf-8"))
        for stem, deps in parsed.items():
            task_id = f"{suite_dir.name}/{stem}"
            if task_id not in dependencies:
                continue
            expanded = [f"{suite_dir.name}/{dep}" for dep in deps]
            dependencies[task_id] = [dep for dep in expanded if dep in dependencies]
    return dependencies


def topo_sort(tasks: dict[str, PurchaseOrder]) -> list[str]:
    indegree = {name: 0 for name in tasks}
    children: dict[str, list[str]] = {name: [] for name in tasks}

    for name, task in tasks.items():
        for dep in task.dependencies:
            if dep not in tasks:
                raise ValueError(f"Task '{name}' depends on unknown task '{dep}'")
            indegree[name] += 1
            children[dep].append(name)

    ready = sorted([name for name, count in indegree.items() if count == 0])
    ordered: list[str] = []

    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()

    if len(ordered) != len(tasks):
        raise ValueError("Cycle detected in purchase order DAG.")
    return ordered


def discover_purchase_orders(tests_root: Path, suite_name: str | None = None) -> dict[str, PurchaseOrder]:
    tasks: dict[str, PurchaseOrder] = {}
    if suite_name is not None:
        suite_dir = tests_root / suite_name
        txt_paths = sorted(suite_dir.glob("input/*.txt"))
        if not txt_paths:
            txt_paths = sorted(suite_dir.glob("*.txt"))
    else:
        txt_paths = sorted(tests_root.glob("*/input/*.txt"))
        if not txt_paths:
            txt_paths = sorted(tests_root.glob("*/*.txt"))

    for txt_path in txt_paths:
        current_suite_name = txt_path.parent.parent.name if txt_path.parent.name == "input" else txt_path.parent.name
        task_name = f"{current_suite_name}/{txt_path.stem}"
        tasks[task_name] = PurchaseOrder(name=task_name, txt_path=txt_path)
    return tasks
