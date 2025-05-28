from django.conf import settings
from django.contrib import admin


def get_model_admin_classes():
    """
    Returns appropriate admin classes based on whether 'unfold' is installed.
    If unfold is available, use its enhanced admin classes, otherwise fallback to Django's default admin classes.
    """
    try:
        if "unfold" in settings.INSTALLED_APPS:
            from unfold.admin import (
                AllValuesFieldListFilter,
                BooleanFieldListFilter,
                ChoicesFieldListFilter,
                DateFieldListFilter,
                FieldListFilter,
                ModelAdmin,
                RelatedFieldListFilter,
                RelatedOnlyFieldListFilter,
                SimpleListFilter,
                StackedInline,
                TabularInline,
            )
        else:
            raise ImportError("unfold not in INSTALLED_APPS")
    except ImportError:
        ModelAdmin = admin.ModelAdmin
        StackedInline = admin.StackedInline
        TabularInline = admin.TabularInline
        SimpleListFilter = admin.SimpleListFilter
        AllValuesFieldListFilter = admin.AllValuesFieldListFilter
        BooleanFieldListFilter = admin.BooleanFieldListFilter
        ChoicesFieldListFilter = admin.ChoicesFieldListFilter
        DateFieldListFilter = admin.DateFieldListFilter
        FieldListFilter = admin.FieldListFilter
        RelatedFieldListFilter = admin.RelatedFieldListFilter
        RelatedOnlyFieldListFilter = admin.RelatedOnlyFieldListFilter

    return {
        "ModelAdmin": ModelAdmin,
        "StackedInline": StackedInline,
        "TabularInline": TabularInline,
        "SimpleListFilter": SimpleListFilter,
        "AllValuesFieldListFilter": AllValuesFieldListFilter,
        "BooleanFieldListFilter": BooleanFieldListFilter,
        "ChoicesFieldListFilter": ChoicesFieldListFilter,
        "DateFieldListFilter": DateFieldListFilter,
        "FieldListFilter": FieldListFilter,
        "RelatedFieldListFilter": RelatedFieldListFilter,
        "RelatedOnlyFieldListFilter": RelatedOnlyFieldListFilter,
    }


admin_classes = get_model_admin_classes()

ModelAdmin = admin_classes["ModelAdmin"]
StackedInline = admin_classes["StackedInline"]
TabularInline = admin_classes["TabularInline"]
SimpleListFilter = admin_classes["SimpleListFilter"]
AllValuesFieldListFilter = admin_classes["AllValuesFieldListFilter"]
BooleanFieldListFilter = admin_classes["BooleanFieldListFilter"]
ChoicesFieldListFilter = admin_classes["ChoicesFieldListFilter"]
DateFieldListFilter = admin_classes["DateFieldListFilter"]
FieldListFilter = admin_classes["FieldListFilter"]
RelatedFieldListFilter = admin_classes["RelatedFieldListFilter"]
RelatedOnlyFieldListFilter = admin_classes["RelatedOnlyFieldListFilter"]
