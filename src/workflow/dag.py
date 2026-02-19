import json
from pathlib import Path

from workflow.models import PurchaseOrder


def load_dependencies(tests_root: Path, task_names: list[str]) -> dict[str, list[str]]:
    dependency_file = tests_root / "dependencies.json"
    if not dependency_file.exists():
        return {name: [] for name in task_names}

    parsed = json.loads(dependency_file.read_text(encoding="utf-8"))
    dependencies: dict[str, list[str]] = {name: [] for name in task_names}
    for name, deps in parsed.items():
        if name in dependencies:
            dependencies[name] = list(deps)
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


def discover_purchase_orders(tests_root: Path) -> dict[str, PurchaseOrder]:
    tasks: dict[str, PurchaseOrder] = {}
    for txt_path in sorted(tests_root.glob("test*/test*.txt")):
        name = txt_path.parent.name
        tasks[name] = PurchaseOrder(name=name, txt_path=txt_path)
    return tasks
