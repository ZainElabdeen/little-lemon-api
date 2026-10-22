import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def move_categories_to_table(apps, schema_editor):
    Category = apps.get_model("LittleLemonAPI", "Category")
    MenuItem = apps.get_model("LittleLemonAPI", "MenuItem")
    for item in MenuItem.objects.all():
        title = (item.category or "uncategorized").strip() or "uncategorized"
        category, _ = Category.objects.get_or_create(
            slug=slugify(title), defaults={"title": title}
        )
        item.category_ref = category
        item.save(update_fields=["category_ref"])


def move_categories_to_text(apps, schema_editor):
    MenuItem = apps.get_model("LittleLemonAPI", "MenuItem")
    for item in MenuItem.objects.select_related("category_ref"):
        item.category = item.category_ref.title if item.category_ref else ""
        item.save(update_fields=["category"])


def rename_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for old, new in (("manager", "Manager"), ("delivery_crew", "Delivery crew")):
        if Group.objects.filter(name=new).exists():
            continue
        Group.objects.filter(name=old).update(name=new)
        Group.objects.get_or_create(name=new)


def restore_group_names(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for old, new in (("manager", "Manager"), ("delivery_crew", "Delivery crew")):
        Group.objects.filter(name=new).update(name=old)


class Migration(migrations.Migration):

    dependencies = [
        ("LittleLemonAPI", "0002_create_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("title", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "ordering": ["title"],
                "verbose_name_plural": "categories",
            },
        ),
        migrations.AddField(
            model_name="menuitem",
            name="featured",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="menuitem",
            name="category_ref",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="LittleLemonAPI.category",
            ),
        ),
        migrations.RunPython(move_categories_to_table, move_categories_to_text),
        migrations.RemoveField(model_name="menuitem", name="category"),
        migrations.RenameField(model_name="menuitem", old_name="category_ref", new_name="category"),
        migrations.AlterField(
            model_name="menuitem",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="menu_items",
                to="LittleLemonAPI.category",
            ),
        ),
        migrations.RunPython(rename_groups, restore_group_names),
    ]
