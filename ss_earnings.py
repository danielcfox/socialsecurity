#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 10 02:11:23 2021

@author: dfox
"""

import math
import pandas as pd
from dateutil.relativedelta import relativedelta

SS_LIFESPAN = 130


class SSEarnings:
    """
    Class for handling Social Security Earnings based calculations.
    Note earnings/income/wages are terms used interchangibly to mean the
    same thing.

    This class maintains the worker's earnings history and projections.
    There is a distinction between "social security earnings" and
    "total earnings"
    "total earnings" is generally known as the AGI from the 1040 return
    "social security earnings" is known as the portion of the AGI that applies
    to social security.
    There are differences between the two, and the most obvious and significant
    one is that there is a maximum amount of earnings that can be taxed and
    applied to social security.

    The SSA keeps track of every worker's social security earnings for each
    year. They never show the AGI (total earnings), though the IRS has those
    records, and the worker might have kept them, too.

    This tool does not need to know the historical total earnings, just the
    social security earnings. However, if earnings data is supplied that is
    higher than the social security maximum earnings, it assumes what has
    been supplied is the total earnings and will reduce the historical
    amount to the maximum allowed.

    This tool also has the convenient feature that future earnings can be
    supplied as total earnings. In fact, total earnings should be used to
    provide a more accurate estimate of future benefits. This is because
    the worker's personal wage growth can be forecast independently from
    SSA's forecast AWI growth. SSA generally forecasts 3.6% AWI growth from
    year to yearm, but, really, many workers who are not promoted will not
    see wage increases that high. In many professionsm 3.0% is considered
    a good wage increase, which is much lower than 3.6%.

    An example would be a worker who currently earns more than the maximum,
    but their total earnings are eventually overtaken by the maximum earnings.

    Indeed, even though the SSA has wage growth projections of roughly 3.6%
    per year, the average annual increase over the last 20 years has been
    2.912%, which is the default this tool uses for worker wage growth.
    """

    personal_wage_growth_default = 0.02912  # cmp. ann. avg. last 20 yrs.

    start_max_income_age = 22
    # this is used for testing and is not user-configurable

    def __init__(self, ss_worker, income_history, **kwargs):
        """
        Constructor for the SSEarnings class.

        Parameters
        ----------
        ss_worker : SSWorker
            The SSEarnings class is instantiated when the SSWorker class is.
            This object is specified here.
        income_history : pandas Series or dict
            Specifies the earnings history of the worker. This can be either
            the total earnings (or AGI) or the earnings applied to social
            security (which has a maximum). Since any worker can go onto the
            ssa.gov website and retrieve their social security earnings
            history (TODO: an app that scrapes that data from the website),
            that is what is usually supplied here.

            If the income history overlaps with the future income, then a
            warning is issued and the history supplied will take precedence
            over the estimated future income. (TODO: Issue the warnings)

            For a pandas Series, the Year is the Index.
            For a dict, the Year is the hash.
        **kwargs : variable arguments
            'income_future': pandas Series or dict or 'use_max'
                             or None (default)
                Specifies the future income of the worker. This must be an
                estimate of the total income (AGI) of the worker, and not just
                the social security earnings, since the AGI can be higher and
                some calculations depend on it. However, since these are
                estimates anyway, using estimated social security earnings
                (like when you have a client who refuses to give the estimate
                 and all you have is that they are at the maximum earnings
                 level) is okay, so long as it is understood that the benefit
                calculated may be less than what the actual benefit would be.

                Of course, the converse is true as well. If the future income
                turns out to be overstated, then the benefit calculated could
                be higher than the actual benefit received.

                'use_max' means to assume the worker has always earned more
                than the social security maximums from age 22 through to the
                year prior to the current year (defined as the most recent
                year the social security earnings maximum is specified). This
                is generally used in a regression test to match with the SSA's
                published benefits for the maximum wage earner.

                If 'income_future' is None (the default), then the future
                earnings will be calculated using 'next_income_year',
                'next_income_amount', and 'personal_wage_growth'

                Once 'income_future' is specified, it overrides anything
                specified in 'next_income_year', 'next_income_amount', and
                'personal_wage_growth'

            'next_income_year': int or 'current_year'
                Specifies the next year of earnings after that supplied by
                'income_history'. Note that while there can be an income gap
                from the history to the next earnings year (which simply
                means there was no income during those years), if there is an
                overlap, the history takes precedence.

                'current_year' specifies to start at the current year. Keep in
                mind that history takes precedence over future estimates. It
                may be common to specify the current year's salary in the
                history and to also use that salary as the basis for future
                estimates. In that case, the history should be the same as the
                income specified in 'next_income_amount', and therefore
                precedence doesn't matter.

                If this keyword is specified, then earnings in subsequent years
                are estimated based upon the values specified in
                'next_income_amount', 'personal_wage_growth', and
                'final_income_year'.

                'next_income_amount' will be the estimated earnings for the
                year specified in 'next_income_year', and then subsequent
                years will be estimated by applying the growth rates specified
                for 'personal_wage_growth'. The income will stop in
                'final_income_year' or the year of retirement, whichever is
                earlier.

                This value cannot be specified if 'income_future' is specified
                and so therefore is ignored. (TODO: throw an exception)

            'next_income_amount': float or 'use_max' or 'extrapolate' (default)
                Specifies the worker's future income applied to the year
                specified by the 'next_income_year' keyword.

                'use_max' means to always apply the maximum social security
                earnings as the future earnings. Note that doing this may
                result in a calculated benefit slightly lower than the actual
                benefit, but if that happens it will not be much lower.

            final_income_year': int (defaults to the year the worker turns 130)
                Specifies the year that the worker will finish working if they
                don't retire (i.e. death). (TODO: do we really need this?)

            'personal_wage_growth': panda Series or dict or list or float
                (default is a float value of 0.02912, or 2.912%, which is
                the average AWI growth rate over the last 20 years).
                Specifies the annual growth rate used to calculate future
                earnings estimates. A float values applies the growth rate to
                all years. Otherwise, each year's growth rate is taken from
                the supplied data structure. If a year is missing in the data,
                then the most recent previous year's value will be used.

            'retire_age_years', 'retire_age_months': int, int
                Specifies the number of years and months at which the worker
                will retire.

        Returns
        -------
        None.

        """
        # The worker's history of social security earnings
        self.ss_earn_hist_dict = {}

        # The worker's projected future social security earnings, without
        # any retirement termination. This is re-calculated every time a
        # new earnings profile or growth projection is applied.
        self.ss_earn_future_dict = {}

        # The worker's historical and projected social security earnings,
        # without any retirement termination. This is re-calculated every time
        # a new earnings profile or growth projection is applied.
        self.ss_earn_all_dict = {}

        # The worker's historical and projected social security earnings,
        # terminated at retirement. This is re-calculated every time a new
        # earnings profile, growth projection, or retirement date is applied.
        self.ss_earn_to_retire_dict = {}

        # The worker's history of total earnings
        self.total_earn_hist_dict = {}

        # The worker's projected future total earnings, without
        # any retirement termination. This is re-calculated every time a
        # new earnings profile or growth projection is applied.
        self.total_earn_future_dict = {}

        # The worker's historical and projected total earnings,
        # without any retirement termination. This is re-calculated every time
        # a new earnings profile or growth projection is applied.
        self.total_earn_all_dict = {}
        # Note that historical total earnings may not be available, but
        # instead just the historical social security earnings. This is okay
        # because we only really need to know the difference during the year
        # of retirement, and for those already retired, we have the accurate
        # historical social security earnings. But in the year of future
        # retirement, we need that total earnings so that when we prorate the
        # earnings when retiring in the middle of the year, we don't prorate
        # the social security maximum but the actual total income.

        # The worker's historical and projected total earnings,
        # terminated at retirement. This is re-calculated every time a new
        # earnings profile, growth projection, or retirement date is applied.
        self.total_earn_to_retire_dict = {}

        # The projected personal wage growth for the worker. This is not the
        # same as the global AWI growth projections.
        self.pwg_dict = {}

        self.worker = ss_worker
        self.config = self.worker.get_config()
        self.birthday = self.worker.get_birthday()
        self.benefit_birthday = self.worker.get_calc_benefit_birthday()
        self.aime = 0.0  # worker's average indexed monthly earnings
        fra = ss_worker.get_fra()

        # we default the worker's retirement age to the full retirement age
        # which is dependent on the worker's birth year (Jan. 1 birthday
        # uses previous year)
        self.retire_age_years = fra[0]
        self.retire_age_months = fra[1]

        self.current_year = self.config.get_current_year()

        # Here we start to do some work. We have the data we need to
        # calculate the worker's earnings index factor for each year
        # The index factor profile is the same for each worker who share
        # the same birth year. (Again, Jan. 1 is treated as the previous year,
        # but this fact is abstracted inside SSWorker and theoretically a
        # new statute could change that without having this class know about
        # it at all. All this (SSEarnings) class knows about is the actual
        # birthday).
        self.index_factor = self.config.calc_income_index_factor(
            self.benefit_birthday.year)

        # Now we set the income/earnings profile for the worker
        # We load the earnings history, but we also calculate the future
        # earnings.
        #
        # There are two essential ways to set the future earnings for the
        # worker. We can set the current year's total earnings and apply a
        # growth rate/profile to it and calculate for all later years.
        # Or we can provide actual numbers for future years.
        # Finally, we can terminate that income at retirement.
        # We keep track/cache all the possible future earnings without regards
        # to retirement for optimization purposes.

        next_income_year = self.current_year
        next_income_amount = 'extrapolate'
        next_income_amount = 0.0
        income_future = None
        pwg = SSEarnings.personal_wage_growth_default

        for key, value in kwargs.items():
            if key == 'income_future':
                income_future = value
            if key == 'next_income_year':
                if value != 'current_year':
                    next_income_year = value
            elif key == 'next_income_amount':
                next_income_amount = value
            # elif key == 'final_income_year':
                # final_income_year = value
            elif key == 'personal_wage_growth':
                pwg = value
            elif key == 'retire_age_years':
                self.retire_age_years = value
            elif key == 'retire_age_months':
                self.retire_age_months = value

        # Here we apply the social security earnings history
        self._set_income_history(income_history)

        # Here we apply/calculate the future total income
        if income_future is not None:
            self._set_income_future_by_profile(income_future)
        else:
            #            print(next_income_year)
            self._set_income_future_by_next(next_income_year,
                                            next_income_amount,
                                            pwg,
                                            (self.benefit_birthday.year +
                                             SS_LIFESPAN))

        # Now that we know the history and future earnings, we combine them
        self._set_earn_all()

        # Here we cap off the future earnings at retirement
        self._set_retirement()

        # Now we can calculate the AIME, or annual indexed monthly earnings,
        # which is the work of this class
        self._calc_aime()

    def reset_retirement_age(self, retire_age_years, retire_age_months):
        """
        Resets the retirement age and re-calculates AIME for the worker.
        More efficient than instantiating a new earnings class object.
        Useful for examining how the benefit changes with retirement age.

        Parameters
        ----------
        retire_age_years, retire_age_months : int, int
            Age in years and months at which the worker decides to retire.

        Returns
        -------
        None.

        Side Effects
        ------------
        Re-calcuates AIME

        """
        self.retire_age_years = retire_age_years
        self.retire_age_months = retire_age_months

        self._set_retirement()
        self._calc_aime()

    def reset_income_future_by_profile(self, income_future):
        """
        Resets the estimated future income profile of the worker.
        More efficient than instantiating a new earnings class object.
        Useful for examining how the benefit changes with future income.

        Parameters
        ----------
        income_future : pandas Series or dict or list
            See 'income_future' keyword in constructor for details.

        Returns
        -------
        None.

        Side Effects
        ------------
        Re-calcuates AIME

        """
        self._set_income_future_by_profile(income_future)
        self._set_earn_all()
        self._set_retirement()
        self._calc_aime()

    def reset_income_future_by_next(self, next_income_year, next_income_amount,
                                    pwg, final_income_year):
        """
        Resets the estimated future income of the worker.
        More efficient than instantiating a new earnings class object.
        Useful for examining how the benefit changes with future income.

        Parameters
        ----------
        next_income_year : int
            see 'next_income_year' keyword in constructor for details
        next_income_amount : float or 'use_max' or 'extrapolate' (default)
            see 'next_income_amount' keyword in constructor for details
        pwg : panda Series or dict or list or float
              (default is a float value of 0.02912, or 2.912%, which is
              the average AWI growth rate over the last 20 years).
            see 'personal_wage_growth' keyword in constructor for details
        final_income_year : int
            see 'final_income_year' keyword in constructor for details

        Returns
        -------
        None.

        Side Effects
        ------------
        Re-calcuates AIME

        """
        self._set_income_future_by_next(next_income_year, next_income_amount,
                                        pwg, final_income_year)
        self._set_earn_all()
        self._set_retirement()
        self._calc_aime()

    def get_aime(self):
        """
        Retrieves the calculated AIME (average indexed monthly earnings) for
        the worker. This is calculated during instantiation of this class, so
        it is always valid.

        Returns
        -------
        int
            The AIME, which is a whole number (of dollars).

        """
        return self.aime

    def get_total_earn_in_year(self, year):
        """
        Retrieves the total income earned by the worker in a particular year.
        This can of course be used for any purpose, but this number is
        explicitly used to reduce the benefits for the worker who earnes
        income while collecting social security before full retirement age.
        That feature, though, is NOT IMPLEMENTED yet.

        Parameters
        ----------
        year : int
            The year to retrieve the income for.

        Returns
        -------
        float
            The income during the specified year.

        """
        if year in self.total_earn_to_retire_dict:
            return self.total_earn_to_retire_dict[year]
        return 0.0

    def _set_ss_income_future(self):
        """
        Internal routine sets the social security earnings to the maximum
        amount if the total earnings are higher.

        Returns
        -------
        None.

        """
        for year in self.total_earn_future_dict:
            max_wage = self.config.get_max_ss_wage(year)
            self.ss_earn_future_dict[year] = \
                min(self.total_earn_future_dict[year], max_wage)
#            if self.total_earn_future_dict[year] > max_wage:
#                print("knocked down ss_earn_future ({}) to max wage ({})"
#                      .format(self.total_earn_future_dict[year], max_wage))
#                print("for year {}".format(year))

    def _set_income_history(self, income_history):
        """
        Internal routine sets local variables to hold the worker's income
        history.

        Parameters
        ----------
        income_history : pandas Series or dict
            Specifies the earnings history of the worker. See the
            income_history argument in the constructor for details

            For a pandas Series, the Year is the Index.
            For a dict, the Year is the hash.


        Returns
        -------
        None.

        """
        if isinstance(income_history, pd.Series):
            self.total_earn_hist_dict = income_history.dropna().to_dict()
        elif isinstance(income_history, dict):
            self.total_earn_hist_dict = income_history.copy()
        elif isinstance(income_history, list):
            # must be indexed from 0 (birth year), end in current year - 1
            # note that this is the actual birth year not the SSA birth year
            # So if you were born 1/1/1960, the birth year is 1960
            self.total_earn_hist_dict = {}
            for index, income in enumerate(income_history):
                self.total_earn_hist_dict[index + self.birthday.year] = income
        elif income_history == "use_max":
            # income_history None should only be used for testing purposes
            # throw an exception here when not testing
            self.total_earn_hist_dict = {}
            for year in range(
                    self.birthday.year + SSEarnings.start_max_income_age,
                    self.current_year):
                self.total_earn_hist_dict[year] = \
                    self.config.get_max_ss_wage(year)
        else:
            self.total_earn_hist_dict = {}

        for year in range(self.birthday.year, self.current_year):
            if year not in self.total_earn_hist_dict:
                self.ss_earn_hist_dict[year] = 0.0
            else:
                # in case items in the income history provided are higher
                # than the maximum wage limit
                max_wage = self.config.get_max_ss_wage(year)
                self.ss_earn_hist_dict[year] = \
                    min(self.total_earn_hist_dict[year], max_wage)
#                if self.total_earn_hist_dict[year] > max_wage:
#                    print("knocked down ss_earn_hist ({}) to max wage ({})"
#                          .format(self.total_earn_hist_dict[year], max_wage))
#                    print("for year {}".format(year))

    def _set_income_future_by_profile(self, income_future):
        """
        Internal routine to calculate and set the local variables that
        hold the worker's estimated future earnings

        Parameters
        ----------
        income_future : pandas Series or dict or list or 'use_max' or None
            (default)
            See keyword 'income_future' in the constructor for details.

        Returns
        -------
        None.

        """
        if isinstance(income_future, pd.Series):
            self.total_earn_future_dict = income_future.dropna().to_dict()
        elif isinstance(income_future, dict):
            self.total_earn_future_dict = income_future.copy()
        elif isinstance(income_future, list):
            # must be indexed from 0 (current year)
            self.total_earn_future_dict = {}
            for index, income in enumerate(income_future):
                self.total_earn_future_dict[index + self.current_year] = \
                    income
        elif income_future == "use_max":
            # income_history None should only be used for testing purposes
            # throw an exception here when not testing
            self.total_earn_future_dict = {}
            for year in range(
                    self.birthday.year + SSEarnings.start_max_income_age,
                    self.current_year()):
                self.total_earn_future_dict[year] = \
                    self.config.get_max_ss_wage(year)
        else:
            self.total_earn_future_dict = {}

        final_income_year = self.current_year + SS_LIFESPAN
        for year in range(self.current_year, final_income_year+1):
            if year not in self.total_earn_future_dict:
                self.total_earn_future_dict[year] = 0.0

        self._set_ss_income_future()

    def _set_income_future_by_next(self, next_income_year, next_income_amount,
                                   pwg, final_income_year):
        """
        Internal routine to calculate and set the local variables that
        hold the worker's estimated future earnings

        Parameters
        ----------
        next_income_year : int
            See keyword 'next_income_year' in constructor for details.
        next_income_amount : float or 'use_max' or 'extrapolate'
            See keyword 'next_income_amount' in constructor for details.
        pwg : pandas Series, dict, list, or float
            See keyword 'personal_wage_growth' in constructor for details.
        final_income_year : int
            See keyword 'final_income_year' in constructor for details.

        Returns
        -------
        None.

        """
        self._set_personal_wage_growth(pwg)
        if next_income_year is not None:
            if next_income_amount == 'extrapolate':
                #                print(next_income_year)
                prev_year = next_income_year - 1
                if prev_year in self.total_earn_hist_dict:
                    next_income = (self.total_earn_hist_dict[prev_year]
                                   * (1 + self.pwg_dict[next_income_year]))
                else:
                    next_income = 0.0
            elif next_income_amount == 'use_max':
                next_income = self.config.get_max_ss_wage(next_income_year)
            else:
                next_income = next_income_amount
            self.total_earn_future_dict[next_income_year] = next_income
            for year in range(next_income_year+1, final_income_year+1):
                if next_income_amount == 'use_max':
                    next_income = self.config.get_max_ss_wage(year)
                else:
                    prev_year = year - 1
                    if prev_year in self.total_earn_future_dict:
                        next_income = (self.total_earn_future_dict[prev_year]
                                       * (1 + self.pwg_dict[year]))
                    else:
                        next_income = 0.0
                self.total_earn_future_dict[year] = next_income

        for year in range(self.current_year, final_income_year+1):
            if year not in self.total_earn_future_dict:
                self.total_earn_future_dict[year] = 0.0

        self._set_ss_income_future()

    def _set_earn_all(self):
        """
        Internal routine that combines historical and future earnings into
        consolidated dictionaries for ease of lookup

        Returns
        -------
        None.

        """
        # if there is overlap, history takes precedence
        # should probably issue a warning or just assert if there's a conflict
        for year in self.ss_earn_future_dict:
            self.ss_earn_all_dict[year] = self.ss_earn_future_dict[year]
        for year in self.ss_earn_hist_dict:
            self.ss_earn_all_dict[year] = self.ss_earn_hist_dict[year]

        # if there is overlap, history takes precedence
        # should probably issue a warning or just assert if there's a conflict
        for year in self.total_earn_future_dict:
            self.total_earn_all_dict[year] = self.total_earn_future_dict[year]
        for year in self.ss_earn_hist_dict:
            self.total_earn_all_dict[year] = self.ss_earn_hist_dict[year]

    def _set_personal_wage_growth(self, pwg):
        """
        Internal routine that sets the pwg_dict based on the passed in
        personal wage growth

        Parameters
        ----------
        pwg : pandas Series, dict, list, or float
            See keyword 'personal_wage_growth' in constructor for details.

        Returns
        -------
        None.

        Side effects
        ------------
        Sets the pwg_dict object variable

        """
        end_lifespan = self.birthday.year + SS_LIFESPAN
        if isinstance(pwg, pd.Series):
            self.pwg_dict = pwg.dropna().to_dict()
        elif isinstance(pwg, dict):
            self.pwg_dict = pwg.copy()
        elif isinstance(pwg, list):
            # must be indexed from 0 (current year),
            # end in birthday.year + ss_lifespan - 1
            self.ss_earn_hist_dict = {}
            for index, income in enumerate(pwg):
                self.pwg_dict[index + self.current_year] = income
        else:
            self.pwg_dict = {}
            for year in range(self.birthday.year, end_lifespan+1):
                self.pwg_dict[year] = pwg
        for year in range(self.birthday.year, end_lifespan+1):
            if year not in self.pwg_dict:
                self.pwg_dict[year] = 0.0

    def _set_retirement(self):
        """
        Internal routine to set the dictionary for the income up to retirement
        age.

        For income during your retirement year, we assume that you will stop
        earning money on the month prior to your retirement date

        Returns
        -------
        None.

        Side Effects
        ------------
        Sets total_earn_to_retire_dict and ss_earn_to_retire_dict

        """

        self.total_earn_to_retire_dict = self.total_earn_all_dict.copy()
        self.ss_earn_to_retire_dict = self.ss_earn_all_dict.copy()
        retire_start_date = (self.benefit_birthday
                             + relativedelta(years=self.retire_age_years,
                                             months=self.retire_age_months,
                                             day=1))
        retire_year = retire_start_date.year
        retire_month = retire_start_date.month
        final_income_year = self.birthday.year + SS_LIFESPAN
        for year in range(retire_year, final_income_year+1):
            if year in self.total_earn_to_retire_dict:
                assert year in self.ss_earn_to_retire_dict
                if year == retire_year:
                    partial_income = float(math.floor(
                        (self.total_earn_all_dict[year]
                         * (retire_month - 1) / 12.0)))
                    self.total_earn_to_retire_dict[year] = partial_income
                    self.ss_earn_to_retire_dict[year] = \
                        min(self.ss_earn_to_retire_dict[year], partial_income)
                else:
                    self.total_earn_to_retire_dict[year] = 0.0
                    self.ss_earn_to_retire_dict[year] = 0.0
            else:
                self.total_earn_to_retire_dict[year] = 0.0
                self.ss_earn_to_retire_dict[year] = 0.0

#        print(self.ss_earn_to_retire_dict)

    def _calc_aime(self):
        """
        Internal routine to calculate the AIME (average indexed monthly
        earnings). This is the culmination of the purpose of this class.
        This is called upon instantiation of the worker object and whenever
        any worker's variables are subsequently changed.

        Returns
        -------
        None.

        Side Effects
        ------------
        Calculates AIME for the worker.

        """
        # compute the income normalized to wage inflation (AWI)
        indexed_income = {}
        for year, income in self.ss_earn_to_retire_dict.items():
            if year in self.index_factor:
                indexed_income[year] = income * self.index_factor[year]
            else:
                indexed_income[year] = 0.0

        # make a list out of the income for each year and sort it to reach
        # the maximum income for the number of years based on birth year
        # for everyone born after 1950, the number of years is 35
        # otherwise it is birth year - 1894
        # Note that this income list is re-generated every year, even after
        # benefits have already started to have been received
        # This means that if a worker continues to earn income, the benefit
        # will increase as long as their income keeps going up
        # However, this increase may not be very much if the 35th-highest
        # income year (indexed to wage inflation) is close to the new earnings
        indexed_income_list = indexed_income.values()
        max_years = self.worker.get_max_inc_years()
        sorted_indexed_income = \
            sorted(indexed_income_list, reverse=True)[:max_years]

        # compute the monthly average income, rounded down to the whole dollar
        self.aime = math.floor(
            sum(sorted_indexed_income) / max_years / 12.0)
