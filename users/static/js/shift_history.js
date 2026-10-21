// The whole shift belongs to its start period, just like the server reports.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('shift-preview-data');
    if (!element) return;
    const data = JSON.parse(element.textContent);
    const formatTime = function (value) {
        const seconds = Math.max(0, Math.floor(value));
        return Math.floor(seconds / 3600) + ' ч ' +
            Math.floor((seconds % 3600) / 60) + ' м ' + (seconds % 60) + ' с';
    };
    const setText = function (id, value) {
        const node = document.getElementById(id);
        if (node) node.textContent = value;
    };
    const update = function () {
        const elapsed = Math.min(data.limit, Math.max(0, Date.now() / 1000 - data.start));
        setText('current-time', formatTime(elapsed));
        setText('current-salary', (elapsed / 3600 * data.rate).toFixed(2));
        setText('total-time', formatTime(data.base_seconds + (data.included ? elapsed : 0)));
        setText('total-salary', (data.base_salary + (data.included ? elapsed / 3600 * data.rate : 0)).toFixed(2));
    };
    update();
    window.setInterval(update, 1000);
});
