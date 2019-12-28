from stark.service.stark import site, ModelStark
from .models import *
from django.forms import ModelForm, widgets as wid


class ModelFormDemo(ModelForm):
    class Meta:
        model = Book
        fields = "__all__"
        labels = {
            "title": "书籍名称",
            "price": "价格"
        }


class BookConfig(ModelStark):
    list_display = ["title", "price", "publishDate", "authors"]
    list_display_links = ["title"]
    model_class = ModelFormDemo
    search_fields = ["title", "price"]

    def edit_price_action(self, request, queryset):
        queryset.update(price=111)
    edit_price_action.short_description = "修改价格"
    actions = [edit_price_action]
    filter_fields = ["authors", "publish"]


site.register(Author)
site.register(Publish)
site.register(AuthorDetail)
site.register(Book,BookConfig)