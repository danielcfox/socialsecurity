#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 10 11:27:53 2021

@author: dfox
"""
import math
import pandas as pd

SS_BENEFIT_AGE = 62
SS_LIFESPAN = 130


def get_proj_dict(start_year, final_year, projection, default):
    """
    Converts a projection (as a pandas Series, dict, list, or float) to
    a dictionary. If there is a missing value for years between start_year and
    final_year, then the value from the most recent previous year will be used.

    Note that this method is used both for COLA and AWI growth projections,
    and could be used for any other projections of data that might be used in
    the future.

    Parameters
    ----------
    start_year : int
        The first year of the span of time that the dictionary should start
        with.
    final_year : int
        The final year (inclusive) of the span of itime that the dictionary
        should end with.
    projection : pandas Series or dict or list or float
        The projection for each year.
        pandas Series: missing data will be dropped first, so the resulting
            dictionary returned will fill in those missing values with the
            most recent previous year's value
        dict: the new dictionary will be this one but with filling in
            missing values with the year's most recent value
        list: list must begin with start_year and be populated sequentially
            and there can be no missing values, except that the list does not
            have to end prior to final_year, and the dictionary
            returned will set the values for all subsequent years to the
            value of the most recent previous year specified.
    default : float
        This is the value used for start_year if start_year is not specified.

    Returns
    -------
    pr_dict : dict
        A dictionary of the projections.

    """

    if isinstance(projection, pd.Series):
        pr_dict = projection.dropna().to_dict()
    elif isinstance(projection, dict):
        pr_dict = projection
    elif isinstance(projection, list):
        pr_dict = {}
        year = start_year
        for val in projection:
            pr_dict[year] = val
            year += 1
            if year > final_year:
                break
    else:  # type float
        pr_dict = {}

    recent_year = start_year
    for year in range(start_year, final_year + 1):
        if year not in pr_dict:
            if recent_year in pr_dict:
                pr_dict[year] = pr_dict[recent_year]
            else:
                pr_dict[year] = default
        else:
            recent_year = year

    return pr_dict


class SSCOLA:
    """
    Class for handling Social Security COLA (Cost-Of-Living Adjustment) based
    calculations.

    This class is strictly for maintaining the COLA-based data.
    Methods will calculate some useful information, but nothing
    worker-specific should be stored here. That information belongs in the
    SSWorker class.
    """

    ss_cola_default = 0.024  # cmp. ann. avg. last 20 yrs.
    mw_cola_offset = 1  # number of years maximum wage lags from COLA

    def __init__(self, ss_config, cola_hist, cola_proj=ss_cola_default):
        """

        Parameters
        ----------
        ss_config : SSConfig
            This class object is instatiated as part of the SSConfig
            instantiation process and that objecdt is passed in here.
        cola_hist : pd.Series, or dict (year as hash key)
            This history of the COLA used in past years. Social Security
            benefits are increased each year this is a COLA (rare that there
            isn't one)
        cola_proj : pd.Series, dict (NOT TESTED), list (NOT TESTED), or float
            The future COLA projections.
            The code is written to support all types, but for now only a
            series or fixed float value for each year has been tested.
            FOR THIS CLASS, the default projected COLA is 0.024 each year,
            or 2.4%.
            What the caller class, SSConfig, uses as its own default is
            outside the scope of this class. However, it is envisioned that
            the SSConfig class will use the SSA's own projections as the
            default.

        Returns
        -------
        None.

        Side Effects
        ------------
        Initializes object variables, of course.
        Specifically it calculates the cola_dict variable which contains
        the COLA for all years, past (actual) values, and future (projected)
        values

        """
        self.config = ss_config
        self.cola_proj = cola_proj
        self.current_year = self.config.get_current_year()
        # begin defaults

        # TBD: test COLA passed in as dict or list
        if isinstance(cola_hist, pd.Series):
            self.cola_dict = cola_hist.dropna().to_dict()
        elif isinstance(cola_hist, dict):
            self.cola_dict = cola_hist.copy()

        self.set_cola_projection(cola_proj)

    def set_cola_projection(self, projection):
        """

        Parameters
        ----------
        projection : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        # TBD: unit test support for all the dtypes for cola
        #       this includes variable cola rates for each year
        #       perhaps randomize the setting of the rates with a fixed
        #       random seed
        # TBD: create a regression test for this
        # TBD: create unit and regression tests for the existence of negative
        #       COLA in the future (we have seen it in the past). For SSA
        #       purposes there can never be a negative COLA, but the data
        #       that feeds into COLA can show a cost-of-living decrease
        #       In that case, the decrease "carries over" so that, if, say
        #       one year there's a decrease in COL of 0.5%, and then next
        #       year an increase of 1.5%, SSA's COLA for the first year would
        #       be 0, and the COLA for the next year would be 1.0%.
        self.cola_proj = projection

        self.cola_dict.update(
            get_proj_dict(self.current_year + 1 - SSCOLA.mw_cola_offset,
                          self.current_year + SS_LIFESPAN - 1,
                          self.cola_proj, SSCOLA.ss_cola_default))

        # TBD: The following code "carries forward" any negative COLA in
        #   the COLA dictionary. Thus if cost-of-living decreases 0.5% in
        #   one year but then increases 1.5% in the next, the actual COLA
        #   applied for the first year will be 0.0% (because it can't be
        #   negative by statute), and the actual COLA for the second year will
        #   be 1.0% (actually 1.015/0.995, rounded to the nearest decimal
        #   of a percent). THIS HAS NOT BEEN TESTED! The only way for this
        #   code to even make sense is if we forecast a year with a
        #   cost-of-living decrease. But that could definitely happen. As of
        #   the time of this comment, all SSA projections for inflation are
        #   2.4% for each year after the next one (which still forecasts
        #   high inflation)
        basis_year = min(self.cola_dict.keys()) - 1
        basis_index = 1.0
        for year in self.cola_dict:
            # print(year, type(self.cola_dict), type(self.cola_dict[year]))
            assert self.cola_dict[year] >= 0.0
            if self.cola_dict[year] < 0.0:
                basis_index = basis_index * (1.0 + self.cola_dict[year])
                self.cola_dict[year] = 0.0
                # keep basis year
            elif basis_year < year - 1:
                # we have an old basis year, apply it
                basis_index = basis_index * (1.0 + self.cola_dict[year])
                if basis_index > 1.0:
                    self.cola_dict[year] = round(1.0 - basis_index, 3)
                    basis_year = year
                    basis_index = 1.0
                else:
                    self.cola_dict[year] = 0.0
            else:
                # normal case
                self.cola_dict[year] = round(self.cola_dict[year], 3)
                basis_year = year
                basis_index = 1.0

        # since COLA influences AWI calculations...
        awiobj = self.config.get_awiobj()
        if awiobj is not None:
            awiobj.set_wage_growth_projection()
            # only update the awi projection if it has already been done

    def ss_cola_adjust(self, base_value, base_year, benefit_year):
        """
        Applies COLA to a value (base_value) from the base year, each year
        through to the benefit year, and returns the benefit.

        This benefit is calculated year-by-year, each time rounding down to
        the nearest dime, and the benefit calculated and returned is also
        rounded down to the nearest dime.

        Parameters
        ----------
        base_value : float
            The value of the benefit in the base year. Note that this value
            should already be rounded down to the nearest dime, but this
            routine will do that rounding if it hasn't been.
        base_year : int
            The year for which the base benefit applies.
        benefit_year : int
            The year in which the COLA-applied benefit will be calculated.

        Returns
        -------
        value: float
            The benefit in the benefit year after COLA has been applied.
            Always rounded down to the nearest dime.

        """
        assert benefit_year >= base_year
        value = float(math.floor(base_value * 10.0)) / 10.0
        if value == 0.0:
            return 0.0
        for year in range(base_year, benefit_year):
            if year in self.cola_dict:
                cola = self.cola_dict[year]
            else:
                cola = SSCOLA.ss_cola_default
            value = value * (1.0 + cola)
            value = math.floor(value * 10.0) / 10.0
        return value

    def value_in_current_dollars(self, base_value, base_year):
        """
        This method adjusts a value (base_value) for inflation from the
        base year (base_year) to the current year, so that what is returned
        is the value in current dollars. This routine works if base_year is
        earlier or later than the current year. It becomes a no-op if
        base_year is the current year.

        Parameters
        ----------
        base_value : float
            The value in dollars in the base year.
        base_year : int
            The base year for which the value applies.

        Returns
        -------
        float
            The value in current dollars. This is not rounded off.

        """
        value = 1.0
        earlier_year = min(base_year, self.current_year)
        later_year = max(base_year, self.current_year)
        for year in range(earlier_year, later_year):
            if year in self.cola_dict:
                cola = self.cola_dict[year]
            else:
                cola = SSCOLA.ss_cola_default
            value = value * (1.0 + cola)
        if base_year < self.current_year:
            return base_value * value
        return base_value / value

    def get_cola_history(self):
        """
        Retrieves the COLA history

        Returns
        -------
        dict
            The COLA history.

        """
        return self.cola_dict
