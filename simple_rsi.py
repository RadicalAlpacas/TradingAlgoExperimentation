# https://github.com/ChakshuGupta13/technical-indicators-backtesting/blob/master/RSI.py
#%%
from datetime import datetime
import backtrader as bt
import alpaca_backtrader_api
import keys
import backtrader.analyzers as btanalyzers

# Your credentials here
ALPACA_API_KEY = keys.keys.get("alpaca")
ALPACA_SECRET_KEY = keys.keys.get("alpaca_secret")

"""
You have 3 options: 
 - backtest (IS_BACKTEST=True, IS_LIVE=False)
 - paper trade (IS_BACKTEST=False, IS_LIVE=False) 
 - live trade (IS_BACKTEST=False, IS_LIVE=True) 
"""
IS_BACKTEST = True
IS_LIVE = False
USE_POLYGON = True



class SmaCross1(bt.Strategy):
    def notify_fund(self, cash, value, fundvalue, shares):
        super().notify_fund(cash, value, fundvalue, shares)

    def notify_store(self, msg, *args, **kwargs):
        super().notify_store(msg, *args, **kwargs)
        self.log(msg)

    def notify_data(self, data, status, *args, **kwargs):
        super().notify_data(data, status, *args, **kwargs)
        print('*' * 5, 'DATA NOTIF:', data._getstatusname(status), *args)
        if data._getstatusname(status) == "LIVE":
            self.live_bars = True

    # list of parameters which are configurable for the strategy
    params = dict(
        pfast=10,  # period for the fast moving average
        pslow=30   # period for the slow moving average
    )

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime[0]
        dt = bt.num2date(dt)
        print('%s, %s' % (dt.isoformat(), txt))

    def notify_trade(self, trade):
        self.log("placing trade for {}. target size: {}".format(
            trade.getdataname(),
            trade.size))

    def notify_order(self, order):
        print(f"Order notification. status{order.getstatusname()}.")
        print(f"Order info. status{order.info}.")

    def stop(self):
        print('==================================================')
        print('Starting Value - %.2f' % self.broker.startingcash)
        print('Ending   Value - %.2f' % self.broker.getvalue())
        print('==================================================')

    def __init__(self):
        self.live_bars = False
        sma1 = bt.ind.SMA(self.data0, period=self.p.pfast)
        sma2 = bt.ind.SMA(self.data0, period=self.p.pslow)
        self.crossover0 = bt.ind.CrossOver(sma1, sma2)

    def next(self):
        if not self.live_bars and not IS_BACKTEST:
            # only run code if we have live bars (today's bars).
            # ignore if we are backtesting
            return
        # if fast crosses slow to the upside
        if not self.positionsbyname[symbol].size and self.crossover0 > 0:
            self.buy(data=data0, size=5)  # enter long

        # in the market & cross to the downside
        if self.positionsbyname[symbol].size and self.crossover0 <= 0:
            self.close(data=data0)  # close long position
#########################################
# Buy and hold strat: https://www.backtrader.com/blog/2019-06-13-buy-and-hold/buy-and-hold/
class BuyAndHold_1(bt.Strategy):
    def start(self):
        self.val_start = self.broker.get_cash()  # keep the starting cash

    def nextstart(self):
        # Buy all the available cash
        size = int(self.broker.get_cash() / self.data)
        self.buy(size=size)

    def stop(self):
        # calculate the actual returns
        self.roi = (self.broker.get_value() / self.val_start) - 1.0
        print('ROI:        {:.2f}%'.format(100.0 * self.roi))


##########################################
# Custom RSI Strat 
#%%
class BasicRSI(bt.Strategy):
    def notify_fund(self, cash, value, fundvalue, shares):
        super().notify_fund(cash, value, fundvalue, shares)

    def notify_store(self, msg, *args, **kwargs):
        super().notify_store(msg, *args, **kwargs)
        self.log(msg)

    def notify_data(self, data, status, *args, **kwargs):
        super().notify_data(data, status, *args, **kwargs)
        if self.p.verbose == True: 
             print('*' * 5, 'DATA NOTIF:', data._getstatusname(status), *args)
        if data._getstatusname(status) == "LIVE":
            self.live_bars = True
    # stuff that can be passed to the class: https://www.backtrader.com/docu/concepts/
    params = dict(
        verbose = False,
        data0 = "data0",
        symbol = "NA",
        rsi_period= 1,
        rsi_lower= 1,
        rsi_upper= 1
    )
    # The logging function for this strategy

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime[0]
        dt = bt.num2date(dt)
        print('%s, %s' % (dt.isoformat(), txt))

    def start(self):
        self.entering = 0
        self.start_val = self.broker.get_value()

    def notify_trade(self, trade):
        if self.p.verbose == True:
            self.log("placing trade for {}. target size: {}".format(
                trade.getdataname(),
                trade.size))

    def notify_order(self, order):
        if self.p.verbose == True:
            print(f"Order notification. status{order.getstatusname()}.")
            print(f"Order info. status{order.info}.")

    def stop(self):
        self.stop_val = self.broker.get_value()
        self.pnl_val = self.stop_val - self.start_val
        if self.p.verbose == True:
            print('==================================================')
            print('Starting Value - %.2f' % self.broker.startingcash)
            print('Ending   Value - %.2f' % self.broker.getvalue())
            print('==================================================')

    # Below is where all the decisions happen 
    def __init__(self):
        self.live_bars = False
        self.RSI = bt.ind.RelativeStrengthIndex(self.data0, period=self.p.rsi_period)
        # sma2 = bt.ind.SMA(self.data0, period=self.p.pslow)
        # self.crossover0 = bt.ind.CrossOver(sma1, sma2)

    def next(self):
        if not self.live_bars and not IS_BACKTEST:
            # only run code if we have live bars (today's bars).
            # ignore if we are backtesting
            return
        # If crosses RSI_UPPER, Sell
        if self.positionsbyname[self.p.symbol].size and self.RSI > self.p.rsi_upper:
            self.close(data=self.p.data0)  # close long position
        # If crosses RSI_Lower, buy
        if not self.positionsbyname[self.p.symbol].size and self.RSI < self.p.rsi_lower:
            self.buy(data=self.p.data0, size=1)  # enter long



##################
# used for running multiple distinct classes...https://www.backtrader.com/blog/posts/2016-10-29-strategy-selection/strategy-selection/
class StFetcher(object):
    _STRATS = [BasicRSI, BuyAndHold_1]

    def __new__(cls, *args, **kwargs):
        idx = kwargs.pop('idx')

        obj = cls._STRATS[idx](*args, **kwargs)
        return obj

#%%
def callable_rsi_backtest(symbol1, start_date, end_date, period, lower, upper, cash):

    # import logging
    # logging.basicConfig(format='%(asctime)s %(message)s', level=logging.info())
# Create a cerebro entity

    
    cerebro = bt.Cerebro()
    
    store = alpaca_backtrader_api.AlpacaStore(
        key_id= keys.keys.get("alpaca"),
        secret_key=keys.keys.get("alpaca_secret"),
        paper=not False,
        usePolygon=True
    )
    DataFactory = store.getdata  # or use alpaca_backtrader_api.AlpacaData

    data0 = DataFactory(dataname=symbol1,
                        historical=True,
                        fromdate=start_date,
                        todate=end_date,
                        timeframe=bt.TimeFrame.Days)

    # broker = store.getbroker()
    # cerebro.setbroker(broker)
    #DATA
    cerebro.adddata(data0)
    #STRATEGY
    cerebro.addstrategy(BasicRSI,verbose=False, data0 = data0, symbol=symbol1, rsi_period = period, rsi_lower = lower, rsi_upper = upper)
    # cerebro.addstrategy(BuyAndHold_1)
    # backtrader broker set initial simulated cash
    cerebro.broker.setcash(cash)

    # Apply Total, Average, Compound and Annualized Returns calculated using a logarithmic approach
    #ANALYZER
    cerebro.addanalyzer(btanalyzers.Returns, _name="returns")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="mysharpe")
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.TimeDrawDown, _name="timedraw")
    cerebro.addanalyzer(btanalyzers.TimeReturn, timeframe=bt.TimeFrame.NoTimeFrame, data = data0, _name="basereturn")

    # cerebro.optstrategy(StFetcher, idx=[0,1])
    theStrats = cerebro.run(cpu = 4)
    # Run the Buy n hold strat

    return theStrats[0]
# results.analyzers.mysharpe.get_analysis


returnedStrats = callable_rsi_backtest("AAPL",datetime(2019, 1, 1), datetime(2020, 10, 26),5, 30, 70,10000)
#%%


# if __name__ == '__main__':
    # import logging
    # logging.basicConfig(format='%(asctime)s %(message)s', level=logging.info())
    # setup params

    # # Create a cerebro entity
    # cerebro = bt.Cerebro()
    # cerebro.addstrategy(BasicRSI,rsi_period = 11,rsi_lower = 34,rsi_upper = 74)

    # store = alpaca_backtrader_api.AlpacaStore(
    #     key_id=ALPACA_API_KEY,
    #     secret_key=ALPACA_SECRET_KEY,
    #     paper=not IS_LIVE,
    #     usePolygon=USE_POLYGON
    # )

    # DataFactory = store.getdata  # or use alpaca_backtrader_api.AlpacaData
    # if IS_BACKTEST:
    #     data0 = DataFactory(dataname=symbol,
    #                         historical=True,
    #                         fromdate=datetime(2020, 1, 1),
    #                         todate=datetime(2020, 10, 11),
    #                         timeframe=bt.TimeFrame.Days)
    # else:
    #     data0 = DataFactory(dataname=symbol,
    #                         historical=False,
    #                         timeframe=bt.TimeFrame.Days,
    #                         backfill_start=True,
    #                         )
    #     # or just alpaca_backtrader_api.AlpacaBroker()
    #     broker = store.getbroker()
    #     cerebro.setbroker(broker)
    # cerebro.adddata(data0)

    # if IS_BACKTEST:
    #     # backtrader broker set initial simulated cash
    #     cerebro.broker.setcash(100000.0)

    #     # Apply Total, Average, Compound and Annualized Returns calculated using a logarithmic approach
    # cerebro.addanalyzer(btanalyzers.Returns, _name="returns")
    # cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="mysharpe")
    # cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    # cerebro.addanalyzer(btanalyzers.TimeDrawDown, _name="timedraw")

    # print('Starting Portfolio Value: {}'.format(cerebro.broker.getvalue()))
    # cerebro.run()
    # print('Final Portfolio Value: {}'.format(cerebro.broker.getvalue()))
    # cerebro.plot()



# %%

# %%