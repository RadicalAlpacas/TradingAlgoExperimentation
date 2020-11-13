#%%
import requests 
import json
import pandas as pd
from time import time
import time as tm
from datetime import datetime, timedelta, date
import numpy as np
from simple_rsi import callable_rsi_backtest
import os
# Set Finnhub api keys
# finnhubKey = keys.keys.get("finnhub")
ALPACA_KEY = os.environ['alpaca_paper']
# IEXKey = keys.keys.get("iex")

# MIsc global options
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
# %%
def get_All_Tickers(date = (date.today())):

    #chech to see if a pickled version for requested date exists, if so, just return that:
    try:
        # SAVE THE DF Locally because this operation uses a lot of api pts wherever you do it. 
        # polygon_tickers_dataframe = pd.read_pickle(f"Stock_universe_{date}")
        print("existing Universe for selected date found, loaded cache")
        return polygon_tickers_dataframe
    except:
        print(f"existing universe for {date} not found, querying polygon API")
        pass

    # function to find & filter all symbols for any date
    # #Get all tickers:
    try:
        polygonTickersData = requests.get(f"https://api.polygon.io/v2/aggs/grouped/locale/US/market/STOCKS/{str(date)}?unadjusted=false&apiKey={ALPACA_KEY}").json().get("results")

        polygon_tickers_dataframe = pd.DataFrame(polygonTickersData)
        print(polygon_tickers_dataframe.head())
        if not polygonTickersData:
            Print("ERROR No Polygon tickers data found")
            raise Exception ("empty Polygon Tickers data, check Polygon api status")
    except Exception as e:
        print(f"failed to query polygon api {e}")
    # Filter 
    # Volume over 1mil, close price over 15&under 200
    polygon_tickers_dataframe = polygon_tickers_dataframe.loc[(polygon_tickers_dataframe["v"]>=1000000 ) & (polygon_tickers_dataframe["c"]>=15 ) & (polygon_tickers_dataframe["c"]<=200)]
    polygon_tickers_dataframe = polygon_tickers_dataframe.sort_values(by=["T"])
    polygon_tickers_dataframe.reset_index(inplace = True)
    # polygon_tickers_dataframe.to_pickle(f"Stock_universe_{date}")
    return polygon_tickers_dataframe

# %%

def rsi_optimizer(periods_list, rsi_lower_list, rsi_upper_list, symbol, start_date, end_date=date.today(), init_cash=1000):
    # Start the timer!
    start_time = time()
    # 
    null_return_dict = {
    "symbol":symbol,
    "optimal_rsi_period" : None,
    "optimal_rsi_lower" : None,
    "optimal_rsi_upper" : None,
    "profit": None,
    "roi":None,
    "buy_and_hold":None}

    # make a list of all the values to test
    periods_list = np.arange(periods_list[0],periods_list[1],periods_list[2], dtype=int)
    rsi_lower_list = np.arange(rsi_lower_list[0],rsi_lower_list[1],rsi_lower_list[2], dtype=int)
    rsi_upper_list = np.arange(rsi_upper_list[0],rsi_upper_list[1],rsi_upper_list[2], dtype=int)
    print(f"total possiblities:{len(periods_list)*len(rsi_lower_list)*len(rsi_upper_list)}")
    # Make a 3grid of 0 placeholders
    period_grid = np.zeros(shape=(len(periods_list),len(rsi_lower_list),len(rsi_upper_list)))
 
    ## RSI Optimization; run the grid search
    try:
        for i, rsi_period in enumerate(periods_list):
            for j, rsi_lower in enumerate(rsi_lower_list):
                for k, rsi_upper in enumerate(rsi_upper_list):
                    results = callable_rsi_backtest(symbol1 = symbol, 
                                                    start_date = start_date, 
                                                    end_date =  end_date, 
                                                    period = rsi_period, 
                                                    lower = rsi_lower, 
                                                    upper = rsi_upper, 
                                                    cash = init_cash
                                                    )
                    net_profit1 = results.pnl_val
                    period_grid[i,j,k] = net_profit1

    except Exception as e:
        print(f"error occured in rsi_optimizer: {e}")     

        return null_return_dict, 0
  
    # Find highest profit
    best_params_position = np.unravel_index(period_grid.argmax(), period_grid.shape)
    # find position of highest profit
    optimal_rsi_period = periods_list[best_params_position[0]]
    optimal_rsi_lower = rsi_lower_list[best_params_position[1]]
    optimal_rsi_upper = rsi_upper_list[best_params_position[2]]
    profit = np.amax(period_grid)

    #calculate the percent return of the strategy (ROI)
    roi = profit/init_cash

    # calculate change in the equity over the time period 
    # buy_and_hold = (stock_data_df["close"].iloc[-1]-stock_data_df["close"].iloc[0])/stock_data_df["close"].iloc[0]
    buy_and_hold = results.analyzers.getbyname("basereturn").get_analysis()
    #TO get the data out, you have to do this: it basically takes the data out of its ordered list, or collection, then gets it within 2 indexes...
    buy_and_hold = list(buy_and_hold.items())[0][1]

    # make a dict with the values to return
    return_dict = {
        "symbol":symbol,
        "optimal_rsi_period" : optimal_rsi_period,
        "optimal_rsi_lower" : optimal_rsi_lower,
        "optimal_rsi_upper" : optimal_rsi_upper,
        "profit":profit,
        "roi": roi,
        "buy_and_hold": buy_and_hold ### !!! TEMP NOT WORKING
    }

    # Calculate total time taken by the function
    end_time = time()
    time_basic = end_time-start_time

    return return_dict, time_basic


# https://bbs.archlinux.org/viewtopic.php?id=77634
def humanize_time(secs):
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return '%02d:%02d:%02d' % (hours, mins, secs)

#%%
def multi_stock_rsi_optimize(df_of_stocks, end_date):
    start_time = time()
    # Add empty columns to dataframe
    results_df = pd.DataFrame(columns = ["symbol", "optimal_rsi_period","optimal_rsi_lower","optimal_rsi_upper","profit", "roi", "buy_and_hold"])
    # set certain columns to smaller data types
    results_df.symbol = results_df.symbol.astype('string')
    results_df.optimal_rsi_period = results_df.optimal_rsi_period.astype('int16')
    results_df.optimal_rsi_lower = results_df.optimal_rsi_lower.astype('int16')
    results_df.optimal_rsi_upper = results_df.optimal_rsi_upper.astype('int16')
    results_df.roi = results_df.roi.astype('float16')
    results_df.buy_and_hold = results_df.buy_and_hold.astype('float16')
    results_df.profit = results_df.profit.astype('float32')
    print(results_df.dtypes)
    symbol_count=0
    for symbol in df_of_stocks:

        symbol_dict, time_one_symbol = rsi_optimizer([3,34,10],[30,41,5],[64,75,5], symbol, datetime(2020, 6, 1), end_date=end_date)
        results_df = results_df.append(symbol_dict, ignore_index=True)

        # Time calculation function
        time_left = ((len(df_of_stocks)-(symbol_count+1))*time_one_symbol)
        print(f"projected time left: {humanize_time(time_left)}")
        # Temp save function to salvage some data from a very long test [depreciated]
        # if (symbol_count % 50 == 0):
        #     results_df.to_pickle(keys.backtests_path/'Partials'/f"{end_date}_Partial_Backtest_Save")
        print(f"finished symbol: {symbol}. {symbol_count+1} analyized so far out of {len(df_of_stocks)}.")
        symbol_count = symbol_count+1


    end_time = time()
    time_basic = end_time-start_time


    return results_df, time_basic


# %%
def run_strategy_generator(date):
    # convert the passed date to string:
    date_str=datetime.strftime(date, "%Y-%m-%d")
    all_ticks = get_All_Tickers(date_str)#.loc[0:400]
    # just get what you need from all ticks-- the ticks! Should save some ram
    all_ticks = all_ticks['T']
    if all_ticks.empty==True :
        print("could not find tickers")
        raise 
    # RUn the mult stock rsi Optimizer
    backtest, time_basic = multi_stock_rsi_optimize(all_ticks, date)
    # Pickle the results of the multistock Optimizer
    # backtest.to_pickle(keys.backtests_path / date_str)
    #print the total time to complete
    print(f"time to complete backtester: {time_basic}")

    # drop empty rows
    backtest.dropna(
        axis=0,
        how='any',
        thresh=None,
        subset=None,
        inplace=True
    )
    # good information for logging in the future:
    # newDf["alpha"] = newDf["roi"]-newDf["buy_and_hold"]
    # total_results = len(backtest)
    # positive_alpha = len(backtest.loc[Backtest["alpha"]>1])
    # pct_positive_alpha = positive_alpha/total_results

    return backtest