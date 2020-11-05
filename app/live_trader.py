#%%
import requests
import keys
from datetime import date, timedelta, datetime
import datetime as dt
import pandas as pd
import alpaca_trade_api as tradeapi
import numpy as np
import fastquant3
import os

#google cloud imports
import io
from io import BytesIO
from google.cloud import storage

# symbol = "AAPL"
# start_date = "2020-08-01"
alpaca_secret = keys.keys.get("alpaca_secret")
alpaca_secret_live = keys.keys.get("alpaca_secret_live")
alpaca_live = keys.keys.get("alpaca_live")
alpaca_paper = keys.keys.get("alpaca_paper")
 
  # Set varables depending on paper trading or not
PAPER_TRADE = True

if PAPER_TRADE==True:
    api_base = 'https://paper-api.alpaca.markets'
    headers = {
    "APCA-API-KEY-ID": alpaca_paper, 
    "APCA-API-SECRET-KEY": alpaca_secret
    }
elif PAPER_TRADE==False:
    api_base ="https://api.alpaca.markets"
    headers = {
    "APCA-API-KEY-ID": alpaca_live,
    "APCA-API-SECRET-KEY": alpaca_secret_live
    }
# Setuo the API globally 
# rest methods https://pypi.org/project/alpaca-trade-api/
api = tradeapi.REST(headers.get("APCA-API-KEY-ID"), headers.get("APCA-API-SECRET-KEY") , base_url=api_base)

# # Setup Storage client
# storage_client = storage.Client.from_service_account_json('backtestalgov1-db431f91295d.json')
# BUCKET_NAME = 'backtests-and-positions'
# #make bucket object
# bucket = storage_client.get_bucket(BUCKET_NAME)

# blob = bucket.blob('myfirstblob.pickle')

# blob.upload_from_filename('Backtesting/2020-11-02')
# blob.download_to_filename("THING")
# DF = pd.read_pickle("THING")
#################################################

#%%
# historic_symbol_data = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{date.today()}?unadjusted=false&sort=asc&apiKey={alpaca_live}").json().get("results")
# %%
# symboldf = pd.DataFrame(historic_symbol_data)



#Quick convert to normal time from epoch:
def epoch_to_msec(time):
    s = time / 1000.0
    # new_time=datetime.fromtimestamp(s).strftime('%Y-%m-%d %H:%M:%S.%f')
    new_time=datetime.fromtimestamp(s).strftime('%Y-%m-%d')

    return new_time
######################################
#%%
def RSI_parser(symbol, end_date, period):
    # Set start date: 
    # day to account for weekends *** BUT NOT HOLIDAYS, hence roughly XX% day Buffer ** also will not work properly when run on weekends (buffer covers for this flaw also)
    # *2 because there needs to be additional data beyond the lookback period as rsi is recursive
    offset_days = -(period+((period//7)*2)+(period%7)+2)*2
    start_date = end_date + timedelta(days = offset_days)
    # Unneccessary formatting
    start_date = datetime.strftime(start_date, "%Y-%m-%d")
    end_date = datetime.strftime(date.today(), "%Y-%m-%d")
    # Get Symbol Data
    historic_symbol_data = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}?unadjusted=false&sort=asc&apiKey={alpaca_live}").json().get("results")
    #shove it in a dataframe real quick:
    historic_symbol_data = pd.DataFrame.from_dict(historic_symbol_data)
    #fix dates 
    # historic_symbol_data["t"] = historic_symbol_data.t.apply(epoch_to_msec)
    # Calcuate the RSI:
    RSI_df = RSI(historic_symbol_data, period)
    # Extract and return the RSI
    max_date_row = RSI_df.loc[RSI_df["t"]==(RSI_df["t"].max())]
    max_date_row.reset_index(inplace = True)
    final_rsi = max_date_row["RSI_current"][0]
    return final_rsi



# %%
def RSI(df, period, base="c"):
    """
    Function to compute Relative Strength Index (RSI)
    https://github.com/arkochhar/Technical-Indicators/blob/master/indicator/indicators.py
    Args :
        df : Pandas DataFrame which contains ['date', 'open', 'high', 'low', 'close', 'volume'] columns
        base : String indicating the column name from which the MACD needs to be computed from (Default Close)
        period : Integer indicates the period of computation in terms of number of candles
        
    Returns :
        df : Pandas DataFrame with new columns added for 
            Relative Strength Index (RSI_$period)
    """
 
    delta = df[base].diff()
    up, down = delta.copy(), delta.copy()

    up[up < 0] = 0
    down[down > 0] = 0
    
    rUp = up.ewm(com=period - 1,  adjust=False).mean()
    rDown = down.ewm(com=period - 1, adjust=False).mean().abs()
    # Nice way to add the period to the column, we don't need that 
    # df['RSI_' + str(period)] = 100 - 100 / (1 + rUp / rDown)
    # df['RSI_' + str(period)].fillna(0, inplace=True)
    df['RSI_current'] = 100 - 100 / (1 + rUp / rDown)
    df['RSI_current'].fillna(0, inplace=True)

    return df


# Entry Contiditions Evaluation
def get_entries(backtest):

    backtest["alpha"] = backtest["roi"]-backtest["buy_and_hold"]
    # find the current RSI of every positive alpha item:
    backtest = backtest.loc[backtest["alpha"]>0]
    # include only profitable strategies:
    backtest = backtest.loc[backtest["profit"]>0]
    # Get the Current RSI for each symbol given the RSI period. 
    backtest["RSI_current"] = np.vectorize(RSI_parser)(backtest['symbol'],date.today(),backtest["optimal_rsi_period"])
    # Of all items tested, get only those where the Current RSI is lower than the Optimal low RSI entry pt
    buying_opp = backtest.loc[backtest["optimal_rsi_lower"]>backtest["RSI_current"]]

    #sort and re-index the new dataframe before returning
    
    buying_opp = buying_opp.sort_values(by=['alpha'], ascending=False)
    buying_opp.reset_index(inplace=True)
    buying_opp.set_index('symbol')

    return buying_opp

#%%

def exits_helper(stop_price,temp_stop_price):
    if ((stop_price<temp_stop_price) | (stop_price==None)):
        return temp_stop_price
    else:
        return stop_price

# Exit Conditions Evaluation
def get_exits(current_positions):
    """
    for each symbol in the dataframe of current assets:
        if over the max RSI place sell order immediately and remove from the positions df
        get the stop value, if its tighter than the current one update it & place a new limit order in alpaca

    repickle the positions df 
    Positions DF:
    symbol|rsi_period|rsi_lower|rsi_upper|current_rsi|modeled_returns|alpha|entry_date|entry_price|exit_date|exit|price
    """
    if current_positions.empty == True:
        return current_positions
    current_positions["temp_stop_price"] = np.vectorize(get_stop)(current_positions["symbol"],
                                    date.today(),
                                    current_positions["optimal_rsi_period"],
                                    (current_positions["optimal_rsi_period"]*2),
                                    stop_factor=3)
    # check if stop columns exist:
    if ('stop_price' in current_positions):
        # !!!!!!!!!!!!!check if there is data in columns if they exist
        #only move stop higher
        # make it faster using this:https://stackoverflow.com/questions/27474921/compare-two-columns-using-pandas
        current_positions['stop_price'] = np.vectorize(exits_helper)(current_positions['stop_price'], current_positions['temp_stop_price'])
    else:
        current_positions["stop_price"]=current_positions["temp_stop_price"]
    del current_positions["temp_stop_price"]

    return current_positions

# Calculate the volatility:

def get_stop(symbol, end_date, ema_period, atr_period, stop_factor=3):
    '''
    should really have a description of the function here
    calculates the Exponential Moving Average of the Average True Range. Designed so that it can be iterated through via numpy vectorize

    #  Volatility of the market is determined by a 10-day Exponential Moving Average of the Average True Range
    # Trailing stop at distance from the close 3-times the volatility
    # The stop could only move in the direction of the trade
    '''
    period = max(ema_period, atr_period)*2
    offset_days = -(period+((period//7)*2)+(period%7)+2)*2
    start_date = end_date + timedelta(days = offset_days)
    # Unneccessary formatting
    start_date = datetime.strftime(start_date, "%Y-%m-%d")
    end_date = datetime.strftime(date.today(), "%Y-%m-%d")
    # Get Symbol Data
    df = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}?unadjusted=false&sort=asc&apiKey={alpaca_live}").json().get("results")

     #shove it in a dataframe real quick:
    df = pd.DataFrame.from_dict(df)

    df = ATR(df, atr_period, ohlc=["o","h","l","c"])

    df = EMA(df, "ATR", "EMA",ema_period)
    max_date_row = df.loc[df["t"]==(df["t"].max())]
    max_date_row.reset_index(inplace = True)
    smoothed_final_ema = max_date_row["EMA"][0]
    stop_price = max_date_row["c"][0]-(smoothed_final_ema*stop_factor)


    return stop_price

def EMA(df, base, target, period, alpha=False):
    """
    Function to compute Exponential Moving Average (EMA)
    https://github.com/arkochhar/Technical-Indicators/blob/master/indicator/indicators.py
    Args :
        df : Pandas DataFrame which contains ['date', 'open', 'high', 'low', 'close', 'volume'] columns
        base : String indicating the column name from which the EMA needs to be computed from
        target : String indicates the column name to which the computed data needs to be stored
        period : Integer indicates the period of computation in terms of number of candles
        alpha : Boolean if True indicates to use the formula for computing EMA using alpha (default is False)
        
    Returns :
        df : Pandas DataFrame with new column added with name 'target'
    """
    period = int(period)
    con = pd.concat([df[:period][base].rolling(window=period).mean(), df[period:][base]])
    
    if (alpha == True):
        # (1 - alpha) * previous_val + alpha * current_val where alpha = 1 / period
        df[target] = con.ewm(alpha=1 / period, adjust=False).mean()
    else:
        # ((current_val - previous_val) * coeff) + previous_val where coeff = 2 / (period + 1)
        df[target] = con.ewm(span=period, adjust=False).mean()
    
    df[target].fillna(0, inplace=True)
    return df


def ATR(df, period, ohlc=['Open', 'High', 'Low', 'Close']):
    """
    Function to compute Average True Range (ATR)
    https://github.com/arkochhar/Technical-Indicators/blob/master/indicator/indicators.py
    Args :
        df : Pandas DataFrame which contains ['date', 'open', 'high', 'low', 'close', 'volume'] columns
        period : Integer indicates the period of computation in terms of number of candles
        ohlc: List defining OHLC Column names (default ['Open', 'High', 'Low', 'Close'])
        
    Returns :
        df : Pandas DataFrame with new columns added for 
            True Range (TR)
            ATR (ATR_$period)
    """
    atr = 'ATR'

    # Compute true range only if it is not computed and stored earlier in the df
    if not 'TR' in df.columns:
        df['h-l'] = df[ohlc[1]] - df[ohlc[2]]
        df['h-yc'] = abs(df[ohlc[1]] - df[ohlc[3]].shift())
        df['l-yc'] = abs(df[ohlc[2]] - df[ohlc[3]].shift())
         
        df['TR'] = df[['h-l', 'h-yc', 'l-yc']].max(axis=1)
         
        df.drop(['h-l', 'h-yc', 'l-yc'], inplace=True, axis=1)

    # Compute EMA of true range using ATR formula after ignoring first row
    EMA(df, 'TR', atr, period, alpha=True)
    
    return df



##################################
def get_positions(df = None):
    print('getting positions')
    '''
    This function updates the positions Dataframe, the old positions dataframe can be passed as an argument or it will be searched for using the REST API
    '''
    if df is not None:
        old_positions = df
    else:
        try:
            old_positions = pd.read_pickle(keys.positions_path / 'old_positions')
        except:
            print("old_positions pickled table not found")
            old_positions = None
            pass
    positions = (api.list_positions())
    new_positions = pd.DataFrame({
    # 'asset_class': [x.asset_class for x in positions],
    # 'assset_id': [x.assset_id for x in positions],
    'symbol': [x.symbol for x in positions],
    'qty': [x.qty for x in positions],
    'avg_entry_price': [x.avg_entry_price for x in positions],
    'change_today': [x.change_today for x in positions],
    'cost_basis': [x.cost_basis for x in positions],
    'current_price': [x.current_price for x in positions],
    'exchange': [x.exchange for x in positions],
    'lastday_price': [x.lastday_price for x in positions],
    'market_value': [x.market_value for x in positions],
    'side': [x.side for x in positions],
    'unrealized_intraday_pl': [x.unrealized_intraday_pl for x in positions],
    'unrealized_intraday_plpc': [x.unrealized_intraday_plpc for x in positions],
    'unrealized_pl': [x.unrealized_pl for x in positions],
    })
    new_positions.set_index('symbol')

    #  if old positions has data, update the new positions and return it. 
    if( old_positions is not None):
        new_positions = old_positions.update(new_positions)
    new_positions = old_positions
    return new_positions

#%%
class order():
# class keeps all the order types tidy

    def limit_sell(symbol, qty, price):
        try:
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='stop',
                stop_price = price,
                time_in_force='gtc'
            )
        except Exception as e:
                print(f"Limit Sell Failed with exception: {e}")
                return

    def sell(symbol, qty):
        try:
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side='sell',
                type='market',
                time_in_force='gtc'
            )
        except Exception as e:
                print(f"sell failed with exception: {e}")
                return

    def buy(symbol, qty):
        try:
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
        except Exception as e:
                print(f"buy failed with exception: {e}")
                return
    
    def oco(symbol, qty, stop_price, limit_price):
        try:
            api.submit_order(
                side= "buy",
                symbol= symbol,
                type= "market",
                qty= qty,
                time_in_force= "gtc",
                order_class= "bracket",
                take_profit= dict(
                    limit_price = limit_price
                ),
                stop_loss= dict(
                    stop_price= stop_price,
                    limit_price= stop_price
                )
            )
        except Exception as e:
                print(f"OCO order failed with exception: {e}")
                return


#%%

def orderer(df, long_market_value, cash):
    '''
    scans the positions df and places orders to fill in the gaps.
    '''
    #first, see if there are any positions:
    if (df['qty'].notnull().values.any()==True):
        # if there are positions, make a seperate df with only positions:
        active_positions = df[df['qty'].notnull()]
        # if RSI level is above top limit, sell
        rsi_upper_exceeded = active_positions.loc[active_positions["optimal_rsi_upper"]<=active_positions["RSI_current"]]
        if rsi_upper_exceeded.empty == False:
            np.vectorize(order.sell)(rsi_upper_exceeded['symbol'], rsi_upper_exceeded['qty'])
        # update all trailing limit orders with new prices
        np.vectorize(order.limit_sell)(active_positions["symbol"], active_positions['qty'], active_positions["stop_price"])

    # if there is no quantity of a position, open an order to acquire it
    # This is designed so that in the future multiple new positions can be added
    new_positions = df[df['qty'].isnull()]
    # reset index so it can be iterated
    new_positions.reset_index(inplace=True)

    if len(new_positions)>0:
        #THis might be too simple, bit this just gets the highest alpha strategy, and buys that one. 
        #need to size the purchase orders appropriately...
        # each asset aims to be approx 10% of portfolio at purchase. 
        # get appropriate purchase value:
        equity = long_market_value+cash
        purchase_cash = (equity*.1)
        # find number of shares which can be purchased with that amount
        askprice = api.get_last_quote(new_positions['symbol'][0]).askprice
        shares = purchase_cash//askprice
        # Find the correct lower stop price for the oco order:
        get_stop(new_positions["symbol"][0], date.today(), new_positions["optimal_rsi_period"][0], (new_positions["optimal_rsi_period"][0]*2),stop_factor=3)
        order.buy(new_positions['symbol'][0],shares)
        
    return df
#%%
def most_recent_weekday():
    '''
    does what it says on th tin
    '''
    today = date.today()
    day_of_week = today.weekday()
    if day_of_week <5:
        return date.today()
    else:
        time_delta = timedelta(today.weekday()-7)
        most_recent = today - time_delta
  
    return most_recent

#%%
if __name__ == "__main__":
    print(f"started live trader working directory:{os.getcwd()}")
    most_recent_weekday = most_recent_weekday()
    # # create empty current positions list:
    # current_positions = pd.DataFrame(columns=['symbol','qty','avg_entry_price','change_today','cost_basis','current_price','exchange','lastday_price','market_value','side','unrealized_intraday_pl','unrealized_intraday_plpc','unrealized_pl'])
 # First, cancel all existing orders for the Day
    # # get current positions
    new_positions = get_positions()

    api.cancel_all_orders()

    cash = float(api.get_account().cash)
    long_mkt_val = float(api.get_account().long_market_value)
    #then, determine if new acquisitions can occur
    equity = cash+long_mkt_val
    if cash > (equity*.1):
        #get opportunities:
        ### NEED FUNCTION TO GET MOST RECENT WEEKDAY
        backtest = fastquant3.run_strategy_generator(most_recent_weekday)
        # backtest = pd.read_pickle(keys.backtests_path /  "2020-11-03")
        backtest.set_index('symbol')
        buying_opp = get_entries(backtest)
        # make sure that the asset isn't already owned, then move the the second or third best option if it is, to encourage diversity
        i = 0
        while i <= len(buying_opp):
            if buying_opp["symbol"][i] not in new_positions.symbol.values:
                purchase = buying_opp.loc[i]
                break
            else:
                i=i+1
        # Update the final df
        # purchase.transpose
        new_positions = new_positions.append(purchase, verify_integrity=True, ignore_index=True)
    # current_positions.set_index('symbol')
    #%%
    
    #Update Stops
    new_positions = get_exits(new_positions)
    #update RSI
    if new_positions.empty == False:
        new_positions["RSI"] = np.vectorize(RSI_parser)(new_positions["symbol"],most_recent_weekday, new_positions["optimal_rsi_period"])
   
        # new_positions.loc[len(new_positions)] = purchase
    # then update stops and rsi, and place any necessary puchase orders:
    new_positions = orderer(new_positions, long_mkt_val, cash)
    new_positions.to_pickle(keys.positions_path / 'old_positions')
#%%
    # add any positions not already in current positions to it
    # current_positions = current_positions.append(positions_df)
    # dropping ALL duplicte values 
    # current_positions.drop_duplicates(subset = "symbol", keep = False, inplace = True) 


    # current_positions = current_positions.append(temp[0])
#%%

    # current_positions = requests.get(f"{api_base}/v2/positions", headers=headers).json()
    # current_positions = pd.DataFrame(current_positions)
    #get backtest data
    
    # Backtest = pd.read_pickle(f"Partial_Backtest_Save")

    # get_entries(Backtest)

#%%
#######

#%%
"""
get exits runs every day
Backtester runs when entries are needed
Get entries runs when entries are needed
"""
# docker build --pull --rm -f "Dockerfile" -t firstziplinealgo:latest "."