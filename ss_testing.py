#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 28 04:45:06 2021.

@author: dfox
"""

import datetime as dt
import os
import pandas as pd
from dateutil.relativedelta import relativedelta
import socialsecurity as ssc
import ss_worker as ssw
from pandas._testing import assert_frame_equal

inc_hist_filename = os.path.join(".", "SS_worker_test_earnings_1000.csv")
personal_filename = os.path.join(".", "SS_worker_test_data_1000.csv")
base_worker_test_filename = os.path.join(".",
                                         "SS_worker_test_baseline_1000.csv")
out_worker_test_filename = os.path.join(".",
                                        "SS_worker_test_output_1000.csv")
SS_LIFESPAN = 130


def max_income_test(start_year, final_year):
    """
    Execute the test that uses maximum income to generate a table.

    The table must match the one supplied by the SSA on ssa.gov.
    Note we have saved two tables, one from 2021 and another from 2022. If
    we're diligent, we can save off a new table each year and create a test
    around that, too.

    For now, we just match the 2022 table.

    Parameters
    ----------
    start_year : int
        The year at which the entries in the table start.
        (Happens to be 1989, but we could always make a table of different
         years. HOWEVER, the ssa.gov table runs from 1989 through 2022, so
         that is the one we will use)
    final_year : int
        The year at which the entries in the table end. Usually the current
        year, which is defined as the latest year we have maximum data for.

    Returns
    -------
    df: pandas DataFrame
        The dataframe the code generates, which will be compared to the one
        read in from the table

    """
    reccols = ['Retirement_Jan_Year', 'AIME_62_1', 'Initial_62_1',
               'In_2022_62_1', 'AIME_65_0', 'Initial_65_0', 'In_2022_65_0',
               'AIME_66_0', 'Initial_66_0', 'In_2022_66_0', 'AIME_67_0',
               'Initial_67_0', 'In_2022_67_0', 'AIME_70_0', 'Initial_70_0',
               'In_2022_70_0']

    df = pd.DataFrame()

    ss = ssc.SSConfig(cola_proj=0.024, ss_wage_growth=0.036)

    for retire_year in range(start_year, final_year+1):
        stats = {}
        stats['Retirement_Jan_Year'] = retire_year
        for retire_age in [(62, 1), (65, 0), (66, 0), (67, 0), (70, 0)]:
            birthday = dt.date(retire_year - retire_age[0], 1, 3)

            worker = ssw.SSWorker(ss, "Max_Income_Test", birthday, 'use_max',
                                  next_income_aount='use_max')

            worker.reset_retirement_age(retire_age[0], retire_age[1])
            worker.reset_collection_start_age(retire_age[0], retire_age[1])

            mo_benefit = worker.get_mo_benefit((retire_year, 2))
            mo_benefit_at_2022 = worker.get_mo_benefit((final_year, 2))
            aime = worker.get_aime()

            stats['AIME_{}_{}'.format(retire_age[0], retire_age[1])] = aime
            stats['Initial_{}_{}'.format(retire_age[0], retire_age[1])] =\
                mo_benefit
            stats['In_{}_{}_{}'.format(final_year, retire_age[0],
                                       retire_age[1])] = mo_benefit_at_2022

        rec = [value for value in stats.values()]
        reccols = [key for key in stats]
        recseries = pd.Series(rec, reccols)
        df = df.append([recseries])
    return df


def generate_max_income_test():
    """
    Generate the table for the maximum income test.

    CAREFUL! We SHOULD use the tables supplied by ssa.gov, but if in the
    future there are no more tables supplied as each year comes, then we can
    use this routine to generate the table to compare against in the future.
    This means THIS CODE MUST BE ACCURATE.

    As years are added, benefit_year should be increased, and the filename
    generated, you can see, has that year embedded in it.

    Returns
    -------
    None.

    """
    # return initial benefit, 2022 benefit
    start_year = 1989
    benefit_year = 2022
    now = dt.datetime.now()
    test_results_filename = os.path.join(".",
                                         "MaxIncomeTestResults_{}_{}.csv"
                                         .format(start_year, benefit_year))
    df = max_income_test(start_year, benefit_year)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(test_results_filename, index=False)
    runtime = dt.datetime.now() - now
    print("generate_max_income_test() runtime = {}".format(runtime))


def assert_test_equal_df(lhs, rhs):
    """
    Test if one pandas DataFrame equals another.

    Asserts if not equal, so only use this if it is an error to not be equal.

    Parameters
    ----------
    lhs : pandas DataFrame
        Left-hand side. Since this is an equals test, lhs and rhs are
        interchangable
    rhs : pandas DataFrame
        Right-hand side.

    Returns
    -------
    None.

    """
    lhs_c = lhs.copy()
    rhs_c = rhs.copy()
    for col in lhs_c:
        if lhs_c[col].dtype is dt.date:
            lhs_c[col] = lhs_c[col].astype(str)
    for col in rhs_c:
        if rhs_c[col].dtype is dt.date:
            rhs_c[col] = rhs_c[col].astype(str)
    assert_frame_equal(lhs_c, rhs_c)


def regression_max_income_test():
    """
    Check that maximum income handling has not been affected by changes.

    Regression test.

    Returns
    -------
    None.

    """
    # return initial benefit, 2022 benefit
    start_year = 1989
    benefit_year = 2022
    now = dt.datetime.now()
    test_compare_filename = os.path.join(".",
                                         "MaxIncomeTestResults_{}_{}.csv"
                                         .format(start_year, benefit_year))
    output_filename = os.path.join(".", "MaxIncomeTestResults_{}_{}_Run.csv"
                                   .format(start_year, benefit_year))
    trdf = pd.read_csv(test_compare_filename)
    df = max_income_test(start_year, benefit_year)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(output_filename, index=False)
    assert_test_equal_df(df, trdf)
    runtime = dt.datetime.now() - now
    print("regression_max_income_test() SUCCESS runtime = {}".format(runtime))


def worker_earnings_test():
    """
    Execute the test to generate a benefits DataFrame from worker earnings.

    Returns
    -------
    df : pandas DataFrame
        DataFrame of the otuput. Can be used to create a table to be used for
        regression testing or to create a table to be compared with an
        accurate run for regression testing.

    """
    df = pd.DataFrame()

    ssconf = ssc.SSConfig()
    current_year = ssconf.get_current_year()

    pddf = pd.read_csv(personal_filename)
    pddf['Birthday'] = pddf['Birthday'].apply(pd.to_datetime)

    for index, row in pddf.iterrows():
        # each row is a worker
        worker = row['Worker']

        birthday = row['Birthday']

        wihdf = pd.read_csv(inc_hist_filename)
        wihdf.sort_values('Year')
        wihdf.set_index('Year', drop=True, inplace=True)

        if ('Next_Income_Year' in row
                and row['Next_Income_Year'] != 'Next_Year'):
            if pd.isnull(row['Next_Income_Year']):
                next_income_year = None
            else:
                next_income_year = int(row['Next_Income_Year'])
        else:
            next_income_year = 'current_year'

        personal_wage_growth = row['Annual_Wage_Growth']

        if ('Next_Income_Amount' in row
                and row['Next_Income_Amount'] != 'Use_Last'):
            next_income_amount = row['Next_Income_Amount']
        else:
            next_income_amount = 'extrapolate'

        stats = {}
        stats['Worker'] = worker
        ssworker = ssw.SSWorker(ssconf, worker, birthday, wihdf[worker],
                                next_income_year=next_income_year,
                                next_income_amount=next_income_amount,
                                personal_wage_growth=personal_wage_growth)
        for retire_age in [(62, 1), (65, 0), (66, 0), (67, 0), (70, 0)]:
            ssworker.reset_retirement_age(retire_age[0], retire_age[1])
            ssworker.reset_collection_start_age(retire_age[0], retire_age[1])
            benefit_start_date = (ssworker.get_calc_benefit_birthday()
                                  + relativedelta(years=retire_age[0],
                                                  months=retire_age[1],
                                                  day=1))
            mo_benefit = ssworker.get_mo_benefit((benefit_start_date.year+1,
                                                  1))
            mo_benefit_current_dollars = \
                int(ssconf.value_in_current_dollars(mo_benefit,
                                                    benefit_start_date.year+1))
            aime, base_benefit, bp1, bp2 = ssworker.get_benefit_info()

            stats['AIME_{}_{}'.format(retire_age[0], retire_age[1])] = aime
            stats['Base_Benefit_{}_{}'.format(retire_age[0],
                                              retire_age[1])] = base_benefit
            stats['BP1_{}_{}'.format(retire_age[0], retire_age[1])] = bp1
            stats['BP2_{}_{}'.format(retire_age[0], retire_age[1])] = bp2
            stats['Benefit_{}_{}_Age_{}'.format(retire_age[0], retire_age[1],
                                                retire_age[0]+1)] = mo_benefit
            stats['Benefit_{}_{}_In_{}_$'.format(retire_age[0], retire_age[1],
                                                 current_year)] = \
                mo_benefit_current_dollars

        rec = [value for value in stats.values()]
        reccols = [key for key in stats]
        recseries = pd.Series(rec, reccols)
        df = df.append([recseries])
    return df


def generate_worker_earnings_test():
    """
    Generate the table for the worker earnings test.

    CAREFUL! This will generate the baseline output table. It will be tested
    against in the future to execute a regression test and compare the
    resulting table.

    Returns
    -------
    None.

    """
    # return initial benefit, 2022 benefit
    now = dt.datetime.now()
    df = worker_earnings_test()
    df.reset_index(drop=True, inplace=True)
    df.to_csv(base_worker_test_filename, index=False)
    runtime = dt.datetime.now() - now
    print("generate_worker_earnings_test() runtime = {}".format(runtime))


def regression_worker_earnings_test():
    """
    Check that calculations hav not been affected by changes.

    Regression test.

    Returns
    -------
    None.

    """
    # return initial benefit, 2022 benefit
    now = dt.datetime.now()
    bwdf = pd.read_csv(base_worker_test_filename)
    df = worker_earnings_test()
    df.reset_index(drop=True, inplace=True)
    df.to_csv(out_worker_test_filename, index=False)
    assert_test_equal_df(df, bwdf)
    runtime = dt.datetime.now() - now
    print("regression_worker_earnings_test() SUCCESS runtime = {}"
          .format(runtime))


# generate_max_income_test()
regression_max_income_test()

# generate_worker_earnings_test()
regression_worker_earnings_test()
