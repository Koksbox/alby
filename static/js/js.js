document.addEventListener('DOMContentLoaded', () => {
            const positionInput = document.getElementById('positionInput');
            const dropdown = document.getElementById('dropdown');

            // Управление отображением выпадающего списка
            positionInput.addEventListener('click', (event) => {
                event.stopPropagation(); // предотвращает закрытие при клике в input
                toggleDropdown();
            });

            dropdown.addEventListener('click', (event) => {
                if (event.target.tagName === 'DIV') {
                    positionInput.value = event.target.textContent;
                    hideDropdown();
                }
            });

            // Скрываем выпадающий список при клике вне его области
            document.addEventListener('click', () => {
                hideDropdown();
            });

            function toggleDropdown() {
                dropdown.style.display = (dropdown.style.display === 'block') ? 'none' : 'block';
            }

            function hideDropdown() {
                dropdown.style.display = 'none';
            }
        });