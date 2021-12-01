#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 24 05:19:01 2021

@author: dfox
"""

import os
import pandas as pd
import ss_cola as ssc
import ss_awi as ssa


def _validate_historical_data(hdf):
    rows, _ = hdf.shape
    assert rows > 0

    current_year = hdf.index.max()
    # the current year is the last year in the global data file

    # Max_Wages must end with current year
    # COLA must end with current year - 1
    # AWI must end with current_year - 2

    assert not pd.isnull(hdf.at[current_year, 'Max_Wages'])
    cola_max_year = current_year - ssc.SSCOLA.mw_cola_offset
    assert not pd.isnull(hdf.at[cola_max_year, 'COLA'])
    awi_max_year = current_year - ssa.SSAWI.mw_awi_offset
    assert not pd.isnull(hdf.at[awi_max_year, 'AWI'])

    # there should not be any value for the COLA or AWI for the current
    # year nor AWI for the year before that
    # the math on this looks weird, but it's based on the offset
    null_cola_years = [year for year in hdf.index
                       if year >= (current_year + 1
                                   - ssc.SSCOLA.mw_cola_offset)]
    null_awi_years = [year for year in hdf.index
                      if year >= (current_year + 1 - ssa.SSAWI.mw_awi_offset)]
    for year in null_cola_years:
        assert pd.isnull(hdf.at[year, 'COLA'])
    for year in null_awi_years:
        assert pd.isnull(hdf.at[year, 'AWI'])


class SSConfig:
    """
    Class for containing and managing the global (non-worker) configuration of
    the social security module. Singleton.
    """

    global_history_data_file = os.path.join(".", "SS_global_history.csv")
    global_projections_data_file = \
        os.path.join(".", "SS_global_projections.csv")

    def __init__(self, **kwargs):
        """
        Constructor for the SSConfig class.

        Parameters
        ----------
        **kwargs : variable arguments
            'cola_proj': pandas Series or dict or list or float
                Specifies the COLA projections, overrides the data in
                infl_proj_file.
                See 'cola_proj' keyword in SSCOLA constructor (in ss_cola.py)
                for details.
            'ss_wage_growth': pandas Series or dict or list or float
                overrides data in infl_proj_file
                See the projection parameter in
                SSAWI.set_wage_growth_projection (in ss_awi.py)
            'historical_data_file': str
                Overrides the value in SSConfig.global_history_data_file
            'infl_proj_file': str
                Overrides the value in SSConfig.global_projections_data_file

        Returns
        -------
        None.

        """

        # begin defaults

        hist_data_file = SSConfig.global_history_data_file
        infl_proj_file = SSConfig.global_projections_data_file
        cola_proj_val = None
        sswg_proj_val = None

        # TBD: test COLA passed in as float, series, dict, or list
        # TBD: test Soc Sec wage growth passed as float, series, dict, or list
        for key, value in kwargs.items():
            if key == 'cola_proj':
                # overrides data in infl_proj_file
                cola_proj_val = value
            if key == 'ss_wage_growth':
                # overrides data in infl_proj_file
                sswg_proj_val = value
            if key == 'historical_data_file':
                assert isinstance(value, str)
                hist_data_file = value
            if key == 'infl_proj_file':
                # overridden if both cola_proj and ss_wage_growth are set
                assert isinstance(value, str)
                infl_proj_file = value

        if ".xlsx" in hist_data_file:
            # TBD: test excel
            hdf = pd.read_excel(hist_data_file)
        else:
            hdf = pd.read_csv(hist_data_file)

        hdf = hdf.set_index('Year')
        self.current_year = hdf.index.max()
        # the current year is the last year in the global data file

        _validate_historical_data(hdf)

        if cola_proj_val is None or sswg_proj_val is None:
            if ".xlsx" in infl_proj_file:
                # TBD: test excel
                idf = pd.read_excel(infl_proj_file)
            else:
                idf = pd.read_csv(infl_proj_file)
            idf = idf.set_index('Year')

        if cola_proj_val is None:
            cola_proj_val = idf['COLA'].dropna()

        if sswg_proj_val is None:
            sswg_proj_val = idf['AWI_Increase'].dropna()

        self.awi = None
        # initialize self.awi to None so that when we run cola constructor
        # for the first time, it doesn't update the awi projection

        self.cola = ssc.SSCOLA(self, hdf['COLA'].dropna(), cola_proj_val)

        self.awi = ssa.SSAWI(self, hdf['AWI'].dropna(),
                             hdf['Max_Wages'].dropna(), sswg_proj_val)
        # self._set_wage_growth_projection(sswg_proj_val)
        # Above will populate self.cola.get_cola_history() with the COLA for
        # each future year
        # Note that self.cola.get_cola_history() will still contain the
        # historical COLA
        # This will populate self.awi_dict with the AWI for each future year
        # Note that self.awi_dict will still contain the historical AWI
        # It will also calculate the maximum wage for each future year
        #
        # This routine may be called externally to change the projections

    def get_current_year(self):
        """
        Retrieves the current year, which is defined as the latest year
        in the SSConfig.global_history_data_file that specifies the
        maximum social security earnings.

        Returns
        -------
        int
            The current year

        """
        return self.current_year

    def get_awiobj(self):
        """
        Retrieves the AWI object. Used by ss_cola.py. AWI object cannot be
        passed to COLA upon instantiation because COLA needs to be
        instantiated first, as calculations based on AWI are dependent upon
        COLA.

        Returns
        -------
        SSAWI object singleton.

        """
        return self.awi

    def get_max_ss_wage(self, year):
        """
        See SSAWI.get_max_ss_wage in ss_awi.py for more details
        """
        return self.awi.get_max_ss_wage(year)

    def get_awi_value(self, year):
        """
        See SSAWI.get_awi_value in ss_awi.py for more details
        """
        return self.awi.get_awi_value(year)

    def calc_income_index_factor(self, birth_year):
        """
        See SSAWI.calc_income_index_factor in ss_awi.py for more details
        """
        return self.awi.calc_income_index_factor(birth_year)

    def calc_base_benefit(self, birth_year, aime):
        """
        See SSAWI.calc_base_benefit in ss_awi.py for more details
        """
        return self.awi.calc_base_benefit(birth_year, aime)

    def ss_cola_adjust(self, base_value, base_year, benefit_year):
        """
        See SSCOLA.ss_cola_adjust in ss_cola.py for more details
        """
        return self.cola.ss_cola_adjust(base_value, base_year, benefit_year)

    def get_cola_history(self):
        """
        See SSCOLA.get_cola_history in ss_cola.py for more details
        """
        return self.cola.get_cola_history()

    def value_in_current_dollars(self, base_value, base_year):
        """
        See SSCOLA.value_in_current_dollars in ss_cola.py for more details
        """
        return self.cola.value_in_current_dollars(base_value, base_year)
