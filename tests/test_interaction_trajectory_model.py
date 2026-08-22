import numpy as np
import torch

from planmargin import interaction_trajectory_model as interaction


def _config() -> interaction.InteractionConfig:
    return interaction.InteractionConfig(
        scenario_count=100,
        shard_count=2,
        hidden_channels=8,
        neighbor_hidden=4,
        head_width=12,
        epochs=1,
        batch_size=4,
        device="cpu",
    )


def test_interaction_network_shape_and_neighbor_ablation() -> None:
    config = _config()
    mean = np.zeros(interaction.FEATURE_WIDTH, dtype=np.float32)
    scale = np.ones(interaction.FEATURE_WIDTH, dtype=np.float32)
    target_scale = np.ones(60, dtype=np.float32)
    model = interaction.InteractionTrajectoryNet(
        feature_mean=mean,
        feature_scale=scale,
        target_scale=target_scale,
        config=config,
        use_neighbors=True,
    )
    features = torch.zeros((3, interaction.FEATURE_WIDTH))
    baseline = torch.zeros((3, 60))
    assert model(features, baseline).shape == (3, 60)


def test_cache_round_trip_preserves_scenario_boundaries(tmp_path) -> None:
    scenarios = []
    for index in range(3):
        scenarios.append(
            interaction.InteractionScenario(
                scenario_id=f"scenario-{index}",
                shard_index=index,
                features=np.full(
                    (index + 1, interaction.FEATURE_WIDTH), index, dtype=np.float32
                ),
                targets=np.zeros((index + 1, 60), dtype=np.float32),
                baseline=np.ones((index + 1, 60), dtype=np.float32),
            )
        )
    path = tmp_path / "cache.npz"
    interaction.write_cache(path, scenarios)
    loaded = interaction.read_cache(path)
    assert [value.scenario_id for value in loaded] == [
        value.scenario_id for value in scenarios
    ]
    assert [len(value.features) for value in loaded] == [1, 2, 3]


def test_split_scenarios_has_no_overlap() -> None:
    scenarios = [
        interaction.InteractionScenario(
            scenario_id=str(index),
            shard_index=0,
            features=np.zeros((1, interaction.FEATURE_WIDTH), dtype=np.float32),
            targets=np.zeros((1, 60), dtype=np.float32),
            baseline=np.zeros((1, 60), dtype=np.float32),
        )
        for index in range(100)
    ]
    split = interaction.split_scenarios(scenarios, 2)
    ids = [
        {value.scenario_id for value in split[name]}
        for name in ("train", "validation", "test")
    ]
    assert not ids[0] & ids[1]
    assert not ids[0] & ids[2]
    assert not ids[1] & ids[2]
    assert sorted(map(len, ids)) == [10, 10, 80]
