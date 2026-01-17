import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List
from utils.logger import logger
from backtest.metrics import PerformanceMetrics

class EnsembleEngine:
    """
    量化多策略融合决策引擎

    物理意义：
    1. 权重分配：结合 Alpha(盈利能力)、Risk(稳定性)、IVP(风险平价) 与 Ortho(正交性)。
    2. 仓位管理：利用凯利公式(Kelly Criterion)解决“下注多少”的数学最优问题。
    3. 执行控制：通过换手阈值抑制(Turnover Suppression)过滤交易噪音。
    """

    def __init__(
        self, 
        target_risk_ratio: float = 0.6,     # 凯利缩放系数：1.0表示全额凯利，0.5表示半凯利(更稳健)
        max_leverage: float = 1.0,          # 最大杠杆限制：1.0即不允许融资买入
        is_long_only: bool = True,          # 是否仅限做多
        turnover_threshold: float = 0.05,   # 调仓阈值：仓位变动<5%时忽略执行，减少滑点损耗
        vol_sensitivity: float = 1.5,       # 波动率敏感度
        max_single_weight: float = 0.5      # 单策略最大权重
    ):
        self.target_risk_ratio = target_risk_ratio
        self.max_leverage = max_leverage
        self.is_long_only = is_long_only
        self.turnover_threshold = turnover_threshold
        self.vol_sensitivity = vol_sensitivity
        self.max_single_weight = max_single_weight
        self.eps = 1e-9


    def action(
        self, 
        strategy_results: Dict[str, Any], 
        current_pos: float = 0.0
    ) -> Dict[str, Any]:
        """
        核心决策入口
        :param strategy_results: 包含各策略 equity_df 和 perf 指标的字典
        :param current_pos: 当前实盘/模拟盘的仓位，用于换手抑制计算
        """
        if not strategy_results:
            logger.warning("Ensemble strategy error:data provided")
            return {}

        # 1. 数据预处理
        names = list(strategy_results.keys())
        trace = {name: {} for name in names}
        trace_summary = {}
        metrics_map = self._parse_metrics(strategy_results)
        returns_df = self._calculate_returns(strategy_results)
        
        # 2. 因子计算
        alpha_scores = self._compute_alpha_scores(metrics_map, trace)
        risk_scores = self._compute_risk_scores(metrics_map, trace)
        #state_mults = self._compute_state_multipliers(metrics_map)
        state_mults = self._compute_dynamic_state_multipliers(metrics_map, returns_df, trace)
        # [正交惩罚]：降低相关性高的策略权重，确保组合多样性
        ortho_penalty = self._compute_ortho_penalty(returns_df, trace)

        # [风险平价]：计算收益率波动率的倒数。物理意义：波动率越大，分配权重越低
        vol_penalty = 1.0 / (returns_df.std() * self.vol_sensitivity + self.eps)
        vol_weights = vol_penalty / vol_penalty.sum()

        # 3. 权重合成层
        weights_info = self._calculate_weights(
            names, 
            alpha_scores, 
            risk_scores, 
            state_mults, 
            ortho_penalty, 
            vol_weights,
            trace,
        )

        # 4. 凯利仓位计算层
        # [加权期望胜率 p]
        avg_p = sum(
            metrics_map[n].trade_win_rate * weights_info[n] 
            for n in names
        )
        # [加权期望盈亏比 b]：利用卡玛比率(Calmar)作为长期获利效率的代理变量
        avg_b = sum(
            (metrics_map[n].annual_return / (abs(metrics_map[n].max_drawdown) + 0.05)) 
            * weights_info[n]
            for n in names
        )
        
        # 凯利公式推导：f* = (p*b - q) / b，其中 q = 1-p
        # 物理意义：在已知胜率和赔率下，使长期收益对数增长率最大化的资产配置比例
        q = 1 - avg_p
        kelly_f = (avg_p * avg_b - q) / (avg_b + self.eps)

        # [OPT] 组合多样性折扣增强版
        diversity_score = 1
        if not returns_df.empty and returns_df.shape[1] > 0:
            returns_df = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float)
            corr_matrix = (returns_df + np.random.normal(0, self.eps, returns_df.shape)).corr(min_periods=1).fillna(0.0).abs()
            np.fill_diagonal(corr_matrix.values, 1.0)
            if corr_matrix.size > 0:
                diversity_score = 1.0 / (1.0 + np.clip(np.nanmean(corr_matrix.values), 0.0, 1.0) + self.eps)

        # 5. 信号融合与最终映射
        # 融合信号量 (-1.0 ~ 1.0)：代表各策略对当前方向的共识程度
        ensemble_signal = sum(
            float(strategy_results[n]['equity_df']['signal'].iloc[-1]) * weights_info[n]
            for n in names
        )
        # 如果置信度极低，非线性削减凯利值
        confidence_factor = np.tanh(abs(ensemble_signal) * 2) 
        
        trace_summary["avg_p"], trace_summary["avg_b"], trace_summary["kelly_f_orig"] = avg_p, avg_b, kelly_f
        trace_summary["diversity_score"] = diversity_score
        trace_summary["ensemble_signal"] = ensemble_signal
        trace_summary["confidence_factor"] = confidence_factor
         
        kelly_f = np.clip(kelly_f * diversity_score * confidence_factor, 0.0, 1.0)
        
        # 建议仓位 = 信号强度(确认度) * 凯利建议值(下注额度) * 风险偏好
        raw_pos_size = ensemble_signal * kelly_f * self.target_risk_ratio
        granularity = 0.05
        suggested_pos = round(np.clip(
            raw_pos_size, 
            0 if self.is_long_only else -self.max_leverage, 
            self.max_leverage
        ) / granularity) * granularity


        # 6. 执行逻辑判定
        # 换手抑制：如果新建议仓位与旧仓位差异极小，则维持现状(HOLD)，避免手续费摩擦
        exec_status = (
            "HOLD"
            if abs(suggested_pos - current_pos) < self.turnover_threshold
            else "EXECUTE"
        )

        trace_summary["kelly_f"] = kelly_f
        trace_summary["target_risk_ratio"] = self.target_risk_ratio
        trace_summary["raw_pos_size"] = raw_pos_size
        trace_summary["suggested_pos"] = suggested_pos
        trace_summary["current_pos"] = current_pos
        trace_summary["exec_status"] = exec_status 

        return self._format_report(
            ensemble_signal, 
            avg_p, 
            suggested_pos, 
            metrics_map, 
            ortho_penalty,
            exec_status,
            trace,
            trace_summary,
        )

    # --- 核心计算模块 ---

    def _parse_metrics(self, data: Dict) -> Dict[str, PerformanceMetrics]:
        return {
            name: (PerformanceMetrics(**data[name]['perf']) 
                   if isinstance(data[name]['perf'], dict) else data[name]['perf'])
            for name in data
        }

    def _calculate_returns(self, data: Dict) -> pd.DataFrame:
        """从权益曲线计算对数收益率，用于相关性分析"""
        series = {n: data[n]['equity_df']['equity'] for n in data}
        df_equity = pd.concat(series.values(), axis=1, keys=series.keys()).ffill().fillna(1.0)
        return np.log(df_equity / df_equity.shift(1)).replace([np.inf, -np.inf], np.nan).dropna()

    def _compute_alpha_scores(
            self, 
            m_map: Dict[str, PerformanceMetrics],
            trace
        ) -> Dict[str, float]:
        """慢因子定权，盈利分：年化* 交易胜率调权 * 样本置信度修正。交易次数太少的策略，Alpha 分数会被对数抑制 """
        confidence_count = 50
        scores = {}
        for n, m in m_map.items():
            reliability = np.log1p(m.trade_count) / np.log1p(confidence_count)
            # 交易胜率(按笔)：空缺时不参与修正，非空时>0.5增加权重，<0.5降低权重
            win_adj = m.trade_win_rate / 0.5 if m.trade_win_rate else 1.0
            alpha = float(m.annual_return * win_adj * reliability)
            scores[n] = alpha
            trace[n]["annual_return"] = m.annual_return
            trace[n]["win_adj"] = win_adj
            trace[n]["reliability"] = reliability
            trace[n]["alpha"] = alpha
        return scores

    def _compute_risk_scores(self, 
            m_map: Dict[str, PerformanceMetrics],
            trace,
        ) -> Dict[str, float]:
        """风险分：物理意义为单位回撤产生的持仓胜率回报。"""
        risks = {}
        for k, m in m_map.items():
            risks[k] = float((m.calmar_ratio if np.isfinite(m.calmar_ratio) else m.annual_return / 0.01) * (m.win_rate / 0.5))
            trace[k]['calmar_ratio'] = m.calmar_ratio
            trace[k]['risk'] = risks[k]
        return risks

    def _compute_state_multipliers(self, m_map: Dict[str, PerformanceMetrics]) -> Dict[str, float]:
        """状态乘子：实时监测策略最近交易的损益，实现“在线止损/扩利”。"""
        mults = {}
        for k, v in m_map.items():
            pnl = v.last_trade_pnl
            if pnl < -abs(v.max_drawdown * 0.5): mults[k] = 0.3 # 最近遭受重创，大幅降权保护
            elif pnl < 0: mults[k] = 0.8 # 最近亏损，谨慎调减
            elif pnl > 0.03: mults[k] = 1.2 # 正在主升浪，适度超配
            else: multk[k] = 1.0
        return mults

    def _compute_dynamic_state_multipliers(self, 
            m_map, 
            returns_df,
            trace
        ) -> Dict[str, float]:
        """
        改动点：将静态止损改为动态标准差止损
        物理意义：如果亏损超过了策略近期波动水平的 2 倍，则触发惩罚
        """
        mults = {}
        for n, m in m_map.items():
            recent_std = returns_df[n].tail(20).std() if n in returns_df else 0.02
            pnl = m.last_trade_pnl     
            # 动态阈值判断
            if pnl < -(recent_std * 2): mults[n] = 0.25 # 异常亏损，深扣
            elif pnl < 0: mults[n] = 0.8
            elif pnl > (recent_std * 1.5): mults[n] = 1.25 # 强势捕获
            else: mults[n] = 1.0
            trace[n]['recent_std'] = recent_std
            trace[n]['pnl'] = pnl
            trace[n]['state'] = mults[n]
        return mults

    def _compute_ortho_penalty(self, returns_df: pd.DataFrame, trace) -> pd.Series:
        """相关性稀释：物理意义是防止多个同质化信号共振导致风险过载。"""
        if returns_df.empty: return pd.Series(1.0, index=returns_df.columns)
        corr = returns_df.corr().abs().fillna(0)
        # penalty = 1 / 相关性总和。相关性越高（越趋近于1），penalty 越小
        # [OPT] 平滑处理，避免极端塌缩
        penalty = (1.0 / (1.0 + corr.mean())).clip(0.3, 1.0)
        for k, v in trace.items():
            v["penalty"] = penalty[k]
        return penalty

    def _calculate_weights(self, names, alpha, risk, state, ortho, vol, trace) -> Dict[str, Dict[str, float]]:
        """多因子加权：综合盈利能力、风险抗性、状态反馈、正交性与波动率"""
        scores, norm_scores = {}, {}
        for n in names:
            # 基础评分权重：50% 收益表现 + 50% 风险稳定性
            base = (alpha[n] * 0.5 + risk[n] * 0.5)
            # 综合调节因子
            val = base * state[n] * vol[n] * ortho[n]
            norm = max(0.0, float(val) if np.isfinite(val) else 0.0)
            trace[n]['vol'] = vol[n]
            scores[n] = norm
        
        total = sum(scores.values()) + self.eps
        scores = {k: min(v / total, self.max_single_weight) for k, v in scores.items()}
        total = sum(scores.values()) + self.eps
        for k, v in scores.items():
            scores[k] = v / total
            trace[k]["weight"] = scores[k]
        return scores


    # --- 报告与分析模块 ---

    def _format_report(self, sig, prob, pos, metrics, ortho_penalty, exec_status, trace, trace_summary) -> Dict:
        # 信号分类逻辑
        if sig < -0.2:
            label = "SELL/EXIT" if self.is_long_only else "STRONG_SELL"
        elif sig > 0.6: label = "STRONG_BUY"
        elif sig > 0.2: label = "BUY"
        else: label = "NEUTRAL"

        # 权重降序排列
        sorted_items = sorted(trace.items(), key=lambda x: x[1]['weight'] if isinstance(x[1], dict) else float('-inf'), reverse=True)
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": label,
            "signal_score": round(sig, 4),
            "confidence_score": f"{prob*100:.2f}%",
            "trade_execution": exec_status,
            "suggested_position": round(float(pos), 4),
            "trace_items": sorted_items,
            "trace_summary": trace_summary,
            "contribution_analysis": self._get_contribution_analysis(ortho_penalty),
            "dynamic_risk_management": self._get_risk_logic(metrics, sig),
            "action_guide": self._generate_text(sig, prob, pos, exec_status),
            "logic_interpretation": self._interpret_logic(sig, pos, prob),
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
                analysis.append(f"【稀释】{name} 策略同质化，权重削减 {dilution:.1f}%")
            elif penalty >= 0.75:
                analysis.append(f"【独立】{name} 提供独特 Alpha 信号，受相关性惩罚极小")
        return analysis

    def _get_risk_logic(self, m_map, ensemble_signal) -> List[str]:
        actions = []
        for n, m in m_map.items():
            if getattr(m, 'is_in_position', False):
                if m.last_trade_pnl < -abs(m.max_drawdown * 0.6):
                    actions.append(f"【紧急】{n} 严重亏损，建议平仓")
                if m.last_trade_pnl > m.annual_return * 0.2:
                    actions.append(f"【提醒】{n} 已达盈利目标，建议止盈")
        return actions if actions else ["组合运行稳健"]

    def _interpret_logic(self, sig, pos, prob) -> str:
        if abs(sig) > 0.5 and abs(pos) < 0.1:
            return "提示：信号极强但建议仓位低。原因：系统检测到策略间相关性过高或置信度处于临界点，触发风险稀释。"
        if prob < 0.2:
            return "提示：当前处于震荡期，共振胜率不足，凯利公式自动转入防御姿态。"
        return "提示：系统运行正常，仓位与信号强度匹配。"

    def _generate_text(self, sig, prob, pos, exec_status) -> str:
        if self.is_long_only and sig < -0.1:
            return f"风险：信号看空 ({float(sig):.2f})。由于不卖空，建议【全线空仓】避险"
        if abs(sig) < 0.2: return "状态：分歧期。建议观望"
        msg = "高胜率共振" if prob > 0.55 else "趋势跟随"
        direction = "买入" if sig > 0 else "做空"
        return f"结论：{msg}。建议{direction}仓位 {abs(float(pos)):.2%}"
