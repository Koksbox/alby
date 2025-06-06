
    const form = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const photoDisplay = document.getElementById('photoDisplay');

    form.addEventListener('submit', function(event) {
        event.preventDefault(); // Останавливаем отправку формы
        const files = fileInput.files;

        // Очищаем предыдущие фото
        photoDisplay.innerHTML = '';

        for (let i = 0; i < files.length; i++) {
            const file = files[i];

            // Создаем объект URL для превью изображения
            const imgUrl = URL.createObjectURL(file);
            const imgElement = document.createElement('img');
            imgElement.src = imgUrl;

            // Добавляем изображение в контейнер
            photoDisplay.appendChild(imgElement);
        }
    });

        document.getElementById('uploadForm').onsubmit = function(event) {
    event.preventDefault(); // Предотвращаем перезагрузку страницы

    const formData = new FormData(this);

    fetch(window.location.href, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': '{{ csrf_token }}' // Добавьте csrf токен
        }
    })
    .then(response => response.text())
    .then(data => {
        // Обновляем содержимое photoDisplay с новыми данными
        document.getElementById('photoDisplay').innerHTML = newDOMString; // Замените это на правильный ответ сервера
    })
    .catch(error => console.error('Ошибка:', error));
};

function removePhoto(photoId) {
    // Представьте, что вы нашли элемент изображения по его ID
    const photoElement = document.getElementById(`photo-${photoId}`);
    if (photoElement) {
        photoElement.remove(); // Удаляем элемент из DOM
    }
}