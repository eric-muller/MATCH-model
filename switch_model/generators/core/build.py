# Copyright (c) 2015-2019 The Switch Authors. All rights reserved.
# Modifications copyright (c) 2021 Gregory J. Miller. All rights reserved.
# Licensed under the Apache License, Version 2.0, which is in the LICENSE file.
"""
Defines generation projects build-outs.

"""

import os
from pyomo.environ import *
from switch_model.financials import capital_recovery_factor as crf
from switch_model.reporting import write_table

dependencies = 'switch_model.timescales', 'switch_model.balancing.load_zones',\
    'switch_model.financials', 'switch_model.energy_sources.properties.properties'

def define_arguments(argparser):
    argparser.add_argument('--select_variants', choices=[None,'relaxed','binary'], default=None,
        help=
            "Run linear relaxation of variant selection"
    )

def define_components(mod):
    """

    Adds components to a Pyomo abstract model object to describe
    generation and storage projects. Unless otherwise stated, all power
    capacity is specified in units of MW and all sets and parameters
    are mandatory.

    GENERATION_PROJECTS is the set of generation and storage projects that
    have been built or could potentially be built. A project is a combination
    of generation technology, load zone and location. A particular build-out
    of a project should also include the year in which construction was
    complete and additional capacity came online. Members of this set are
    abbreviated as gen in parameter names and g in indexes. Use of p instead
    of g is discouraged because p is reserved for period.

    gen_tech[g] describes what kind of technology a generation project is
    using.

    GENERATION_TECHNOLOGIES is the set of all generation technologies in the model

    gen_energy_source[g] describes the energy source (fuel or renewable resource) used
    by each generator

    gen_load_zone[g] is the load zone this generation project is built in.

    gen_max_age[g] is the maximum number of years that a project can operate once built

    gen_is_variable[g]

    gen_is_baseload

    gen_is_storage

    gen_is_cogen

    gen_scheduled_outage_rate

    gen_forced_outage_rate

    VARIABLE_GENS is a subset of GENERATION_PROJECTS that only includes
    variable generators such as wind or solar that have exogenous
    constraints on their energy production.

    BASELOAD_GENS is a subset of GENERATION_PROJECTS that only includes
    baseload generators such as coal or geothermal.

    STORAGE_GENS

    NON_STORAGE_GENS

    GENS_IN_ZONE[z] and VARIABLE_GENS_IN_ZONE are indexed sets that lists all
    generation projects or variable generation projects within each load zone.

    GENS_BY_TECHNOLOGY

    CAPACITY_LIMITED_GENS is the subset of GENERATION_PROJECTS that are
    capacity limited. Most of these will be generator types that are resource
    limited like wind, solar or geothermal, but this can be specified for any
    generation project. Some existing or proposed generation projects may have
    upper bounds on increasing capacity or replacing capacity as it is retired
    based on permits or local air quality regulations.

    gen_capacity_limit_mw[g] is defined for generation technologies that are
    resource limited and do not compete for land area. This describes the
    maximum possible capacity of a generation project in units of megawatts.

    DISCRETELY_SIZED_GENS

    gen_unit_size[g]

    CCS_EQUIPPED_GENS

    gen_ccs_capture_efficiency[g]

    gen_ccs_energy_load[g]

    gen_uses_fuel[g]

    NON_FUEL_BASED_GENS

    FUEL_BASED_GENS

    gen_full_load_heat_rate

    MULTIFUEL_GENS

    FUELS_FOR_MULTIFUEL_GEN

    FUELS_FOR_GEN

    GENS_BY_ENERGY_SOURCE

    GENS_BY_NON_FUEL_ENERGY_SOURCE

    GENS_BY_FUEL

    -- CONSTRUCTION --

    GEN_BLD_YRS is a two-dimensional set of generation projects and the
    years in which construction or expansion occured or can occur. You
    can think of a project as a physical site that can be built out over
    time. BuildYear is the year in which construction is completed and
    new capacity comes online, not the year when constrution begins.
    BuildYear will be in the past for existing projects and will be the
    first year of an investment period for new projects. Investment
    decisions are made for each project/invest period combination. This
    set is derived from other parameters for all new construction. This
    set also includes entries for existing projects that have already
    been built and planned projects whose capacity buildouts have already been
    decided; information for legacy projects come from other files
    and their build years will usually not correspond to the set of
    investment periods. There are two recommended options for
    abbreviating this set for denoting indexes: typically this should be
    written out as (g, build_year) for clarity, but when brevity is
    more important (g, b) is acceptable.

    NEW_GEN_BLD_YRS is a subset of GEN_BLD_YRS that only
    includes projects that have not yet been constructed. This is
    derived by joining the set of GENERATION_PROJECTS with the set of
    NEW_GENERATION_BUILDYEARS using generation technology.

    PREDETERMINED_GEN_BLD_YRS is a subset of GEN_BLD_YRS that
    only includes existing or planned projects that are not subject to
    optimization.

    gen_predetermined_cap[(g, build_year) in PREDETERMINED_GEN_BLD_YRS] is
    a parameter that describes how much capacity was built in the past
    for existing projects, or is planned to be built for future projects.

    BuildGen[g, build_year] is a decision variable that describes
    how much capacity of a project to install in a given period. This also
    stores the amount of capacity that was installed in existing projects
    that are still online.

    GenCapacity[g, period] is an expression that returns the total
    capacity online in a given period. This is the sum of installed capacity
    minus all retirements.

    Max_Build_Potential[g] is a constraint defined for each project
    that enforces maximum capacity limits for resource-limited projects.

        GenCapacity <= gen_capacity_limit_mw

    gen_min_build_capacity[g]

    NEW_GEN_WITH_MIN_BUILD_YEARS is the subset of NEW_GEN_BLD_YRS for
    which minimum capacity build-out constraints will be enforced.

    BuildMinGenCap[g, build_year] is a binary variable that indicates
    whether a project will build capacity in a period or not. If the model is
    committing to building capacity, then the minimum must be enforced.

    Enforce_Min_Build_Lower[g, build_year]  and
    Enforce_Min_Build_Upper[g, build_year] are a pair of constraints that
    force project build-outs to meet the minimum build requirements for
    generation technologies that have those requirements. They force BuildGen
    to be 0 when BuildMinGenCap is 0, and to be greater than
    g_min_build_capacity when BuildMinGenCap is 1. In the latter case,
    the upper constraint should be non-binding; the upper limit is set to 10
    times the peak non-conincident demand of the entire system.

    GENS_WITH_VARIANTS

    VARIANT_GROUPS

    gen_variant_group[g]

    BuildVariants

    BuildVariants_Linking_Constraint

    GENS_IN_VARIANT_GROUP

    Enforce_Single_Project_Variant

    --- OPERATIONS ---

    PERIODS_FOR_GEN_BLD_YR[g, build_year] is an indexed
    set that describes which periods a given project build will be
    operational.

    BLD_YRS_FOR_GEN_PERIOD[g, period] is a complementary
    indexed set that identify which build years will still be online
    for the given project in the given period. For some project-period
    combinations, this will be an empty set.

    GEN_PERIODS describes periods in which generation projects
    could be operational. Unlike the related sets above, it is not
    indexed. Instead it is specified as a set of (g, period)
    combinations useful for indexing other model components.

    PERIODS_FOR_GEN

    BuildGen_assign_default_value

    GEN_PERIODS


    --- COSTS ---


    The following cost components are defined for each project. 

    ppa_energy_cost[g]

    ppa_capacity_cost[g]

    -- Derived cost parameters --

    GenCapacityCost[g, p] is the total annual capacity cost for each generator.

    TotalGenCapacityCost[p] is the total annual capacity cost.
    This aggregation is performed for the benefit of the objective function.

    """
    mod.GENERATION_PROJECTS = Set()

    mod.gen_tech = Param(mod.GENERATION_PROJECTS)
    mod.GENERATION_TECHNOLOGIES = Set(initialize=lambda m:
        {m.gen_tech[g] for g in m.GENERATION_PROJECTS}
    )
    mod.gen_energy_source = Param(mod.GENERATION_PROJECTS,
        validate=lambda m,val,g: val in m.ENERGY_SOURCES or val == "multiple")
    mod.gen_load_zone = Param(mod.GENERATION_PROJECTS, within=mod.LOAD_ZONES)
    mod.gen_max_age = Param(mod.GENERATION_PROJECTS, within=PositiveIntegers, default=25)
    mod.gen_is_variable = Param(mod.GENERATION_PROJECTS, within=Boolean)
    mod.gen_is_baseload = Param(mod.GENERATION_PROJECTS, within=Boolean, default=False)
    mod.gen_is_storage = Param(mod.GENERATION_PROJECTS, within=Boolean, default=False)
    mod.gen_is_cogen = Param(mod.GENERATION_PROJECTS, within=Boolean, default=False)
    mod.gen_scheduled_outage_rate = Param(mod.GENERATION_PROJECTS,
        within=PercentFraction, default=0)
    mod.gen_forced_outage_rate = Param(mod.GENERATION_PROJECTS,
        within=PercentFraction, default=0)
    mod.min_data_check('GENERATION_PROJECTS', 'gen_tech', 'gen_energy_source',
        'gen_load_zone', 'gen_is_variable')

    # Generation Project subsets
    mod.VARIABLE_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: m.gen_is_variable[g])
    
    mod.BASELOAD_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: m.gen_is_baseload[g])
    mod.STORAGE_GENS = Set(initialize=mod.GENERATION_PROJECTS, 
                           filter=lambda m, g: m.gen_is_storage[g])
    mod.NON_STORAGE_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: not m.gen_is_storage[g])

    """Construct GENS_* indexed sets efficiently with a
    'construction dictionary' pattern: on the first call, make a single
    traversal through all generation projects to generate a complete index,
    use that for subsequent lookups, and clean up at the last call."""
    def GENS_IN_ZONE_init(m, z):
        if not hasattr(m, 'GENS_IN_ZONE_dict'):
            m.GENS_IN_ZONE_dict = {_z: [] for _z in m.LOAD_ZONES}
            for g in m.GENERATION_PROJECTS:
                m.GENS_IN_ZONE_dict[m.gen_load_zone[g]].append(g)
        result = m.GENS_IN_ZONE_dict.pop(z)
        if not m.GENS_IN_ZONE_dict:
            del m.GENS_IN_ZONE_dict
        return result
    mod.GENS_IN_ZONE = Set(
        mod.LOAD_ZONES,
        initialize=GENS_IN_ZONE_init
    )
    mod.VARIABLE_GENS_IN_ZONE = Set(
        mod.LOAD_ZONES,
        initialize=lambda m, z: [g for g in m.GENS_IN_ZONE[z] if m.gen_is_variable[g]])

    def GENS_BY_TECHNOLOGY_init(m, t):
        if not hasattr(m, 'GENS_BY_TECH_dict'):
            m.GENS_BY_TECH_dict = {_t: [] for _t in m.GENERATION_TECHNOLOGIES}
            for g in m.GENERATION_PROJECTS:
                m.GENS_BY_TECH_dict[m.gen_tech[g]].append(g)
        result = m.GENS_BY_TECH_dict.pop(t)
        if not m.GENS_BY_TECH_dict:
            del m.GENS_BY_TECH_dict
        return result
    mod.GENS_BY_TECHNOLOGY = Set(
        mod.GENERATION_TECHNOLOGIES,
        initialize=GENS_BY_TECHNOLOGY_init
    )

    mod.CAPACITY_LIMITED_GENS = Set(within=mod.GENERATION_PROJECTS)
    mod.gen_capacity_limit_mw = Param(
        mod.CAPACITY_LIMITED_GENS, within=NonNegativeReals)
    mod.DISCRETELY_SIZED_GENS = Set(within=mod.GENERATION_PROJECTS)
    mod.gen_unit_size = Param(
        mod.DISCRETELY_SIZED_GENS, within=PositiveReals)
    mod.CCS_EQUIPPED_GENS = Set(within=mod.GENERATION_PROJECTS)
    mod.gen_ccs_capture_efficiency = Param(
        mod.CCS_EQUIPPED_GENS, within=PercentFraction)
    mod.gen_ccs_energy_load = Param(
        mod.CCS_EQUIPPED_GENS, within=PercentFraction)

    mod.gen_uses_fuel = Param(
        mod.GENERATION_PROJECTS,
        initialize=lambda m, g: (
            m.gen_energy_source[g] in m.FUELS
                or m.gen_energy_source[g] == "multiple"))
    mod.NON_FUEL_BASED_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: not m.gen_uses_fuel[g])
    mod.FUEL_BASED_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: m.gen_uses_fuel[g])

    mod.gen_full_load_heat_rate = Param(
        mod.FUEL_BASED_GENS,
        within=NonNegativeReals)
    mod.MULTIFUEL_GENS = Set(
        initialize=mod.GENERATION_PROJECTS,
        filter=lambda m, g: m.gen_energy_source[g] == "multiple")
    mod.FUELS_FOR_MULTIFUEL_GEN = Set(mod.MULTIFUEL_GENS, within=mod.FUELS)
    mod.FUELS_FOR_GEN = Set(mod.FUEL_BASED_GENS,
        initialize=lambda m, g: (
            m.FUELS_FOR_MULTIFUEL_GEN[g]
            if g in m.MULTIFUEL_GENS
            else [m.gen_energy_source[g]]))

    def GENS_BY_ENERGY_SOURCE_init(m, e):
        if not hasattr(m, 'GENS_BY_ENERGY_dict'):
            m.GENS_BY_ENERGY_dict = {_e: [] for _e in m.ENERGY_SOURCES}
            for g in m.GENERATION_PROJECTS:
                if g in m.FUEL_BASED_GENS:
                    for f in m.FUELS_FOR_GEN[g]:
                        m.GENS_BY_ENERGY_dict[f].append(g)
                else:
                    m.GENS_BY_ENERGY_dict[m.gen_energy_source[g]].append(g)
        result = m.GENS_BY_ENERGY_dict.pop(e)
        if not m.GENS_BY_ENERGY_dict:
            del m.GENS_BY_ENERGY_dict
        return result
    mod.GENS_BY_ENERGY_SOURCE = Set(
        mod.ENERGY_SOURCES,
        initialize=GENS_BY_ENERGY_SOURCE_init
    )
    mod.GENS_BY_NON_FUEL_ENERGY_SOURCE = Set(
        mod.NON_FUEL_ENERGY_SOURCES,
        initialize=lambda m, s: m.GENS_BY_ENERGY_SOURCE[s]
    )
    mod.GENS_BY_FUEL = Set(
        mod.FUELS,
        initialize=lambda m, f: m.GENS_BY_ENERGY_SOURCE[f]
    )

    mod.PREDETERMINED_GEN_BLD_YRS = Set(
        dimen=2)
    mod.GEN_BLD_YRS = Set(
        dimen=2,
        validate=lambda m, g, bld_yr: (
            (g, bld_yr) in m.PREDETERMINED_GEN_BLD_YRS or
            (g, bld_yr) in m.GENERATION_PROJECTS * m.PERIODS))
    mod.NEW_GEN_BLD_YRS = Set(
        dimen=2,
        initialize=lambda m: m.GEN_BLD_YRS - m.PREDETERMINED_GEN_BLD_YRS)
    mod.gen_predetermined_cap = Param(
        mod.PREDETERMINED_GEN_BLD_YRS,
        within=NonNegativeReals)
    mod.min_data_check('gen_predetermined_cap')

    def gen_build_can_operate_in_period(m, g, build_year, period):
        if build_year in m.PERIODS:
            online = m.period_start[build_year]
        else:
            online = build_year
        retirement = online + m.gen_max_age[g]
        return (
            online <= m.period_start[period] < retirement
        )
        # This is probably more correct, but is a different behavior
        # mid_period = m.period_start[period] + 0.5 * m.period_length_years[period]
        # return online <= m.period_start[period] and mid_period <= retirement

    # The set of periods when a project built in a certain year will be online
    mod.PERIODS_FOR_GEN_BLD_YR = Set(
        mod.GEN_BLD_YRS,
        within=mod.PERIODS,
        ordered=True,
        initialize=lambda m, g, bld_yr: set(
            period for period in m.PERIODS
            if gen_build_can_operate_in_period(m, g, bld_yr, period)))
    # The set of build years that could be online in the given period
    # for the given project.
    mod.BLD_YRS_FOR_GEN_PERIOD = Set(
        mod.GENERATION_PROJECTS, mod.PERIODS,
        initialize=lambda m, g, period: set(
            bld_yr for (gen, bld_yr) in m.GEN_BLD_YRS
            if gen == g and
               gen_build_can_operate_in_period(m, g, bld_yr, period)))
    # The set of periods when a generator is available to run
    mod.PERIODS_FOR_GEN = Set(
        mod.GENERATION_PROJECTS,
        initialize=lambda m, g: [p for p in m.PERIODS if len(m.BLD_YRS_FOR_GEN_PERIOD[g, p]) > 0]
    )

    def bounds_BuildGen(model, g, bld_yr):
        if((g, bld_yr) in model.PREDETERMINED_GEN_BLD_YRS):
            return (model.gen_predetermined_cap[g, bld_yr],
                    model.gen_predetermined_cap[g, bld_yr])
        elif(g in model.CAPACITY_LIMITED_GENS):
            # This does not replace Max_Build_Potential because
            # Max_Build_Potential applies across all build years.
            return (0, model.gen_capacity_limit_mw[g])
        else:
            return (0, None)
    mod.BuildGen = Var(
        mod.GEN_BLD_YRS,
        within=NonNegativeReals,
        bounds=bounds_BuildGen)
    # Some projects are retired before the first study period, so they
    # don't appear in the objective function or any constraints.
    # In this case, pyomo may leave the variable value undefined even
    # after a solve, instead of assigning a value within the allowed
    # range. This causes errors in the Progressive Hedging code, which
    # expects every variable to have a value after the solve. So as a
    # starting point we assign an appropriate value to all the existing
    # projects here.
    def BuildGen_assign_default_value(m, g, bld_yr):
        m.BuildGen[g, bld_yr] = m.gen_predetermined_cap[g, bld_yr]
    mod.BuildGen_assign_default_value = BuildAction(
        mod.PREDETERMINED_GEN_BLD_YRS,
        rule=BuildGen_assign_default_value)

    # note: in pull request 78, commit e7f870d..., GEN_PERIODS
    # was mistakenly redefined as GENERATION_PROJECTS * PERIODS.
    # That didn't directly affect the objective function in the tests
    # because most code uses GEN_TPS, which was defined correctly.
    # But it did have some subtle effects on the main Hawaii model.
    # It would be good to have a test that this set is correct,
    # e.g., assertions that in the 3zone_toy model,
    # ('C-Coal_ST', 2020) in m.GEN_PERIODS and ('C-Coal_ST', 2030) not in m.GEN_PERIODS
    # and 'C-Coal_ST' in m.GENS_IN_PERIOD[2020] and 'C-Coal_ST' not in m.GENS_IN_PERIOD[2030]
    mod.GEN_PERIODS = Set(
        dimen=2,
        initialize=lambda m:
            [(g, p) for g in m.GENERATION_PROJECTS for p in m.PERIODS_FOR_GEN[g]])

    mod.GenCapacity = Expression(
        mod.GENERATION_PROJECTS, mod.PERIODS,
        rule=lambda m, g, period: sum(
            m.BuildGen[g, bld_yr]
            for bld_yr in m.BLD_YRS_FOR_GEN_PERIOD[g, period]))

    mod.Max_Build_Potential = Constraint(
        mod.CAPACITY_LIMITED_GENS, mod.PERIODS,
        rule=lambda m, g, p: (
            m.gen_capacity_limit_mw[g] >= m.GenCapacity[g, p]))

    # The following components enforce minimum capacity build-outs.
    # Note that this adds binary variables to the model.
    mod.gen_min_build_capacity = Param (mod.GENERATION_PROJECTS,
        within=NonNegativeReals, default=0)
    mod.NEW_GEN_WITH_MIN_BUILD_YEARS = Set(
        initialize=mod.NEW_GEN_BLD_YRS,
        filter=lambda m, g, p: (
            m.gen_min_build_capacity[g] > 0))
    mod.BuildMinGenCap = Var(
        mod.NEW_GEN_WITH_MIN_BUILD_YEARS,
        within=Binary)
    mod.Enforce_Min_Build_Lower = Constraint(
        mod.NEW_GEN_WITH_MIN_BUILD_YEARS,
        rule=lambda m, g, p: (
            m.BuildMinGenCap[g, p] * m.gen_min_build_capacity[g]
            <= m.BuildGen[g, p]))

    # Define a constant for enforcing binary constraints on project capacity
    # The value of 100 GW should be larger than any expected build size. For
    # perspective, the world's largest electric power plant (Three Gorges Dam)
    # is 22.5 GW. I tried using 1 TW, but CBC had numerical stability problems
    # with that value and chose a suboptimal solution for the
    # discrete_and_min_build example which is installing capacity of 3-5 MW.
    mod._gen_max_cap_for_binary_constraints = 10**5
    mod.Enforce_Min_Build_Upper = Constraint(
        mod.NEW_GEN_WITH_MIN_BUILD_YEARS,
        rule=lambda m, g, p: (
            m.BuildGen[g, p] <= m.BuildMinGenCap[g, p] *
                mod._gen_max_cap_for_binary_constraints))


    # Mutually-exclusive project variants
    #####################################
    # The following components enforce building only one of several mutually-exclusive project variants.
    #create a new set of generator projects that are part of a mutually exclusive group
    mod.GENS_WITH_VARIANTS = Set(within=mod.GENERATION_PROJECTS)

    #need to create a set of the group names
    mod.VARIANT_GROUPS = Set() 

    #create a parameter that describes which group each generator is in
    mod.gen_variant_group = Param (
        mod.GENS_WITH_VARIANTS, 
        within=mod.VARIANT_GROUPS)

    if mod.options.select_variants != None:

        # Create binary decision variable for each generator that has a variant
        if mod.options.select_variants == 'binary':
            # Binary version of decision variable
            mod.BuildVariants = Var(
                mod.GENS_WITH_VARIANTS,
                within=Binary)
        elif mod.options.select_variants == 'relaxed':
            # Implement as a linear relaxation to improve solve time
            mod.BuildVariants = Var(
                mod.GENS_WITH_VARIANTS,
                within=NonNegativeReals,
                bounds=(0,1))
    

        # I need a linking constraint such that BuildGen <= max_capacity * BuildVariants
        mod.BuildVariants_Linking_Constraint = Constraint(
            mod.GENS_WITH_VARIANTS, mod.PERIODS,
            rule = lambda m, g, p: m.GenCapacity[g, p] <= m.gen_capacity_limit_mw[g] * m.BuildVariants[g]
        )

        # create a set describing which generators are in each group
        def GENS_IN_VARIANT_GROUP_init(m, gr):
            if not hasattr(m, 'GENS_IN_VARIANT_GROUP_dict'):
                m.GENS_IN_VARIANT_GROUP_dict = {_gr: [] for _gr in m.VARIANT_GROUPS}
                for g in m.GENS_WITH_VARIANTS:
                    m.GENS_IN_VARIANT_GROUP_dict[m.gen_variant_group[g]].append(g)
            result = m.GENS_IN_VARIANT_GROUP_dict.pop(gr)
            if not m.GENS_IN_VARIANT_GROUP_dict:
                del m.GENS_IN_VARIANT_GROUP_dict
            return result
        mod.GENS_IN_VARIANT_GROUP = Set(
            mod.VARIANT_GROUPS,
            initialize=GENS_IN_VARIANT_GROUP_init
        )

        #enforce constraint that only one variant of a group can be built
        # I need to sum the binary values of all of the project in each set
        #constraint should be indexed by group the sum for the group should <= 1
        mod.Enforce_Single_Project_Variant = Constraint(
            mod.VARIANT_GROUPS,
            rule=lambda m, gr: sum(m.BuildVariants[g] for g in m.GENS_IN_VARIANT_GROUP[gr]) <= 1)
    

    # Costs
    mod.ppa_energy_cost = Param (mod.GENERATION_PROJECTS, within=NonNegativeReals)
    mod.ppa_capacity_cost = Param (mod.GENERATION_PROJECTS, within=NonNegativeReals) 
    mod.min_data_check('ppa_energy_cost','ppa_capacity_cost')


    # Derived annual costs
    mod.GenCapacityCost = Expression(
        mod.GENERATION_PROJECTS, mod.PERIODS,
        rule=lambda m, g, p: sum(
            m.BuildGen[g, bld_yr] * m.ppa_capacity_cost[g]
            for bld_yr in m.BLD_YRS_FOR_GEN_PERIOD[g, p]))
    # Summarize costs for the objective function. Units should be total
    # annual future costs in $base_year real dollars. The objective
    # function will convert these to base_year Net Present Value in
    # $base_year real dollars.
    mod.TotalGenCapacityCost = Expression(
        mod.PERIODS,
        rule=lambda m, p: sum(
            m.GenCapacityCost[g, p]
            for g in m.GENERATION_PROJECTS))
    mod.Cost_Components_Per_Period.append('TotalGenCapacityCost')


def load_inputs(mod, switch_data, inputs_dir):
    """

    Import data describing project builds. The following files are
    expected in the input directory.

    generation_projects_info.csv has mandatory and optional columns. The
    operations.gen_dispatch module will also look for additional columns in
    this file. You may drop optional columns entirely or mark blank
    values with a dot '.' for select rows for which the column does not
    apply. Mandatory columns are:
        GENERATION_PROJECT, gen_tech, gen_energy_source, gen_load_zone,
        gen_max_age, gen_is_variable, gen_is_baseload,
        gen_full_load_heat_rate, gen_variable_om, gen_connect_cost_per_mw
    Optional columns are:
        gen_scheduled_outage_rate, gen_forced_outage_rate,
        gen_capacity_limit_mw, gen_unit_size, gen_ccs_energy_load,
        gen_ccs_capture_efficiency, gen_min_build_capacity, gen_is_cogen

    The following file lists existing builds of projects, and is
    optional for simulations where there is no existing capacity:

    gen_build_predetermined.csv
        GENERATION_PROJECT, build_year, gen_predetermined_cap

    The following file is mandatory, because it sets cost parameters for
    both existing and new project buildouts:

    gen_build_costs.csv
        GENERATION_PROJECT, build_year, gen_overnight_cost, gen_fixed_om

    """
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'generation_projects_info.csv'),
        auto_select=True,
        optional_params=['gen_is_baseload', 'gen_scheduled_outage_rate',
        'gen_forced_outage_rate', 'gen_capacity_limit_mw', 'gen_unit_size',
        'gen_ccs_energy_load', 'gen_ccs_capture_efficiency',
        'gen_min_build_capacity', 'gen_is_cogen', 'gen_excess_max', 'gen_variant_group'],
        index=mod.GENERATION_PROJECTS,
        param=(mod.gen_tech, mod.gen_energy_source,
               mod.gen_load_zone, mod.gen_is_variable, mod.gen_is_storage,
               mod.gen_is_baseload, mod.gen_scheduled_outage_rate,
               mod.gen_forced_outage_rate, mod.gen_capacity_limit_mw,
               mod.gen_unit_size, mod.gen_ccs_energy_load,
               mod.gen_ccs_capture_efficiency, mod.gen_full_load_heat_rate,
               mod.ppa_energy_cost, mod.gen_min_build_capacity,
               mod.ppa_capacity_cost, mod.gen_is_cogen,
               mod.gen_excess_max, mod.gen_variant_group, mod.gen_pricing_node))
    # Construct sets of capacity-limited, ccs-capable and unit-size-specified
    # projects. These sets include projects for which these parameters have
    # a value
    if 'gen_capacity_limit_mw' in switch_data.data():
        switch_data.data()['CAPACITY_LIMITED_GENS'] = {
            None: list(switch_data.data(name='gen_capacity_limit_mw').keys())}
    if 'gen_unit_size' in switch_data.data():
        switch_data.data()['DISCRETELY_SIZED_GENS'] = {
            None: list(switch_data.data(name='gen_unit_size').keys())}
    if 'gen_ccs_capture_efficiency' in switch_data.data():
        switch_data.data()['CCS_EQUIPPED_GENS'] = {
            None: list(switch_data.data(name='gen_ccs_capture_efficiency').keys())}
    if 'gen_variant_group' in switch_data.data():
        switch_data.data()['GENS_WITH_VARIANTS'] = {
            None: list(switch_data.data(name='gen_variant_group').keys())}
        switch_data.data()['VARIANT_GROUPS'] = {
            None: list(set(switch_data.data(name='gen_variant_group').values()))} #NOTE: This may be more efficient than building csvs to define sets if it works
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'gen_build_predetermined.csv'),
        auto_select=True,
        index=mod.PREDETERMINED_GEN_BLD_YRS,
        param=(mod.gen_predetermined_cap))
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'gen_build_years.csv'),
        set=mod.GEN_BLD_YRS)
    # read FUELS_FOR_MULTIFUEL_GEN from gen_multiple_fuels.dat if available
    multi_fuels_path = os.path.join(inputs_dir, 'gen_multiple_fuels.dat')
    if os.path.isfile(multi_fuels_path):
        switch_data.load(filename=multi_fuels_path)


def post_solve(m, outdir):
    write_table(
        m,
        sorted(m.GEN_PERIODS) if m.options.sorted_output else m.GEN_PERIODS,
        output_file=os.path.join(outdir, "gen_cap.csv"),
        headings=(
            "generation_project", "PERIOD",
            "gen_tech", "gen_load_zone", "gen_energy_source",
            "GenCapacity", "Annual_PPA_Capacity_Cost"),
        # Indexes are provided as a tuple, so put (g,p) in parentheses to
        # access the two components of the index individually.
        values=lambda m, g, p: (
            g, p,
            m.gen_tech[g], m.gen_load_zone[g], m.gen_energy_source[g],
            m.GenCapacity[g, p], m.GenCapacityCost[g, p]))
