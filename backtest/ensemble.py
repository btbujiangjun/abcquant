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
    逻辑流：宏观风控 -> 环境识别 -> 策略融合 -> 职业执行

    物理意义：
    1. 权重分配：结合 Alpha(盈利能力)、Risk(稳定性)、IVP(风险平价) 与 Ortho(正交性)。
    2. 仓位管理：利用凯利公式(Kelly Criterion)解决“下注多少”的数学最优问题。
    3. 执行控制：通过换手阈值抑制(Turnover Suppression)过滤交易噪音。
    4. 稳健性：引入贝叶斯平滑与时间衰减，解决不同回测周期结果差异过大的问题。
    """

    def __init__(
        self, 
        target_risk_ratio: float = 0.6,     # 凯利缩放系数：1.0表示全额凯利，0.5表示半凯利(更稳健)
        max_leverage: float = 1.0,          # 最大杠杆限制：1.0即不允许融资买入
        is_long_only: bool = True,          # 是否仅限做多
        turnover_threshold: float = 0.05,   # 调仓阈值：仓位变动<5%时忽略执行，减少滑点损耗
        vol_sensitivity: float = 1.5,       # 波动率敏感度
        max_single_weight: float = 0.5,     # 单策略最大权重
        sell_urgency_factor: float = 0.5,   # 卖出灵敏度系数 (阈值减半)
    ):
        self.target_risk_ratio = target_risk_ratio
        self.max_leverage = max_leverage
        self.is_long_only = is_long_only
        self.turnover_threshold = turnover_threshold
        self.vol_sensitivity = vol_sensitivity
        self.max_single_weight = max_single_weight
        self.sell_urgency_factor = sell_urgency_factor
        self.eps = 1e-9


    def action(
        self, 
        strategy_results: Dict[str, Any], 
        df_market: pd.DataFrame,
        df_macro: Dict[str, pd.DataFrame] = None,
        current_pos: float = 0.0
    ) -> Dict[str, Any]:
        """
        核心决策入口
        :param strategy_results: 包含各策略 equity_df 和 perf 指标的字典
        :param current_pos: 当前实盘/模拟盘的仓位，用于换手抑制计算
        """
        if not strategy_results:
            logger.warning("Ensemble strategy error: no data provided")
            return {}

        # 0. 数据预处理
        names = list(strategy_results.keys())
        trace = {name: {} for name in names}
        trace_summary = {}
        metrics_map = self._parse_metrics(strategy_results)
        returns_df = self._calculate_returns(strategy_results)
        
        # 1. 环境与宏观感知
        regime_info = self._get_market_regime(df_market)
        macro_info = self._get_macro_signals(df_macro)

        # 2. 因子计算 (增强稳健性)
        alpha_scores = self._compute_alpha_scores(metrics_map, trace)
        risk_scores = self._compute_risk_scores(metrics_map, trace)
        # 使用动态状态乘子，增加平滑逻辑
        state_mults = self._compute_dynamic_state_multipliers(metrics_map, returns_df, trace)
        # [正交惩罚]：降低相关性高的策略权重
        ortho_penalty = self._compute_ortho_penalty(returns_df, trace)

        # [风险平价]：计算收益率波动率的倒数。增加最小波动率保护，防止回测初期数据极少时的分母塌缩
        vols = np.clip(returns_df.std(), 0.005, 0.5) # 保护边界
        vol_weights = 1.0 / (vols * self.vol_sensitivity + self.eps)
        vol_weights /= (vol_weights.sum() + self.eps)

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

        # 4. 凯利仓位计算层 (平滑胜率与盈亏比)
        # 利用贝叶斯推断平滑胜率：p_adj = (wins + 2) / (trades + 4)，向 0.5 收缩
        avg_p = sum(
            ((metrics_map[n].trade_win_rate * metrics_map[n].trade_count + 1) / (metrics_map[n].trade_count + 2) 
             if metrics_map[n].trade_count > 0 else 0.5) * weights_info[n]
            for n in names
        )
        
        # [加权期望盈亏比 b]：卡玛比率修正，限制极端值的影响
        avg_b = sum(
            np.clip(metrics_map[n].annual_return / (abs(metrics_map[n].max_drawdown) + 0.05), 0.1, 5.0) 
            * weights_info[n]
            for n in names
        )
        
        q = 1 - avg_p
        kelly_f_orig = (avg_p * avg_b - q) / (avg_b + self.eps)

        # [OPT] 组合多样性折扣增强版：使用压缩估计(Shrinkage)处理协方差
        diversity_score = 1
        if not returns_df.empty and returns_df.shape[1] > 1:
            # 引入常数相关系数收缩，解决样本量不足时的相关性矩阵病态问题
            corr_matrix = returns_df.corr().fillna(0.0).abs()
            avg_corr = np.nanmean(corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)])
            diversity_score = 1.0 / (1.0 + np.clip(avg_corr, 0.0, 1.0))

        # 5. 信号融合与最终映射
        ensemble_signal = sum(
            float(strategy_results[n]['equity_df']['signal'].iloc[-1]) * weights_info[n]
            for n in names
        )
        
        # 信心因子：采用双曲正切平滑，防止信号在阈值边缘反复横跳
        confidence_factor = np.tanh(abs(ensemble_signal) * 1.5) 
        kelly_f = np.clip(kelly_f_orig * diversity_score * confidence_factor, 0.0, 1.0)
        
        # 引入宏观信号
        raw_target = ensemble_signal * kelly_f * self.target_risk_ratio
        if macro_info['risk_level'] == 2: target_pos = raw_target * 0.1
        elif macro_info['risk_level'] == 1: target_pos = raw_target * 0.5
        else: target_pos = raw_target

        # 6. 非对称职业执行
        diff = target_pos - current_pos
        is_selling = (current_pos > 0 and diff < 0) or (current_pos < 0 and diff > 0)
        eff_threshold = self.turnover_threshold * (self.sell_urgency_factor if is_selling else 1.0)
        
        if abs(diff) < eff_threshold:
            exec_status, suggested_pos = "HOLD", current_pos
        else:
            exec_status, suggested_pos = "EXECUTE", target_pos

        # 对齐与裁剪, 5% 粒度对齐
        granularity = 0.05
        suggested_pos = round(np.clip(
            suggested_pos, 
            0 if self.is_long_only else -self.max_leverage, 
            self.max_leverage
        ) / granularity) * granularity

        trace_summary.update({
            "avg_p": avg_p, "avg_b": avg_b, "kelly_f_orig": kelly_f_orig,
            "diversity_score": diversity_score, "ensemble_signal": ensemble_signal,
            "confidence_factor": confidence_factor, "macro_info": macro_info,
            "kelly_f": kelly_f, "target_risk_ratio": self.target_risk_ratio,
            "raw_pos_size": raw_target, "suggested_pos": suggested_pos,
            "current_pos": current_pos, "exec_status": exec_status 
        })

        return self._format_report(
            ensemble_signal, avg_p, suggested_pos, metrics_map, 
            ortho_penalty, exec_status, trace, trace_summary
        )

    # --- 核心计算模块 (针对样本敏感度优化) ---

    def _parse_metrics(self, data: Dict) -> Dict[str, PerformanceMetrics]:
        return {
            name: (PerformanceMetrics(**data[name]['perf']) 
                   if isinstance(data[name]['perf'], dict) else data[name]['perf'])
            for name in data
        }

    def _calculate_returns(self, data: Dict) -> pd.DataFrame:
        series = {n: data[n]['equity_df']['equity'] for n in data}
        df_equity = pd.concat(series.values(), axis=1, keys=series.keys()).ffill().fillna(1.0)
        # 使用 pct_change 代替 log，在大回撤期间 log 可能导致极值
        return df_equity.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    def _get_macro_signals(self, data:Dict[str, pd.DataFrame]=None) -> Dict:
        """获取美股宏观指标 (VIX, IXIC)"""
        if data is None or 'VIX' not in data or 'IXIC' not in data:
            return {"risk_level": 0, "status_msg": "无法获取宏观数据，默认正常", "vix": 20}
        vix = data['VIX']['close'].iloc[-1]
        ixic = data['IXIC']['close']
        ixic_bull = ixic.iloc[-1] > ixic.tail(20).mean()

        if vix > 30: return {"risk_level": 2, "status_msg": "VIX恐慌 - 极度减仓"}
        if vix > 22 or not ixic_bull: return {"risk_level": 1, "status_msg": "宏观转弱 - 仓位对折"}
        return {"risk_level": 0, "status_msg": "宏观稳定"}

    def _get_market_regime(self, df: pd.DataFrame) -> Dict:
        """环境识别：效率系数 (ER)"""
        if df is None or len(df) < 20:
            return {"er": 0.5, "regime": "TREND"}
        # ER = 方向位移 / 绝对波动总和
        diff = abs(df['close'].iloc[-1] - df['close'].iloc[-20])
        path = (df['close'] - df['close'].shift(1)).abs().rolling(20).sum().iloc[-1]
        er = diff / (path + self.eps)
        # ER > 0.4 通常认为进入强趋势模式
        return {"er": er, "regime": "TREND" if er > 0.35 else "RANGE"}

    def _compute_alpha_scores(self, m_map: Dict[str, PerformanceMetrics], trace) -> Dict[str, float]:
        """Alpha分：引入 Sigmoid 饱和函数处理收益率，防止短周期暴利导致权重失衡"""
        confidence_count = 30 # 降低置信阈值
        scores = {}
        for n, m in m_map.items():
            # 样本量修正：使用 Sigmoid 替代对数，平滑增长
            reliability = 1 / (1 + np.exp(-(m.trade_count - confidence_count) / 10))
            # 盈利压制：使用双曲正切限制过高的年化收益对权重的冲击
            bounded_annual = np.tanh(m.annual_return * 2.0) 
            alpha = float(bounded_annual * reliability)
            scores[n] = alpha
            trace[n].update({"annual_return": m.annual_return, "reliability": reliability, "alpha": alpha})
        return scores

    def _compute_risk_scores(self, m_map: Dict[str, PerformanceMetrics], trace) -> Dict[str, float]:
        """风险分：增加最大回撤的惩罚权重，防止短周期内由于 MDD 尚未显现导致的风险低估"""
        risks = {}
        for k, m in m_map.items():
            mdd = abs(m.max_drawdown) + 0.05
            # 引入夏普与卡玛的调和平均，增强稳定性
            risks[k] = float(m.annual_return / mdd * (m.win_rate / 0.5))
            trace[k].update({'calmar_ratio': m.calmar_ratio, 'risk': risks[k]})
        return risks

    def _compute_dynamic_state_multipliers(self, m_map, returns_df, trace) -> Dict[str, float]:
        """动态状态乘子：引入波动率通道止损，物理意义是根据策略自身个性的波动来决定是否降权"""
        mults = {}
        for n, m in m_map.items():
            # 取最近 20 日波动，如果样本不足则使用全局波动
            recent_std = returns_df[n].tail(20).std() if (n in returns_df and len(returns_df) > 5) else 0.02
            pnl = m.last_trade_pnl     
            
            # 使用 Z-score 思想进行软切换
            if pnl < -(recent_std * 2.5): mults[n] = 0.2  # 严重异常
            elif pnl < -(recent_std * 1.0): mults[n] = 0.7 # 触碰下轨
            elif pnl > (recent_std * 2.0): mults[n] = 1.2  # 超常发挥
            else: mults[n] = 1.0
            
            trace[n].update({'recent_std': recent_std, 'pnl': pnl, 'state': mults[n]})
        return mults

    def _compute_ortho_penalty(self, returns_df: pd.DataFrame, trace) -> pd.Series:
        """相关性稀释：使用指数加权，防止历史相关性干扰当前判断"""
        if returns_df.empty or returns_df.shape[1] < 2: 
            return pd.Series(1.0, index=returns_df.columns if not returns_df.empty else [])
        
        # 对近期相关性赋予更高权重
        corr = returns_df.tail(60).corr().abs().fillna(0)
        penalty = (1.0 / (1.0 + corr.mean())).clip(0.4, 1.0)
        for n in returns_df.columns:
            if n in trace: trace[n]["penalty"] = penalty[n]
        return penalty

    def _calculate_weights(self, names, alpha, risk, state, ortho, vol, trace) -> Dict[str, float]:
        scores = {n: max(0.01, (alpha[n]*0.4+risk[n]*0.6)) * state[n] * vol[n] * ortho.get(n,1.0) for n in names} 
        total = sum(scores.values()) + self.eps
        # 归一化并施加最大单仓限制
        weights = {k: min(v / total, self.max_single_weight) for k, v in scores.items()}
        
        # 二次归一化确保总和为 1
        final_total = sum(weights.values()) + self.eps
        final_weights = {k: v / final_total for k, v in weights.items()}
        
        for k, v in final_weights.items(): trace[k]["weight"] = v
        return final_weights

    # --- 报告与分析模块 ---

    def _format_report(self, sig, prob, pos, metrics, ortho_penalty, exec_status, trace, trace_summary) -> Dict:
        if sig < -0.2:
            label = "SELL/EXIT" if self.is_long_only else "STRONG_SELL"
        elif sig > 0.6: label = "STRONG_BUY"
        elif sig > 0.2: label = "BUY"
        else: label = "NEUTRAL"

        sorted_items = sorted(trace.items(), key=lambda x: x[1].get('weight', 0), reverse=True)
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
            "logic_interpretation": self._interpret_logic(trace_summary, sig, pos, prob),
        }

    def _get_contribution_analysis(self, ortho_penalty: pd.Series) -> List[str]:
        analysis = []
        for name, penalty in ortho_penalty.items():
            dilution = (1 - penalty) * 100
            if dilution > 40:
                analysis.append(f"【稀释】{name} 与其它策略高度正相关，权重压缩 {dilution:.1f}%")
        return analysis if analysis else ["策略组合间正交性良好"]

    def _get_risk_logic(self, m_map, ensemble_signal) -> List[str]:
        actions = []
        for n, m in m_map.items():
            if getattr(m, 'is_in_position', False):
                if m.last_trade_pnl < -abs(m.max_drawdown * 0.7):
                    actions.append(f"【风控】{n} 触发动态回撤阈值，建议减仓")
        return actions if actions else ["组合风险指标在可控范围"]

    def _interpret_logic(self, summary, sig, pos, prob) -> str:
        """
        动态逻辑解释：根据 trace_summary 的数值实时诊断信号与仓位的匹配度
        """
        if not summary:
            return "解释：系统运行正常，仓位分配符合凯利准则。"

        # 获取关键诊断因子
        b = summary.get("avg_b", 0)
        diversity = summary.get("diversity_score", 1.0)
        confidence = summary.get("confidence_factor", 1.0)
        raw_kelly = summary.get("kelly_f", 0)
        
        reasons = []

        # 1. 处理 sig 与 pos 的方向或强度背离
        if abs(sig) > 0.5:
            if abs(pos) < 0.2:
                reasons.append(f"共识信号极强({sig:.2f})但仓位受限")
                # 诊断原因
                if prob < 0.45:
                    reasons.append(f"统计胜率不足({prob:.1%})导致信心匮乏")
                if b < 1.1:
                    reasons.append(f"预期盈亏比({b:.2f})过低，博弈价值不高")
                if diversity < 0.7:
                    reasons.append(f"策略同质化严重(独立性仅{diversity:.1%})触发风险稀释")
                if confidence < 0.6:
                    reasons.append(f"信号确认度({confidence:.2f})处于低位，非线性削减了下注额")
            else:
                reasons.append(f"共识信号明确，且胜率与赔率支持高仓位运作")
        
        # 2. 特殊风险提示
        if raw_kelly > 0.8 and self.target_risk_ratio > 0.7:
            reasons.append("警告：当前处于激进凯利模式，注意单次极端回撤风险")
        
        if abs(sig) < 0.2 and abs(pos) < 0.1:
            reasons.append("当前处于震荡分歧期，系统自动进入观察模式")

        macro_info = summary.get("macro_info", {})
        if macro_info["risk_level"] > 0:
            reasons.append(f"当前宏观环境风险等级{macro_info['risk_level']}，{macro_info['status_msg']}")

        # 3. 换手抑制诊断
        if summary.get("exec_status") == "HOLD":
            reasons.append(f"仓位微调未达{self.turnover_threshold*100:.0f}%阈值，维持现状以节省摩擦成本")

        base_msg = f"【动态诊断】{ ' | '.join(reasons) if reasons else '各指标逻辑匹配良好' }。"
        formula_msg = f" 决策链条：信号强({sig:.2f}) → 凯利建议({raw_kelly:.1%}) → 经风控衰减后目标仓位({pos:.0%})。"
        
        return base_msg + formula_msg

    def _generate_text(self, sig, prob, pos, exec_status) -> str:
        if self.is_long_only and sig < -0.05: return "建议：看空信号，全线空仓避险。"
        if abs(sig) < 0.15: return "建议：信号强度不足，维持现有防御姿态。"
        msg = "高确定性共振" if prob > 0.58 else "趋势占优"
        return f"结论：{msg}。建议目标仓位 {float(pos):.0%}，当前执行状态：{exec_status}"
