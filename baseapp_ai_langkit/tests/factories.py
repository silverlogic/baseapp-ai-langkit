import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "default")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    # Dynamically add username if it exists in the model
    if "username" in get_user_model()._meta.get_fields():
        username = factory.Faker("user_name")

    class Meta:
        model = get_user_model()
