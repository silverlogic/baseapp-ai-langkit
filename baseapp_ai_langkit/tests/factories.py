import factory
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "default")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    # Dynamically add username if it exists in the model
    if any(field.name == "username" for field in get_user_model()._meta.get_fields()):
        username = factory.Sequence(lambda n: f"test_user_{n}")

    class Meta:
        model = get_user_model()
