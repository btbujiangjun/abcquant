const CONFIG = { 
    strategies: [], 
    minStreak: 3,
    strong_Streak: 5,
};


class UI {
    constructor() {
        this.currentDataStore = [];
    }

    renderSignalMatrix(signals) {
        if (!Array.isArray(signals) || signals.length === 0) {
            $('#matrixBody').empty();
            return;
        }

        /* ---------- 1. 提取策略对象 ---------- */
        const strategies = signals.map(item => {
            return {
                key: item.strategy_class,
                name: item.strategy_name || item.strategy_class,
                perf: item.perf
            };
        });

        /* ---------- 2. 按 annual_return 排序 ---------- */
        strategies.sort((a, b) => (b.perf?.annual_return || 0) - (a.perf?.annual_return || 0));

        this.updateTableHeader(strategies)
        
        /* ---------- 3. 构建 matrixMap ---------- */
        const matrixMap = {};

        strategies.forEach(({ key: strategyKey, name }, idx) => {
            let equity_df = signals[idx].equity_df;
            if (!Array.isArray(equity_df)) return;

            equity_df.forEach(bar => {
                const date = typeof bar.date === "string" ? bar.date.split('T')[0] : bar.date;
                if (!matrixMap[date]) {
                    matrixMap[date] = {
                        date,
                        price: Number(bar.close || 0).toFixed(2),
                        signals: {}
                    };
                }

                const sig =
                    bar.signal === 1 ? 'BUY' :
                    bar.signal === -1 ? 'SELL' :
                    'HOLD';

                matrixMap[date][`signals`] = matrixMap[date][`signals`] || {};
                matrixMap[date].signals[strategyKey] = sig;
            });
        });

        /* ---------- 4. 构造 currentDataStore（日期降序） ---------- */
        this.currentDataStore = Object.values(matrixMap)
            .sort((a, b) => b.date.localeCompare(a.date));

        /* ---------- 5. 渲染 HTML ---------- */
        let html = '';
        this.currentDataStore.forEach((row, rowIndex) => {
            html += `<tr><td class="sticky-date">${row.date}</td><td>${row.price}</td>`;

            strategies.forEach(({ key }) => {
                const sig = row.signals[key] || 'HOLD';
                const streak = this.calculateStreak(sig, rowIndex, key);

                let alertClass = '';
                let prefix = '';
                if (rowIndex === 0 && sig !== 'HOLD' && streak >= CONFIG.minStreak) {
                    alertClass = sig === 'BUY' ? 'pulse-buy' : 'pulse-sell';
                    prefix = streak >= CONFIG.strong_Streak ? '🔥 ' : '✨ ';
                }

                const icon =
                    sig === 'BUY' ? '▲' :
                    sig === 'SELL' ? '▼' :
                    '■';
                const streakLabel = streak > 1 ? `<span class="streak-badge">(${streak}D)</span>` : '';

                html += `<td><span class="sig-tag ${sig.toLowerCase()} ${alertClass}">${prefix}${icon} ${sig}${streakLabel}</span></td>`;
            });

            html += '</tr>';
        });

        $('#matrixBody').html(html);
    }

    calculateStreak(sig, rowIndex, strategyKey) {
        let streak = 1;
        for (let i = rowIndex + 1; i < this.currentDataStore.length; i++) {
            if (this.currentDataStore[i].signals[strategyKey] === sig) streak++;
            else break;
        }
        return streak;
    }

    updateTableHeader(strategies) {
        const $header = $('#headerRow');
        const $stats  = $('#statsRow');

        $header.find('th:gt(1)').remove();
        $stats.empty();

        strategies.forEach(s => {
            const perf = s.perf || {};

            $header.append('<th>' + (s.strategy_class || s.key).replace(/Strategy/g, '') + '</th>');

            const totalDays  = perf.total_days || 0;
            const tradeDays  = perf.trade_days || 0;
            const emptyDays  = totalDays - tradeDays;

            const tradeRatio = totalDays > 0 ? tradeDays / totalDays : 0;
            const emptyRatio = totalDays > 0 ? emptyDays / totalDays : 0;

            // ===== 指标区 =====
            const html = [
                '<th class="stats-th">',

                this.renderStat('总收益',     this.fmt(perf.total_return, true, false)),
                this.renderStat('年化收益',   this.fmt(perf.annual_return, true)),
                this.renderStat('最大回撤',   this.fmt(perf.max_drawdown, true, false)),
                this.renderStat('盈亏比',     this.fmt(perf.profit_loss_ratio, false)),
                this.renderStat('夏普比率',   this.fmt(perf.sharpe_ratio, false)),
                this.renderStat('卡玛比率',   this.fmt(perf.calmar_ratio, false)),
                this.renderStat('按天胜率',   this.fmt(perf.win_rate, true)),
                this.renderStat('按笔胜率',   this.fmt(perf.trade_win_rate, true)),
                this.renderStat('交易笔数',   perf.trade_count ?? '-'),
                this.renderStat('持仓状态',   perf.current_position ?? '-'),
                this.renderStat('最近盈利',   this.fmt(perf.last_trade_pnl, true)),
                this.renderStat('交易天数',   totalDays),

                this.renderRatioStat(
                    '持仓天数',
                    tradeDays,
                    this.fmt(tradeRatio, true, false)
                ),

                this.renderRatioStat(
                    '空仓天数',
                    emptyDays,
                    this.fmt(emptyRatio, true, false)
                ),

                '</th>'
            ].join('');

            $stats.append(html);
        });
    }

    fmt(val, isPct = false, isCss = true){
        if (val == null) return '--';
        const v = isPct ? (val * 100).toFixed(2) + '%' : val.toFixed(2);
        const cls = isPct ? (val > 0 ? 'text-pos' : 'text-neg') : '';
        return isCss ? `<span class="${cls}">${v}</span>` : `<span>${v}</span>`;
    };

    renderStat(label, value) {
        return (
            '<div class="stat-item">' +
                '<span class="stat-label">' + label + '</span>' +
                '<span class="stat-value">' + value + '</span>' +
            '</div>'
        );
    }

    renderRatioStat(label, mainValue, ratioValue) {
        return (
            '<div class="stat-item">' +
                '<span class="stat-label">' + label + '</span>' +
                '<span class="stat-value">' +
                    mainValue + '(' + ratioValue + ')' +
                '</span>' +
            '</div>'
        );
    }

    static drawKellyGauge(element_id, value) {
        const canvas = document.getElementById(element_id);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const cx = canvas.width / 2;
        const cy = canvas.height - 20;
        const r = 100;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.beginPath();
        ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI);
        ctx.lineWidth = 12;
        ctx.strokeStyle = '#f1f5f9';
        ctx.stroke();

        if (value > 0) {
            ctx.beginPath();
            ctx.arc(cx, cy, r, Math.PI, Math.PI + Math.min(value, 1) * Math.PI);
            ctx.lineWidth = 12;
            const g = ctx.createLinearGradient(0, 0, canvas.width, 0);
            g.addColorStop(0, '#86efac');
            g.addColorStop(1, '#16a34a');
            ctx.strokeStyle = g;
            ctx.stroke();
        }

        const angle = Math.PI + Math.min(Math.max(value, 0), 1) * Math.PI;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle);

        ctx.beginPath();
        ctx.moveTo(0, -4);
        ctx.lineTo(r - 15, 0);
        ctx.lineTo(0, 4);
        ctx.fillStyle = '#1e293b';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
}

