# Copyright (C) 2021, RTE (http://www.rte-france.com/)
# See AUTHORS.txt
# SPDX-License-Identifier: MPL-2.0

import datetime as dt
import itertools

from dash import dcc, html
from dash import callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from grid2op.Exceptions import Grid2OpException
from pathlib import Path
import numpy as np

from grid2viz.src.kpi.EpisodeTrace import get_attacks_trace
from grid2viz.src.manager import grid2viz_home_directory
from grid2viz.src.manager import make_episode, make_network_agent_study
from grid2viz.src.utils import common_graph
from grid2viz.src.utils.callbacks_helpers import toggle_modal_helper
from grid2viz.src.utils.constants import DONT_SHOW_FILENAME
from grid2viz.src.utils.graph_utils import (
    relayout_callback,
    get_axis_relayout,
    layout_no_data,
)

layout_def = {
    "legend": {"orientation": "h"},
    "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
}


def generate_agent_icon(name, color):
    return html.Div(
        className="d-flex align-items-center mb-3",
        children=[
            html.I(className="col-1 fas fa-user-alt",
                   style={"font-size": "30px", "color": color}),
            html.Div(name, style={"font-size": "30px", "color": color})
        ]
    )


def register_callbacks_micro(app):

    @app.callback(
        [
            Output("slider", "min"),
            Output("slider", "max"),
            Output("slider", "value"),
            Output("slider", "marks"),
        ],
        [Input("window", "data"),Input("url", "pathname"),Input('auto-stepper', 'n_intervals'),Input("card-tabs", "active_tab")], #Input("card-tabs", "active_tab")
        [
            State('my-toggle-switch', "on"),
            #State("slider", "min"),
            #State("slider", "max"),
            #State("slider", "marks"),
            State("user_timestamps", "value"),
            State("agent_study", "data"),
            State("agent_ref", "data"),
            State("scenario", "data"),
        ],
    )
    def update_slider(window,url,n_intervals,active_tab,togle_value, selected_timestamp, agent_study,agent_ref, scenario):
        if window is None:
            raise PreventUpdate
        if(type(url) is not str):
            raise PreventUpdate
        url_split = url.split("/")
        url_split = url_split[len(url_split) - 1]

        if(url_split!="micro"):
            raise PreventUpdate

        ctx = callback_context
        # No clicks
        if not ctx.triggered:
            raise PreventUpdate
        # No clicks again
        # https://github.com/plotly/dash/issues/684
        if ctx.triggered[0]["value"] is None:
            raise PreventUpdate

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        new_episode = make_episode(
            agent_study if active_tab == "tab-0" else agent_ref, scenario
        )
        min_ = new_episode.timestamps.index(
            dt.datetime.strptime(window[0], "%Y-%m-%dT%H:%M:%S")
        )
        max_ = new_episode.timestamps.index(
            dt.datetime.strptime(window[1], "%Y-%m-%dT%H:%M:%S")
        )
        if(button_id == "auto-stepper"):
            if not togle_value:
                raise PreventUpdate
            else:
                value=min_+(n_intervals)%(max_-min_)

        else:

            #if value not in range(min_, max_):
            value = new_episode.timestamps.index(
                dt.datetime.strptime(selected_timestamp, "%Y-%m-%d %H:%M")
            )
        timestamp_range = new_episode.timestamps[min_:(max_+1)]
        timestamp_range = [timestamp.time() for timestamp in timestamp_range]

        if("is_action" in new_episode.action_data_table.columns):
            is_actions = list(new_episode.action_data_table.is_action[min_:(max_+1)].values)

            marks = {int(min_ + idx): {'label': t, 'style': {'color': 'orange'}} if is_act else {'label': t, 'style': {
                'color': 'black'}} for idx, (t, is_act) in enumerate(zip(timestamp_range, is_actions))}

            if ("is_alarm" in new_episode.action_data_table.columns):
                is_alarm = list(new_episode.action_data_table.is_alarm[min_:(max_ + 1)].values)
                for idx, mark_key in enumerate(marks.keys()):
                    if is_alarm[idx]:
                        marks[mark_key]['style']['background-color']='lightcoral'
        else:
            marks = {int(min_ + idx): {'label': t, 'style': {'color': 'black'}} for idx, t in enumerate(timestamp_range)}

        return min_, max_, value, marks
#

    @app.callback(
        [
            Output('auto-stepper', 'interval'),
            Output('auto-stepper', 'n_intervals'),
        ],
        Input('my-toggle-switch', "on"),
        State('auto-stepper', 'n_intervals'),
    )
    def activate_stepper(value,n_intervals):
#
        if(value):
            #disable_stepper=False
            interval=2000
            return interval,n_intervals
        else:
            disable_stepper=True
            interval = 30000000
            return interval,0

    @app.callback(
        Output("relayoutStoreMicro", "data"),
        [
            Input("env_charts_ts", "relayoutData"),
            Input("usage_rate_ts", "relayoutData"),
            Input("overflow_ts", "relayoutData"),
            Input("rewards_ts", "relayoutData"),
            Input("cumulated_rewards_ts", "relayoutData"),
            Input("action_topology_ts", "relayoutData"),
            Input("action_dispatch_ts", "relayoutData"),
            Input("voltage_flow_graph", "relayoutData"),
        ],
        [State("relayoutStoreMicro", "data")],
    )
    def relayout_store_overview(*args):
        return relayout_callback(*args)

    # indicator line
    @app.callback(
        [
            Output("rewards_ts", "figure"),
            Output("cumulated_rewards_ts", "figure"),
            Output("action_topology_ts", "figure"),
            Output("action_dispatch_ts", "figure"),
        ],
        [
            Input("relayoutStoreMicro", "data"),
            Input("window", "data"),
            State("agent_study", "data"),
        ],
        [
            State("rewards_ts", "figure"),
            State("cumulated_rewards_ts", "figure"),
            State("action_topology_ts", "figure"),
            State("action_dispatch_ts", "figure"),
            State("agent_ref", "data"),
            State("scenario", "data"),
        ],
    )
    def load_ts(
        relayout_data_store,
        window,
        study_agent,
        rew_figure,
        cumrew_figure,
        topology_action_fig,
        dispatch_action_fig,
        agent_ref,
        scenario,
    ):

        figures = [rew_figure, cumrew_figure, topology_action_fig,dispatch_action_fig]

        condition = (
            relayout_data_store is not None and relayout_data_store["relayout_data"]
        )
        if condition:
            relayout_data = relayout_data_store["relayout_data"]
            relayouted = False
            for figure in figures:
                axis_layout = get_axis_relayout(figure, relayout_data)
                if axis_layout is not None:
                    figure["layout"].update(axis_layout)
                    relayouted = True
            if relayouted:
                return figures

        rew_figure, cumrew_figure = common_graph.make_rewards_ts(
            study_agent, agent_ref, scenario, rew_figure, cumrew_figure
        )

        new_topology_action_fig,new_dispatch_action_fig = common_graph.make_action_ts(
            study_agent, agent_ref, scenario, topology_action_fig["layout"]
        )
        #TO DO
        figures = [rew_figure, cumrew_figure, new_topology_action_fig,new_dispatch_action_fig]

        if window is not None:
            start_datetime = dt.datetime.strptime(window[0], "%Y-%m-%dT%H:%M:%S")
            end_datetime = dt.datetime.strptime(window[-1], "%Y-%m-%dT%H:%M:%S")
            for figure in figures:
                figure["layout"].update(
                    xaxis=dict(range=[start_datetime, end_datetime], autorange=False)
                )

        return figures

    # flux line callback
    # @app.callback(
    #     [Output("line_side_choices", "options"), Output("line_side_choices", "value")],
    #     [Input("voltage_flow_choice", "value"), Input("flow_radio", "value")],
    #     [State("agent_study", "data"), State("scenario", "data")],
    # )
    # def load_voltage_flow_line_choice(category, flow_choice, study_agent, scenario):
    #     option = []
    #     new_episode = make_episode(study_agent, scenario)
    #
    #     if category == "voltage":
    #         for name in new_episode.line_names:
    #             option.append({"label": "ex_" + name, "value": "ex_" + name})
    #             option.append({"label": "or_" + name, "value": "or_" + name})
    #     if category == "flow":
    #         for name in new_episode.line_names:
    #             if flow_choice == "active_flow":
    #                 option.append(
    #                     {"label": "ex_active_" + name, "value": "ex_active_" + name}
    #                 )
    #                 option.append(
    #                     {"label": "or_active_" + name, "value": "or_active_" + name}
    #                 )
    #             if flow_choice == "current_flow":
    #                 option.append(
    #                     {"label": "ex_current_" + name, "value": "ex_current_" + name}
    #                 )
    #                 option.append(
    #                     {"label": "or_current_" + name, "value": "or_current_" + name}
    #                 )
    #
    #             if flow_choice == "flow_usage_rate":
    #                 option.append(
    #                     {"label": "usage_rate_" + name, "value": "usage_rate_" + name}
    #                 )
    #     if category == "redispatch":
    #         option = [
    #             {"label": gen_name, "value": gen_name}
    #             for gen_name in new_episode.prod_names
    #         ]
    #
    #     return option, [option[0]["value"]]

    # @app.callback(
    #     Output("voltage_flow_graph", "figure"),
    #     [
    #         Input("line_side_choices", "value"),
    #         Input("voltage_flow_choice", "value"),
    #         Input("relayoutStoreMicro", "data"),
    #         Input("window", "data"),
    #     ],
    #     [
    #         State("voltage_flow_graph", "figure"),
    #         State("agent_study", "data"),
    #         State("scenario", "data"),
    #     ],
    # )
    # def load_flow_voltage_graph(
    #     selected_objects,
    #     choice,
    #     relayout_data_store,
    #     window,
    #     figure,
    #     study_agent,
    #     scenario,
    # ):
    #     if relayout_data_store is not None and relayout_data_store["relayout_data"]:
    #         relayout_data = relayout_data_store["relayout_data"]
    #         layout = figure["layout"]
    #         new_axis_layout = get_axis_relayout(figure, relayout_data)
    #         if new_axis_layout is not None:
    #             layout.update(new_axis_layout)
    #             return figure
    #     new_episode = make_episode(study_agent, scenario)
    #     if selected_objects is not None:
    #         if choice == "voltage":
    #             figure["data"] = load_voltage_for_lines(selected_objects, new_episode)
    #         if "flow" in choice:
    #             figure["data"] = load_flows_for_lines(selected_objects, new_episode)
    #         if "redispatch" in choice:
    #             figure["data"] = load_redispatch(selected_objects, new_episode)
    #
    #     if window is not None:
    #         figure["layout"].update(xaxis=dict(range=window, autorange=False))
    #
    #     return figure
    #
    # @app.callback(
    #     Output("flow_radio", "style"),
    #     [Input("voltage_flow_choice", "value")],
    # )
    # def load_flow_graph(choice):
    #     if choice == "flow":
    #         return {"display": "block"}
    #     else:
    #         return {"display": "none"}

    def load_voltage_for_lines(lines, new_episode):
        voltage = new_episode.flow_and_voltage_line
        traces = []

        for value in lines:
            # the first 2 characters are the side of line ('ex' or 'or')
            line_side = str(value)[:2]
            line_name = str(value)
            if line_side == "ex":
                traces.append(
                    go.Scatter(
                        x=new_episode.timestamps,
                        # remove the first 3 char to get the line name and round to 3 dec
                        y=np.array(voltage["ex"]["voltage"][line_name[3:]].tolist()),
                        name=line_name,
                    )
                )
            if line_side == "or":
                traces.append(
                    go.Scatter(
                        x=new_episode.timestamps,
                        y=np.array(voltage["or"]["voltage"][line_name[3:]].tolist()),
                        name=line_name,
                    )
                )
        return traces

    def load_redispatch(generators, new_episode):
        actual_dispatch = new_episode.actual_redispatch
        target_dispatch = new_episode.target_redispatch
        traces = []

        x = new_episode.timestamps

        for gen in generators:
            traces.append(
                go.Scatter(x=x, y=actual_dispatch[gen], name=f"{gen} actual dispatch")
            )
            traces.append(
                go.Scatter(x=x, y=target_dispatch[gen], name=f"{gen} target dispatch")
            )

        return traces

    def load_flows_for_lines(lines, new_episode):
        flow = new_episode.flow_and_voltage_line
        traces = []

        x = new_episode.timestamps

        for value in lines:
            line_side = str(value)[
                :2
            ]  # the first 2 characters are the side of line ('ex' or 'or')
            flow_type = str(value)[3:].split("_", 1)[
                0
            ]  # the type is the 1st part of the string: 'type_name'
            line_name = str(value)[3:].split("_", 1)[
                1
            ]  # the name is the 2nd part of the string: 'type_name'
            if line_side == "ex":
                traces.append(
                    go.Scatter(x=x, y=np.array(flow["ex"][flow_type][line_name].tolist()), name=value)
                )
            elif line_side == "or":
                traces.append(
                    go.Scatter(x=x, y=np.array(flow["or"][flow_type][line_name].tolist()), name=value)
                )
            else:  # this concern usage rate
                name = value.split("_", 2)[2]  # get the powerline name
                index_powerline = list(new_episode.line_names).index(name)
                usage_rate_powerline = new_episode.rho.loc[
                    new_episode.rho["equipment"] == index_powerline
                ]["value"]

                traces.append(go.Scatter(x=x, y=np.array(usage_rate_powerline.tolist()), name=name))

        return traces

    # context line callback
    @app.callback(
        [Output("asset_selector", "options"), Output("asset_selector", "value")],
        [Input("environment_choices_buttons", "value")],
        [State("agent_study", "data"), State("scenario", "data")],
    )
    def update_ts_graph_avail_assets(kind, study_agent, scenario):
        new_episode = make_episode(study_agent, scenario)
        return common_graph.ts_graph_avail_assets(kind, new_episode)

    @app.callback(
        Output("env_charts_ts", "figure"),
        [
            Input("asset_selector", "value"),
            Input("relayoutStoreMicro", "data"),
            Input("window", "data"),
        ],
        [
            State("env_charts_ts", "figure"),
            State("environment_choices_buttons", "value"),
            State("scenario", "data"),
            State("agent_study", "data"),
        ],
    )
    def load_context_data(
        equipments, relayout_data_store, window, figure, kind, scenario, agent_study
    ):
        if relayout_data_store is not None and relayout_data_store["relayout_data"]:
            relayout_data = relayout_data_store["relayout_data"]
            layout = figure["layout"]
            new_axis_layout = get_axis_relayout(figure, relayout_data)
            if new_axis_layout is not None:
                layout.update(new_axis_layout)
                return figure

        if kind is None:
            return figure
        if isinstance(equipments, str):
            equipments = [equipments]  # to make pd.series.isin() work
        episode = make_episode(agent_study, scenario)
        figure["data"] = common_graph.environment_ts_data(kind, episode, equipments)

        if window is not None:
            figure["layout"].update(xaxis=dict(range=window, autorange=False))

        return figure

    @app.callback(
        [Output("overflow_ts", "figure"), Output("usage_rate_ts", "figure")],
        [Input("relayoutStoreMicro", "data"), Input("window", "data")],
        [
            State("overflow_ts", "figure"),
            State("usage_rate_ts", "figure"),
            State("agent_study", "data"),
            State("scenario", "data"),
        ],
    )
    def update_agent_ref_graph(
        relayout_data_store,
        window,
        figure_overflow,
        figure_usage,
        study_agent,
        scenario,
    ):
        if relayout_data_store is not None and relayout_data_store["relayout_data"]:
            relayout_data = relayout_data_store["relayout_data"]
            layout_usage = figure_usage["layout"]
            new_axis_layout = get_axis_relayout(figure_usage, relayout_data)
            if new_axis_layout is not None:
                layout_usage.update(new_axis_layout)
                figure_overflow["layout"].update(new_axis_layout)
                return figure_overflow, figure_usage

        if window is not None:
            figure_overflow["layout"].update(xaxis=dict(range=window, autorange=False))
            figure_usage["layout"].update(xaxis=dict(range=window, autorange=False))

        return common_graph.agent_overflow_usage_rate_trace(
            make_episode(study_agent, scenario), figure_overflow, figure_usage
        )

    @app.callback(
        Output("timeseries_table_micro", "data"), [Input("timeseries_table", "data")]
    )
    def sync_timeseries_table(data):
        return data

    @app.callback(
        [
            #Output("card-content", "children"),
            Output("interactive_graph", "figure"),
            Output("usage_rate_ts_network", "figure"),
            Output("tooltip_table_micro", "children"),
            Output("slider","disabled"),
            Output("my-toggle-switch", "disabled"),
        ],
        [Input("slider", "value"), Input("card-tabs", "active_tab")],Input("my-toggle-switch", "off"),
        [

            State("agent_study", "data"),
            State("scenario", "data"),
            State("agent_ref", "data"),
            State("interactive_graph", "figure"),
            State("slider", "min"),
            #State("card-content", "children"),
        ],
    )
    def update_interactive_graph(
        slider_value, active_tab,Power_Button_off, agent_study, scenario, agent_ref,current_network_fig, slider_min,
    ):
        episode = make_episode(
            agent_study if active_tab == "tab-0" else agent_ref, scenario
        )
        usage_rate_traces = go.Figure(data=episode.usage_rate_trace).data
        try:
            act = episode.actions[slider_value]
        except:# Grid2OpException as ex:
            disabled_Power_Button=True
            disabled_Slider=True
            return (
                dcc.Graph(
                    figure=go.Figure(
                        layout=layout_no_data(
                            "The agent is game over at this time step."
                        )
                    )
                ),
                go.Figure(layout=layout_def, data=usage_rate_traces),
                "",
                disabled_Slider,
                disabled_Power_Button
            )
        #current_network_fig=None#card_content[0]['props']['figure']#None
        if(current_network_fig):
            print("fig here")
        disabled_Power_Button = False
        disabled_Slider = False
        redraw_full_graph = not bool(Power_Button_off)
        if any(act.get_types()):
            act_as_str = str(act)
        else:
            act_as_str = "NO ACTION"

        network_figure = make_network_agent_study(episode, timestep=slider_value, figure_obs=current_network_fig,redraw=redraw_full_graph)

        generate_agent_icon("Redispatch Agent", "red"),
        generate_agent_icon("Curtailment Agent", "red"),
        generate_agent_icon("Topology Agent 1 zone", "red"),
        generate_agent_icon("Topology Agent 2nd zone", "red"),
        generate_agent_icon("Topology Agent 3rd zone", "grey"),
        agents_icons = []
        agents_str = "Involved agents:\n"
        if "Force reconnection" in act_as_str:
            agents_str += "\t - Reconnection Agent\n"
            agents_icons.append(generate_agent_icon("Reconnection Agent (discrete)", "red"))
        else:
            agents_icons.append(generate_agent_icon("Reconnection Agent (discrete)", "grey"))
        if "NOT perform any redispatching" not in act_as_str:
            agents_str += "\t - Redispatching and Curtailment Agent Agent\n"
            agents_icons.append(generate_agent_icon("Redispatching and Curtailment Agent (continuous)", "red"))
            network_figure = make_network_agent_study(episode, timestep=slider_value, figure_obs=current_network_fig,
                                                      redraw=redraw_full_graph, draw_loads=True)
        else:
            agents_icons.append(generate_agent_icon("Redispatching and Curtailment Agent (continuous)", "grey"))
            network_figure = make_network_agent_study(episode, timestep=slider_value, figure_obs=current_network_fig,
                                                      redraw=redraw_full_graph)
        # if "NOT perform any curtailment" not in act_as_str:
        #     agents_str += "\t - Curtailement Agent\n"
        #     agents_icons.append(generate_agent_icon("Curtailment Agent", "red"))
        # else:
        #     agents_icons.append(generate_agent_icon("Curtailment Agent", "grey"))
        if "Assign bus" in act_as_str:
            sub_name_modified = list(
                itertools.chain.from_iterable(episode.action_data_table.subs_modified)
            )
            sub_id_modified = [
                int(str.split("_")[1])
                for str in episode.action_data_table.subs_modified[slider_value]
            ]
            nb_subs_modified = len(sub_id_modified)
            if nb_subs_modified == 1:
                agents_str += "\t - 1 Topology Agent\n"
                agents_icons.append(generate_agent_icon("Topology Agent 1 zone (discrete)", "red"))
                agents_icons.append(generate_agent_icon("Topology Agent 2nd zone (discrete)", "grey"))
                agents_icons.append(generate_agent_icon("Topology Agent 3rd zone (discrete)", "grey"))
            if nb_subs_modified == 2:
                agents_str += "\t - 2 Topology Agents on 2 zones\n"
                agents_icons.append(generate_agent_icon("Topology Agent 1 zone (discrete)", "red"))
                agents_icons.append(generate_agent_icon("Topology Agent 2nd zone (discrete)", "red"))
                agents_icons.append(generate_agent_icon("Topology Agent 3rd zone (discrete)", "grey"))
            if nb_subs_modified == 3:
                agents_str += "\t - 3 Topology Agents on 3 zones\n"
                agents_icons.append(generate_agent_icon("Topology Agent 1 zone (discrete)", "red"))
                agents_icons.append(generate_agent_icon("Topology Agent 2nd zone (discrete)", "red"))
                agents_icons.append(generate_agent_icon("Topology Agent 3rd zone (discrete)", "red"))
        else:
            agents_icons.append(generate_agent_icon("Topology Agent 1 zone (discrete)", "grey"))
            agents_icons.append(generate_agent_icon("Topology Agent 2nd zone (discrete)", "grey"))
            agents_icons.append(generate_agent_icon("Topology Agent 3rd zone (discrete)", "grey"))

        new_fig = make_subplots()
        new_fig.update_layout(layout_def)
        for trace in usage_rate_traces:
            trace.x = trace.x[slider_min:slider_value + 1]
            trace.y = trace.y[slider_min:slider_value + 1]
            new_fig.add_trace(trace)
        # attacks_traces = get_attacks_trace(episode, ["total"])
        # if len(attacks_traces) > 0:
        #     attack_trace = attacks_traces[0]
        #     attack_trace.x = attack_trace.x[slider_min:slider_value + 1]
        #     attack_trace.y = attack_trace.y[slider_min:slider_value + 1]
        #     attack_trace.mode = "lines"
        #     attack_trace.line.color = "purple"
        #     new_fig.add_trace(attack_trace, secondary_y=True)
        new_fig.add_trace(
            go.Scatter(x=usage_rate_traces[0].x, y=np.ones(len(usage_rate_traces[0].x)), line=dict(color='black', width=4, dash='dash'), name="Danger Threshold")
        )
        # new_fig.update_yaxes(range=[0, 2],title_text="Maximum usate rate over the Network")
        # new_fig.update_yaxes(range=[0, 1], secondary_y=True, title_text="Number of lines under Attack")



        return (
            #dcc.Graph(figure=make_network_agent_study(episode, timestep=slider_value,figure_obs=current_network_fig)),
            #yes in case the power button is turned off
            network_figure,
            new_fig,
            agents_icons,
            disabled_Slider,
            disabled_Power_Button
        )

    @app.callback(
        [
            Output("modal_micro", "is_open"),
            Output("dont_show_again_div_micro", "className"),
        ],
        [Input("close_micro", "n_clicks"), Input("page_help", "n_clicks")],
        [State("modal_micro", "is_open"), State("dont_show_again_micro", "checked")],
    )
    def toggle_modal(close_n_clicks, open_n_clicks, is_open, dont_show_again):
        dsa_filepath = Path(grid2viz_home_directory) / DONT_SHOW_FILENAME("micro")
        return toggle_modal_helper(
            close_n_clicks,
            open_n_clicks,
            is_open,
            dont_show_again,
            dsa_filepath,
            "page_help",
        )

    @app.callback(Output("modal_image_micro", "src"), [Input("url", "pathname")])
    def show_image(pathname):
        return app.get_asset_url("screenshots/agent_study.png")