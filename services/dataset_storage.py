from pathlib import Path


def safe_path_component(value: str, field_name: str) -> str:
    component = (value or "").strip()
    if not component:
        raise ValueError(f"{field_name} 不能为空")
    if component in {".", ".."} or "/" in component or "\\" in component:
        raise ValueError(f"{field_name} 包含非法路径字符")
    if Path(component).name != component:
        raise ValueError(f"{field_name} 包含非法路径字符")
    return component


def resolve_dataset_path(root: Path, *components: str) -> Path:
    root_path = root.resolve()
    target_path = root_path.joinpath(*components).resolve()
    try:
        target_path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("保存路径超出存储目录") from exc
    return target_path
