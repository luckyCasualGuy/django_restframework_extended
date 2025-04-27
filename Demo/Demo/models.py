from django.db import models


class SomeModel(models.Model):
    value = models.CharField(max_length=100, null=True, blank=True, db_column="VALUE")
    created_datae = models.DateTimeField(auto_now_add=True, db_column="CREATED_DATE")
    updated_date = models.DateTimeField(auto_now=True, db_column="UPDATED_DATE")

    class Meta:
        db_table = "SOME_MODEL"



class SomeOtherModel(models.Model):
    some_model = models.ForeignKey(SomeModel, on_delete=models.CASCADE, db_column="SOME_MODEL_ID")
    created_datae = models.DateTimeField(auto_now_add=True, db_column="CREATED_DATE")
    updated_date = models.DateTimeField(auto_now=True, db_column="UPDATED_DATE")

    class Meta:
        db_table = "SOME_OTHER_MODEL"



