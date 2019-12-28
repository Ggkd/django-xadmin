from django.conf.urls import url
from django.shortcuts import HttpResponse,render,redirect
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from stark.utils.page import Pagination
from django.db.models import Q
import copy
from django.db.models.fields.related import ManyToManyField,ForeignKey
from django.forms.models import ModelChoiceField


class ShowList(object):
    def __init__(self, config, data_list, request):
        self.config = config
        self.data_list = data_list
        self.request = request
        # 分页
        data_count = self.data_list.count()     # 获取数据总数量
        current_page = int(self.request.GET.get("page", 1))      # 获取当前页码
        base_url = self.request.path    # 获取url（不带参数）
        # 生成分页对象
        self.paginator = Pagination(current_page, data_count, base_url, self.request.GET, per_page_num=2, pager_count=11)
        # 当前页的数据列表
        self.page_data = self.data_list[self.paginator.start: self.paginator.end]
        # actions
        self.actions = self.config.new_actions()

    def get_filter_linktags(self):
        link_dict = {}         # 定义字段对应的a连接    {"book":["<a>金平..</a>", "<a>"], ...}

        for filter_field in self.config.filter_fields:  # 获取要过滤的字段 ["book", "author",..... ]
            url_params = copy.deepcopy(self.request.GET)  # 获取参数
            current_field_id = self.request.GET.get(filter_field, 0)   # 获取当前被选中的字段的id
            filter_field_obj = self.config.model._meta.get_field(filter_field)      # 获取字段对象
            if isinstance(filter_field_obj, ForeignKey) or isinstance(filter_field_obj, ManyToManyField):   # 如果字段对象是一对多或者多对多
                data_list = filter_field_obj.rel.to.objects.all()    # 根据字段对象获取该模型类的queryset对象["book1","book2",...]
            else:
                data_list = self.config.model.objects.all().values("pk", filter_field)     # 取普通字段的pk和该字段的所有数据
            temp = []   # 定义一个临时列表
            # all标签
            if url_params.get(filter_field):    # if GET请求参数中包含当前循环的字段，就把这个参数（字段）删除
                del url_params[filter_field]
                temp.append("<a href='?%s'>ALL</a>" % url_params.urlencode())
            else:   # 不存在就说明该字段没有被选中
                temp.append("<a class='active' href='#'>ALL</a>")
            # 数据标签
            for obj in data_list:
                # 继续判断，如果是一对多或者多对多，就用对象去获取pk和值
                if isinstance(filter_field_obj, ForeignKey) or isinstance(filter_field_obj, ManyToManyField):
                    pk = obj.pk
                    text = str(obj)
                    url_params[filter_field] = pk       # 字段作为键，pk作为值       ?publish=1&authors=2
                else:
                    pk = obj.get("pk")
                    text = obj.get(filter_field)
                    url_params[filter_field] = text     # 字段作为键，实际数据作为值     ?title="金平没"
                _url = url_params.urlencode()
                if current_field_id == str(pk) or current_field_id == text:
                    link_tag = "<a class='active' href='?%s'>%s</a>" % (_url, text)
                else:
                    link_tag = "<a href='?%s'>%s</a>" % (_url, text)
                temp.append(link_tag)
            link_dict[filter_field] = temp
        return link_dict

    # 获取action操作
    def get_actions_list(self):
        temp = []
        for action in self.actions:
            temp.append({
                "name": action.__name__,
                "desc": action.short_description
            })
        return temp

    def show_header(self):
        # 获取表头信息
        # 定义一个列表，格式：["复选框", name , age, "操作"....]
        head_list = []
        for field in self.config.new_list_display():  # [checkbox,__str__, name,age,edit,deletes......]
            if callable(field):
                val = field(self.config, header=True)
                head_list.append(val)
            else:
                if field == '__str__':
                    val = self.config.model._meta.model_name.upper()  # 返回模型类的名称
                else:
                    val = self.config.model._meta.get_field(field).verbose_name  # 获取字段的verbose_name，不存在就返回Model勒种定义的field名称
                head_list.append(val)
        return head_list

    def show_body(self):
        # 获取表单信息
        # 定义一个新的数据列表  格式：
        """
        [
            ["name", "age"]
            ["name", "age"]
            .......
        ]
        """
        new_data_list = []
        for obj in self.page_data:  # 获取data_list中的每一个对象
            temp = []  # 定义一个内层列表，存储一个对象所有字段的值
            for field in self.config.new_list_display():  # 获取每一个要展示的字段   ["name", "age"]
                if callable(field):  # 判断字段是否可被调用
                    val = field(self.config, obj)  # 给自定义方法传递参数
                else:
                    try:
                        field_obj = self.config.model._meta.get_field(field)
                        if isinstance(field_obj, ManyToManyField):
                            vals = getattr(obj, field).all()    # 获取所有数据
                            new_temp = []
                            for i in vals:
                                new_temp.append(str(i))
                            val = ",".join(new_temp)
                        else:
                            val = getattr(obj, field)  # field是字符串，利用反射获取对象每个字段的值，
                            if field in self.config.list_display_links:  # 判断字段是否在list_display_links中，
                                _url = self.config.get_change_url(obj)
                                val = mark_safe("<a href='%s'>%s</a>" % (_url, val))
                    except Exception as e:
                        val = getattr(obj, field)
                temp.append(val)
            new_data_list.append(temp)
        return new_data_list


class ModelStark(object):
    list_display = ["__str__"]
    list_display_links = []
    model_class = None
    search_fields = []
    actions = []
    filter_fields = []

    def __init__(self, model, site):
        self.model = model
        self.site = site

    # 批量删除
    def delete_action(self, request, queryset):
        queryset.delete()
    delete_action.short_description = "批量删除"

    """编辑按钮"""
    def edit(self, obj=None, header=False):
        if header:      # 判断是不是表头
            return "操作"
        _url = self.get_change_url(obj)
        return mark_safe("<a href='%s'>编辑</a>" % _url)

    """删除按钮"""
    def deletes(self, obj=None, header=False):
        if header:      # 判断是不是表头
            return "操作"
        _url = self.get_delete_url(obj)
        return mark_safe("<a href='%s'>删除</a>" % _url)

    """复选框"""
    def checkbox(self, obj=None, header=False):
        if header:      # 判断是不是表头
            return mark_safe("<input id='all_select' type='checkbox'>")
        return mark_safe("<input class='select' name='selected_id' type='checkbox' value='%s'>" % obj.pk)

    """获取编辑的url"""
    def get_change_url(self, obj):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_change" % (app_label, model_name), args=(obj.pk,))
        return _url

    """获取删除的url"""
    def get_delete_url(self, obj):
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_delete" % (app_label, model_name), args=(obj.pk,))
        return _url

    """获取添加的url"""
    def get_add_url(self):

        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_add" % (app_label, model_name))
        return _url

    """获取列表的url"""
    def get_list_url(self):

        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label
        _url = reverse("%s_%s_list" % (app_label, model_name))
        return _url

    # 获取所有的action
    def new_actions(self):
        temp = []
        temp.append(ModelStark.delete_action)
        temp.extend(self.actions)
        return temp

    # 获取被指定的所有字段
    def new_list_display(self):
        temp = []
        temp.append(ModelStark.checkbox)
        temp.extend(self.list_display)
        if not self.list_display_links:  # 判断是否指定了可点击的列
            temp.append(ModelStark.edit)
        temp.append(ModelStark.deletes)
        return temp

    # 获取定义的ModelFormDemo类
    def get_modelform_class(self):
        if not self.model_class:    # 如果用户为定义，返回默认的ModelFormDemo类名
            class ModelFormDemo(ModelForm):
                class Meta:
                    model = self.model
                    fields = "__all__"
            return ModelFormDemo
        else:   # 返回用户定义的ModelFormDemo类名
            return self.model_class

    # 添加视图
    def add_view(self, request):
        ModelFormDemo = self.get_modelform_class()   # 取到的是类名
        form_obj = ModelFormDemo()
        for bfield in form_obj:
            if isinstance(bfield.field, ModelChoiceField):  # bfield.field 获取的是字段对象；bfield.name 获取的是字段名称，类型是字符串；
                bfield.is_related = True
                # 获取该字段的模型表和模型表的app
                # bfield.field.queryset.model   一对多或者多对多字段的关联模型表
                relateed_model_name = bfield.field.queryset.model._meta.model_name
                relateed_app_label = bfield.field.queryset.model._meta.app_label
                _url = reverse("%s_%s_add" % (relateed_app_label, relateed_model_name))
                bfield.add_url = _url+"?pop_id=id_%s" % bfield.name         # id_%s 和select标签的id对应
        if request.method == "POST":
            form_obj = ModelFormDemo(request.POST)
            if form_obj.is_valid():
                obj = form_obj.save()
                pop_id = request.GET.get("pop_id")
                if pop_id:      # 判断是否为小窗口的添加
                    ret = {"pk": obj.pk, "value": str(obj), "pop_id": pop_id}
                    return render(request, 'pop.html', ret)
                else:
                    return redirect(self.get_list_url())
        return render(request, 'add_view.html', locals())

    # 删除视图
    def delete_view(self, request, id):
        list_url = self.get_list_url()
        if request.method == "POST":
            self.model.objects.get(pk=id).delete()
            return redirect(list_url)
        return render(request, 'delete_view.html', locals())

    # 编辑视图
    def change_view(self, request, id):
        ModelFormDemo = self.get_modelform_class()  # 取到的是类名
        edit_obj = self.model.objects.get(pk=id)
        if request.method == "POST":
            form_obj = ModelFormDemo(request.POST, instance=edit_obj)
            if form_obj.is_valid():
                form_obj.save()
                return redirect(self.get_list_url())
            else:
                return render(request, 'edit_view.html', locals())

        form_obj = ModelFormDemo(instance=edit_obj)
        return render(request, 'edit_view.html', locals())

    # 获取search关键字和search字段
    def get_search(self, request):
        key_word = request.GET.get("q", "")
        search_connection = Q()
        if key_word:
            key_word = key_word.strip()
            search_connection.connector = 'or'
            for field in self.search_fields:
                search_connection.children.append((field+"__contains", key_word))
        return key_word, search_connection

    # 过滤数据的查询条件
    def get_filter_data(self, request):
        filter_condition = Q()
        for field, pk in request.GET.items():
            if field in self.filter_fields:
                filter_condition.children.append((field, pk))
        return filter_condition

    """列表展示页"""
    def list_view(self, request):
        if request.method == "POST":
            action_name = request.POST.get("action")      # 获取执行的action名称
            id_list = request.POST.getlist("selected_id")   # 获取被选中的id
            action_func = getattr(self, action_name)    # 反射获取函数
            queryset = self.model.objects.filter(pk__in=id_list)    # 过滤被选中的查询集
            action_func(request, queryset)   # 执行action
            return redirect(self.get_list_url())

        # 获取search的key_word,Q对象
        key_word, search_connection = self.get_search(request)
        # 过滤
        filter_connection = self.get_filter_data(request)
        # 获取userinfo 的数据,并进行search过滤
        data_list = self.model.objects.all().filter(search_connection).filter(filter_connection)

        # 获取表头
        show_list = ShowList(self, data_list, request)
        head_list = show_list.show_header()
        # 获取表体
        new_data_list = show_list.show_body()
        # 获取添加的url
        add_url = self.get_add_url()
        return render(request, 'list.html', locals())

    def get_urls2(self):
        temp = []       # 添加每个app/model的增删改查url
        model_name = self.model._meta.model_name
        app_label = self.model._meta.app_label

        temp.append(url(r'^add/', self.add_view, name="%s_%s_add" % (app_label, model_name)))
        temp.append(url(r'^(\d+)/delete/', self.delete_view, name="%s_%s_delete" % (app_label, model_name)))
        temp.append(url(r'^(\d+)/change/', self.change_view, name="%s_%s_change" % (app_label, model_name)))
        temp.append(url(r'^$', self.list_view, name="%s_%s_list" % (app_label, model_name)))
        return temp

    @property
    def urls2(self):
        return self.get_urls2(), None, None


class StarkSite(object):
    def __init__(self):
        self._registry = {}

    def register(self, model, stark_class=None):
        if not stark_class:
            stark_class = ModelStark
        self._registry[model] = stark_class(model, self)

    def get_urls(self):
        temp = []
        for model, stark_class_obj in self._registry.items():
            model_name = model._meta.model_name
            app_label = model._meta.app_label
            # 添加路由
            # url(r'app01/user/',)
            temp.append(url(r'^%s/%s/' % (app_label, model_name), stark_class_obj.urls2))
        return temp

    @property
    def urls(self):
        return self.get_urls(), None, None


site = StarkSite()