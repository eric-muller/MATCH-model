# Copyright (c) 2021 The MATCH Authors. All rights reserved.
# Licensed under the Apache License, Version 2.0, which is in the LICENSE file.

"""

"""

import os
from pyomo.environ import *
import pandas as pd

dependencies = 'match_model.timescales', 'match_model.balancing.load_zones',\
    'match_model.financials',\
    'match_model.generators.core.build', 'match_model.generators.core.dispatch', \
    'match_model.generators.extensions.storage'
    
def define_components(mod):
    """
    If the average Pnode revenue is higher than the contract cost, the model will try to overbuild
    """

    mod.social_cost_of_carbon = Param(
        within=NonNegativeReals,
        default=0)

    mod.gen_emission_factor = Param(mod.NON_STORAGE_GENS)

    mod.gen_ccs_capture_efficiency = Param(
        mod.CCS_EQUIPPED_GENS, within=PercentFraction)

    mod.gen_ccs_energy_load = Param(
        mod.CCS_EQUIPPED_GENS, within=PercentFraction)

    # Caclulate emissions from each generator
    def GeneratorEmissions_rule(m, g, t):
        if g not in m.CCS_EQUIPPED_GENS:
            return (m.TotalGen[g,t] * m.gen_emission_factor[g])
        else:
            ccs_emission_frac = 1 - m.gen_ccs_capture_efficiency[g]
            return (m.TotalGen[g,t] * m.gen_emission_factor[g] * ccs_emission_frac)
    mod.GeneratorEmissions = Expression(
        mod.NON_STORAGE_GEN_TPS,
        rule=GeneratorEmissions_rule
    )

    # Costs for objective function
    ##############################

    # Pnode Revenue is earned from injecting power into the grid 
    mod.GenPnodeRevenue = Expression(
        mod.GEN_TPS,
        rule=lambda m, g, t: -1 * (m.DispatchGen[g,t] * m.nodal_price[m.gen_pricing_node[g],t] if g in m.NON_STORAGE_GENS else 0))
        
    mod.GenPnodeRevenueInTP = Expression(
        mod.TIMEPOINTS,
        rule=lambda m,t: sum(m.GenPnodeRevenue[g,t]  for g in m.NON_STORAGE_GENS))
    # add Pnode revenue to objective function
    mod.Cost_Components_Per_TP.append('GenPnodeRevenueInTP')

    
def load_inputs(mod, match_data, inputs_dir):
    """
    """
    match_data.load_aug(
        filename=os.path.join(inputs_dir, 'generation_projects_info.csv'),
        auto_select=True,
        optional_params=['gen_ccs_energy_load', 'gen_ccs_capture_efficiency'],
        index=mod.GENERATION_PROJECTS,
        param=[mod.gen_emission_factor, mod.gen_ccs_energy_load, mod.gen_ccs_capture_efficiency])

    # construct set of CCS equipped gens based on whether the CCS capture efficiency is specified
    if 'gen_ccs_capture_efficiency' in match_data.data():
        match_data.data()['CCS_EQUIPPED_GENS'] = {
            None: list(match_data.data(name='gen_ccs_capture_efficiency').keys())}

def post_solve(instance, outdir):
    congestion_data = [{
        "generation_project": g,
        "timestamp": instance.tp_timestamp[t],
        "Generation_MW": value(instance.TotalGen[g, t]), 
        "Contract_Cost": value(instance.TotalGen[g, t] * instance.ppa_energy_cost[g]),
        "Pnode_Revenue": value(instance.GenPnodeRevenue[g,t] + instance.ExcessGenPnodeRevenue[g,t]) if instance.gen_is_variable[g] else value(instance.GenPnodeRevenue[g, t]),
        "Delivery_Cost": value(instance.GenDeliveryCost[g,t]),
    } for (g, t) in instance.NON_STORAGE_GEN_TPS]
    nodal_by_gen_df = pd.DataFrame(congestion_data)
    nodal_by_gen_df.set_index(["generation_project", "timestamp"], inplace=True)
    nodal_by_gen_df.to_csv(os.path.join(outdir, "costs_by_gen.csv"))

    nodal_data = [{
        "timestamp": instance.tp_timestamp[t],
        "Dispatched Generation PPA Cost":value(instance.GenPPACostInTP[t]),
        "Excess Generation PPA Cost":value(instance.ExcessGenPPACostInTP[t]),
        "Dispatched Generation Pnode Revenue": value(instance.GenPnodeRevenueInTP[t]),
        "Excess Generation Pnode Revenue": value(instance.ExcessGenPnodeRevenueInTP[t]),
        "DLAP Cost": value(instance.DLAPLoadCostInTP[t]),
    } for t in instance.TIMEPOINTS]
    nodal_df = pd.DataFrame(nodal_data)
    nodal_df.set_index(["timestamp"], inplace=True)
    nodal_df.to_csv(os.path.join(outdir, "costs_by_tp.csv"))



    


    
