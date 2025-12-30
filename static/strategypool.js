$(document).ready(function() {
    const table = $('#strategy_pool_table').DataTable({
        "pageLength": 20,
    });

    $('#addForm').submit(function(e) {
        e.preventDefault();
        const formData = new FormData();
        formData.append('strategy_name', $('#strategy_name').val());
        formData.append('strategy_class', $('#strategy_class').val());
        formData.append('param_configs', $('#param_configs').val());

        fetch('/strategypool/add', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => location.reload());
    });

    $('#strategy_pool_table tbody').on('click', '.btn-del', function () {
        // 使用 $(this) 获取当前点击的那个按钮
        const id = $(this).attr('data-id'); 
        const name = $(this).attr('data-name');

        console.log("正在尝试删除:", id, name); // 调试用

        if (!id || !name) {
            alert("错误：无法获取策略信息");
            return;
        }

        if (confirm(`确定从策略库中永久删除 [${name}] 吗？`)) {
            fetch(`/strategypool/del/${id}`, { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        // 从 DataTable 对象中删除该行并重绘
                        table.row($(this).parents('tr')).remove().draw();
                    } else {
                        alert("删除失败: " + data.message);
                    }
                })
                .catch(err => console.error("网络错误:", err));
        }
    });
});


