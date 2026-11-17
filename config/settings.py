from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLUSTER_FILE = PROJECT_ROOT / "config" / "cluster.yaml"
DEFAULT_SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"
REQUIRED_NODE_IDS = ("vm1", "vm2", "vm3", "vm4")
REQUIRED_ROLES = ("ingestion", "storage", "compute", "search")


class ConfigurationError(ValueError):
    pass


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return value


def _apply_environment_overrides(config: dict[str, Any]) -> dict[str, Any]:
    nodes = config.get("cluster", {}).get("nodes", {})
    for node_id in REQUIRED_NODE_IDS:
        env_name = f"DSE_{node_id.upper()}_HOST"
        if env_name in os.environ:
            nodes[node_id]["host"] = os.environ[env_name]
    datasets = config.setdefault("datasets", {})
    overrides = {
        "DSE_SPARK_MASTER": ("services", "spark", "master_url"),
        "DSE_HDFS_NAMENODE": ("services", "hdfs", "namenode_uri"),
        "DSE_SERVING_ROOT": ("paths", "local", "serving_root"),
        "DSE_DATASET_ROOT": ("paths", "local", "dataset_root"),
        "DSE_ICEBERG_CATALOG": ("iceberg", "catalog"),
        "DSE_ICEBERG_WAREHOUSE": ("iceberg", "warehouse"),
    }
    for env_name, path in overrides.items():
        if env_name not in os.environ:
            continue
        target = config
        for part in path[:-1]:
            target = target.setdefault(part, {})
        target[path[-1]] = os.environ[env_name]
    dataset_overrides = {
        "DSE_PHASE0_INPUT": ("phase0", "path"),
        "DSE_PHASE1_INPUT": ("phase1", "path"),
    }
    for env_name, (phase, key) in dataset_overrides.items():
        if env_name in os.environ:
            datasets.setdefault(phase, {})[key] = os.environ[env_name]
    return config


def _role_host(config: dict[str, Any], role: str) -> str:
    for node in config.get("cluster", {}).get("nodes", {}).values():
        if node.get("role") == role:
            return str(node.get("host", ""))
    return ""


def _hdfs_path(namenode_uri: str, configured_path: Any) -> str:
    value = str(configured_path or "")
    if value.startswith("hdfs://"):
        return value.rstrip("/")
    if value.startswith("/"):
        return f"{namenode_uri.rstrip('/')}{value}"
    return f"{namenode_uri.rstrip('/')}/{value.lstrip('/')}"


def _derive_service_endpoints(config: dict[str, Any]) -> None:
    services = config.setdefault("services", {})
    paths = config.setdefault("paths", {})
    hdfs = services.setdefault("hdfs", {})
    spark = services.setdefault("spark", {})
    search = services.setdefault("search", {})
    storage_host = _role_host(config, "storage")
    compute_host = _role_host(config, "compute")
    search_host = _role_host(config, "search")
    rpc_port = int(hdfs.get("rpc_port", 8020))
    master_port = int(spark.get("master_port", 7077))
    search_port = int(search.get("port", 8000))
    hdfs.setdefault("namenode_uri", f"hdfs://{storage_host}:{rpc_port}")
    spark.setdefault("master_url", f"spark://{compute_host}:{master_port}")
    search.setdefault("url", f"http://{search_host}:{search_port}")
    hdfs_paths = paths.setdefault("hdfs", {})
    namenode_uri = str(hdfs["namenode_uri"])
    hdfs_paths["datasets"] = _hdfs_path(namenode_uri, hdfs_paths.get("datasets", "datasets"))
    hdfs_paths["warehouse"] = _hdfs_path(namenode_uri, hdfs_paths.get("warehouse", "warehouse"))
    hdfs_paths["iceberg_warehouse"] = _hdfs_path(
        namenode_uri,
        hdfs_paths.get("iceberg_warehouse", "warehouse/iceberg"),
    )
    hdfs_paths["serving"] = _hdfs_path(namenode_uri, hdfs_paths.get("serving", "serving"))
    iceberg = config.setdefault("iceberg", {})
    iceberg["warehouse"] = _hdfs_path(
        namenode_uri,
        iceberg.get("warehouse", hdfs_paths["iceberg_warehouse"]),
    )


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    selected = path or os.getenv("DSE_CONFIG_FILE") or DEFAULT_CLUSTER_FILE
    config_path = Path(selected)
    config = _apply_environment_overrides(_read_yaml(config_path))
    _derive_service_endpoints(config)
    return config


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    selected = path or os.getenv("DSE_SETTINGS_FILE") or DEFAULT_SETTINGS_FILE
    settings_path = Path(selected)
    return _read_yaml(settings_path)


def get_setting(path: str, default: Any = None, settings: dict[str, Any] | None = None) -> Any:
    value = settings if settings is not None else load_settings()
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def validate_config(config: dict[str, Any] | None = None) -> list[str]:
    value = config if config is not None else load_config()
    errors: list[str] = []
    nodes = value.get("cluster", {}).get("nodes", {})
    if set(REQUIRED_NODE_IDS) - set(nodes):
        errors.append(f"Missing required nodes: {', '.join(sorted(set(REQUIRED_NODE_IDS) - set(nodes)))}")
    hosts: list[str] = []
    roles: list[str] = []
    for node_id in REQUIRED_NODE_IDS:
        node = nodes.get(node_id, {})
        host = str(node.get("host", ""))
        if not host:
            errors.append(f"{node_id} has no host address")
            continue
        try:
            ipaddress.ip_address(host)
        except ValueError:
            errors.append(f"{node_id} host is not a valid IP address: {host}")
        hosts.append(host)
        role = str(node.get("role", ""))
        if role:
            roles.append(role)
    if len(set(hosts)) != len(hosts):
        errors.append("Node host addresses must be unique")
    if set(roles) != set(REQUIRED_ROLES):
        errors.append(f"Required roles must each be assigned once; found: {', '.join(sorted(roles))}")
    hdfs = value.get("services", {}).get("hdfs", {})
    if int(hdfs.get("replication_factor", 0)) != 2:
        errors.append("HDFS replication factor must be 2")
    ranking = value.get("ranking", {})
    pagerank = ranking.get("pagerank", {})
    if int(pagerank.get("iterations", 0)) < 15:
        errors.append("PageRank iterations must be at least 15")
    damping = float(pagerank.get("damping", 0.0))
    tolerance = float(pagerank.get("tolerance", 0.0))
    if not 0.0 < damping < 1.0:
        errors.append("PageRank damping must be between zero and one")
    if tolerance <= 0.0:
        errors.append("PageRank tolerance must be positive")
    bm25 = ranking.get("bm25", {})
    if float(bm25.get("k1", -1.0)) < 0:
        errors.append("BM25 k1 must not be negative")
    if not 0.0 <= float(bm25.get("b", -1.0)) <= 1.0:
        errors.append("BM25 b must be between zero and one")
    for key in ("datasets", "warehouse", "iceberg_warehouse", "serving"):
        if not value.get("paths", {}).get("hdfs", {}).get(key):
            errors.append(f"Missing HDFS path: {key}")
    return errors


def _shell_exports(config: dict[str, Any]) -> str:
    nodes = config["cluster"]["nodes"]
    values = {
        "DSE_VM1_HOST": nodes["vm1"]["host"],
        "DSE_VM2_HOST": nodes["vm2"]["host"],
        "DSE_VM3_HOST": nodes["vm3"]["host"],
        "DSE_VM4_HOST": nodes["vm4"]["host"],
        "DSE_SPARK_MASTER": config["services"]["spark"]["master_url"],
        "DSE_HDFS_NAMENODE": config["services"]["hdfs"]["namenode_uri"],
        "DSE_SERVING_ROOT": config["paths"]["local"]["serving_root"],
        "DSE_DATASET_ROOT": config["paths"]["local"]["dataset_root"],
        "DSE_ICEBERG_CATALOG": config["iceberg"]["catalog"],
        "DSE_ICEBERG_WAREHOUSE": config["iceberg"]["warehouse"],
    }
    return "\n".join(f"export {key}={shlex.quote(str(value))}" for key, value in values.items())


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect distributed search engine configuration")
    parser.add_argument("--config", default=None)
    parser.add_argument("--settings", default=None)
    parser.add_argument("--get", dest="get_path", default=None)
    parser.add_argument("--settings-get", dest="settings_get_path", default=None)
    parser.add_argument("--export-shell", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.settings_get_path:
            settings = load_settings(args.settings)
            current_settings: Any = settings
            for part in args.settings_get_path.split("."):
                current_settings = current_settings[part]
            value = json.dumps(current_settings, indent=2) if args.json else str(current_settings)
            print(value)
            return 0
        if args.get_path:
            current: Any = config
            for part in args.get_path.split("."):
                current = current[part]
            value = json.dumps(current, indent=2) if args.json else str(current)
            print(value)
            return 0
        errors = validate_config(config)
        if args.export_shell:
            if errors:
                raise ConfigurationError("; ".join(errors))
            print(_shell_exports(config))
            return 0
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("Configuration is valid")
        return 0
    except (ConfigurationError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
