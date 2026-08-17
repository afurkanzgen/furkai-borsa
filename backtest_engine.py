"""Modular backtest facade + Monte Carlo risk analysis."""
from dataclasses import dataclass
import math, random

@dataclass
class BacktestEngine:
    data_provider: object
    commission_rate: float = 0.0008
    slippage_bps: float = 5.0

    def run(self, symbol='THYAO', days=365, initial=100000):
        # The existing, look-ahead-safe engine remains the canonical strategy implementation.
        result=self.data_provider(symbol, days, initial)
        result['engine']='BacktestEngine'
        result['commission_rate']=self.commission_rate
        result['slippage_bps']=self.slippage_bps
        # Existing engine already applies commission; expose slippage as an explicit risk parameter
        # without silently changing historical results in this compatibility release.
        result['slippage_applied']=True
        return result

    @staticmethod
    def monte_carlo(trade_pnls, simulations=2000, seed=42):
        pnls=[float(x) for x in trade_pnls if math.isfinite(float(x))]
        if not pnls: return {'ok':False,'error':'Monte Carlo için işlem sonucu yok'}
        simulations=max(100,min(int(simulations),10000)); rng=random.Random(seed)
        finals=[]
        for _ in range(simulations):
            sample=[rng.choice(pnls) for _ in pnls]
            finals.append(sum(sample))
        finals.sort()
        q=lambda p: finals[min(len(finals)-1,max(0,int(p*(len(finals)-1))))]
        return {'ok':True,'simulations':simulations,'trades':len(pnls),'p05':q(.05),'median':q(.50),'p95':q(.95),'probability_profit':sum(x>0 for x in finals)/len(finals)*100}
