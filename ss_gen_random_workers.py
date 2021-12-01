#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 30 03:32:56 2021

@author: dfox
"""
import datetime as dt
import math
import os
import pandas as pd
import random
import socialsecurity as ss


def gen_random_date(start_date, end_date):
    """
    Generates a random date within the date range from start_date (inclusive)
    to end_date (exclusive)

    Parameters
    ----------
    start_date : datetime.date
        The beginning of the range (inclusive) of dates from which to choose a
        random date.
    end_date : datetime.date
        The end of the range (exclusive) of dates from which to choose a random
        date.

    Returns
    -------
    random_date : datetime.date
        The generated random date.

    """
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + dt.timedelta(days=random_number_of_days)
    return random_date


def gen_random_earnings_history(ssconfig, birthday):
    ss_birthday = birthday - dt.timedelta(days=1)
    start_base = random.randrange(100)
    if start_base < 66:
        start_age = 18
        start_fraction = random.randrange(30, 120) / 100.0
    elif start_base < 87:
        start_age = 22
        start_fraction = random.randrange(70, 200) / 100.0
    elif start_base < 97:
        start_age = 24
        start_fraction = random.randrange(140, 250) / 100.0
    else:
        start_age = 29
        start_fraction = random.randrange(200, 1000) / 100.0
    pwg = random.randrange(20, 50) / 1000.0
    retire_age = random.randrange(62, 76)
    if retire_age == 75:
        retire_age = random.randrange(75, 86)
    if retire_age == 85:
        retire_age = random.randrange(85, 95)
    if ss_birthday.month == 2 and ss_birthday.day == 29 and start_age % 4 != 0:
        start_date = dt.date(ss_birthday.year + start_age, 3, 1)
    else:
        start_date = dt.date(ss_birthday.year + start_age, ss_birthday.month,
                             ss_birthday.day)
    if (ss_birthday.month == 2 and ss_birthday.day == 29
            and retire_age % 4 != 0):
        end_date = dt.date(ss_birthday.year + retire_age, 3, 1)
    else:
        end_date = dt.date(ss_birthday.year + retire_age, ss_birthday.month,
                           ss_birthday.day)
    stop_year = end_date.year
    if stop_year >= ssconfig.get_current_year():
        stop_year = ssconfig.get_current_year() - 1
    base_value = ssconfig.get_awi_value(start_date.year)
    if base_value == 0.0:
        base_value = ssconfig.get_max_ss_wage(start_date.year)
    start_wage = math.floor(start_fraction * base_value)

    earnings = {}
    next_wage = start_wage
    for year in range(start_date.year, stop_year+1):
        gap_base = random.randrange(100)
        if gap_base < 4:
            continue
        if year == start_date.year:
            earnings[year] = int(next_wage * (12 - start_date.month) / 12.0)
        elif year == end_date.year:
            earnings[year] = int(next_wage * start_date.month / 12.0)
        else:
            earnings[year] = int(next_wage)
            assert earnings[year] != 0
        if (ssconfig.get_awi_value(year) != 0.0
                and ssconfig.get_awi_value(year+1) != 0.0):
            awi_growth = (ssconfig.get_awi_value(year+1)
                          / ssconfig.get_awi_value(year)) - 1
            npwg = pwg * awi_growth / 0.035
        else:
            npwg = pwg
        next_wage = int(next_wage * (1.0 + npwg))

    return earnings, start_date, end_date, pwg


def gen_random_worker(ssconfig, name):
    worker = {}
    current_year = ssconfig.get_current_year()
    rand_start_date = dt.date(1924, 1, 2)
    rand_end_date = dt.date(2000, 1, 2)
    birthday = gen_random_date(rand_start_date, rand_end_date)
    earnings, start_date, retire_date, pwg = \
        gen_random_earnings_history(ssconfig, birthday)

    earnings_new = {}
    for year in range(rand_start_date.year, current_year):
        if year not in earnings:
            earnings_new[year] = 0
        else:
            earnings_new[year] = earnings[year]

    if start_date.year >= current_year:
        next_income_year = start_date.year
    elif retire_date.year < current_year:
        next_income_year = None
    else:
        gap_base = random.randrange(100)
        if gap_base < 4:
            next_income_year = current_year + 1
        else:
            next_income_year = 'Next_Year'

    next_income_amount = 'Use_Last'

    worker['Worker'] = name
    worker['Birthday'] = birthday
    worker['Annual_Wage_Growth'] = pwg
    worker['Next_Income_Year'] = next_income_year
    worker['Next_Income_Amount'] = next_income_amount

    return worker, earnings_new


def gen_random_personal_data():
    ssconfig = ss.SSConfig()
    workers = []
    earnings_list = []
    random.seed(423)
    for index in range(1000):
        worker, earnings = gen_random_worker(ssconfig,
                                             'Worker_{}'.format(index))
        workers.append(worker)
        earnings_list.append(earnings)
    worker_cols = [key for key in workers[0]]
    earnings_cols = ['Year']
    earnings_cols.extend([worker['Worker'] for worker in workers])
    wdf = pd.DataFrame()
    for worker in workers:
        rec = [value for value in worker.values()]
        recseries = pd.Series(rec, worker_cols)
        wdf = wdf.append([recseries])
    edf = pd.DataFrame(index=[key for key in earnings_list[0].keys()])
    edf.index.rename('Year', inplace=True)
    for index, earnings in enumerate(earnings_list):
        series = pd.Series(earnings, index=[key for key in earnings.keys()])
        edf[workers[index]['Worker']] = series

    wdf.to_csv(os.path.join(".", "SS_worker_test_data.csv"), index=False)
    edf.to_csv(os.path.join(".", "SS_worker_test_earnings.csv"))


now = dt.datetime.now()
gen_random_personal_data()
runtime = dt.datetime.now() - now
print("gen_random_personal_data() SUCCESS runtime = {}".format(runtime))
