from __future__ import annotations

from config.settings import load_config


def test_cluster_roles_have_the_required_daemon_boundaries() -> None:
    nodes = load_config()["cluster"]["nodes"]
    assert nodes["vm1"]["runs_hdfs_daemons"] is False
    assert nodes["vm1"]["runs_spark_daemons"] is False
    assert nodes["vm4"]["runs_hdfs_daemons"] is False
    assert nodes["vm4"]["runs_spark_daemons"] is False
    assert nodes["vm2"]["runs_hdfs_daemons"] is True
    assert nodes["vm2"]["runs_spark_daemons"] is True
    assert nodes["vm3"]["runs_hdfs_daemons"] is True
    assert nodes["vm3"]["runs_spark_daemons"] is True


def test_hdfs_replication_and_pagerank_constraints_match_assignment() -> None:
    config = load_config()
    assert config["services"]["hdfs"]["replication_factor"] == 2
    assert config["ranking"]["pagerank"]["damping"] == 0.85
    assert config["ranking"]["pagerank"]["iterations"] >= 10
    assert config["ranking"]["bm25"] == {"k1": 1.2, "b": 0.75}
