# Copyright 2021-2023 Lawrence Livermore National Security, LLC and other
# MuyGPyS Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: MIT

import numpy as np
import jax.numpy as jnp

from typing import Tuple

from functools import partial
from jax import jit

# from sklearn.metrics.pairwise import cosine_similarity
@partial(jit, static_argnums=(0,))
def _make_fast_regress_tensors(
    metric: str,
    batch_nn_indices: jnp.ndarray,
    train_features: jnp.ndarray,
    train_targets: jnp.ndarray,
) -> Tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    num_train, _ = train_features.shape
    batch_nn_indices_fast = jnp.concatenate(
        (
            jnp.expand_dims(jnp.arange(0, num_train), axis=1),
            batch_nn_indices[:, :-1],
        ),
        axis=1,
    )

    pairwise_dists_fast = _pairwise_distances(
        train_features, batch_nn_indices_fast, metric=metric
    )
    batch_nn_targets_fast = train_targets[batch_nn_indices_fast, :]
    return pairwise_dists_fast, batch_nn_targets_fast


@partial(jit, static_argnums=(0,))
def _make_regress_tensors(
    metric: str,
    batch_indices: jnp.ndarray,
    batch_nn_indices: jnp.ndarray,
    test_features: jnp.ndarray,
    train_features: jnp.ndarray,
    train_targets: jnp.ndarray,
) -> Tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    if test_features is None:
        test_features = train_features
    crosswise_dists = _crosswise_distances(
        test_features,
        train_features,
        batch_indices,
        batch_nn_indices,
        metric=metric,
    )
    pairwise_dists = _pairwise_distances(
        train_features, batch_nn_indices, metric=metric
    )
    batch_nn_targets = train_targets[batch_nn_indices, :]
    return crosswise_dists, pairwise_dists, batch_nn_targets


@partial(jit, static_argnums=(0,))
def _make_train_tensors(
    metric: str,
    batch_indices: jnp.ndarray,
    batch_nn_indices: jnp.ndarray,
    train_features: jnp.ndarray,
    train_targets: jnp.ndarray,
) -> Tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    crosswise_dists, pairwise_dists, batch_nn_targets = _make_regress_tensors(
        metric,
        batch_indices,
        batch_nn_indices,
        train_features,
        train_features,
        train_targets,
    )
    batch_targets = train_targets[batch_indices, :]
    return crosswise_dists, pairwise_dists, batch_targets, batch_nn_targets


@partial(jit, static_argnums=(4,))
def _crosswise_distances(
    data: jnp.ndarray,
    nn_data: jnp.ndarray,
    data_indices: jnp.ndarray,
    nn_indices: jnp.ndarray,
    metric: str = "l2",
) -> jnp.ndarray:
    locations = data[data_indices]
    points = nn_data[nn_indices]
    if metric == "l2":
        diffs = _crosswise_diffs(locations, points)
        return _l2(diffs)
    elif metric == "F2":
        diffs = _crosswise_diffs(locations, points)
        return _F2(diffs)
    # elif metric == "ip":
    #     return _crosswise_prods(locations, points)
    # elif metric == "cosine":
    #     return _crosswise_cosine(locations, points)
    else:
        raise ValueError(f"Metric {metric} is not supported!")


@jit
def _crosswise_diffs(
    locations: jnp.ndarray, points: jnp.ndarray
) -> jnp.ndarray:
    return locations[:, None, :] - points


@partial(jit, static_argnums=(2,))
def _pairwise_distances(
    data: jnp.ndarray,
    nn_indices: jnp.ndarray,
    metric: str = "l2",
) -> jnp.ndarray:
    points = data[nn_indices]
    if metric == "l2":
        diffs = _diffs(points)
        return _l2(diffs)
    elif metric == "F2":
        diffs = _diffs(points)
        return _F2(diffs)
    # elif metric == "ip":
    #     return _prods(points)
    # elif metric == "cosine":
    #     return _cosine(points)
    else:
        raise ValueError(f"Metric {metric} is not supported!")


@jit
def _diffs(points: jnp.ndarray) -> jnp.ndarray:
    return points[:, :, None, :] - points[:, None, :, :]


@jit
def _F2(diffs: jnp.ndarray) -> jnp.ndarray:
    return jnp.sum(diffs**2, axis=-1)


@jit
def _l2(diffs: jnp.ndarray) -> jnp.ndarray:
    return jnp.sqrt(_F2(diffs))


@jit
def _fast_nn_update(
    nn_indices: jnp.ndarray,
) -> jnp.ndarray:
    train_count, _ = nn_indices.shape
    new_nn_indices = jnp.concatenate(
        (
            jnp.expand_dims(jnp.arange(0, train_count), axis=1),
            nn_indices[:, :-1],
        ),
        axis=1,
    )
    return new_nn_indices
