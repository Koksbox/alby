$(document).ready(function() {
    var currentPostUser = null;

    function checkPostUser() {
        $.getJSON('/api/?format=json&_=' + new Date().getTime(), function(data) {
            console.log('Полученные данные:', data);
            var newPostUser = data.post_user;
            if (currentPostUser === null) {
                currentPostUser = newPostUser;
                return;
            }
            if (newPostUser !== currentPostUser) {
                currentPostUser = newPostUser;
                if (newPostUser == 'manager') {
                    window.location.href = '/manager/';
                } else {
                    window.location.href = '/profile/';
                }
            }
        }).fail(function(jqxhr, textStatus, error) {
            console.error('Ошибка при вызове API:', textStatus, error);
        });
    }
    setInterval(checkPostUser, 3000);
});