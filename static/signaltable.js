static function renderMatrix(strategies, currentDataStore) {
    let html = ""; 
    currentDataStore.forEach((row, rowIndex) => {
        html += `<tr><td class="sticky-date">${row.date}</td><td>${row.price}</td>`;
        strategies.forEach((stratName) => {
            const sig = row.signals[stratName] || "HOLD";
            let streak = calculateStreak(sig, rowIndex, stratName);
            let alertClass = ""; 
            let prefix = ""; 
            if (rowIndex === 0 && sig !== "HOLD" && streak >= CONFIG.minStreak) {
                alertClass = sig === "BUY" ? "pulse-buy" : "pulse-sell";
                prefix = streak >= CONFIG.strong_Streak ? "🔥 " : "✨ ";
            } 
            const icon = sig === 'BUY' ? '▲' : (sig === 'SELL' ? '▼' : '■');
            const streakLabel = (streak > 1) ? `<span class="streak-badge">(${streak}D)</span>` : ""; 
            html += `<td><span class="sig-tag ${sig.toLowerCase()} ${alertClass}">${prefix}${icon} ${sig}${streakLabel}</span></td>`;
        }); 
        html += "</tr>";
    }); 
    $('#matrixBody').html(html);
}
static function calculateStreak(sig, rowIndex, stratName) {
    let streak = 1;
    for (let k = rowIndex + 1; k < currentDataStore.length; k++) {
        if (currentDataStore[k].signals[stratName] === sig) {
            streak++;
        } else {
            break;
        } 
    } 
    return streak;
}
