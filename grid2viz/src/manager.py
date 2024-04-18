# Copyright (C) 2021, RTE (http://www.rte-france.com/)
# See AUTHORS.txt
# SPDX-License-Identifier: MPL-2.0

import configparser
import itertools
import json
import os
import time
from pathlib import Path
import pickle
import gzip

from colorama import Fore, Style
import dill
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.spatial import ConvexHull
from grid2op.Episode import EpisodeData
from grid2op.PlotGrid import PlotPlotly, PlotMatplot

from grid2viz.src.kpi.EpisodeAnalytics import EpisodeAnalytics

# refer to https://github.com/rte-france/Grid2Op/blob/master/getting_started/8_PlottingCapabilities.ipynb for better usage

graph = None
graph_matplotlib = None


# TODO: addSubstationColor - integrate that into grid2op Plotgrid
def add_substation_color_matplot(subs, plot_helper, fig):
    radius_size = plot_helper._sub_radius
    # fig = plot_helper.plot_layout()
    ax = fig.gca()

    for id_sub in subs:
        subName = "sub_" + str(id_sub)
        x, y = plot_helper._grid_layout[subName]
        circle = plt.Circle((x, y), int(radius_size), color="gold")
        ax.add_artist(circle)

    return fig


def add_substation_color_plotly(subs, plot_helper, fig, color="red", symbol="circle"):
    radius_size = int(plot_helper._sub_radius * 2)

    for id_sub in subs:
        subName = "sub_" + str(id_sub)
        x_center, y_center = plot_helper._grid_layout[subName]

        marker_dict = dict(
            size=radius_size,
            color=color,
            symbol=symbol,
            showscale=False,
            opacity=0.8,
        )
        fig.add_trace(
            go.Scatter(
                x=[x_center],
                y=[y_center],
                mode="markers",
                text=[subName],
                name="sub" + subName,
                marker=marker_dict,
                showlegend=False,
            )
        )
    return fig

def add_alarm_area_plotly(line_subs, plot_helper, fig, color="gold"):

    x=[]
    y=[]
    for id_sub in line_subs:
        subName = "sub_" + str(id_sub)
        x_center, y_center = plot_helper._grid_layout[subName]
        x.append(x_center)
        y.append(y_center)

    points = [[lx, ly] for lx, ly in zip(x, y)]
    hull = ConvexHull(points)
    hull_vertices_x = [x[i] for i in hull.vertices]
    hull_vertices_y = [y[i] for i in hull.vertices]
    fig.add_trace(go.Scatter(
        x=hull_vertices_x,
        y=hull_vertices_y,
        marker=dict(color=color, size=2),
        mode="markers",
        # name="Women",
        fill="toself",
        opacity=0.5
    ))
    return fig



def make_network(episode, responsive=True):
    """
    Create a Plotly network graph with the layout configuration and the selected episode.

    :param episode: An episode containing targeted data for the graph.
    :return: Network graph
    """
    global graph
    if graph is None:
        graph = PlotPlotly(
            grid_layout=episode.observation_space.grid_layout,
            observation_space=episode.observation_space,
            # responsive=False,
            load_radius=0,
            gen_radius=0,
            sub_radius=12,
            width=1800,
            # height=900,
        )
    return graph


def make_network_matplotlib(episode,timestep=0):
    global graph_matplotlib
    if graph_matplotlib is None:
        graph_matplotlib = PlotMatplot(
            grid_layout=episode.observation_space.grid_layout,
            observation_space=episode.observation_space,
            line_name=False,
            gen_name=False,
            load_name=False,
        )
    return graph_matplotlib


######
# we want a non responsive graph for now in agent_study
# so we have to define it differently from the global graph in make_network that we don't use here
import base64
import io
def make_network_agent_study(episode, timestep, figure_obs=None, responsive=False,redraw=False, draw_loads=False):
    # subs_on_bus_2 = np.repeat(False, episode_data.observations[0].n_sub)
    #graph=None
    #if(isMatplotLib):########not working for now. Was trying to use matplotlib to accelerate ploting time
     #   buf = io.BytesIO()
     #   make_network_scenario_overview(episode,timestep=timestep)
#
#
     #   # plt.figure(network_graph.number)
     #   # plt.close(fig)
     #   plt.savefig(buf, format="png")
     #   buf.seek(0)
     #   #encoded_image = base64.b64encode(buf.read())
#
     #   #fig=encoded_image.decode()
     #   data = base64.b64encode(buf.getbuffer()).decode("utf8")  # encode to html elements
     #   buf.close()
     #   return "data:image/png;base64,{}".format(data)

    observation=episode.observations[timestep]

    graph=make_network(episode, responsive)
    graph._sub_radius = 12  # instead of 25 by default
    graph._bus_radius = 7  # instead of 4 by default
    if draw_loads:
        # graph._load_radius = 8
        graph._load_fill_color = "orange"
        graph._load_line_width = 1

        # graph._gen_radius = 8
        graph._gen_fill_color = "blue"
        graph._gen_line_width = 1
    else:

        graph._load_fill_color = "white"
        graph._load_line_width = 0

        graph._gen_fill_color = "white"
        graph._gen_line_width = 0


    if(figure_obs)and not redraw:# don't redraw it from scratch, just change what is needed

        import plotly.colors as pc
        data_fig=figure_obs["data"]#go.Figure(figure_obs)

        rho_lines=observation.rho
        n_lines=len(rho_lines)

        id_line=0
        i_traces=0
        previous_trace=None
        while id_line<n_lines:
            trace=data_fig[i_traces]

            if "line" in trace.keys():#update line color
                color_scheme = (
                        pc.sequential.Blues_r[:4]
                        + pc.sequential.Oranges[4:6]
                        + pc.sequential.Reds[-3:-1]
                )
                rho=rho_lines[id_line]
                capacity = np.clip(rho, 0.0, 1.0)
                color = color_scheme[int(capacity * float(len(color_scheme) - 1))]
                trace["line"]['color']=str(color)
                # if(previous_trace) and ("text" in previous_trace.keys()):
                #     previous_trace["text"]=[str(np.round(rho*100,2))+" %"]

                id_line+=1
            i_traces+=1
            previous_trace=trace

        #remove contextual trace such as color sub for specific topology and alarm zone

        #remove alarm first
        n_traces=len(data_fig)-1
        for i_traces in range(n_traces,-1,-1):
            trace = data_fig[i_traces]
            if "fill" in trace.keys():
                data_fig.pop(i_traces)
            elif "sub" in str(trace["text"]):
                break

        #update topology traces at substations
        n_traces=len(data_fig)-1
        for i_traces in range(n_traces,-1,-1):
            trace = data_fig[i_traces]
            if "sub" in str(trace["text"]):
                if "marker" in trace.keys():
                    if trace["marker"]["color"]!='PaleTurquoise':
                        data_fig.pop(i_traces)
                    else:
                        break

        fig=go.Figure(figure_obs)

    else:
        #if graph is None:
        #    graph = PlotPlotly(
        #        grid_layout=episode.observation_space.grid_layout,
        #        observation_space=episode.observation_space,
        #        responsive=responsive,
        #    )
        fig = graph.plot_obs(episode.observations[timestep], line_info=None)#,redraw=redraw,figure=figure_obs)
        # full_fig = fig.full_figure_for_development()
        # print(full_fig.layout.xaxis.range)
        # fig.update_layout(
        #     xaxis=dict(range=[-200, 1200]),
        #     yaxis=dict(range=[-200, 800])
        # )

    ##########
    # coloring subs not in reference topologie
    nb_bus_subs = [
        episode.observations[timestep].state_of(substation_id=i)["nb_bus"]
        for i in range(episode.observations[timestep].n_sub)
    ]
    sub_2buses = [
        i for i in range(episode.observations[timestep].n_sub) if nb_bus_subs[i] >= 2
    ]
    fig = add_substation_color_plotly(
        sub_2buses, graph, fig, color="darkgreen", symbol="square"
    )  # also other color for subs not in ref topo

    # We color subs where we had actions
    sub_name_modified = list(
        itertools.chain.from_iterable(episode.action_data_table.subs_modified)
    )
    sub_id_modified = [
        int(str.split("_")[1])
        for str in episode.action_data_table.subs_modified[timestep]
    ]
    fig = add_substation_color_plotly(sub_id_modified, graph,fig)


    if ("is_alarm" in episode.action_data_table.columns):
        alarms_lines_area = episode.observations[timestep].alarms_lines_area

        light_colors_plotly = ["lightcoral", "lightsalmon", "lightpink"]
        n_colors = len(light_colors_plotly)

        if (episode.action_data_table.is_alarm[timestep]):

            alarm_zones = episode.action_data_table.alarm_zone[timestep]

            for i_zone,zone in enumerate(alarm_zones):
                id_lines_alarm = []
                for idx, line_name in enumerate(episode.observations[timestep].name_line):
                    line_alarm_zones = alarms_lines_area[line_name]
                    if(zone in line_alarm_zones):
                        id_lines_alarm.append(idx)
                line_subs = [episode.observations[timestep].line_ex_to_subid[l_idx] for l_idx in id_lines_alarm]
                line_subs += [episode.observations[timestep].line_or_to_subid[l_idx] for l_idx in id_lines_alarm]
                line_subs = np.unique(line_subs)

                area_color= i_zone % n_colors
                fig = add_alarm_area_plotly(line_subs, graph, fig, color=light_colors_plotly[area_color])

    return fig


def make_network_agent_overview(episode):
    graph = make_network(episode)

    # modified_lines = actions_model.get_modified_lines(episode)
    # line_values = [None] * episode.n_lines
    # for line in modified_lines.index:
    #    line_values[np.where(episode.line_names == line)[0][0]] = line

    lines_attacked = list(
        episode.attacks_data_table["id_lines"][
            episode.attacks_data_table.attack
        ].unique()
    )
    lines_overflowed_ids = list(
        itertools.chain.from_iterable(episode.total_overflow_ts.line_ids)
    )
    # to color assets on our graph with different colors while not overloading it with information
    # we will use plot_obs instead of plot_info for now
    ####
    # For that we override an observation with the desired values
    obs_colored = episode.observations[0]

    # having a rho with value 1.0 give us a red line while 0.7 gives us an orange line and 0.3 a blue line
    rho_to_color = np.array(
        [
            float(0.6) if line in lines_attacked else float(0.3)
            for line in episode.line_names
        ]
    )
    rho_to_color[lines_overflowed_ids] = 1.0
    line_status_colored = np.array(
        [False if line in lines_attacked else True for line in episode.line_names]
    )
    obs_colored.rho = rho_to_color
    obs_colored.line_status = line_status_colored

    # network_graph = make_network(episode).plot_info(
    #    line_values=[ line if line in lines_attacked else None for line in  episode.line_names]
    #    #coloring="line"
    # )
    # )
    fig = graph.plot_obs(obs_colored, line_info=None, gen_info=None, load_info=None)

    ##########
    # We color subs where we had actions
    sub_name_modified = list(
        itertools.chain.from_iterable(episode.action_data_table.subs_modified)
    )
    sub_id_modified = set([int(str.split("_")[1]) for str in sub_name_modified])
    fig = add_substation_color_plotly(sub_id_modified, graph, fig)

    return fig


def make_network_scenario_overview(episode,timestep=0):
    max_loads = (
        episode.load[["value", "equipement_id"]]
        .groupby("equipement_id")
        .max()
        .sort_index()
    )
    max_gens = (
        episode.production[["value", "equipement_id"]]
        .groupby("equipement_id")
        .max()
        .sort_index()
    )
    lines_in_maintenance = list(
        episode.maintenances["line_name"][episode.maintenances.value == 1].unique()
    )

    graph = make_network_matplotlib(episode)

    # to color assets on our graph with different colors while not overloading it with information
    # we will use plot_obs instead of plot_info for now
    ####
    # For that we override an observation with the desired values
    obs_colored = episode.observations[timestep]

    # having a rho with value 0.1 give us a blue line while 0.5 gives us an orange line
    # line in maintenance would display as dashed lines
    rho_to_color = np.array(
        [
            float(0.0) if line in lines_in_maintenance else float(0.4)
            for line in episode.line_names
        ]
    )
    line_status_colored = np.array(
        [False if line in lines_in_maintenance else True for line in episode.line_names]
    )
    obs_colored.rho = rho_to_color
    obs_colored.line_status = line_status_colored

    obs_colored.load_p = np.array(max_loads.value)
    obs_colored.gen_p = np.array(max_gens.value)

    network_graph = graph.plot_obs(obs_colored, line_info=None)
    # network_graph=graph.plot_info(
    #    #observation=episode.observations[0],
    #    load_values=max_loads.values.flatten(),
    #    load_unit="MW",
    #    gen_values=max_gens.values.flatten(),
    #    gen_unit="MW"
    #    #line_values=[ 1 if line in lines_in_maintenance else 0 for line in  episode.line_names],
    #    #coloring="line"
    # )

    return network_graph


store = {}


def make_episode(agent, episode_name,with_reboot=False):
    """
    Load episode from cache. If not already in, compute episode data
    and save it in cache.

    :param agent: Agent Name
    :param episode_name: Name of the studied episode
    :return: Episode with computed data
    """
    if is_in_ram_cache(episode_name, agent):
        episode=get_from_ram_cache(episode_name, agent)
    elif is_in_fs_cache(episode_name, agent):
        episode = get_from_fs_cache(episode_name, agent)
        save_in_ram_cache(episode_name, agent, episode)
        #to see evolution of ram footprint
        #from guppy import hpy
        #h = hpy()
        #print(h.heap())
    else:
        episode = compute_episode(episode_name, agent,with_reboot)
        save_in_ram_cache(episode_name, agent, episode)

    if(with_reboot and "reboot" not in dir(episode)):
        #in that case we need to reload the episode from episode data object
        episode_data = retrieve_episode_from_disk(episode_name, agent)
        episode.decorate_with_reboot(episode_data)
        save_in_ram_cache(episode_name, agent, episode)

    return episode


def make_episode_without_decorate(agent, episode_name,save=False):
    """
    Load episode from cache without decorating with the EpisodeData attributes
    This is needed to use multiprocessing which pickles/unpickles the results.

    :param agent: Agent Name
    :param episode_name: Name of the studied episode
    :return: Episode with computed data (without EpisodeData attributes), EpisodeData instance
    """
    if is_in_ram_cache(episode_name, agent):
        if save:
            return None
        return get_from_ram_cache(episode_name, agent)
    elif is_in_fs_cache(episode_name, agent):
        if save:
            return None
        beg = time.time()
        episode_analytics=get_from_fs_cache(episode_name, agent)
        return episode_analytics
    else:
        episode_data = retrieve_episode_from_disk(episode_name, agent)
        if episode_data is not None:
            episode_analytics = EpisodeAnalytics(episode_data, episode_name, agent)
            if save:
                episode_analytics.decorate_light_without_reboot(episode_data)
                save_in_fs_cache(episode_name, agent, episode_analytics)
                return None #to avoid problem with picklalisable issues in multiprocess
            return episode_analytics
        else:
            return None


def clear_fs_cache():
    os.rmdir(cache_dir)


def is_in_fs_cache(episode_name, agent):
    dill_path=get_fs_cached_file(episode_name, agent)
    is_in_fs_cache=(os.path.isfile(dill_path) | os.path.isfile(dill_path+".bz"))
    return is_in_fs_cache


def get_fs_cached_file(episode_name, agent):
    episode_dir = os.path.join(cache_dir, episode_name)
    if not os.path.exists(episode_dir):
        os.makedirs(episode_dir,exist_ok=True)
    return os.path.join(episode_dir, agent + ".dill")

def save_in_fs_cache(episode_name, agent, episode):
    path = get_fs_cached_file(episode_name, agent)

    #####
    #to assess size of objects

    #from pympler import asizeof
    #total_size=asizeof.asizeof(episode)
    #for key,value in vars(episode).items():
    #   print(key)
    #   print(asizeof.asizeof(value))
    #   print(int(asizeof.asizeof(value)/total_size*100))

    #import bz2
    #import zipfile
    #bz2.BZ2File('bz2_test.pbz2', 'wb') as f:
    with gzip.open(path+".bz", "wb") as f:
    #with zipfile.ZipFile.write(path+".zip") as f:
    #with open(path, "wb") as f:
        #dill.dump(episode, f, protocol=4)
        pickle.dump(episode, f, protocol=4)



def get_from_fs_cache(episode_name, agent):
    beg = time.time()
    path = get_fs_cached_file(episode_name, agent)
    print(f"Loading from filesystem cache agent {agent} on scenario {episode_name}...")

    start = time.time()

    if(os.path.exists(path + ".bz")):

        with gzip.open(path + ".bz", "rb") as f:
            # with zipfile.ZipFile.open(path + ".zip") as f:
            print(path)
            episode_analytics=pickle.load(f)
    else:
        with open(path, "rb") as f:
            episode_analytics = pickle.load(f)

    ######
    #add observation_space only to decorate as it could not be saved in pickle
    agent_path = os.path.join(agents_dir, agent)
    episode_analytics.decorate_obs_act_spaces(agent_path)


    ##########
    ##Warning for compatibility with older cache version:
    if("observations" not in dir(episode_analytics)):
        print("WARNING: the cache management have been updated in grid2viz 1.3.1 for faster loading. "
              "You Should delete the old _cache folder and recompute it with latest grid2viz version")
    episode_analytics.optimize_memory_footprint(opt_obs_act=True)#this adds a bit of 25% loading time overhead,
    # in particular when resetting observations and actions, which only brings a 10% size decrease

    #episode_analytics.decorate(episode_data)
    #episode_analytics=decorate(episode_analytics,episode_data)

    end = time.time()
    print(
        f"Agent {agent} on scenario {episode_name} loaded from filesystem cache in: {(end - beg):.1f} s"
    )
    return episode_analytics


def compute_episode(episode_name, agent,with_reboot=False):
    print(f"Loading from logs agent {agent} on scenario {episode_name}...")
    beg = time.time()
    episode_data = retrieve_episode_from_disk(episode_name, agent)
    episode_analytics = EpisodeAnalytics(episode_data, episode_name, agent)
    if with_reboot:
        episode_analytics.decorate_with_reboot(episode_data)
    else:
        episode_analytics.decorate_light_without_reboot(episode_data)
        save_in_fs_cache(episode_name, agent, episode_analytics)
        episode_analytics.decorate_obs_act_spaces(os.path.join(agents_dir, agent))
    end = time.time()
    print(
        f"Agent {agent} on scenario {episode_name} loaded from logs in: {(end - beg):.1f} s"
    )
    return episode_analytics


def retrieve_episode_from_disk(episode_name, agent):
    path = os.path.join(agents_dir, agent)
    episode_path = os.path.abspath(os.path.join(path, episode_name))
    if os.path.isdir(episode_path):
        episode_data = EpisodeData.from_disk(path, episode_name)
        return episode_data
    else:
        return None


def is_in_ram_cache(episode_name, agent):
    return make_ram_cache_id(episode_name, agent) in store


def save_in_ram_cache(episode_name, agent, episode):
    store[make_ram_cache_id(episode_name, agent)] = episode


def get_from_ram_cache(episode_name, agent):
    return store[make_ram_cache_id(episode_name, agent)]


def make_ram_cache_id(episode_name, agent):
    return agent + episode_name


def check_all_tree_and_get_meta_and_best(base_dir, agents):
    best_agents = {}
    meta_json = {}
    scenarios = set()
    survival_dic = {}
    attention_dic = {}

    for agent in agents:
        survival_dic_agent = {}
        attention_dic_agent = {}
        for scenario_name in os.listdir(os.path.join(base_dir, agent)):

            scenario_folder = os.path.join(base_dir, agent, scenario_name)
            if not os.path.isdir(scenario_folder):
                continue
            with open(os.path.join(scenario_folder, "episode_meta.json")) as f:
                episode_meta = json.load(fp=f)
                meta_json[scenario_name] = episode_meta

                survival_dic_agent[scenario_name] = int(
                    int(episode_meta["nb_timestep_played"])
                    * 100
                    / int(episode_meta["chronics_max_timestep"])
                )
                scenarios.add(scenario_name)

                if scenario_name not in best_agents:
                    best_agents[scenario_name] = {
                        "value": -1,
                        "agent": None,
                        "out_of": 0,
                        "cum_reward": -1,
                    }
                condition_to_update_best_agent = best_agents[scenario_name][
                    "value"
                ] < episode_meta["nb_timestep_played"] or (
                    best_agents[scenario_name]["value"]
                    == episode_meta["nb_timestep_played"]
                    and best_agents[scenario_name]["cum_reward"]
                    < episode_meta["cumulative_reward"]
                )
                if condition_to_update_best_agent:
                    best_agents[scenario_name]["value"] = episode_meta[
                        "nb_timestep_played"
                    ]
                    best_agents[scenario_name]["agent"] = agent
                    best_agents[scenario_name]["cum_reward"] = episode_meta[
                        "cumulative_reward"
                    ]

            best_agents[scenario_name]["out_of"] = (
                best_agents[scenario_name]["out_of"] + 1
            )
            other_reward_json_path=os.path.join(scenario_folder, "other_rewards.json")
            if os.path.exists(other_reward_json_path):
                with open(other_reward_json_path) as f:
                    other_reward_meta = json.load(fp=f)
                    last_step_rewards=other_reward_meta[len(other_reward_meta) - 1]
                    if 'attention_score' in last_step_rewards.keys():
                        attention_dic_agent[scenario_name] = last_step_rewards['attention_score']
                    f.close()


        survival_dic[agent] = survival_dic_agent
        attention_dic[agent] = attention_dic_agent

    scenarios=list(scenarios)#instead of set, to avoid type errors when using pandas for instance
    survival_df = pd.DataFrame(columns=agents, index=scenarios)
    attention_df = pd.DataFrame(columns=agents, index=scenarios)#, dtype=np.int64)
    for agent in agents:
        survival_dic_agent = survival_dic[agent]
        attention_dic_agent = attention_dic[agent]
        for (scenario, survival_time) in survival_dic_agent.items():
            survival_df.loc[scenario][agent] = survival_time
        if len(attention_dic_agent) != 0:
            for (scenario, attention_score) in attention_dic_agent.items():
                attention_df.loc[scenario][agent] = np.round(attention_score,2)

    survival_df = survival_df.fillna(-1)  # To be able to cast as int below.
    survival_df = survival_df.astype(int)

    return meta_json, best_agents, survival_df, attention_df

def make_cache(scenarios,agents,n_cores,cache_dir,agent_selection=None):

    if(agent_selection is not None):
        agents=[agent for agent in agents if agent in agent_selection]

    from pathos.multiprocessing import ProcessPool

    if not os.path.exists(cache_dir):
        print("Starting Multiprocessing for reading the best agent of each scenario")

    # TODO: tous les agents n'ont pas forcément tourner sur exactement tous les mêmes scenarios
    # Eviter une erreur si un agent n'a pas tourné sur un scenario
    agent_scenario_list = [
        (agent, scenario) for agent in agents for scenario in scenarios
    ]

    agents_data = []
    if n_cores == 1:  # no multiprocess useful for debug if needed
        i = 0
        for agent_scenario in agent_scenario_list:
            agents_data.append(
                make_episode_without_decorate(agent_scenario[0], agent_scenario[1],save=True)
            )
            i += 1
    else:
        pool = ProcessPool(n_cores)
        list(
            pool.imap(
                make_episode_without_decorate,
                [agent_scenario[0] for agent_scenario in agent_scenario_list],  # agents
                [agent_scenario[1] for agent_scenario in agent_scenario_list],
                [True for agent_scenario in agent_scenario_list],
            )
        )  # scenarios #we go over all agents and all scenarios for each agent
        pool.close()
        print("Multiprocessing done")


"""
Initialisation routine
"""
""" Parsing of config file"""
if not "GRID2VIZ_ROOT" in os.environ:
    #get grid2viz package path
    pkg_root_dir = os.getcwd()#os.path.dirname(os.path.abspath((os.path.join(os.path.abspath(__file__), os.pardir))))
    os.environ["GRID2VIZ_ROOT"] = pkg_root_dir
    path_cfg = os.path.join(os.environ["GRID2VIZ_ROOT"], "config.ini")
else:
    path_cfg = os.path.join(os.environ["GRID2VIZ_ROOT"], "config.ini")

parser = configparser.ConfigParser()
print(
    Fore.BLUE + Style.BRIGHT + "The config file used is located at: {}".format(path_cfg)
)
parser.read(path_cfg)

agents_dir = parser.get("DEFAULT", "agents_dir")
print(Fore.BLUE + "Agents data used is located at: {}".format(agents_dir))
cache_dir = os.path.join(agents_dir, "_cache")
"""Parsing of agent folder tree"""
agents = sorted(
    [
        file
        for file in os.listdir(agents_dir)
        if os.path.isdir(os.path.join(agents_dir, file)) and not file.startswith("_")
    ]
)
meta_json, best_agents, survival_df, attention_df = check_all_tree_and_get_meta_and_best(
    agents_dir, agents
)
scenarios = []
scenarios_agent = {}
agent_scenario = {}

try:
    n_cores = int(parser.get("DEFAULT", "n_cores"))
except configparser.NoOptionError:
    n_cores = 1

for agent in agents:
    scen_path = os.path.join(agents_dir, agent)
    scens = [
        file
        for file in os.listdir(scen_path)
        if os.path.isdir(os.path.join(scen_path, file))
    ]
    scenarios_agent[agent] = scens
    for scen in scens:
        if scen not in agent_scenario:
            agent_scenario[scen] = []
        if agent not in agent_scenario[scen]:
            agent_scenario[scen].append(agent)
    scenarios = scenarios + scens

scenarios = set(scenarios)
env_path = parser.get("DEFAULT", "env_dir")
# Create a .grid2viz directory in the user home directory
grid2viz_home_directory = Path.home() / ".grid2viz"
grid2viz_home_directory.mkdir(parents=False, exist_ok=True)
