#!/usr/bin/env python3

from yahooquery import Ticker
from scipy import interpolate
from datetime import timedelta
from pandas import Timestamp

import numpy
import matplotlib.pyplot as plt
import argparse

def main():
    parser = argparse.ArgumentParser(
                        prog = 'options-implied-move',
                        description = 'Calculates the options implied move of a given stock symbol',
                        epilog = 'I don''t know what to write here')
    parser.add_argument('symbol', help='the symbol for which the options implied move will be calculated')   
    parser.add_argument('-e', '--expiration', required=False, help='the expiration date in the form YYYY-MM-DD of the option chain to be used to calculate the options implied move')
    parser.add_argument('-f', '--filter', required=False, help='filter out data points from transactions older than a given number of minutes ')
    parser.add_argument('-p', '--plot-data', required=False, help='plot all the data')

    args = parser.parse_args()

    symbol = args.symbol
    expirationDate = args.expiration

    ticker_data = Ticker(symbol)

    options_chain_data = ticker_data.option_chain

    myticker_options_chain=options_chain_data.loc[symbol]

    if expirationDate:
        try:
            next_expiration=Timestamp.fromisoformat(expirationDate)
            next_expiration_human_friendly=next_expiration.month_name()[0:3]+"{:02d}".format(next_expiration.day)
        except ValueError as err:
            print('Error parsing informed expiration: ', err)
            quit(1)
    else:
        # Now we will find the next options chain expiration after ER

        # Collect the option expirations by creating a set of unique values collected
        # from the vector of labels of the first indexing field ('expiration')
        # https://pandas.pydata.org/docs/user_guide/advanced.html#reconstructing-the-level-labels
        expirations = set(myticker_options_chain.index.get_level_values(0))

        # Find out the next expiration date
        next_expiration=min(expirations)
        next_expiration_human_friendly=next_expiration.month_name()[0:3]+"{:02d}".format(next_expiration.day)
    
    # Now that we know the next expiration, select calls and puts from the 
    # option chain expiring next, making sure options are sorted by strike:
    
    # Take only options prices from trades completed within the 30 Minutes 
    # prior to the most recent option trade received
    # Note: implement code to treat value passed through option -f / --filter

    next_calls = myticker_options_chain.loc[next_expiration, 'calls'].sort_values(by=['strike'])
    lastTradeDates=next_calls.lastTradeDate
    thirdy_minutes=timedelta(minutes=30)
    threshold=lastTradeDates.sort_values(ascending=False)[0]-thirdy_minutes
    next_calls=next_calls[lastTradeDates > threshold]

    next_puts = myticker_options_chain.loc[next_expiration, 'puts'].sort_values(by=['strike'])
    lastTradeDates=next_puts.lastTradeDate
    thirdy_minutes=timedelta(minutes=30)
    threshold=lastTradeDates.sort_values(ascending=False)[0]-thirdy_minutes
    next_puts=next_puts[lastTradeDates > threshold]

    myticket_price = ticker_data.price[symbol]
    regularMarketPrice = myticket_price['regularMarketPrice']

    fc = interpolate.interp1d(next_calls['strike'], next_calls['lastPrice'], fill_value='extrapolate')
    fp = interpolate.interp1d(next_puts['strike'], next_puts['lastPrice'], fill_value='extrapolate')

    atm_call = fc(regularMarketPrice)
    atm_put = fp(regularMarketPrice)

    optionsImpliedMove = (atm_call + atm_put) / regularMarketPrice

    fiv_c = interpolate.interp1d(next_calls['strike'], next_calls['impliedVolatility']*100, fill_value='extrapolate')
    fiv_p = interpolate.interp1d(next_puts['strike'], next_puts['impliedVolatility']*100, fill_value='extrapolate')

    print('Next Calls:')
    print('==================================================================================')
    print(next_calls)
    print('Next Puts:')
    print('==================================================================================')
    print(next_puts)

    print("                    Underlying: ${:.3f}".format(regularMarketPrice))
    print("                      ATM Call: ${:.3f}".format(atm_call))
    print("                       ATM Put: ${:.3f}".format(atm_put))
    print("                  ATM Straddle: ${:.3f}".format(atm_call + atm_put))
    print("Options Implied Move for {:s}: {:.3%}".format(next_expiration_human_friendly, optionsImpliedMove))
    print("                   ATM Call IV: {:.3%}".format(fiv_c(regularMarketPrice)/100))
    print("                    ATM Put IV: {:.3%}".format(fiv_p(regularMarketPrice)/100))

    # == Plot data ==
    xc = numpy.arange(  min(next_calls['strike']),
                        max(next_calls['strike']),
                        0.1)

    xp = numpy.arange(  min(next_puts['strike']),
                        max(next_puts['strike']),
                        0.1)
    y1 = fc(xc)
    y2 = fp(xp)
    y3 = fiv_c(xc)
    y4 = fiv_p(xp)

    fig, ax = plt.subplots()
    twin1 = ax.twinx()

    # strike range of next_calls and next_puts can be different, so make sure we 
    # cover all the range using min and max values of both Series:
    x = numpy.arange(   min(min(next_calls['strike']), min(next_puts['strike'])), 
                        max(max(next_calls['strike']), max(next_puts['strike'])),
                        0.1)

    p1, = ax.plot(xc, y1, 'g-', label="Call Options")
    p2, = ax.plot(xp, y2, 'r-', label="Put Options")
    p3, = twin1.plot(xc, y3, 'g--', label="Call Options IV")
    p4, = twin1.plot(xp, y4, 'r--', label="Put Options IV")

    ax.set_ylim(0, max(max(y1), max(y2)))
    twin1.set_ylim(0, max(max(y3), max(y4)))

    ax.set_xlabel('Strikes')
    ax.set_ylabel('Price (USD)', color='b')
    twin1.set_ylabel('IV %', color='b')

    # Vertical line at the underlying prince that spans the yrange.
    p5 = ax.axvline(x=regularMarketPrice, linewidth=1.5, color='b', ls='--', label='Underlying Price')

    ax.yaxis.label.set_color(p1.get_color())
    twin1.yaxis.label.set_color(p3.get_color())

    #ax.annotate('{:.3f}'.format(app.underlyingPrice),
    #            xy=(app.underlyingPrice, max(max(y1), max(y2))), xycoords='data')

    #ax.annotate('{:.3f}'.format(app.underlyingPrice),
    #            xy=(app.underlyingPrice, max(max(y1), max(y2))/2), xycoords='data',
    #            xytext=(0.8, 0.95), textcoords='axes fraction',
    #            arrowprops=dict(facecolor='black', shrink=0.05),
    #            horizontalalignment='left', verticalalignment='top')

    """
    ax.legend(handles=[p1, p2, p3, p4, p5], loc="right")

    plt.text((min(next_calls['strike']) + max(next_calls['strike']) ) / 2, max(max(y3), max(y4))*0.90, "Options Implied Move = {:.2%}".format(optionsImpliedMove), size=12, rotation=0.0,
            ha="center", va="center",
            bbox=dict(boxstyle="round",
                    ec=(1., 0.5, 0.5),
                    fc=(1., 0.8, 0.8),
                    ))

    plt.text((min(next_calls['strike']) + max(next_calls['strike']) ) / 2, max(max(y3), max(y4))*1.075, next_expiration_human_friendly + ' options Chain for $' + symbol, size=14, rotation=0.0,
            ha="center", va="center",
            bbox=dict(boxstyle="square",
                    ec=(0.3, 1.0, 0.3),
                    fc=(0.8, 1.0, 0.8),
                    ))

    plt.text((min(min(next_calls['strike']), min(next_puts['strike'])) + max(max(next_calls['strike']), max(next_puts['strike']))) / 2,
            max(max(y3), max(y4))*1.075,
            '$' + symbol + ' ' + next_expiration_human_friendly + " Options Implied Move = {:.2%}".format(optionsImpliedMove), size=14, rotation=0.0,
            ha="center", va="center",
            bbox=dict(boxstyle="round",
                    ec=(0.3, 1.0, 0.3),
                    fc=(0.8, 1.0, 0.8),
                    ))
    """

    ax.legend(handles=[p1, p2, p3, p4, p5], loc="best")

    fig.canvas.manager.set_window_title('yahooquery Options Implied Move Calculator')

    cell_text = []
    cell_text.append(['Underlying: ', '${:.2f}'.format(regularMarketPrice)])
    cell_text.append(['ATM Call: ', '${:.2f}'.format(atm_call)])
    cell_text.append(['ATM Put: ', '${:.2f}'.format(atm_put)])
    cell_text.append(['ATM Straddle: ', '${:.2f}'.format(atm_call + atm_put)])
    cell_text.append(['ATM Call IV (%): ', '{:.2f}'.format(fiv_c(regularMarketPrice))])
    cell_text.append(['ATM Put IV (%): ', '{:.2f}'.format(fiv_p(regularMarketPrice))])
    cell_text.append(['${:s} {:s} Options Implied Move (%): '.format(symbol, next_expiration_human_friendly), '+/-{:.2f}'.format(optionsImpliedMove*100)])

    # Add a table at the top of the axes
    the_table = plt.table(cellText=cell_text,
                          loc='top', edges='open', cellLoc='right', colWidths=[0.85, 0.15])
    the_table.scale(1, 1.2)
    plt.subplots_adjust(top=0.75)

    plt.savefig('impliedMove.png')
    plt.show()

if __name__ == "__main__":
    main()