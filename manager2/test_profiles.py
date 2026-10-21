from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from users.role_utils import DIRECTOR_EMAIL

User = get_user_model()


class ExistingProfileAccessTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.manager = self.make_user("manager", "manager")
        self.junior = self.make_user("junior", "junior_manager")
        self.employee = self.make_user("employee", "employee")
        self.director = User.objects.create_user(email=DIRECTOR_EMAIL, password="password",
                                                  full_name="Director", is_active=True)

    def make_user(self, name, role):
        return User.objects.create_user(email=name + "-profile@test.com", password="password",
                                         full_name=name, post_user=role, is_active=True)

    def test_manager_employee_profile_keeps_existing_fields(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("profile_employee_manager", args=[self.employee.pk]))
        self.assertEqual(response.status_code, 200)
        for text in (self.employee.full_name, self.employee.email, "Ставка:", "Сбросить пароль"):
            self.assertContains(response, text)

    def test_manager_cannot_target_director_or_manager_via_employee_routes(self):
        self.client.force_login(self.manager)
        for target in (self.manager, self.director):
            for route in ("profile_employee_manager", "employee_shifts", "manager_user_statistic",
                          "edit_user_manager"):
                with self.subTest(target=target.pk, route=route):
                    response = self.client.get(reverse(route, args=[target.pk]))
                    self.assertEqual(response.status_code, 404)

    def test_junior_does_not_gain_access_to_employee_statistics(self):
        self.client.force_login(self.junior)
        response = self.client.get(reverse("manager_user_statistic", args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)

    def test_director_can_view_employee_and_manager_profiles(self):
        self.client.force_login(self.director)
        for target in (self.employee, self.manager):
            self.assertEqual(self.client.get(reverse("profile_employee", args=[target.pk])).status_code, 200)

    def test_missing_manager_edit_page_returns_existing_profile(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("edit_user_manager", args=[self.employee.pk]))
        self.assertRedirects(response, reverse("profile_employee_manager", args=[self.employee.pk]))

    def test_contact_update_cannot_change_employee_role_or_rate(self):
        self.client.force_login(self.manager)
        self.client.post(reverse("edit_user_manager", args=[self.employee.pk]), {
            "full_name": "Updated", "post_user": "senior_manager", "big_stavka": "999",
        })
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, "Updated")
        self.assertEqual(self.employee.post_user, "employee")
        self.assertEqual(self.employee.big_stavka, 0)

    def test_director_partial_profile_edit_preserves_optional_fields_and_rate(self):
        self.employee.phone_number = "123456789"
        self.employee.big_stavka = 175
        self.employee.save()
        self.client.force_login(self.director)
        response = self.client.post(reverse("edit_user", args=[self.employee.pk]), {
            "full_name": "Updated by director", "big_stavka": "",
        })
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, "Updated by director")
        self.assertEqual(self.employee.phone_number, "123456789")
        self.assertEqual(self.employee.post_user, "employee")
        self.assertEqual(self.employee.big_stavka, 175)

    def test_director_role_change_uses_existing_default_rate_rule(self):
        self.employee.big_stavka = 175
        self.employee.save()
        self.client.force_login(self.director)
        response = self.client.post(reverse("edit_user", args=[self.employee.pk]), {
            "post_user": "specialist", "big_stavka": "",
        })
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.post_user, "specialist")
        self.assertEqual(self.employee.big_stavka, 180)
