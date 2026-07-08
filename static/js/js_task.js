 // Переключение формы добавления задачи
        const toggleTaskFormBtn = document.getElementById('toggleTaskFormBtn');
        const taskFormContainer = document.getElementById('taskFormContainer');
        toggleTaskFormBtn.addEventListener('click', function () {
            taskFormContainer.classList.toggle('active');
            toggleTaskFormBtn.textContent =
                taskFormContainer.classList.contains('active') ? 'Скрыть форму' : 'Добавить новую задачу';
        });

document.addEventListener("DOMContentLoaded", function () {
    const toggleTaskFormBtn = document.getElementById("toggleTaskFormBtn");
    const taskFormContainer = document.getElementById("taskFormContainer");

    toggleTaskFormBtn.addEventListener("click", () => {
        if (taskFormContainer.style.display === "none" || taskFormContainer.style.display === "") {
            taskFormContainer.style.display = "block";
        } else {
            taskFormContainer.style.display = "none";
        }
    });
});