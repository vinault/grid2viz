# Copyright (C) 2021, RTE (http://www.rte-france.com/)
# See AUTHORS.txt
# SPDX-License-Identifier: MPL-2.0

import argparse
import configparser
import os

## A bug can appear with MacOSX if matplotlib is not set to a non-interactive mode
# issue: https://github.com/matplotlib/matplotlib/issues/14304/
import matplotlib

matplotlib.use("agg")

CONFIG_FILE_CONTENT = """
# This file have been automatically generated, please do not modify it. 
# You can remove it once done with the application.
[DEFAULT]
agents_dir={agents_dir}
env_dir={env_dir}
n_cores={n_cores}
[WARMSTART]
scenario={scenario}
agent_ref={agent_ref}
agent_study={agent_study}
page={page}
time_step={time_step}
# This file will be re generated to each call of "python -m grid2viz.main"
"""

ARG_AGENTS_PATH_DESC = (
    "The path where the episode logs of the Agents to compare are stored."
    " (default to None to study the example agents provided with the package)"
)
ARG_ENV_PATH_DESC = (
    "The path where the environment config is stored."
    " (default to None to use the provided default environment)"
)
ARG_PORT_DESC = "The port to serve grid2viz on. (default to 8050)"
ARG_DEBUG_DESC = "Enable debug mode for developers. (default to False)"
ARG_N_CORES_DESC = "The number of cores to use for the first loading of the best agents of each scenario"

ARG_CACHE_DESC = "Enable the building of  all the cache data for all agents at once before relaunching grid2viz."

ARG_WARM_START_DESC = "Enable the application to warm start to a given section based on the parameters defined in the WARMSTART section of the config.ini file."

ARG_CONFIG_PATH_DESC = "Path to the configuration file config.ini."

ARG_ACTIVATE_BETA_DESC = "Enable beta features. (default to False)"


def main(
        use_fnc_args=False,
        env_path=None,
        agents_path=None,
        cache_only=False,
        port=None,
        debug=None,
        n_cores=None,
        warm_start=None,
        warm_start_params=None,
        config_path=None
    ):

    print("Coucou Nicolas")
    parser_main = argparse.ArgumentParser(description="Grid2Viz")
    parser_main.add_argument(
        "--agents_path",
        default=None,
        required=False,
        type=str,
        help=ARG_AGENTS_PATH_DESC,
    )
    parser_main.add_argument(
        "--env_path", default=None, required=False, type=str, help=ARG_ENV_PATH_DESC
    )
    parser_main.add_argument(
        "--port", default=8050, required=False, type=int, help=ARG_PORT_DESC
    )
    parser_main.add_argument("--debug", action="store_true", help=ARG_DEBUG_DESC)

    parser_main.add_argument("--n_cores", default=2, type=int, help=ARG_N_CORES_DESC)
    parser_main.add_argument("--cache", action="store_true", help=ARG_CACHE_DESC)
    parser_main.add_argument(
        "--warm-start", action="store_true", help=ARG_WARM_START_DESC
    )
    parser_main.add_argument(
        "--config-path",
        default=None,
        required=False,
        type=str,
        help=ARG_CONFIG_PATH_DESC,
    )
    parser_main.add_argument(
        "--activate-beta", action="store_true", help=ARG_ACTIVATE_BETA_DESC
    )

    args = parser_main.parse_args()

    if use_fnc_args:
        if env_path is not None:
            args.env_path = env_path
        if agents_path is not None:
            args.agents_path = agents_path
        if cache_only is not None:
            args.cache = cache_only
        if port is not None:
            args.port = port
        if debug is not None:
            args.debug = debug
        if n_cores is not None:
            args.n_cores = n_cores
        if warm_start is not None:
            args.warm_start = warm_start
        if config_path is not None:
            args.config_path = config_path

    pkg_root_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["GRID2VIZ_ROOT"] = pkg_root_dir
    config_path = os.path.join(pkg_root_dir, "config.ini")

    if args.agents_path is not None:
        agents_dir = os.path.abspath(args.agents_path)
    elif args.config_path is not None:
        parser = configparser.ConfigParser()
        parser.read(args.config_path)
        try:
            agents_dir = parser.get("DEFAULT", "agents_dir")
            print(f"Using agent logs path from config file: {agents_dir}")
        except configparser.NoOptionError:
            print("A config file was provided without an agents_dir key")
            agents_dir = os.path.join(pkg_root_dir, "data", "agents")
            print("Using default agents logs at {}".format(agents_dir))
    else:
        agents_dir = os.path.join(pkg_root_dir, "data", "agents")
        print("Using default agents logs at {}".format(agents_dir))

    if args.env_path is not None:
        env_dir = os.path.abspath(args.env_path)
    elif args.config_path is not None:
        parser = configparser.ConfigParser()
        parser.read(args.config_path)
        try:
            env_dir = parser.get("DEFAULT", "env_dir")
            print(f"Using environment from config file: {env_dir}")
        except configparser.NoOptionError:
            print("A config file was provided without an env_dir key.")
            env_dir = os.path.join(pkg_root_dir, "data", "rte_case14_realistic")
            print(f"Using default environment at {env_dir}")
    else:
        env_dir = os.path.join(pkg_root_dir, "data", "rte_case14_realistic")
        print(f"Using default environment at {env_dir}")

    n_cores = args.n_cores

    if args.warm_start:
        with open(config_path, "w") as f:
            f.write(
                CONFIG_FILE_CONTENT.format(
                    agents_dir=agents_dir,
                    env_dir=env_dir,
                    n_cores=n_cores,
                    scenario=warm_start_params["scenario"],
                    agent_ref=warm_start_params["agent_ref"],
                    agent_study=warm_start_params["agent_study"],
                    page=warm_start_params["page"],
                    time_step=warm_start_params["time_step"],
                )
            )
    else:
        with open(config_path, "w") as f:
            f.write(
                CONFIG_FILE_CONTENT.format(
                    agents_dir=agents_dir,
                    env_dir=env_dir,
                    n_cores=n_cores,
                    scenario="",
                    agent_ref="",
                    agent_study="",
                    page="",
                    time_step=0,
                )
            )

    is_makeCache_only = args.cache
    activate_beta = args.activate_beta

    # Inline import to load app only now
    if is_makeCache_only:
        print(f"number of cores : {n_cores}")
        from grid2viz.src.manager import (
            scenarios,
            agents,
            n_cores,
            cache_dir,
            make_cache
        )
        make_cache(scenarios, agents, n_cores, cache_dir)
    else:
        from grid2viz.app import app_run, define_layout_and_callbacks

        page = None
        if args.warm_start:
            if args.config_path is None:
                raise ValueError(
                    "Cannot warmstart without a configuration provided with --config-path"
                )
            parser = configparser.ConfigParser()
            print(args.config_path)
            parser.read(args.config_path)
            try:
                scenario = parser.get("WARMSTART", "scenario")
            except configparser.NoOptionError:
                scenario = None
            try:
                agent_ref = parser.get("WARMSTART", "agent_ref")
            except configparser.NoOptionError:
                agent_ref = None
            try:
                agent_study = parser.get("WARMSTART", "agent_study")
            except configparser.NoOptionError:
                agent_study = None
            try:
                user_timestep = parser.get("WARMSTART", "time_step")
            except configparser.NoOptionError:
                user_timestep = None
            window = None
            page = parser.get("WARMSTART", "page")
            config = dict(
                env_path=parser.get("DEFAULT", "env_dir"),
                agents_dir=parser.get("DEFAULT", "agents_dir"),
            )
            define_layout_and_callbacks(
                scenario,
                agent_ref,
                agent_study,
                user_timestep,
                window,
                page,
                config,
                activate_beta,
            )
        else:
            define_layout_and_callbacks(activate_simulation=activate_beta)
        app_run(args.port, args.debug, page)


if __name__ == "__main__":
    main(
        use_fnc_args=True,
        env_path=r"C:\Users\vrenault\data_grid2op\l2rpn_idf_2023",
        agents_path=r"D:\l2rpn\grid2viz\agents\agent_runner_new_tutor",
        config_path=r"D:\l2rpn\grid2viz\grid2viz\config.ini",
        warm_start=False,
        warm_start_params={
            "scenario": "2035-01-01_0",
            "agent_ref": "20230809-1955 GeneralTutorByArea",
            # "agent_ref": "20230803-0716 DoNothing",
            "agent_study": "20230809-1955 GeneralTutorByArea",
            "page": "macro",
            "time_step": 0
        },
        cache_only=True,
        n_cores=2
    )
