# -*- coding: utf-8 -*-
"""
Created on Fri Sep 10 02:11:23 2021

@author: dfox
"""

import datetime as dt
import math
from dateutil.relativedelta import relativedelta
import ss_earnings as sse

SS_BENEFIT_AGE = 62


def _sub_tuple(lhs, rhs, base):
    """
    Subtracts two tuples
    The second number of the tuple is in base <base> (i.e. mod base)
    The first number of the tuple can be arbitrarily large as any int

    Parameters
    ----------
    lhs : tuple: (int, int)
        left-hand-side of add operator
        first value is the higher order of magnitude
    rhs : tuple: (int, int)
        right-hand-side of add operator
        first value is the higher order of magnitude
    base : int
        The number base for the second number.

    Returns
    -------
    tuple: (int, int)
        The difference of the two tuples

    """
    if lhs[1] < rhs[1]:
        return lhs[0] - 1 - rhs[0], lhs[1] + base - rhs[1]

    return lhs[0] - rhs[0], lhs[1] - rhs[1]


def _sub_years_months(lhs, rhs):
    """
    Subtracts time period values expressed as a tuple of (years, months)

    Parameters
    ----------
    lhs : tuple: (int, int)
        left-hand-side of the subtract operator
        expressed as (years, months)
        must be a duration of time, NOT A DATE
    rhs : tuple: (int, int)
        right-hand-side of the subtract operator
        expressed as (years, months)
        must be a duration of time, NOT A DATE

    Returns
    -------
    tuple: (int, int)
        The difference between the two time period values
        expressed as a duration of (years, months)

    """

    # TBD: test when months subtracts to a negative number
    return _sub_tuple(lhs, rhs, 12)


class SSWorker:
    """
    Class for managing and handling a social security worker. Each worker
    instantiates an object of this class.
    """

    personal_wage_growth_default = 0.02912  # cmp. ann. avg. last 20 yrs.

    start_max_income_age = 22
    # this is used for testing and is not user-configurable

    def __init__(self, ss_config, name, birthday, income_history, **kwargs):
        """

        Parameters
        ----------
        ss_config : SSConfig
            The SSConfig object is a singleton that is instantiated prior
            to the SSWorker class instantiation for each worker and is a
            required parameter
        name : str
            The name of the worker.
        birthday : datetime.date
            The worker's actual birthday, and not the ones used for social
            security purposes.
            The "birthday" used for the calculation of benefits is a day
            earlier than the actual birthday.
            The "birthday" used to determine benefit eligibility is two days
            earlier than the actual birthday.
        income_history : pandas Series or dict
            The earnings history of the worker. See the income_history
            parameter in SSEarnings.__init__ in ss_earnings.py

        Returns
        -------
        None.

        Side Effects
        ------------
        Initializes everything and calculates the monthly base benefit based
        on the parameters provided

        """
        # begin defaults

        self.config = ss_config
        self.name = name
        self.birthday = birthday

        # birth date for benefit purposes goes back one day
        self.calc_benefit_birthday = birthday - dt.timedelta(days=1)
#        self.eligibility_birthday = birthday - dt.timedelta(days=2)

        """
        # default collection start Jan after reach FRA
        # note that when you can start collectionn is dependent on your
        # benefit birthday (-2 days)
        # However (see below), the first benefit year is dependent on your
        # birthday used for benefit calculation purposes (-1 days)
        fra = self.get_fra()
        self.collection_start_age = ((self.eligibility_birthday.year
                                      - self.calc_benefit_birthday.year
                                      + fra[0]),
                                     12 - self.calc_benefit_birthday.month)
        """
        self.collection_start_age = self.get_fra()

        for key, value in kwargs.items():
            if key == 'collection_start_age':
                self.collection_start_age = value

        self.benefit_multiplier = self.get_benefit_multiplier(
            self.collection_start_age[0], self.collection_start_age[1])

        # first benefit year, based on calc_benefit_birthday NOT
        # eligibility_birthday
        # by default, we calculate the benefit for the first eligible year
#       self.first_benefit_year = (self.calc_benefit_birthday.year
#                                  + self.collection_start_age[0] + 1)

        self.earnings = sse.SSEarnings(self, income_history, **kwargs)

        self._calc_mo_base_benefit()
        self.mo_benefit_cola = {}
        self.mo_benefit = {}
#        self._calc_mo_benefit(self.first_benefit_year)

    def get_max_inc_years(self):
        """
        Returns the number of years of maximum income to normalize wages on

        Returns
        -------
        int
            The maximum number of years.

        """
        return min(35, self.calc_benefit_birthday.year - 1894)

    def get_birthday(self):
        """
        Returns the worker's birthday

        Returns
        -------
        datetime.date
            Worker's birthday.

        """
        return self.birthday

    def get_calc_benefit_birthday(self):
        """
        Return's the worker's birthday for SSA calculation purposes
        SSA moves the birthday a day back

        Returns
        -------
        datetime.date
            Worker's Social Security Birthday.

        """
        return self.calc_benefit_birthday

    def get_config(self):
        """
        Returns the configuration object singleton

        Returns
        -------
        SSConfig
            The configuration object singleton.

        """
        return self.config

    def get_fra(self):
        """
        Calculates Social Security Full Retirement Age (FRA) for an individual
        based on their year of birth

        Parameters
        ----------
        None

        Returns
        -------
        tuple: (int, int)
            Social Security Full Retirement Age (FRA): (years, months)

        """
        birth_year = self.calc_benefit_birthday.year
        if birth_year <= 1937:
            return 65, 0
        if birth_year < 1943:
            return 65, 2*(birth_year - 1937)
        if birth_year <= 1954:
            return 66, 0
        if birth_year < 1960:
            return 66, 2*(birth_year - 1954)
        return 67, 0

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
        return self.earnings.get_aime()

    def reset_retirement_age(self, retire_age_years, retire_age_months):
        """
        Resets the retirement age without needing to re-instantiate this
        class. This makes studying the effects of retirement on benefits more
        efficient.

        Parameters
        ----------
        retire_age_years, retire_age_months : int, int
            Retirement age in years, months.

        Returns
        -------
        None.

        Side Effects
        ------------
        Re-calculates the monthly base benefit

        """
        self.mo_benefit_cola = {}
        self.mo_benefit = {}
        self.earnings.reset_retirement_age(retire_age_years, retire_age_months)
        self._calc_mo_base_benefit()
#        self._calc_mo_benefit(self.first_benefit_year)

    def reset_income_future_by_profile(self, income_future):
        """
        Resets the worker's future income profile without needing to
        re-instantiate this class. This makes studying the effects of changing
        future income on benefits more efficient.

        Parameters
        ----------
        income_future : pandas Series or dict or list
            See 'income_future' keyword in SSEarnings constructor in
            ss_earnings.py for details.

        Returns
        -------
        None.


        Side Effects
        ------------
        Re-calculates the monthly base benefit
        """
        self.mo_benefit_cola = {}
        self.mo_benefit = {}
        self.earnings.reset_income_future_by_profile(income_future)
        self._calc_mo_base_benefit()
#        self._calc_mo_benefit(self.first_benefit_year)

    def reset_income_future_by_next(self, next_income_year, next_income_amount,
                                    pwg, final_income_year):
        """
        Resets the worker's future estimated income without needing to
        re-instantiate this class. This makes studying the effects of changing
        future income on benefits more efficient.

        Parameters
        ----------
        next_income_year : int
            see 'next_income_year' keyword in SSEarnings constructor in
            ss_earnings.py for details
        next_income_amount : float or 'use_max' or 'extrapolate' (default)
            see 'next_income_amount' keyword in SSEarnings constructor in
            ss_earnings.py for details
        pwg : panda Series or dict or list or float
              (default is a float value of 0.02912, or 2.912%, which is
              the average AWI growth rate over the last 20 years).
            see 'personal_wage_growth' keyword in SSEarnings constructor in
            ss_earnings.py for details
        final_income_year : int
            see 'final_income_year' keyword in SSEarnings constructor in
            ss_earnings.py for details

        Returns
        -------
        None.


        Side Effects
        ------------
        Re-calculates the monthly base benefit
       """
        self.mo_benefit_cola = {}
        self.mo_benefit = {}
        self.earnings.reset_income_future_by_next(next_income_year,
                                                  next_income_amount,
                                                  pwg,
                                                  final_income_year)
        self._calc_mo_base_benefit()
#        self._calc_mo_benefit(self.first_benefit_year)

    def reset_collection_start_age(self, collection_start_age_years,
                                   collection_start_age_months):
        """
        Resets the age the worker starts to receive benefits without needing to
        re-instantiate this class. This makes studying the effects of changing
        the age of collection start more efficient.

        Parameters
        ----------
        collection_start_age_years, collection_start_age_months : int, int
            The age in years, months that the worker will being to receive
            benefits.

        Returns
        -------
        None.


        Side Effects
        ------------
        Re-calculates the monthly base benefit
        """
        self.mo_benefit_cola = {}
        self.mo_benefit = {}
        self.collection_start_age = (collection_start_age_years,
                                     collection_start_age_months)
#        print(self.collection_start_age)
        self.benefit_multiplier = self.get_benefit_multiplier(
            self.collection_start_age[0], self.collection_start_age[1])
#        print(self.benefit_multiplier)
#        self.first_benefit_year = (self.calc_benefit_birthday.year
#                                   + self.collection_start_age[0] + 1)
        self._calc_mo_base_benefit()
#        self._calc_mo_benefit(self.first_benefit_year)

    def _calc_benefit_cola(self, benefit_year):
        if len(self.mo_benefit_cola):
            last_year_calc = max(self.mo_benefit_cola.keys())
        else:
            last_year_calc = self.calc_benefit_birthday.year + SS_BENEFIT_AGE
            self.mo_benefit_cola[last_year_calc] = self.base_benefit

        if last_year_calc < benefit_year:
            for year in range(last_year_calc+1, benefit_year+1):
                self.mo_benefit_cola[year] = self.config.ss_cola_adjust(
                    self.mo_benefit_cola[year-1], year-1, year)

    def get_benefit_multiplier(self, ben_start_years, ben_start_months):
        """
        Calculates the benefit multiplier based on the age the worker chooses
        to begin to receive benefits

        As an example, for those born on or after 1960:
            at age 62: 0.70
            at age 62, 1 months: 0.704167
            at age 64: 0.80
            at age 67: 1.00 (This is full retirement age (FRA))
            at age 70: 1.24

            These numbers change at the granularity of a month.

        Parameters
        ----------
        ben_start_years, ben_start_months : int, int
            Age in years, months the worker begins to collect benefits.

        Returns
        -------
        float
            The multiplier.

        """
        # TBD add a regression test that uses the entire range of birth
        # years and start age

        start_age = (ben_start_years, ben_start_months)

        if start_age >= (70, 0):
            start_age = (70, 0)

        # kinda crazy, but if your birthday for calculation purposes in on the
        # 1st of the month (which is the 2nd of the month of your actual
        # birthday, BTW), then you can't retire at 62, 0, you must wait until
        # 62, 1. That's right, *only* people born on the 2nd of a month can
        # retire at 62 years, 0 months. The rest must wait until 62 years,
        # 1 month
        if start_age < (62, 0):
            return 0.0
        if self.calc_benefit_birthday.day != 1 and start_age == (62, 0):
            return 0.0

        birth_year = self.calc_benefit_birthday.year
        fra = self.get_fra()

        base_mult_dict = {
            1924: 0.030, 1925: 0.035, 1926: 0.035, 1927: 0.040, 1928: 0.040,
            1929: 0.045, 1930: 0.045, 1931: 0.050, 1932: 0.050,
            1933: 0.055, 1934: 0.055, 1935: 0.060, 1936: 0.060,
            1937: 0.065, 1938: 0.065, 1939: 0.070, 1940: 0.070,
            1941: 0.075, 1942: 0.075, 1943: 0.080
            }

        if birth_year in base_mult_dict:
            base_mult = base_mult_dict[birth_year]
        elif birth_year < min(base_mult_dict.keys()):
            base_mult = base_mult_dict[min(base_mult_dict.keys())]
        else:
            base_mult = base_mult_dict[max(base_mult_dict.keys())]

        above_fra = _sub_years_months(start_age, fra)
        if above_fra >= (0, 0):
            #    if above_fra[0] >= 0 and above_fra[1] >= 0:
            return (1.0 + (base_mult * above_fra[0])
                    + (base_mult * above_fra[1])/12)

        bp1 = _sub_years_months(fra, (3, 0))
        above_bp1 = _sub_years_months(start_age, bp1)
        if above_bp1 >= (0, 0):
            return 0.8 + 0.2*above_bp1[0]/3 + 0.2*above_bp1[1]/36

        below_bp1 = _sub_years_months(bp1, start_age)
        return 0.8 - 0.05*below_bp1[0] - 0.05*below_bp1[1]/12

    def _calc_mo_base_benefit(self):
        """
        Internal method for calculating the base benefit.
        The SSConfig method is a wrapper for the SSAWI method.
        See SSAWI.calc_base_benefit in ss_awi.py for more details
        """
        self.base_benefit, self.bp1, self.bp2 = self.config.calc_base_benefit(
            self.calc_benefit_birthday.year,
            self.earnings.get_aime())

    def get_mo_benefit(self, benefit_date=None):
        """
        Retrieves the monthly benefit for the worker on a specific benefit
        date. The value is calculated if it is not already cached.

        Parameters
        ----------
        benefit_date : tuple: (year, month), optional
            (Year, Month) for which the monthly benefit will be retrieved.
            The default is None. If None, then the benefit date is assumed to
            be the first month of collection, based on the worker's collection
            start age

        Returns
        -------
        int
            The monthly benefit in whole dollars

        """
#        print(benefit_date)

        # First we apply an obscure law, and it only applies if you are age
        # 62. You are only first eligible for benefits in the month you are
        # first 62 for every day in the month. Since SSA treats your birthday
        # as one day earlier, this means that if you were born on the 1st
        # or 2nd, you are first eligible in the month that you turn 62.
        # However, if you were born on the 3rd onward, you are first eligible
        # for the next month.
        #
        # Now here's where it really gets weird. If your birthday is the 1st
        # and therefore your SSA birthday is in the previous month, then
        # your first eligible month is the month of your actual birthday
        # which is actually age 62, 1 month. If your birthday is the 2nd
        # and therefore your SSA birthday is on the 1st, then your first
        # eligible month is still the month of your actual birthday, but that
        # is now age 62, 0 months! If your birthday is from the 3rd onward,
        # then your first eligible month is the month after your actual
        # birthday, which is actually age 62, 1 month. Thus, you cannot start
        # to collect benefits until you are age 62 and 1 month UNLESS your
        # birthday is on the 2nd, in which case you can start to collect
        # benefits at age 62 years, 0 months.

        if (self.collection_start_age[0] == SS_BENEFIT_AGE
                and self.collection_start_age[1] == 0
                and self.calc_benefit_birthday != 1):
            # Tecnically, we are checking if the worker was age 62 for every
            # day of the month, given that their SSA age is one day prior
            # (which is what self.calc_benefit_birthday is). IF for some
            # reason the way the SSA determines the birthday will change
            # in the future, in the constructor self.calc_benefit_birthday
            # would be calculated differently, and this code will not need
            # to be changed
            #            print("returning not eligible")
            # ineligible year, month, do not put in cache
            # we would have to have the cache be by month, too, and
            # this is a lot of complexity for little benefit
            return 0.0

        # To clarify:
            # benefit_start_date is the day the worker chose to start
            #   receiving benefits
            # benefit_date is the day we are calculating the benefit for

        benefit_start_date = \
            (self.calc_benefit_birthday
             + relativedelta(years=self.collection_start_age[0],
                             months=self.collection_start_age[1],
                             day=1))
        if benefit_date is None:
            benefit_year = benefit_start_date.year
            benefit_month = benefit_start_date.month
        else:
            benefit_year = benefit_date[0]
            benefit_month = benefit_date[1]
#            print(benefit_year, benefit_start_date.year)
#            print(benefit_month, benefit_start_date.month)
            if ((benefit_year < benefit_start_date.year)
                or ((benefit_year == benefit_start_date.year)
                    and (benefit_month < benefit_start_date.month))):
                #                print("returning not eligible")
                # ineligible year, month, do not put in cache
                # we would have to have the cache be by month, too, and
                # this is a lot of complexity for little benefit
#                print(benefit_year)
#                print(benefit_start_date.year)
#                print(benefit_month)
#                print(benefit_start_date.month)
#                print("ineligible")
                return 0.0

        # first retrieve out of the cache
        # if the benefit has already been calculated, then simply retirieve
        # it from the cache, which is erased when relevant worker variables
        # are changed
        benefit = 0.0
        if benefit_year in self.mo_benefit:
            benefit = self.mo_benefit[benefit_year]
#            print("benefit in chache", benefit)
            return benefit

        # Now to calculate the benefit. Note that these calculations must be
        # performed in this specific order, and all calcuations use the
        # previous birth year (calc_benefit_birthday.year) for someone born
        # Jan 1. Note that this calculation is repeated every year.
        # First we calculate the base_benefit based on the bend points
        # if we asked for the benefit in a month before we applied for the
        # benefits, then no calculation needed, return 0
        #
        # base benefit is pre-calculated (see _clac_base_benefit())
        # based on earnings profile, or average monthly indexed income (AIME),
        # (see _calc_aime() in ss_earnings.py)
        # and average wage index (AWI) profile (see calc_income_index_facotr()
        # in ss_awi.py)
        # base benefit is the benefit at age 62 WITHOUT adjustment for
        # when you collect benefits and is always calculated first
        #
        # Ironically, the only way anyone is actually paid the base benefit
        # is if they were born on the 2nd of the month and chooses to receive
        # benefits at age 62 years, 0 months
#        print(self.base_benefit)

        # cost-of-living-adjustment (cola) of base benefit is calculated next
        # and is calculated by applying cola for each year from the
        # base benefit (eligibility year aged 62) through to the benefit year
        #
        # Your base benefit is your benefit at full retirement age
        # However, for cost-of-living adjustment (COLA) purposes, this base
        # benefit is actually in the dollars for the year you turn 62
        # (remember born Jan 1 is considered to be born in the previous year)
        # So then the COLA to base benefit applies from age 62 to your benefit
        # year.
        #
        # Example, we want to calculate the benefit in year 2040 for a worker
        # born in 1968 and the base_benefit at FRA (age 67 or 2035) is $1,000
        # in ***2030 (age 62) dollars***. For this calculation, we ignore what
        # the FRA is and focus on the benefit year (2040) for which we are
        # calculationg. We then apply COLA for each year from 2030 to 2040 to
        # get the cost-of-living-adjusted (COLA) base benefit
        #
        # note this may already be calculated and is in cache which is
        # erased when relevant worker variables are changed
        if benefit_year not in self.mo_benefit_cola:
            self._calc_benefit_cola(benefit_year)

#        print(self.mo_benefit_cola[benefit_year])

        # now the actual benefit is calculated
        # we have calculated the base benefit, then adjusted for cost-of-living
        # increases from age 62 to the benefit year
        # now we apply the benefit multiplier, which is based on the worker's
        # birth year and the age the worker has chosen to being collecting
        # benefits. (see get_benefit_multiplier in socialsecurity.py)
        # This has also been pre-calculated and is re-calculated if the
        # worker's age of collecting benefits is changed
        # Note the worker's birth year cannot be changed, instead a new
        # worker would need to be instantiated.
        #
        benefit = math.floor((self.mo_benefit_cola[benefit_year]
                             * self.benefit_multiplier))

#        print(self.benefit_multiplier)

#        print(benefit)

        # TBD and NOT IMPLEMENTED:
        # If the worker elects to receive benefits before full retirement age
        # (FRA) but still has significant income, then the benefit is
        # reduced by 50%
        # The threshold is higher during the exact year of FRA
        # In years later than FRA, the worker can continue to earn income
        # without penalty.
        # Furthermore, the threshold adjusts every year
        #
        # This is further complicated by the fact that, prior to the year
        # 2000, the reduction was based on age, not FRA, and prior to 1975
        # it applied to ALL income, reduced by 50%. This law was changed
        # primarily for people for whom social security was just not enough
        # and wanted to supplement it with some extra income.
        #
        # TBD: Introduce annual earnings limit for years before or at FRA
        # $1 of benefit will be withheld for every $2 of earnings in excess of
        #   the exempt amount in years prior to reaching FRA
        # $1 of benefit will be withheld for every $3 of earnings in execss of
        #   the exempt amount in the year of FRA, and only applies to income
        #   received in months prior to attaining FRA
        # There is a table for this, but from 2002 it can be calculated as:
        #   before FRA:
        #       round(AWI(2yrsprior) * 67.0 / 22935.42, 0) * 10.0 * 12.0
        #   at FRA:
        #       round(AWI(2yrsprior) * 250.0 / 32154.82, 0) * 10.0 * 12.0
        #   From 1975-2001 you must use the table, and prior to 1975 both
        #       numbers were 0
        # Note that these limits will not increase when there has been no COLA
        #   applied for that year (which is the COLA for the previous year)
        # Also, the limit cannot decrease from the previous year
        #
        # This is futher compounded by the fact that the full month's worth of
        #   benefit is withheld until the amount to be withheld is met or
        # Any excess withheld will be paid out in the next calendar year
        #
        # Example: During 2021, you plan to work and earn $23,920 ($4,960
        #   above the $18,960 limit). We would withhold $2,480 of your
        #   Social Security benefits ($1 for every $2 you earn over the limit).
        #   To do this, we would withhold all benefit payments
        #   from January 2021 through May 2021.
        #   Beginning in June 2021, you would receive your $600 benefit
        #   and this amount would be paid to you each month for the remainder
        #   of the year.
        #   In 2022, we would pay you the additional $520 we withheld in May
        #   2021.

        # This is further complicated by the fact that, prior to the year
        # 2000, the reduction was based on age, not FRA, and prior to 1975
        # it applied to ALL income, reduced by 50%. This law was changed
        # primarily for people for whom social security was just not enough
        # and wanted to supplement it with some extra income.

        # Finally, if this tool is used to calculate what the benefits
        # were in the past, then the income history of the worker needs to
        # be the TOTAL income and not the social security earnings. Otherwise,
        # when this rule is fully implemented, it will be inaccurate if the
        # rule was applied. Note that if the income history contains income
        # higher than the social security maximum wage threshold, then it is
        # treated as the maximum wage.
        #
        # So what to do until this is fully implemented? That's a tough call.
        # First off, after 2000, this is a terrible strategy.
        # The only "good" case for someone doing this is if they retire early
        # but then later want to come out of retirement unexpectedly for some
        # reason, prior to reaching FRA. This still is a result of poor
        # planning.
        #
        # Because it is such a terrible strategy now, I have chosen this
        # implementation as a very low priority
        #
        # So until this is fully implemented, I have chosen to apply the
        # 2022 rules to all years. Unfortunately, this means it is only
        # truly accurate for benefit year 2022.

        """
        income_ben_year = self.earnings.get_total_earn_in_year(benefit_year)
        fra = self.get_fra()
        fra_benefit_year = fra[0] + self.calc_benefit_birthday.year
        if benefit_year == fra_benefit_year:
            if income_ben_year > 51960.00:
                benefit = float(math.ceil(
                    benefit - ((income_ben_year - 51960.00) / 2.0)))
                if benefit < 0.0:
                    benefit = 0.0
                print("reduced benefit")
        elif benefit_year < fra_benefit_year:
            if income_ben_year > 19560.00:
                benefit = float(math.ceil(
                    benefit - ((income_ben_year - 19560.00) / 2.0)))
                if benefit < 0.0:
                    benefit = 0.0
                print("reduced benefit")
        """

        self.mo_benefit[benefit_year] = benefit
        return benefit

    def get_benefit_info(self):
        """
        Gets benefit information about the calculation

        Returns
        -------
        TYPE
            DESCRIPTION.
        TYPE
            DESCRIPTION.
        TYPE
            DESCRIPTION.

        """
        return self.earnings.get_aime(), self.base_benefit, self.bp1, self.bp2
