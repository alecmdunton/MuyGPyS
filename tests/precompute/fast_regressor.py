# Copyright 2021-2023 Lawrence Livermore National Security, LLC and other
# MuyGPyS Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: MIT

import numpy as np

from absl.testing import absltest
from absl.testing import parameterized

from MuyGPyS import config

config.parse_flags_with_absl()  # Affords option setting from CLI

from MuyGPyS.examples.classify import make_multivariate_classifier, classify_any
from MuyGPyS.examples.regress import make_multivariate_regressor, regress_any
from MuyGPyS.examples.fast_regress import (
    do_fast_regress,
)
from MuyGPyS.gp.distance import pairwise_distances, crosswise_distances
from MuyGPyS.gp.muygps import MultivariateMuyGPS as MMuyGPS
from MuyGPyS.optimize.batch import sample_batch
from MuyGPyS.optimize.chassis import (
    optimize_from_indices,
    optimize_from_tensors,
)
from MuyGPyS.optimize.sigma_sq import mmuygps_sigma_sq_optim
from MuyGPyS.neighbors import NN_Wrapper
from MuyGPyS._test.gp import (
    benchmark_prepare_cholK,
    benchmark_sample_from_cholK,
    BenchmarkGP,
)
from MuyGPyS._test.utils import (
    _make_gaussian_dict,
    _make_gaussian_data,
    _basic_nn_kwarg_options,
    _basic_opt_method_and_kwarg_options,
    _get_sigma_sq_series,
)


class MakeFastRegressorTest(parameterized.TestCase):
    @parameterized.parameters(
        (
            (1000, 1000, 10, b, n, nn_kwargs, lm, k_kwargs)
            for b in [250]
            for n in [10]
            for nn_kwargs in [_basic_nn_kwarg_options[0]]
            for lm in ["mse"]
            # for ssm in ["analytic"]
            # for rt in [True]
            for k_kwargs in (
                {
                    "kern": "matern",
                    "metric": "l2",
                    "nu": {"val": "sample", "bounds": (1e-1, 1e0)},
                    # "nu": {"val": 0.38},
                    "length_scale": {"val": 1.5},
                    "eps": {"val": 1e-5},
                },
            )
        )
    )
    def test_make_fast_multivariate_regressor(
        self,
        train_count,
        test_count,
        feature_count,
        batch_count,
        nn_count,
        nn_kwargs,
        loss_method,
        k_kwargs,
    ):
        # skip if we are using the MPI implementation

        # construct the observation locations
        response_count = 2
        train, test = _make_gaussian_data(
            train_count,
            test_count,
            feature_count,
            response_count=response_count,
            categorical=False,
        )

        (
            _,
            _,
            predictions,
            precomputed_coefficient_matrix,
            _,
        ) = do_fast_regress(
            test["input"],
            train["input"],
            train["output"],
            nn_count=nn_count,
            batch_count=batch_count,
            loss_method=loss_method,
            opt_method="bayes",
            opt_kwargs={
                "allow_duplicate_points": True,
                "init_points": 2,
                "n_iter": 2,
            },
            k_kwargs=k_kwargs,
            nn_kwargs=nn_kwargs,
        )
        self.assertEqual(
            precomputed_coefficient_matrix.shape,
            (train_count, nn_count, response_count),
        )
        self.assertEqual(predictions.shape, (test_count, response_count))


class MakeFastMultivariateRegressorTest(parameterized.TestCase):
    @parameterized.parameters(
        (
            (
                1000,
                1000,
                10,
                b,
                n,
                nn_kwargs,
                lm,
                opt_method_and_kwargs,
                ssm,
                rt,
                k_kwargs,
            )
            for b in [250]
            for n in [10]
            for nn_kwargs in _basic_nn_kwarg_options
            for lm in ["mse"]
            for opt_method_and_kwargs in _basic_opt_method_and_kwarg_options
            for ssm in ["analytic", None]
            for rt in [True, False]
            for k_kwargs in (
                (
                    "matern",
                    [
                        {
                            "nu": {"val": 0.5},
                            "length_scale": {"val": 1.5},
                            "eps": {"val": 1e-5},
                        },
                        {
                            "nu": {"val": 0.8},
                            "length_scale": {"val": 0.7},
                            "eps": {"val": 1e-5},
                        },
                    ],
                ),
            )
        )
    )
    def test_make_fast_multivariate_regressor(
        self,
        train_count,
        test_count,
        feature_count,
        batch_count,
        nn_count,
        nn_kwargs,
        loss_method,
        opt_method_and_kwargs,
        sigma_method,
        return_distances,
        k_kwargs,
    ):
        # skip if we are using the MPI implementation
        kern, k_kwargs = k_kwargs
        opt_method, opt_kwargs = opt_method_and_kwargs
        response_count = len(k_kwargs)

        # construct the observation locations
        train, test = _make_gaussian_data(
            train_count,
            test_count,
            feature_count,
            response_count,
            categorical=False,
        )

        (
            mmuygps,
            nbrs_lookup,
            predictions,
            precomputed_coefficient_matrix,
            timings,
        ) = do_fast_regress(
            test["input"],
            train["input"],
            train["output"],
            nn_count=nn_count,
            batch_count=batch_count,
            loss_method=loss_method,
            opt_method=opt_method,
            sigma_method=sigma_method,
            kern=kern,
            k_kwargs=k_kwargs,
            nn_kwargs=nn_kwargs,
            opt_kwargs=opt_kwargs,
        )

        self.assertEqual(
            precomputed_coefficient_matrix.shape,
            (train_count, nn_count, response_count),
        )
        self.assertEqual(predictions.shape, (test_count, response_count))

        for i, muygps in enumerate(mmuygps.models):
            print(f"For model {i}:")
            for key in k_kwargs[i]:
                if key == "eps":
                    self.assertEqual(k_kwargs[i][key]["val"], muygps.eps())
                elif k_kwargs[i][key]["val"] == "sample":
                    print(
                        f"\toptimized {key} to find value "
                        f"{muygps.kernel.hyperparameters[key]()}"
                    )
                else:
                    self.assertEqual(
                        k_kwargs[i][key]["val"],
                        muygps.kernel.hyperparameters[key](),
                    )
            if sigma_method is None:
                self.assertFalse(muygps.sigma_sq.trained())
            else:
                self.assertTrue(muygps.sigma_sq.trained())
                print(
                    f"\toptimized sigma_sq to find value "
                    f"{muygps.sigma_sq()}"
                )


if __name__ == "__main__":
    absltest.main()
