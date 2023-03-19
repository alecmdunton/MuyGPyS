# Copyright 2021-2023 Lawrence Livermore National Security, LLC and other
# MuyGPyS Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: MIT

from typing import Callable

from MuyGPyS.gp.distortion.isotropic import IsotropicDistortion
from MuyGPyS.gp.distortion.null import NullDistortion


def apply_distortion(distortion_fn: Callable):
    def distortion_appier(fn: Callable):
        def distorted_fn(diffs, *args, **kwargs):
            return fn(distortion_fn(diffs), *args, **kwargs)

        return distorted_fn

    return distortion_appier


def embed_with_distortion_model(fn: Callable, distortion_fn: Callable):
    if isinstance(distortion_fn, IsotropicDistortion):
        return apply_distortion(distortion_fn)(fn)
    elif isinstance(distortion_fn, NullDistortion):
        return fn
    else:
        raise ValueError(f"Noise model {type(distortion_fn)} is not supported!")