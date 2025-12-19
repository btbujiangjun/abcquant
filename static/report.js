// 初始化
document.addEventListener('DOMContentLoaded',()=>{
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    document.getElementById("datePicker").value = yesterday.toISOString().slice(0, 10);
    load_report();
});
async function load_report() {
  const date = document.getElementById("datePicker").value;
  const interval = 30
  const resp = await fetch(`/api/report?date=${date}&interval=${interval}`);
  const data = await resp.json();
  render("report_table", data.data);
}

function render(tableBodyId, data) {
  const tbody = document.getElementById(tableBodyId);
  tbody.innerHTML = data;
}



