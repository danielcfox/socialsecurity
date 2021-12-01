#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 10 12:12:17 2021

@author: dfox
"""

import math
import pandas as pd
import ss_cola as ssc

SS_BENEFIT_AGE = 62
SS_LIFESPAN = 130


def _max_wage_formula(awi):
    """
    Returns the maximum wage associated with a specific AWI
    """
    return round(awi * 60600.0 / 22935.42 / 300.0, 0) * 300.0


def _bend_point1_formula(awi):
    """
    Returns bend point 1 associated with a specific AWI
    """
    return round(awi * 180.0 / 9779.44, 0)


def _bend_point2_formula(awi):
    """
    Returns bend point 2 associated with a specific AWI
    """
    return round(awi * 1085.0 / 9779.44, 0)


class SSAWI:
    """
    Class for handling Social Security AWI (Average Wage Index) based
    calculations.

    This class is strictly for maintaining the AWI-based data.
    Methods will calculate some useful information, but nothing
    worker-specific should be stored here. That information belongs in the
    SSWorker class.
    """

    ss_wage_growth_default = 0.036  # cmp. ann. avg. last 20 yrs.
    mw_awi_offset = 2  # number of years maximum wage lags from AWI
    ss_eligibility_age = SS_BENEFIT_AGE - mw_awi_offset  # 60

    def __init__(self, ss_config, awi_hist, mw_hist,
                 awi_proj=ss_wage_growth_default):
        """
        SSAWI class constructor. Note this class MUST be instantiated AFTER
        the SSCOLA class is instantiated.

        Parameters
        ----------
        ss_config : SSConfig
            This class object is instatiated as part of the SSConfig
            instantiation process and that objecdt is passed in here.
        awi_hist : pd.Series, or dict (year as hash key)
            This history of the AWI, which is used in normalizing worker
            earnings when calculating the AIME (Average Indexed Monthly
            Earnings)
        mw_hist : pd.Series, or dict (year as hash key)
            The maximum annual wage history for social security taxes. Note
            that for all calculations, this does not seem necessary.
            However, it is used for the basic maximum earnings test for
            which we have tables from the SSA to compare to, so we will use
            it here.
        awi_proj : pd.Series, dict (NOT TESTED), list (NOT TESTED), or float
            The future AWI growth projections.
            The code is written to support all types, but for now only a
            series or fixed float value for each year has been tested.
            The default is 0.036 growth per year, or 3.6%.

        Returns
        -------
        None.

        """

        self.config = ss_config
        self.awi_proj = awi_proj
        self.current_year = self.config.get_current_year()
        # begin defaults

        # TBD: test AWI growth passed in as dict or list
        if isinstance(mw_hist, pd.Series):
            self.mw_dict = mw_hist.dropna().to_dict()
        elif isinstance(mw_hist, dict):
            self.mw_dict = mw_hist.copy()

        if isinstance(awi_hist, pd.Series):
            self.awi_dict = awi_hist.dropna().to_dict()
        elif isinstance(mw_hist, dict):
            self.awi_dict = awi_hist.copy()

        self.set_wage_growth_projection()

    def _calc_max_wage(self, mwyear):
        """
        This internal method calculates the maximum wage limit based on the
        statutory formula and the following rules:
          It cannot increase from the previous year if there was no COLA
              for that year
          It cannot decrease from the previous year
        Note this MUST be calculated AFTER the cola projections have been set
        and AFTER the previous year's max wage has been calculated

        Parameters
        ----------
        mwyear : int
            The year the maximum wage is calcalated for.

        Returns
        -------
        max_wage: int
            The maximum wage limit for social security payroll taxes for the
            specified year.

        """
        max_wage = 0.0
        cola_dict = self.config.get_cola_history()
        assert len(cola_dict) > 0
        awiyear = mwyear - SSAWI.mw_awi_offset
        if awiyear in self.awi_dict:
            awi = self.awi_dict[awiyear]
            max_wage = _max_wage_formula(awi)
            colayear = mwyear - ssc.SSCOLA.mw_cola_offset
            prevmwyear = max_wage - 1
            if colayear in cola_dict and prevmwyear in self.mw_dict:
                if ((cola_dict[colayear] == 0.0)
                        or (max_wage < self.mw_dict[prevmwyear])):
                    # self.mw_dict[mwyear] = self.mw_dict[prevmwyear]
                    max_wage = self.mw_dict[prevmwyear]
        return max_wage

    def set_wage_growth_projection(self, projection=None):
        """
        Sets the Social Security wage growth future projections
        MUST be called AFTER the COLA future projections have been set with
        _set_cola_projection()

        Parameters
        ----------
        projection : pandas Series, dict, list, or float
            The yearly AWI (Average Wage Index) growth projections.
            Note that this is NOT the wage growth of the Worker unless
            specified as such (NOT TESTED).
            A pandas Series must have the index as the year
            A dict must have the year as the hash
            A list must be sequential
                index 0: current year + 1 - awi offset (2)
            A float specifies a fixed growth rate for each subsequent year

        Returns
        -------
        None.

        Side effects
        -------
        Sets self.mw_dict

        """
        # TBD: unit test support for all the dtypes for ss wage growth
        #       this includes variable ss wage growth rates for each year
        #       perhaps randomize the setting of the rates with a fixed
        #       random seed
        # TBD: create a regression test for this
        # TBD: create unit and regression tests for the existence of negative
        #       ss wage growth rates in the future (we have seen it in the
        #       past).

        if projection is not None:
            self.awi_proj = projection

        cola_dict = self.config.get_cola_history()
        assert len(cola_dict) > 0
        wg_dict = ssc.get_proj_dict(
            self.current_year + 1 - SSAWI.mw_awi_offset,
            self.current_year + SS_LIFESPAN,
            self.awi_proj, SSAWI.ss_wage_growth_default)

        for year in wg_dict:
            self.awi_dict[year] = round(
                self.awi_dict[year-1] * (1.0 + wg_dict[year]), 2)
            mwyear = year + SSAWI.mw_awi_offset
            # sets self.mw_dict[mwyear]
            self.mw_dict[mwyear] = self._calc_max_wage(mwyear)

    def get_max_ss_wage(self, year=None):
        """
        Retrieves the social security maximum wage/earnings.

        If the year passed in is the current year or prior, then the figure
        returned is the actual number used for that year.

        If the year passed is later than the current year, then the figure
        returned is a projection based on the AWI growth projections and
        the formula/rules set by the SSA (see _calc_max_wage)

        If no year is specified (year is None), then a dictionary, hashed by
        year, is returned with all of the maximum wages for each year. For the
        current year, or prior, this is the exact limit used. For later than
        the current year, this is the projected value.

        Return value is only valid for the *current* COLA and wage growth
        projections. If the caller wishes to change the COLA and wage growth
        projections (there is a default), then they must call BOTH
        set_cola_projection() and set_wage_growth_projection() prior to
        calling this method (or simply re-instantiate an SSConfig object with
        the new projections specified in the constructor)

        Parameters
        ----------
        year : int, optional
            The year for which to get the social security maximum wage for.
            The default is None, which means return all of the values in
            a dictionary, using a hash of the year

        Returns
        -------
        float or dict
            float: The maximum wage for the specified year.
            dict: A dictionary, hashed by year, of the maximum wages for all
                    years

        """
        if year is not None:
            if year in self.mw_dict:
                return self.mw_dict[year]
            return 0.0
        return self.mw_dict

    def get_awi_value(self, year):
        if year in self.awi_dict:
            return self.awi_dict[year]
        return 0.0

    def _calc_bend_points(self, birth_year_worker):
        """
        Internal routine.
        Calculates the bend points for the monthly benefit calculation.

        Parameters
        ----------
        birth_year_worker : int
            The worker's year of birth.

        Returns
        -------
        bp1 : float
            The first (lower) bend point for the monthly benefit calculation.
        bp2 : float
            The second (higher) bend point for the monthly benefit calculation.

        """
        # bpyear is 60
        bpyear = birth_year_worker + SSAWI.ss_eligibility_age
        bp1 = _bend_point1_formula(self.awi_dict[bpyear])
        bp2 = _bend_point2_formula(self.awi_dict[bpyear])
        return bp1, bp2

    def calc_income_index_factor(self, birth_year):
        """
        Compute the income index factor, based on AWI
        The worker's wage for each year is normalized to the AWI for the year
        the worker turns 60 (SSAWI.ss_eligibility_age)
        Note that COLA is NOT factored at all into the income index factor
        This de-couples wage inflation and cost-of-living inflation.
        Since earnings prior to 1951 are not taken into account at all,
        the index we calculate for those years is 0.0

        Parameters
        ----------
        birth_year : int
            Worker's birth year.

        Returns
        -------
        incidx : dictionary
            The income index factor dictionary, hashed by year.

        """
        awi_at_ss_eligibility_age = \
            self.awi_dict[birth_year + SSAWI.ss_eligibility_age]
        incidx = {}
        for year in range(birth_year, birth_year + SS_LIFESPAN):
            if year < 1951:
                incidx[year] = 0.0
            else:
                age = year - birth_year
                if age < SSAWI.ss_eligibility_age:
                    incidx[year] = (awi_at_ss_eligibility_age
                                    / self.awi_dict[year])
                else:
                    incidx[year] = 1.0
        return incidx

    def calc_base_benefit(self, birth_year, aime):
        """
        Compute the base monthly benefit for the worker.
        The base benefit has no direct meaning but is a critical step in
        calculating the worker's monthly benefit.

        Technically, it is the benefit in the year of full retirement age
        (FRA), unadjusted for COLA from the year of eligibility (62), that the
        worker would receive if they started collecting benefits at FRA

        Parameters
        ----------
        birth_year : int
            The worker's birth year.
        aime : float
            The worker's average indexed monthly earnings.

        Returns
        -------
        base_benefit: float
            The worker's base benefit in the dollars for the year of
            eligibility
        bend_point_1: float
            The first bend point used for the calculation
        bend_point_2: float
            The second bend point used for the calculation

        """
        bend_point_1, bend_point_2 = self._calc_bend_points(birth_year)

        if aime < bend_point_1:
            base_benefit = aime * 0.9
        elif aime < bend_point_2:
            base_benefit = ((bend_point_1 * 0.9)
                            + ((aime - bend_point_1) * 0.32))
        else:
            base_benefit = ((bend_point_1 * 0.9)
                            + ((bend_point_2 - bend_point_1)
                               * 0.32)
                            + ((aime - bend_point_2) * 0.15))
        base_benefit = math.floor(base_benefit * 10.0) / 10.0

        return base_benefit, bend_point_1, bend_point_2
