import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy 
from freqtrade.strategy import timeframe_to_prev_date
import os
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.data.converter import order_book_to_dataframe
from talipp.indicators import EMA, SMA ,BB,RSI

from user_data.strategies.BinanceStream import BaseIndicator, OrderBook,BinanceStream


 
        
    
        
class CombinedBinHAndClucV4WS(BinanceStream):
    INTERFACE_VERSION = 2

    minimal_roi = {
        "0": 0.018
    }

    stoploss = -0.9 # effectively disabled.

    timeframe = '1h'
    compute_original=False
    # Sell signal
    use_sell_signal = True
    sell_profit_only = True
    sell_profit_offset = 0.001 # it doesn't meant anything, just to guarantee there is a minimal profit.
    ignore_roi_if_buy_signal = True

    # Trailing stoploss
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.007
    trailing_stop_positive_offset = 0.018

    # Custom stoploss
    use_custom_stoploss = False

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 50

    
   
    def init_indicators(self,pair_info):
        pair = pair_info.pair
        pair_info.bi=BaseIndicator(pair,timeframe="5m",currency="USDT")
        pair_info.bb_40=BB(40,2.0,input_indicator=pair_info.bi.c) #Attach BB to the base close indicator
        pair_info.bb20=BB(20,2.0,input_indicator=pair_info.bi.c) 
        pair_info.ema_slow=EMA(50,input_indicator=pair_info.bi.c)
        pair_info.volume_mean_slow=SMA(30,input_indicator=pair_info.bi.v)
        pair_info.rsi=RSI(9,input_indicator=pair_info.bi.c)
        pair_info.ob=OrderBook(pair,currency="USDT")
        pair_info.indicators_buy = False
        pair_info.ticker_buy =False
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
    def new_ticker(self,pair_info, candle):
        pair_info.ticker_buy=True    
        last_price = float(candle["c"]) 
        if last_price > pair_info.bi.c[-1][-1]:
            pair_info.ticker_buy = True
        else:
            pair_info.ticker_buy = False
            
       
    def new_ob(self,pair_info,depth_cache):
        delta_bid = 0.002
        delta_ask = 0.002
        ob_ratio = 1.3
        if  not pair_info.ticker_buy or not pair_info.indicators_buy:
            return 
        bids=np.array(depth_cache.get_bids())
        asks=np.array(depth_cache.get_asks())
        mid_price=(0.5*bids[0][0]+0.5*asks[0][0])

        bid_cut = mid_price - mid_price*delta_bid
        ask_cut = mid_price + mid_price*delta_ask
        bid_side=bids[bids[:,0]>bid_cut]
        ask_side=asks[asks[:,0]<ask_cut]
        wall_side=bid_side
        asum=ask_side[:,1].sum() 
        bsum=bid_side[:,1].sum() 
        if bsum > ob_ratio*asum:
            pair_info.buy()    
    
    def new_candle(self,pair_info):
        pair_info.indicators_buy=True    

        bbdelta = pair_info.bb_40[-1].cb - pair_info.bb_40[-1].lb
        close = pair_info.bi.c[-1][-1]
        close_prev=pair_info.bi.c[-2][-1]
        closedelta = abs(close - close_prev)
        tail = abs(pair_info.bi.c[-1][-1] - pair_info.bi.l[-1][-1]) 
        volume = pair_info.bi.v[-1][-1]
        
        buy_condition = ((  
            pair_info.bi.l[-2][0] > 0 
            and  bbdelta > (close* 0.0084)
            and  closedelta>(close * 0.0175) 
            and  tail < (bbdelta * 0.25) 
            and  close<pair_info.bb_40[-2].lb 
            and  close<pair_info.bi.c[-2][0] 
        )
        |
        (   close < pair_info.ema_slow[-1] 
            and  close < 0.985 * pair_info.bb20[-1].lb 
            and  volume < pair_info.volume_mean_slow[-2] * 20 
           
        ))
       
        if buy_condition:
           pair_info.indicators_buy = True
        else:
           pair_info.indicators_buy = False
            

        sell_condition=(
            close > pair_info.bb20[-1].ub and
            close_prev > pair_info.bb20[-2].ub and
            volume > 0 
        )

        if sell_condition:
            pair_info.sell()
    
  