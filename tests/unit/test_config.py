from __future__ import annotations

from config.settings import load_config, validate_config


def test_required_nodes_and_roles_are_valid() -> None:
    config = load_config()
    assert validate_config(config) == []
    assert set(config["cluster"]["nodes"]) == {"vm1", "vm2", "vm3", "vm4"}
    assert {node["role"] for node in config["cluster"]["nodes"].values()} == {
        "ingestion",
        "storage",
        "compute",
        "search",
    }


def test_environment_override_changes_only_requested_host(monkeypatch) -> None:
    monkeypatch.setenv("DSE_VM3_HOST", "10.255.255.3")
    config = load_config()
    assert config["cluster"]["nodes"]["vm3"]["host"] == "10.255.255.3"
    assert config["services"]["spark"]["master_url"] == "spark://10.255.255.3:7077"
    assert validate_config(config) == []


def test_hdfs_paths_are_derived_as_complete_uris() -> None:
    config = load_config()
    namenode = config["services"]["hdfs"]["namenode_uri"]
    assert config["paths"]["hdfs"]["datasets"] == f"{namenode}/datasets"
    assert config["paths"]["hdfs"]["warehouse"] == f"{namenode}/warehouse"
    assert config["paths"]["hdfs"]["iceberg_warehouse"] == f"{namenode}/warehouse/iceberg"
    assert config["paths"]["hdfs"]["serving"] == f"{namenode}/serving"
    assert config["iceberg"]["warehouse"] == f"{namenode}/warehouse/iceberg"


def test_duplicate_hosts_are_rejected(monkeypatch) -> None:
    configured = load_config()
    vm1_host = configured["cluster"]["nodes"]["vm1"]["host"]
    monkeypatch.setenv("DSE_VM3_HOST", vm1_host)
    errors = validate_config(load_config())
    assert any("unique" in error for error in errors)
