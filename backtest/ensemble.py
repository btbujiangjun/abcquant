import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime
from utils.logger import logger
from backtest.metrics import PerformanceMetrics

class EnsembleEngine:
    """
    量化多策略融合决策引擎 (Professional v2.1)
    支持：原始分透出、权重降序排列、相关性稀释分析。
    """

    def __init__(
        self, 
        target_risk_ratio: float = 2.0, 
        max_leverage: float = 1.0,
        is_long_only: bool = True
    ):
        self.target_risk_ratio = target_risk_ratio
        self.max_leverage = max_leverage
        self.is_long_only = is_long_only
        self.eps = 1e-9

    def action(self, strategy_results: Dict[str, Any]) -> Dict[str, Any]:
        if not strategy_results:
            logger.warning("Emsemble strategy error:data provided")
            return {}

        names = list(strategy_results.keys())
        metrics_map = self._parse_metrics(strategy_results)
        returns_df = self._calculate_returns(strategy_results)
        
        # 因子计算
        alpha_scores = self._compute_alpha_scores(metrics_map)
        risk_scores = self._compute_risk_scores(metrics_map)
        state_mults = self._compute_state_multipliers(metrics_map)
        ortho_penalty = self._compute_ortho_penalty(returns_df)

        # 权重合成 (返回包含 orig_score 的字典)
        weights_info = self._calculate_weights(
            names, alpha_scores, risk_scores, state_mults, ortho_penalty
        )

        # 信号融合
        ensemble_signal = sum(
            float(strategy_results[n]['equity_df']['signal'].iloc[-1]) * weights_info[n]['norm_score'] 
            for n in names
        )
        avg_prob = sum(metrics_map[n].trade_win_rate * weights_info[n]['norm_score'] for n in names)
        
        # 仓位映射
        raw_pos_size = np.tanh(ensemble_signal * (avg_prob / 0.5)) * self.max_leverage
        suggested_pos = max(0.0, raw_pos_size) if self.is_long_only else raw_pos_size

        return self._format_report(
            ensemble_signal, avg_prob, suggested_pos, weights_info, metrics_map, ortho_penalty
        )

    # --- 核心计算模块 ---

    def _parse_metrics(self, data: Dict) -> Dict[str, PerformanceMetrics]:
        return {
            name: (PerformanceMetrics(**data[name]['perf']) 
                   if isinstance(data[name]['perf'], dict) else data[name]['perf'])
            for name in data
        }

    def _calculate_returns(self, data: Dict) -> pd.DataFrame:
        series = {n: data[n]['equity_df']['equity'] for n in data}
        df_equity = pd.concat(series.values(), axis=1, keys=series.keys()).ffill().fillna(1.0)
        returns = np.log(df_equity / df_equity.shift(1)).replace([np.inf, -np.inf], np.nan)
        return returns.dropna()

    def _compute_alpha_scores(self, m_map: Dict[str, PerformanceMetrics]) -> Dict[str, float]:
        scores = {}
        for n, m in m_map.items():
            reliability = np.log1p(m.trade_count) / np.log1p(200)
            win_adj = m.trade_win_rate / 0.5 if m.trade_win_rate else 1.0
            scores[n] = float(m.annual_return * win_adj * reliability)
        return scores

    def _compute_risk_scores(self, m_map: Dict[str, PerformanceMetrics]) -> Dict[str, float]:
        return {
            n: float((m.calmar_ratio if np.isfinite(m.calmar_ratio) else m.annual_return / 0.01) 
                     * (m.win_rate / 0.5))
            for n, m in m_map.items()
        }

    def _compute_state_multipliers(self, m_map: Dict[str, PerformanceMetrics]) -> Dict[str, float]:
        mults = {}
        for n, m in m_map.items():
            pnl = m.last_trade_pnl
            if pnl < -abs(m.max_drawdown * 0.5): mults[n] = 0.3
            elif pnl < 0: mults[n] = 0.8
            elif pnl > 0.03: mults[n] = 1.2
            else: mults[n] = 1.0
        return mults

    def _compute_ortho_penalty(self, returns_df: pd.DataFrame) -> pd.Series:
        if returns_df.empty: return pd.Series(1.0, index=returns_df.columns)
        corr = returns_df.corr().fillna(0)
        # penalty = 1 / 相关性总和。相关性越高（越趋近于1），penalty 越小
        penalty = 1.0 / corr.abs().sum(axis=1)
        return penalty.replace([np.inf, -np.inf], 0).fillna(0)

    def _calculate_weights(self, names, alpha, risk, state, ortho) -> Dict[str, Dict[str, float]]:
        raw_scores = {}
        for n in names:
            base = (alpha[n] * 0.5 + risk[n] * 0.5)
            # 这里 ortho 决定了最终得分被稀释的程度
            val = base * state[n] * ortho[n]
            raw_scores[n] = max(0.0, float(val) if np.isfinite(val) else 0.0)
        
        total = sum(raw_scores.values()) + self.eps
        return {
            k: {
                "norm_score": v / total, 
                "orig_score": round(v, 4)
            } for k, v in raw_scores.items()
        }

    # --- 报告与分析模块 ---

    def _format_report(self, sig, prob, pos, weights_info, metrics, ortho_penalty) -> Dict:
        # 信号分类逻辑
        if sig < -0.2:
            label = "SELL/EXIT" if self.is_long_only else "STRONG_SELL"
        elif sig > 0.6: label = "STRONG_BUY"
        elif sig > 0.2: label = "BUY"
        else: label = "NEUTRAL"

        # 权重降序排列
        sorted_items = sorted(weights_info.items(), key=lambda x: x[1]['norm_score'], reverse=True)
        sorted_weights = {
            k: {"weight": round(v['norm_score'], 4), "orig_score": v['orig_score']} 
            for k, v in sorted_items
        }

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": label,
            "signal_score": round(sig, 4),
            "confidence_score": f"{abs(sig)*100:.2f}%",
            "suggested_position": round(float(pos), 4),
            "strategy_weights": sorted_weights,
            "contribution_analysis": self._get_contribution_analysis(ortho_penalty),
            "dynamic_risk_management": self._get_risk_logic(metrics, sig),
            "action_guide": self._generate_text(sig, prob, pos)
        }

    def _get_contribution_analysis(self, ortho_penalty: pd.Series) -> List[str]:
        """
        分析哪些策略因为同质化严重而被稀释
        """
        analysis = []
        # ortho_penalty 越小，稀释越严重。1.0 代表完全不稀释（独立性最高）
        for name, penalty in ortho_penalty.items():
            dilution = (1 - penalty) * 100
            if dilution > 50:
                analysis.append(f"【稀释】{name} 与其他策略高度同质化，权重已被削减 {dilution:.1f}%。")
            elif penalty >= 0.95:
                analysis.append(f"【独立】{name} 提供了独特的 Alpha 信号，受相关性惩罚极小。")
        return analysis

    def _get_risk_logic(self, m_map, ensemble_signal) -> List[str]:
        actions = []
        for n, m in m_map.items():
            if getattr(m, 'is_in_position', False):
                if m.last_trade_pnl < -abs(m.max_drawdown * 0.6):
                    actions.append(f"【紧急】{n} 严重亏损，建议平仓。")
                if m.last_trade_pnl > m.annual_return * 0.2:
                    actions.append(f"【提醒】{n} 已达盈利目标，建议止盈。")
        return actions if actions else ["组合运行稳健"]

    def _generate_text(self, sig, prob, pos) -> str:
        if self.is_long_only and sig < -0.1:
            return f"风险：信号看空 ({sig:.2f})。由于不卖空，建议【全线空仓】避险。"
        if abs(sig) < 0.2: return "状态：分歧期。建议观望。"
        msg = "高胜率共振" if prob > 0.55 else "趋势跟随"
        direction = "买入" if sig > 0 else "做空"
        return f"结论：{msg}。建议{direction}仓位 {abs(pos):.2%}。"
