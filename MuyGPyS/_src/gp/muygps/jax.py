# Copyright 2021-2023 Lawrence Livermore National Security, LLC and other
# MuyGPyS Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: MIT

import jax.numpy as jnp

from jax import jit


@jit
def _muygps_compute_solve(
    K: jnp.ndarray,
    Kcross: jnp.ndarray,
    batch_nn_targets: jnp.ndarray,
) -> jnp.ndarray:
    batch_count, nn_count, response_count = batch_nn_targets.shape
    responses = Kcross.reshape(batch_count, 1, nn_count) @ jnp.linalg.solve(
        K, batch_nn_targets
    )
    return responses.reshape(batch_count, response_count)


@jit
def _muygps_compute_diagonal_variance(
    K: jnp.ndarray,
    Kcross: jnp.ndarray,
) -> jnp.ndarray:
    batch_count, nn_count = Kcross.shape
    return 1 - jnp.sum(
        Kcross
        * jnp.linalg.solve(K, Kcross.reshape(batch_count, nn_count, 1)).reshape(
            batch_count, nn_count
        ),
        axis=1,
    )


@jit
def _muygps_fast_regress_solve(
    Kcross: jnp.ndarray,
    coeffs_tensor: jnp.ndarray,
) -> jnp.ndarray:
    return jnp.einsum("ij,ijk->ik", Kcross, coeffs_tensor)


@jit
def _mmuygps_fast_regress_solve(
    Kcross: jnp.ndarray,
    coeffs_tensor: jnp.ndarray,
) -> jnp.ndarray:
    return jnp.einsum("ijk,ijk->ik", Kcross, coeffs_tensor)


@jit
def _muygps_fast_regress_precompute(
    K: jnp.ndarray,
    train_nn_targets_fast: jnp.ndarray,
) -> jnp.ndarray:
    return jnp.linalg.solve(K, train_nn_targets_fast)
